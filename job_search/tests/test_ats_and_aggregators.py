"""Workday, the unauthenticated ATS feeds, and the free-key aggregators.

As with the portal sources, none of these hosts is reachable from this
environment, so the tests drive parsing and failure paths against recorded
payload shapes. The recurring theme is the same one that has bitten this
project four times: a source that returns nothing must never be
indistinguishable from an employer with nothing open.
"""
from __future__ import annotations

from datetime import date

import pytest

from jobsearch.sources import aggregators, ats_public, workday
from jobsearch.sources.base import SourceError


# --------------------------------------------------------------------------
# Workday
# --------------------------------------------------------------------------

SHELL_URL = ("https://shell.wd3.myworkdayjobs.com/en-US/shellcareers/job/"
             "Shell-Technology-Centre---Bangalore/Senior-Strategy-Consultant_R206921-1")


def test_workday_config_is_derived_from_a_posting_url():
    """Tenant, data-centre number and site are all unguessable from a name."""
    src = workday.WorkdaySource.from_url(SHELL_URL)
    assert (src.tenant, src.wd, src.site, src.locale) == (
        "shell", "wd3", "shellcareers", "en-US")
    assert src.endpoint == (
        "https://shell.wd3.myworkdayjobs.com/wday/cxs/shell/shellcareers/jobs")


def test_workday_rejects_a_non_workday_url():
    with pytest.raises(ValueError, match="myworkdayjobs"):
        workday.WorkdaySource.from_url("https://careers.spglobal.com/jobs/123")


def test_workday_requires_tenant_and_site():
    with pytest.raises(ValueError, match="tenant and a site"):
        workday.WorkdaySource(tenant="shell", site="")


def test_workday_tenants_are_discovered_from_stored_urls():
    found = workday.tenants_from_urls([
        SHELL_URL,
        "https://woodmac.wd3.myworkdayjobs.com/woodmaccareers/job/London/Analyst_R1",
        "https://careers.spglobal.com/jobs/999",     # not Workday
        "",
    ])
    assert set(found) == {"shell", "woodmac"}
    assert found["woodmac"]["site"] == "woodmaccareers"
    # No locale segment in that URL -- the default must fill in, not crash.
    assert found["woodmac"]["locale"] == "en-US"


def test_workable_slugs_are_discovered_from_stored_urls():
    assert workday.workable_slugs_from_urls(
        ["https://apply.workable.com/rystad-energy/j/371BD8220A",
         "https://example.test/x"]) == {"rystad-energy"}


def test_workday_limit_is_capped_at_twenty(monkeypatch):
    """A larger limit returns an empty page instead of erroring, which reads
    exactly like 'this employer has no openings'."""
    seen = {}

    def capture(url, body, headers=None):
        seen["body"] = body
        return {"total": 0, "jobPostings": []}

    monkeypatch.setattr(workday, "http_post_json", capture)
    workday.WorkdaySource("shell", "shellcareers").fetch()
    assert seen["body"]["limit"] == workday.MAX_LIMIT == 20


