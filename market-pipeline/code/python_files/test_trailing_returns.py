#!/usr/bin/env python3
"""
test_trailing_returns.py — proves trailing_returns.py's window arithmetic and
pattern classification against synthetic, hand-computable data.

Run: python3 test_trailing_returns.py
"""
import numpy as np
import pandas as pd

import trailing_returns as TR


def test_nearest_on_or_before_exact_and_missing():
    idx = pd.bdate_range("2024-01-01", periods=10)
    s = pd.Series(range(100, 110), index=idx)  # 100, 101, ..., 109
    # exact match
    px, dt = TR._nearest_on_or_before(s, idx[5])
    assert px == 105 and dt == idx[5]
    # target inside a genuine weekend gap -> snaps to the Friday bar before it.
    # idx[4] = Friday 2024-01-05 (price 104); +2 days = Sunday 2024-01-07,
    # which is not itself a business day in this index.
    px, dt = TR._nearest_on_or_before(s, idx[4] + pd.Timedelta(days=2))
    assert px == 104 and dt == idx[4], f"got px={px} dt={dt}, expected 104 / {idx[4]}"
    # target before the series starts -> None
    px, dt = TR._nearest_on_or_before(s, idx[0] - pd.Timedelta(days=5))
    assert px is None and dt is None
    print("  test_nearest_on_or_before_exact_and_missing: PASS")


def test_annualize_known_values():
    # 10% return over exactly 365 days -> annualized = 10% (no compounding needed)
    assert abs(TR._annualize(10.0, 365) - 10.0) < 1e-6
    # 10% return over 182 days (~6mo) compounds to roughly 21% annualized
    ann = TR._annualize(10.0, 182)
    assert 20 < ann < 22, f"expected ~21%, got {ann}"
    # 0.3% over 1 day compounds to a huge annualized number -- just check it's
    # large and finite, not that it crashes
    ann1d = TR._annualize(0.3, 1)
    assert np.isfinite(ann1d) and ann1d > 100
    print("  test_annualize_known_values: PASS")


def test_trailing_returns_hand_computed_windows():
    # Build a price series where every window's base price is a distinct,
    # hand-placed value so each return is independently checkable.
    idx = pd.bdate_range("2020-01-01", periods=1400)  # ~5.5 years of bars
    price = pd.Series(100.0, index=idx)
    as_of = idx[1399]  # last bar

    def set_price_near(calendar_offset, value):
        target = as_of - calendar_offset
        pos = idx.searchsorted(target)
        price.iloc[max(0, pos)] = value

    price.iloc[-1] = 110.0                          # as-of price
    price.iloc[-2] = 100.0                           # 1 trading day back
    set_price_near(pd.DateOffset(weeks=1), 105.0)     # 1wk back
    set_price_near(pd.DateOffset(months=3), 90.0)     # 3mo back
    set_price_near(pd.DateOffset(months=6), 80.0)     # 6mo back
    set_price_near(pd.DateOffset(years=1), 70.0)      # 1y back
    set_price_near(pd.DateOffset(years=5), 55.0)      # 5y back

    wide = pd.DataFrame({"FOO": price})
    orig_wide_panel = TR._wide_panel
    TR._wide_panel = lambda mkt: (wide, as_of)
    try:
        df = TR.trailing_returns([("FOO", "TEST")], as_of=as_of)
    finally:
        TR._wide_panel = orig_wide_panel

    row = df.iloc[0]
    assert abs(row["ret_1d"] - 10.0) < 0.01, f"ret_1d={row['ret_1d']}"       # 110/100-1
    assert abs(row["ret_1wk"] - (110/105-1)*100) < 0.01, f"ret_1wk={row['ret_1wk']}"
    assert abs(row["ret_3mo"] - (110/90-1)*100) < 0.01, f"ret_3mo={row['ret_3mo']}"
    assert abs(row["ret_6mo"] - (110/80-1)*100) < 0.01, f"ret_6mo={row['ret_6mo']}"
    assert abs(row["ret_1y"] - (110/70-1)*100) < 0.01, f"ret_1y={row['ret_1y']}"
    assert abs(row["ret_5y"] - (110/55-1)*100) < 0.01, f"ret_5y={row['ret_5y']}"
    print("  test_trailing_returns_hand_computed_windows: PASS")


def test_trailing_returns_insufficient_history_gives_nan_not_crash():
    idx = pd.bdate_range("2026-01-01", periods=10)  # only 2 weeks of data
    price = pd.Series(range(100, 110), index=idx, dtype=float)
    wide = pd.DataFrame({"FOO": price})
    as_of = idx[-1]
    orig = TR._wide_panel
    TR._wide_panel = lambda mkt: (wide, as_of)
    try:
        df = TR.trailing_returns([("FOO", "TEST")], as_of=as_of)
    finally:
        TR._wide_panel = orig
    row = df.iloc[0]
    assert pd.notna(row["ret_1d"]), "1d should resolve with only 10 bars"
    assert pd.notna(row["ret_1wk"]), "1wk should resolve with only 10 bars"
    assert pd.isna(row["ret_1y"]), "1y must be NaN, not fabricated, with only 2 weeks of data"
    assert pd.isna(row["ret_5y"]), "5y must be NaN, not fabricated, with only 2 weeks of data"
    print("  test_trailing_returns_insufficient_history_gives_nan_not_crash: PASS")


