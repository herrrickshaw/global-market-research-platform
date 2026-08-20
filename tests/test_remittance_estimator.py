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


# ===========================================================================
# ROI on a foreign life
# ===========================================================================
from roi_foreign_life import (  # noqa: E402
    GULF_RECRUITMENT_MONTHS,
    HOST_WAGE_GROWTH_BAND,
    PLFS_SALARIED_INR_MONTH,
    india_wage_growth,
    payback,
)


def test_india_wage_growth_is_derived_from_the_plfs_series():
    g = india_wage_growth()
    yrs = sorted(PLFS_SALARIED_INR_MONTH)
    lo, hi = PLFS_SALARIED_INR_MONTH[yrs[0]], PLFS_SALARIED_INR_MONTH[yrs[-1]]
    expected = round(((hi / lo) ** (1 / (yrs[-1] - yrs[0])) - 1) * 100, 2)
    assert g["cagr_pct"] == expected
    assert len(g["yoy_pct"]) == len(yrs) - 1


def test_the_crossover_holds_indian_wages_grow_faster():
    """The module's central finding. If PLFS is revised such that this flips,
    the conclusion must be rewritten rather than silently kept."""
    assert india_wage_growth()["cagr_pct"] > HOST_WAGE_GROWTH_BAND[1]


def test_india_wages_beat_india_cpi_in_real_terms():
    from real_savings_ranking import INDIA_CPI

    assert india_wage_growth()["cagr_pct"] > INDIA_CPI["CPI (General)"]


def test_india_wages_do_not_beat_wpi():
    """Which is why property is the case where the foreign premium fails."""
    from real_savings_ranking import INDIA_WPI_YOY

    assert india_wage_growth()["cagr_pct"] < INDIA_WPI_YOY


def test_payback_scales_inversely_with_savings():
    p = payback(15000)
    assert (p.payback_years.diff().dropna() >= 0).all()      # sorted ascending
    assert (p.savings_landed_india_usd.diff().dropna() <= 0).all()


def test_payback_is_proportional_to_cost():
    a, b = payback(10000), payback(20000)
    ja = a.set_index("country").payback_years
    jb = b.set_index("country").payback_years
    assert ((jb / ja).round(1) == 2.0).all()


def test_gulf_recruitment_cost_is_a_measured_range_not_a_point():
    lo, hi = GULF_RECRUITMENT_MONTHS
    assert lo < hi
    assert hi >= 9    # the survey's upper bound; nine months of earnings


# ===========================================================================
# OECD ingest slot
# ===========================================================================
def test_oecd_slot_is_empty_and_falls_back_to_interpolation():
    """The slot ships empty because oecd.org is unreachable here. Every row must
    therefore be on the interpolated basis, and say so."""
    from real_savings_ranking import OECD_NPATR_AT_AVERAGE_WAGE

    d = build_frame(28000)
    if not OECD_NPATR_AT_AVERAGE_WAGE:
        assert (d.tax_basis == "interpolated from the $30k/$120k schedule").all()


def test_an_oecd_rate_overrides_the_interpolation_for_that_country():
    """Proves the ingest path works before anyone has data to put in it."""
    import real_savings_ranking as rs

    original = dict(rs.OECD_NPATR_AT_AVERAGE_WAGE)
    try:
        rs.OECD_NPATR_AT_AVERAGE_WAGE["Germany"] = 37.5
        d = rs.build_frame(28000).set_index("country")
        assert d.loc["Germany", "effective_tax_pct"] == 37.5
        assert d.loc["Germany", "tax_basis"] == "OECD net personal average tax rate"
        # everyone else is untouched
        assert d.loc["Japan", "tax_basis"] == "interpolated from the $30k/$120k schedule"
    finally:
        rs.OECD_NPATR_AT_AVERAGE_WAGE.clear()
        rs.OECD_NPATR_AT_AVERAGE_WAGE.update(original)


def test_the_denmark_sanity_anchor_is_recorded_for_whoever_fills_the_slot():
    from real_savings_ranking import OECD_NPATR_SANITY

    assert OECD_NPATR_SANITY["max_country"] == "Denmark"
    assert 30 < OECD_NPATR_SANITY["max_rate_2024"] < 40


