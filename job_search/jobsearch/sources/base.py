"""Shared HTTP plumbing for job sources."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

USER_AGENT = "job-search-copilot/0.1 (personal job search; contact via GitHub)"
DEFAULT_TIMEOUT = 20


class SourceError(RuntimeError):
    """A source failed in a way the pipeline should log and skip, not crash on."""


_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, text/html"})
    return _session


def _request(url: str, *, params: dict | None = None, retries: int = 2,
             timeout: int = DEFAULT_TIMEOUT) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = _get_session().get(url, params=params, timeout=timeout)
            # 404 means "no board here" - a normal answer when probing slugs,
            # not a transient failure worth retrying.
            if resp.status_code == 404:
                raise SourceError(f"404 {url}")
            if resp.status_code == 429:
                wait = 2 ** attempt
                log.warning("rate limited on %s, sleeping %ss", url, wait)
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
    raise SourceError(f"GET {url} failed: {last}")


def http_get_json(url: str, params: dict | None = None) -> Any:
    resp = _request(url, params=params)
    try:
        return resp.json()
    except ValueError as exc:
        raise SourceError(f"non-JSON response from {url}: {exc}") from exc


def http_get_text(url: str, params: dict | None = None) -> str:
    return _request(url, params=params).text


class JobSource:
    """Base class. Subclasses implement fetch() and return list[JobPosting]."""

    name = "base"

    def fetch(self, *args, **kwargs) -> list:
        raise NotImplementedError