def test_classify_pattern_reversal_up_matches_the_worked_example():
    # "a 6-month decline followed by 1 week of growth peaks investor interest"
    row = pd.Series({"ret_6mo": -15.0, "ret_1wk": 5.0,
                     "ret_1wk_ann": 0, "ret_6mo_ann": 0})
    assert TR.classify_pattern(row) == "REVERSAL_UP"
    print("  test_classify_pattern_reversal_up_matches_the_worked_example: PASS")


def test_classify_pattern_reversal_down_mirror():
    row = pd.Series({"ret_6mo": 15.0, "ret_1wk": -5.0,
                     "ret_1wk_ann": 0, "ret_6mo_ann": 0})
    assert TR.classify_pattern(row) == "REVERSAL_DOWN"
    print("  test_classify_pattern_reversal_down_mirror: PASS")


def test_classify_pattern_reversal_needs_real_threshold_not_noise():
    # a 1% wiggle after a decline should NOT count as a reversal
    row = pd.Series({"ret_6mo": -15.0, "ret_1wk": 1.0,
                     "ret_1wk_ann": 0, "ret_6mo_ann": 0})
    assert TR.classify_pattern(row) == "", "sub-threshold bounce must not flag REVERSAL_UP"
    print("  test_classify_pattern_reversal_needs_real_threshold_not_noise: PASS")


def test_classify_pattern_accel_up_when_no_reversal_shape():
    # same-direction momentum: both positive, short rate meaningfully above long rate
    row = pd.Series({"ret_6mo": 8.0, "ret_1wk": 4.0,   # not a reversal shape (both positive)
                     "ret_1wk_ann": TR._annualize(4.0, 7), "ret_6mo_ann": 17.0})
    assert TR.classify_pattern(row) == "ACCEL_UP"
    print("  test_classify_pattern_accel_up_when_no_reversal_shape: PASS")


def test_classify_pattern_accel_needs_real_week_not_annualized_noise():
    # a 1% week annualizes to ~68% -- beats a 17% 6mo rate on paper, but a
    # quiet week is not acceleration (this is what fired on 94% of names)
    row = pd.Series({"ret_6mo": 8.0, "ret_1wk": 1.0,
                     "ret_1wk_ann": TR._annualize(1.0, 7), "ret_6mo_ann": 17.0})
    assert TR.classify_pattern(row) == ""
    print("  test_classify_pattern_accel_needs_real_week_not_annualized_noise: PASS")


def test_classify_pattern_reversal_needs_real_prior_decline():
    # a -4% drift over 6 months is not a decline to reverse from
    row = pd.Series({"ret_6mo": -4.0, "ret_1wk": 9.0,
                     "ret_1wk_ann": 0, "ret_6mo_ann": 0})
    assert TR.classify_pattern(row) != "REVERSAL_UP"
    print("  test_classify_pattern_reversal_needs_real_prior_decline: PASS")


def test_split_suspect_suppresses_pattern():
    # 1:10 reverse split inside the last week of an otherwise falling series:
    # raw closes read as a +900% week after a 6mo decline -> would be REVERSAL_UP
    idx = pd.bdate_range("2025-01-01", "2026-09-18")
    price = pd.Series(np.linspace(10.0, 2.0, len(idx)), index=idx)
    price.iloc[-3:] = price.iloc[-3:] * 10
    wide = pd.DataFrame({"FOO": price})
    orig = TR._wide_panel
    TR._wide_panel = lambda mkt: (wide, idx[-1])
    try:
        df = TR.trailing_returns([("FOO", "TEST")])
    finally:
        TR._wide_panel = orig
    row = df.iloc[0]
    assert bool(row["split_suspect"]), "10x one-day jump must mark split_suspect"
    assert row["pattern"] == "", f"split-suspect row must not flag, got {row['pattern']}"
    print("  test_split_suspect_suppresses_pattern: PASS")


def test_ordinary_series_not_split_suspect():
    idx = pd.bdate_range("2025-01-01", "2026-09-18")
    price = pd.Series(np.linspace(10.0, 12.0, len(idx)), index=idx)
    assert not TR._has_split_jump(price, idx[-1])
    # a jump older than the 1y lookback doesn't count either
    old = price.copy(); old.iloc[:5] = old.iloc[:5] / 10
    assert not TR._has_split_jump(old, idx[-1])
    print("  test_ordinary_series_not_split_suspect: PASS")


def test_classify_pattern_default_empty():
    row = pd.Series({"ret_6mo": 8.0, "ret_1wk": 0.5,
                     "ret_1wk_ann": 15.0, "ret_6mo_ann": 17.0})
    assert TR.classify_pattern(row) == ""
    print("  test_classify_pattern_default_empty: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