# ===========================================================================
# US debt service
# ===========================================================================
from us_debt_service import (  # noqa: E402
    AUTO,
    INDIA_EDU_LOAN,
    MORTGAGE,
    NYFED_Q1_2026_TRILLIONS,
    STUDENT_LOAN,
    emi,
    india_loan_emi_usd,
    scenarios,
    us_surplus,
)


def test_emi_matches_the_closed_form_annuity():
    # A loan at 0% amortises to principal/n; the formula must approach that.
    assert emi(120000, 0.0001, 10) == pytest.approx(1000, rel=1e-3)
    # And a known case: higher rate and longer tenor both raise the total paid.
    assert emi(1000000, 12, 15) > emi(1000000, 9, 15)
    assert emi(1000000, 9, 10) > emi(1000000, 9, 15)


def test_nyfed_components_do_not_exceed_the_total():
    parts = sum(v for k, v in NYFED_Q1_2026_TRILLIONS.items() if k != "total_household")
    assert parts <= NYFED_Q1_2026_TRILLIONS["total_household"]


def test_debt_service_only_reduces_what_lands():
    s = scenarios(87.0)
    base = s.iloc[0]
    assert base.debt_service_usd_yr == 0
    assert (s.lands_in_india_usd_yr <= base.lands_in_india_usd_yr).all()
    assert (s.share_of_surplus_pct >= 0).all()


def test_the_indian_financed_case_costs_more_than_half_the_surplus():
    s = scenarios(87.0).set_index("scenario")
    assert s.loc["Indian education loan + new car", "share_of_surplus_pct"] > 50


def test_a_weaker_rupee_makes_the_indian_loan_cheaper_in_dollars():
    """The one line in the whole analysis where rupee depreciation helps."""
    strong = scenarios(80.0).set_index("scenario")
    weak = scenarios(95.0).set_index("scenario")
    k = "Indian education loan, Rs 85L @ 9.15%"
    assert weak.loc[k, "debt_service_usd_yr"] < strong.loc[k, "debt_service_usd_yr"]


def test_india_loan_emi_rises_with_principal_and_rate():
    d = india_loan_emi_usd(87.0)
    for lender in d.lender.unique():
        sub = d[d.lender == lender].sort_values("loan_rs_lakh")
        assert (sub.emi_usd_month.diff().dropna() > 0).all()
    for lakh in d.loan_rs_lakh.unique():
        sub = d[d.loan_rs_lakh == lakh].sort_values("rate_pct")
        assert (sub.emi_usd_month.diff().dropna() > 0).all()


def test_mortgage_is_never_netted_against_the_surplus():
    """A mortgage replaces rent already in the basket and its principal is
    saving, not spending. Netting it would double-count housing AND misread
    equity as consumption. No scenario may include it."""
    s = scenarios(87.0)
    assert not s.scenario.str.contains("ortgage").any()
    # And the source figures are still carried, for the narrative.
    assert MORTGAGE["monthly_pi"] < MORTGAGE["monthly_piti"]
    assert MORTGAGE["first_payment_interest"] > MORTGAGE["first_payment_principal"]


def test_us_surplus_matches_the_savings_ranking():
    from real_savings_ranking import build_frame as bf

    s = us_surplus()
    r = bf(28000).set_index("country").loc["United States"]
    assert s["surplus"] == pytest.approx(float(r.savings_ppp_usd))
    assert s["landed"] == pytest.approx(float(r.savings_landed_india_usd))


def test_used_car_is_cheaper_than_new_and_masters_only_cheaper_than_with_undergrad():
    assert AUTO["monthly_used"] < AUTO["monthly_new"]
    assert STUDENT_LOAN["monthly_masters_only"] < STUDENT_LOAN["monthly_incl_undergrad"]
    assert INDIA_EDU_LOAN["cost_lakh_low"] < INDIA_EDU_LOAN["cost_lakh_high"]


# ===========================================================================
# Rent vs wages (non-US)
# ===========================================================================
from rent_vs_wages import PANEL, surplus_path  # noqa: E402
from rent_vs_wages import table as rent_table  # noqa: E402


def test_the_us_is_excluded_from_the_rent_panel():
    """The US is handled in us_debt_service.py on its own terms."""
    assert "United States" not in PANEL


def test_gap_is_wage_growth_minus_rent_growth():
    t = rent_table(0.35).set_index("country")
    for c, (w, r_sit, r_new, _n) in PANEL.items():
        assert t.loc[c, "gap_sitting_pp"] == pytest.approx(w - r_sit, abs=0.01)
        if r_new is not None:
            assert t.loc[c, "gap_new_pp"] == pytest.approx(w - r_new, abs=0.01)


