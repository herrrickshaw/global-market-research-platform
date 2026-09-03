from datetime import date, timedelta

from jobsearch.models import CompanyNetwork, Connection, JobPosting
from jobsearch.profile import TargetProfile
from jobsearch.scoring import freshness, role_fit, score_job

P = TargetProfile()
TODAY = date(2026, 8, 20)


def _job(title, company="Acme", location="Berlin, Germany", desc="", posted=None):
    return JobPosting("test", company, title, location, "http://x", posted, desc)


def test_core_title_scores_above_adjacent_title():
    strong, _ = role_fit(_job("Head of Business Development"), P)
    weak, _ = role_fit(_job("Project Manager"), P)
    assert strong > weak > 0


def test_hard_negative_zeroes_the_score():
    score, reasons = role_fit(_job("Business Development Intern"), P)
    assert score == 0.0 and "excluded" in reasons[0]


def test_unrelated_role_scores_zero():
    assert role_fit(_job("Warehouse Operative"), P)[0] == 0.0


def test_location_mismatch_penalised_not_excluded():
    here, _ = role_fit(_job("Business Development Manager", location="Berlin, Germany"), P)
    there, _ = role_fit(_job("Business Development Manager", location="Ohio, USA"), P)
    assert 0 < there < here


def test_description_match_discounted_versus_title_match():
    in_title, _ = role_fit(_job("Investment Promotion Lead"), P)
    in_desc, r = role_fit(_job("Programme Officer", desc="lead investment promotion work"), P)
    assert 0 < in_desc < in_title
    assert any("description" in x for x in r)


def test_freshness_decays_and_undated_is_neutral():
    assert freshness(_job("x", posted=TODAY), TODAY) == 1.0
    assert freshness(_job("x", posted=TODAY - timedelta(days=30)), TODAY) == 0.5
    assert freshness(_job("x", posted=None), TODAY) == 0.5
    old = freshness(_job("x", posted=TODAY - timedelta(days=120)), TODAY)
    assert old < 0.1


def test_network_lifts_an_equal_role():
    conn = Connection("A", "B", "u", "", "Acme", "Recruiter", None)
    net = CompanyNetwork("Acme", "acme", [conn], [conn], [])
    job = _job("Business Development Manager", posted=TODAY)
    warm = score_job(job, net, P, TODAY)
    cold = score_job(job, None, P, TODAY)
    assert warm.total > cold.total
    assert warm.has_warm_path and not cold.has_warm_path


def test_zero_role_fit_cannot_be_rescued_by_network():
    conn = Connection("A", "B", "u", "", "Acme", "Recruiter", None)
    net = CompanyNetwork("Acme", "acme", [conn] * 50, [conn] * 5, [conn] * 20)
    m = score_job(_job("Warehouse Operative"), net, P, TODAY)
    assert m.total == 0.0


def test_platform_implementation_roles_are_excluded():
    """Consulting-sounding titles that are really platform work must not rank.

    'Senior Manager - SAP Treasury, Advisory' previously scored 0.689 purely on
    the generic 'advisory' keyword, despite requiring SAP depth the CV lacks.
    """
    for title in ["Senior Manager - SAP Treasury, Advisory",
                  "Oracle Fusion SCM Manager",
                  "ServiceNow ITOM Manager - Tech Consulting",
                  "Manager, Salesforce Implementation"]:
        assert role_fit(_job(title), P)[0] == 0.0, title


def test_capability_centre_titles_are_matched():
    """GCC / shared-services build-out is directly evidenced on the CV but the
    titles never say 'business development', so they need their own keywords."""
    for title in ["Manager - GBS, GCC & Outsourcing Advisory",
                  "Global Capability Centre Lead",
                  "Director, Shared Services Transformation"]:
        assert role_fit(_job(title), P)[0] > 0.4, title


