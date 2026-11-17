"""Greenhouse public job board API. No auth required."""
from __future__ import annotations

import logging
from datetime import datetime

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json

log = logging.getLogger(__name__)
ENDPOINT = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseSource(JobSource):
    name = "greenhouse"

    def fetch(self, slug: str, company: str | None = None) -> list[JobPosting]:
        data = http_get_json(ENDPOINT.format(slug=slug), params={"content": "true"})
        jobs = []
        for j in data.get("jobs", []):
            posted = None
            raw = j.get("updated_at") or j.get("first_published")
            if raw:
                try:
                    posted = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
                except ValueError:
                    pass
            jobs.append(JobPosting(
                source=self.name,
                company=company or slug,
                title=j.get("title", ""),
                location=(j.get("location") or {}).get("name", ""),
                url=j.get("absolute_url", ""),
                posted_at=posted,
                description=(j.get("content") or "")[:4000],
                external_id=str(j.get("id", "")),
            ))
        return jobs
