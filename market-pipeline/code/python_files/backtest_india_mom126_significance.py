#!/usr/bin/env python3
"""
backtest_india_mom126_significance.py — a proper re-test of India's mom126
signal, and wiring the result into the production zone-rule pipeline.

WHY THIS EXISTS
---------------
backtest_zone_rule_rec_simulation.py found India's FIXED mom126 basket beats
its benchmark (14.7% vs 10.2% CAGR, 2018-2026) -- but flagged a caveat:
zone_rules.json's own BUY-SELL spread significance test for India mom126 only
reaches t=1.19, below the 1.5 bar backtest_zone_rules.py uses everywhere else
to call a signal real. A long-only basket can beat a benchmark in a rising
market without genuine discriminating power. This script re-tests properly
before anything gets wired into production.

WHAT'S DIFFERENT FROM THE ORIGINAL t=1.19 TEST
-----------------------------------------------
backtest_zone_rules.py resamples to WEEKLY bars first (to cut overlap/cost
across ALL 5 markets x 4 rules), so its "126-day" momentum is actually
pct_change(25) on weekly bars -- an approximation, and its de-overlap step
(`iloc[::2]`) only keeps a small fraction of the weekly formation dates.

This script, focused on India mom126 ONLY, uses the REAL daily panel and the
EXACT lookback now live in watchlist_digest.py's fix (`_pct_change(df, 126)`,
126 TRADING days, no weekly approximation), and forms formation dates on a
genuinely non-overlapping grid (every FWD-th trading day, since the holding
period IS the forward window -- no post-hoc de-overlap needed, no discarded
weekly formations). This is strictly more data and a more exact match to the
live signal than the original test, so it is the right test to gate a
production change on.

WIRING
------
If the re-test clears the same |t|>=1.5 bar backtest_zone_rules.py uses AND
the spread is positive: updates zone_rules.json's IN entry (winner -> mom126)
and zone_rules_by_market.md's IN row, which flow into watchlist_digest.py's
_zone_rules()/_zone_regime() the same way the other 4 markets' winners do --
no separate code path. If it does NOT clear the bar: leaves IN on "trend"
(the existing fallback) and records the re-test result so this isn't silently
re-tried by a future session.

Educational/research only. NOT investment advice.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from backtest_zone_rules import WH, START, TERCILE, FWD, OUT_JSON, OUT_MD

HERE = Path(__file__).resolve().parent
SIG_BAR = 1.5   # same significance bar backtest_zone_rules.py uses to call a winner


def load_closes_daily(mkt: str) -> pd.DataFrame:
    """Same source/pivot as backtest_zone_rules.load_closes(), but stops at
    the daily grid instead of resampling to weekly."""
    parts = sorted(glob.glob(f"{WH}/{mkt}/year=*.parquet"))
    df = pd.concat((pd.read_parquet(p, columns=["Date", "Symbol", "Close"])
                    for p in parts), ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])
    w = df.pivot_table(index="Date", columns="Symbol", values="Close",
                       aggfunc="last").sort_index()
    return w.asfreq("B").ffill(limit=2)


def retest_spread(w: pd.DataFrame, lookback: int = 126, fwd: int = FWD,
                  start: str = START) -> dict:
    """BUY-SELL forward spread of top/bottom-tercile `lookback`-day momentum,
    on a genuinely non-overlapping daily formation grid (every `fwd`-th day)."""
    r = w.pct_change(lookback, fill_method=None)
    lo = r.rank(axis=1, pct=True)
    sig = (lo >= 1 - TERCILE).astype(int) - (lo <= TERCILE).astype(int)
    fwdret = (w.shift(-fwd) / w - 1).clip(-0.40, 0.40)
    tradeable = w >= 1.0

    dates = w.index[w.index >= start]
    dates = dates[::fwd]   # every fwd-th day -> non-overlapping by construction
    spreads = []
    for t in dates:
        if t not in sig.index or t not in fwdret.index:
            continue
        s = sig.loc[t]
        f = fwdret.loc[t].where(tradeable.loc[t])
        buys = f[s == 1].dropna()
        sells = f[s == -1].dropna()
        if len(buys) >= 6 and len(sells) >= 6:
            spreads.append(buys.mean() - sells.mean())
    sp = pd.Series(spreads)
    if len(sp) < 10:
        return {"n_indep_obs": len(sp), "spread_pct": None, "t_stat": None}
    return {"n_indep_obs": len(sp), "spread_pct": round(float(sp.mean() * 100), 3),
            "t_stat": round(float(sp.mean() / sp.std() * np.sqrt(len(sp))), 2)}


def wire_result(res: dict) -> str:
    """Update zone_rules.json + zone_rules_by_market.md if the re-test clears
    the significance bar; otherwise record the null result. Returns a short
    status string for the printed report."""
    rules = json.loads(OUT_JSON.read_text())
    in_entry = rules["IN"]
    in_entry.setdefault("all", {})
    in_entry["all"]["mom126_daily_retest"] = [res["spread_pct"], res["t_stat"],
                                              f"n={res['n_indep_obs']}, 2026-08-23"]

    if res["t_stat"] is not None and res["spread_pct"] is not None \
            and res["spread_pct"] > 0 and abs(res["t_stat"]) >= SIG_BAR:
        in_entry["rule"] = "mom126"
        in_entry["spread_pct"] = res["spread_pct"]
        in_entry["t"] = res["t_stat"]
        status = (f"WIRED: IN winner -> mom126 (daily re-test: "
                 f"{res['spread_pct']:+.3f}%, t{res['t_stat']:+.2f}, "
                 f"n={res['n_indep_obs']} independent obs, clears |t|>={SIG_BAR})")
    else:
        status = (f"NOT WIRED: IN stays on 'trend'. Daily re-test "
                 f"({res['spread_pct']}, t{res['t_stat']}, n={res['n_indep_obs']}) "
                 f"did not clear |t|>={SIG_BAR} and/or spread<=0 -- confirms the "
                 f"14.7%-vs-10.2% CAGR edge in backtest_zone_rule_rec_simulation.py "
                 f"was NOT backed by real discriminating power. Recorded so this "
                 f"is not silently re-tried later.")

    OUT_JSON.write_text(json.dumps(rules, indent=1))

    md = OUT_MD.read_text()
    marker = "🔴 IN mom126 daily re-test (2026-08-23):"
    note = (f"\n\n{marker} {res['spread_pct']}% (t{res['t_stat']}, "
           f"n={res['n_indep_obs']} independent 10-day windows, real daily "
           f"126-trading-day lookback -- matches the live watchlist_digest.py "
           f"field exactly, not the weekly-bar approximation above). {status}\n")
    if marker not in md:
        OUT_MD.write_text(md + note)
    return status


def main() -> int:
    print("India mom126 significance re-test (daily bars, exact live lookback) …")
    w = load_closes_daily("IN")
    res = retest_spread(w)
    print(f"  spread={res['spread_pct']}%  t={res['t_stat']}  "
         f"n_independent_obs={res['n_indep_obs']}")
    status = wire_result(res)
    print(f"\n{status}")
    print(f"\nwrote {OUT_JSON} and appended to {OUT_MD}")
    print("\nEducational/research only. NOT investment advice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