def test_new_letting_rent_is_never_below_sitting_except_where_rents_are_falling():
    """Tenant protections hold sitting rents down, so new lettings normally run
    hotter. Canada is the exception because the whole market is falling."""
    for c, (_w, r_sit, r_new, _n) in PANEL.items():
        if r_new is None:
            continue
        if r_sit >= 0:
            assert r_new >= r_sit, c


def test_the_basis_flips_the_sign_where_protection_is_strongest():
    t = rent_table(0.35).set_index("country")
    flipped = set(t[t.basis_flips_sign].index)
    assert {"Japan", "Germany", "Netherlands"} <= flipped
    # And Japan is the widest gap of the panel.
    gaps = {c: v[2] - v[1] for c, v in PANEL.items() if v[2] is not None}
    assert max(gaps, key=gaps.get) == "Japan"


def test_new_letting_basis_is_never_kinder_than_sitting_where_they_differ():
    a = surplus_path(0.35, 10, False).set_index("country").change_pct
    b = surplus_path(0.35, 10, True).set_index("country").change_pct
    for c in a.index:
        r_sit, r_new = PANEL[c][1], PANEL[c][2]
        if r_new is not None and r_new > r_sit:
            assert b[c] < a[c], c


def test_a_bigger_rent_share_hurts_where_rent_outruns_wages():
    small = surplus_path(0.25, 10, True).set_index("country").change_pct
    large = surplus_path(0.45, 10, True).set_index("country").change_pct
    # Japan: rent growth far exceeds wage growth, so more rent exposure is worse.
    assert large["Japan"] < small["Japan"]
    # Canada: rents are falling, so more rent exposure is better.
    assert large["Canada"] > small["Canada"]


def test_japan_surplus_collapses_on_the_migrants_own_rent_basis():
    """The module's headline. Pinned so a data revision surfaces it."""
    sp = surplus_path(0.35, 10, True).set_index("country")
    assert sp.loc["Japan", "change_pct"] < -50
    assert (sp.drop(index="Japan").change_pct > 0).all()


def test_the_savings_ordering_survives_a_decade_of_rent_divergence():
    """Also a real result: what moves is the size of the gaps, not the order."""
    sp = surplus_path(0.35, 10, True)
    now = sp.sort_values("surplus_now_usd", ascending=False).country.tolist()
    later = sp.sort_values("surplus_yr10_usd", ascending=False).country.tolist()
    assert now == later


# ===========================================================================
# Consolidated ranking
# ===========================================================================
from consolidated_ranking import assemble, rank_of  # noqa: E402


def test_the_us_is_the_only_row_carrying_a_debt_adjustment():
    d = assemble().set_index("country")
    assert d.loc["United States", "yr1_debtloaded_usd"] < d.loc["United States", "yr1_debtfree_usd"]
    others = d.drop(index="United States")
    assert (others.yr1_debtloaded_usd == others.yr1_debtfree_usd).all()
    assert (others.debt_data == "none gathered").all()


def test_the_us_has_no_ten_year_figure_and_is_not_ranked_on_it():
    """rent_vs_wages is non-US by design, so the US cannot be placed on that
    horizon. It must be absent rather than silently defaulted."""
    d = assemble()
    us = d[d.country == "United States"].iloc[0]
    assert pd.isna(us.yr10_rentadj_usd)
    assert "United States" not in rank_of(d, "yr10_rentadj_usd")


def test_ranks_are_dense_and_start_at_one():
    d = assemble()
    for col in ("yr1_debtfree_usd", "yr1_debtloaded_usd", "yr10_rentadj_usd"):
        r = rank_of(d, col)
        assert sorted(r.values()) == list(range(1, len(r) + 1))


def test_ranking_is_by_descending_value():
    d = assemble()
    r = rank_of(d, "yr1_debtfree_usd")
    s = d.set_index("country").yr1_debtfree_usd
    best = min(r, key=r.get)
    assert s[best] == s.max()


