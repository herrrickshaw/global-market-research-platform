"""Arbeitnow open job board feed. Free, no auth. Strong Germany/EU coverage."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json

ENDPOINT = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowSource(JobSource):
    name = "arbeitnow"

    def fetch(self, max_pages: int = 5) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for page in range(1, max_pages + 1):
            try:
                data = http_get_json(ENDPOINT, params={"page": page})
            except SourceError:
                break
            batch = data.get("data", [])
            if not batch:
                break
            for j in batch:
                posted = None
                if j.get("created_at"):
                    try:
                        posted = datetime.fromtimestamp(
                            int(j["created_at"]), tz=timezone.utc).date()
                    except (ValueError, OSError, TypeError):
                        pass
                jobs.append(JobPosting(
                    source=self.name,
                    company=j.get("company_name", ""),
                    title=j.get("title", ""),
                    location=j.get("location", "") or "",
                    url=j.get("url", ""),
                    posted_at=posted,
                    description=(j.get("description") or "")[:4000],
                    remote=bool(j.get("remote")),
                    external_id=str(j.get("slug", "")),
                ))
        return jobs