def test_commodity_market_analyst_titles_are_matched():
    """Regression: "Senior Market Analyst, Gas and LNG" scored zero because no
    title keyword covered commodity/market research. That work is directly on
    the CV (Shell Category Analyst market intelligence; Invest India oil & gas
    benchmarking), so it must rank, not vanish."""
    score, reasons = role_fit(
        _job("Senior Market Analyst, Gas and LNG", company="Rystad Energy",
             location="Houston, Texas, United States"), P)
    assert score > 0.3, reasons
    assert "no role keyword match" not in reasons

    oil, _ = role_fit(_job("Senior Regional Oil Market Analyst",
                           location="Houston, Texas, United States"), P)
    assert oil > 0.3


def test_account_management_still_excluded_from_market_analyst_change():
    """Widening analyst coverage must not drag in pure sales titles."""
    score, _ = role_fit(_job("Senior Account Manager - Financials",
                             location="London, United Kingdom"), P)
    assert score == 0.0


def test_cost_estimation_titles_are_matched():
    """Regression: only the exact string "cost engineer" matched, so
    "Tech Specialist - Cost Estimation" scored zero — despite cost engineering
    being an explicit CV bullet on a ~USD 7bn LNG train."""
    score, reasons = role_fit(
        _job("Tech Specialist - Cost Estimation", location="Chennai, Tamil Nadu, India"), P)
    assert score > 0.3, reasons


def test_finance_planning_ranks_below_core_business_development():
    """FP&A is adjacent to the CV, not central, so it must score but must not
    outrank a genuine business-development role."""
    fpa, _ = role_fit(_job("Head of FP&A", location="Chennai, Tamil Nadu, India"), P)
    bd, _ = role_fit(_job("Head of Business Development",
                          location="Chennai, Tamil Nadu, India"), P)
    assert 0 < fpa < bd


def test_financial_crime_roles_are_excluded():
    """Regression: "FinCrime Due Diligence & Advisory Sr Mgr" ranked 4th at
    0.892 on the words "due diligence" and "advisory". The CV's due diligence
    is transaction due diligence (M&A, JV/BOOT), not KYC/AML screening."""
    score, reasons = role_fit(
        _job("FinCrime Due Diligence & Advisory Sr Mgr", location="Poland"), P)
    assert score == 0.0, reasons

    # ...but genuine transaction due diligence must still rank.
    deal, _ = role_fit(_job("Manager, Transaction Advisory & Due Diligence",
                            location="London, United Kingdom"), P)
    assert deal > 0.3


# --------------------------------------------------------------------------
# Titles that hide the function -- the sixth instance of this failure
# --------------------------------------------------------------------------

def test_bracketed_inserts_do_not_defeat_a_keyword():
    """"Research (Senior) Analyst" does not CONTAIN "research analyst".

    The insert sits inside the phrase and breaks it, so the role scored zero on
    "no keyword match" while the identical "Senior Research Analyst" matched.
    German and Dutch postings make this routine: "(f/m/d)" and "(m/w/d)" are
    near-universal there, and they land mid-title.
    """
    fit, why = role_fit(_job("Research (Senior) Analyst - The Netherlands",
                             location="Amsterdam, Netherlands"), P)
    assert fit > 0.3, why


def test_seniority_inside_an_insert_is_still_read():
    """Stripping inserts to match must not also discard the seniority signal."""
    senior, _ = role_fit(_job("Research (Senior) Analyst", location="London"), P)
    plain, _ = role_fit(_job("Research Analyst", location="London"), P)
    assert senior > plain


def test_a_gendered_german_insert_is_ignored():
    fit, _ = role_fit(_job("Head of LNG Trading (f/m/d)",
                           location="Duesseldorf, Germany"), P)
    assert fit > 0.3


def test_titles_that_state_the_function_in_other_words_still_match():
    """Each of these scored zero until the CV line behind it was encoded.

    Refined-product analytics is the Shell Category Analyst work; project
    development is on the CV's own subtitle and is what Invest India did in
    substance; "Leiter" is simply "Head of" in the language of the corridor
    the ESMT MBA and B1 German open up.
    """
    for title, location in [
        ("Head of Refined Products Analytics", "London, United Kingdom"),
        ("Project Development Manager France", "Paris, France"),
        ("Leiter Energy Hub Nordwest", "Wilhelmshaven, Germany"),
        ("Senior Waterborne LNG Analyst", "London, United Kingdom"),
    ]:
        fit, why = role_fit(_job(title, location=location), P)
        assert fit > 0.3, f"{title}: {why}"


