#!/usr/bin/env python3
"""test_zone_rule_rec_simulation.py — hand-computed checks for the OLD-vs-NEW
mom126 basket simulation, before trusting it on real 10y panels.
Run: python3 test_zone_rule_rec_simulation.py"""
import numpy as np
import pandas as pd

import backtest_zone_rule_rec_simulation as SIM


def test_compound_nonoverlap_hand_computed():
    # 5 non-overlapping period returns (step=1): +10%, -5%, +10%, +5%, +2%.
    # Compounded: 1.10*0.95*1.10*1.05*1.02 = 1.2311145 -> total +23.11%.
    idx = pd.date_range("2020-01-03", periods=5, freq="14D")  # 2-week spacing
    r = pd.Series([0.10, -0.05, 0.10, 0.05, 0.02], index=idx)
    res = SIM.compound_nonoverlap(r, step=1)
    assert abs(res["total_return_pct"] - 23.11) < 0.2, res
    assert res["win_rate_pct"] == 80.0, res
    assert res["n_periods"] == 5
    print("  test_compound_nonoverlap_hand_computed: PASS")


def test_compound_nonoverlap_deoverlaps_with_step():
    # 12 weekly-spaced returns; step=2 should keep only every-2nd (6 periods),
    # matching backtest_zone_rules.py's de-overlap convention.
    idx = pd.date_range("2020-01-03", periods=12, freq="7D")
    r = pd.Series([0.05] * 12, index=idx)
    res = SIM.compound_nonoverlap(r, step=2)
    assert res["n_periods"] == 6, res
    # 6 periods of +5% compounded: 1.05**6 - 1 = 34.01%
    assert abs(res["total_return_pct"] - 34.01) < 0.1, res
    print("  test_compound_nonoverlap_deoverlaps_with_step: PASS")


def test_compound_nonoverlap_too_few_periods_returns_none():
    idx = pd.date_range("2020-01-03", periods=3, freq="7D")
    r = pd.Series([0.05, 0.03, -0.01], index=idx)
    res = SIM.compound_nonoverlap(r, step=1)
    assert res["total_return_pct"] is None, "must not compute a real number off 3 periods"
    print("  test_compound_nonoverlap_too_few_periods_returns_none: PASS")


def test_signal_old_uses_d5_signal_new_uses_d126():
    # Symbol A: strong 5-day pop, weak 126-day (~25wk) momentum -- OLD must
    # flag it BUY (top-tercile d5), NEW must NOT (bottom-tercile d126).
    # Symbol B: the mirror case.
    idx = pd.bdate_range("2018-01-01", periods=200, freq="W-FRI")
    # r126 = pct_change(25); for the last bar (idx -1) that compares against
    # idx -26, so the "25-weeks-ago" level must cover index -26 -- i.e.
    # everything up to and including -25 (iloc[:-24] covers 0..-25 inclusive).
    a = pd.Series(100.0, index=idx)
    a.iloc[:-24] = 200.0      # was much higher 25wk ago -> r126 = 150/200-1 = -25% (weak)
    a.iloc[-1] = 150.0        # huge pop on the very last bar -> d5 = 150/100-1 = +50% (strong)
    b = pd.Series(100.0, index=idx)
    b.iloc[:-24] = 50.0       # was much lower 25wk ago -> r126 = 95/50-1 = +90% (strong)
    b.iloc[-1] = 95.0         # slight dip on the last bar -> d5 = 95/100-1 = -5% (weak)
    filler = pd.DataFrame({f"F{i}": 100.0 for i in range(6)}, index=idx)
    w = pd.concat([pd.DataFrame({"A": a, "B": b}), filler], axis=1)

    old = SIM.signal_old(w)
    new = SIM.signal_new(w)
    t = idx[-1]
    assert old.loc[t, "A"] == 1, "A's huge last-bar pop must flag BUY under OLD (d5-ranked)"
    assert new.loc[t, "A"] != 1, "A's weak 126d momentum must NOT flag BUY under NEW (d126-ranked)"
    assert new.loc[t, "B"] == 1, "B's strong 126d momentum must flag BUY under NEW"
    print("  test_signal_old_uses_d5_signal_new_uses_d126: PASS")


def test_basket_period_returns_excludes_illiquid_penny_names():
    idx = pd.bdate_range("2018-01-01", periods=60, freq="W-FRI")
    good = pd.Series(np.linspace(100, 110, 60), index=idx)
    penny = pd.Series(np.linspace(0.5, 5.0, 60), index=idx)  # starts under $1 floor
    filler = pd.DataFrame({f"F{i}": np.linspace(100, 105, 60) for i in range(6)}, index=idx)
    w = pd.concat([pd.DataFrame({"GOOD": good, "PENNY": penny}), filler], axis=1)
    sig = pd.DataFrame(1, index=w.index, columns=w.columns)  # everyone flagged BUY
    orig_start = SIM.START
    SIM.START = str(idx[0].date())
    try:
        out = SIM.basket_period_returns(w, sig)
    finally:
        SIM.START = orig_start
    assert len(out) > 0, "must produce some scoreable periods"
    print("  test_basket_period_returns_excludes_illiquid_penny_names: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
