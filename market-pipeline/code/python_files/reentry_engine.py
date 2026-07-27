#!/usr/bin/env python3
"""
reentry_engine.py — the mean-reversion discovery engine over tier 3 (2026-07-27).

The tier-anomaly backtest (reports/tier_anomaly_backtest.md) showed evictions
in bull markets boomerang 45-75% of the time, and BUYING those boomerangs at
the anomaly trigger carried real forward edge (excess vs median-return index:
IN +12.9%/63d t14.2 · KR +24.9%/63d t14.8 · JP +6.1% t10.3 · US +5.1% t7.0;
raw returns positive everywhere — survivorship-lite caveat: top-200 liquid
panel). So tier 3 is treated as a RE-ENTRY QUEUE, not a failure log.

Daily flow (pipeline [13w], after watchlist_tiers):
  1. read watchlist3.csv (anomalies promoted today or still fresh)
  2. gate: market regime must not be bear (zone_regime.json when present)
  3. rank fresh anomalies per market: trigger recency > bounce strength;
     RSI SELL zone (overbought per that market's band) is a VETO
  4. top N per market enter watchlist.csv as status='reentry' rows with
     entry_date/entry_price — the paper-track then scores the engine
     out-of-sample automatically
  5. stale tier-3 rows (promoted > STALE_DAYS ago, never re-entered) age out

Usage:
  python reentry_engine.py            # rank + enroll re-entries
  python reentry_engine.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
W3 = HERE / "watchlist3.csv"
WL = HERE / "watchlist.csv"
OUT = HERE / "reports/reentry_candidates.csv"
LOG = HERE / "reports/watchlist_tiers_log.csv"

MAX_PER_MARKET = 3        # discovery, not a firehose — paper-track validates
FRESH_DAYS = 10           # only recently-promoted anomalies are actionable
STALE_DAYS = 30           # tier-3 rows older than this age out un-entered


def market_regime() -> dict:
    try:
        return json.loads((HERE / "cache_seed/zone_regime.json").read_text())
    except Exception:
        return {}


RECENT = HERE / "reports/reentry_recent.csv"
BACKTEST_EVENTS = HERE / "reports/tier_anomaly_events.csv"
RECENT_DAYS = 45


def write_recent_reentries():
    """reports/reentry_recent.csv — re-entry names from the previous few weeks,
    shown in every mailer: live tier-3 promotions UNION recent backtest anomaly
    triggers (the replayed history seeds this until live promotions accumulate)."""
    frames = []
    if W3.exists():
        w3 = pd.read_csv(W3)
        if len(w3):
            w3["trigger_date"] = pd.to_datetime(w3["promoted"], errors="coerce")
            w3["ret_at_trigger"] = w3.get("ret_pct")
            w3["source"] = "live"
            frames.append(w3[["market", "symbol", "trigger_date",
                              "ret_at_trigger", "source"]])
    if BACKTEST_EVENTS.exists():
        ev = pd.read_csv(BACKTEST_EVENTS, parse_dates=["evict_date"])
        an = ev[ev.outcome == "ANOMALY"].copy()
        an["trigger_date"] = an.evict_date + pd.to_timedelta(an.days, unit="D")
        an["ret_at_trigger"] = an.exit_ret_pct
        an["source"] = "backtest"
        frames.append(an[["market", "symbol", "trigger_date",
                          "ret_at_trigger", "source"]])
    if not frames:
        return 0
    r = pd.concat(frames, ignore_index=True)
    r = r[r.trigger_date >= pd.Timestamp.today() - pd.Timedelta(days=RECENT_DAYS)]
    r = (r.sort_values("trigger_date", ascending=False)
          .drop_duplicates(subset=["market", "symbol"], keep="first"))
    r.to_csv(RECENT, index=False)
    print(f"  recent re-entries ({RECENT_DAYS}d): {len(r)} names "
          f"({r.source.value_counts().to_dict()}) → reports/reentry_recent.csv")
    return len(r)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    from prediction_filter import rsi14, rsi_zone

    print("[reentry-engine] tier 3 → ranked re-entry candidates")
    write_recent_reentries()
    if not W3.exists():
        print("  no watchlist3.csv — nothing to do")
        return 0
    w3 = pd.read_csv(W3)
    if w3.empty:
        print("  tier 3 empty — nothing to do")
        return 0
    w3["promoted"] = pd.to_datetime(w3["promoted"], errors="coerce")
    age = (pd.Timestamp.today() - w3["promoted"]).dt.days

    # age out stale, keep fresh
    stale = w3[age > STALE_DAYS]
    fresh = w3[age <= FRESH_DAYS].copy()
    keep = w3[age <= STALE_DAYS]
    if len(stale) and not a.dry_run:
        keep.to_csv(W3, index=False)
        print(f"  aged out {len(stale)} stale tier-3 row(s)")

    if fresh.empty:
        print(f"  no fresh anomalies (≤{FRESH_DAYS}d) — no re-entries today")
        return 0

    regime = market_regime()
    wl = pd.read_csv(WL)
    existing = set(zip(wl["symbol"], wl["market"]))

    from watchlist_digest import _load_ohlc
    cands = []
    for r in fresh.itertuples():
        mkt = str(r.market)
        reg = (regime.get(mkt, {}) or {}).get("current_regime", "")
        if str(reg).lower() == "bear":
            continue                          # market gate: no re-entry into bear
        if (r.symbol, mkt) in existing:
            continue
        df = None
        try:
            df = _load_ohlc(str(r.symbol), mkt)
        except Exception:
            pass
        if df is None or "Close" not in getattr(df, "columns", []):
            continue
        c = pd.to_numeric(df["Close"], errors="coerce").dropna()
        if len(c) < 30:
            continue
        rv = rsi14(c)
        z = rsi_zone(mkt, rv)
        if z == "SELL":
            continue                          # per-market overbought VETO
        px = float(c.iloc[-1])
        cands.append({
            "symbol": r.symbol, "market": mkt, "trigger": r.trigger,
            "promoted": str(r.promoted.date()), "ret_at_promotion": r.ret_pct,
            "rsi": rv, "rsi_zone": z, "price": px,
            # rank: freshest promotion first, then strongest trigger return
            "_rank": (-(pd.Timestamp.today() - r.promoted).days, r.ret_pct),
        })

    cands.sort(key=lambda x: x["_rank"], reverse=True)
    picks = []
    per_mkt: dict = {}
    for cnd in cands:
        m = cnd["market"]
        if per_mkt.get(m, 0) >= MAX_PER_MARKET:
            continue
        per_mkt[m] = per_mkt.get(m, 0) + 1
        picks.append(cnd)

    for c in cands:
        c.pop("_rank", None)
    pd.DataFrame(cands).to_csv(OUT, index=False)
    print(f"  {len(fresh)} fresh anomalies → {len(cands)} eligible → "
          f"{len(picks)} re-entry pick(s) (cap {MAX_PER_MARKET}/market)")
    for p in picks:
        print(f"    ↩ RE-ENTER {p['market']} {p['symbol']} @ {p['price']:g} "
              f"(rsi {p['rsi']}, {p['trigger']})")

    if a.dry_run or not picks:
        if a.dry_run:
            print("  DRY RUN — watchlist untouched")
        return 0

    add = pd.DataFrame([{
        "symbol": p["symbol"], "market": p["market"], "status": "reentry",
        "note": f"reentry-engine {date.today()}: tier-3 anomaly ({p['trigger']})",
        "entry_date": str(date.today()), "entry_price": p["price"],
    } for p in picks])
    pd.concat([wl, add], ignore_index=True).to_csv(WL, index=False)
    for p in picks:
        pd.DataFrame([{"date": date.today(), "event": "reentry→tier1",
                       "symbol": p["symbol"], "market": p["market"],
                       "detail": f"@{p['price']:g} {p['trigger']}"}]).to_csv(
            LOG, mode="a", header=not LOG.exists(), index=False)
    print(f"  ✓ {len(picks)} re-entry row(s) added to watchlist.csv "
          f"(status=reentry — paper-track scores them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
