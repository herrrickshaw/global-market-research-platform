#!/usr/bin/env python3
"""
watchlist_tiers.py — the three-tier watchlist system (2026-07-27).

  TIER 1  watchlist.csv          filter/screener-driven picks (unchanged)
  TIER 2  watchlist2.csv         VALIDATION watchlist — every purged name lands
                                 here and is tracked against the exact criteria
                                 that evicted it (prediction verdict + RSI zone).
                                 Dynamically evolving: new purges auto-enroll,
                                 names that behave as predicted age out.
  TIER 3  watchlist3.csv         ANOMALIES — tier-2 names whose price action
                                 CONTRADICTS the eviction thesis (evicted as
                                 WEAK, then rallied). These are the prediction
                                 model's misses: the research queue.

Daily flow (pipeline step [13w], after prediction_filter):
  1. SYNC   — any watchlist_purged.csv row not yet in tier 2/3 enrolls in
              tier 2 with a baseline price (first close after enrolment).
  2. TRACK  — per tier-2 name: current close, % since baseline, live RSI zone
              (per-market bands from prediction_filter).
  3. PROMOTE— anomaly rule (preset, deterministic):
                ret_since_purge >= +10%           (eviction call plainly wrong)
             OR ret >= +5% AND rsi_zone == BUY    (recovering + re-entry band)
             → row MOVES to tier 3 with the trigger recorded.
  4. AGE-OUT— tier-2 names that behaved as predicted (ret <= -15% or tracked
              > 90d without promotion) are dropped (validated, logged).

Usage:
  python watchlist_tiers.py            # sync + track + promote
  python watchlist_tiers.py --dry-run
  python watchlist_tiers.py --status   # print tier summaries only
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PURGED = HERE / "watchlist_purged.csv"
W2 = HERE / "watchlist2.csv"
W3 = HERE / "watchlist3.csv"
LOG = HERE / "reports/watchlist_tiers_log.csv"

PROMOTE_RET = 10.0        # % since baseline → anomaly regardless of RSI
PROMOTE_RET_RSI = 5.0     # % since baseline when RSI zone is BUY
AGEOUT_RET = -15.0        # validated decliner — eviction confirmed, drop
AGEOUT_DAYS = 90          # tracked long enough without contradiction

W2_COLS = ["symbol", "market", "purge_note", "enrolled", "baseline_price",
           "last_price", "ret_pct", "rsi", "rsi_zone", "last_checked"]


def _log(event: str, sym: str, mkt: str, detail: str):
    row = pd.DataFrame([{"date": date.today(), "event": event,
                         "symbol": sym, "market": mkt, "detail": detail}])
    row.to_csv(LOG, mode="a", header=not LOG.exists(), index=False)


def load(p: Path, cols) -> pd.DataFrame:
    if p.exists():
        return pd.read_csv(p)
    return pd.DataFrame(columns=cols)


def last_close(sym: str, mkt: str):
    try:
        from watchlist_digest import _load_ohlc
        df = _load_ohlc(str(sym), str(mkt))
        if df is not None and "Close" in df.columns:
            c = pd.to_numeric(df["Close"], errors="coerce").dropna()
            if len(c):
                return float(c.iloc[-1]), df
    except Exception:
        pass
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    from prediction_filter import rsi14, rsi_zone

    w2 = load(W2, W2_COLS)
    w3 = load(W3, W2_COLS + ["promoted", "trigger"])

    if a.status:
        print(f"tier 2 (validation): {len(w2)} · tier 3 (anomalies): {len(w3)}")
        if len(w3):
            print(w3[["symbol", "market", "ret_pct", "trigger"]].tail(10).to_string(index=False))
        return 0

    print("[watchlist-tiers] sync → track → promote")

    # 1 — SYNC: enroll purged names not yet in tier 2/3
    if PURGED.exists():
        pg = pd.read_csv(PURGED)
        seen = set(zip(w2.get("symbol", []), w2.get("market", []))) | \
               set(zip(w3.get("symbol", []), w3.get("market", [])))
        new = pg[~pg.apply(lambda r: (r["symbol"], r["market"]) in seen, axis=1)]
        new = new.drop_duplicates(subset=["symbol", "market"], keep="last")
        enrolled = 0
        for r in new.itertuples():
            px, _ = last_close(r.symbol, r.market)
            if px is None:
                continue
            w2 = pd.concat([w2, pd.DataFrame([{
                "symbol": r.symbol, "market": r.market,
                "purge_note": str(getattr(r, "note", ""))[:120],
                "enrolled": str(date.today()), "baseline_price": px,
                "last_price": px, "ret_pct": 0.0, "rsi": None,
                "rsi_zone": "?", "last_checked": str(date.today()),
            }])], ignore_index=True)
            enrolled += 1
            _log("enroll", r.symbol, r.market, f"baseline={px}")
        print(f"  sync: {enrolled} newly-purged name(s) enrolled in tier 2 "
              f"(tier2 now {len(w2)})")

    # 2/3 — TRACK + PROMOTE
    promoted, aged, keep = [], [], []
    for r in w2.itertuples():
        px, df = last_close(r.symbol, r.market)
        row = r._asdict(); row.pop("Index", None)
        if px is not None:
            base = float(row["baseline_price"]) or px
            ret = round((px - base) / base * 100, 2)
            rv = rsi14(df["Close"]) if df is not None else None
            row.update({"last_price": px, "ret_pct": ret, "rsi": rv,
                        "rsi_zone": rsi_zone(str(r.market), rv),
                        "last_checked": str(date.today())})
            days = (pd.Timestamp.today() - pd.Timestamp(row["enrolled"])).days
            trigger = None
            if ret >= PROMOTE_RET:
                trigger = f"ret {ret:+.1f}% >= +{PROMOTE_RET}%"
            elif ret >= PROMOTE_RET_RSI and row["rsi_zone"] == "BUY":
                trigger = f"ret {ret:+.1f}% + RSI BUY zone"
            if trigger:
                row["promoted"] = str(date.today()); row["trigger"] = trigger
                promoted.append(row)
                _log("promote→tier3", r.symbol, r.market, trigger)
                continue
            if ret <= AGEOUT_RET or days > AGEOUT_DAYS:
                aged.append(row)
                _log("ageout(validated)", r.symbol, r.market,
                     f"ret {ret:+.1f}% after {days}d — eviction confirmed")
                continue
        keep.append(row)

    w2_new = pd.DataFrame(keep, columns=W2_COLS) if keep else pd.DataFrame(columns=W2_COLS)
    if promoted:
        w3 = pd.concat([w3, pd.DataFrame(promoted)], ignore_index=True)

    print(f"  track: {len(keep)} tier-2 tracked · {len(promoted)} promoted to "
          f"tier 3 (anomalies) · {len(aged)} aged out (eviction validated)")
    for p in promoted:
        print(f"    ⚡ ANOMALY {p['market']} {p['symbol']}: {p['trigger']}")

    if a.dry_run:
        print("  DRY RUN — files untouched")
        return 0

    w2_new.to_csv(W2, index=False)
    w3.to_csv(W3, index=False)
    print(f"  ✓ tier2={len(w2_new)} tier3={len(w3)} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
