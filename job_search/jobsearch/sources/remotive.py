"""Remotive remote-jobs API. Free, no auth."""
from __future__ import annotations

from datetime import datetime

from ..models import JobPosting
from .base import JobSource, http_get_json

ENDPOINT = "https://remotive.com/api/remote-jobs"


class RemotiveSource(JobSource):
    name = "remotive"

    def fetch(self, search: str | None = None, limit: int = 500) -> list[JobPosting]:
        params: dict = {"limit": limit}
        if search:
            params["search"] = search
        data = http_get_json(ENDPOINT, params=params)
        jobs = []
        for j in data.get("jobs", []):
            posted = None
            raw = j.get("publication_date")
            if raw:
                try:
                    posted = datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
                except ValueError:
                    pass
            jobs.append(JobPosting(
                source=self.name,
                company=j.get("company_name", ""),
                title=j.get("title", ""),
                location=j.get("candidate_required_location", "") or "Remote",
                url=j.get("url", ""),
                posted_at=posted,
                description=(j.get("description") or "")[:4000],
                remote=True,
                external_id=str(j.get("id", "")),
            ))
        return jobs
