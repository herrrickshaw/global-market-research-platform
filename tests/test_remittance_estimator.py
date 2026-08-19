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

import pandas as pd
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


# ===========================================================================
# Real-savings / inflation module
# ===========================================================================
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "research", "diaspora"))

from real_savings_ranking import (  # noqa: E402
    INDIA_CPI,
    INDIA_WPI_INDEX,
    INDIA_WPI_YOY,
    USE_OF_FUNDS,
    WAGE_GRADE,
    WAGE_PPP_USD_2024,
    build_frame,
)


def test_wpi_yoy_is_derived_from_the_two_index_levels_not_asserted():
    expected = round((INDIA_WPI_INDEX["2026-04"] / INDIA_WPI_INDEX["2025-04"] - 1) * 100, 2)
    assert INDIA_WPI_YOY == expected


def test_wholesale_inflation_outruns_consumer_inflation():
    # The whole point of reporting both: an asset-directed remittance faces a
    # materially higher hurdle than a consumption-directed one.
    assert INDIA_WPI_YOY > INDIA_CPI["CPI (General)"]


def test_every_use_of_funds_maps_to_a_real_cpi_division():
    for use, idx in USE_OF_FUNDS.items():
        assert idx in INDIA_CPI, f"{use} points at a division not in the CPI table"


def test_every_wage_has_a_grade():
    assert set(WAGE_GRADE) == set(WAGE_PPP_USD_2024)
    assert all(g[0] in "ABC" for g in WAGE_GRADE.values())


def test_gulf_wages_are_migrant_specific_and_never_graded_a():
    # Gulf wages come from the ILO-anchored segment model, not the OECD series,
    # so they must never be graded A or enter the like-for-like table.
    for c in ("UAE", "Qatar", "Saudi Arabia", "Kuwait", "Oman", "Bahrain"):
        assert not WAGE_GRADE[c].startswith("A")
        assert "Indian-migrant-specific" in WAGE_GRADE[c]


def test_gulf_gets_no_basket_and_no_savings_figure():
    """Applying the advanced-economy basket to a Gulf migrant wage returns
    negative savings, which the observed remittance flow falsifies. The Gulf is
    carried for its wage only."""
    from real_savings_ranking import GULF

    d = build_frame(28000).set_index("country")
    gulf = d[d.index.isin(GULF)]
    assert len(gulf) == 6
    assert gulf.wage_ppp_usd.notna().all()
    assert gulf.real_basket_usd.isna().all()
    assert gulf.savings_ppp_usd.isna().all()


def test_ilo_correction_moved_the_gulf_wage_down_hard():
    """The recruitment-survey national averages overstated the Indian migrant
    wage by several times. If that correction is ever silently reverted, the
    Gulf reappears at the top of every savings table."""
    from gulf_wage_model import NATIONAL_AVERAGE_USD_YEAR, blended_wage

    central = blended_wage().set_index("scenario").blended_indian_migrant_usd_yr["central"]
    for _c, national in NATIONAL_AVERAGE_USD_YEAR.items():
        assert national / central > 4


def test_gulf_wage_band_is_consistent_with_the_knomad_survey_medians():
    """The blue-collar band is anchored on Qatar's post-2021 statutory floor.
    The 2015 survey predates that floor, so the check is not "both medians sit
    inside the band" — it is that the higher-paid nationality sits inside it and
    the lower-paid one sits below the floor that was later introduced to lift
    exactly such wages."""
    from gulf_wage_model import (
        BLUE_COLLAR_USD_YEAR,
        KNOMAD_QATAR_MEDIAN_USD_MONTH,
        KNOMAD_SURVEY_YEAR,
    )

    lo, hi = BLUE_COLLAR_USD_YEAR[0] / 12, BLUE_COLLAR_USD_YEAR[2] / 12
    assert KNOMAD_SURVEY_YEAR < 2021
    assert lo <= KNOMAD_QATAR_MEDIAN_USD_MONTH["Philippines"] <= hi
    assert KNOMAD_QATAR_MEDIAN_USD_MONTH["Ethiopia"] < lo
    # And the whole survey sits below the band's top, as pre-floor wages should.
    assert max(KNOMAD_QATAR_MEDIAN_USD_MONTH.values()) < hi


