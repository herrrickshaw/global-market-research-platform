"""Shared HTTP plumbing for job sources."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

USER_AGENT = "job-search-copilot/0.1 (personal job search; contact via GitHub)"
DEFAULT_TIMEOUT = 20


# Query params that carry secrets. Sources authenticate via the query string
# (Adzuna requires it), so raw URLs must never reach a log or an exception.
_SECRET_PARAMS = ("app_key", "app_id", "api_key", "apikey", "key", "token",
                  "secret", "password", "access_token")


def redact(url: str) -> str:
    """Mask credential values in a URL before it is logged or raised."""
    import re
    pattern = r"([?&](?:" + "|".join(_SECRET_PARAMS) + r")=)[^&\s]*"
    return re.sub(pattern, r"\1***", url or "", flags=re.I)


class SourceError(RuntimeError):
    """A source failed in a way the pipeline should log and skip, not crash on."""


_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html"})
    return _session


def _request(url: str, *, params: dict | None = None, headers: dict | None = None,
             retries: int = 2, timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = _get_session().get(url, params=params, headers=headers, timeout=timeout)
            # 404 means "no board here" - a normal answer when probing slugs,
            # not a transient failure worth retrying.
            if resp.status_code == 404:
                raise SourceError(f"404 {redact(url)}")
            if resp.status_code == 429:
                wait = 2 ** attempt
                log.warning("rate limited on %s, sleeping %ss", redact(url), wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except SourceError:
            raise
        except Exception as exc:  # network, TLS, timeout, bad status
            last = exc
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise SourceError(f"GET {redact(url)} failed: {redact(str(last))}")


def http_get_json(url: str, params: dict | None = None,
                  headers: dict | None = None) -> Any:
    # Header-authenticated sources (RapidAPI) pass their key here rather than in
    # the query string. Headers are never logged; redact() only sees the URL.
    resp = _request(url, params=params, headers=headers)
    try:
        return resp.json()
    except ValueError as exc:
        raise SourceError(f"non-JSON response from {redact(url)}: {exc}") from exc


def http_get_text(url: str, params: dict | None = None) -> str:
    return _request(url, params=params).text


class JobSource:
    """Base class. Subclasses implement fetch() and return list[JobPosting]."""

    name = "base"

    def fetch(self, *args, **kwargs) -> list:
        raise NotImplementedError