def test_the_ordering_is_stable_across_all_three_horizons():
    """The module's central claim: over the countries present in all three,
    nothing moves. If a data revision breaks that, the write-up is stale."""
    d = assemble()
    r1, r2, r3 = (rank_of(d, c) for c in
                  ("yr1_debtfree_usd", "yr1_debtloaded_usd", "yr10_rentadj_usd"))
    common = [c for c in d.country if c in r3]
    assert len(common) == 6
    reb = [{c: i + 1 for i, c in enumerate(sorted(common, key=lambda x: r[x]))}
           for r in (r1, r2, r3)]
    for c in common:
        assert reb[0][c] == reb[1][c] == reb[2][c], c


def test_permanence_is_reported_but_not_folded_into_any_score():
    """It is in the table and deliberately out of the ordering — no savings
    figure prices a green-card queue."""
    d = assemble()
    assert "years_to_permanence" in d.columns
    r = rank_of(d, "yr1_debtfree_usd")
    byrank = sorted(r, key=r.get)
    perm = d.set_index("country").years_to_permanence
    # If permanence were in the score the ordering would track it; it does not.
    assert byrank != sorted(byrank, key=lambda c: (perm[c] if pd.notna(perm[c]) else 99))


def test_the_oecd_net_income_figures_are_carried_but_flagged_unusable():
    from real_savings_ranking import (
        OECD_NET_INCOME_AT_AW_USD_2025,
        OECD_NET_INCOME_NOTE,
        OECD_NPATR_AT_AVERAGE_WAGE,
        WAGE_PPP_USD_2024,
    )

    assert OECD_NPATR_AT_AVERAGE_WAGE == {}, "slot must stay empty until reconcilable"
    assert "different conversion basis" in OECD_NET_INCOME_NOTE
    # The proof they are unusable: dividing them by our gross wage series yields
    # tax rates no country levies. Nobody taxes an average wage at under 5%.
    for c in ("United Kingdom", "Switzerland"):
        implied = (1 - OECD_NET_INCOME_AT_AW_USD_2025[c] / WAGE_PPP_USD_2024[c]) * 100
        assert implied < 5, f"{c} implies {implied:.2f}% — absurd, hence the basis mismatch"


# ===========================================================================
# Literature validation
# ===========================================================================
from literature_validation import LIT, rows as lit_rows  # noqa: E402


def test_every_judgement_parameter_carries_a_verdict():
    valid = {"SUPPORTED", "DIRECTIONAL", "STRUCTURAL", "UNSUPPORTED"}
    for r in lit_rows():
        assert r["verdict"] in valid, r["parameter"]
        assert r["evidence"] and r["reading"], r["parameter"]


def test_unsupported_parameters_are_named_not_hidden():
    """Two parameters have no literature behind them. They must stay visible."""
    unsup = {r["parameter"] for r in lit_rows() if r["verdict"] == "UNSUPPORTED"}
    assert "Hub-routing exposure weights (h)" in unsup
    assert "Advanced-economy migration cost" in unsup


def test_the_wage_band_derives_from_the_measured_panel_not_a_literal():
    """The bug this exercise found: a hardcoded 2.0-4.0% band contradicted the
    repo's own panel, where the Netherlands runs at 4.50%."""
    from rent_vs_wages import PANEL
    from roi_foreign_life import HOST_WAGE_GROWTH_BAND

    w = [v[0] for v in PANEL.values()]
    assert HOST_WAGE_GROWTH_BAND == (min(w), max(w))
    for c, v in PANEL.items():
        assert HOST_WAGE_GROWTH_BAND[0] <= v[0] <= HOST_WAGE_GROWTH_BAND[1], c


def test_the_crossover_survives_the_widened_band():
    """Widening the band could have killed the ROI module's central finding.
    It does not — but if a data revision ever makes it, fail loudly."""
    from roi_foreign_life import HOST_WAGE_GROWTH_BAND, india_wage_growth

    assert india_wage_growth()["cagr_pct"] > HOST_WAGE_GROWTH_BAND[1]


def test_the_gulf_band_sits_above_the_global_mean_and_the_ae_band_below():
    """The IOM global average is 15%. Gulf labour migration should sit above it
    and advanced-economy professionals at or below it."""
    from india_remittance_estimator import PLAUSIBLE_REMIT_RATE

    global_mean = 0.15
    assert PLAUSIBLE_REMIT_RATE["GCC"][0] > global_mean
    assert PLAUSIBLE_REMIT_RATE["Advanced"][1] <= global_mean
    assert "15%" in LIT["iom_15pct"]


