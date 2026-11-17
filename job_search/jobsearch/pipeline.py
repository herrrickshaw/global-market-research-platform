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
from .sources.jsearch import country_code
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
                # A confirmed-open posting must not then be discarded for
                # being old. Uniper's Head of LNG Trading was posted 2026-07-17
                # and last seen 2026-09-08: alive, and thrown away by a 45-day
                # posted-date cutoff. Asking for open roles supersedes asking
                # for new ones, so the posted window stands down.
                days=None if cfg.apollo_stale_after else (cfg.apollo_days or None),
                stale_after=cfg.apollo_stale_after or None)
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
    jobs += collect_workday_jobs(cfg)
    jobs += collect_successfactors_jobs(cfg)
    jobs += collect_aggregator_jobs(cfg)
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
                    batch = src.fetch(q, days=cfg.portal_days, max_pages=1,
                                      country=country_code(loc))
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


def collect_workday_jobs(cfg: Config) -> list[JobPosting]:
    """Workday boards, configured per company or discovered from stored URLs.

    Auto-discovery is the point: the Apollo dump already carries a
    myworkdayjobs URL for every Workday employer in it, and those URLs hold the
    tenant, data-centre number and site -- none of which is guessable. So a
    company that cost credits to page through Apollo becomes free to read in
    full, with no coverage caveat, without anyone configuring anything.
    """
    from .sources import WorkdaySource, tenants_from_urls

    tenants: dict[str, dict] = {}
    for name, value in (cfg.workday_tenants or {}).items():
        if isinstance(value, str):
            try:
                src = WorkdaySource.from_url(value)
            except ValueError as exc:
                log.warning("workday %s: %s", name, exc)
                continue
            tenants[name] = {"tenant": src.tenant, "site": src.site,
                             "wd": src.wd, "locale": src.locale, "company": name}
        elif isinstance(value, dict):
            tenants[name] = {**value, "company": value.get("company", name)}

    if cfg.workday_autodiscover and cfg.apollo_dump:
        try:
            import json
            from pathlib import Path
            doc = json.loads(Path(cfg.apollo_dump).read_text())
            urls = [j.get("url", "") for v in doc.values() if isinstance(v, dict)
                    for j in v.get("jobs", [])]
            for tenant, found in tenants_from_urls(urls).items():
                tenants.setdefault(tenant, {**found, "company": None})
        except (OSError, ValueError) as exc:
            log.warning("workday autodiscovery from %s failed: %s", cfg.apollo_dump, exc)

    jobs: list[JobPosting] = []
    for name, cfg_ in tenants.items():
        try:
            src = WorkdaySource(tenant=cfg_["tenant"], site=cfg_["site"],
                                wd=cfg_.get("wd", "wd3"),
                                locale=cfg_.get("locale", "en-US"))
            batch = src.fetch(company=cfg_.get("company"))
            log.info("workday %s: %d postings", name, len(batch))
            jobs += batch
        except (SourceError, KeyError, ValueError) as exc:
            log.warning("workday %s failed: %s", name, exc)
    return jobs


def collect_successfactors_jobs(cfg: Config) -> list[JobPosting]:
    """SuccessFactors career sites, one per employer.

    Configured rather than probed: the host is an employer's own choice
    (careers.ey.com, southasiacareers.deloitte.com) and is not derivable from
    the company name. A failure here is logged per site, so one dead career
    site never hides the others.
    """
    from .sources import SuccessFactorsSource

    jobs: list[JobPosting] = []
    for company, host in (cfg.successfactors_sites or {}).items():
        try:
            batch = SuccessFactorsSource(host).fetch(company=company)
            log.info("successfactors %s (%s): %d postings", company, host, len(batch))
            jobs += batch
        except (SourceError, ValueError) as exc:
            log.warning("successfactors %s (%s) failed: %s", company, host, exc)
    return jobs


