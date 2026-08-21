"""Portal aggregators: JSearch, SerpApi Google Jobs, and the RapidAPI feeds.

None of these can be exercised against the live hosts here -- this environment's
egress policy answers 403 to CONNECT for every one of them -- so the tests
drive the parsing and failure paths against recorded payload shapes instead.
That is the part that actually broke before: a blocked source that returned []
was indistinguishable from an employer with nothing open.
"""
from __future__ import annotations

from datetime import date

import pytest

from jobsearch.sources import jsearch, rapidapi_jobs, serpapi
from jobsearch.sources.base import SourceError, redact


# --------------------------------------------------------------------------
# JSearch
# --------------------------------------------------------------------------

JSEARCH_ROW = {
    "job_id": "abc123",
    "employer_name": "Shell",
    "job_title": "Senior Strategy Consultant",
    "job_city": "London", "job_state": "England", "job_country": "GB",
    "job_apply_link": "https://example.test/apply/abc123",
    "job_posted_at_datetime_utc": "2026-08-04T09:00:00.000Z",
    "job_description": "Strategy work.",
    "job_publisher": "LinkedIn",
    "job_is_remote": False,
}


def test_jsearch_records_the_originating_portal():
    """Which board a posting came from is the whole point of the aggregator."""
    posting = jsearch._to_posting(JSEARCH_ROW)
    assert posting.source == "jsearch:LinkedIn"
    assert posting.company == "Shell"
    assert posting.location == "London, England, GB"
    assert posting.posted_at == date(2026, 8, 4)


def test_jsearch_survives_a_missing_publisher():
    posting = jsearch._to_posting({**JSEARCH_ROW, "job_publisher": ""})
    assert posting.source == "jsearch"


def test_jsearch_window_never_undershoots_the_requested_days():
    # Mapping 30 days onto "week" would silently drop three weeks of postings.
    assert jsearch._window(30) == "month"
    assert jsearch._window(7) == "week"
    assert jsearch._window(2) == "3days"
    assert jsearch._window(None) == "all"


def test_jsearch_rejects_an_unsupported_window():
    src = jsearch.JSearchSource(api_key="k")
    with pytest.raises(SourceError, match="date_posted"):
        src.fetch("analyst", date_posted="fortnight")


def test_jsearch_without_a_key_raises_rather_than_returning_nothing():
    with pytest.raises(SourceError, match="RAPIDAPI_KEY"):
        jsearch.JSearchSource(api_key="").fetch("analyst")


def test_jsearch_page_one_failure_propagates(monkeypatch):
    def boom(*_a, **_k):
        raise SourceError("403 blocked")

    monkeypatch.setattr(jsearch, "http_get_json", boom)
    with pytest.raises(SourceError):
        jsearch.JSearchSource(api_key="k").fetch("analyst")


def test_jsearch_later_page_failure_keeps_what_was_already_found(monkeypatch):
    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"data": [JSEARCH_ROW]}
        raise SourceError("timeout")

    monkeypatch.setattr(jsearch, "http_get_json", flaky)
    jobs = jsearch.JSearchSource(api_key="k").fetch("analyst", max_pages=3)
    assert len(jobs) == 1


# --------------------------------------------------------------------------
# SerpApi Google Jobs
# --------------------------------------------------------------------------

def test_google_jobs_parses_relative_dates():
    today = date(2026, 8, 21)
    assert serpapi.parse_relative_date("3 days ago", today) == date(2026, 8, 18)
    assert serpapi.parse_relative_date("2 weeks ago", today) == date(2026, 8, 7)
    assert serpapi.parse_relative_date("1 month ago", today) == date(2026, 7, 22)
    assert serpapi.parse_relative_date("5 hours ago", today) == today


def test_google_jobs_returns_none_for_an_unparseable_date():
    # Guessing here would feed an invented date into the freshness score.
    assert serpapi.parse_relative_date("recently", date(2026, 8, 21)) is None
    assert serpapi.parse_relative_date("", date(2026, 8, 21)) is None


def test_google_jobs_records_the_via_portal():
    posting = serpapi._to_posting({
        "title": "Energy Analyst",
        "company_name": "Shell",
        "location": "London, UK",
        "via": "via LinkedIn",
        "share_link": "https://example.test/j/1",
        "detected_extensions": {"posted_at": "4 days ago"},
    }, today=date(2026, 8, 21))
    assert posting.source == "google_jobs:LinkedIn"
    assert posting.posted_at == date(2026, 8, 17)


def test_google_jobs_falls_back_to_the_first_apply_link():
    posting = serpapi._to_posting({
        "title": "Analyst", "company_name": "X",
        "apply_options": [{"link": "https://example.test/apply"}],
    })
    assert posting.url == "https://example.test/apply"


