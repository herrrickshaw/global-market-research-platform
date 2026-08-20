"""Apollo.io organization job postings.

Two ways in, because Apollo's job-postings endpoint is reachable by different
routes depending on where this runs:

``ApolloSource``
    Direct REST against api.apollo.io using an API key. Use this locally.
    Costs 1 Apollo credit per request.

``ApolloDumpSource``
    Reads postings already fetched and saved to JSON — e.g. pulled through an
    Apollo MCP connection in an environment whose egress policy blocks
    api.apollo.io. Costs nothing and needs no key.

Both yield the same JobPosting shape, so the pipeline cannot tell them apart.

Note on scale: large employers advertise thousands of roles (Siemens Energy
returned 1,817 across 19 pages), and the endpoint sorts by recency rather than
relevance. ``fetch`` therefore pages through and filters as it goes instead of
assuming page 1 contains anything useful.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

from ..models import JobPosting
from .base import JobSource, SourceError, http_get_json

log = logging.getLogger(__name__)

ORG_POSTINGS = "https://api.apollo.io/api/v1/organizations/{id}/job_postings"
ORG_ENRICH = "https://api.apollo.io/api/v1/organizations/enrich"

MAX_PAGES = 20
PER_PAGE = 100


def _parse_date(raw: str | None):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _to_posting(j: dict, company: str, source: str) -> JobPosting:
    location = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
    return JobPosting(
        source=source,
        company=company,
        title=j.get("title", ""),
        location=location,
        url=j.get("url", ""),
        posted_at=_parse_date(j.get("posted_at")),
        external_id=str(j.get("id", "")),
    )


class ApolloSource(JobSource):
    """Live Apollo REST. Requires APOLLO_API_KEY; costs 1 credit per page."""

    name = "apollo"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("APOLLO_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict:
        return {"X-Api-Key": self.api_key, "Content-Type": "application/json"}

    def resolve_org_id(self, domain: str) -> str | None:
        """Enrich a domain to its Apollo organization id. 1 credit if found."""
        if not self.configured:
            raise SourceError("APOLLO_API_KEY not set")
        import requests
        resp = requests.post(ORG_ENRICH, params={"domain": domain},
                             headers=self._headers(), timeout=30)
        if resp.status_code >= 400:
            raise SourceError(f"apollo enrich {domain}: HTTP {resp.status_code}")
        return ((resp.json() or {}).get("organization") or {}).get("id")

    def fetch(self, org_id: str, company: str, max_pages: int = MAX_PAGES) -> list[JobPosting]:
        """Page through a company's postings. 1 credit per page."""
        if not self.configured:
            raise SourceError("APOLLO_API_KEY not set")
        import requests

        jobs: list[JobPosting] = []
        for page in range(1, max_pages + 1):
            resp = requests.get(ORG_POSTINGS.format(id=org_id),
                                params={"page": page, "per_page": PER_PAGE},
                                headers=self._headers(), timeout=30)
            if resp.status_code >= 400:
                raise SourceError(f"apollo postings {company}: HTTP {resp.status_code}")
            data = resp.json() or {}
            batch = data.get("organization_job_postings", [])
            if not batch:
                break
            jobs += [_to_posting(j, company, self.name) for j in batch]

            pg = data.get("pagination") or {}
            if page >= (pg.get("total_pages") or 1):
                break
        log.info("apollo %s: %d postings", company, len(jobs))
        return jobs


class ApolloDumpSource(JobSource):
    """Replay postings saved from an Apollo MCP session. No key, no credits."""

    name = "apollo_dump"

    def fetch(self, path: str | Path = "data/apollo_postings.json") -> list[JobPosting]:
        p = Path(path)
        if not p.exists():
            raise SourceError(f"no Apollo dump at {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SourceError(f"corrupt Apollo dump {p}: {exc}") from exc

        jobs: list[JobPosting] = []
        for company, payload in data.items():
            if company.startswith("_") or not isinstance(payload, dict):
                continue
            for j in payload.get("jobs", []):
                jobs.append(_to_posting(j, company, self.name))
            if payload.get("_caveat"):
                # Surface partial coverage rather than letting it read as complete.
                log.warning("%s: %s", company, payload["_caveat"])
        return jobs
