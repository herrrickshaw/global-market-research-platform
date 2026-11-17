"""SuccessFactors career sites - and the truncation trap they carry.

These sites are where the India arms of the Big Four actually post. EY's
parent feed returned 3,198 postings and zero India roles; Deloitte's 4,709 and
zero. Both firms hire heavily in India. The absence was a domain artefact.
"""
from __future__ import annotations

from datetime import date

import pytest

from jobsearch.sources import successfactors as sf
from jobsearch.sources.base import SourceError

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>EY Careers</title>
  <item>
    <title>Associate Director-Sector Insights-Govt and Public Sector | Gurgaon</title>
    <link>https://careers.ey.com/ey/job/Gurgaon-Associate-Director/1386910333/</link>
    <description>&lt;p&gt;Sector insights for Government &amp;amp; Infrastructure.&lt;/p&gt;</description>
    <pubDate>Mon, 18 Aug 2026 09:00:00 GMT</pubDate>
    <guid>1386910333</guid>
  </item>
</channel></rss>"""


def _rss_with(n: int) -> str:
    items = "".join(
        f"<item><title>Role {i} | Gurgaon</title>"
        f"<link>https://careers.ey.com/j/{i}</link></item>"
        for i in range(n))
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'


def test_host_is_normalised_from_a_url_or_a_bare_domain():
    assert sf.SuccessFactorsSource("https://careers.ey.com/").host == "careers.ey.com"
    assert sf.SuccessFactorsSource("careers.ey.com").host == "careers.ey.com"


def test_an_empty_host_is_refused():
    with pytest.raises(ValueError, match="career-site host"):
        sf.SuccessFactorsSource("")


def test_parses_the_rss_feed(monkeypatch):
    monkeypatch.setattr(sf, "http_get_text", lambda *_a, **_k: RSS)
    jobs = sf.SuccessFactorsSource("careers.ey.com").fetch(company="EY India")
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title.startswith("Associate Director-Sector Insights")
    assert j.company == "EY India"
    assert j.posted_at == date(2026, 8, 18)
    assert j.url.endswith("/1386910333/")
    # HTML entities and tags must not survive into the description an ATS
    # scorer will read.
    assert "<p>" not in j.description and "&amp;" not in j.description


def test_location_is_recovered_from_the_title_when_absent():
    """Career-site RSS rarely carries a location field; the title carries it
    after the last separator, which is where a reader would look."""
    monkeypatch_free = sf.SuccessFactorsSource("careers.ey.com")
    jobs = monkeypatch_free._parse(RSS, "EY India")
    assert jobs[0].location == "Gurgaon"


def _only_the_keyword_feed(payload):
    """Serve `payload` from the keyword feed and 404 the complete one."""
    def responder(url, *_a, **_k):
        if "sitemal" in url:
            raise SourceError("404")
        return payload
    return responder


def test_the_twenty_job_cap_is_reported_as_a_sample(monkeypatch, caplog):
    """The keyword RSS returns at most 20 jobs whatever the query.

    A board with hundreds of roles answers with 20 and says nothing. Left
    unlabelled that reads as the complete board -- the same failure this
    project has met with Shell's pages and Siemens' 26.
    """
    monkeypatch.setattr(sf, "http_get_text",
                        _only_the_keyword_feed(_rss_with(sf.RSS_CAP)))
    with caplog.at_level("WARNING"):
        jobs = sf.SuccessFactorsSource("careers.ey.com").fetch()
    assert len(jobs) == sf.RSS_CAP
    assert "SAMPLE" in caplog.text


def test_twenty_jobs_from_the_complete_feed_are_not_a_sample(monkeypatch, caplog):
    """`/sitemal.xml` is uncapped, so 20 there is an answer, not a ceiling.

    Warning anyway would cry wolf on every small board and teach the reader to
    ignore the one warning that matters.
    """
    monkeypatch.setattr(sf, "http_get_text",
                        lambda *_a, **_k: _rss_with(sf.RSS_CAP))
    with caplog.at_level("WARNING"):
        jobs = sf.SuccessFactorsSource("careers.ey.com").fetch()
    assert len(jobs) == sf.RSS_CAP
    assert "SAMPLE" not in caplog.text


def test_the_complete_feed_is_preferred_over_the_capped_one(monkeypatch):
    seen = []

    def record(url, *_a, **_k):
        seen.append(url)
        return RSS

    monkeypatch.setattr(sf, "http_get_text", record)
    sf.SuccessFactorsSource("careers.ey.com").fetch()
    assert len(seen) == 1 and seen[0].endswith("/sitemal.xml")


def test_rss_1_namespaced_items_are_found(monkeypatch):
    """The complete feed is RSS 1.0, which namespaces every element.

    Selecting on the qualified tag name finds every posting in the capped feed
    and none at all in the complete one -- an empty parse that would fall
    through to the truncated fallback without a word.
    """
    rdf = ('<?xml version="1.0"?>'
           '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"'
           ' xmlns="http://purl.org/rss/1.0/"'
           ' xmlns:dc="http://purl.org/dc/elements/1.1/">'
           '<item><title>Strategy Manager | Bengaluru</title>'
           '<link>https://careers.ey.com/j/9</link>'
           '<dc:date>2026-08-14T00:00:00Z</dc:date></item></rdf:RDF>')
    monkeypatch.setattr(sf, "http_get_text", lambda *_a, **_k: rdf)
    jobs = sf.SuccessFactorsSource("careers.ey.com").fetch(company="EY India")
    assert len(jobs) == 1
    assert jobs[0].title.startswith("Strategy Manager")
    assert jobs[0].location == "Bengaluru"
    assert jobs[0].posted_at == date(2026, 8, 14)


def test_a_query_is_url_encoded_into_the_keyword_feed(monkeypatch):
    seen = []

    def responder(url, *_a, **_k):
        seen.append(url)
        if "sitemal" in url:
            raise SourceError("404")
        return RSS

    monkeypatch.setattr(sf, "http_get_text", responder)
    sf.SuccessFactorsSource("careers.ey.com").fetch(query="business development")
    assert "business+development" in seen[1] or "business%20development" in seen[1]


def test_every_endpoint_failing_raises_rather_than_returning_empty(monkeypatch):
    """A broken integration is not an employer with nothing open.

    Returning [] here would have reproduced exactly the bug that hid EY India
    for this entire search.
    """
    monkeypatch.setattr(sf, "http_get_text",
                        lambda *_a, **_k: (_ for _ in ()).throw(SourceError("403")))
    with pytest.raises(SourceError, match="no SuccessFactors feed responded"):
        sf.SuccessFactorsSource("careers.ey.com").fetch()


def test_html_masquerading_as_a_feed_raises(monkeypatch):
    """A career site that answers the feed path with its normal HTML page
    parses to zero postings, which must not read as an empty board."""
    monkeypatch.setattr(sf, "http_get_text",
                        lambda *_a, **_k: "<html><body>Careers</body></html>")
    with pytest.raises(SourceError, match="no SuccessFactors feed responded"):
        sf.SuccessFactorsSource("careers.ey.com").fetch()


def test_a_second_endpoint_is_tried_when_the_first_fails(monkeypatch):
    calls = {"n": 0}

    def flaky(url, *_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SourceError("404")
        return RSS

    monkeypatch.setattr(sf, "http_get_text", flaky)
    jobs = sf.SuccessFactorsSource("careers.ey.com").fetch()
    assert len(jobs) == 1 and calls["n"] == 2


def test_rfc822_and_iso_dates_both_parse():
    assert sf._parse_date("Mon, 18 Aug 2026 09:00:00 GMT") == date(2026, 8, 18)
    assert sf._parse_date("2026-08-18T09:00:00Z") == date(2026, 8, 18)
    # Unreadable -> None, never a guessed date feeding the freshness score.
    assert sf._parse_date("last week") is None
    assert sf._parse_date("") is None


def test_double_escaped_html_is_flattened_completely():
    """These feeds escape HTML inside XML, so one decode is never enough.

    A single tag-strip leaves `&amp;` and `&nbsp;` as literal text, and the
    ATS scorer then treats `amp` and `nbsp` as CV keywords.
    """
    assert sf._strip_html("&lt;p&gt;Oil &amp;amp; gas&lt;/p&gt;") == "Oil & gas"
    assert sf._strip_html("<p>Oil &amp; gas</p>") == "Oil & gas"
    assert sf._strip_html("") == ""
