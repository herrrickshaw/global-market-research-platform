"""Ashby public job board API. No auth required."""
from __future__ import annotations

from datetime import datetime

from ..models import JobPosting
from .base import JobSource, http_get_json

ENDPOINT = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


class AshbySource(JobSource):
    name = "ashby"

    def fetch(self, slug: str, company: str | None = None) -> list[JobPosting]:
        data = http_get_json(ENDPOINT.format(slug=slug), params={"includeCompensation": "false"})
        jobs = []
        for j in data.get("jobs", []):
            posted = None
            if j.get("publishedAt"):
                try:
                    posted = datetime.fromisoformat(
                        j["publishedAt"].replace("Z", "+00:00")).date()
                except ValueError:
                    pass
            jobs.append(JobPosting(
                source=self.name,
                company=company or data.get("name") or slug,
                title=j.get("title", ""),
                location=j.get("location", "") or "",
                url=j.get("jobUrl", "") or j.get("applyUrl", ""),
                posted_at=posted,
                description=(j.get("descriptionPlain") or "")[:4000],
                remote=bool(j.get("isRemote")),
                external_id=str(j.get("id", "")),
            ))
        return jobs
