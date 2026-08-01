#!/usr/bin/env python3
"""
dii_wide_retest.py — re-test the DII result outside the liquid segment.

WHY
---
`ownership_behaviour_india.py --source screener` found DII holding predicting
lower volatility at t=-9.9 with controls, on 347 companies. That looked like the
study's strongest result. It has a problem the public-float result also had, and
the public-float result did not survive it:

    the 397 companies in the screener panel   median turnover Rs 40.5 crore/day
    the 3,986 India equities NOT in it        median turnover Rs 0.08 crore/day

A 500x difference. The DII estimate is drawn entirely from the liquid segment —
the identical restriction that produced a +0.516 public-float correlation which
collapsed to -0.054 once the universe widened. Until DII is measured across the
same range, "t=-9.9" and "+0.516" have exactly the same evidentiary standing.

WHAT THIS DOES
Adds companies by SYSTEMATIC SAMPLING ACROSS THE TURNOVER RANK of everything
missing, rather than walking the universe alphabetically. Alphabetical order is
what produced the liquid-only panel in the first place: collection started from a
turnover-sorted seed and never reached the tail before screener.in blocked. A
budget of N requests spent evenly across the rank buys variation; the same N
spent alphabetically buys more of what we already have.

🔴 RATE. screener.in blocked after ~800 requests at 0.9s. It has since released.
This runs at 2.5s and checkpoints every 25, because a second block costs more
than the extra wall-clock: it would leave the retest half-done and the question
open. Stops on a run of failures rather than pushing through.

    dii_wide_retest.py --collect --budget 600
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache_seed"
PANEL = CACHE / "india_ownership_wide.parquet"


def _targets(budget: int) -> list:
    """Systematic sample across the turnover rank of what we do NOT have."""
    import screener_kit as kit
    have = set(pd.read_parquet(PANEL)["symbol"].unique()) if PANEL.exists() else set()
    ref = pd.read_parquet(CACHE / "ticker_exchange_reference.parquet")
    eq = set(ref[ref["country"] == "IN"]["base_ticker"].astype(str).str.upper())

    d = kit.load("IN")
    turn = {s: float((v["Close"] * v["Volume"]).median())
            for s, v in d.items() if len(v) > 100}
    t = pd.Series(turn)
    t = t[t.index.isin(eq) & ~t.index.isin(have)].sort_values()
    if t.empty:
        return []
    # Even stride down the turnover rank: full-range coverage for a fixed budget.
    step = max(1, len(t) // budget)
    picks = list(t.index[::step][:budget])
    print(f"  missing {len(t):,} equities; sampling {len(picks):,} evenly across "
          f"turnover rank (Rs {t.iloc[0]:,.0f} .. {t.iloc[-1]:,.0f})")
    return picks


def collect(budget: int = 600, sleep: float = 2.5) -> int:
    import equity_ownership as EO

    todo = _targets(budget)
    if not todo:
        print("  nothing to collect"); return 0
    rows = pd.read_parquet(PANEL).to_dict("records") if PANEL.exists() else []
    before = len({r["symbol"] for r in rows})
    got, consec = 0, 0

    import requests
    UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")}
    absent = 0
    for i, sym in enumerate(todo, 1):
        # 🔴 CLASSIFY THE FAILURE BEFORE COUNTING IT. A 404 means screener.in has
        # no page for this ticker; a connection error means we are blocked. The
        # first version treated both as failure, and since this samples ASCENDING
        # from the lowest turnover (Rs 180/day) the opening names are delisted
        # shells that legitimately 404 — so the block guard tripped on the first
        # 20 symbols and the whole retest aborted with 0 added while screener.in
        # was perfectly healthy. Only transport failures may count toward a block.
        try:
            probe = requests.get(f"https://www.screener.in/company/{sym}/",
                                 headers=UA, timeout=20)
            if probe.status_code == 404:
                absent += 1
                consec = 0            # absent is an ANSWER, not a failure
                time.sleep(sleep)
                continue
            if probe.status_code != 200:
                raise RuntimeError(f"http {probe.status_code}")
        except Exception:
            consec += 1
            if consec >= 20:
                print(f"  🔴 {consec} consecutive TRANSPORT failures at {sym} — stopping "
                      f"rather than risk a second block. {got} added this run.")
                break
            time.sleep(sleep)
            continue
        try:
            t, mc = EO._screener_company(sym)
        except Exception:
            t, mc = None, None
        if t is None or mc is None:
            absent += 1      # page exists but carries no shareholding table
            consec = 0
            time.sleep(sleep)
            continue
        t = t.set_index(t.columns[0])
        t.index = t.index.astype(str).str.replace(r"[+\s]+$", "", regex=True).str.strip()
        for h in [ix for ix in t.index if EO._HOLDER.search(ix)]:
            row = t.loc[h]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            vals = pd.to_numeric(row.astype(str).str.rstrip("%"), errors="coerce")
            for q, v in vals.items():
                if pd.notna(v):
                    rows.append({"symbol": sym, "quarter": str(q), "holder": h,
                                 "pct": float(v), "mcap_cr": mc})
        got += 1
        if i % 25 == 0:
            pd.DataFrame(rows).to_parquet(PANEL, compression="zstd", index=False)
            print(f"    {i}/{len(todo)}  added={got}  absent={absent}")
        time.sleep(sleep)

    d = pd.DataFrame(rows)
    d.to_parquet(PANEL, compression="zstd", index=False)
    print(f"  -> {PANEL.name}: {d.symbol.nunique():,} companies "
          f"(was {before:,}, +{d.symbol.nunique() - before:,})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--budget", type=int, default=600)
    ap.add_argument("--sleep", type=float, default=2.5)
    a = ap.parse_args()
    if not a.collect:
        ap.print_help(); return 1
    return collect(budget=a.budget, sleep=a.sleep)


if __name__ == "__main__":
    sys.exit(main())