def test_only_qatar_and_kuwait_bind_on_migrant_workers():
    from gulf_wage_model import WAGE_FLOORS

    binding = {c for c, (_b, _t, covers, _n) in WAGE_FLOORS.items() if covers}
    assert binding == {"Qatar", "Kuwait"}
    # The two largest Indian-migrant destinations have no expatriate floor.
    for c in ("UAE", "Saudi Arabia"):
        assert WAGE_FLOORS[c][0] is None


def test_stock_composition_is_used_not_the_arrival_flow():
    """The arrival flow has shifted to majority-skilled; the stock has not.
    Using the flow mix would roughly double the modelled wage."""
    from gulf_wage_model import COMPOSITION_FLOW_2025, COMPOSITION_STOCK

    assert COMPOSITION_STOCK["blue_collar"] == 0.70
    assert COMPOSITION_FLOW_2025["skilled"] > COMPOSITION_STOCK["professional"]


def test_remittance_estimate_only_fits_the_most_generous_wage_scenario():
    """The headline cross-module finding: the ILO-anchored wage base supports
    the Gulf remittance figure only at the top of every band."""
    from gulf_wage_model import consistency_check, segment_decomposition

    cc = consistency_check(8659.0)
    assert (cc.verdict == "fits").sum() == 1
    assert cc.loc[cc.verdict == "fits", "wage scenario"].iat[0] == "high"
    sd = segment_decomposition(8659.0)
    assert (sd["credible?"] == "yes").sum() == 1


def test_savings_falls_as_the_basket_rises():
    lo = build_frame(20000).set_index("country").savings_ppp_usd
    hi = build_frame(36000).set_index("country").savings_ppp_usd
    common = lo.dropna().index.intersection(hi.dropna().index)
    assert len(common) > 5
    assert (hi[common] < lo[common]).all()


def test_transfer_cost_never_increases_what_lands_in_india():
    d = build_frame(28000).dropna(subset=["savings_ppp_usd"])
    assert (d.savings_landed_india_usd <= d.savings_ppp_usd).all()


def test_savings_rate_is_a_share_of_net_wage():
    d = build_frame(28000).dropna(subset=["savings_ppp_usd", "net_wage_ppp_usd"])
    recomputed = (d.savings_ppp_usd / d.net_wage_ppp_usd * 100).round(1)
    assert (recomputed - d.savings_rate_pct).abs().max() < 0.05


def test_the_two_rankings_genuinely_disagree():
    """If retention efficiency predicted absolute savings, the module would be
    redundant. It does not — that inversion is the finding."""
    from savings_destination_ranking import score

    d = build_frame(28000)
    like = d[d.wage_grade.str.startswith("A") & d.net_wage_ppp_usd.notna()].copy()
    like["savings_rank"] = range(1, len(like) + 1)
    ret = score(build(COUNTRIES, 0.5), "ACCUMULATE", "professional")
    ret = ret.dropna(subset=["score"]).reset_index(drop=True)
    ret["retention_rank"] = ret.index + 1
    m = like.merge(ret[["country", "retention_rank"]], on="country")
    assert m.retention_rank.corr(m.savings_rank) < 0.3
    # The US specifically: poor on retention, best on absolute savings.
    us = m.loc[m.country == "United States"].iloc[0]
    assert us.savings_rank == 1
    assert us.retention_rank > len(m)


# ===========================================================================
# Effective tax rate — the wage/rate mismatch fix
# ===========================================================================
def test_effective_rate_interpolates_between_the_two_known_points():
    import pandas as pd

    from real_savings_ranking import effective_tax_rate

    wage = pd.Series([30000.0, 75000.0, 120000.0])
    r30 = pd.Series([10.0, 10.0, 10.0])
    r120 = pd.Series([40.0, 40.0, 40.0])
    got = effective_tax_rate(wage, r30, r120)
    assert got.iloc[0] == 10.0
    assert got.iloc[2] == 40.0
    assert got.iloc[1] == 25.0   # exactly halfway


