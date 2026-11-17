#!/usr/bin/env python3
"""test_factor_screens.py — hand-computed checks for factor_screens.py's core
logic. Run: python3 test_factor_screens.py"""
import numpy as np
import pandas as pd

import factor_screens as FS


def test_momentum_12_1_hand_computed():
    idx = pd.bdate_range("2020-01-01", periods=300)
    # Symbol A: strong 12-1 momentum. Symbol B: flat. Symbol C: strong but
    # ONLY in the skipped last month (must NOT count toward mom_12_1).
    a = pd.Series(np.linspace(100, 200, 300), index=idx)   # steady rise
    b = pd.Series(100.0, index=idx)                         # flat
    c = pd.Series(100.0, index=idx)
    c.iloc[-10:] = 300.0  # huge pop entirely inside the last 21d skip window
    wide = pd.DataFrame({"A": a, "B": b, "C": c})
    orig = FS._wide_panel
    FS._wide_panel = lambda mkt: wide
    try:
        out = FS.momentum_12_1("TEST", as_of=idx[-1])
    finally:
        FS._wide_panel = orig
    assert "A" in set(out["symbol"]), "the steadily-rising symbol must be flagged"
    assert "C" not in set(out["symbol"]), \
        "a pop entirely inside the skip window must NOT count toward momentum"
    print("  test_momentum_12_1_hand_computed: PASS")


def test_momentum_insufficient_history_returns_empty():
    idx = pd.bdate_range("2020-01-01", periods=50)  # well under 252+21
    wide = pd.DataFrame({"A": np.linspace(100, 200, 50)}, index=idx)
    orig = FS._wide_panel
    FS._wide_panel = lambda mkt: wide
    try:
        out = FS.momentum_12_1("TEST", as_of=idx[-1])
    finally:
        FS._wide_panel = orig
    assert out.empty, "must return empty, not crash or fabricate a signal, with insufficient history"
    print("  test_momentum_insufficient_history_returns_empty: PASS")


def test_high_52w_hand_computed():
    idx = pd.bdate_range("2020-01-01", periods=260)
    a = pd.Series(100.0, index=idx)
    a.iloc[-1] = 100.0          # sits exactly at its own trailing high
    b = pd.Series(100.0, index=idx)
    b.iloc[100] = 150.0          # made its high 160 bars ago
    b.iloc[-1] = 90.0            # now well off it
    wide = pd.DataFrame({"A": a, "B": b})
    orig = FS._wide_panel
    FS._wide_panel = lambda mkt: wide
    try:
        out = FS.high_52w("TEST", as_of=idx[-1])
    finally:
        FS._wide_panel = orig
    row_a = out[out.symbol == "A"]
    assert len(row_a) and abs(row_a.iloc[0]["nearness_pct"] - 100.0) < 0.01
    print("  test_high_52w_hand_computed: PASS")


def test_high_52w_excludes_split_artifact():
    idx = pd.bdate_range("2020-01-01", periods=260)
    clean = pd.Series(np.linspace(100, 110, 260), index=idx)
    split = pd.Series(np.linspace(100, 110, 260), index=idx)
    split.iloc[150] = split.iloc[149] * 0.1  # a 90% one-day drop -- classic unadjusted split artifact
    wide = pd.DataFrame({"CLEAN": clean, "SPLIT": split})
    orig = FS._wide_panel
    FS._wide_panel = lambda mkt: wide
    try:
        out = FS.high_52w("TEST", as_of=idx[-1])
    finally:
        FS._wide_panel = orig
    assert "SPLIT" not in set(out["symbol"]), \
        "a symbol with a >60% one-day move (split artifact) must be excluded, not scored"
    print("  test_high_52w_excludes_split_artifact: PASS")


def test_sanity_check_flags_only_extreme_moves():
    idx = pd.bdate_range("2020-01-01", periods=10)
    s = pd.Series([100, 105, 95, 200, 190, 191, 50, 51, 52, 53], index=idx, dtype=float)
    wide = pd.DataFrame({"X": s})
    bad = FS._sanity_check_no_split_artifacts(wide, max_1d_move=0.60)
    # 100->200 is +100% (flagged), 200->190 is -5% (not flagged),
    # 191->50 is -74% (flagged)
    flagged_positions = bad["X"].to_numpy().nonzero()[0].tolist()
    assert 3 in flagged_positions, "100->200 (+100%) must be flagged"
    assert 6 in flagged_positions, "191->50 (-74%) must be flagged"
    assert 1 not in flagged_positions, "100->105 (+5%) must NOT be flagged"
    print("  test_sanity_check_flags_only_extreme_moves: PASS")


