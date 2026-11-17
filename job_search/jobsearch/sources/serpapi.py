"""SerpApi Google Jobs - Google's job index, which carries the Indian portals.

Worth having alongside JSearch because Google indexes iimjobs, Naukri, Foundit
and Hirist, which JSearch's US-centric board set largely misses. For a senior
India search that gap matters: those portals carry roles that never reach a
company ATS at all.

Key: https://serpapi.com/manage-api-key -> config.yaml under sources.serpapi,
or SERPAPI_KEY in the environment. Auth is by query string, so every URL goes
through redact() before it can reach a log or an exception.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json

log = logging.getLogger(__name__)

ENDPOINT = "https://serpapi.com/search"
RESULTS_PER_PAGE = 10

# Google's date filter, passed through the `chips` parameter.
_CHIPS = {1: "date_posted:today", 3: "date_posted:3days",
          7: "date_posted:week", 31: "date_posted:month"}

_RELATIVE = re.compile(r"(\d+)\s*(hour|day|week|month)s?\s*ago", re.I)
_UNIT_DAYS = {"hour": 0, "day": 1, "week": 7, "month": 30}


def _chip(days: int | None) -> str:
    """Coarsest Google bucket that still covers `days`; '' means unfiltered."""
    if not days:
        return ""
    for limit in sorted(_CHIPS):
        if days <= limit:
            return _CHIPS[limit]
    return ""


def parse_relative_date(text: str, today: date | None = None):
    """'3 days ago' -> a date. Google Jobs never gives an absolute timestamp.

    Returns None for anything unrecognised rather than guessing: an invented
    date would feed straight into the freshness component of the score.
    """
    if not text:
        return None
    today = today or date.today()
    m = _RELATIVE.search(text)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    return today - timedelta(days=n * _UNIT_DAYS[unit])


class SerpApiJobsSource(JobSource):
    name = "google_jobs"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SERPAPI_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def fetch(self, query: str, *, location: str = "India", days: int | None = None,
              max_pages: int = 2, today: date | None = None) -> list[JobPosting]:
        if not self.configured:
            raise SourceError("SerpApi credentials missing (SERPAPI_KEY)")
        chips = _chip(days)
        jobs: list[JobPosting] = []
        for page in range(max_pages):
            params = {"engine": "google_jobs", "q": query, "hl": "en",
                      "api_key": self.api_key, "start": page * RESULTS_PER_PAGE}
            if location:
                params["location"] = location
            if chips:
                params["chips"] = chips
            try:
                data = http_get_json(ENDPOINT, params=params)
            except SourceError:
                if page == 0:
                    raise
                break
            if data.get("error"):
                # SerpApi reports a bad key or an exhausted quota as HTTP 200
                # with an error body, so this has to be checked explicitly --
                # otherwise it reads as an empty result set.
                if page == 0:
                    raise SourceError(f"serpapi: {data['error']}")
                break
            batch = data.get("jobs_results") or []
            if not batch:
                break
            for j in batch:
                jobs.append(_to_posting(j, today=today))
        return jobs


def _to_posting(j: dict, today: date | None = None) -> JobPosting:
    # "via LinkedIn" / "via Naukri.com" -- which portal actually carries it.
    via = re.sub(r"^via\s+", "", (j.get("via") or "").strip(), flags=re.I)
    ext = j.get("detected_extensions") or {}
    apply_options = j.get("apply_options") or []
    url = j.get("share_link") or (apply_options[0].get("link") if apply_options else "")
    return JobPosting(
        source=f"google_jobs:{via}" if via else "google_jobs",
        company=j.get("company_name") or "",
        title=j.get("title") or "",
        location=j.get("location") or "",
        url=url or "",
        posted_at=parse_relative_date(ext.get("posted_at"), today=today),
        description=(j.get("description") or "")[:4000],
        remote=bool(ext.get("work_from_home")),
        external_id=str(j.get("job_id") or ""),
    )
