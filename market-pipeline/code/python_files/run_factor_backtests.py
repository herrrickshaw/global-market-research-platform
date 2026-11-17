#!/usr/bin/env python3
"""
run_factor_backtests.py — runs every screen in factor_screens.py across real
history and backtests it with the same real-benchmark, entry-bar-correct
scoring used for the debt-turnaround screen (which found a real -14.71%
underperformance despite a flattering raw return — that discipline applies
here too; nothing below is trusted until it clears the same bar).

momentum_12_1 / high_52w: looped monthly (first trading day of each month)
across the last N years of the deep local panels, both IN and US -- a real
multi-date backtest, not a single as-of-today snapshot.

gross_profitability / accruals: US only (India's total_assets is 0%
populated everywhere checked, confirmed 2026-08-23 — not fabricated around),
already ranked cross-sectionally within each historical fiscal period by
factor_screens.py itself.

    run_factor_backtests.py --years 3       # momentum/52w-high lookback window
    run_factor_backtests.py --min-days 21
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
from debt_turnaround_screen import _india_benchmark  # noqa: E402 -- reuse, don't reimplement


def monthly_dates(wide: pd.DataFrame, years: int) -> list:
    idx = wide.index
    cutoff = idx.max() - pd.DateOffset(years=years)
    idx = idx[idx >= cutoff]
    months = pd.Series(idx).dt.to_period("M")
    firsts = pd.Series(idx).groupby(months).min()
    return sorted(firsts.tolist())


def scan_history(fn, markets: list, years: int) -> pd.DataFrame:
    all_sig = []
    for mkt in markets:
        wide = FS._wide_panel(mkt)  # loaded ONCE per market, reused across every rebalance date
        if wide.empty:
            print(f"    {mkt}: no local panel, skipped"); continue
        dates = monthly_dates(wide, years)
        n_excluded_total = 0
        for d in dates:
            sig = fn(mkt, as_of=d, wide=wide)
            if not sig.empty:
                n_excluded_total += sig.attrs.get("n_excluded_split_risk", 0)
                all_sig.append(sig)
        print(f"    {mkt}: {len(dates)} rebalance dates scanned"
              + (f", {n_excluded_total} split-risk exclusions" if n_excluded_total else ""))
    return pd.concat(all_sig, ignore_index=True) if all_sig else pd.DataFrame()


def score(signals: pd.DataFrame, id_col: str, min_days: int) -> pd.DataFrame:
    """Generic entry-bar-correct, benchmark-relative scorer. id_col is
    'symbol' for factor_screens.py output. Reuses the exact benchmark
    construction validated for debt_turnaround_screen.py."""
    if signals.empty:
        return pd.DataFrame()
    today = pd.Timestamp.today().normalize()
    signals = signals.copy()
    signals["signal_date"] = pd.to_datetime(signals["signal_date"])
    signals["days_held"] = (today - signals["signal_date"]).dt.days
    ready = signals[signals["days_held"] >= min_days]
    if ready.empty:
        return pd.DataFrame()

    rows = []
    skipped = {"not_in_panel": 0, "too_early": 0, "stale_entry": 0, "split_risk": 0}
    STALE_ENTRY_DAYS = 30  # calendar days; see 2026-08-23 CETX finding below
    for mkt, grp in ready.groupby("market"):
        p = ST.PANELS.get(mkt)
        if not p or not p.exists():
            continue
        px = ST._panel(p, columns=["Date", "Symbol", "Close"])
        px["Symbol"] = px["Symbol"].astype(str).str.upper()
        wide = px.pivot_table(index="Date", columns="Symbol", values="Close",
                              aggfunc="last").sort_index()
        bench = _india_benchmark() if mkt == "IN" else (
            wide[ST.BENCH.get(mkt)].dropna() if ST.BENCH.get(mkt) in wide.columns
            else pd.Series(dtype=float))
        for _, r in grp.iterrows():
            sym = str(r[id_col]).upper()
            if sym not in wide.columns:
                skipped["not_in_panel"] += 1; continue
            s = wide[sym].dropna()
            # ENTRY-BAR-CORRECT: the NEXT bar strictly after signal_date, not
            # the signal-date bar itself -- for a factor detected as-of a
            # close, entering ON that same close is unobtainable (the exact
            # bug fixed 2026-08-22 in backtest_screeners.py).
            after_sig = s[s.index > r["signal_date"]]
            if after_sig.empty:
                skipped["too_early"] += 1; continue
            entry_px, entry_dt = float(after_sig.iloc[0]), after_sig.index[0]
            # 🔴 2026-08-23 finding: without a staleness guard, a ticker with
            # a multi-year GAP in its price history (e.g. CETX: signal fired
            # 2012-01-10, next available bar was 2016-06-27 -- a 4-YEAR gap)
            # silently "enters" years late, producing a nonsensical trade
            # that bears no resemblance to what the signal actually meant.
            # Four distinct historical CETX signals all collapsed onto that
            # same 2016 bar, and this single distorted symbol dominated the
            # median "-118% vs bench" result that triggered this fix. Reject
            # any entry more than STALE_ENTRY_DAYS calendar days after the
            # signal rather than accept an arbitrarily delayed one.
            if (entry_dt - r["signal_date"]).days > STALE_ENTRY_DAYS:
                skipped["stale_entry"] += 1; continue
            # Same split-artifact guard as high_52w() (factor_screens.py),
            # applied at the entry/exit transition specifically -- distressed
            # micro-caps like CETX are exactly the class of stock prone to
            # unadjusted reverse splits contaminating a single bar.
            prior = s[s.index < entry_dt]
            if len(prior) and prior.iloc[-1] > 0 and abs(entry_px / prior.iloc[-1] - 1) > 0.60:
                skipped["split_risk"] += 1; continue
            after = s[s.index >= entry_dt]
            if len(after) < 2:
                skipped["too_early"] += 1; continue
            last_px, last_dt = float(after.iloc[-1]), after.index[-1]
            if len(after) > 1 and after.iloc[-2] > 0 and abs(last_px / after.iloc[-2] - 1) > 0.60:
                skipped["split_risk"] += 1; continue
            ret = (last_px / entry_px - 1) * 100
            bafter = bench[(bench.index >= entry_dt) & (bench.index <= last_dt)]
            bench_ret = ((float(bafter.iloc[-1]) / float(bafter.iloc[0]) - 1) * 100
                        if len(bafter) >= 2 else np.nan)
            rows.append({"symbol": sym, "market": mkt, "signal_date": r["signal_date"],
                        "entry_date": entry_dt, "ret_pct": ret, "bench_ret_pct": bench_ret,
                        "xret_pct": ret - bench_ret if pd.notna(bench_ret) else np.nan,
                        "days_held": (last_dt - entry_dt).days})
    out = pd.DataFrame(rows)
    out.attrs["skipped"] = skipped
    return out


def report(name: str, scored: pd.DataFrame, raw_signal_count: int, n_excluded: int = 0):
    excl = f", {n_excluded} excluded as implausible/data-error" if n_excluded else ""
    print(f"\n  {'='*78}\n  {name}  ({raw_signal_count} raw signals detected{excl})")
    skip_msg = ", ".join(f"{k}={v}" for k, v in scored.attrs.get("skipped", {}).items() if v)
    if skip_msg:
        print(f"  skipped during scoring: {skip_msg}")
    if scored.empty:
        print("  nothing scoreable yet"); return
    print(f"  {'-'*78}")
    print(f"  {'market':<7}{'n':>6}{'med ret%':>10}{'med vs bench':>14}{'win%':>7}{'med days':>10}")
    for mkt, g in scored.groupby("market"):
        print(f"  {mkt:<7}{len(g):>6}{g.ret_pct.median():>10.2f}"
              f"{g.xret_pct.median():>14.2f}{(g.ret_pct>0).mean()*100:>6.0f}%"
              f"{g.days_held.median():>10.0f}")
    print(f"  OVERALL n={len(scored)}  median vs bench = {scored.xret_pct.median():.2f}%  "
          f"win rate (raw) = {(scored.ret_pct>0).mean()*100:.0f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--min-days", type=int, default=21)
    a = ap.parse_args()

    print("=" * 88)
    print("  FACTOR SCREEN BACKTESTS — 2026-08-23")
    print("=" * 88)

    print("\n[1/4] 12-1 momentum (Jegadeesh & Titman 1993), monthly rebalance...")
    mom = scan_history(FS.momentum_12_1, ["IN", "US"], a.years)
    mom_scored = score(mom, "symbol", a.min_days) if not mom.empty else pd.DataFrame()
    report("MOMENTUM 12-1", mom_scored, len(mom))

    print("\n[2/4] 52-week-high proximity (George & Hwang 2004), monthly rebalance...")
    h52 = scan_history(FS.high_52w, ["IN", "US"], a.years)
    h52_scored = score(h52, "symbol", a.min_days) if not h52.empty else pd.DataFrame()
    report("52-WEEK-HIGH PROXIMITY", h52_scored, len(h52))

    print("\n[3/4] Gross profitability (Novy-Marx 2013), US only, per-filing-period ranked...")
    gp = FS.gross_profitability("US")
    gp_scored = score(gp, "symbol", a.min_days) if not gp.empty else pd.DataFrame()
    report("GROSS PROFITABILITY (US)", gp_scored, len(gp), gp.attrs.get("n_excluded_implausible", 0))

    print("\n[4/4] Accruals (Sloan 1996), US only, per-filing-period ranked...")
    acc = FS.accruals("US")
    acc_scored = score(acc, "symbol", a.min_days) if not acc.empty else pd.DataFrame()
    report("ACCRUALS (US)", acc_scored, len(acc), acc.attrs.get("n_excluded_implausible", 0))

    print(f"\n{'='*88}\n  'vs bench' is what matters — beating the index over the SAME holding "
         f"period. Raw win rate is shown for reference only; it does not control for "
         f"a rising market lifting most names regardless of the signal.")


if __name__ == "__main__":
    main()