def test_rent_share_stays_under_the_eurostat_overburden_threshold():
    from rent_vs_wages import DEFAULT_RENT_SHARE

    assert DEFAULT_RENT_SHARE < 0.40, "40% is Eurostat's housing-cost overburden line"
    assert DEFAULT_RENT_SHARE > 0.25, "below this it stops being a market-rate city rent"


# ===========================================================================
# Salaried vs business-owner migrants
# ===========================================================================
from salaried_vs_business import (  # noqa: E402
    DIASPORA_BUSINESS,
    GULF_PER_REMITTER_USD,
    US_TAX_MECHANICS,
    gulf_decomposition,
    implied_business_remittance,
    structural_table,
    us_payroll_gap,
)


def test_self_employment_payroll_is_exactly_double_the_employee_share():
    """The employee pays one half; the self-employed pay both."""
    assert US_TAX_MECHANICS["self_employment_pct"] == pytest.approx(
        US_TAX_MECHANICS["employee_fica_pct"] * 2, abs=0.01)


def test_the_payroll_gap_grows_with_income_up_to_the_threshold():
    g = us_payroll_gap()
    assert (g.extra_cost_usd.diff().dropna() > 0).all()
    assert (g.self_employed_payroll_usd > g.employee_payroll_usd).all()


def test_both_populations_enter_india_through_the_same_channel():
    """The core point: the data cannot separate them."""
    t = structural_table().set_index("dimension")
    row = t.loc["Enters India as"]
    assert "NRE" in row["salaried migrant"]
    assert "NRE" in row["business-owner migrant"]
    assert "IDENTICAL" in row["business-owner migrant"]


def test_the_salaried_side_has_a_ceiling_and_the_business_side_does_not():
    t = structural_table().set_index("dimension")
    assert "ceiling" in t.loc["Income basis", "salaried migrant"]
    assert "no wage ceiling" in t.loc["Income basis", "business-owner migrant"]
    assert "Unbounded" in t.loc["Remittance ceiling", "business-owner migrant"]


def test_implied_business_remittance_solves_the_mixture():
    """Recover the observed average from the decomposition it implies."""
    wage, r, b = 15123.0, 0.40, 0.05
    v = implied_business_remittance(GULF_PER_REMITTER_USD, wage, r, b)
    recovered = (1 - b) * wage * r + b * v
    assert recovered == pytest.approx(GULF_PER_REMITTER_USD, abs=1)


def test_a_smaller_owner_share_demands_more_per_owner():
    wage, r = 15123.0, 0.40
    few = implied_business_remittance(GULF_PER_REMITTER_USD, wage, r, 0.03)
    many = implied_business_remittance(GULF_PER_REMITTER_USD, wage, r, 0.10)
    assert few > many


def test_a_higher_salaried_rate_demands_less_from_owners():
    wage, b = 15123.0, 0.05
    lo = implied_business_remittance(GULF_PER_REMITTER_USD, wage, 0.30, b)
    hi = implied_business_remittance(GULF_PER_REMITTER_USD, wage, 0.50, b)
    assert hi < lo


def test_every_gulf_decomposition_cell_is_plausible():
    """If any cell required an implausible per-owner figure, the business
    channel would not explain the gap and the module's claim would fail."""
    d = gulf_decomposition()
    assert (d.plausible == "yes").all()
    assert (d.implied_business_remit_usd_yr > 0).all()


def test_indian_us_entrepreneurs_out_earn_the_business_owner_average():
    b = DIASPORA_BUSINESS
    assert b["us_indian_entrepreneur_income_usd"] > b["us_all_business_owner_income_usd"]
    premium = b["us_indian_entrepreneur_income_usd"] / b["us_all_business_owner_income_usd"] - 1
    assert 0.5 < premium < 0.75


# ===========================================================================
# Occupation-controlled wages
# ===========================================================================
from occupation_wages import (  # noqa: E402
    EXCLUDED,
    FX_PER_USD,
    INDIA_VARIANTS,
    SALARIES,
    table,
    to_usd,
    with_tax,
)


def test_every_salary_currency_has_an_exchange_rate():
    for occ, by_country in SALARIES.items():
        for country, (_amt, cur, _note) in by_country.items():
            assert cur in FX_PER_USD, f"{occ}/{country} uses {cur}, which has no rate"


def test_india_is_present_wherever_a_multiple_is_reported():
    d = table(FX_PER_USD)
    for occ in d.occupation.unique():
        sub = d[d.occupation == occ]
        has_india = "India" in set(sub.country)
        if not has_india:
            assert sub.multiple_of_india.isna().all(), (
                f"{occ} reports a multiple with no Indian comparator")


