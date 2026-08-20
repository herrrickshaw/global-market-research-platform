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
