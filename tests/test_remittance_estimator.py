"""
Invariant tests for research/diaspora/india_remittance_estimator.py.

These guard the properties that make the estimate an estimate rather than a
pile of arithmetic: the reconciliation must move volume between countries
without creating or destroying any, every reconciled figure must stay inside
the band its two parent estimators define, and the denominator must never
exceed the population it is drawn from.

Run:
    python -m pytest tests/test_remittance_estimator.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "research", "diaspora"))

from india_remittance_estimator import (  # noqa: E402
    BASE_PARAMS,
    COUNTRIES,
    GCC,
    KNOMAD_2021_USDBN,
    TOTAL_REMIT_FY24_USDBN,
    build,
    calibrate_intensity,
    checks,
)

H_VALUES = [0.0, 0.25, 0.5, 0.75, 1.0]


@pytest.fixture(scope="module")
def df():
    return build(COUNTRIES, 0.5)


def _covered(frame):
    return frame.nri_count_jan25.notna()


# --------------------------------------------------------------- calibration
def test_intensity_index_is_anchored_to_the_gulf():
    idx, per_head = calibrate_intensity()
    assert idx["GCC"] == 1.0
    assert idx["Other"] == idx["Advanced"]
    # The two Gulf anchors must agree with each other far better than either
    # agrees with the US one — that contrast is the whole basis of the model.
    gulf_spread = abs(per_head["UAE"] - per_head["Saudi Arabia"]) / per_head["UAE"]
    us_gap = abs(per_head["UAE"] - per_head["United States"]) / per_head["UAE"]
    assert gulf_spread < 0.10
    assert us_gap > 0.30


def test_every_knomad_anchor_has_a_matching_country_row():
    names = {c[0] for c in COUNTRIES}
    assert set(KNOMAD_2021_USDBN) <= names


# ------------------------------------------------------------- conservation
@pytest.mark.parametrize("h", H_VALUES)
def test_reconciliation_conserves_the_covered_pot(h):
    """E3 redistributes; it must not leak. This caught a real $17bn leak."""
    d = build(COUNTRIES, h)
    cov = _covered(d)
    assert d.loc[cov, "e3_reconciled_usd_bn"].sum() == pytest.approx(
        d.loc[cov, "e1_survey_usd_bn"].sum(), abs=0.05
    )
    assert abs(d.attrs["reattribution_residual_usd_bn"]) < 1e-6


@pytest.mark.parametrize("h", H_VALUES)
def test_stock_model_conserves_the_covered_pot(h):
    d = build(COUNTRIES, h)
    cov = _covered(d)
    assert d.loc[cov, "e2_stock_usd_bn"].sum() == pytest.approx(
        d.loc[cov, "e1_survey_usd_bn"].sum(), abs=0.05
    )


def test_survey_estimate_never_exceeds_the_published_total(df):
    assert df.e1_survey_usd_bn.sum() <= TOTAL_REMIT_FY24_USDBN


# -------------------------------------------------------------------- bands
@pytest.mark.parametrize("h", H_VALUES)
def test_reconciled_stays_inside_the_parent_band(h):
    d = build(COUNTRIES, h)
    assert (d.e3_reconciled_usd_bn >= d.est_low_usd_bn - 1e-6).all()
    assert (d.e3_reconciled_usd_bn <= d.est_high_usd_bn + 1e-6).all()


def test_h_zero_reproduces_the_published_survey_exactly():
    d = build(COUNTRIES, 0.0)
    assert (d.e3_reconciled_usd_bn == d.e1_survey_usd_bn).all()


def test_raising_h_moves_volume_from_hubs_to_the_gulf():
    lo, hi = build(COUNTRIES, 0.0), build(COUNTRIES, 1.0)
    for hub in ("United States", "United Kingdom", "Singapore"):
        assert (hi.loc[hi.country == hub, "e3_reconciled_usd_bn"].iat[0]
                < lo.loc[lo.country == hub, "e3_reconciled_usd_bn"].iat[0])
    assert (hi[hi.bloc == "GCC"].e3_reconciled_usd_bn.sum()
            > lo[lo.bloc == "GCC"].e3_reconciled_usd_bn.sum())


# -------------------------------------------------------------- denominator
def test_remitter_base_never_exceeds_the_diaspora_it_is_drawn_from(df):
    cov = _covered(df)
    stock = df.loc[cov, "nri_count_jan25"].fillna(0) + df.loc[cov, "pio_count_jan25"].fillna(0)
    assert (df.loc[cov, "remitter_base_high"] <= stock).all()


def test_remitter_base_is_monotone(df):
    cov = _covered(df)
    assert (df.loc[cov, "remitter_base_low"] <= df.loc[cov, "remitter_base_central"]).all()
    assert (df.loc[cov, "remitter_base_central"] <= df.loc[cov, "remitter_base_high"]).all()


def test_per_head_bands_are_ordered(df):
    sub = df.dropna(subset=["per_remitter_central_usd"])
    assert (sub.per_remitter_low_usd <= sub.per_remitter_central_usd).all()
    assert (sub.per_remitter_central_usd <= sub.per_remitter_high_usd).all()


def test_gulf_parameters_assume_no_pio_remitting():
    # The Gulf has no naturalisation path, so a non-zero PIO propensity there
    # would be inventing remitters that cannot exist.
    assert BASE_PARAMS["GCC"]["pio_propensity"] == (0.0, 0.0, 0.0)


def test_countries_without_a_denominator_get_no_per_head_figure(df):
    missing = df[df.nri_count_jan25.isna()]
    assert len(missing) > 0
    assert missing.per_remitter_central_usd.isna().all()
    assert (missing.evidence_grade == "D - survey share only, no denominator").all()
    # ...but they still get a flow estimate.
    assert missing.e3_reconciled_usd_bn.notna().all()


# ---------------------------------------------------------------- findings
def test_correction_pulls_the_gulf_per_head_into_documented_behaviour(df):
    gulf = df[(df.bloc == "GCC") & df.per_remitter_central_usd.notna()]
    assert len(gulf) == len(GCC)
    assert (gulf.plausibility == "PLAUSIBLE").all()


def test_the_implausible_first_cut_readings_are_flagged_not_repeated(df):
    for hub in ("United Kingdom", "Singapore", "United States"):
        row = df.loc[df.country == hub].iloc[0]
        assert row.plausibility.startswith("ABOVE")
        assert row.per_remitter_central_usd < row.naive_per_nri_usd * 2


def test_full_check_suite_passes(df, capsys):
    assert checks(df, full=True)
