from jobsearch.connections import load_connections
from jobsearch.dedupe import (consolidate, dedupe_connections, find_ambiguous_clusters,
                              find_name_collisions, merge_exports, refresh_stats)
from jobsearch.models import Connection
from jobsearch.normalize import normalize_linkedin_url

OLD = "tests/fixtures/connections_sample.csv"
NEW = "tests/fixtures/connections_sample_newer.csv"


def _by_url(conns):
    return {normalize_linkedin_url(c.url): c for c in conns}


def test_consolidate_keeps_highest_rank_and_first_seen_order():
    items = [{"k": "a", "v": 1}, {"k": "b", "v": 5}, {"k": "a", "v": 9}]
    out = consolidate(items, key_fn=lambda x: x["k"], rank_fn=lambda x: (x["v"],))
    assert [x["k"] for x in out] == ["a", "b"]
    assert out[0]["v"] == 9


def test_consolidate_passes_through_unkeyable_records():
    items = [{"k": "", "v": 1}, {"k": "a", "v": 2}, {"k": "", "v": 3}]
    out = consolidate(items, key_fn=lambda x: x["k"], rank_fn=lambda x: (x["v"],))
    assert len(out) == 3


def test_single_export_dedupe_is_a_noop_on_unique_urls():
    conns = load_connections(OLD)
    deduped, stats = dedupe_connections(conns)
    assert stats["duplicates_removed"] == 0
    assert len(deduped) == len(conns)


def test_merge_keeps_newer_company_and_title():
    """Regression: ranking on connected_on kept the OLDER record, since that
    field is identical across exports. Freshness must come from export order."""
    old, new = load_connections(OLD), load_connections(NEW)
    merged, stats = merge_exports(old, new)
    m = _by_url(merged)
    bruno = m["linkedin.com/in/bruno-mertens"]
    assert bruno.company == "Uniper SE"           # was Siemens Energy AG
    assert bruno.position == "VP Corporate Development"
    assert m["linkedin.com/in/devi-nair"].position == "Director"   # was Senior Manager
    assert m["linkedin.com/in/asha-rao"].position == "Senior Talent Partner"
    assert stats["duplicates_removed"] == 5


def test_merge_matches_across_locale_subdomains():
    """Bruno is de.linkedin.com in the old export, www in the new one."""
    merged, _ = merge_exports(load_connections(OLD), load_connections(NEW))
    urls = [normalize_linkedin_url(c.url) for c in merged]
    assert urls.count("linkedin.com/in/bruno-mertens") == 1


def test_merge_retains_people_absent_from_newest_export():
    """Carla is only in the old export - a deactivated profile, not a lost contact."""
    merged, stats = merge_exports(load_connections(OLD), load_connections(NEW))
    assert "linkedin.com/in/carla-diaz" in _by_url(merged)
    assert stats["only_in_older"] == 1
    assert stats["new_in_newest"] == 1


def test_refresh_stats_counts_changes():
    s = refresh_stats(load_connections(OLD), load_connections(NEW))
    assert s["added"] == 1 and s["disappeared"] == 1
    assert s["company_changed"] == 1 and s["title_changed"] == 3


def _c(name, url, company):
    first, last = name.split()
    return Connection(first, last, url, "", company, "Manager", None)


def test_ambiguous_cluster_flagged_not_merged():
    rows = [_c("Neha Singh", "https://linkedin.com/in/neha-singh-1", "Invest India"),
            _c("Neha Singh", "https://linkedin.com/in/neha-singh-2", "Invest India")]
    clusters = find_ambiguous_clusters(rows)
    assert len(clusters) == 1 and clusters[0]["count"] == 2
    deduped, _ = dedupe_connections(rows)
    assert len(deduped) == 2, "same name+company must NOT be auto-merged"


def test_name_collision_across_companies_is_reported_not_merged():
    rows = [_c("Mohit Singh", "https://linkedin.com/in/mohit-1", "Amazon"),
            _c("Mohit Singh", "https://linkedin.com/in/mohit-2", "Deloitte")]
    assert len(find_name_collisions(rows)) == 1
    assert len(find_ambiguous_clusters(rows)) == 0
    deduped, _ = dedupe_connections(rows)
    assert len(deduped) == 2