def test_effective_rate_clamps_outside_the_known_range():
    import pandas as pd

    from real_savings_ranking import effective_tax_rate

    wage = pd.Series([5000.0, 400000.0])
    got = effective_tax_rate(wage, pd.Series([10.0, 10.0]), pd.Series([40.0, 40.0]))
    assert got.iloc[0] == 10.0    # never below the low anchor
    assert got.iloc[1] == 40.0    # never above the high anchor


def test_effective_rate_sits_inside_the_schedule_for_every_country():
    d = build_frame(28000).dropna(subset=["effective_tax_pct", "tax_burden_30k_pct"])
    assert (d.effective_tax_pct >= d.tax_burden_30k_pct - 1e-9).all()
    assert (d.effective_tax_pct <= d.tax_burden_120k_pct + 1e-9).all()


def test_the_old_bug_would_have_overtaxed_the_average_wage():
    """Every country's average wage is below $120k, so charging the $120k rate
    overstated tax everywhere. Guards against a silent revert."""
    d = build_frame(28000).dropna(subset=["effective_tax_pct"])
    assert (d.wage_ppp_usd < 120000).all()
    # Only where the schedule is actually progressive. The Gulf's is flat at
    # zero (Bahrain flat at 1%), so there the two rates coincide by definition.
    prog = d[d.tax_burden_120k_pct > d.tax_burden_30k_pct]
    assert len(prog) >= 7
    assert (prog.effective_tax_pct < prog.tax_burden_120k_pct).all()
    flat = d[d.tax_burden_120k_pct == d.tax_burden_30k_pct]
    assert (flat.effective_tax_pct == flat.tax_burden_120k_pct).all()


# ===========================================================================
# Immigration destination panel
# ===========================================================================
from immigration_destination_panel import (  # noqa: E402
    PATHWAY,
    US_BACKLOG,
    WAGE_PPP_USD_2024_EXTENDED,
    panel,
)


def test_panel_covers_more_than_the_savings_modules():
    d = panel()
    assert len(d) >= 30
    assert len(d) > len(WAGE_PPP_USD_2024)


def test_extended_wages_do_not_collide_with_the_ranked_set():
    """The extended set is grade B and must not silently overwrite a grade-A or
    ILO-anchored wage already in the ranked set."""
    assert not (set(WAGE_PPP_USD_2024_EXTENDED) & set(WAGE_PPP_USD_2024))


def test_every_country_with_a_wage_or_pathway_appears_once():
    d = panel()
    assert d.country.is_unique
    assert set(PATHWAY) <= set(d.country)


def test_blocked_reason_is_recorded_for_every_unrankable_row():
    d = panel()
    blocked = d[~d.has_savings_inputs]
    assert len(blocked) > 0
    assert (blocked.blocked_by.str.len() > 0).all()
    assert (d[d.has_savings_inputs].blocked_by == "").all()


def test_the_tax_schedule_is_now_the_binding_constraint():
    """Adding 14 OECD wages moved nothing into the ranked set — the gap is tax
    data, not wage data. If that ever flips, the README's claim is stale."""
    d = panel()
    blocked = d[~d.has_savings_inputs]
    tax_blocked = blocked.blocked_by.str.contains("no tax schedule").sum()
    wage_only = (blocked.blocked_by == "no wage").sum()
    assert tax_blocked > wage_only


def test_gulf_has_inputs_but_is_still_excluded_downstream():
    """Having wage + a zero tax schedule is not the same as being rankable on
    savings; the Gulf still has no migrant-specific living cost."""
    from real_savings_ranking import GULF

    d = panel().set_index("country")
    assert d.loc[list(GULF), "has_savings_inputs"].all()
    rs = build_frame(28000).set_index("country")
    assert rs.loc[list(GULF), "savings_ppp_usd"].isna().all()


def test_points_based_routes_reach_permanence_faster_than_sponsored_ones():
    d = panel().dropna(subset=["years_to_permanence"])
    pts = d[d.points_based]
    spons = d[~d.points_based.astype(bool)]
    assert pts.years_to_permanence.mean() < spons.years_to_permanence.mean()


def test_us_has_no_statutory_timeline_and_carries_the_backlog_note():
    d = panel().set_index("country")
    assert pd.isna(d.loc["United States", "years_to_permanence"])
    assert "US_BACKLOG" in d.loc["United States", "pathway_note"]
    assert "per-country cap" in US_BACKLOG["cause"]
