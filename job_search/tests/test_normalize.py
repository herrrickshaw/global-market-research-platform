import pytest
from jobsearch.normalize import (normalize_company, normalize_linkedin_url,
                                 normalize_person_name, normalize_title)


@pytest.mark.parametrize("raw,expected", [
    ("Shell plc", "shell"),
    ("Siemens Energy AG", "siemens energy"),
    ("Reliance Industries Limited", "reliance industries"),
    ("Boston Consulting Group (BCG)", "boston consulting"),
    ("Infosys Pvt Ltd", "infosys"),
    ("Bosch GmbH & Co KG", "bosch"),
    ("  EY  ", "ey"),
])
def test_normalize_company(raw, expected):
    assert normalize_company(raw) == expected


@pytest.mark.parametrize("raw", ["Self-employed", "Freelance", "", "   ", "Student"])
def test_no_employer_yields_empty_key(raw):
    """These must never become a join key or every freelancer merges into one company."""
    assert normalize_company(raw) == ""


def test_url_canonicalisation_is_locale_and_case_insensitive():
    variants = [
        "https://www.linkedin.com/in/Foo-Bar",
        "http://de.linkedin.com/in/foo-bar/",
        "linkedin.com/in/foo-bar?trk=abc",
        "https://LINKEDIN.com/in/FOO-BAR#top",
    ]
    assert len({normalize_linkedin_url(v) for v in variants}) == 1


def test_normalize_title_strips_gender_tags_and_req_ids():
    assert normalize_title("Senior Manager (m/w/d) - Req 12345") == "senior manager"


def test_normalize_person_name_folds_accents_and_suffixes():
    assert normalize_person_name("José Álvarez, PMP") == "jose alvarez"


def test_credentials_are_redacted_before_logging():
    """Adzuna authenticates via query string, so raw URLs must never be logged
    or embedded in an exception -- the key would leak into every error line."""
    from jobsearch.sources.base import redact
    url = ("https://api.adzuna.com/v1/api/jobs/in/search/1"
           "?app_id=abc123&app_key=deadbeefcafe&what=business+development")
    out = redact(url)
    assert "deadbeefcafe" not in out and "abc123" not in out
    assert "app_key=***" in out and "app_id=***" in out
    assert "what=business+development" in out, "non-secret params must survive"


def test_redact_is_safe_on_urls_without_secrets():
    from jobsearch.sources.base import redact
    plain = "https://boards-api.greenhouse.io/v1/boards/x/jobs?content=true"
    assert redact(plain) == plain
    assert redact("") == ""
