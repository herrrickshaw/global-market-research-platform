"""RapidAPI job feeds: LinkedIn and Indeed postings, plus a broad ATS index.

Four hosts, one auth scheme, near-identical response shapes:

  linkedin-job-search-api.p.rapidapi.com   LinkedIn postings + a count endpoint
                                           (cheap way to size a query before
                                           spending calls listing it)
  linkedin-jobs-api2.p.rapidapi.com        sibling LinkedIn feed; picks the
                                           window by path, not by query param
  active-jobs-db.p.rapidapi.com            postings read off company ATSes
                                           across many employers
  indeed12.p.rapidapi.com                  Indeed, scoped to one employer

This is the sanctioned way to read LinkedIn and Indeed postings. Neither offers
a jobs API to an individual developer and both forbid scraping; these feeds
license an aggregated index instead, so the postings arrive without touching
the account you are job-hunting with.

Key: https://rapidapi.com/ -> config.yaml under sources.rapidapi, or
RAPIDAPI_KEY in the environment. Auth is by header, so the key never enters a
URL and cannot reach a log.

FIELD MAPPING IS DEFENSIVE ON PURPOSE. These feeds have shipped several key
namings for the same value (`organization` vs `company_name`, `date_posted` vs
`datePosted`, locations as a string, a list, or a list of dicts), and a response
may arrive as a bare list or wrapped in `data`/`jobs`. Rather than pin one
shape and return silent blanks when it changes, every field is read through a
list of accepted names and `_unmapped()` reports keys we did not recognise, so
a schema drift shows up as a log line instead of an empty column.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json

log = logging.getLogger(__name__)

LINKEDIN_HOST = "linkedin-job-search-api.p.rapidapi.com"
ACTIVE_ATS_HOST = "active-jobs-db.p.rapidapi.com"
LINKEDIN_ALT_HOST = "linkedin-jobs-api2.p.rapidapi.com"
INDEED_HOST = "indeed12.p.rapidapi.com"

# Accepted by both hosts; anything else is rejected upstream and comes back as
# an empty list, which would otherwise read as "nothing is hiring".
TIME_FRAMES = ("1h", "24h", "7d", "30d")

_TITLE_KEYS = ("title", "job_title", "name")
_COMPANY_KEYS = ("organization", "company", "company_name", "employer_name",
                 "organization_name")
_URL_KEYS = ("url", "job_url", "apply_url", "link", "organization_url")
_DATE_KEYS = ("date_posted", "datePosted", "posted_at", "date_created",
              "published_at")
_DESC_KEYS = ("description_text", "description", "job_description", "text")
_ID_KEYS = ("id", "job_id", "external_id", "ats_job_id")
_LOC_KEYS = ("locations_derived", "locations_raw", "location", "locations",
             "cities_derived", "job_location")
_REMOTE_KEYS = ("remote_derived", "is_remote", "remote", "job_is_remote")

_KNOWN = set(_TITLE_KEYS + _COMPANY_KEYS + _URL_KEYS + _DATE_KEYS + _DESC_KEYS
             + _ID_KEYS + _LOC_KEYS + _REMOTE_KEYS)


def _first(row: dict, keys: tuple[str, ...], default=""):
    for k in keys:
        v = row.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _as_location(value) -> str:
    """Locations arrive as a string, a list of strings, or a list of dicts."""
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [value.get(k) for k in ("city", "region", "state", "country")]
        return ", ".join(p for p in parts if p)
    if isinstance(value, (list, tuple)):
        return "; ".join(filter(None, (_as_location(v) for v in value)))
    return str(value)


def _as_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _rows(payload) -> list[dict]:
    """Unwrap a bare list, or a {data|jobs|results: [...]} envelope."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("data", "jobs", "results"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
    return []


def _unmapped(row: dict) -> set[str]:
    return {k for k in row if k not in _KNOWN}


def to_posting(row: dict, source: str) -> JobPosting:
    return JobPosting(
        source=source,
        company=str(_first(row, _COMPANY_KEYS)),
        title=str(_first(row, _TITLE_KEYS)),
        location=_as_location(_first(row, _LOC_KEYS, default=None)),
        url=str(_first(row, _URL_KEYS)),
        posted_at=_as_date(_first(row, _DATE_KEYS, default=None)),
        description=str(_first(row, _DESC_KEYS))[:4000],
        remote=bool(_first(row, _REMOTE_KEYS, default=False)),
        external_id=str(_first(row, _ID_KEYS)),
    )


