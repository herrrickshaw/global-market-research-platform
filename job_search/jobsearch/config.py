"""YAML config loading with sane defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .profile import DEFAULT_PROFILE, TargetProfile


@dataclass
class Config:
    connections_files: list[str] = field(default_factory=list)
    profile: TargetProfile = field(default_factory=lambda: DEFAULT_PROFILE)
    enable_arbeitnow: bool = True
    enable_remotive: bool = True
    enable_adzuna: bool = False
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_countries: list[str] = field(default_factory=lambda: ["de", "gb", "in"])
    adzuna_queries: list[str] = field(default_factory=lambda: [
        "business development", "investment", "strategy", "partnerships"])
    # --- RapidAPI family (JSearch, LinkedIn feeds, Active-ATS, Indeed) and
    # SerpApi Google Jobs. One RapidAPI key unlocks every rapidapi host.
    rapidapi_key: str = ""
    serpapi_key: str = ""
    # JSearch is sold through RapidAPI and through OpenWebNinja direct. When
    # both keys are present the direct one wins: it is the cheaper front door
    # for the same index, so there is no reason to spend a RapidAPI call on it.
    openwebninja_key: str = ""
    enable_jsearch: bool = False
    enable_linkedin: bool = False
    enable_active_ats: bool = False
    enable_google_jobs: bool = False
    enable_indeed: bool = False
    # Titles to search; locations come from the profile's target countries.
    portal_queries: list[str] = field(default_factory=lambda: [
        "business development manager", "strategy consultant",
        "market intelligence", "energy analyst", "partnerships director"])
    portal_locations: list[str] = field(default_factory=lambda: ["India", "United Kingdom"])
    portal_time_frame: str = "7d"
    portal_days: int = 30
    indeed_top_n: int = 10
    indeed_locality: str = "in"
    # Workday cannot be probed by slug (the host carries a data-centre
    # number), so it is listed per company. Values may be a myworkdayjobs URL
    # or an explicit {tenant, site, wd} mapping; `scan` also auto-discovers
    # tenants from URLs already present in the Apollo dump.
    workday_tenants: dict = field(default_factory=dict)
    workday_autodiscover: bool = True
    # SuccessFactors career sites, keyed by employer. This is where the India
    # arms of the Big Four live -- their parent-company feeds report zero India
    # roles, which is a domain artefact, not an absence of hiring.
    successfactors_sites: dict = field(default_factory=dict)
    # Optional renderer for JS-rendered own-domain careers pages. Never used
    # for the portals in zyte.DENIED_HOSTS -- that list is not configurable.
    zyte_api_key: str = ""
    jooble_key: str = ""
    careerjet_affid: str = ""
    careerjet_locale: str = "en_IN"
    # Resume used for ATS scoring. resume_path wins; otherwise the newest
    # supported file in resume_dir is used.
    resume_path: str = ""
    resume_dir: str = "data/cv"
    min_ats: int = 0          # 0 = report the score, filter nothing
    sort_by_ats: bool = False
    ats_probe_top_n: int = 40
    apollo_dump: str = ""
    apollo_countries: list = field(default_factory=list)
    apollo_days: int = 0
    # Drop postings the source has not re-observed in this many days. 0 keeps
    # everything. This is the only setting that speaks to whether a role is
    # still OPEN rather than merely recent.
    apollo_stale_after: int = 0
    careers_pages: dict = field(default_factory=dict)
    out_dir: str = "out"
    top_n: int = 200


def load_config(path: str | Path | None) -> Config:
    cfg = Config()
    if not path:
        path = "config.yaml"
    p = Path(path)
    if p.exists():
        import yaml
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for key in ("connections_files", "out_dir", "top_n", "ats_probe_top_n",
                    "careers_pages", "apollo_dump", "workday_tenants",
                    "workday_autodiscover", "successfactors_sites",
                    "resume_path", "resume_dir",
                    "min_ats", "sort_by_ats", "apollo_countries", "apollo_days",
                    "apollo_stale_after"):
            if key in raw:
                setattr(cfg, key, raw[key])
        src = raw.get("sources", {}) or {}
        cfg.enable_arbeitnow = src.get("arbeitnow", cfg.enable_arbeitnow)
        cfg.enable_remotive = src.get("remotive", cfg.enable_remotive)
        adz = src.get("adzuna", {}) or {}
        if adz:
            cfg.enable_adzuna = bool(adz.get("enabled", False))
            cfg.adzuna_app_id = adz.get("app_id", "")
            cfg.adzuna_app_key = adz.get("app_key", "")
            cfg.adzuna_countries = adz.get("countries", cfg.adzuna_countries)
            cfg.adzuna_queries = adz.get("queries", cfg.adzuna_queries)
        rapid = src.get("rapidapi", {}) or {}
        if rapid:
            cfg.rapidapi_key = rapid.get("api_key", "")
            cfg.enable_jsearch = bool(rapid.get("jsearch", False))
            cfg.enable_linkedin = bool(rapid.get("linkedin", False))
            cfg.enable_active_ats = bool(rapid.get("active_ats", False))
            cfg.enable_indeed = bool(rapid.get("indeed", False))
            cfg.portal_queries = rapid.get("queries", cfg.portal_queries)
            cfg.portal_locations = rapid.get("locations", cfg.portal_locations)
            cfg.portal_time_frame = rapid.get("time_frame", cfg.portal_time_frame)
            cfg.portal_days = rapid.get("days", cfg.portal_days)
            cfg.indeed_top_n = rapid.get("indeed_top_n", cfg.indeed_top_n)
            cfg.indeed_locality = rapid.get("indeed_locality", cfg.indeed_locality)
        zyt = src.get("zyte", {}) or {}
        if zyt:
            cfg.zyte_api_key = zyt.get("api_key", "")
        joo = src.get("jooble", {}) or {}
        if joo:
            cfg.jooble_key = joo.get("api_key", "")
        cjt = src.get("careerjet", {}) or {}
        if cjt:
            cfg.careerjet_affid = cjt.get("affid", "")
            cfg.careerjet_locale = cjt.get("locale", cfg.careerjet_locale)
        own = src.get("openwebninja", {}) or {}
        if own:
            cfg.openwebninja_key = own.get("api_key", "")
        serp = src.get("serpapi", {}) or {}
        if serp:
            cfg.serpapi_key = serp.get("api_key", "")
            cfg.enable_google_jobs = bool(serp.get("enabled", False))
            cfg.portal_queries = serp.get("queries", cfg.portal_queries)
            cfg.portal_locations = serp.get("locations", cfg.portal_locations)
        prof = raw.get("profile", {}) or {}
        if prof:
            base = TargetProfile()
            for key in ("title_keywords", "sector_keywords", "seniority_keywords",
                        "exclude_keywords", "locations", "remote_ok", "min_score"):
                if key in prof:
                    setattr(base, key, prof[key])
            cfg.profile = base

    # A key in the environment is enough to turn a source on -- same rule the
    # Adzuna block below already follows, so `RAPIDAPI_KEY=... python cli.py
    # scan` works with no config edit.
    cfg.rapidapi_key = cfg.rapidapi_key or os.getenv("RAPIDAPI_KEY", "")
    if cfg.rapidapi_key and not any((cfg.enable_jsearch, cfg.enable_linkedin,
                                     cfg.enable_active_ats, cfg.enable_indeed)):
        cfg.enable_jsearch = cfg.enable_linkedin = cfg.enable_active_ats = True
    cfg.openwebninja_key = cfg.openwebninja_key or os.getenv("OPENWEBNINJA_KEY", "")
    if cfg.openwebninja_key:
        cfg.enable_jsearch = True
    cfg.serpapi_key = cfg.serpapi_key or os.getenv("SERPAPI_KEY", "")
    if cfg.serpapi_key:
        cfg.enable_google_jobs = True
    cfg.zyte_api_key = cfg.zyte_api_key or os.getenv("ZYTE_API_KEY", "")
    cfg.jooble_key = cfg.jooble_key or os.getenv("JOOBLE_KEY", "")
    cfg.careerjet_affid = cfg.careerjet_affid or os.getenv("CAREERJET_AFFID", "")
    cfg.adzuna_app_id = cfg.adzuna_app_id or os.getenv("ADZUNA_APP_ID", "")
    cfg.adzuna_app_key = cfg.adzuna_app_key or os.getenv("ADZUNA_APP_KEY", "")
    if cfg.adzuna_app_id and cfg.adzuna_app_key:
        cfg.enable_adzuna = True
    return cfg