def test_google_jobs_treats_an_error_body_as_a_failure(monkeypatch):
    """SerpApi reports a bad key as HTTP 200 with an error field.

    Without this check an exhausted quota reads as 'no jobs found'.
    """
    monkeypatch.setattr(serpapi, "http_get_json",
                        lambda *_a, **_k: {"error": "Invalid API key"})
    with pytest.raises(SourceError, match="Invalid API key"):
        serpapi.SerpApiJobsSource(api_key="k").fetch("analyst")


def test_google_jobs_chip_covers_the_requested_window():
    assert serpapi._chip(30) == "date_posted:month"
    assert serpapi._chip(7) == "date_posted:week"
    assert serpapi._chip(None) == ""


def test_serpapi_key_is_redacted_from_a_url():
    url = "https://serpapi.com/search?engine=google_jobs&api_key=SECRET&q=analyst"
    masked = redact(url)
    assert "SECRET" not in masked
    assert "engine=google_jobs" in masked  # non-secret params stay diagnosable


# --------------------------------------------------------------------------
# RapidAPI feeds (LinkedIn x2, Active-ATS, Indeed)
# --------------------------------------------------------------------------

def test_rapidapi_maps_alternate_field_names():
    """These feeds have shipped several namings for the same value."""
    a = rapidapi_jobs.to_posting({
        "organization": "Shell", "title": "Analyst",
        "date_posted": "2026-08-04T00:00:00Z",
        "locations_derived": ["London, England, GB"],
        "url": "https://example.test/1", "id": "1",
    }, "linkedin")
    b = rapidapi_jobs.to_posting({
        "company_name": "Shell", "job_title": "Analyst",
        "datePosted": "2026-08-04", "location": "London, England, GB",
        "job_url": "https://example.test/1", "job_id": "1",
    }, "linkedin")
    assert (a.company, a.title, a.posted_at) == (b.company, b.title, b.posted_at)
    assert a.location == b.location


def test_rapidapi_flattens_structured_locations():
    posting = rapidapi_jobs.to_posting({
        "title": "Analyst",
        "locations_derived": [{"city": "Chennai", "country": "India"}],
    }, "active_ats")
    assert posting.location == "Chennai, India"


def test_rapidapi_unwraps_every_envelope_shape():
    row = {"title": "A"}
    assert rapidapi_jobs._rows([row]) == [row]
    assert rapidapi_jobs._rows({"data": [row]}) == [row]
    assert rapidapi_jobs._rows({"jobs": [row]}) == [row]
    assert rapidapi_jobs._rows({"nope": 1}) == []


def test_rapidapi_reports_unmapped_fields():
    """Schema drift should surface as a log line, not a blank column."""
    assert rapidapi_jobs._unmapped({"title": "A", "brand_new_field": 1}) == {"brand_new_field"}


def test_rapidapi_rejects_an_unsupported_time_frame():
    src = rapidapi_jobs.ActiveJobsDBSource(api_key="k")
    with pytest.raises(SourceError, match="time_frame"):
        src.fetch(time_frame="6d")


def test_rapidapi_page_one_failure_propagates(monkeypatch):
    monkeypatch.setattr(rapidapi_jobs, "http_get_json",
                        lambda *_a, **_k: (_ for _ in ()).throw(SourceError("403")))
    with pytest.raises(SourceError):
        rapidapi_jobs.ActiveJobsDBSource(api_key="k").fetch(title="analyst")


def test_linkedin_alt_host_selects_the_window_by_path(monkeypatch):
    seen = {}

    def capture(url, params=None, headers=None):
        seen["url"] = url
        return []

    monkeypatch.setattr(rapidapi_jobs, "http_get_json", capture)
    rapidapi_jobs.LinkedInJobsApi2Source(api_key="k").fetch(time_frame="24h")
    assert seen["url"].endswith("/active-jb-24h")
    assert "linkedin-jobs-api2" in seen["url"]


def test_linkedin_count_reads_any_of_the_count_keys(monkeypatch):
    monkeypatch.setattr(rapidapi_jobs, "http_get_json",
                        lambda *_a, **_k: {"total": 42})
    assert rapidapi_jobs.LinkedInJobSearchSource(api_key="k").count(title="x") == 42


def test_linkedin_count_refuses_to_guess_at_an_unknown_shape(monkeypatch):
    monkeypatch.setattr(rapidapi_jobs, "http_get_json",
                        lambda *_a, **_k: {"unexpected": "shape"})
    with pytest.raises(SourceError, match="unrecognised"):
        rapidapi_jobs.LinkedInJobSearchSource(api_key="k").count(title="x")


def test_indeed_requires_a_company():
    with pytest.raises(SourceError, match="company-scoped"):
        rapidapi_jobs.Indeed12Source(api_key="k").fetch()


def test_indeed_backfills_the_employer_on_each_row(monkeypatch):
    """The company-scoped endpoint omits the employer from its rows.

    Left blank, every match would join to an empty company and score zero
    network strength -- the exact signal this tool exists to compute.
    """
    monkeypatch.setattr(rapidapi_jobs, "http_get_json",
                        lambda *_a, **_k: [{"title": "Analyst", "id": "1"}])
    jobs = rapidapi_jobs.Indeed12Source(api_key="k").fetch(
        company="Wood Mackenzie", max_pages=1)
    assert jobs[0].company == "Wood Mackenzie"