def test_workday_pages_by_offset_and_stops_at_total(monkeypatch):
    pages = [
        {"total": 3, "jobPostings": [{"title": f"A{i}", "externalPath": f"/job/{i}"}
                                     for i in range(2)]},
        {"total": 3, "jobPostings": [{"title": "A2", "externalPath": "/job/2"}]},
    ]
    calls = {"n": 0}

    def serve(url, body, headers=None):
        calls["n"] += 1
        return pages[min(body["offset"] // 20, len(pages) - 1)]

    monkeypatch.setattr(workday, "http_post_json", serve)
    jobs = workday.WorkdaySource("shell", "shellcareers").fetch(company="Shell")
    assert len(jobs) == 3
    assert calls["n"] == 2          # stopped at total, did not keep paging
    assert jobs[0].company == "Shell"
    assert jobs[0].url.startswith("https://shell.wd3.myworkdayjobs.com/en-US/")


def test_workday_page_one_failure_propagates(monkeypatch):
    monkeypatch.setattr(workday, "http_post_json",
                        lambda *_a, **_k: (_ for _ in ()).throw(SourceError("403")))
    with pytest.raises(SourceError):
        workday.WorkdaySource("shell", "shellcareers").fetch()


def test_workday_warns_when_it_returns_less_than_total(monkeypatch, caplog):
    """A truncated pull must not read as the whole board."""
    monkeypatch.setattr(workday, "http_post_json", lambda *_a, **_k: {
        "total": 500, "jobPostings": [{"title": "A", "externalPath": "/job/1"}]})
    with caplog.at_level("WARNING"):
        workday.WorkdaySource("shell", "shellcareers").fetch(max_pages=1)
    assert "of 500" in caplog.text


def test_workday_parses_its_relative_posted_text():
    today = date(2026, 8, 21)
    assert workday.parse_posted_on("Posted Today", today) == today
    assert workday.parse_posted_on("Posted Yesterday", today) == date(2026, 8, 20)
    assert workday.parse_posted_on("Posted 3 Days Ago", today) == date(2026, 8, 18)
    assert workday.parse_posted_on("Posted 30+ Days Ago", today) == date(2026, 7, 22)
    # Unreadable -> None, never a guessed date feeding the freshness score.
    assert workday.parse_posted_on("Posted recently", today) is None
    assert workday.parse_posted_on("", today) is None


# --------------------------------------------------------------------------
# SmartRecruiters / Workable / Personio
# --------------------------------------------------------------------------

def test_smartrecruiters_builds_an_applyable_url(monkeypatch):
    """The API's own `ref` points at posting JSON, not a page a human can use."""
    monkeypatch.setattr(ats_public, "http_get_json", lambda *_a, **_k: {
        "content": [{"id": "744", "name": "Strategy Manager",
                     "location": {"city": "London", "country": "uk"},
                     "releasedDate": "2026-08-04T00:00:00.000Z"}]})
    jobs = ats_public.SmartRecruitersSource().fetch("acme", company="Acme")
    assert jobs[0].url == "https://careers.smartrecruiters.com/acme/744"
    assert jobs[0].location == "London, uk"
    assert jobs[0].posted_at == date(2026, 8, 4)


def test_smartrecruiters_page_one_failure_propagates(monkeypatch):
    monkeypatch.setattr(ats_public, "http_get_json",
                        lambda *_a, **_k: (_ for _ in ()).throw(SourceError("404")))
    with pytest.raises(SourceError):
        ats_public.SmartRecruitersSource().fetch("acme")


def test_workable_reads_the_public_widget(monkeypatch):
    monkeypatch.setattr(ats_public, "http_get_json", lambda *_a, **_k: {
        "name": "Rystad Energy",
        "jobs": [{"title": "Senior Analyst", "city": "Oslo", "country": "Norway",
                  "url": "https://apply.workable.com/rystad-energy/j/371BD8220A",
                  "published_on": "2026-08-10", "shortcode": "371BD8220A"}]})
    jobs = ats_public.WorkableSource().fetch("rystad-energy")
    assert jobs[0].company == "Rystad Energy"      # falls back to the feed's name
    assert jobs[0].location == "Oslo, Norway"
    assert jobs[0].posted_at == date(2026, 8, 10)


def test_personio_parses_its_xml_feed(monkeypatch):
    xml = """<?xml version="1.0"?><workzag-jobs>
      <position><id>42</id><name>Business Development Manager</name>
        <office>Munich</office><createdAt>2026-08-01</createdAt>
        <jobDescriptions>Grow the book.</jobDescriptions></position>
    </workzag-jobs>"""
    monkeypatch.setattr(ats_public, "http_get_text", lambda *_a, **_k: xml)
    jobs = ats_public.PersonioSource().fetch("acme", company="Acme")
    assert jobs[0].title == "Business Development Manager"
    assert jobs[0].location == "Munich"
    assert jobs[0].url == "https://acme.jobs.personio.de/job/42"


def test_personio_reports_an_html_error_page_as_a_failure(monkeypatch):
    """An HTML error page is often WELL-FORMED XML: it parses fine, contains
    no <position>, and returns [] -- indistinguishable from a company with
    nothing open. Only checking the root element catches it."""
    monkeypatch.setattr(ats_public, "http_get_text",
                        lambda *_a, **_k: "<html>404 not found</html>")
    with pytest.raises(SourceError, match="likely an error page"):
        ats_public.PersonioSource().fetch("acme")


# --------------------------------------------------------------------------
# Jooble / Careerjet
# --------------------------------------------------------------------------

def test_jooble_never_leaks_its_key_into_an_error(monkeypatch):
    """Jooble's key is a PATH segment, so redact() -- which masks query values
    -- cannot help. The failure path must not carry the URL at all."""
    monkeypatch.setattr(aggregators, "http_post_json",
                        lambda *_a, **_k: (_ for _ in ()).throw(
                            SourceError("POST https://jooble.org/api/s3cret failed")))
    with pytest.raises(SourceError) as excinfo:
        aggregators.JoobleSource(api_key="s3cret").fetch("analyst")
    assert "s3cret" not in str(excinfo.value)
    assert "***" in str(excinfo.value)


def test_jooble_parses_its_rows(monkeypatch):
    monkeypatch.setattr(aggregators, "http_post_json", lambda *_a, **_k: {
        "jobs": [{"title": "BD Manager", "company": "Acme", "location": "Mumbai",
                  "link": "https://example.test/1", "updated": "2026-08-04T00:00:00",
                  "id": "1"}]})
    jobs = aggregators.JoobleSource(api_key="k").fetch("bd", "India", max_pages=1)
    assert jobs[0].company == "Acme"
    assert jobs[0].posted_at == date(2026, 8, 4)


def test_jooble_without_a_key_raises():
    with pytest.raises(SourceError, match="JOOBLE_KEY"):
        aggregators.JoobleSource(api_key="").fetch("analyst")


def test_careerjet_treats_an_error_body_as_a_failure(monkeypatch):
    """A bad affid comes back as HTTP 200 with type=ERROR."""
    monkeypatch.setattr(aggregators, "http_get_json",
                        lambda *_a, **_k: {"type": "ERROR", "error": "bad affid"})
    with pytest.raises(SourceError, match="bad affid"):
        aggregators.CareerjetSource(affid="x").fetch("analyst")


def test_careerjet_parses_several_date_formats():
    assert aggregators._date("2026-08-04") == date(2026, 8, 4)
    assert aggregators._date("04/08/2026") == date(2026, 8, 4)
    assert aggregators._date("2026/08/04") == date(2026, 8, 4)
    assert aggregators._date("not a date") is None


def test_careerjet_without_an_affid_raises():
    with pytest.raises(SourceError, match="CAREERJET_AFFID"):
        aggregators.CareerjetSource(affid="").fetch("analyst")


def test_personio_distinguishes_an_empty_board_from_an_error_page(monkeypatch):
    """A genuinely empty feed is not an error -- only a wrong root is."""
    monkeypatch.setattr(ats_public, "http_get_text",
                        lambda *_a, **_k: "<workzag-jobs></workzag-jobs>")
    assert ats_public.PersonioSource().fetch("acme") == []


def test_personio_rejects_a_malformed_response(monkeypatch):
    monkeypatch.setattr(ats_public, "http_get_text", lambda *_a, **_k: "<html><p>oops")
    with pytest.raises(SourceError, match="non-XML"):
        ats_public.PersonioSource().fetch("acme")


# --------------------------------------------------------------------------
# "Posted recently" and "still open" are different questions
# --------------------------------------------------------------------------

def test_last_seen_at_is_captured_from_apollo():
    """Apollo returns last_seen_at on every posting and it was being discarded.

    posted_at answers "how new is this". Only last_seen_at answers "is it still
    on the board", which is what someone about to spend an evening writing
    applications actually needs.
    """
    from datetime import date
    from jobsearch.sources.apollo import _to_posting

    j = _to_posting({"title": "Manager", "city": "Mumbai", "country": "India",
                     "posted_at": "2026-08-11T09:00:00.000+00:00",
                     "last_seen_at": "2026-09-09T11:00:00.000+00:00"},
                    "Crisil", "apollo")
    assert j.posted_at == date(2026, 8, 11)
    assert j.last_seen_at == date(2026, 9, 9)
    assert j.days_since_seen(date(2026, 9, 11)) == 2


def test_a_missing_last_seen_reads_as_unknown_not_as_fresh():
    """Absent is not zero, again. A source that does not track the field cannot
    vouch for a posting being open, so it must report None rather than today."""
    from datetime import date
    from jobsearch.sources.apollo import _to_posting

    j = _to_posting({"title": "Manager", "posted_at": "2026-08-11T09:00:00Z"},
                    "C", "apollo")
    assert j.last_seen_at is None
    assert j.days_since_seen(date(2026, 9, 11)) is None


def test_stale_after_excludes_postings_with_no_sighting_data():
    """Asking for open-only roles must not quietly pass through everything whose
    freshness is unknown - that would turn a filter into a no-op."""
    from datetime import date, timedelta

    from jobsearch.models import JobPosting
    from jobsearch.sources.apollo import _matches

    today = date.today()
    fresh = JobPosting("apollo", "C", "Manager", "Mumbai, India", "u",
                       posted_at=today - timedelta(days=40),
                       last_seen_at=today - timedelta(days=2))
    gone = JobPosting("apollo", "C", "Manager", "Mumbai, India", "u",
                      posted_at=today - timedelta(days=10),
                      last_seen_at=today - timedelta(days=45))
    unknown = JobPosting("apollo", "C", "Manager", "Mumbai, India", "u",
                         posted_at=today - timedelta(days=3))

    assert _matches(fresh, None, None, 21) is True
    assert _matches(gone, None, None, 21) is False
    assert _matches(unknown, None, None, 21) is False
    # With no stale_after asked for, nothing is filtered on sighting age.
    for j in (fresh, gone, unknown):
        assert _matches(j, None, None, None) is True


def test_posted_recently_and_still_open_can_disagree():
    """The whole point of the field: a five-week-old posting still on the board
    beats a ten-day-old one that has already come down."""
    from datetime import date, timedelta

    from jobsearch.models import JobPosting
    from jobsearch.sources.apollo import _matches

    today = date.today()
    old_but_live = JobPosting("apollo", "C", "A", "Mumbai, India", "u",
                              posted_at=today - timedelta(days=35),
                              last_seen_at=today - timedelta(days=1))
    new_but_closed = JobPosting("apollo", "C", "B", "Mumbai, India", "u",
                                posted_at=today - timedelta(days=10),
                                last_seen_at=today - timedelta(days=40))
    since = today - timedelta(days=20)
    # Recency alone gets this exactly backwards.
    assert _matches(old_but_live, None, since, None) is False
    assert _matches(new_but_closed, None, since, None) is True
    # Sighting age gets it right.
    assert _matches(old_but_live, None, None, 21) is True
    assert _matches(new_but_closed, None, None, 21) is False
