"""Orchestration: connections in, ranked warm-intro matches out."""
from __future__ import annotations

import logging
from datetime import date

from .config import Config
from .connections import load_connections
from .dedupe import find_ambiguous_clusters, merge_exports
from .models import JobPosting, Match
from .network import build_company_index, network_strength
from .normalize import normalize_company
from .scoring import score_job
from .sources import (ActiveJobsDBSource, AdzunaSource, ApolloDumpSource,
                      ArbeitnowSource, CareersPageSource, Indeed12Source,
                      JSearchSource, LinkedInJobSearchSource, RemotiveSource,
                      SerpApiJobsSource)
from .sources.base import SourceError
from .discovery import SlugCache, resolve_board
from .sources import ATS_SOURCES

log = logging.getLogger(__name__)


def load_network(paths: list[str]) -> tuple[list, dict, dict]:
    """Load and merge one or more exports (oldest first) into a company index."""
    if not paths:
        raise ValueError("no connections files configured")
    batches = [load_connections(p) for p in paths]
    if len(batches) == 1:
        from .dedupe import dedupe_connections
        merged, stats = dedupe_connections(batches[0])
    else:
        merged, stats = merge_exports(*batches, labels=paths)
    index = build_company_index(merged)
    stats["companies"] = len(index)
    stats["ambiguous_clusters"] = len(find_ambiguous_clusters(merged))
    return merged, index, stats


def collect_feed_jobs(cfg: Config) -> list[JobPosting]:
    """Broad feeds: pull everything, filter later. Failures are logged, not fatal."""
    jobs: list[JobPosting] = []
    if cfg.enable_arbeitnow:
        try:
            batch = ArbeitnowSource().fetch(max_pages=5)
            log.info("arbeitnow: %d postings", len(batch))
            jobs += batch
        except SourceError as exc:
            log.warning("arbeitnow failed: %s", exc)
    if cfg.enable_remotive:
        try:
            batch = RemotiveSource().fetch()
            log.info("remotive: %d postings", len(batch))
            jobs += batch
        except SourceError as exc:
            log.warning("remotive failed: %s", exc)
    if cfg.apollo_dump:
        try:
            batch = ApolloDumpSource().fetch(
                cfg.apollo_dump,
                countries=tuple(cfg.apollo_countries) or None,
                days=cfg.apollo_days or None)
            log.info("apollo dump: %d postings", len(batch))
            jobs += batch
        except SourceError as exc:
            log.warning("apollo dump failed: %s", exc)
    if cfg.enable_adzuna:
        src = AdzunaSource(cfg.adzuna_app_id, cfg.adzuna_app_key)
        for country in cfg.adzuna_countries:
            for query in cfg.adzuna_queries:
                try:
                    batch = src.fetch(country=country, what=query, max_pages=2)
                    log.info("adzuna %s/%s: %d postings", country, query, len(batch))
                    jobs += batch
                except SourceError as exc:
                    log.warning("adzuna %s/%s failed: %s", country, query, exc)
    jobs += collect_portal_jobs(cfg)
    return jobs


def collect_portal_jobs(cfg: Config) -> list[JobPosting]:
    """LinkedIn / Indeed / Glassdoor postings, via licensed aggregators.

    Every source here is a query x location fan-out, so the call count is the
    product of both lists -- worth keeping in mind against a metered quota.
    A source that fails on its first page is logged loudly rather than folded
    into an empty result, so a dead key never reads as a quiet market.
    """
    jobs: list[JobPosting] = []
    queries = cfg.portal_queries or []
    locations = cfg.portal_locations or [""]

    if cfg.enable_jsearch:
        # Prefer the direct front door when its key is configured -- same
        # index, one less intermediary.
        src = (JSearchSource(cfg.openwebninja_key, backend="openwebninja")
               if cfg.openwebninja_key else JSearchSource(cfg.rapidapi_key))
        for query in queries:
            for loc in locations:
                q = f"{query} in {loc}" if loc else query
                try:
                    batch = src.fetch(q, days=cfg.portal_days, max_pages=1)
                    log.info("jsearch %r: %d postings", q, len(batch))
                    jobs += batch
                except SourceError as exc:
                    log.warning("jsearch %r failed: %s", q, exc)

    for enabled, cls, label in (
        (cfg.enable_linkedin, LinkedInJobSearchSource, "linkedin"),
        (cfg.enable_active_ats, ActiveJobsDBSource, "active_ats"),
    ):
        if not enabled:
            continue
        src = cls(cfg.rapidapi_key)
        for query in queries:
            for loc in locations:
                try:
                    batch = src.fetch(title=query, location=loc,
                                      time_frame=cfg.portal_time_frame, max_pages=1)
                    log.info("%s %r/%r: %d postings", label, query, loc, len(batch))
                    jobs += batch
                except SourceError as exc:
                    log.warning("%s %r/%r failed: %s", label, query, loc, exc)

    if cfg.enable_google_jobs:
        src = SerpApiJobsSource(cfg.serpapi_key)
        for query in queries:
            for loc in locations:
                try:
                    batch = src.fetch(query, location=loc, days=cfg.portal_days,
                                      max_pages=1)
                    log.info("google_jobs %r/%r: %d postings", query, loc, len(batch))
                    jobs += batch
                except SourceError as exc:
                    log.warning("google_jobs %r/%r failed: %s", query, loc, exc)
    return jobs


