"""Zyte API as an optional fetch backend for own-domain careers pages.

Why this exists. Checking the postings already on file showed three target
employers publishing on their own career sites with no readable ATS behind
them: Siemens Energy (`jobs.siemens-energy.com`), S&P Global
(`careers.spglobal.com`) and TotalEnergies (`jobs.totalenergies.com`). Those
pages are published so candidates read them, but they render their listings in
JavaScript, so a plain GET returns an empty shell and `careers_page.py` finds
nothing. Zyte renders the page and hands back the finished HTML, which the
existing schema.org parser then reads unchanged.

WHAT THIS IS NOT FOR. Zyte will fetch anything, which makes it exactly the
tool for quietly doing what this project has declined to do all along. Putting
a vendor in front of a scrape does not change what the scrape is: LinkedIn,
Naukri, iimjobs, Hirist, Instahyre and Foundit all forbid it in their terms,
and the account at risk is the one being job-hunted with.

So the boundary is enforced here in code rather than left to a README
paragraph. `DENIED_HOSTS` is checked on every call and cannot be turned off by
configuration -- a later config edit pointing `careers_pages` at a LinkedIn URL
raises instead of silently scraping. Prose is not a control; this is.
"""
from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from .base import SourceError, _post

log = logging.getLogger(__name__)

ENDPOINT = "https://api.zyte.com/v1/extract"

# Sites whose terms forbid automated collection. Deliberately not configurable.
DENIED_HOSTS = (
    "linkedin.com",
    "naukri.com",
    "iimjobs.com",
    "hirist.com", "hirist.tech",
    "instahyre.com",
    "foundit.in", "monsterindia.com",
    "glassdoor.com", "glassdoor.co.in",
    "indeed.com",
    "shine.com",
    "timesjobs.com",
)


class DeniedByPolicy(SourceError):
    """The requested host is one this tool will not scrape."""


def _host(url: str) -> str:
    return (urlparse(url or "").hostname or "").lower()


def is_denied(url: str) -> bool:
    """True when the URL's host is a site whose terms forbid scraping.

    Matches the registrable domain and any subdomain of it, so
    `in.linkedin.com` and `www.naukri.com` are caught alongside the bare host.
    """
    host = _host(url)
    if not host:
        return False
    return any(host == d or host.endswith("." + d) for d in DENIED_HOSTS)


class ZyteFetcher:
    """Renders a page and returns its HTML. Not a JobSource in its own right.

    It produces HTML, not postings -- `CareersPageSource` still does the
    parsing, so there is one schema.org implementation rather than two.
    """

    name = "zyte"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("ZYTE_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def fetch_html(self, url: str, *, browser: bool = True) -> str:
        if is_denied(url):
            raise DeniedByPolicy(
                f"refusing to fetch {_host(url)}: its terms forbid automated "
                f"collection, and a vendor in front of the request does not "
                f"change that")
        if not self.configured:
            raise SourceError("Zyte credentials missing (ZYTE_API_KEY)")

        # browserHtml renders JavaScript; httpResponseBody is the cheaper raw
        # fetch. The JS-rendered careers sites are the whole reason for this,
        # so browser rendering is the default.
        body = {"url": url}
        if browser:
            body["browserHtml"] = True
        else:
            body["httpResponseBody"] = True

        # Zyte authenticates with HTTP Basic (key as username, empty password),
        # so the key travels in a header and never enters the URL.
        import base64
        token = base64.b64encode(f"{self.api_key}:".encode()).decode()
        headers = {"Authorization": f"Basic {token}"}

        resp = _post(ENDPOINT, json_body=body, headers=headers)
        try:
            data = resp.json()
        except ValueError as exc:
            raise SourceError(f"zyte: non-JSON response for {_host(url)}: {exc}") from exc

        html = data.get("browserHtml") or data.get("httpResponseBody") or ""
        if not html:
            # An empty body here is a failed render, not a page with no jobs.
            raise SourceError(
                f"zyte: empty response body for {_host(url)} "
                f"(render failed; not evidence the page has no postings)")
        if not browser and data.get("httpResponseBody"):
            import base64 as _b64
            html = _b64.b64decode(html).decode("utf-8", errors="replace")
        return html
