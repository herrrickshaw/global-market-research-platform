#!/usr/bin/env python3
"""
extract_gmail_briefs.py — parse real historical "Daily Market Brief" emails
(drafts + sent) into a dated, priced recommendations parquet.

WHY THIS EXISTS
Discovered 2026-08-22: many days between the pipeline's early period and its
current daily_mailer.sh have no reconstructable pick history from local files
(no archived per-day brief, no daily picks CSV). But the Gmail MCP tool has no
send capability — it can only create_draft — so a large share of early briefs
were drafted and never actually sent. These drafts (and the few that DID get
sent) are real, dated, per-stock content: exactly the ground truth missing
from stock_pick_performance.py's other three sources. This script recovers it.

SOURCES (raw MCP tool output, saved to disk by the harness when oversized):
  - list_drafts(query="subject:Daily Market Brief", view=DRAFT_VIEW_FULL) → 15
    drafts, 2026-06-29 to 2026-07-16 (multiple attempts on some days — the
    LATEST draft per calendar date is kept; earlier same-day drafts are
    presumed superseded attempts, not distinct recommendations).
  - get_thread on the two calendar dates with a SENT copy outside the drafts
    range (2026-07-09, 2026-07-17) — sent preferred over draft when the
    thread also carries a forwarded copy of the same content.

HTML STRUCTURE (consistent across all fetched emails): one `<h3>` per
market/screener section, containing a market flag emoji, followed by a
`<table>` with a header row `<th>` naming its columns (always includes
Symbol; price column is named LTP, or "Close"/"Entry" in older formats).
Rows are extracted keyed by header name so column-order drift across days
doesn't silently misalign fields.

OUTPUT: research/gmail_brief_picks.parquet — symbol, market, entry_date,
entry_price, tier, filter (the Screens/detail column), section (which
table/heading it came from), source_kind (draft|sent), draft_or_msg_id.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

RESEARCH = Path(__file__).resolve().parent
OUT = RESEARCH / "gmail_brief_picks.parquet"

DRAFTS_FILE = Path(
    "/Users/umashankar/.claude/projects/-Users-umashankar/"
    "e1f0ddd1-b215-44a0-9738-8aad56a02a1a/tool-results/"
    "mcp-620fa380-4286-4c8b-a3b3-70befb188c68-list_drafts-1787418287771.txt"
)
THREAD_FILES = [
    ("/Users/umashankar/.claude/projects/-Users-umashankar/e1f0ddd1-b215-44a0-9738-8aad56a02a1a/"
     "tool-results/mcp-620fa380-4286-4c8b-a3b3-70befb188c68-get_thread-1787418419066.txt"),
    ("/Users/umashankar/.claude/projects/-Users-umashankar/e1f0ddd1-b215-44a0-9738-8aad56a02a1a/"
     "tool-results/mcp-620fa380-4286-4c8b-a3b3-70befb188c68-get_thread-1787418419358.txt"),
]

MARKET_MAP = [  # (marker substring, code) -- checked in order against section heading text
    ("🇮🇳", "IN"), ("India", "IN"),
    ("🇺🇸", "US"), (" US ", "US"), ("U.S.", "US"),
    ("🇪🇺", "EU"), ("Europe", "EU"),
    ("🇯🇵", "JP"), ("Japan", "JP"),
    ("🇰🇷", "KR"), ("Korea", "KR"),
]

MONTH_RE = re.compile(r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{4})")
MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}


def date_from_subject(subject: str) -> pd.Timestamp | None:
    m = MONTH_RE.search(subject)
    if not m:
        return None
    d, mon, y = m.groups()
    return pd.Timestamp(year=int(y), month=MONTHS[mon], day=int(d))


def current_market(heading_text: str, fallback: str | None) -> str | None:
    for marker, code in MARKET_MAP:
        if marker in heading_text:
            return code
    return fallback


def parse_num(s: str) -> float | None:
    s = s.replace(",", "").replace("₹", "").replace("$", "").replace("€", "").replace("£", "").strip()
    s = re.sub(r"[+%]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def parse_brief_html(html: str, entry_date: pd.Timestamp, source_kind: str,
                     msg_id: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    mkt = None
    # Walk the document in order so each table inherits the nearest preceding
    # heading's market + section name.
    for el in soup.find_all(["h1", "h2", "h3", "table"]):
        if el.name in ("h1", "h2", "h3"):
            text = el.get_text(" ", strip=True)
            mkt = current_market(text, mkt)
            section = text
            continue
        # el is a table
        headers = [th.get_text(strip=True) for th in el.find_all("th")]
        if not headers or not any("symbol" in h.lower() for h in headers):
            continue  # not a pick table (e.g. the validation-status table)
        sym_i = next(i for i, h in enumerate(headers) if "symbol" in h.lower())
        price_i = next((i for i, h in enumerate(headers)
                        if h.lower() in ("ltp", "close", "entry", "price")), None)
        tier_i = next((i for i, h in enumerate(headers) if h.lower() == "tier"), None)
        detail_i = next((i for i, h in enumerate(headers)
                         if h.lower() in ("screens", "name")), None)
        for tr in el.find_all("tr")[1:]:  # skip header row
            cells = tr.find_all("td")
            if len(cells) <= sym_i:
                continue
            sym = cells[sym_i].get_text(strip=True).upper()
            if not sym or not re.match(r"^[A-Z0-9.\-]+$", sym):
                continue
            price = parse_num(cells[price_i].get_text(strip=True)) if price_i is not None and price_i < len(cells) else None
            tier = cells[tier_i].get_text(strip=True) if tier_i is not None and tier_i < len(cells) else None
            detail = cells[detail_i].get_text(strip=True) if detail_i is not None and detail_i < len(cells) else None
            if price is None or price <= 0:
                continue
            rows.append({
                "symbol": sym, "market": mkt or "??", "entry_date": entry_date,
                "entry_price": price, "tier": tier, "filter": detail,
                "section": section, "source_kind": source_kind, "msg_id": msg_id,
            })
    return rows


def load_drafts() -> list[dict]:
    d = json.loads(DRAFTS_FILE.read_text())
    by_date: dict[pd.Timestamp, dict] = {}
    for draft in d["drafts"]:
        subj = draft.get("subject", "")
        edate = date_from_subject(subj)
        if edate is None:
            continue
        ts = pd.Timestamp(draft["date"])
        # keep the LATEST draft per calendar date (later attempts supersede earlier ones)
        if edate not in by_date or ts > by_date[edate]["_ts"]:
            by_date[edate] = {"_ts": ts, "html": draft["htmlBody"], "id": draft["id"]}
    out = []
    for edate, v in by_date.items():
        out.extend(parse_brief_html(v["html"], edate, "draft", v["id"]))
    print(f"  drafts: {len(by_date)} calendar dates -> {len(out)} picks")
    return out


def load_sent_threads() -> list[dict]:
    out = []
    seen_dates = set()
    for f in THREAD_FILES:
        t = json.loads(Path(f).read_text())
        # prefer a message actually labelled SENT with the exact (non-Fwd:) subject
        cands = [m for m in t["messages"] if "SENT" in m.get("labelIds", [])
                and not m.get("subject", "").startswith("Fwd:")]
        if not cands:
            cands = [m for m in t["messages"] if "SENT" in m.get("labelIds", [])]
        if not cands:
            continue
        msg = cands[0]
        edate = date_from_subject(msg["subject"])
        if edate is None or edate in seen_dates:
            continue
        seen_dates.add(edate)
        picks = parse_brief_html(msg["htmlBody"], edate, "sent", msg["id"])
        out.extend(picks)
        print(f"  sent thread {f.split('/')[-1][:40]}...: {edate.date()} -> {len(picks)} picks")
    return out


def _dedup(df: pd.DataFrame) -> pd.DataFrame:
    # same symbol+market+date might appear in both the combined "Screener"
    # table and a screener-specific table (e.g. Darvas Breakouts) -- keep
    # first occurrence (Screener table, walked first)
    return df.drop_duplicates(subset=["symbol", "market", "entry_date"], keep="first")


def run_incremental(input_json: Path) -> None:
    """Daily-monitoring entry point. `input_json` is a JSON array of
    {subject, date, htmlBody, id, kind: "draft"|"sent"} — freshly fetched by
    the calling agent this run, NOT the one-time saved investigation files.
    Only calendar dates not already present in OUT are parsed and appended;
    everything else is a silent no-op so this is safe to run daily forever."""
    entries = json.loads(input_json.read_text())
    existing = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(columns=["entry_date"])
    known_dates = set(pd.to_datetime(existing["entry_date"]).dt.normalize()) if len(existing) else set()

    new_rows = []
    seen_this_run = set()
    for e in entries:
        subj = e.get("subject", "")
        edate = date_from_subject(subj)
        if edate is None:
            continue
        edate = edate.normalize()
        if edate in known_dates:
            continue  # already have this calendar date, from any prior run
        # within this run, prefer sent over draft, and the latest timestamp otherwise
        key = edate
        if key in seen_this_run:
            continue
        html = e.get("htmlBody")
        if not html:
            continue
        rows = parse_brief_html(html, edate, e.get("kind", "unknown"), e.get("id", ""))
        if rows:
            new_rows.extend(rows)
            seen_this_run.add(key)

    if not new_rows:
        print(f"  no new dates found (already have {len(known_dates)} calendar dates)")
        return

    new_df = _dedup(pd.DataFrame(new_rows))
    merged = pd.concat([existing, new_df], ignore_index=True) if len(existing) else new_df
    merged = _dedup(merged)
    merged.to_parquet(OUT, index=False)
    added_dates = sorted(d.date().isoformat() for d in new_df["entry_date"].unique())
    print(f"  added {len(new_df)} picks across {len(added_dates)} new date(s): {added_dates}")
    print(f"  -> {OUT}  ({len(merged)} rows total, {len(known_dates)+len(added_dates)} calendar dates)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--incremental-json", type=str, default=None,
                    help="daily-monitoring mode: path to a JSON array of freshly "
                         "fetched {subject,date,htmlBody,id,kind} entries; only "
                         "genuinely new calendar dates are parsed and appended")
    a = ap.parse_args()

    if a.incremental_json:
        run_incremental(Path(a.incremental_json))
        return

    all_rows = load_drafts() + load_sent_threads()
    df = pd.DataFrame(all_rows)
    if df.empty:
        print("  no rows parsed"); return
    before = len(df)
    df = _dedup(df)
    print(f"\n  {before} raw rows -> {len(df)} after in-date dedup")
    print(f"  date range: {df['entry_date'].min().date()} -> {df['entry_date'].max().date()}")
    print(f"  dates covered: {sorted(d.date().isoformat() for d in df['entry_date'].unique())}")
    print(f"  market counts:\n{df['market'].value_counts().to_string()}")
    print(f"  unknown-market rows (mkt=='??'): {(df['market']=='??').sum()}")

    df.to_parquet(OUT, index=False)
    print(f"\n  -> {OUT}  ({len(df)} rows)")


if __name__ == "__main__":
    main()
