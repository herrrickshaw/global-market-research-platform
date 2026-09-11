"""End-to-end pipeline test with stubbed sources (no network)."""
from datetime import date

import jobsearch.pipeline as pipeline
from jobsearch.config import Config
from jobsearch.models import JobPosting
from jobsearch.pipeline import dedupe_jobs, run

TODAY = date(2026, 8, 20)
OLD, NEW = "tests/fixtures/connections_sample.csv", "tests/fixtures/connections_sample_newer.csv"


def _cfg():
    c = Config()
    c.connections_files = [OLD, NEW]
    c.profile.min_score = 0.20
    return c


FAKE_JOBS = [
    # Shell: user has 2 connections incl. a talent partner -> strong warm path
    JobPosting("greenhouse", "Shell plc", "Head of Business Development",
               "Berlin, Germany", "http://j/1", date(2026, 8, 18), "LNG portfolio growth"),
    # Uniper: Bruno moved there in the newer export -> only matches post-merge
    JobPosting("lever", "Uniper SE", "Director Corporate Development",
               "Düsseldorf, Germany", "http://j/2", date(2026, 8, 10), "energy transition"),
    # No connections anywhere -> cold
    JobPosting("arbeitnow", "Totally Unknown GmbH", "Investment Promotion Manager",
               "Munich, Germany", "http://j/3", date(2026, 8, 1), ""),
    # Hard negative -> must be filtered out entirely
    JobPosting("arbeitnow", "Shell plc", "Software Engineer Intern",
               "Berlin, Germany", "http://j/4", date(2026, 8, 19), ""),
    # Irrelevant role at a strong-network company -> network must not rescue it
    JobPosting("greenhouse", "Invest India", "Warehouse Operative",
               "Delhi, India", "http://j/5", date(2026, 8, 19), ""),
]


def test_pipeline_end_to_end(monkeypatch):
    monkeypatch.setattr(pipeline, "collect_feed_jobs", lambda cfg: list(FAKE_JOBS))
    monkeypatch.setattr(pipeline, "collect_ats_jobs", lambda cfg, idx: [])
    monkeypatch.setattr(pipeline, "collect_careers_pages", lambda cfg: [])

    matches, stats = run(_cfg(), today=TODAY)
    titles = [m.job.title for m in matches]

    assert "Software Engineer Intern" not in titles, "hard negative must be dropped"
    assert "Warehouse Operative" not in titles, "network must not rescue a zero fit"
    assert matches == sorted(matches, key=lambda m: -m.total), "must be ranked"

    top = matches[0]
    assert top.job.company == "Shell plc" and top.has_warm_path
    assert stats["matches_with_warm_path"] >= 2


def test_uniper_matches_only_because_of_the_merge(monkeypatch):
    """Bruno is at Siemens Energy in the old export and Uniper in the new one.
    The Uniper role has a warm path only if the merge picked up the job change."""
    monkeypatch.setattr(pipeline, "collect_feed_jobs", lambda cfg: list(FAKE_JOBS))
    monkeypatch.setattr(pipeline, "collect_ats_jobs", lambda cfg, idx: [])
    monkeypatch.setattr(pipeline, "collect_careers_pages", lambda cfg: [])

    merged_matches, _ = run(_cfg(), today=TODAY)
    uniper = next(m for m in merged_matches if m.job.company == "Uniper SE")
    assert uniper.has_warm_path

    stale = _cfg()
    stale.connections_files = [OLD]          # old export only
    stale_matches, _ = run(stale, today=TODAY)
    uniper_stale = next(m for m in stale_matches if m.job.company == "Uniper SE")
    assert not uniper_stale.has_warm_path
    assert uniper.total > uniper_stale.total


def test_cross_source_job_dedupe_prefers_canonical_ats_record():
    dupes = [
        JobPosting("arbeitnow", "Shell", "Head of Business Development (m/w/d)",
                   "Berlin, Germany", "http://aggregator/x", None, ""),
        JobPosting("greenhouse", "Shell plc", "Head of Business Development",
                   "Berlin, Germany", "http://boards/x", date(2026, 8, 18), "full text"),
    ]
    out = dedupe_jobs(dupes)
    assert len(out) == 1
    assert out[0].source == "greenhouse", "canonical ATS record should win"


def test_reports_render(tmp_path, monkeypatch):
    from jobsearch.report import to_csv, to_html, to_markdown
    monkeypatch.setattr(pipeline, "collect_feed_jobs", lambda cfg: list(FAKE_JOBS))
    monkeypatch.setattr(pipeline, "collect_ats_jobs", lambda cfg, idx: [])
    monkeypatch.setattr(pipeline, "collect_careers_pages", lambda cfg: [])
    matches, _ = run(_cfg(), today=TODAY)

    csv_p = to_csv(matches, tmp_path / "m.csv")
    md_p = to_markdown(matches, tmp_path / "m.md")
    html_p = to_html(matches, tmp_path / "m.html")
    assert csv_p.read_text().startswith("score,")
    assert "Head of Business Development" in md_p.read_text()
    html = html_p.read_text()
    assert "<table>" in html and 'class="warm"' in html


def test_open_only_stands_down_the_posted_date_window():
    """Asking for still-open roles supersedes asking for new ones.

    Uniper's Head of LNG Trading was posted 2026-07-17 and last seen
    2026-09-08: alive, and silently discarded by a 45-day posted-date cutoff.
    Filtering on both at once throws away exactly the long-lived senior roles
    that sighting data exists to rescue.
    """
    import json
    from datetime import date, timedelta

    from jobsearch.config import Config
    from jobsearch.pipeline import collect_feed_jobs

    today = date.today()
    dump = {"Uniper": {"org_id": "x", "total": 1, "jobs": [
        {"title": "Head of LNG Trading", "country": "Germany",
         "posted_at": str(today - timedelta(days=56)),
         "last_seen_at": str(today - timedelta(days=3)),
         "url": "u"}]}}

    import tempfile
    import pathlib
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / "dump.json"
        path.write_text(json.dumps(dump))

        cfg = Config()
        cfg.apollo_dump = str(path)
        cfg.apollo_days = 45
        # Recency alone loses it.
        assert collect_feed_jobs(cfg) == []
        # Asking for open roles gets it back.
        cfg.apollo_stale_after = 21
        got = collect_feed_jobs(cfg)
        assert len(got) == 1 and got[0].title == "Head of LNG Trading"
