"""The Zyte renderer, and the boundary it is not allowed to cross.

Zyte will fetch anything, which makes it precisely the tool for quietly doing
what this project has declined to do throughout: scrape the job portals. A
README paragraph is not a control, so the refusal is enforced in code and
pinned here.
"""
from __future__ import annotations

import pytest

from jobsearch.sources import careers_page, zyte
from jobsearch.sources.base import SourceError
from jobsearch.sources.zyte import DeniedByPolicy


@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/jobs/view/123",
    "https://in.linkedin.com/jobs/business-development",
    "https://www.naukri.com/job-listings-x",
    "https://www.iimjobs.com/j/senior-manager-1",
    "https://hirist.tech/j/2",
    "https://www.instahyre.com/job/3",
    "https://www.foundit.in/job/4",
    "https://www.glassdoor.co.in/Job/x.htm",
    "https://uk.indeed.com/viewjob?jk=5",
])
def test_portals_are_refused(url):
    assert zyte.is_denied(url)
    with pytest.raises(DeniedByPolicy, match="terms forbid"):
        zyte.ZyteFetcher(api_key="k").fetch_html(url)


@pytest.mark.parametrize("url", [
    "https://jobs.siemens-energy.com/en/search",
    "https://careers.spglobal.com/jobs",
    "https://jobs.totalenergies.com/en_US/careers",
    "https://www.investindia.gov.in/careers",
])
def test_own_domain_careers_sites_are_allowed(url):
    """The employers' own careers pages are published to be read."""
    assert not zyte.is_denied(url)


def test_denylist_matches_on_domain_boundaries_only():
    """A substring check would wrongly refuse an unrelated host."""
    assert not zyte.is_denied("https://notlinkedin.com/jobs")
    assert not zyte.is_denied("https://linkedin.com.example.org/x")
    assert zyte.is_denied("https://careers.linkedin.com/x")


def test_policy_refusal_precedes_the_credential_check():
    """A denied host must be refused even with no key -- otherwise the refusal
    reads as a configuration problem that a key would fix."""
    with pytest.raises(DeniedByPolicy):
        zyte.ZyteFetcher(api_key="").fetch_html("https://www.linkedin.com/jobs/1")


def test_missing_key_is_reported_for_an_allowed_host():
    with pytest.raises(SourceError, match="ZYTE_API_KEY"):
        zyte.ZyteFetcher(api_key="").fetch_html("https://careers.spglobal.com/jobs")


def test_empty_render_is_a_failure_not_an_empty_board(monkeypatch):
    """A failed render returning [] would read as 'this employer isn't hiring'."""
    class Resp:
        def json(self):
            return {"browserHtml": ""}

    monkeypatch.setattr(zyte, "_post", lambda *_a, **_k: Resp())
    with pytest.raises(SourceError, match="not evidence"):
        zyte.ZyteFetcher(api_key="k").fetch_html("https://careers.spglobal.com/jobs")


def test_key_travels_in_the_authorization_header(monkeypatch):
    seen = {}

    class Resp:
        def json(self):
            return {"browserHtml": "<html></html>"}

    def capture(url, *, json_body, headers=None, **_k):
        seen["url"], seen["headers"] = url, headers or {}
        return Resp()

    monkeypatch.setattr(zyte, "_post", capture)
    zyte.ZyteFetcher(api_key="s3cret").fetch_html("https://careers.spglobal.com/jobs")
    assert seen["headers"]["Authorization"].startswith("Basic ")
    assert "s3cret" not in seen["url"]


def test_renderer_output_feeds_the_existing_schema_org_parser():
    """The renderer supplies HTML; parsing stays in one place."""
    html = """<html><script type="application/ld+json">
      {"@type":"JobPosting","title":"Senior M&A Consultant",
       "datePosted":"2026-08-04",
       "hiringOrganization":{"name":"Siemens Energy"},
       "jobLocation":{"address":{"addressLocality":"Munich",
                                 "addressCountry":"DE"}}}
    </script></html>"""

    class FakeRenderer:
        def fetch_html(self, url):
            return html

    jobs = careers_page.CareersPageSource(fetcher=FakeRenderer()).fetch(
        "https://jobs.siemens-energy.com/search", company="Siemens Energy")
    assert len(jobs) == 1
    assert jobs[0].title == "Senior M&A Consultant"
    assert "Munich" in jobs[0].location


def test_careers_page_without_a_renderer_is_unchanged(monkeypatch):
    monkeypatch.setattr(careers_page, "http_get_text",
                        lambda *_a, **_k: "<html>no jobs here</html>")
    assert careers_page.CareersPageSource().fetch("https://example.test/careers") == []
