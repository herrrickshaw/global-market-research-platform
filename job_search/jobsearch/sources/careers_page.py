"""Generic careers-page scraper.

Deliberately built on schema.org JobPosting JSON-LD rather than per-site CSS
selectors. Most modern ATS-backed careers pages emit JSON-LD for Google Jobs
indexing, so one parser covers many sites and does not break every time a
company reskins its careers page. Sites without JSON-LD fall back to a
heuristic link scrape, which is best-effort by nature.

This is the most fragile source in the tool -- it is opt-in per company via
config, never run across the whole network.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_text

log = logging.getLogger(__name__)

_JOB_LINK_HINT = re.compile(r"/(job|jobs|career|careers|vacanc|position|opening|stelle)", re.I)


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(value) -> str:
    """Flatten a JSON-LD value that may be a string, dict, or list."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "value", "text", "@value"):
            if key in value:
                return _text(value[key])
        return ""
    if isinstance(value, list):
        return ", ".join(filter(None, (_text(v) for v in value)))
    return str(value)


def _location(node: dict) -> str:
    parts = []
    for loc in _as_list(node.get("jobLocation")):
        if not isinstance(loc, dict):
            parts.append(_text(loc))
            continue
        addr = loc.get("address")
        if isinstance(addr, dict):
            parts.append(", ".join(filter(None, [
                _text(addr.get("addressLocality")),
                _text(addr.get("addressRegion")),
                _text(addr.get("addressCountry")),
            ])))
        else:
            parts.append(_text(addr) or _text(loc.get("name")))
    if not parts and node.get("jobLocationType"):
        return "Remote"
    return " | ".join(p for p in parts if p)


def _walk_for_jobpostings(node, out: list[dict]) -> None:
    """Recurse a JSON-LD document collecting every JobPosting node."""
    if isinstance(node, dict):
        types = {t.lower() for t in _as_list(node.get("@type")) if isinstance(t, str)}
        if "jobposting" in types:
            out.append(node)
        for value in node.values():
            _walk_for_jobpostings(value, out)
    elif isinstance(node, list):
        for item in node:
            _walk_for_jobpostings(item, out)


class CareersPageSource(JobSource):
    name = "careers_page"

    def __init__(self, fetcher=None):
        # An optional renderer (see sources/zyte.py). Supplying one is what
        # makes JS-rendered careers sites readable; the parsing below is
        # identical either way, so there is one schema.org implementation.
        self.fetcher = fetcher

    def fetch(self, url: str, company: str | None = None) -> list[JobPosting]:
        if self.fetcher is not None:
            html = self.fetcher.fetch_html(url)
        else:
            html = http_get_text(url)
        jobs = self._from_jsonld(html, url, company)
        if not jobs:
            jobs = self._from_links(html, url, company)
        return jobs

    def _from_jsonld(self, html: str, base_url: str, company: str | None) -> list[JobPosting]:
        nodes: list[dict] = []
        for raw in re.findall(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html, re.S | re.I,
        ):
            try:
                _walk_for_jobpostings(json.loads(raw.strip()), nodes)
            except (ValueError, TypeError):
                continue

        jobs = []
        for n in nodes:
            posted = None
            if n.get("datePosted"):
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                    try:
                        posted = datetime.strptime(_text(n["datePosted"])[:19], fmt).date()
                        break
                    except ValueError:
                        continue
            org = _text((n.get("hiringOrganization") or {})) if isinstance(
                n.get("hiringOrganization"), dict) else _text(n.get("hiringOrganization"))
            desc = re.sub(r"<[^>]+>", " ", _text(n.get("description")))
            jobs.append(JobPosting(
                source=self.name,
                company=company or org or urlparse(base_url).netloc,
                title=_text(n.get("title")),
                location=_location(n),
                url=_text(n.get("url")) or base_url,
                posted_at=posted,
                description=re.sub(r"\s+", " ", desc)[:4000],
                remote="remote" in _location(n).lower(),
            ))
        return [j for j in jobs if j.title]

    def _from_links(self, html: str, base_url: str, company: str | None) -> list[JobPosting]:
        """Fallback: scrape anchors that look like job links. Best-effort only."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            log.warning("beautifulsoup4 not installed; skipping link fallback for %s", base_url)
            return []

        soup = BeautifulSoup(html, "html.parser")
        seen, jobs = set(), []
        for a in soup.find_all("a", href=True):
            href, title = a["href"], a.get_text(strip=True)
            if not title or len(title) < 6 or len(title) > 120:
                continue
            if not _JOB_LINK_HINT.search(href):
                continue
            full = urljoin(base_url, href)
            if full in seen:
                continue
            seen.add(full)
            jobs.append(JobPosting(
                source=self.name + ":links",
                company=company or urlparse(base_url).netloc,
                title=title,
                location="",
                url=full,
            ))
        return jobs
