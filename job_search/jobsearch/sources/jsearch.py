"""JSearch - one query across LinkedIn, Indeed, Glassdoor and ZipRecruiter.

This is the sanctioned way to read LinkedIn postings. LinkedIn itself offers no
jobs API to an individual developer and forbids scraping; JSearch licenses an
aggregated index instead, so the postings arrive without touching the account
you are job-hunting with.

Two front doors sell the same index, and this adapter speaks both:

  backend="rapidapi"      jsearch.p.rapidapi.com/search      RAPIDAPI_KEY
  backend="openwebninja"  api.openwebninja.com/jsearch/...   OPENWEBNINJA_KEY

Either key goes in config.yaml under sources.jsearch, or in the environment.
Auth is by header in both cases, so the key never enters a URL.

Each posting records which portal it came from (`source: "jsearch:LinkedIn"`),
so a report can show how much of the coverage is LinkedIn versus elsewhere.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json

log = logging.getLogger(__name__)

HOST = "jsearch.p.rapidapi.com"
ENDPOINT = f"https://{HOST}/search"

# JSearch is sold through two front doors with the same response envelope:
# RapidAPI (key in X-RapidAPI-Key) and OpenWebNinja direct (key in X-API-Key,
# and the path is /jsearch/search-v2). One adapter serves both; only the
# endpoint and the auth header differ.
OWN_ENDPOINT = "https://api.openwebninja.com/jsearch/search-v2"
BACKENDS = ("rapidapi", "openwebninja")

# JSearch accepts only this fixed vocabulary; anything else is a silent no-op
# on their side, which would look like "no recent jobs" here.
DATE_POSTED = {"all", "today", "3days", "week", "month"}


def _window(days: int | None) -> str:
    """Map a day count onto the coarsest JSearch bucket that still covers it."""
    if not days:
        return "all"
    if days <= 1:
        return "today"
    if days <= 3:
        return "3days"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    return "all"


# JSearch's `country` is the Google domain it queries, not a filter applied to
# the results -- google.co.in answers "strategy consultant in Germany" with
# India-weighted listings and no error. Leaving it at the default therefore
# does not widen a search, it quietly redirects one: every European query in a
# 7-country run was being asked of India's index.
_COUNTRY_BY_PLACE = {
    "india": "in", "chennai": "in", "bengaluru": "in", "bangalore": "in",
    "delhi": "in", "new delhi": "in", "gurgaon": "in", "gurugram": "in",
    "mumbai": "in", "hyderabad": "in", "pune": "in", "noida": "in",
    "kolkata": "in", "ahmedabad": "in",
    "united kingdom": "gb", "uk": "gb", "england": "gb", "london": "gb",
    "scotland": "gb", "aberdeen": "gb", "manchester": "gb",
    "germany": "de", "berlin": "de", "munich": "de", "hamburg": "de",
    "frankfurt": "de", "duesseldorf": "de", "dusseldorf": "de", "essen": "de",
    "netherlands": "nl", "amsterdam": "nl", "rotterdam": "nl",
    "the hague": "nl", "den haag": "nl", "utrecht": "nl",
    "france": "fr", "paris": "fr", "spain": "es", "madrid": "es",
    "barcelona": "es", "italy": "it", "milan": "it", "rome": "it",
    "switzerland": "ch", "zurich": "ch", "geneva": "ch", "basel": "ch",
    "belgium": "be", "brussels": "be", "antwerp": "be",
    "denmark": "dk", "copenhagen": "dk", "odense": "dk",
    "sweden": "se", "stockholm": "se", "gothenburg": "se",
    "norway": "no", "oslo": "no", "stavanger": "no",
    "finland": "fi", "helsinki": "fi", "ireland": "ie", "dublin": "ie",
    "poland": "pl", "warsaw": "pl", "austria": "at", "vienna": "at",
    "portugal": "pt", "lisbon": "pt", "czechia": "cz", "prague": "cz",
}

DEFAULT_COUNTRY = "in"


def country_code(location: str, default: str = DEFAULT_COUNTRY) -> str:
    """Best-guess ISO country for a location string, `default` when unknown.

    Substring matching is deliberate and ordered longest-first: "Rotterdam,
    Netherlands" must resolve on the country, not on whichever city happens to
    be checked first.
    """
    text = (location or "").strip().lower()
    if not text:
        return default
    if text in _COUNTRY_BY_PLACE:
        return _COUNTRY_BY_PLACE[text]
    for place in sorted(_COUNTRY_BY_PLACE, key=len, reverse=True):
        if place in text:
            return _COUNTRY_BY_PLACE[place]
    return default


class JSearchSource(JobSource):
    name = "jsearch"

    def __init__(self, api_key: str | None = None, backend: str = "rapidapi"):
        if backend not in BACKENDS:
            raise ValueError(f"backend must be one of {list(BACKENDS)}, got {backend!r}")
        self.backend = backend
        env = "OPENWEBNINJA_KEY" if backend == "openwebninja" else "RAPIDAPI_KEY"
        self.api_key = api_key or os.getenv(env, "")
        self._env = env

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    @property
    def endpoint(self) -> str:
        return OWN_ENDPOINT if self.backend == "openwebninja" else ENDPOINT

    @property
    def _headers(self) -> dict:
        if self.backend == "openwebninja":
            return {"X-API-Key": self.api_key}
        return {"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": HOST}

    def fetch(self, query: str, *, country: str = DEFAULT_COUNTRY, days: int | None = None,
              max_pages: int = 2, date_posted: str | None = None) -> list[JobPosting]:
        """Fetch postings for one query. `query` carries the location too,
        JSearch-style: "business development manager in london"."""
        if not self.configured:
            raise SourceError(f"JSearch credentials missing ({self._env})")
        window = date_posted or _window(days)
        if window not in DATE_POSTED:
            raise SourceError(f"date_posted must be one of {sorted(DATE_POSTED)}, got {window!r}")

        jobs: list[JobPosting] = []
        for page in range(1, max_pages + 1):
            params = {"query": query, "page": page, "num_pages": 1,
                      "country": country, "date_posted": window}
            try:
                data = http_get_json(self.endpoint, params=params,
                                     headers=self._headers)
            except SourceError:
                # Same rule as Adzuna: a page-1 failure means blocked or
                # unauthenticated. Swallowing it would make that state
                # indistinguishable from "this employer isn't hiring".
                if page == 1:
                    raise
                break
            # RapidAPI wraps rows in {"data": [...]}; the direct host has
            # shipped a bare list, so accept either rather than read a shape
            # change as an empty market.
            batch = (data.get("data") if isinstance(data, dict) else data) or []
            if not batch:
                break
            for j in batch:
                jobs.append(_to_posting(j))
        return jobs


def _to_posting(j: dict) -> JobPosting:
    publisher = (j.get("job_publisher") or "").strip()
    location = ", ".join(
        p for p in (j.get("job_city"), j.get("job_state"), j.get("job_country")) if p
    )
    return JobPosting(
        source=f"jsearch:{publisher}" if publisher else "jsearch",
        company=j.get("employer_name") or "",
        title=j.get("job_title") or "",
        location=location,
        url=j.get("job_apply_link") or j.get("job_google_link") or "",
        posted_at=_parse_date(j.get("job_posted_at_datetime_utc")),
        description=(j.get("job_description") or "")[:4000],
        remote=bool(j.get("job_is_remote")),
        external_id=str(j.get("job_id") or ""),
    )


def _parse_date(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        return None
