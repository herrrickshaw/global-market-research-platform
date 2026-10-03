#!/usr/bin/env python3
"""
test_purge_embargo.py — proves purge_embargo.py's boundary arithmetic against
hand-computed expected results on synthetic trading calendars. A subtly wrong
purge/embargo boundary is worse than no purge at all (it launders leakage
behind a false sense of rigor) — this is the whole reason the 2026-08-23
research round argued for a hand-built ~40-80 line function over a dependency:
small enough to actually verify by hand, which this file does.

Run: python3 -m pytest test_purge_embargo.py -v
     (or: python3 test_purge_embargo.py  -- falls back to plain asserts if
     pytest isn't on the path, so this is checkable without a new dependency)
"""
import numpy as np
import pandas as pd

from purge_embargo import embargo_mask, purge_mask, train_test_val_gap


def _bdays(start: str, n: int) -> pd.DatetimeIndex:
    """n business-day trading dates starting at `start`, weekends skipped —
    a clean synthetic calendar with no holidays, so overlap positions are
    hand-computable without special-casing a real exchange calendar."""
    return pd.bdate_range(start=start, periods=n)


def test_purge_mask_exact_boundary():
    # 20 trading days, horizon=3: date[i]'s label window is [date[i], date[i+3]]
    dates = _bdays("2024-01-01", 20)
    # test period = dates[10:13] (a 3-day block)
    test_start, test_end = dates[10], dates[12]
    mask = purge_mask(dates, test_start, test_end, horizon_days=3)
    # date[7]'s label window is [date[7], date[10]] -- date[10]==test_start,
    # so it DOES overlap (touches the boundary) and must be purged.
    assert mask[7], "date[7] (label reaches exactly to test_start) must be purged"
    # date[6]'s label window is [date[6], date[9]] -- date[9] < test_start,
    # no overlap, must NOT be purged.
    assert not mask[6], "date[6] (label ends before test_start) must survive"
    # every date inside [test_start, test_end] itself must be purged (it IS the boundary range)
    assert mask[10] and mask[11] and mask[12]
    # a date well after test_end (label window entirely past test) must survive
    assert not mask[15]
    print("  test_purge_mask_exact_boundary: PASS")


def test_purge_mask_horizon_zero_is_noop_beyond_the_block_itself():
    dates = _bdays("2024-01-01", 20)
    test_start, test_end = dates[10], dates[12]
    mask = purge_mask(dates, test_start, test_end, horizon_days=0)
    # with horizon=0, a date's label window is just itself -- only dates
    # actually inside [test_start, test_end] should be marked
    assert not mask[9]
    assert mask[10] and mask[11] and mask[12]
    assert not mask[13]
    print("  test_purge_mask_horizon_zero_is_noop_beyond_the_block_itself: PASS")


def test_embargo_mask_after():
    dates = _bdays("2024-01-01", 20)
    boundary = dates[10]
    mask = embargo_mask(dates, boundary, embargo_days=3, direction="after")
    # exactly dates[11], dates[12], dates[13] should be embargoed (3 trading
    # days strictly after the boundary)
    expected = np.zeros(20, dtype=bool)
    expected[11:14] = True
    assert (mask == expected).all(), f"got {np.where(mask)[0].tolist()}, expected [11,12,13]"
    print("  test_embargo_mask_after: PASS")


def test_embargo_mask_before():
    dates = _bdays("2024-01-01", 20)
    boundary = dates[10]
    mask = embargo_mask(dates, boundary, embargo_days=3, direction="before")
    expected = np.zeros(20, dtype=bool)
    expected[7:10] = True
    assert (mask == expected).all(), f"got {np.where(mask)[0].tolist()}, expected [7,8,9]"
    print("  test_embargo_mask_before: PASS")


