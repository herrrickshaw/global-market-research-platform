#!/usr/bin/env python3
"""
llm_extract.py
==============
Generic "unstructured document -> structured JSON" extraction, using the
repo's existing Groq (OpenAI-compatible) LLM pattern (see repo-inventory/
canonicalize.py) with a Gemini fallback -- both already configured via
~/.env.local for the "AI Advisor" feature.

Primary provider is NVIDIA's Nemotron-3.5-Lightning (30B total / 3B active
hybrid Mamba-Transformer MoE, tuned for fast structured extraction and tool
calling -- see https://github.com/NVIDIA-NeMo/Nemotron/tree/main/usage-cookbook/Nemotron-3.5-Lightning).
At 3B active parameters vs. Groq's 70B default it cuts both latency and
per-call load for this schema-in/JSON-out workload; Groq then Gemini remain
as fallbacks if NVIDIA_API_KEY isn't set or the call fails. Model slug
confirmed against build.nvidia.com's catalog as of 2026-08:
https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b
-- override via NVIDIA_MODEL if NVIDIA renames/retags it later.

Derived from patents MY269019 "System and method for generating queryable
structured document from an unstructured document using machine learning"
(IIIT-Hyderabad, LTRC) and MY269128 "System for extracting and analyzing
nutritional information from food labels using a large language model"
(IIIT-Hyderabad, MLL) -- same core technique (unstructured text -> a fixed
schema via an LLM), applied here to two places in this repo that currently
rely on brittle regex/layout parsing:
  - SEBI DRHP filing text (SEBI_web_scraper.ipynb)
  - Portfolio broker-statement text (portfolio.py's PDF parsing)

Page-level grounding (2026-08): citations can optionally be tied to a page
number, not just a text span. This mirrors the methodology used by
scholarly360/indian_ipo_prospectus_data_with_pageno on Hugging Face (the
closest public dataset to this module's actual DRHP-extraction use case --
though at 100 prospectuses from 2022 it's too small/stale to train or
benchmark against directly) and by gtfintechlab's IPO-Mine project (fresh
through 2026, but SEC/US filings, not SEBI): both ground extracted claims to
a specific page in a long multi-page filing rather than "somewhere in the
document." Pass `text` as a list of (page_number, page_text) tuples instead
of a single string to get page numbers in `_grounding`, incl. a
`page_verified` flag catching the case where the model cites real text but
attributes it to the wrong page.

(Also evaluated: numind/NuExtract3, a 4B VLM purpose-built for schema-in/
JSON-out extraction, released May 2026 -- genuinely fresh and worth adding
as another `_client_and_model` provider if/when this module needs
image-input extraction (scanned DRHPs) rather than pre-OCR'd text; not
added here since the current callers are text-only. kdave/Indian_Financial_
News (sentiment) was also checked and ruled out: stale since 01/2024, and
labeled via an ad-hoc Google-Sheets GPT add-on rather than a documented
methodology -- not a sound base for this repo's sentiment_pipeline.py.)

Usage:
    from llm_extract import extract_structured

    schema = {
        "company_name": "string",
        "issue_size_cr": "number, issue size in INR crore",
        "price_band_low": "number",
        "price_band_high": "number",
        "listing_exchange": "string, e.g. NSE/BSE/both",
    }
    result = extract_structured(drhp_text, schema)
    # or, for page-grounded citations:
    result = extract_structured([(1, page1_text), (2, page2_text)], schema)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path


def _load_env_local() -> dict:
    """Minimal .env.local loader (avoids a hard python-dotenv dependency)."""
    env_path = Path.home() / ".env.local"
    values: dict = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values


def _client_and_model(provider: str):
    """Returns (openai.OpenAI-compatible client, model_name) for the given provider."""
    env = {**_load_env_local(), **os.environ}
    from openai import OpenAI

    if provider == "nvidia":
        key = env.get("NVIDIA_API_KEY")
        if not key:
            raise RuntimeError("NVIDIA_API_KEY not found in ~/.env.local or environment")
        return (OpenAI(api_key=key, base_url="https://integrate.api.nvidia.com/v1"),
                env.get("NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"))
    if provider == "groq":
        key = env.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not found in ~/.env.local or environment")
        return (OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1"),
                env.get("GROQ_MODEL", "llama-3.3-70b-versatile"))
    if provider == "gemini":
        key = env.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not found in ~/.env.local or environment")
        return (OpenAI(api_key=key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/"),
                env.get("GEMINI_MODEL", "gemini-2.0-flash"))
    raise ValueError(f"unknown provider {provider!r}")


def _extract_json(text: str) -> dict:
    """Pull the first {...} JSON object out of a model response (models sometimes wrap it in prose or ```json fences)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    match = re.search(r"\{.*\}", candidate, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in model response: {text[:200]!r}")
    return json.loads(match.group(0))


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _paginate(text: str | list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Normalize *text* into a list of (page_number, page_text). A plain
    string becomes a single unnumbered page (page 1)."""
    if isinstance(text, str):
        return [(1, text)]
    return list(text)


def _span_in(span: object, source_text: str) -> bool:
    """True if *span* appears verbatim (allowing whitespace differences) in source_text."""
    if not isinstance(span, str) or not span.strip():
        return False
    return _normalize_whitespace(span) in _normalize_whitespace(source_text)


def _verify_citation(citation: object, pages: list[tuple[int, str]]) -> dict:
    """
    Checks a citation -- either a plain span string, or a page-grounded
    {"span": ..., "page": ...} object -- against *pages*.

    Returns {"grounded": bool, "span": str|None, "page": int|None,
    "page_verified": bool}. "grounded" is True iff the span appears
    ANYWHERE across all pages (the original, page-agnostic check).
    "page_verified" is the stronger check: True iff the span appears
    specifically on the claimed page -- catches the model citing real
    document text but attributing it to the wrong page.
    """
    full_text = "\n".join(t for _, t in pages)
    if isinstance(citation, dict):
        span, page = citation.get("span"), citation.get("page")
    else:
        span, page = citation, None
    grounded = _span_in(span, full_text)
    page_text = next((t for n, t in pages if n == page), None) if page is not None else None
    page_verified = grounded and (page_text is not None) and _span_in(span, page_text)
    return {"grounded": grounded, "span": span, "page": page, "page_verified": page_verified}


def extract_structured(
    text: str | list[tuple[int, str]],
    schema: dict,
    instructions: str = "",
    provider: str = "nvidia",
    fallback_provider: str | list[str] | None = ("groq", "gemini"),
    require_citations: bool = True,
) -> dict:
    """
    Extract a JSON object matching *schema* out of unstructured *text* using
    an LLM. *schema* maps field name -> a short description of what to put
    there (used verbatim in the prompt, not validated as a JSON-schema spec --
    kept simple since every caller here just wants a flat field->value dict).

    require_citations (default True): also asks the model for a verbatim
    source-text span backing each non-null field, then verifies that span
    actually appears in *text* before trusting it -- citation-grounding, one
    of the few concretely effective mitigations in the literature on LLM
    extraction from financial documents. That literature is sobering: on
    FinanceBench (real 10-Ks/10-Qs/8-Ks), GPT-4-Turbo with retrieval got 81%
    of questions wrong; FinTagging found the best model only 17% accurate at
    linking extracted facts to correct XBRL taxonomy concepts. Single-shot
    "trust the JSON" extraction is not a safe default for this domain.

    Adds a "_grounding" key to the result: {field: {"grounded": bool, "span":
    str|None, "page": int|None, "page_verified": bool}}. An ungrounded field
    is NOT dropped from the result -- it's still returned as extracted --
    but is flagged grounded=False so callers can decide whether to trust it
    (e.g. skip it, flag it for manual review, or log it). This catches the
    class of hallucination where the model invents a value with no textual
    basis in the document at all, which schema-only prompting
    (require_citations=False, the original behavior) can't catch.

    Pass *text* as a list of (page_number, page_text) tuples (instead of a
    single string) to also get each citation tied to a page: "page" is the
    page the model claims the span came from, and "page_verified" is True
    only if the span actually appears on THAT page -- catching the model
    citing real document text but attributing it to the wrong page, which
    "grounded" alone (span found ANYWHERE in the document) would miss.

    KNOWN LIMITATION, confirmed by testing: grounding only verifies the
    cited SPAN is real text copied from the document -- it does not verify
    that a COMPUTED/DERIVED value is actually correct given that span. E.g.
    asking for a "price_band_midpoint" (an arithmetic mean the model must
    calculate, not a literal quote) got grounded=True because the model
    correctly cited the real "Rs. 210 to Rs. 222" span -- but nothing here
    checks that 216 is actually the midpoint of 210 and 222. For
    computed/derived fields, add a separate correctness check (e.g.
    recompute simple arithmetic yourself from the grounded raw values rather
    than trusting the model's derived one).

    Falls back to *fallback_provider* if the primary provider's call or JSON
    parse fails, then raises if that fails too -- callers should catch and
    degrade gracefully (e.g. skip the field, don't crash a whole report).
    """
    pages = _paginate(text)
    paginated = len(pages) > 1
    document_text = "\n\n".join(f"[page {n}]\n{t}" for n, t in pages) if paginated else pages[0][1]
    schema_lines = "\n".join(f'  "{k}": {v}' for k, v in schema.items())

    if require_citations:
        if paginated:
            citation_shape = (
                'the value must be an object {"span": <the exact verbatim substring of the '
                'document text below that supports the extracted value -- copy it exactly, do '
                'not paraphrase or summarize>, "page": <the page number from the [page N] '
                "marker immediately above where that span appears>}. For null fields, use null."
            )
        else:
            citation_shape = (
                "the value must be the exact verbatim substring of the document text below "
                "that supports the extracted value (copy it exactly, do not paraphrase or "
                "summarize). For null fields, use null."
            )
        prompt = (
            "Extract the following fields from the document text below. "
            "Respond with ONLY a single JSON object with exactly two top-level keys, "
            '"fields" and "citations" -- no prose, no markdown fences.\n\n'
            f'"fields" must have these keys:\n{schema_lines}\n'
            "Use null for any field not present in the text.\n\n"
            f'"citations" must have the SAME keys as "fields". For each non-null field, '
            f"{citation_shape}\n\n"
            f"{instructions}\n\n"
            f"Document text:\n{document_text}"
        )
    else:
        prompt = (
            "Extract the following fields from the document text below. "
            "Respond with ONLY a single JSON object -- no prose, no markdown fences. "
            "Use null for any field not present in the text.\n\n"
            f"Fields:\n{schema_lines}\n\n"
            f"{instructions}\n\n"
            f"Document text:\n{document_text}"
        )

    if fallback_provider is None:
        fallbacks = []
    elif isinstance(fallback_provider, str):
        fallbacks = [fallback_provider]
    else:
        fallbacks = list(fallback_provider)
    providers = [provider] + fallbacks
    last_error = None
    for p in providers:
        try:
            client, model = _client_and_model(p)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            parsed = _extract_json(resp.choices[0].message.content)
            if not require_citations:
                return parsed

            fields = parsed.get("fields", {})
            citations = parsed.get("citations", {})
            grounding = {}
            for key in schema:
                value = fields.get(key)
                citation = citations.get(key)
                if value is None:
                    grounding[key] = {"grounded": True, "span": None, "page": None, "page_verified": True}
                else:
                    grounding[key] = _verify_citation(citation, pages)
            result = dict(fields)
            result["_grounding"] = grounding
            return result
        except Exception as exc:
            last_error = exc
            continue
    raise RuntimeError(f"extract_structured failed on all providers {providers}: {last_error}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="LLM structured extraction demo")
    ap.add_argument("--demo", choices=["drhp", "portfolio"], default="drhp")
    args = ap.parse_args()

    if args.demo == "drhp":
        sample_text = (
            "Vantage Cold Chain Logistics Limited proposes to raise up to "
            "Rs. 850 crore through a fresh issue of equity shares, with a "
            "price band of Rs. 210 to Rs. 222 per equity share of face value "
            "Rs. 10 each. The equity shares are proposed to be listed on both "
            "BSE and NSE. The issue opens on 14 August and closes on 18 August."
        )
        schema = {
            "company_name": "string",
            "issue_size_cr": "number, total issue size in INR crore",
            "price_band_low": "number",
            "price_band_high": "number",
            "listing_exchange": "string, e.g. NSE/BSE/both",
        }
    else:
        sample_text = (
            "Holdings as of statement date: 120 shares of RELIANCE INDUSTRIES LTD "
            "purchased at an average price of Rs 2,410.50; 40 shares of TCS at "
            "average cost Rs 3,550.00; cash balance Rs 15,230.75."
        )
        schema = {
            "holdings": "array of {symbol, quantity, avg_price}",
            "cash_balance": "number",
        }

    result = extract_structured(sample_text, schema)
    print(json.dumps(result, indent=2))
