"""Connection deduplication.

Built on ``consolidate`` from the parent platform's
``Downloads/code/python_files/entity_resolution.py`` (key_fn + rank_fn, keep the
highest-ranked record per key, preserve first-seen order). It is vendored here
rather than imported so this package stays self-contained, and follows the house
convention from ANALYSIS_METHODOLOGY_SUMMARY.md 1.3: key on a primary id, keep
the most recent occurrence.

Policy, and why it is deliberately conservative
-----------------------------------------------
Measured against a real 13,825-row export:

    duplicate profile URLs .................. 0
    duplicate emails ........................ 0
    same name + same company, diff URL ...... 3 clusters
    same name, DIFFERENT company ............ 193 names   <-- false-merge risk
    blank URL ............................... 151 rows

A single export is already unique on profile URL, so URL-keyed dedup is a no-op
on one file -- it earns its keep when you merge exports taken months apart, where
the same person reappears with a changed company, title, or locale subdomain.

Fuzzy name-based merging is NOT done automatically: it risks 193 wrong merges to
catch at most 3 real ones. Ambiguous clusters are reported for human review via
``find_ambiguous_clusters`` instead.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Callable, Iterable, TypeVar

from .models import Connection
from .normalize import normalize_company, normalize_linkedin_url, normalize_person_name

T = TypeVar("T")

_EPOCH = date(1970, 1, 1)


def consolidate(candidates: list[T], key_fn: Callable[[T], str],
                rank_fn: Callable[[T], tuple]) -> list[T]:
    """Collapse candidates sharing key_fn(c) to the single highest-ranked one.

    rank_fn returns a tuple compared with normal tuple ordering (higher wins).
    Preserves first-seen order of each key's winning record. Records whose key
    is falsy are passed through untouched -- they have no identity to merge on.
    """
    best: dict[str, T] = {}
    best_rank: dict[str, tuple] = {}
    order: list[str] = []
    passthrough: list[tuple[int, T]] = []

    for idx, c in enumerate(candidates):
        key = key_fn(c)
        if not key:
            passthrough.append((idx, c))
            continue
        rank = rank_fn(c)
        if key not in best:
            order.append(key)
            best[key], best_rank[key] = c, rank
        elif rank > best_rank[key]:
            best[key], best_rank[key] = c, rank

    return [best[k] for k in order] + [c for _, c in passthrough]


def completeness(conn: Connection) -> int:
    """How much usable signal a record carries. Tie-breaker only."""
    return sum(bool(x) for x in (conn.company, conn.position, conn.email))


def recency_rank(conn: Connection) -> tuple:
    """Rank records from a SINGLE export.

    NOTE: ``connected_on`` is the date the connection was made, not the date the
    record was written -- it is identical across exports for the same person, so
    it says nothing about which record is fresher. Within one export that does
    not matter (there are no true duplicates), and completeness is the only
    meaningful tie-breaker. Cross-export freshness is handled by
    ``merge_exports``, which ranks on export order instead.
    """
    return (completeness(conn), conn.connected_on or _EPOCH)


def dedupe_connections(connections: Iterable[Connection]) -> tuple[list[Connection], dict]:
    """Deduplicate one export on canonical profile URL. Returns (deduped, stats).

    Rows with no URL cannot be keyed and are always preserved -- dropping them
    would silently lose real connections.
    """
    rows = list(connections)
    keyed = [c for c in rows if normalize_linkedin_url(c.url)]
    unkeyed = [c for c in rows if not normalize_linkedin_url(c.url)]

    deduped = consolidate(keyed, key_fn=lambda c: normalize_linkedin_url(c.url),
                          rank_fn=recency_rank)
    stats = {
        "input_rows": len(rows),
        "keyed_rows": len(keyed),
        "unkeyed_rows": len(unkeyed),
        "duplicates_removed": len(keyed) - len(deduped),
        "output_rows": len(deduped) + len(unkeyed),
    }
    return deduped + unkeyed, stats


def merge_exports(*batches: Iterable[Connection],
                  labels: list[str] | None = None) -> tuple[list[Connection], dict]:
    """Merge exports taken at different times into one current view.

    Batches MUST be passed oldest-first: freshness is derived from export
    position, because no field in the row itself distinguishes an old record
    from a new one. The newest export wins on every field (company, title,
    email), so job changes since the older export are picked up.

    Records present only in an older export are retained, not dropped -- a
    connection missing from a later export usually means a deactivated profile
    rather than a lost contact, and silently discarding them loses real people.
    """
    ordered = [list(b) for b in batches]
    if labels is None:
        labels = [f"export_{i}" for i in range(len(ordered))]

    # Wrap each record with its batch index so rank_fn can see provenance.
    wrapped: list[tuple[int, Connection]] = []
    for idx, batch in enumerate(ordered):
        wrapped.extend((idx, c) for c in batch)

    keyed = [w for w in wrapped if normalize_linkedin_url(w[1].url)]
    unkeyed = [w for w in wrapped if not normalize_linkedin_url(w[1].url)]

    winners = consolidate(
        keyed,
        key_fn=lambda w: normalize_linkedin_url(w[1].url),
        # Newer batch always beats older; completeness breaks within-batch ties.
        rank_fn=lambda w: (w[0], completeness(w[1])),
    )

    url_sets = [{normalize_linkedin_url(c.url) for c in b if normalize_linkedin_url(c.url)}
                for b in ordered]
    newest = url_sets[-1] if url_sets else set()
    older_union = set().union(*url_sets[:-1]) if len(url_sets) > 1 else set()

    stats = {
        "batches": len(ordered),
        "labels": labels,
        "rows_per_batch": [len(b) for b in ordered],
        "input_rows": len(wrapped),
        "output_rows": len(winners) + len(unkeyed),
        "duplicates_removed": len(keyed) - len(winners),
        "new_in_newest": len(newest - older_union),
        "only_in_older": len(older_union - newest),
    }
    return [c for _, c in winners] + [c for _, c in unkeyed], stats


def refresh_stats(old: Iterable[Connection], new: Iterable[Connection]) -> dict:
    """Quantify what changed between two exports of the same network."""
    o = {normalize_linkedin_url(c.url): c for c in old if normalize_linkedin_url(c.url)}
    n = {normalize_linkedin_url(c.url): c for c in new if normalize_linkedin_url(c.url)}
    both = set(o) & set(n)
    return {
        "old_rows": len(o),
        "new_rows": len(n),
        "added": len(set(n) - set(o)),
        "disappeared": len(set(o) - set(n)),
        "company_changed": sum(1 for k in both
                               if o[k].company != n[k].company and o[k].company and n[k].company),
        "title_changed": sum(1 for k in both
                             if o[k].position != n[k].position and o[k].position and n[k].position),
    }


def find_ambiguous_clusters(connections: Iterable[Connection]) -> list[dict]:
    """Find same-person candidates that are NOT safe to merge automatically.

    Same normalised name AND same normalised company, but different profile
    URLs: either one person with two accounts, or two colleagues who share a
    name. Surfaced for human review, never merged.
    """
    buckets: dict[tuple[str, str], list[Connection]] = defaultdict(list)
    for c in connections:
        name = normalize_person_name(c.name)
        company = normalize_company(c.company)
        if name and company:
            buckets[(name, company)].append(c)

    clusters = []
    for (name, company), members in buckets.items():
        urls = {normalize_linkedin_url(m.url) for m in members if normalize_linkedin_url(m.url)}
        if len(urls) > 1:
            clusters.append({
                "name": name,
                "company": company,
                "count": len(members),
                "profiles": sorted(urls),
                "records": members,
            })
    return sorted(clusters, key=lambda x: -x["count"])


def find_name_collisions(connections: Iterable[Connection]) -> list[dict]:
    """Same normalised name at different companies -- distinct people.

    Reported so the false-merge risk is visible and quantified rather than
    discovered later as data corruption.
    """
    buckets: dict[str, set] = defaultdict(set)
    for c in connections:
        name = normalize_person_name(c.name)
        company = normalize_company(c.company)
        if name and company:
            buckets[name].add(company)
    return sorted(
        ({"name": n, "companies": sorted(co)} for n, co in buckets.items() if len(co) > 1),
        key=lambda x: -len(x["companies"]),
    )