def collect_indeed_jobs(cfg: Config, index: dict) -> list[JobPosting]:
    """Indeed is company-scoped, so drive it from the network ranking.

    Asking Indeed about the employers where the network is deepest is a
    strictly better use of a metered call than a blind keyword sweep: every
    posting it returns already has a warm path attached.
    """
    if not cfg.enable_indeed:
        return []
    from .network import top_companies

    src = Indeed12Source(cfg.rapidapi_key)
    jobs: list[JobPosting] = []
    for net in top_companies(index, cfg.indeed_top_n):
        try:
            batch = src.fetch(company=net.display_name,
                              locality=cfg.indeed_locality, max_pages=1)
            log.info("indeed %s: %d postings", net.display_name, len(batch))
            jobs += batch
        except SourceError as exc:
            log.warning("indeed %s failed: %s", net.display_name, exc)
    return jobs


def collect_ats_jobs(cfg: Config, index: dict) -> list[JobPosting]:
    """Probe ATS boards for the companies where the network is strongest."""
    from .network import top_companies

    cache = SlugCache()
    jobs: list[JobPosting] = []
    for net in top_companies(index, cfg.ats_probe_top_n):
        board = resolve_board(net.display_name, cache)
        if not board:
            continue
        provider, slug = board
        try:
            batch = ATS_SOURCES[provider]().fetch(slug, company=net.display_name)
            log.info("%s/%s (%s): %d postings", provider, slug, net.display_name, len(batch))
            jobs += batch
        except SourceError as exc:
            log.warning("%s/%s failed: %s", provider, slug, exc)
    cache.save()
    return jobs


def collect_careers_pages(cfg: Config) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    src = CareersPageSource()
    for company, url in (cfg.careers_pages or {}).items():
        try:
            batch = src.fetch(url, company=company)
            log.info("careers %s: %d postings", company, len(batch))
            jobs += batch
        except SourceError as exc:
            log.warning("careers page %s failed: %s", company, exc)
    return jobs


def dedupe_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    """Collapse the same opening seen on several boards, preferring a dated record."""
    from .dedupe import consolidate

    return consolidate(
        jobs,
        key_fn=lambda j: "|".join(str(x) for x in j.dedupe_key()),
        # Prefer a posting that has a date, then a description, then the ATS
        # record over an aggregator's copy (ATS links are canonical).
        rank_fn=lambda j: (j.posted_at is not None, len(j.description or ""),
                           j.source in ("greenhouse", "lever", "ashby")),
    )


def run(cfg: Config, today: date | None = None) -> tuple[list[Match], dict]:
    connections, index, stats = load_network(cfg.connections_files)
    log.info("network: %d connections across %d companies", len(connections), len(index))

    jobs = (collect_feed_jobs(cfg) + collect_ats_jobs(cfg, index)
            + collect_indeed_jobs(cfg, index) + collect_careers_pages(cfg))
    raw_count = len(jobs)
    jobs = dedupe_jobs(jobs)
    log.info("jobs: %d raw -> %d unique", raw_count, len(jobs))

    matches = []
    for job in jobs:
        net = index.get(normalize_company(job.company))
        matches.append(score_job(job, net, cfg.profile, today))

    matches = [m for m in matches if m.total >= cfg.profile.min_score]
    matches.sort(key=lambda m: -m.total)

    stats.update({
        "jobs_raw": raw_count,
        "jobs_unique": len(jobs),
        "matches": len(matches),
        "matches_with_warm_path": sum(1 for m in matches if m.has_warm_path),
    })
    return matches[: cfg.top_n], stats
