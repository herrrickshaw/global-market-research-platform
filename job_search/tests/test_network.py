from jobsearch.connections import load_connections
from jobsearch.network import (build_company_index, is_hiring_contact, is_senior_contact,
                               network_strength)
from jobsearch.models import CompanyNetwork, Connection

SAMPLE = "tests/fixtures/connections_sample.csv"


def _c(position, company="Acme"):
    return Connection("A", "B", "https://linkedin.com/in/x", "", company, position, None)


def test_shell_variants_collapse_into_one_company():
    idx = build_company_index(load_connections(SAMPLE))
    assert idx["shell"].size == 2       # "Shell plc" + "Shell"
    assert idx["shell"].display_name in {"Shell plc", "Shell"}


def test_employerless_connections_are_excluded():
    idx = build_company_index(load_connections(SAMPLE))
    assert "" not in idx
    assert not any("self" in k for k in idx)


def test_hiring_and_senior_detection():
    assert is_hiring_contact(_c("Talent Acquisition Partner"))
    assert is_hiring_contact(_c("Technical Recruiter"))
    assert not is_hiring_contact(_c("Process Engineer"))
    assert is_senior_contact(_c("Head of Business Development"))
    assert is_senior_contact(_c("VP Strategy"))
    assert not is_senior_contact(_c("Analyst"))


def test_vp_does_not_match_inside_other_words():
    assert not is_senior_contact(_c("Development Associate"))


def test_recruiter_outweighs_headcount():
    """One talent contact should beat a big cold headcount."""
    recruiter = CompanyNetwork("R", "r", [_c("Recruiter")] * 2,
                               [_c("Recruiter")] * 2, [])
    crowd = CompanyNetwork("C", "c", [_c("Analyst")] * 30, [], [])
    assert network_strength(recruiter) > network_strength(crowd)


def test_empty_network_scores_zero():
    assert network_strength(CompanyNetwork("X", "x", [], [], [])) == 0.0