def collect_aggregator_jobs(cfg: Config) -> list[JobPosting]:
    """Jooble and Careerjet: the free-key sources that actually reach India."""
    from .sources import CareerjetSource, JoobleSource

    jobs: list[JobPosting] = []
    queries = cfg.portal_queries or []
    locations = cfg.portal_locations or [""]

    if cfg.jooble_key:
        src = JoobleSource(cfg.jooble_key)
        for query in queries:
            for loc in locations:
                try:
                    batch = src.fetch(query, loc, max_pages=1)
                    log.info("jooble %r/%r: %d postings", query, loc, len(batch))
                    jobs += batch
                except SourceError as exc:
                    log.warning("jooble %r/%r failed: %s", query, loc, exc)

    if cfg.careerjet_affid:
        src = CareerjetSource(cfg.careerjet_affid)
        for query in queries:
            for loc in locations:
                try:
                    batch = src.fetch(query, loc, locale=cfg.careerjet_locale,
                                      max_pages=1)
                    log.info("careerjet %r/%r: %d postings", query, loc, len(batch))
                    jobs += batch
                except SourceError as exc:
                    log.warning("careerjet %r/%r failed: %s", query, loc, exc)
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
    from .sources import ZyteFetcher

    # A renderer turns the JS-only careers sites (Siemens Energy, S&P Global,
    # TotalEnergies) from empty shells into readable pages. Without a key the
    # source behaves exactly as before.
    fetcher = ZyteFetcher(cfg.zyte_api_key) if cfg.zyte_api_key else None
    jobs: list[JobPosting] = []
    src = CareersPageSource(fetcher=fetcher)
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
                           j.source in ("greenhouse", "lever", "ashby",
                                        "workday", "successfactors")),
    )


def load_resume_text(cfg: Config) -> str:
    """Read the resume once per run, or return "" and say why.

    A missing resume is not fatal -- the ranking still works on titles and the
    network. It just means no ATS column, which is reported as absent rather
    than as a zero score.
    """
    from .resume import ResumeError, find_resume, load_resume

    path = cfg.resume_path or find_resume(cfg.resume_dir)
    if not path:
        log.info("no resume found in %s - ATS scoring disabled for this run",
                 cfg.resume_dir)
        return ""
    try:
        text = load_resume(path)
    except ResumeError as exc:
        log.warning("resume not read (%s) - ATS scoring disabled", exc)
        return ""
    log.info("resume: %s (%d characters)", path, len(text))
    return text


def run(cfg: Config, today: date | None = None) -> tuple[list[Match], dict]:
    connections, index, stats = load_network(cfg.connections_files)
    log.info("network: %d connections across %d companies", len(connections), len(index))

    jobs = (collect_feed_jobs(cfg) + collect_ats_jobs(cfg, index)
            + collect_indeed_jobs(cfg, index) + collect_careers_pages(cfg))
    raw_count = len(jobs)
    jobs = dedupe_jobs(jobs)
    log.info("jobs: %d raw -> %d unique", raw_count, len(jobs))

    resume = load_resume_text(cfg)

    matches = []
    for job in jobs:
        net = index.get(normalize_company(job.company))
        matches.append(score_job(job, net, cfg.profile, today, resume=resume))

    matches = [m for m in matches if m.total >= cfg.profile.min_score]

    scored = [m for m in matches if m.ats_percent is not None]
    if cfg.min_ats > 0:
        # Filter only what was actually measured. Dropping postings that
        # carried no description would silently discard every Apollo result,
        # since that feed returns no JD text at all.
        before = len(matches)
        matches = [m for m in matches
                   if m.ats_percent is None or m.ats_percent >= cfg.min_ats]
        log.info("ATS filter >=%d%%: %d -> %d (unscored postings kept)",
                 cfg.min_ats, before, len(matches))

    if cfg.sort_by_ats and scored:
        # Unscored postings sort last rather than first: absent is not a high
        # score. Ties fall back to the blended ranking.
        matches.sort(key=lambda m: (-(m.ats_percent or -1), -m.total))
    else:
        matches.sort(key=lambda m: -m.total)

    no_jd = sum(1 for m in matches if m.ats_percent is None)
    if resume and no_jd:
        log.warning("%d of %d matches carry no job-description text, so they "
                    "have no ATS score - absent, not zero", no_jd, len(matches))

    stats.update({
        "jobs_raw": raw_count,
        "jobs_unique": len(jobs),
        "matches": len(matches),
        "matches_with_warm_path": sum(1 for m in matches if m.has_warm_path),
        "ats_scored": len(scored),
        "ats_unscored_no_jd": no_jd,
    })
    return matches[: cfg.top_n], stats
