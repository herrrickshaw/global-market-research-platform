#!/usr/bin/env python3
"""
test_debt_turnaround_screen.py — proves detect_trajectory() against
hand-constructed ticker histories where the right answer is known by
inspection. Run: python3 test_debt_turnaround_screen.py
"""
import pandas as pd

from debt_turnaround_screen import detect_trajectory


def _mk(ticker, debts, ebits, revs, mkt="US"):
    n = len(debts)
    return pd.DataFrame({
        "ticker": [ticker] * n, "market": [mkt] * n,
        "fiscal_period": [f"{2020+i}Q4" for i in range(n)],
        "signal_date": pd.date_range("2020-01-01", periods=n, freq="YE"),
        "long_term_debt": debts, "ebit": ebits, "revenue": revs,
    })


def test_clean_turnaround_fires():
    # debt declining 300->200->100, ebit rising -50->10->50 (crosses to
    # positive at t), revenue rising 1000->1100->1300 -- textbook case
    df = _mk("FOO", [300, 200, 100], [-50, 10, 50], [1000, 1100, 1300])
    hits = detect_trajectory(df)
    assert len(hits) == 1 and hits.iloc[0]["ticker"] == "FOO"
    print("  test_clean_turnaround_fires: PASS")


def test_ebit_still_negative_does_not_fire():
    # ebit rising but never crosses above 0 -- "losing less", not a turnaround
    df = _mk("BAR", [300, 200, 100], [-50, -30, -10], [1000, 1100, 1300])
    hits = detect_trajectory(df)
    assert hits.empty, "ebit must be > 0 at t, not just improving"
    print("  test_ebit_still_negative_does_not_fire: PASS")


def test_debt_rising_does_not_fire():
    df = _mk("BAZ", [100, 200, 300], [-50, 10, 50], [1000, 1100, 1300])
    hits = detect_trajectory(df)
    assert hits.empty, "debt must be DECLINING, not rising"
    print("  test_debt_rising_does_not_fire: PASS")


def test_revenue_flat_does_not_fire():
    df = _mk("QUX", [300, 200, 100], [-50, 10, 50], [1000, 1000, 1000])
    hits = detect_trajectory(df)
    assert hits.empty, "revenue must be strictly rising, not flat"
    print("  test_revenue_flat_does_not_fire: PASS")


def test_non_monotonic_debt_does_not_fire():
    # debt dips then rebounds: 300 -> 150 -> 200 -- net decline over the
    # window but NOT monotonic; the strict rule should reject this
    df = _mk("WOBBLE", [300, 150, 200], [-50, 10, 50], [1000, 1100, 1300])
    hits = detect_trajectory(df)
    assert hits.empty, "a non-monotonic debt path must not pass the strict decline rule"
    print("  test_non_monotonic_debt_does_not_fire: PASS")


def test_insufficient_history_does_not_fire():
    # only 2 periods -- cannot see 3 consecutive, must not fire or crash
    df = _mk("SHORT", [200, 100], [10, 50], [1100, 1300])
    hits = detect_trajectory(df)
    assert hits.empty
    print("  test_insufficient_history_does_not_fire: PASS")


def test_missing_values_in_window_does_not_fire():
    import numpy as np
    df = _mk("GAPPY", [300, np.nan, 100], [-50, 10, 50], [1000, 1100, 1300])
    hits = detect_trajectory(df)
    assert hits.empty, "a NaN anywhere in the 3-period window must block the signal, not be skipped over"
    print("  test_missing_values_in_window_does_not_fire: PASS")


def test_only_the_qualifying_period_fires_not_every_period_after():
    # extend the clean-turnaround case by one more period where growth
    # continues -- t+1 should ALSO fire (its own trailing 3-window still
    # qualifies: 200,100,80 declining; 10,50,70 rising positive; revenue
    # rising) -- confirms the function evaluates EVERY period independently,
    # not just the first one it finds.
    df = _mk("CONT", [300, 200, 100, 80], [-50, 10, 50, 70], [1000, 1100, 1300, 1500])
    hits = detect_trajectory(df)
    assert len(hits) == 2, f"expected 2 qualifying periods, got {len(hits)}"
    print("  test_only_the_qualifying_period_fires_not_every_period_after: PASS")


def test_two_tickers_do_not_cross_contaminate():
    a = _mk("A", [300, 200, 100], [-50, 10, 50], [1000, 1100, 1300])
    b = _mk("B", [100, 200, 300], [10, -30, -50], [1300, 1100, 1000])  # opposite of a good case
    df = pd.concat([a, b], ignore_index=True)
    hits = detect_trajectory(df)
    assert set(hits["ticker"]) == {"A"}, f"got {set(hits['ticker'])}"
    print("  test_two_tickers_do_not_cross_contaminate: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
