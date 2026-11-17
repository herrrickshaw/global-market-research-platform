"""Three more public ATS feeds, all unauthenticated: SmartRecruiters,
Workable and Personio.

Each is addressed by an opaque per-company slug, exactly like Greenhouse and
Lever, so they join `ATS_SOURCES` and get probed by the existing slug
resolution -- widening how many of the network's employers can be read for free
rather than through a metered aggregator.

Personio is the odd one: its public feed is XML, not JSON, and it is worth
carrying anyway because German and Austrian mid-caps use it heavily, which is
exactly the part of Europe the JSON-first sources cover worst.
"""
from __future__ import annotations

import logging
from datetime import datetime
from xml.etree import ElementTree

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json, http_get_text

log = logging.getLogger(__name__)

SMARTRECRUITERS = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
WORKABLE = "https://apply.workable.com/api/v1/widget/accounts/{slug}"
PERSONIO = "https://{slug}.jobs.personio.de/xml"

SR_PAGE = 100


def _iso_date(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        return None


class SmartRecruitersSource(JobSource):
    """Public Postings API. No auth when the customer has enabled it."""

    name = "smartrecruiters"

    def fetch(self, slug: str, company: str | None = None,
              max_pages: int = 5) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for page in range(max_pages):
            params = {"limit": SR_PAGE, "offset": page * SR_PAGE}
            try:
                data = http_get_json(SMARTRECRUITERS.format(slug=slug), params=params)
            except SourceError:
                if page == 0:
                    raise
                break
            batch = data.get("content") or []
            if not batch:
                break
            for j in batch:
                loc = j.get("location") or {}
                jobs.append(JobPosting(
                    source=self.name,
                    company=company or (j.get("company") or {}).get("name") or slug,
                    title=j.get("name") or "",
                    location=", ".join(
                        p for p in (loc.get("city"), loc.get("region"),
                                    loc.get("country")) if p),
                    # The API's own `ref` is the posting JSON, not a page a
                    # human can apply on; build the careers URL instead.
                    url=f"https://careers.smartrecruiters.com/{slug}/{j.get('id', '')}",
                    posted_at=_iso_date(j.get("releasedDate")),
                    remote=bool(loc.get("remote")),
                    external_id=str(j.get("id") or ""),
                ))
            if len(batch) < SR_PAGE:
                break
        return jobs


class WorkableSource(JobSource):
    """Public careers widget. `details=true` inlines the description."""

    name = "workable"

    def fetch(self, slug: str, company: str | None = None) -> list[JobPosting]:
        data = http_get_json(WORKABLE.format(slug=slug), params={"details": "true"})
        name = (data.get("name") if isinstance(data, dict) else None) or slug
        jobs = []
        for j in (data.get("jobs") or []) if isinstance(data, dict) else []:
            jobs.append(JobPosting(
                source=self.name,
                company=company or name,
                title=j.get("title") or "",
                location=", ".join(
                    p for p in (j.get("city"), j.get("state"), j.get("country")) if p),
                url=j.get("url") or j.get("application_url") or "",
                posted_at=_iso_date(j.get("published_on") or j.get("created_at")),
                description=(j.get("description") or "")[:4000],
                remote=bool(j.get("telecommuting")),
                external_id=str(j.get("shortcode") or j.get("id") or ""),
            ))
        return jobs


class PersonioSource(JobSource):
    """Public XML feed. Heavy in the German-speaking mid-market."""

    name = "personio"

    def fetch(self, slug: str, company: str | None = None,
              language: str = "en") -> list[JobPosting]:
        text = http_get_text(PERSONIO.format(slug=slug), params={"language": language})
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as exc:
            raise SourceError(f"personio/{slug}: non-XML response: {exc}") from exc

        # Parsing successfully is not the same as getting a jobs feed. An HTML
        # error page is often well-formed XML, so it parses, contains no
        # <position>, and returns [] -- indistinguishable from a company with
        # nothing open. Check the root element actually is the feed.
        positions = list(root.iter("position"))
        if not positions and root.tag.lower() not in ("workzag-jobs", "jobs"):
            raise SourceError(
                f"personio/{slug}: expected a jobs feed, got <{root.tag}> "
                f"(likely an error page, not an empty board)")

        jobs = []
        for pos in positions:
            def field(tag: str) -> str:
                el = pos.find(tag)
                return (el.text or "").strip() if el is not None and el.text else ""

            job_id = field("id")
            jobs.append(JobPosting(
                source=self.name,
                company=company or slug,
                title=field("name"),
                location=", ".join(p for p in (field("office"), field("subcompany")) if p),
                url=f"https://{slug}.jobs.personio.de/job/{job_id}" if job_id else "",
                posted_at=_iso_date(field("createdAt")),
                description=field("jobDescriptions")[:4000],
                external_id=job_id,
            ))
        return jobs
