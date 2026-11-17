#!/usr/bin/env python3
"""
run_factor_backtests_fixed.py — fixed-horizon version of run_factor_backtests.py.

WHY THIS EXISTS. The "as of today" scorer in run_factor_backtests.py gave
median vs-benchmark figures of -94%/-117% for the two US fundamentals
screens. Investigation (2026-08-23) traced this to a real confound, not a
bug: signals from ~2016 held ~3,700 days (10 years) to "today" against a
benchmark that quadrupled over that exact window, with ~9% of the microcap-
heavy signal population going to near-total loss in the meantime. That's a
genuine result for THAT measurement design, but it isn't a fair test of
Novy-Marx/Sloan's actual claims, which were measured over FIXED, comparable
holding periods (typically ~1 year), not "hold until whenever today happens
to be." This script removes that confound: every signal is scored at the
SAME set of fixed horizons after its own entry, using this repo's own
established horizon convention (backtest_screeners.py's HORIZONS).

Reuses every guard already proven necessary the hard way:
  - entry-bar-correct: enters on the first bar STRICTLY AFTER signal_date
    (the 2026-08-22 backtest_screeners.py fix)
  - stale-entry guard: rejects an entry more than 30 calendar days after the
    signal (the CETX 4-year-gap finding, 2026-08-23)
  - split-artifact guard: rejects an entry/exit bar that jumps >60% in one
    day from its neighbor (same convention as factor_screens.py's
    _sanity_check_no_split_artifacts)
  - real benchmarks: NIFTYBEES+NIFTY50 splice for India, SPY for US (same
    _india_benchmark() as debt_turnaround_screen.py / run_factor_backtests.py)

    run_factor_backtests_fixed.py --years 3 --min-days 21
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import factor_screens as FS  # noqa: E402
import signal_tracker as ST  # noqa: E402
from debt_turnaround_screen import _india_benchmark  # noqa: E402
from run_factor_backtests import scan_history  # noqa: E402 -- reuse the monthly-rebalance loop

HORIZONS_TRADING_DAYS = {"1mo": 21, "3mo": 63, "6mo": 126, "1yr": 252}
STALE_ENTRY_DAYS = 30
SPLIT_JUMP_THRESHOLD = 0.60


def score_fixed_horizon(signals: pd.DataFrame, id_col: str, min_days: int = 0,
                        wide_override: dict = None, bench_override: dict = None) -> pd.DataFrame:
    """wide_override / bench_override: {market: DataFrame/Series} -- injection
    points used ONLY by test_fixed_horizon_scorer.py so tests never touch the
    real warehouse. Real runs leave these None and load from ST.PANELS."""
    if signals.empty:
        out = pd.DataFrame(); out.attrs["skipped"] = {}; return out
    signals = signals.copy()
    signals["signal_date"] = pd.to_datetime(signals["signal_date"])
    if min_days:
        today = pd.Timestamp.today().normalize()
        signals = signals[(today - signals["signal_date"]).dt.days >= min_days]
    if signals.empty:
        out = pd.DataFrame(); out.attrs["skipped"] = {}; return out

    rows = []
    skipped = {"not_in_panel": 0, "too_early": 0, "stale_entry": 0, "split_risk": 0}
    for mkt, grp in signals.groupby("market"):
        if wide_override and mkt in wide_override:
            wide = wide_override[mkt]
        else:
            p = ST.PANELS.get(mkt)
            if not p or not p.exists():
                skipped["not_in_panel"] += len(grp); continue
            px = ST._panel(p, columns=["Date", "Symbol", "Close"])
            px["Symbol"] = px["Symbol"].astype(str).str.upper()
            wide = px.pivot_table(index="Date", columns="Symbol", values="Close",
                                  aggfunc="last").sort_index()
        if bench_override and mkt in bench_override:
            bench = bench_override[mkt]
        else:
            bench = _india_benchmark() if mkt == "IN" else (
                wide[ST.BENCH.get(mkt)].dropna() if ST.BENCH.get(mkt) in wide.columns
                else pd.Series(dtype=float))

        for _, r in grp.iterrows():
            sym = str(r[id_col]).upper()
            if sym not in wide.columns:
                skipped["not_in_panel"] += 1; continue
            s = wide[sym].dropna()
            after_sig = s[s.index > r["signal_date"]]
            if after_sig.empty:
                skipped["too_early"] += 1; continue
            entry_dt = after_sig.index[0]
            entry_px = float(after_sig.iloc[0])
            if (entry_dt - r["signal_date"]).days > STALE_ENTRY_DAYS:
                skipped["stale_entry"] += 1; continue
            prior = s[s.index < entry_dt]
            if len(prior) and prior.iloc[-1] > 0 and \
                    abs(entry_px / prior.iloc[-1] - 1) > SPLIT_JUMP_THRESHOLD:
                skipped["split_risk"] += 1; continue

            entry_pos = s.index.get_loc(entry_dt)
            row = {"symbol": sym, "market": mkt, "signal_date": r["signal_date"],
                  "entry_date": entry_dt, "entry_price": entry_px}
            any_horizon_resolved = False
            for hname, hdays in HORIZONS_TRADING_DAYS.items():
                exit_pos = entry_pos + hdays
                if exit_pos >= len(s):
                    row[f"ret_{hname}"] = np.nan
                    row[f"xret_{hname}"] = np.nan
                    continue
                exit_dt = s.index[exit_pos]
                exit_px = float(s.iloc[exit_pos])
                # split-artifact guard on the exit bar too
                if abs(exit_px / float(s.iloc[exit_pos - 1]) - 1) > SPLIT_JUMP_THRESHOLD:
                    row[f"ret_{hname}"] = np.nan
                    row[f"xret_{hname}"] = np.nan
                    continue
                ret = (exit_px / entry_px - 1) * 100
                bafter = bench[(bench.index >= entry_dt) & (bench.index <= exit_dt)]
                bench_ret = ((float(bafter.iloc[-1]) / float(bafter.iloc[0]) - 1) * 100
                            if len(bafter) >= 2 else np.nan)
                row[f"ret_{hname}"] = ret
                row[f"xret_{hname}"] = ret - bench_ret if pd.notna(bench_ret) else np.nan
                any_horizon_resolved = True
            if any_horizon_resolved:
                rows.append(row)
            else:
                skipped["too_early"] += 1  # every horizon ran past the panel's end
    out = pd.DataFrame(rows)
    out.attrs["skipped"] = skipped
    return out


def report(name: str, scored: pd.DataFrame, raw_signal_count: int, n_excluded: int = 0):
    excl = f", {n_excluded} excluded as implausible/data-error" if n_excluded else ""
    print(f"\n  {'='*90}\n  {name}  ({raw_signal_count} raw signals detected{excl})")
    skip_msg = ", ".join(f"{k}={v}" for k, v in scored.attrs.get("skipped", {}).items() if v)
    if skip_msg:
        print(f"  skipped: {skip_msg}")
    if scored.empty:
        print("  nothing scoreable"); return
    for mkt, g in scored.groupby("market"):
        print(f"\n  {mkt}  (n={len(g)})")
        print(f"  {'horizon':<8}{'n':>7}{'med ret%':>10}{'med vs bench':>14}{'win%':>7}")
        for hname in HORIZONS_TRADING_DAYS:
            col_r, col_x = f"ret_{hname}", f"xret_{hname}"
            sub_r = g[col_r].dropna()
            sub_x = g[col_x].dropna()
            if sub_r.empty:
                continue
            print(f"  {hname:<8}{len(sub_r):>7}{sub_r.median():>10.2f}"
                 f"{sub_x.median() if len(sub_x) else float('nan'):>14.2f}"
                 f"{(sub_r>0).mean()*100:>6.0f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--min-days", type=int, default=0,
                    help="0 = score every signal at every horizon it can reach, "
                         "regardless of how recently it fired")
    a = ap.parse_args()

    print("=" * 90)
    print("  FIXED-HORIZON FACTOR SCREEN BACKTESTS — 2026-08-23")
    print("  Every signal scored at 1mo/3mo/6mo/1yr from ITS OWN entry, not \"as of today\"")
    print("=" * 90)

    print("\n[1/4] 12-1 momentum, monthly rebalance...")
    mom = scan_history(FS.momentum_12_1, ["IN", "US"], a.years)
    mom_scored = score_fixed_horizon(mom, "symbol", a.min_days) if not mom.empty else pd.DataFrame()
    report("MOMENTUM 12-1", mom_scored, len(mom))

    print("\n[2/4] 52-week-high proximity, monthly rebalance...")
    h52 = scan_history(FS.high_52w, ["IN", "US"], a.years)
    h52_scored = score_fixed_horizon(h52, "symbol", a.min_days) if not h52.empty else pd.DataFrame()
    report("52-WEEK-HIGH PROXIMITY", h52_scored, len(h52))

    print("\n[3/4] Gross profitability, US only...")
    gp = FS.gross_profitability("US")
    gp_scored = score_fixed_horizon(gp, "symbol", a.min_days) if not gp.empty else pd.DataFrame()
    report("GROSS PROFITABILITY (US)", gp_scored, len(gp), gp.attrs.get("n_excluded_implausible", 0))

    print("\n[4/4] Accruals, US only...")
    acc = FS.accruals("US")
    acc_scored = score_fixed_horizon(acc, "symbol", a.min_days) if not acc.empty else pd.DataFrame()
    report("ACCRUALS (US)", acc_scored, len(acc), acc.attrs.get("n_excluded_implausible", 0))

    print(f"\n{'='*90}\n  'vs bench' over the SAME fixed horizon is what matters. Every signal "
         f"contributes independently at each horizon it can reach -- no signal is penalized "
         f"or rewarded for how long ago it happened to fire.")


if __name__ == "__main__":
    main()
