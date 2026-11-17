"""Jooble and Careerjet - free-key aggregators that actually cover India.

Adzuna is strong in the UK and Germany but thin in India; these two are the
opposite, which is why both are here rather than one. Careerjet in particular
indexes Indian job boards that no ATS-first source reaches.

Neither is a substitute for iimjobs and Naukri, which stay manual-search
territory -- but both widen the free tier well past what Adzuna alone gives.

  Jooble     https://jooble.org/api/about   -> JOOBLE_KEY
  Careerjet  https://www.careerjet.com/partners -> CAREERJET_AFFID
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json, http_post_json

log = logging.getLogger(__name__)

# The key is a path segment, not a query param, so redact() -- which only masks
# query values -- cannot help. The key is therefore never interpolated into any
# string that gets logged or raised; _safe_endpoint() is what error paths use.
JOOBLE = "https://jooble.org/api/{key}"
CAREERJET = "https://public.api.careerjet.net/search"


def _date(raw):
    if not raw:
        return None
    for parse in (
        lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).date(),
        lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        lambda s: datetime.strptime(s, "%Y/%m/%d").date(),
        lambda s: datetime.strptime(s, "%d/%m/%Y").date(),
    ):
        try:
            return parse(str(raw))
        except (ValueError, TypeError):
            continue
    return None


class JoobleSource(JobSource):
    """POST-only JSON API across 60+ countries."""

    name = "jooble"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("JOOBLE_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _safe_endpoint(self) -> str:
        """Never let the key -- a path segment -- reach a log or an exception."""
        return "https://jooble.org/api/***"

    def fetch(self, keywords: str, location: str = "", *, max_pages: int = 2,
              radius: int = 0) -> list[JobPosting]:
        if not self.configured:
            raise SourceError("Jooble credentials missing (JOOBLE_KEY)")
        jobs: list[JobPosting] = []
        for page in range(1, max_pages + 1):
            body = {"keywords": keywords, "location": location, "page": page}
            if radius:
                body["radius"] = radius
            try:
                data = http_post_json(JOOBLE.format(key=self.api_key), body)
            except SourceError as exc:
                # Re-raise without the original message: it embeds the URL,
                # and for Jooble the URL *is* the credential.
                if page == 1:
                    raise SourceError(
                        f"POST {self._safe_endpoint()} failed ({type(exc).__name__})"
                    ) from None
                break
            batch = data.get("jobs") or []
            if not batch:
                break
            for j in batch:
                jobs.append(JobPosting(
                    source=self.name,
                    company=j.get("company") or "",
                    title=j.get("title") or "",
                    location=j.get("location") or "",
                    url=j.get("link") or "",
                    posted_at=_date(j.get("updated")),
                    description=(j.get("snippet") or "")[:4000],
                    external_id=str(j.get("id") or ""),
                ))
        return jobs


class CareerjetSource(JobSource):
    """Locale-scoped search across 80+ countries; strong Indian board coverage."""

    name = "careerjet"

    def __init__(self, affid: str | None = None):
        self.affid = affid or os.getenv("CAREERJET_AFFID", "")

    @property
    def configured(self) -> bool:
        return bool(self.affid)

    def fetch(self, keywords: str, location: str = "", *, locale: str = "en_IN",
              max_pages: int = 2, pagesize: int = 50) -> list[JobPosting]:
        if not self.configured:
            raise SourceError("Careerjet credentials missing (CAREERJET_AFFID)")
        jobs: list[JobPosting] = []
        for page in range(1, max_pages + 1):
            params = {"affid": self.affid, "keywords": keywords,
                      "location": location, "locale_code": locale,
                      "pagesize": pagesize, "page": page,
                      # Required by the API; any stable value is fine and none
                      # of this identifies the user.
                      "user_ip": "127.0.0.1", "user_agent": "job-search-copilot"}
            try:
                data = http_get_json(CAREERJET, params=params)
            except SourceError:
                if page == 1:
                    raise
                break
            if data.get("type") == "ERROR":
                # Careerjet reports a bad affid as a 200 with type=ERROR, which
                # would otherwise read as an empty market.
                if page == 1:
                    raise SourceError(f"careerjet: {data.get('error', 'unknown error')}")
                break
            batch = data.get("jobs") or []
            if not batch:
                break
            for j in batch:
                jobs.append(JobPosting(
                    source=self.name,
                    company=j.get("company") or "",
                    title=j.get("title") or "",
                    location=j.get("locations") or "",
                    url=j.get("url") or "",
                    posted_at=_date(j.get("date")),
                    description=(j.get("description") or "")[:4000],
                    external_id=str(j.get("url") or ""),
                ))
            if len(batch) < pagesize:
                break
        return jobs
