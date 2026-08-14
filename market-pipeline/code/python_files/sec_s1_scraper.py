#!/usr/bin/env python3
"""
sec_s1_scraper.py
==================
US counterpart to SEBI_web_scraper.ipynb: lists recent S-1 (US IPO
prospectus) filings from SEC EDGAR. No Selenium needed here, unlike SEBI's
site -- EDGAR serves a real, public, no-auth Atom feed of "current" filings
by form type, so this is a plain HTTP fetch + parse.

Methodology note (2026-08): informed by gtfintechlab's IPO-Mine project
(github.com/gtfintechlab/IPO-Mine, "Section-Structured Analysis of Long,
Multimodal IPO Documents" -- coverage fresh through 2026) and by
scholarly360/indian_ipo_prospectus_data_with_pageno on Hugging Face, neither
of which this module pulls data from directly (SEC/US filings vs. India in
the former; too small/stale to depend on in the latter -- see llm_extract.py
for the full writeup). What's borrowed is the grounding discipline: rather
than trusting one whole-document LLM call, each filing is paginated and run
through llm_extract.extract_structured()'s page-grounded citations (added
alongside this file), so every extracted field is traceable to a specific
page of a specific filing -- a guarantee SEBI_web_scraper.ipynb's output
doesn't have today (it lists DRHP filings but never opens or extracts
fields from them).

Two modes:
  list-only (default): just the S-1 filing list -- fast, no LLM calls, the
                        direct US analogue of what SEBI_web_scraper.ipynb
                        already produces.
  --extract:            also fetches each filing's primary document and runs
                         extract_structured() against a DRHP-equivalent
                         schema (company name, offering size, price range,
                         listing exchange, ticker).

SEC requires a compliant User-Agent (a real name + contact email) on every
request -- https://www.sec.gov/os/webmaster-faq#developers -- or it starts
throttling/blocking the IP. Set SEC_EDGAR_USER_AGENT via env_loader.py's
credential store, e.g. "MyResearchTool contact@example.com".

NOTE: www.sec.gov was unreachable from the sandbox this was written in
(network egress proxy blocks it, same as it blocked build.nvidia.com and
huggingface.co while building the rest of this change) -- so this has NOT
been run against live EDGAR yet. See .github/workflows/spike-cloud-egress.yml
(Leg 5) for a CI-runner reachability check before relying on this in
production.

Usage:
  python sec_s1_scraper.py                       # list-only, 40 filings
  python sec_s1_scraper.py --extract --count 20   # also extract fields
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import feedparser
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_loader  # noqa: E402
from llm_extract import extract_structured  # noqa: E402

EDGAR_CURRENT_FEED = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcurrent&type=S-1&company=&dateb=&owner=include&count={count}&output=atom"
)

# DRHP-equivalent schema -- same shape as SEBI_web_scraper's target fields
# (see llm_extract.py's __main__ demo) so India and US IPO extractions are
# directly comparable downstream.
SCHEMA = {
    "company_name": "string, the issuer's legal name",
    "offering_size_usd": "number, total offering size in USD (convert from millions if stated that way)",
    "price_range_low": "number, low end of the offer price range per share, USD",
    "price_range_high": "number, high end of the offer price range per share, USD",
    "listing_exchange": "string, e.g. NASDAQ/NYSE",
    "ticker_symbol": "string, proposed ticker symbol",
}

_TITLE_RE = re.compile(r"^(\S+)\s*-\s*(.+?)\s*\(\d+\)")


def _user_agent() -> str:
    ua = env_loader.get("SEC_EDGAR_USER_AGENT")
    if not ua:
        raise RuntimeError(
            "SEC_EDGAR_USER_AGENT not set -- SEC requires a real contact "
            "identity on every request (name + email) or it throttles/blocks "
            'the IP. Set it in the credential store, e.g. '
            '"MyResearchTool contact@example.com".'
        )
    return ua


def fetch_recent_s1_filings(count: int = 40) -> list[dict]:
    """Recent S-1 filings across all filers, from SEC EDGAR's public
    'current filings' Atom feed -- no auth, no Selenium, unlike SEBI's site."""
    sess = requests.Session()
    sess.headers.update({"User-Agent": _user_agent()})
    r = sess.get(EDGAR_CURRENT_FEED.format(count=count), timeout=30)
    r.raise_for_status()
    feed = feedparser.parse(r.content)

    filings = []
    for entry in feed.entries:
        # EDGAR titles look like "S-1 - Company Name (0001234567) (Filer)"
        m = _TITLE_RE.match(entry.get("title", ""))
        form, company = (m.group(1), m.group(2)) if m else ("S-1", entry.get("title", ""))
        filings.append({
            "filing_date": entry.get("updated", ""),
            "form_type": form,
            "company": company,
            "filing_index_url": entry.get("link", ""),
        })
    return filings


def _primary_document_url(sess: requests.Session, filing_index_url: str) -> str | None:
    """The Atom entry links to the filing's index page, not the document
    itself; the primary .htm document is the first non-index link there."""
    r = sess.get(filing_index_url, timeout=30)
    r.raise_for_status()
    hrefs = re.findall(r'href="([^"]+\.htm)"', r.text)
    docs = [h for h in hrefs if "index" not in h.lower()]
    if not docs:
        return None
    href = docs[0]
    return href if href.startswith("http") else f"https://www.sec.gov{href}"


def _paginate_html(html: str, chars_per_page: int = 4000) -> list[tuple[int, str]]:
    """SEC filings are one long HTML document with no real page breaks --
    approximate pages by character count so llm_extract's page-grounded
    citations still give a usable pointer back into the filing."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    pages = [text[i:i + chars_per_page] for i in range(0, len(text), chars_per_page)]
    return list(enumerate(pages, start=1))


def extract_filing_fields(sess: requests.Session, filing_index_url: str) -> dict | None:
    doc_url = _primary_document_url(sess, filing_index_url)
    if not doc_url:
        return None
    r = sess.get(doc_url, timeout=60)
    r.raise_for_status()
    pages = _paginate_html(r.text)
    return extract_structured(pages, SCHEMA)


def main() -> int:
    ap = argparse.ArgumentParser(description="US S-1 IPO filing scraper (SEC EDGAR)")
    ap.add_argument("--count", type=int, default=40, help="how many recent S-1 filings to list")
    ap.add_argument("--extract", action="store_true",
                     help="also extract structured fields per filing (slow, calls the LLM)")
    ap.add_argument("--out", default="reports/sec_s1_filings.csv", help="output CSV path")
    args = ap.parse_args()

    filings = fetch_recent_s1_filings(args.count)
    print(f"Found {len(filings)} recent S-1 filings.")

    if args.extract:
        sess = requests.Session()
        sess.headers.update({"User-Agent": _user_agent()})
        for f in filings:
            try:
                fields = extract_filing_fields(sess, f["filing_index_url"])
                if fields:
                    f.update(fields)
            except Exception as e:
                print(f"  extraction failed for {f['company']}: {e}")
            time.sleep(0.3)  # stay well under SEC's 10 req/s fair-access limit

    import pandas as pd
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(filings).to_csv(out_path, index=False)
    print(f"Wrote {len(filings)} filings to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