class _RapidApiJobSource(JobSource):
    """Shared plumbing. Subclasses set `host`, `path` and `name`."""

    host = ""
    path = ""
    # Some of these hosts select the window by path (`/active-jb-24h`) rather
    # than by query param. Setting this builds the path from `time_frame`; the
    # param is sent as well, which the path-based hosts simply ignore.
    path_from_time_frame = False

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def _headers(self) -> dict:
        return {"x-rapidapi-host": self.host, "x-rapidapi-key": self.api_key,
                "Content-Type": "application/json"}

    def _endpoint(self, path: str) -> str:
        return f"https://{self.host}{path}"

    def fetch(self, *, title: str = "", location: str = "", time_frame: str = "7d",
              limit: int = 50, max_pages: int = 2,
              description_format: str = "text") -> list[JobPosting]:
        if not self.configured:
            raise SourceError(f"{self.name} credentials missing (RAPIDAPI_KEY)")
        if time_frame not in TIME_FRAMES:
            raise SourceError(
                f"time_frame must be one of {list(TIME_FRAMES)}, got {time_frame!r}")

        path = f"/active-jb-{time_frame}" if self.path_from_time_frame else self.path
        jobs: list[JobPosting] = []
        drift_reported = False
        for page in range(max_pages):
            params = {"time_frame": time_frame, "limit": limit,
                      "offset": page * limit,
                      "description_format": description_format}
            if title:
                params["title"] = title
            if location:
                params["location"] = location
            try:
                payload = http_get_json(self._endpoint(path),
                                        params=params, headers=self._headers)
            except SourceError:
                # A page-1 failure is a blocked host, a bad key or an exhausted
                # quota. Returning [] would make it indistinguishable from
                # "no matching roles" and silently understate coverage.
                if page == 0:
                    raise
                break
            batch = _rows(payload)
            if not batch:
                break
            if not drift_reported:
                extra = _unmapped(batch[0])
                if extra:
                    log.info("%s: unmapped response fields %s",
                             self.name, sorted(extra)[:12])
                    drift_reported = True
            jobs += [to_posting(r, self.name) for r in batch]
            if len(batch) < limit:
                break
        return jobs


class LinkedInJobSearchSource(_RapidApiJobSource):
    """LinkedIn postings, licensed through RapidAPI rather than scraped.

    The listing endpoints on this family encode the window in the path, so the
    path has to be built from `time_frame`. Pinning it to `/active-jb-7d` and
    passing `time_frame=30d` as a param looks like it works -- the request
    succeeds -- but returns seven days of postings for a thirty-day question,
    with nothing in the output saying so. If a host does not offer the window
    asked for, a 404 from the unknown path is the better outcome: a loud
    failure beats quietly truncated coverage.
    """

    name = "linkedin"
    host = LINKEDIN_HOST
    path_from_time_frame = True

    def count(self, *, title: str = "", location: str = "",
              time_frame: str = "24h") -> int:
        """How many postings a query would return, without listing them.

        One call instead of paging, so a query can be sized before spending
        the call budget on it.
        """
        if not self.configured:
            raise SourceError("linkedin credentials missing (RAPIDAPI_KEY)")
        if time_frame not in TIME_FRAMES:
            raise SourceError(
                f"time_frame must be one of {list(TIME_FRAMES)}, got {time_frame!r}")
        params = {"time_frame": time_frame}
        if title:
            params["title"] = title
        if location:
            params["location"] = location
        payload = http_get_json(self._endpoint("/active-jb-count"),
                                params=params, headers=self._headers)
        if isinstance(payload, dict):
            for key in ("count", "total", "total_count", "results"):
                if isinstance(payload.get(key), int):
                    return payload[key]
        if isinstance(payload, int):
            return payload
        raise SourceError(f"linkedin count: unrecognised response {type(payload).__name__}")


class LinkedInJobsApi2Source(LinkedInJobSearchSource):
    """Second LinkedIn feed on a sibling host; selects the window by path."""

    name = "linkedin2"
    host = LINKEDIN_ALT_HOST
    path_from_time_frame = True


class ActiveJobsDBSource(_RapidApiJobSource):
    """Postings read straight off company ATSes, across many employers."""

    name = "active_ats"
    host = ACTIVE_ATS_HOST
    path = "/active-ats"


class Indeed12Source(_RapidApiJobSource):
    """Indeed, scoped to one employer at a time.

    This one is company-keyed rather than query-keyed, which suits this tool
    better than it looks: the network index already ranks employers by how many
    connections sit inside them, so the natural call pattern is to walk the top
    companies and ask Indeed what each is advertising -- exactly the join the
    scan is built around.
    """

    name = "indeed"
    host = INDEED_HOST

    def fetch(self, *, company: str = "", locality: str = "in",
              max_pages: int = 2, **_ignored) -> list[JobPosting]:
        if not self.configured:
            raise SourceError("indeed credentials missing (RAPIDAPI_KEY)")
        if not company:
            raise SourceError("Indeed12 is company-scoped; pass company=")

        jobs: list[JobPosting] = []
        for page in range(1, max_pages + 1):
            # Indeed's own slug: spaces become hyphens, and the path segment is
            # already URL-encoded by requests.
            slug = company.strip().replace(" ", "-")
            try:
                payload = http_get_json(
                    self._endpoint(f"/company/{slug}/jobs"),
                    params={"locality": locality, "start": page},
                    headers=self._headers)
            except SourceError:
                if page == 1:
                    raise
                break
            batch = _rows(payload)
            if not batch:
                break
            for row in batch:
                posting = to_posting(row, self.name)
                # The company-scoped endpoint does not repeat the employer on
                # each row; without this every match would join to a blank
                # company and score zero network strength.
                if not posting.company:
                    posting.company = company
                jobs.append(posting)
        return jobs