def test_the_new_keywords_do_not_drag_in_unrelated_work():
    """Negative controls. Widening the map must not turn it into a sieve."""
    for title in ["Manager Audit and Technology",
                  "Head of Solar Development Engineering",
                  "Senior Account Manager",
                  "Warehouse Supervisor"]:
        fit, _ = role_fit(_job(title, location="London, United Kingdom"), P)
        assert fit == 0.0, title


def test_lng_trading_surfaces_without_outranking_the_core():
    """LNG is the deepest sector line on the CV, but a TRADING desk is a
    different discipline it does not evidence -- so the role should appear,
    not lead."""
    trading, _ = role_fit(_job("Head of LNG Trading (f/m/d)",
                               location="Duesseldorf, Germany"), P)
    core, _ = role_fit(_job("Senior Business Development Manager, LNG",
                            location="Duesseldorf, Germany"), P)
    assert 0.3 < trading < core


# --------------------------------------------------------------------------
# The FDI vocabulary the rest of the world uses
# --------------------------------------------------------------------------

def test_investment_promotion_is_reachable_by_its_other_names():
    """"Investment promotion" is largely an Indian phrasing.

    The same function is advertised as "inward investment" in Britain and
    Ireland, "trade and investment" by agencies, and "site selection" in the
    private sector. Keying only on the Indian phrase makes the CV's headline
    identity unreachable in exactly the second market it targets.
    """
    for title, location in [
        ("Inward Investment Manager", "London, United Kingdom"),
        ("Head of Trade and Investment", "Dublin, Ireland"),
        ("Economic Development Director", "Amsterdam, Netherlands"),
        ("Trade Commissioner - South Asia", "New Delhi, India"),
    ]:
        fit, why = role_fit(_job(title, location=location), P)
        assert fit > 0.5, f"{title}: {why}"


def test_origination_is_the_title_word_for_deal_origination():
    """Energy and infrastructure finance advertise the CV's "Deal Origination
    & Investor Outreach" competency as, simply, origination."""
    fit, _ = role_fit(_job("Origination Manager - Renewables",
                           location="Madrid, Spain"), P)
    assert fit > 0.5


def test_go_to_market_matches_the_hyphenated_spelling():
    """strip_inserts() keeps hyphens, so a spaced key can never match a
    hyphenated title -- the same asymmetry already fixed in the ATS scorer.
    Both spellings are carried deliberately."""
    hyphenated, _ = role_fit(_job("Go-To-Market Strategy Manager"), P)
    spaced, _ = role_fit(_job("Go To Market Strategy Manager"), P)
    assert hyphenated > 0.5 and spaced > 0.5


def test_a_sector_vertical_carries_a_role_with_no_function_word():
    """The verticals built at Invest India (green hydrogen, CBG, SAF, CCUS)
    appear in titles as the sector. A role can fit perfectly and carry none of
    the function words."""
    fit, _ = role_fit(_job("Green Hydrogen Project Lead",
                           location="Rotterdam, Netherlands"), P)
    assert fit > 0.4


def test_the_fdi_keywords_do_not_drag_in_unrelated_work():
    """Negative controls for this widening, same rule as the last one."""
    for title in ["Site Reliability Engineer",
                  "Economic Research Intern",
                  "Hydrogen Plant Maintenance Technician",
                  "Trade Compliance Customs Clerk",
                  "Origination Analyst - Salesforce CPQ"]:
        fit, _ = role_fit(_job(title, location="London, United Kingdom"), P)
        assert fit == 0.0, title


# --------------------------------------------------------------------------
# Zeroes found by pulling four new employers and reading what scored 0.000
# --------------------------------------------------------------------------