def test_rapidapi_key_travels_in_headers_not_the_url(monkeypatch):
    """Header auth is why this family cannot leak a key into a log line."""
    seen = {}

    def capture(url, params=None, headers=None):
        seen["url"], seen["headers"], seen["params"] = url, headers, params
        return []

    monkeypatch.setattr(rapidapi_jobs, "http_get_json", capture)
    rapidapi_jobs.ActiveJobsDBSource(api_key="s3cret").fetch(title="analyst")
    assert seen["headers"]["x-rapidapi-key"] == "s3cret"
    assert "s3cret" not in seen["url"]
    assert "s3cret" not in str(seen["params"])


def test_jsearch_backends_differ_only_in_endpoint_and_auth_header():
    """One index, two front doors -- a wrong header here reads as 'no jobs'."""
    rapid = jsearch.JSearchSource(api_key="k", backend="rapidapi")
    direct = jsearch.JSearchSource(api_key="k", backend="openwebninja")
    assert rapid.endpoint.startswith("https://jsearch.p.rapidapi.com")
    assert direct.endpoint == jsearch.OWN_ENDPOINT
    assert "X-RapidAPI-Key" in rapid._headers
    assert direct._headers == {"X-API-Key": "k"}


def test_jsearch_rejects_an_unknown_backend():
    with pytest.raises(ValueError, match="backend"):
        jsearch.JSearchSource(api_key="k", backend="nope")


def test_jsearch_accepts_a_bare_list_payload(monkeypatch):
    monkeypatch.setattr(jsearch, "http_get_json", lambda *_a, **_k: [JSEARCH_ROW])
    jobs = jsearch.JSearchSource(api_key="k").fetch("analyst", max_pages=1)
    assert len(jobs) == 1


def test_linkedin_window_is_the_one_actually_fetched(monkeypatch):
    """A path pinned to /active-jb-7d silently answers a 30-day question
    with seven days of postings, and nothing in the output admits it."""
    seen = {}

    def capture(url, params=None, headers=None):
        seen["url"] = url
        return []

    monkeypatch.setattr(rapidapi_jobs, "http_get_json", capture)
    rapidapi_jobs.LinkedInJobSearchSource(api_key="k").fetch(
        title="analyst", time_frame="30d")
    assert seen["url"].endswith("/active-jb-30d")


# --------------------------------------------------------------------------
# JSearch country routing
# --------------------------------------------------------------------------

def test_jsearch_country_is_derived_from_the_location():
    """`country` picks the Google domain, it does not filter the results.

    Every European query in a seven-country run was going to google.co.in,
    which answers with India-weighted listings and no error at all -- so the
    Europe half of an "India and Europe" search was never actually searched.
    """
    from jobsearch.sources.jsearch import country_code

    assert country_code("Germany") == "de"
    assert country_code("United Kingdom") == "gb"
    assert country_code("Netherlands") == "nl"
    assert country_code("India") == "in"


def test_a_city_resolves_to_its_country():
    from jobsearch.sources.jsearch import country_code

    assert country_code("Rotterdam") == "nl"
    assert country_code("Bengaluru") == "in"


def test_a_country_wins_over_a_city_in_the_same_string():
    """"Rotterdam, Netherlands" must not resolve on whichever token is
    checked first."""
    from jobsearch.sources.jsearch import country_code

    assert country_code("Rotterdam, Netherlands") == "nl"
    assert country_code("Milan, Italy") == "it"


def test_an_unknown_location_falls_back_rather_than_guessing():
    from jobsearch.sources.jsearch import DEFAULT_COUNTRY, country_code

    assert country_code("Atlantis") == DEFAULT_COUNTRY
    assert country_code("") == DEFAULT_COUNTRY
    assert country_code("Atlantis", default="gb") == "gb"


def test_the_pipeline_passes_the_derived_country_through(monkeypatch):
    """The bug was in the caller, not the source: `fetch` had a sensible
    `country=` parameter that nothing ever passed."""
    from jobsearch import pipeline as P

    seen = []

    class FakeJSearch:
        def __init__(self, *a, **k):
            pass

        def fetch(self, query, **kw):
            seen.append((query, kw.get("country")))
            return []

    monkeypatch.setattr(P, "JSearchSource", FakeJSearch)
    cfg = P.Config()
    cfg.enable_jsearch = True
    cfg.openwebninja_key = "x"
    cfg.portal_queries = ["strategy consultant"]
    cfg.portal_locations = ["India", "Germany"]
    P.collect_portal_jobs(cfg)
    assert ("strategy consultant in India", "in") in seen
    assert ("strategy consultant in Germany", "de") in seen
