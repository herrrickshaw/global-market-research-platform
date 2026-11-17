"""Resolve a company name to an ATS board slug.

Greenhouse/Lever/Ashby boards are addressed by an opaque slug that is usually a
squashed form of the company name ('siemens energy' -> 'siemensenergy'). There
is no lookup API, so we generate candidate slugs and probe. Results are cached
to disk because a miss costs a round trip and slugs rarely change.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from .sources import ATS_SOURCES
from .sources.base import SourceError

log = logging.getLogger(__name__)


def candidate_slugs(company: str) -> list[str]:
    """Generate plausible board slugs for a company name, best guess first."""
    base = re.sub(r"[^a-z0-9\s]", "", (company or "").lower()).strip()
    if not base:
        return []
    words = base.split()
    out = [
        "".join(words),           # siemensenergy
        "-".join(words),          # siemens-energy
        words[0],                 # siemens
    ]
    if len(words) > 1:
        out.append("".join(w[0] for w in words))   # se
    seen, uniq = set(), []
    for s in out:
        if s and s not in seen and len(s) > 1:
            seen.add(s)
            uniq.append(s)
    return uniq


class SlugCache:
    def __init__(self, path: str | Path = "data/slug_cache.json"):
        self.path = Path(path)
        self._data: dict = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except ValueError:
                log.warning("corrupt slug cache at %s, starting fresh", self.path)

    def get(self, company: str):
        return self._data.get(company.lower())

    def put(self, company: str, value) -> None:
        self._data[company.lower()] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, sort_keys=True))


def resolve_board(company: str, cache: SlugCache | None = None) -> tuple[str, str] | None:
    """Probe ATS providers for a live board. Returns (provider, slug) or None."""
    if cache is not None:
        cached = cache.get(company)
        if cached is not None:
            return tuple(cached) if cached else None

    result = None
    for slug in candidate_slugs(company):
        for provider, cls in ATS_SOURCES.items():
            try:
                jobs = cls().fetch(slug, company=company)
            except SourceError:
                continue
            except Exception as exc:
                log.debug("probe %s/%s failed: %s", provider, slug, exc)
                continue
            if jobs:
                result = (provider, slug)
                break
        if result:
            break

    if cache is not None:
        cache.put(company, list(result) if result else [])
    return result
