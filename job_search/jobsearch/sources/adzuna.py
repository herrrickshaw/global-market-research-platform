"""Adzuna aggregator API. Free tier; needs app_id + app_key.

Register at https://developer.adzuna.com/ and put the credentials in
config.yaml under sources.adzuna, or set ADZUNA_APP_ID / ADZUNA_APP_KEY.
"""
from __future__ import annotations

import os
from datetime import datetime

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json

ENDPOINT = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


class AdzunaSource(JobSource):
    name = "adzuna"

    def __init__(self, app_id: str | None = None, app_key: str | None = None):
        self.app_id = app_id or os.getenv("ADZUNA_APP_ID", "")
        self.app_key = app_key or os.getenv("ADZUNA_APP_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_key)

    def fetch(self, country: str = "de", what: str = "business development",
              where: str = "", max_pages: int = 3,
              results_per_page: int = 50) -> list[JobPosting]:
        if not self.configured:
            raise SourceError("Adzuna credentials missing (ADZUNA_APP_ID / ADZUNA_APP_KEY)")
        jobs: list[JobPosting] = []
        for page in range(1, max_pages + 1):
            params = {
                "app_id": self.app_id, "app_key": self.app_key,
                "results_per_page": results_per_page, "what": what,
                "content-type": "application/json",
            }
            if where:
                params["where"] = where
            try:
                data = http_get_json(ENDPOINT.format(country=country, page=page), params=params)
            except SourceError:
                # A failure on page 1 means the source is unreachable or the
                # credentials are bad -- propagate it. Returning [] here would
                # make a blocked host indistinguishable from "no matching jobs",
                # which silently understates coverage in every report.
                if page == 1:
                    raise
                break
            batch = data.get("results", [])
            if not batch:
                break
            for j in batch:
                posted = None
                if j.get("created"):
                    try:
                        posted = datetime.fromisoformat(
                            j["created"].replace("Z", "+00:00")).date()
                    except ValueError:
                        pass
                jobs.append(JobPosting(
                    source=self.name,
                    company=(j.get("company") or {}).get("display_name", ""),
                    title=j.get("title", ""),
                    location=(j.get("location") or {}).get("display_name", ""),
                    url=j.get("redirect_url", ""),
                    posted_at=posted,
                    description=(j.get("description") or "")[:4000],
                    external_id=str(j.get("id", "")),
                ))
        return jobs