def test_train_test_val_gap_pushes_naive_boundaries_forward():
    # 400 trading days, plenty of room. horizon=5, embargo=10 -> required
    # gap = 15 trading days at each boundary.
    dates = _bdays("2024-01-01", 400)
    train_end = dates[100]
    naive_test_start = dates[101]     # zero-gap naive split, like the repo's current bug
    naive_val_start = dates[200]
    test_start, val_start = train_test_val_gap(
        train_end, naive_test_start, naive_val_start,
        horizon_days=5, trading_dates=dates, embargo_days=10)

    gap1 = dates.get_loc(test_start) - dates.get_loc(train_end)
    assert gap1 == 15, f"train->test gap = {gap1}, expected 15"

    # val gap is measured from test's NAIVE last observation (dates[199],
    # the day before naive_val_start=dates[200]), not from the shifted
    # test_start -- this is exactly the bug caught and fixed during review.
    test_end_naive_pos = 199
    gap2 = dates.get_loc(val_start) - test_end_naive_pos
    assert gap2 == 15, f"test->val gap = {gap2}, expected 15"
    print("  test_train_test_val_gap_pushes_naive_boundaries_forward: PASS")


def test_train_test_gap_never_moves_earlier_than_naive():
    # if the naive split already had more slack than the gap requires, the
    # function must NOT pull test_start earlier -- the gap is a floor.
    dates = _bdays("2024-01-01", 400)
    train_end = dates[100]
    naive_test_start = dates[150]  # already 50 trading days of slack
    naive_val_start = dates[250]
    test_start, _ = train_test_val_gap(
        train_end, naive_test_start, naive_val_start,
        horizon_days=5, trading_dates=dates, embargo_days=10)
    assert test_start == naive_test_start, "must not pull test_start earlier than naive"
    print("  test_train_test_gap_never_moves_earlier_than_naive: PASS")


def test_val_gap_never_moves_earlier_when_naive_already_has_slack():
    # test/val are adjacent by construction in a naive contiguous schedule
    # (test's naive end is always the trading day right before naive_val_start),
    # so val_start can only stay at naive_val_start if the required gap is
    # small enough that "1 trading day of natural adjacency" already covers
    # it -- there is no way to manufacture slack here by moving test_start,
    # since the val gap is deliberately anchored on test's NAIVE end, not on
    # wherever test_start itself ends up (see the regression test below for
    # why that anchoring choice matters).
    dates = _bdays("2024-01-01", 400)
    train_end = dates[100]
    naive_test_start = dates[101]
    naive_val_start = dates[200]
    # horizon+embargo=0 -> required gap is 0, trivially satisfied by anything
    _, val_start = train_test_val_gap(
        train_end, naive_test_start, naive_val_start,
        horizon_days=0, trading_dates=dates, embargo_days=0)
    assert val_start == naive_val_start, "zero required gap must not move val_start"
    print("  test_val_gap_never_moves_earlier_when_naive_already_has_slack: PASS")


def test_train_test_val_gap_regression_bug_would_have_failed_this():
    # THE BUG THIS TEST WOULD HAVE CAUGHT: an earlier draft measured the
    # test->val gap from test_start (the newly-shifted value) instead of
    # from test's own last observation. If train->test purging pushed
    # test_start forward by MORE than the horizon+embargo gap, that buggy
    # version would have under-counted the test->val gap. Construct exactly
    # that scenario: a huge train->test gap forces test_start far forward,
    # then confirm test->val is STILL a full, independent 15-day gap from
    # test's actual naive end, not shrunk by how far test_start moved.
    dates = _bdays("2024-01-01", 400)
    train_end = dates[100]
    naive_test_start = dates[101]   # zero slack, forces the full 15-day push
    naive_val_start = dates[120]    # test period is naively only 19 days wide
    test_start, val_start = train_test_val_gap(
        train_end, naive_test_start, naive_val_start,
        horizon_days=5, trading_dates=dates, embargo_days=10)
    test_end_naive_pos = 119  # day before naive_val_start (dates[120])
    gap2 = dates.get_loc(val_start) - test_end_naive_pos
    assert gap2 == 15, (f"test->val gap = {gap2}, expected 15 -- if this is "
                        f"anything else, the val-gap anchor regressed to "
                        f"measuring from test_start again")
    print("  test_train_test_val_gap_regression_bug_would_have_failed_this: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
