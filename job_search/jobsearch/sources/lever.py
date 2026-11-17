"""Lever public postings API. No auth required."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import JobPosting
from .base import JobSource, http_get_json

ENDPOINT = "https://api.lever.co/v0/postings/{slug}"


class LeverSource(JobSource):
    name = "lever"

    def fetch(self, slug: str, company: str | None = None) -> list[JobPosting]:
        data = http_get_json(ENDPOINT.format(slug=slug), params={"mode": "json"})
        jobs = []
        for j in data if isinstance(data, list) else []:
            posted = None
            if j.get("createdAt"):
                try:
                    posted = datetime.fromtimestamp(j["createdAt"] / 1000, tz=timezone.utc).date()
                except (ValueError, OSError, TypeError):
                    pass
            cats = j.get("categories") or {}
            jobs.append(JobPosting(
                source=self.name,
                company=company or slug,
                title=j.get("text", ""),
                location=cats.get("location", "") or "",
                url=j.get("hostedUrl", ""),
                posted_at=posted,
                description=(j.get("descriptionPlain") or j.get("description") or "")[:4000],
                remote=("remote" in (cats.get("location") or "").lower()),
                external_id=str(j.get("id", "")),
            ))
        return jobs