def test_the_multiple_is_one_for_india_itself():
    d = table(FX_PER_USD).set_index(["occupation", "country"])
    for occ in ("software engineer", "registered nurse"):
        assert d.loc[(occ, "India"), "multiple_of_india"] == 1.0


def test_conversion_is_division_not_multiplication():
    """A rate of 95.43 INR per USD must make a rupee salary SMALLER in dollars."""
    assert to_usd(900000, "INR", FX_PER_USD) < 900000
    assert to_usd(56086, "GBP", FX_PER_USD) > 56086   # GBP is worth more than USD
    assert to_usd(1000, "USD", FX_PER_USD) == 1000


def test_the_ordering_differs_between_occupations():
    """The module's central claim: there is no single best country, only a best
    country for a job."""
    from occupation_wages import ordering

    d = table(FX_PER_USD)
    swe = [c for c in ordering(d, "software engineer")]
    nurse = [c for c in ordering(d, "registered nurse")]
    common = [c for c in swe if c in nurse]
    assert len(common) >= 3
    assert [c for c in swe if c in common] != [c for c in nurse if c in common]


def test_tax_reorders_the_nurse_row_but_not_the_engineer_row():
    """Pinned because an earlier draft asserted tax never reorders, which is
    true of national averages and false at the role level."""
    t = with_tax(table(FX_PER_USD))
    t = t[t.net_usd_market.notna()]
    for occ, expect_swap in (("registered nurse", True), ("software engineer", False)):
        sub = t[t.occupation == occ]
        gross = sub.sort_values("usd_market", ascending=False).country.tolist()
        net = sub.sort_values("net_usd_market", ascending=False).country.tolist()
        assert (gross != net) is expect_swap, occ


def test_india_has_no_net_figure_because_there_is_no_indian_tax_schedule():
    t = with_tax(table(FX_PER_USD))
    india = t[t.country == "India"]
    assert len(india) > 0
    assert india.net_usd_market.isna().all()


def test_india_variants_are_all_above_the_national_average():
    """Migrants come from the top of the Indian distribution, so every variant
    must exceed the national figure — that is what makes the headline multiple
    an upper bound."""
    national = to_usd(*SALARIES["software engineer"]["India"][:2], FX_PER_USD)
    for _label, (amt, cur) in INDIA_VARIANTS.items():
        assert to_usd(amt, cur, FX_PER_USD) > national


def test_unusable_figures_are_excluded_with_a_stated_reason():
    assert len(EXCLUDED) >= 4
    for key, why in EXCLUDED.items():
        assert isinstance(key, tuple) and len(key) == 2
        assert len(why) > 30, f"{key} needs a real reason, not a label"


def test_the_debt_module_now_uses_the_sourced_rupee_rate():
    from us_debt_service import DEFAULT_INR_PER_USD

    assert DEFAULT_INR_PER_USD == FX_PER_USD["INR"]
    assert DEFAULT_INR_PER_USD > 90, "the old hardcoded 87.0 was an unsourced guess"


def test_seniority_basis_is_recorded_for_every_salary():
    from occupation_wages import seniority_basis

    d = table(FX_PER_USD)
    assert d.seniority_basis.notna().all()
    assert seniority_basis("BLS OEWS May-2025 mean") == "all-levels"
    assert seniority_basis("chartered accountant, mid-level") == "mid-level"
    assert seniority_basis("entry-level band") == "entry"


def test_the_accountant_row_is_flagged_as_mixed_basis():
    """It reports a larger multiple than software engineering purely because
    its Indian denominator is mid-level while the US figure is an all-levels
    mean. Presenting that as a finding would be wrong."""
    d = table(FX_PER_USD)
    acc = d[d.occupation == "accountant"]
    assert acc.seniority_basis.nunique() > 1
    # ...while the two headline roles are internally consistent.
    for occ in ("software engineer", "registered nurse"):
        assert d[d.occupation == occ].seniority_basis.nunique() == 1


def test_a_mixed_basis_multiple_is_larger_than_the_clean_one_which_is_the_trap():
    d = table(FX_PER_USD).set_index(["occupation", "country"])
    assert (d.loc[("accountant", "United States"), "multiple_of_india"]
            > d.loc[("software engineer", "United States"), "multiple_of_india"])