def test_titles_that_scored_zero_against_real_postings_now_match():
    """Each of these is a real posting that scored 0.000 "no role keyword
    match" the first time it reached the scorer, and each is plainly a fit.

    The Crisil mobility role is the Invest India job description almost
    verbatim - development-finance and government-business advisory - and it
    scored zero because the map held "consultant" but not "consulting".
    """
    for title in ["Manager - Mobility Consulting (DFI & Government Business)",
                  "Manager (Power / Clean Energy Domain)",
                  "Regional Manager - Large Corporates (BD)",
                  "Director - Private Markets"]:
        fit, why = role_fit(_job(title, location="Mumbai, India"), P)
        assert fit > 0.5, f"{title}: {why}"


def test_bd_does_not_match_becton_dickinson():
    """Two letters is a greedy key. "BD" is business development in an Indian
    posting and Becton Dickinson in a medical-device one; the second scored
    0.85 before its brands became hard negatives."""
    fit, _ = role_fit(_job("Territory Sales Rep - BD Biosciences",
                           location="Mumbai, India"), P)
    assert fit == 0.0


def test_consulting_does_not_drag_in_software_consulting():
    """The same wrong-function trap the SAP and Salesforce negatives already
    cover - "consulting" is a broad word and software wears it too."""
    for title in ["Consulting Software Architect", "Lead Solution Architect"]:
        fit, _ = role_fit(_job(title, location="London, United Kingdom"), P)
        assert fit == 0.0, title


def test_clean_energy_is_keyed_but_bare_power_is_not():
    """"Power" alone would pull in power-systems engineering, which the CV
    does not evidence and which dominates utility job boards."""
    good, _ = role_fit(_job("Manager, Clean Energy Advisory",
                            location="Gurugram, India"), P)
    bad, _ = role_fit(_job("Power Systems Design Engineer",
                           location="Gurugram, India"), P)
    assert good > 0.5 and bad == 0.0


# --------------------------------------------------------------------------
# "Specialist" means opposite things in different houses
# --------------------------------------------------------------------------

def test_development_finance_grade_titles_escape_the_junior_penalty():
    """"Specialist", "Officer" and "Consultant" are junior rungs in a corporate
    title and career-grade professional titles at the World Bank, IFC, GIZ and
    IEEFA - the development-finance employers the FDI keywords exist to reach.

    IEEFA's "Power Sector Specialist, South Asia" is a 10+ year India energy-
    policy role; the blanket junior penalty halved it to 0.33 and buried it at
    51st place.
    """
    for title in ["Power Sector Specialist, South Asia",
                  "Senior Investment Officer, Loan Syndication",
                  "Industry Specialist - Financial Services"]:
        fit, why = role_fit(_job(title, location="New Delhi, India"), P)
        assert fit > 0.6, f"{title}: {why}"
        assert not any("below target seniority" in r for r in why), title


def test_a_bare_junior_title_still_takes_the_penalty():
    """The exemption is for strong DOMAIN matches only. A generic "Consultant"
    has no domain qualifier and stays demoted."""
    fit, why = role_fit(_job("Consultant", location="London, United Kingdom"), P)
    assert any("below target seniority" in r for r in why)
    assert fit < 0.4


def test_sales_development_reps_are_excluded_not_merely_demoted():
    """This file used to claim BDR roles were "correctly excluded". They were
    not: "Business Development Representative" scored 0.95 on the
    "business development" key, and the junior penalty cannot catch them now
    that strong domain matches are exempt from it."""
    for title in ["Business Development Representative",
                  "Sales Development Representative",
                  "Account Executive - Maritime"]:
        fit, _ = role_fit(_job(title, location="London, United Kingdom"), P)
        assert fit == 0.0, title


def test_the_real_business_development_titles_are_untouched():
    """Negative control for the exclusion above: it must not swallow the
    genuine BD roles that are the core of this search."""
    for title in ["Head of Business Development",
                  "Senior Business Development Manager",
                  "Renewables Business Development Manager"]:
        fit, _ = role_fit(_job(title, location="London, United Kingdom"), P)
        assert fit > 0.8, title
