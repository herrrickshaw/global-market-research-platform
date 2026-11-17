#!/usr/bin/env python3
"""
backtest_zone_rule_rec_simulation.py — what a trader mechanically following
the digest's mom126 BUY calls would have ACTUALLY earned: OLD (the live bug —
mom126 silently ranked by d5) vs NEW (fixed — mom126 ranked by real d126),
on the 3 markets currently live on mom126 (US/JP/EU, per zone_regime.json's
active_rule in the current bull regime). See project_per_market_zone_rules.md
and backtest_zone_rule_horizon_fix.py for the bug itself.

DESIGN
------
Long-only, equal-weight, weekly-rebalanced BUY-tercile basket (top-tercile of
the ranking signal), held for the SAME FWD=10-trading-day window
backtest_zone_rules.py uses. Compounded over NON-OVERLAPPING periods (every
2nd weekly formation date, since a 10-trading-day/2-week hold overlaps by one
week between consecutive weekly formations) so the equity curve does not
double-count overlapping holds — same de-overlap technique
backtest_zone_rules.py already uses for its t-stat.

Benchmarked against each market's real index (^GSPC/^N225/^STOXX50E via
data_sources.multi_fetch, same source market_performance.py uses) compounded
over the IDENTICAL date grid, so OLD/NEW/benchmark are directly comparable.

Educational/research only. NOT investment advice.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from backtest_zone_rules import load_closes, MARKETS, TERCILE, START, FWD
from data_sources import fetch as multi_fetch

HERE = Path(__file__).resolve().parent
OUT_MD = HERE / "reports" / "zone_rule_rec_simulation.md"

# US/JP/EU are currently live on mom126 (zone_regime.json bull active_rule) --
# the bug actually affected production there. KR/IN currently run "revert"/
# "trend" respectively (unaffected by this bug), included for completeness --
# 🔴 KR's own zone_rules.json already shows mom126 (r126-ranked) tests NEGATIVE
# there (-0.329%/t-2.13, the intended "correct" version) even before any bug --
# so for Korea "fixed" does not imply "helps"; see the printed verdict.
AFFECTED_MARKETS = ("US", "JP", "EU", "KR", "IN")
LIVE_ON_MOM126 = ("US", "JP", "EU")   # for the summary note only
BENCH_TICKER = {"US": "^GSPC", "JP": "^N225", "EU": "^STOXX50E",
                "KR": "^KS11", "IN": "^NSEI"}
STEP = max(1, FWD // 5)   # weekly bars, FWD trading days -> FWD//5 weeks; de-overlap stride


def _tercile_sig(r: pd.DataFrame) -> pd.DataFrame:
    lo = r.rank(axis=1, pct=True)
    return (lo >= 1 - TERCILE).astype(int) - (lo <= TERCILE).astype(int)


def signal_old(w: pd.DataFrame) -> pd.DataFrame:
    """The live bug: mom126 ranked by 5-day return, non-inverted (top tercile = BUY)."""
    r5 = w.pct_change(1, fill_method=None)
    return _tercile_sig(r5)


def signal_new(w: pd.DataFrame) -> pd.DataFrame:
    """The fix: mom126 ranked by its real 126-trading-day (~6mo) return."""
    r126 = w.pct_change(25, fill_method=None)   # weekly bars: 25 weeks ~= 126 trading days
    return _tercile_sig(r126)


def basket_period_returns(w: pd.DataFrame, sig: pd.DataFrame) -> pd.Series:
    """Per formation-date forward return of the equal-weight BUY-tercile basket.
    Same tradeable floor (>=$1, local currency) and winsorization (+/-40%)
    backtest_zone_rules.score() uses, so this is apples-to-apples with the
    already-validated spread numbers."""
    fwd = (w.shift(-FWD // 5) / w - 1).clip(-0.40, 0.40)
    tradeable = w >= 1.0
    out = {}
    for t in w.index[w.index >= START]:
        f = fwd.loc[t].where(tradeable.loc[t])
        s = sig.loc[t]
        buys = f[s == 1].dropna()
        if len(buys) >= 6:
            out[t] = float(buys.mean())
    return pd.Series(out).sort_index()


def compound_nonoverlap(period_returns: pd.Series, step: int = STEP) -> dict:
    """De-overlap by taking every `step`-th formation date (matching
    backtest_zone_rules.py's t = sp.iloc[::2] technique), then compound those
    non-overlapping period returns into a real cumulative equity curve."""
    r = period_returns.iloc[::step]
    if len(r) < 5:
        return {"n_periods": len(r), "total_return_pct": None, "cagr_pct": None,
                "win_rate_pct": None, "sharpe": None}
    equity = (1 + r).cumprod()
    total = float(equity.iloc[-1] - 1) * 100
    years = (r.index[-1] - r.index[0]).days / 365.25
    cagr = (float(equity.iloc[-1]) ** (1 / years) - 1) * 100 if years > 0 else None
    win = float((r > 0).mean()) * 100
    sharpe = float(r.mean() / r.std() * np.sqrt(252 / (5 * step))) if r.std() else None
    return {"n_periods": len(r), "total_return_pct": round(total, 1),
            "cagr_pct": round(cagr, 1) if cagr is not None else None,
            "win_rate_pct": round(win, 1), "sharpe": round(sharpe, 2) if sharpe else None}


def benchmark_result(mkt: str, full_formation_index: pd.DatetimeIndex) -> dict:
    """Same non-overlapping compounding, applied to the real index. The
    forward return is computed on the benchmark's OWN full weekly grid first
    (matching how the strategy's `fwd` is computed before any date
    restriction), THEN restricted to the strategy's full (pre-step) formation
    dates, THEN de-overlapped by the same `step` inside compound_nonoverlap --
    exactly once. Reindexing to an already-de-overlapped date index before
    computing pct_change (an earlier version of this function did that) silently
    doubles the effective spacing and skips half the real de-overlapped periods."""
    tkr = BENCH_TICKER[mkt]
    data = multi_fetch([tkr], order=("yahoo", "stooq"), period="10y",
                       min_bars=60, verbose=False)
    df = data.get(tkr)
    if df is None or df.empty:
        return {"n_periods": 0, "total_return_pct": None, "cagr_pct": None,
                "win_rate_pct": None, "sharpe": None}
    close = pd.to_numeric(df["Close"], errors="coerce").dropna()
    close = close.asfreq("B").ffill(limit=2).resample("W-FRI").last()
    fwd = close.pct_change(FWD // 5).shift(-(FWD // 5))
    r = fwd.reindex(full_formation_index).dropna()
    r = r[r.index >= START]
    return compound_nonoverlap(r, step=STEP)


def main() -> int:
    rows = []
    for mkt in AFFECTED_MARKETS:
        print(f"\n{mkt}: loading 10y panel + benchmark …")
        w = load_closes(mkt)
        old_ret = basket_period_returns(w, signal_old(w))
        new_ret = basket_period_returns(w, signal_new(w))
        old_res = compound_nonoverlap(old_ret)
        new_res = compound_nonoverlap(new_ret)
        bench_res = benchmark_result(mkt, old_ret.index)
        live = "LIVE on mom126" if mkt in LIVE_ON_MOM126 else "NOT live (currently uses a different rule)"
        rows.append({"market": mkt, "live_status": live, "version": "OLD (buggy, d5-ranked)", **old_res})
        rows.append({"market": mkt, "live_status": live, "version": "NEW (fixed, d126-ranked)", **new_res})
        rows.append({"market": mkt, "live_status": live, "version": f"Benchmark ({BENCH_TICKER[mkt]})", **bench_res})

    df = pd.DataFrame(rows)
    print("\n" + "=" * 100)
    print("  mom126 BUY-BASKET SIMULATION — OLD vs NEW vs benchmark, non-overlapping periods")
    print("=" * 100)
    print(df.to_string(index=False))
    print("\nEducational/research only. NOT investment advice.")

    lines = ["# mom126 zone-rule fix — simulated BUY-basket performance", "",
             "Long-only, equal-weight, weekly-rebalanced BUY-tercile basket, held "
             f"{FWD} trading days, compounded over non-overlapping periods "
             "(matching backtest_zone_rules.py's de-overlap technique). "
             "OLD = the live bug (mom126 ranked by 5-day return). "
             "NEW = the fix (ranked by real 126-day/~6mo return). "
             "Educational/research only. NOT investment advice.", "",
             df.to_markdown(index=False)]
    OUT_MD.write_text("\n".join(lines))
    print(f"\nwrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
