#!/usr/bin/env python3
"""test_piotroski_fscore.py — hand-computed check for the 9-point F-score
logic in run_existing_screeners_fixed.py. Run: python3 test_piotroski_fscore.py"""
import numpy as np
import pandas as pd

import run_existing_screeners_fixed as R


def _row(ticker, period, **kw):
    base = dict(ticker=ticker, fiscal_period=period, filed=f"{period[:4]}-05-01",
               fy_end=f"{period[:4]}-03-31", net_income=np.nan, cfo=np.nan,
               revenue=np.nan, gross_profit=np.nan, long_term_debt=np.nan,
               current_assets=np.nan, current_liabilities=np.nan, shares=np.nan,
               assets_est=np.nan)
    base.update(kw)
    return base


def test_perfect_score_hits_9_of_9():
    # period 1: baseline. period 2: every metric improves in the F-score direction.
    rows = [
        _row("PERFECT", "2020Q1", net_income=5, cfo=8, revenue=100, gross_profit=40,
             long_term_debt=50, current_assets=60, current_liabilities=40,
             shares=1000, assets_est=200),
        _row("PERFECT", "2021Q1", net_income=10, cfo=15, revenue=120, gross_profit=55,
             long_term_debt=30, current_assets=80, current_liabilities=35,
             shares=1000, assets_est=210),
    ]
    df = pd.DataFrame(rows)
    df["filed"] = pd.to_datetime(df["filed"])
    df["fy_end"] = pd.to_datetime(df["fy_end"])
    orig = R._psql
    R._psql = lambda q: df
    try:
        out = R.piotroski_fscore("US")
    finally:
        R._psql = orig
    row = out[(out.symbol == "PERFECT")]
    assert len(row) == 1, "only period 2 has a prior period to compare against"
    assert row.iloc[0]["fscore"] == 9, f"expected 9/9, got {row.iloc[0]['fscore']}"
    print("  test_perfect_score_hits_9_of_9: PASS")


def test_worst_score_hits_0_of_9():
    rows = [
        _row("WORST", "2020Q1", net_income=5, cfo=8, revenue=100, gross_profit=40,
             long_term_debt=30, current_assets=80, current_liabilities=35,
             shares=1000, assets_est=200),
        # every metric moves the WRONG way
        _row("WORST", "2021Q1", net_income=-10, cfo=-20, revenue=90, gross_profit=25,
             long_term_debt=60, current_assets=50, current_liabilities=60,
             shares=1200, assets_est=210),
    ]
    df = pd.DataFrame(rows)
    df["filed"] = pd.to_datetime(df["filed"])
    df["fy_end"] = pd.to_datetime(df["fy_end"])
    orig = R._psql
    R._psql = lambda q: df
    try:
        out = R.piotroski_fscore("US")
    finally:
        R._psql = orig
    assert out.empty, "0/9 must not pass the >=7 threshold"
    print("  test_worst_score_hits_0_of_9: PASS")


def test_missing_field_excludes_that_point_not_fails_it():
    # PARTIAL has no shares data at all -- p7 (no dilution) must be excluded
    # from BOTH the numerator and the max-achievable denominator, not scored
    # as a failure (0), which would wrongly understate the company's F-score.
    rows = [
        _row("PARTIAL", "2020Q1", net_income=5, cfo=8, revenue=100, gross_profit=40,
             long_term_debt=50, current_assets=60, current_liabilities=40,
             assets_est=200),  # shares intentionally absent
        _row("PARTIAL", "2021Q1", net_income=10, cfo=15, revenue=120, gross_profit=55,
             long_term_debt=30, current_assets=80, current_liabilities=35,
             assets_est=210),  # shares intentionally absent both periods
    ]
    df = pd.DataFrame(rows)
    df["filed"] = pd.to_datetime(df["filed"])
    df["fy_end"] = pd.to_datetime(df["fy_end"])
    orig = R._psql
    R._psql = lambda q: df
    try:
        out = R.piotroski_fscore("US")
    finally:
        R._psql = orig
    row = out[(out.symbol == "PARTIAL")]
    assert len(row) == 1, "8 of 9 criteria evaluable (>=7) should still qualify"
    assert row.iloc[0]["fscore"] == 8, f"expected 8/8 evaluable points, got {row.iloc[0]['fscore']}"
    assert row.iloc[0]["fscore_max"] == 8
    print("  test_missing_field_excludes_that_point_not_fails_it: PASS")


def test_no_prior_period_gives_no_signal():
    rows = [_row("FIRST", "2020Q1", net_income=5, cfo=8, revenue=100, gross_profit=40,
                long_term_debt=50, current_assets=60, current_liabilities=40,
                shares=1000, assets_est=200)]
    df = pd.DataFrame(rows)
    df["filed"] = pd.to_datetime(df["filed"])
    df["fy_end"] = pd.to_datetime(df["fy_end"])
    orig = R._psql
    R._psql = lambda q: df
    try:
        out = R.piotroski_fscore("US")
    finally:
        R._psql = orig
    assert out.empty, "a ticker's first period has no prior to compare against -- must not fabricate a score"
    print("  test_no_prior_period_gives_no_signal: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
