"""
Tests for the Adzuna salary client.

Two things matter here beyond the arithmetic. First, credentials must never be
in the source — they belong in the environment, and a test that scans the repo
for them is cheaper than noticing a leak after a push. Second, the client must
fail loudly and usefully when it cannot reach the API, because in the
environment it was written in it never can.

Run:
    python -m pytest tests/test_adzuna_client.py -v
"""

import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "research", "diaspora"))

from adzuna_salary_fetch import (  # noqa: E402
    COUNTRIES,
    CURRENCY,
    DRY_RUN_FIXTURE,
    OCCUPATIONS,
    build_url,
    redact,
    summarise,
)


# --------------------------------------------------------------- credentials
def test_the_live_credentials_are_not_committed():
    """Scan tracked files for whatever credentials are actually in use.

    Note what this test does NOT do: hardcode the values it is looking for.
    An earlier version did exactly that, and the effect was to commit the very
    secret it existed to catch — the test found itself and failed, which is the
    only reason it was noticed. If the credentials are not in the environment
    there is nothing to scan for, and the test says so rather than passing
    silently and implying a guarantee it did not check.
    """
    secrets = [v for v in (os.environ.get("ADZUNA_APP_ID"),
                           os.environ.get("ADZUNA_APP_KEY")) if v]
    if not secrets:
        pytest.skip("ADZUNA_APP_ID/KEY not in the environment — nothing to scan for")
    args = ["git", "grep", "-lI"]
    for v in secrets:
        args += ["-e", v]
    out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    assert out.stdout.strip() == "", f"credential value found in: {out.stdout}"


def test_no_file_hardcodes_an_adzuna_credential_assignment():
    """Catches the shape of the mistake even when the values are unknown:
    any file assigning a literal to one of the credential names."""
    out = subprocess.run(
        ["git", "grep", "-lIE",
         r"ADZUNA_APP_(ID|KEY)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9]{6,}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert out.stdout.strip() == "", f"hardcoded credential assignment in: {out.stdout}"


def test_the_module_reads_credentials_from_the_environment_only():
    src = open(os.path.join(ROOT, "research", "diaspora", "adzuna_salary_fetch.py"),
               encoding="utf-8").read()
    assert 'os.environ.get("ADZUNA_APP_ID")' in src
    assert 'os.environ.get("ADZUNA_APP_KEY")' in src


def test_redact_strips_the_key_from_a_url(monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "SECRET_ID")
    monkeypatch.setenv("ADZUNA_APP_KEY", "SECRET_KEY")
    url = build_url("in", "software engineer", "SECRET_ID", "SECRET_KEY")
    assert "SECRET_KEY" in url
    cleaned = redact(url)
    assert "SECRET_KEY" not in cleaned
    assert "SECRET_ID" not in cleaned
    assert "<ADZUNA_APP_KEY>" in cleaned


# --------------------------------------------------------------------- shape
def test_india_is_covered_because_it_is_the_counterfactual():
    """India on the same methodology as the destinations is the whole point."""
    assert "in" in COUNTRIES
    assert COUNTRIES["in"] == "India"
    assert CURRENCY["in"] == "INR"


def test_every_country_has_a_currency():
    assert set(COUNTRIES) == set(CURRENCY)


def test_url_carries_both_credentials_and_the_search_term():
    url = build_url("gb", "data scientist", "ID", "KEY")
    assert "/jobs/gb/search/1?" in url
    assert "app_id=ID" in url and "app_key=KEY" in url
    assert "data+scientist" in url


# ---------------------------------------------------------------- summarise
def test_summarise_computes_midpoints_not_minima():
    s = summarise(DRY_RUN_FIXTURE, "in", "software engineer")
    # midpoints of the fixture: 1.15m, 1.5m, 0.9m, 1.95m
    assert s["salary_mean"] == 1375000
    assert s["salary_median"] == 1500000
    assert s["salary_p25"] == 1150000
    assert s["salary_p75"] == 1950000


def test_summarise_reports_coverage_because_it_is_never_complete():
    s = summarise(DRY_RUN_FIXTURE, "in", "software engineer")
    assert s["salary_coverage_pct"] == 100.0
    partial = {"count": 10, "results": [{"salary_min": 100, "salary_max": 200},
                                        {"salary_min": None, "salary_max": None}]}
    p = summarise(partial, "us", "x")
    assert p["salary_coverage_pct"] == 50.0
    assert p["adverts_with_salary"] == 1


def test_summarise_survives_adverts_with_no_salary_at_all():
    empty = {"count": 3, "results": [{"title": "x"}, {"title": "y"}]}
    s = summarise(empty, "de", "software engineer")
    assert s["salary_median"] is None
    assert s["adverts_with_salary"] == 0
    assert s["salary_coverage_pct"] == 0.0


def test_summarise_handles_a_completely_empty_payload():
    s = summarise({}, "fr", "x")
    assert s["adverts_returned"] == 0
    assert s["salary_coverage_pct"] is None


# ------------------------------------------------------------------- the CLI
def test_dry_run_makes_no_network_call_and_exits_clean():
    r = subprocess.run(
        [sys.executable, "research/diaspora/adzuna_salary_fetch.py",
         "--dry-run", "--countries", "in,us", "--out", "/tmp/adz-test"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "DRY RUN" in r.stdout
    assert "no network call" in r.stdout


def test_an_uncovered_country_is_rejected_with_the_valid_list():
    r = subprocess.run(
        [sys.executable, "research/diaspora/adzuna_salary_fetch.py",
         "--dry-run", "--countries", "in,xx"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert r.returncode != 0
    assert "does not cover: xx" in (r.stdout + r.stderr)


def test_occupations_target_where_indian_migrants_concentrate():
    assert "software engineer" in OCCUPATIONS
    assert "registered nurse" in OCCUPATIONS
    assert len(OCCUPATIONS) >= 4


@pytest.mark.parametrize("var", ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"])
def test_missing_credentials_exit_with_guidance_not_a_traceback(var, monkeypatch):
    env = dict(os.environ)
    env["ADZUNA_APP_ID"] = "x"
    env["ADZUNA_APP_KEY"] = "y"
    env.pop(var)
    r = subprocess.run(
        [sys.executable, "research/diaspora/adzuna_salary_fetch.py", "--countries", "in"],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=60,
    )
    assert r.returncode != 0
    assert "ADZUNA_APP_ID" in (r.stdout + r.stderr)
    assert "Traceback" not in r.stderr