def test_gross_profitability_ranks_within_period_not_across_all_history():
    # Period 1 has generally low GP/assets values, period 2 generally high --
    # a ticker that would be "top decile" in period 1 might not be in period
    # 2's much stronger pool, and vice versa. Cross-sectional-per-period
    # ranking must respect that; a flat "top decile of everything" ranking
    # would wrongly let period 2's weakest names crowd out period 1 entirely.
    rows = []
    for i in range(20):  # period 1: values 1..20
        rows.append({"ticker": f"P1_{i}", "fiscal_period": "2020Q1", "filed": "2020-05-01",
                    "fy_end": "2020-03-31", "gross_profit": float(i + 1), "assets_est": 100.0})
    for i in range(20):  # period 2: values 101..120 (much higher pool)
        rows.append({"ticker": f"P2_{i}", "fiscal_period": "2021Q1", "filed": "2021-05-01",
                    "fy_end": "2021-03-31", "gross_profit": float(101 + i), "assets_est": 100.0})
    df = pd.DataFrame(rows)
    df["filed"] = pd.to_datetime(df["filed"])
    df["fy_end"] = pd.to_datetime(df["fy_end"])

    import factor_screens as FS
    orig = FS._psql
    FS._psql = lambda q: df
    try:
        out = FS.gross_profitability("US")
    finally:
        FS._psql = orig
    p1_hits = [s for s in out["symbol"] if s.startswith("P1_")]
    p2_hits = [s for s in out["symbol"] if s.startswith("P2_")]
    assert len(p1_hits) > 0, \
        "period 1's own top decile must be flagged even though its absolute values are far below period 2's"
    assert len(p2_hits) > 0, "period 2's top decile must also be flagged"
    print("  test_gross_profitability_ranks_within_period_not_across_all_history: PASS")


def test_rsi_oversold_hand_computed():
    # A steadily FALLING series should show low RSI (oversold); a steadily
    # RISING series should show high RSI (not oversold). Not a precise
    # hand-computed RSI value (Wilder smoothing makes that tedious to derive
    # by hand), but the DIRECTION is unambiguous and checkable.
    idx = pd.bdate_range("2020-01-01", periods=60)
    falling = pd.Series(np.linspace(200, 100, 60), index=idx)
    rising = pd.Series(np.linspace(100, 200, 60), index=idx)
    flat = pd.Series(150.0, index=idx)
    wide = pd.DataFrame({"FALLING": falling, "RISING": rising, "FLAT": flat})
    out = FS.rsi_oversold("TEST", as_of=idx[-1], wide=wide)
    assert "FALLING" in set(out["symbol"]), "a steadily falling price must show oversold RSI"
    assert "RISING" not in set(out["symbol"]), "a steadily rising price must NOT show oversold RSI"
    print("  test_rsi_oversold_hand_computed: PASS")


def test_rsi_oversold_insufficient_history_returns_empty():
    idx = pd.bdate_range("2020-01-01", periods=10)  # well under RSI_PERIOD+20
    wide = pd.DataFrame({"X": np.linspace(200, 100, 10)}, index=idx)
    out = FS.rsi_oversold("TEST", as_of=idx[-1], wide=wide)
    assert out.empty
    print("  test_rsi_oversold_insufficient_history_returns_empty: PASS")


def test_debt_reduction_simple_single_leg():
    df = pd.DataFrame([
        {"ticker": "DOWN", "fiscal_period": "2020Q1", "filed": "2020-05-01",
         "fy_end": "2020-03-31", "long_term_debt": 300.0},
        {"ticker": "DOWN", "fiscal_period": "2021Q1", "filed": "2021-05-01",
         "fy_end": "2021-03-31", "long_term_debt": 200.0},
        {"ticker": "UP", "fiscal_period": "2020Q1", "filed": "2020-05-01",
         "fy_end": "2020-03-31", "long_term_debt": 100.0},
        {"ticker": "UP", "fiscal_period": "2021Q1", "filed": "2021-05-01",
         "fy_end": "2021-03-31", "long_term_debt": 200.0},
    ])
    df["filed"] = pd.to_datetime(df["filed"])
    df["fy_end"] = pd.to_datetime(df["fy_end"])
    orig = FS._psql
    FS._psql = lambda q: df
    try:
        out = FS.debt_reduction_simple("US")
    finally:
        FS._psql = orig
    assert set(out["symbol"]) == {"DOWN"}, f"got {set(out['symbol'])}"
    print("  test_debt_reduction_simple_single_leg: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
