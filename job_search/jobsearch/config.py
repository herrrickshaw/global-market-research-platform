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
    ats_probe_top_n: int = 40
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
        for key in ("connections_files", "out_dir", "top_n", "ats_probe_top_n", "careers_pages"):
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
        prof = raw.get("profile", {}) or {}
        if prof:
            base = TargetProfile()
            for key in ("title_keywords", "sector_keywords", "seniority_keywords",
                        "exclude_keywords", "locations", "remote_ok", "min_score"):
                if key in prof:
                    setattr(base, key, prof[key])
            cfg.profile = base

    cfg.adzuna_app_id = cfg.adzuna_app_id or os.getenv("ADZUNA_APP_ID", "")
    cfg.adzuna_app_key = cfg.adzuna_app_key or os.getenv("ADZUNA_APP_KEY", "")
    if cfg.adzuna_app_id and cfg.adzuna_app_key:
        cfg.enable_adzuna = True
    return cfg
