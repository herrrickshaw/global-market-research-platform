#!/usr/bin/env python3
"""
prediction_filter.py — routine prediction-lens filter over the watchlist.

Pipeline step (daily, before the digest builds) that turns the one-off
mailer_prediction_audit into a standing eviction input:

  1. refresh reports/watchlist_prediction_scores.csv (market regime ×
     stock Markov state × Kalman drift, via mailer_prediction_audit)
  2. PURGE non-held WEAK names — stock in bear Markov state AND negative
     Kalman drift while their market gate passes. Rows are archived to
     watchlist_purged.csv (append-only), same convention as zone eviction.
  3. NEVER touch `held` rows — that's the portfolio; exiting it is the
     user's call, not the pipeline's (same rule as the digest's zone
     eviction). Held WEAK names are listed as SELL-REVIEW in the output
     and land in reports/held_sell_review.csv for the mailer to surface.
  4. skip markets whose stock-level panel is stale (> MAX_PANEL_AGE_DAYS):
     a week-old bear-state verdict is not evidence today.

Usage:
  python prediction_filter.py            # refresh scores + purge + report
  python prediction_filter.py --dry-run  # show what would purge, touch nothing
  python prediction_filter.py --no-refresh   # reuse existing scores csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
WATCHLIST = HERE / "watchlist.csv"
PURGED = HERE / "watchlist_purged.csv"
SCORES = HERE / "reports/watchlist_prediction_scores.csv"
SELL_REVIEW = HERE / "reports/held_sell_review.csv"

PROTECTED_STATUS = {"held"}          # never purged — portfolio tracking
MAX_PANEL_AGE_DAYS = 7               # stale stock-level panel → no verdicts acted on

# ── per-market RSI bands (2026-07-27) ────────────────────────────────────────
# Same market-character map the zone rules use (backtest_zone_rules.py):
# IN = momentum/trend → RSI strength is GOOD (buy 50-75), exhaustion >80 and
#   breakdown <40 are exits. US/JP/KR/EU = mean-revert → oversold is the buy
#   (<=35), overbought the sell (>=70). Each market reads the same indicator
#   differently ON PURPOSE — a uniform band was backtested-wrong the same way
#   the uniform EMA rule was (KR t−2.5).
RSI_BANDS = {
    "IN": {"style": "momentum", "buy": (50, 75), "sell_lo": 40, "sell_hi": 80},
    "US": {"style": "revert", "buy_max": 35, "sell_min": 70},
    "JP": {"style": "revert", "buy_max": 35, "sell_min": 70},
    "KR": {"style": "revert", "buy_max": 35, "sell_min": 70},
    "EU": {"style": "revert", "buy_max": 35, "sell_min": 70},
}


def rsi14(close: pd.Series) -> float | None:
    c = pd.to_numeric(close, errors="coerce").dropna()
    if len(c) < 20:
        return None
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = up / dn.replace(0, pd.NA)
    r = 100 - 100 / (1 + rs)
    return round(float(r.iloc[-1]), 1) if pd.notna(r.iloc[-1]) else None


def rsi_zone(market: str, r: float | None) -> str:
    """Per-market BUY/HOLD/SELL read of the same RSI value."""
    if r is None:
        return "?"
    b = RSI_BANDS.get(market, RSI_BANDS["US"])
    if b["style"] == "momentum":
        if r < b["sell_lo"] or r > b["sell_hi"]:
            return "SELL"
        lo, hi = b["buy"]
        return "BUY" if lo <= r <= hi else "HOLD"
    if r <= b["buy_max"]:
        return "BUY"
    if r >= b["sell_min"]:
        return "SELL"
    return "HOLD"


def annotate_rsi(s: pd.DataFrame) -> pd.DataFrame:
    """Attach rsi + rsi_zone per name (prices via the digest's own loader),
    then refine verdicts: ENTER-OK in an RSI SELL band → ENTER-WAIT (RSI)."""
    try:
        from watchlist_digest import _load_ohlc
    except Exception as e:
        print(f"  ⚠ RSI layer skipped (digest loader: {str(e)[:60]})")
        s["rsi"] = None; s["rsi_zone"] = "?"
        return s
    rsis, zones = [], []
    for r in s.itertuples():
        df = None
        try:
            df = _load_ohlc(str(r.symbol), str(r.market))
        except Exception:
            pass
        v = rsi14(df["Close"]) if df is not None and "Close" in getattr(df, "columns", []) else None
        rsis.append(v); zones.append(rsi_zone(str(r.market), v))
    s["rsi"] = rsis; s["rsi_zone"] = zones
    hot = (s["verdict"] == "ENTER-OK") & (s["rsi_zone"] == "SELL")
    s.loc[hot, "verdict"] = "ENTER-WAIT (RSI)"
    n = s["rsi"].notna().sum()
    print(f"  RSI layer: {n}/{len(s)} priced · zones "
          f"{s.rsi_zone.value_counts().to_dict()} · "
          f"{int(hot.sum())} ENTER-OK downgraded to ENTER-WAIT (RSI hot)")
    return s


def refresh_scores() -> bool:
    try:
        import mailer_prediction_audit as A
        _, b_df = A.part_b()
        b_df.to_csv(SCORES, index=False)
        print(f"  scores refreshed: {len(b_df)} names")
        return True
    except Exception as e:
        print(f"  ⚠ score refresh failed ({str(e)[:80]}) — using existing csv")
        return SCORES.exists()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-refresh", action="store_true")
    ap.add_argument("--max-age", type=int, default=MAX_PANEL_AGE_DAYS,
                    help="override the stale-panel guard (one-off purges only)")
    a = ap.parse_args()

    print("[prediction-filter] watchlist × prediction lens")
    if not a.no_refresh:
        if not refresh_scores():
            return 1
    s = pd.read_csv(SCORES)
    s["asof"] = pd.to_datetime(s["asof"], errors="coerce")

    # RSI layer — per-market read of the same indicator (momentum IN,
    # mean-revert US/JP/KR/EU); refines verdicts + persists to the CSV so
    # the mailer block shows the combined lens.
    s = annotate_rsi(s)
    s.to_csv(SCORES, index=False)

    weak = s[s["verdict"].str.contains("WEAK", na=False)].copy()
    if weak.empty:
        print("  no WEAK names — nothing to do")
        return 0

    # stale-panel guard
    age = (pd.Timestamp.today() - weak["asof"]).dt.days
    stale = weak[age > a.max_age]
    weak = weak[age <= a.max_age]
    if len(stale):
        print(f"  {len(stale)} WEAK skipped — stock panel older than "
              f"{a.max_age}d ({sorted(stale.market.unique())}); "
              f"refresh the panels before acting on those")

    purge = weak[~weak["status"].isin(PROTECTED_STATUS)]
    held = weak[weak["status"].isin(PROTECTED_STATUS)]

    # held WEAK → sell-review file for the mailer, never auto-purged
    if len(held):
        held_out = held[["market", "symbol", "status", "stock_state",
                         "kalman_drift_ann_pct", "markov_e21d_pct", "verdict"]]
        held_out.to_csv(SELL_REVIEW, index=False)
        print(f"  {len(held)} held WEAK → SELL-REVIEW (reports/held_sell_review.csv) "
              f"— portfolio rows are never auto-purged")

    if purge.empty:
        print("  no purgeable (non-held) WEAK names")
        return 0

    wl = pd.read_csv(WATCHLIST)
    keys = set(zip(purge["market"], purge["symbol"]))
    mask = wl.apply(lambda r: (r["market"], r["symbol"]) in keys, axis=1)
    victims = wl[mask].copy()

    print(f"  purging {len(victims)} non-held WEAK name(s):")
    for _, r in purge.iterrows():
        if (r["market"], r["symbol"]) in set(zip(victims["market"], victims["symbol"])):
            print(f"    {r['market']} {r['symbol']:10s} [{r['status']}] "
                  f"state={r['stock_state']} drift={r['kalman_drift_ann_pct']}% "
                  f"markov21d={r['markov_e21d_pct']}%")

    if a.dry_run:
        print("  DRY RUN — watchlist untouched")
        return 0

    victims["status"] = "evicted"
    victims["note"] = (f"prediction-filter {date.today()}: WEAK "
                       f"(bear Markov state + negative Kalman drift)")
    # append-only archive, then drop from the live list (same as zone purge)
    header = not PURGED.exists()
    victims.to_csv(PURGED, mode="a", header=header, index=False)
    wl[~mask].to_csv(WATCHLIST, index=False)
    print(f"  ✓ {len(victims)} archived to watchlist_purged.csv, "
          f"watchlist now {int((~mask).sum())} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
