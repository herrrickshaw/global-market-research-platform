"""Workday's public job feed - the one that matters most for this search.

Checked against the postings already on file: **Shell** (`shell.wd3`) and
**Wood Mackenzie** (`woodmac.wd3`) both run on Workday. Reading it directly
replaces metered Apollo pages with a free, complete feed -- no per-page credit,
and no "the older half of the window is uncovered" caveat, because pagination
here runs to an explicit `total`. Shell was the employer whose window needed
five extra credit-charged pages to close; this closes it for nothing.

Not every large employer is here: the same check found Siemens Energy on
`jobs.siemens-energy.com`, S&P Global on `careers.spglobal.com` and
TotalEnergies on `jobs.totalenergies.com` -- own-domain career sites, not
Workday. Assume nothing about an employer's ATS; read it off a posting URL.

Two things about this endpoint punish a naive client:

- **A GET returns nothing useful.** It is POST-only, with a JSON body.
- **`limit` is capped at 20.** Asking for more does not error -- it returns an
  empty `jobPostings` array, which reads exactly like "this employer has no
  openings". The cap is enforced here rather than trusted to the caller.

Workday tenants cannot be guessed from a company name the way a Greenhouse slug
can (the host carries a data-centre number: wd1, wd3, wd5...), so this source is
configured per company. `from_url()` derives that config from any careers link
you already have, which is how it will usually be set up.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

from ..models import JobPosting
from .base import JobSource, SourceError, http_post_json

log = logging.getLogger(__name__)

ENDPOINT = "https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
JOB_URL = "https://{tenant}.{wd}.myworkdayjobs.com/{locale}/{site}/job{path}"

# Larger values silently return an empty page rather than an error.
MAX_LIMIT = 20

_URL_RE = re.compile(
    r"https?://(?P<tenant>[^.]+)\.(?P<wd>wd\d+)\.myworkdayjobs\.com/"
    r"(?:(?P<locale>[a-z]{2}-[A-Z]{2})/)?(?P<site>[^/?#]+)",
    re.I,
)

# Workday reports recency as text ("Posted 3 Days Ago", "Posted Yesterday",
# "Posted Today"), never an absolute date.
_POSTED_RE = re.compile(r"(\d+)\+?\s*(day|week|month)s?\s*ago", re.I)
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}


def parse_posted_on(text: str, today: date | None = None):
    """'Posted 3 Days Ago' -> a date. None when it cannot be read.

    Returning None beats guessing: an invented date feeds straight into the
    freshness term of the score.
    """
    if not text:
        return None
    today = today or date.today()
    low = text.lower()
    if "today" in low or "just posted" in low:
        return today
    if "yesterday" in low:
        return today - timedelta(days=1)
    m = _POSTED_RE.search(low)
    if not m:
        return None
    return today - timedelta(days=int(m.group(1)) * _UNIT_DAYS[m.group(2)])


class WorkdaySource(JobSource):
    name = "workday"

    def __init__(self, tenant: str, site: str, wd: str = "wd3", locale: str = "en-US"):
        if not tenant or not site:
            raise ValueError("Workday needs both a tenant and a site")
        self.tenant, self.site, self.wd, self.locale = tenant, site, wd, locale

    @classmethod
    def from_url(cls, url: str) -> "WorkdaySource":
        """Build from any myworkdayjobs link, e.g. a posting URL already on file.

        This is the practical setup path: the tenant, data-centre number and
        site are all in a link you already have, and none of them is guessable.
        """
        m = _URL_RE.match(url or "")
        if not m:
            raise ValueError(f"not a myworkdayjobs URL: {url!r}")
        g = m.groupdict()
        return cls(tenant=g["tenant"], site=g["site"], wd=g["wd"].lower(),
                   locale=g.get("locale") or "en-US")

    @property
    def endpoint(self) -> str:
        return ENDPOINT.format(tenant=self.tenant, wd=self.wd, site=self.site)

    def fetch(self, company: str | None = None, *, max_pages: int = 10,
              search_text: str = "", today: date | None = None) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        total: int | None = None
        for page in range(max_pages):
            body = {"appliedFacets": {}, "limit": MAX_LIMIT,
                    "offset": page * MAX_LIMIT, "searchText": search_text}
            try:
                data = http_post_json(self.endpoint, body)
            except SourceError:
                # Page 1 failing means the tenant/site is wrong or the host is
                # unreachable -- never fold that into "no openings".
                if page == 0:
                    raise
                break
            batch = data.get("jobPostings") or []
            if total is None:
                total = data.get("total")
            if not batch:
                break
            for row in batch:
                jobs.append(self._to_posting(row, company, today=today))
            if total is not None and len(jobs) >= total:
                break
        if total is not None and len(jobs) < total:
            # Say so rather than let a truncated pull read as the whole board.
            log.warning("%s/%s: retrieved %d of %d postings (raise max_pages)",
                        self.tenant, self.site, len(jobs), total)
        return jobs

    def _to_posting(self, row: dict, company: str | None, today=None) -> JobPosting:
        path = row.get("externalPath") or ""
        return JobPosting(
            source=self.name,
            company=company or self.tenant,
            title=row.get("title") or "",
            location=row.get("locationsText") or "",
            url=JOB_URL.format(tenant=self.tenant, wd=self.wd, locale=self.locale,
                               site=self.site, path=path) if path else "",
            posted_at=parse_posted_on(row.get("postedOn") or "", today=today),
            description=(row.get("jobDescription") or "")[:4000],
            external_id=str(row.get("bulletFields", [""])[0] or path),
        )


WORKABLE_RE = re.compile(r"https?://apply\.workable\.com/(?P<slug>[^/?#]+)", re.I)


def workable_slugs_from_urls(urls) -> set[str]:
    """Pick Workable account slugs out of posting URLs already collected."""
    return {m.group("slug").lower()
            for m in (WORKABLE_RE.match(u or "") for u in urls or ()) if m}


def tenants_from_urls(urls) -> dict[str, dict]:
    """Derive Workday config from posting URLs already collected.

    Bootstraps the source from data on hand -- the stored Apollo postings carry
    the tenant, data-centre number and site for every Workday employer in them,
    so there is nothing to look up by hand.
    """
    found: dict[str, dict] = {}
    for url in urls or ():
        m = _URL_RE.match(url or "")
        if not m:
            continue
        g = m.groupdict()
        found.setdefault(g["tenant"].lower(), {
            "tenant": g["tenant"], "site": g["site"],
            "wd": g["wd"].lower(), "locale": g.get("locale") or "en-US",
        })
    return found
