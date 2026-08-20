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


# ---------------------------------------------------------------- recency
from datetime import date, timedelta  # noqa: E402

from jobsearch.network import (  # noqa: E402
    RECENCY_FLOOR,
    network_strength,
    recency_factor,
)
from jobsearch.models import CompanyNetwork, Connection  # noqa: E402


def _net(*years_ago, hiring=0, senior=0, size=None):
    today = date(2026, 8, 20)
    conns = [
        Connection(first_name="A", last_name=str(i), url="", email="",
                   company="X", position="Engineer",
                   connected_on=today - timedelta(days=int(y * 365.25)))
        for i, y in enumerate(years_ago)
    ]
    return CompanyNetwork(
        display_name="X", normalized="x", connections=conns,
        hiring_contacts=conns[:hiring], senior_contacts=conns[:senior],
    )


def test_a_fresh_connection_is_not_decayed():
    assert recency_factor(_net(0.0), today=date(2026, 8, 20)) == 1.0


def test_an_old_connection_decays_to_the_floor():
    assert recency_factor(_net(12.0), today=date(2026, 8, 20)) == RECENCY_FLOOR


def test_decay_is_monotone_in_age():
    today = date(2026, 8, 20)
    factors = [recency_factor(_net(y), today=today) for y in (0, 2, 5, 8, 10)]
    assert factors == sorted(factors, reverse=True)


def test_the_most_recent_connection_sets_the_factor_not_the_oldest():
    """One recent contact keeps the path warm even beside ancient ones."""
    today = date(2026, 8, 20)
    assert recency_factor(_net(9.0, 0.5), today=today) > recency_factor(_net(9.0), today=today)


def test_missing_dates_are_not_penalised():
    """A missing date is missing information, not evidence of staleness."""
    conns = [Connection(first_name="A", last_name="B", url="", email="",
                        company="X", position="Engineer", connected_on=None)]
    net = CompanyNetwork(display_name="X", normalized="x", connections=conns)
    assert recency_factor(net, today=date(2026, 8, 20)) == 1.0


def test_recency_discounts_strength_but_cannot_create_it():
    """A stale company scores below an identical fresh one, and an empty
    network stays at zero however recent it is."""
    today = date(2026, 8, 20)
    fresh = network_strength(_net(0.2, 0.3, hiring=1), today=today)
    stale = network_strength(_net(9.0, 9.5, hiring=1), today=today)
    assert 0 < stale < fresh
    empty = CompanyNetwork(display_name="X", normalized="x", connections=[])
    assert network_strength(empty, today=today) == 0.0
