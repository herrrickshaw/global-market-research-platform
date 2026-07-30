#!/usr/bin/env python3
"""
nse_index_factsheets.py — NIFTY monthly index factsheets: discover, fetch, parse.

WHAT THEY CONTAIN (the two the user supplied, ind_nifty50.pdf / ind_nifty_it.pdf):
per index, per month — description and methodology, launch/base dates, number of
constituents, price returns over several horizons, standard deviation, beta and
correlation vs NIFTY 50, **P/E, P/B, dividend yield**, **sector weights**, and
**top constituents by weight**. Nothing else in this warehouse carries index
sector composition or index-level beta.

🔴 TWO TRAPS, both of which produce silently wrong results:

  1. **HTTP 200 DOES NOT MEAN THE FILE EXISTS.** niftyindices.com is a single-page
     app that answers ANY unmatched path with its 77,788-byte HTML shell and a
     200 status. Probing `ind_nifty50_30062026.pdf`, `Factsheet/2026/...`,
     `Factsheet/Archive/...` all "succeed" that way. Every fetch here is
     validated on the `%PDF` magic bytes; status code is ignored.
  2. **THERE IS NO DATED ARCHIVE.** Only the CURRENT month is published, under a
     stable filename. So this is a SNAPSHOT collector: run monthly and history
     accumulates going forward, but the past cannot be reconstructed. It does
     NOT solve point-in-time constituents (see nse_index_tri.py's note) — the
     factsheets carry only TOP constituents by weight, not full membership.

FILENAMES ARE NOT A PREDICTABLE SLUG. `ind_nifty50.pdf` and `ind_nifty_it.pdf`
exist; `ind_nifty500.pdf`, `ind_niftynext50.pdf` and `ind_niftysmallcap250.pdf`
do not. Sectoral indices tend to `ind_nifty_<sector>.pdf`, broad ones vary. No
listing page or JS manifest exposes the real set, so this generates several slug
candidates per index name from `indices.nse_daily` and keeps whichever returns
actual PDF bytes. Discovered names are cached so later runs skip the misses.

Usage:
  python3 scripts/nse_index_factsheets.py --discover     # find valid filenames
  python3 scripts/nse_index_factsheets.py --fetch        # download + parse
  python3 scripts/nse_index_factsheets.py --status
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import pg_client

DSN = "dbname=market_data host=/tmp user=umashankar"
SCHEMA = "indices"
BASE = "https://www.niftyindices.com/Factsheet/{fn}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CACHE = Path.home() / ".local" / "state" / "nse_factsheet_names.json"
PDFDIR = Path.home() / "market-pipeline" / "data" / "nse_factsheets"
WORKERS = 6

# Native Postgres DDL for pg_client.ensure_schema() — no `pg.` ATTACH-alias
# prefix, Postgres type names (DOUBLE PRECISION not DuckDB's bare DOUBLE).
DDL = f"""
CREATE SCHEMA IF NOT EXISTS "{SCHEMA}";
CREATE TABLE IF NOT EXISTS "{SCHEMA}".factsheet_meta (
  index_name VARCHAR, as_of DATE, filename VARCHAR, n_constituents INTEGER,
  pe DOUBLE PRECISION, pb DOUBLE PRECISION, div_yield DOUBLE PRECISION,
  fetched_at TIMESTAMP  -- pb/div_yield ALWAYS NULL: see parse()
);
CREATE TABLE IF NOT EXISTS "{SCHEMA}".factsheet_sector (
  index_name VARCHAR, as_of DATE, sector VARCHAR, weight_pct DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS "{SCHEMA}".factsheet_holding (
  index_name VARCHAR, as_of DATE, company VARCHAR, weight_pct DOUBLE PRECISION
);
"""


def slugs(name: str):
    """Candidate filenames for one index name — the naming is inconsistent, so
    try the observed shapes rather than assuming one."""
    n = name.lower().replace("&", "and")
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    parts = [p for p in n.split() if p]
    if parts and parts[0] == "nifty":
        parts = parts[1:]
    joined, under = "".join(parts), "_".join(parts)
    out = [f"ind_nifty{joined}.pdf", f"ind_nifty_{under}.pdf",
           f"ind_nifty{under}.pdf", f"ind_nifty_{joined}.pdf"]
    seen, uniq = set(), []
    for s in out:
        if s not in seen:
            seen.add(s); uniq.append(s)
    return uniq


def get_url(u: str) -> bytes | None:
    """Bytes if really a PDF, else None. Status code is NOT trusted."""
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            b = r.read()
        return b if b[:4] == b"%PDF" else None
    except Exception:                                    # noqa: BLE001
        return None


def get_pdf(fn: str) -> bytes | None:
    """Bytes if it is really a PDF, else None. Status code is NOT trusted."""
    try:
        req = urllib.request.Request(BASE.format(fn=fn), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            b = r.read()
        return b if b[:4] == b"%PDF" else None
    except Exception:                                    # noqa: BLE001
        return None


def connect():
    pg_client.connect()
    pg_client.ensure_schema([s.strip() for s in DDL.split(";") if s.strip()])
    return pg_client.get_connection()


def index_names(con):
    with con.cursor() as cur:
        cur.execute(f'SELECT DISTINCT index_name FROM "{SCHEMA}".nse_daily ORDER BY 1')
        return [r[0] for r in cur.fetchall()]


LISTING = "https://www.niftyindices.com/reports/index-factsheet"


def discover(con) -> int:
    """Scrape the official factsheet listing page — do NOT guess filenames.

    🔴 Slug generation was the wrong approach and found only 37 of 173. Three
    reasons it could never have worked: filenames are MIXED CASE
    (`ind_Nifty_Smallcap_250.pdf`, not the lowercase every candidate assumed),
    there are at least four unrelated conventions in use side by side
    (`ind_nifty_bank.pdf`, `Factsheet_NIFTY100_ESG_Index.pdf`,
    `FactsheetNIFTY500Value50.pdf`, `Factsheet_MultiAsset..._50202010.pdf`),
    and the set is LARGER than the daily-archive index list — 254 factsheets
    against 173 indices, because many published indices never appear in the
    daily close file. The listing page enumerates all of them.
    """
    req = urllib.request.Request(LISTING, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", errors="replace")
    hrefs = re.findall(r'href="([^"]*/Factsheet/[^"]+\.pdf)"', html, re.I)
    hrefs += [f"https://www.niftyindices.com/Factsheet/{m}" for m in
              re.findall(r'["\'/]([A-Za-z0-9_&.-]+\.pdf)["\'<]', html)
              if "/" not in m]
    seen, urls = set(), []
    for h in hrefs:
        u = h if h.startswith("http") else "https://www.niftyindices.com" + h
        u = u.replace("//Factsheet", "/Factsheet")
        fn = u.rsplit("/", 1)[-1]
        if fn.lower() in seen:
            continue
        seen.add(fn.lower()); urls.append((fn, u))
    print(f"listing page exposes {len(urls)} candidate factsheets", flush=True)

    found = {}
    def probe(item):
        fn, u = item
        try:
            rq = urllib.request.Request(u, headers={"User-Agent": UA})
            with urllib.request.urlopen(rq, timeout=45) as rr:
                b = rr.read()
            return (fn, u) if b[:4] == b"%PDF" else None
        except Exception:                                # noqa: BLE001
            return None
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for k, f in enumerate(as_completed([ex.submit(probe, i) for i in urls]), 1):
            r2 = f.result()
            if r2:
                found[r2[0]] = r2[1]
            if k % 40 == 0:
                print(f"  {k}/{len(urls)} probed · {len(found)} real PDFs", flush=True)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(found, indent=1, sort_keys=True))
    print(f"\n{len(found)} of {len(urls)} candidates are real PDFs -> {CACHE}")
    return 0


NUM = r"(-?\d+(?:\.\d+)?)"


def parse(b: bytes, index_name: str, fn: str) -> dict:
    from pypdf import PdfReader
    import io
    r = PdfReader(io.BytesIO(b))
    txt = "\n".join(p.extract_text() or "" for p in r.pages)
    out = {"index_name": index_name, "filename": fn, "sectors": [], "holdings": []}
    # 🔴 The as-of date must come from the FIRST LINE and be sanity-bounded.
    # Bond factsheets carry a MATURITY year in the index name
    # (Nifty_GSecJun2036Index), and a loose search over the first 200 chars
    # happily returned 2036-06-30 as the "as of" date. Anything outside a
    # plausible publication window is rejected rather than stored.
    out["as_of"] = None
    today = pd.Timestamp.today().normalize()
    for line in txt.split("\n")[:4]:
        m = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", line)
        if not m:
            continue
        try:
            d0 = pd.to_datetime(m.group(1))
        except Exception:                                # noqa: BLE001
            continue
        if today - pd.Timedelta(days=400) <= d0 <= today + pd.Timedelta(days=40):
            out["as_of"] = d0.date()
            break
    # 🔴 DO NOT parse P/E, P/B or dividend yield from these PDFs. The text
    # extraction scrambles the Fundamentals block — the number following the
    # literal "Dividend Yield" label is actually P/B. Validated against
    # indices.nse_daily on 8 indices: the parsed "div_yield" equalled the
    # archive's pb EXACTLY every time, while parsed P/E matched P/E exactly.
    # The daily archive is authoritative for all three, so they are read from
    # there and the factsheet contributes only what is unique to it: sector
    # weights, top holdings, and constituent count.
    mm = re.search(r"P/E\s*\n?\s*" + NUM, txt)
    out["pe"] = float(mm.group(1)) if mm else None
    out["pb"] = out["div_yield"] = None
    # 🔴 n_constituents is NOT parseable from these PDFs. The Portfolio
    # Characteristics block prints VALUES BEFORE THEIR LABELS after text
    # extraction ("1000 / 50 / Base Value / ... / No. of Constituents"), so
    # taking the nearest preceding number returns the BASE YEAR: ind_nifty50
    # read 1995, Smallcap 250 read 2005. Left NULL rather than shipping a
    # column of base dates labelled as constituent counts — the real count is
    # in the constituent CSVs (ind_nifty<index>list.csv) if it is needed.
    out["n_constituents"] = None
    sec = re.search(r"Sector Representation(.*?)(?:Top constituents|$)", txt, re.S)
    if sec:
        for line in sec.group(1).split("\n"):
            m2 = re.match(r"\s*([A-Za-z][A-Za-z ,&'\-\.]+?)\s+" + NUM + r"\s*$", line)
            if m2 and m2.group(1).strip().lower() not in ("sector", "weight"):
                out["sectors"].append((m2.group(1).strip(), float(m2.group(2))))
    hold = re.search(r"Top constituents by weightage(.*?)$", txt, re.S)
    if hold:
        for line in hold.group(1).split("\n"):
            m2 = re.match(r"\s*(.+?Ltd\.?)\s+" + NUM + r"\s*$", line)
            if m2:
                out["holdings"].append((m2.group(1).strip(), float(m2.group(2))))
    return out


def fetch(con) -> int:
    if not CACHE.exists():
        print("run --discover first"); return 1
    names = json.loads(CACHE.read_text())
    PDFDIR.mkdir(parents=True, exist_ok=True)
    meta, secs, holds = [], [], []
    for k, (fn, url) in enumerate(sorted(names.items()), 1):
        nm = fn
        b = get_url(url)
        if b is None:
            print(f"  {nm:32s} MISSING now"); continue
        (PDFDIR / fn).write_bytes(b)
        try:
            d = parse(b, nm, fn)
        except Exception as e:                            # noqa: BLE001
            print(f"  {nm:32s} parse failed: {str(e)[:40]}"); continue
        meta.append({k2: d.get(k2) for k2 in
                     ("index_name", "as_of", "filename", "n_constituents",
                      "pe", "pb", "div_yield")})
        secs += [{"index_name": nm, "as_of": d["as_of"], "sector": s, "weight_pct": w}
                 for s, w in d["sectors"]]
        holds += [{"index_name": nm, "as_of": d["as_of"], "company": c, "weight_pct": w}
                  for c, w in d["holdings"]]
        if k % 20 == 0:
            print(f"  {k}/{len(names)} parsed", flush=True)
        time.sleep(0.3)
    if not meta:
        print("nothing parsed"); return 1
    fetched_at = dt.datetime.now()
    for tbl, rows, cols in (
        ("factsheet_meta", meta, ["index_name", "as_of", "filename", "n_constituents",
                                  "pe", "pb", "div_yield", "fetched_at"]),
        ("factsheet_sector", secs, ["index_name", "as_of", "sector", "weight_pct"]),
        ("factsheet_holding", holds, ["index_name", "as_of", "company", "weight_pct"]),
    ):
        if not rows:
            continue
        df = pd.DataFrame(rows)
        if tbl == "factsheet_meta":
            df["fetched_at"] = fetched_at
        # Dedupe on index_name alone. (index_name, as_of) was the key and it
        # silently failed: as_of is NULL for factsheets whose header does not
        # parse, and `IN` never matches NULL, so nothing was deleted and every
        # re-run appended duplicates — 326 rows for 253 files.
        names = sorted(df.index_name.unique().tolist())
        out_rows = pg_client.to_rows(df, cols)
        pg_client.delete_and_insert(SCHEMA, tbl, "index_name = ANY(%s)",
                                    (names,), out_rows, cols)
        print(f"  {tbl}: {len(df):,} rows")
    print(f"\nPDFs cached in {PDFDIR}")
    return 0


def status(con) -> int:
    for t in ("factsheet_meta", "factsheet_sector", "factsheet_holding"):
        try:
            with con.cursor() as cur:
                cur.execute(f'SELECT count(*), max(as_of) FROM "{SCHEMA}".{t}')
                n, d = cur.fetchone()
            print(f"  {t:20s} {n:>6,} rows   latest {d}")
        except Exception:                                 # noqa: BLE001
            con.rollback()
            print(f"  {t:20s} absent")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    con = connect()
    if a.discover:
        return discover(con)
    if a.fetch:
        return fetch(con)
    return status(con)


if __name__ == "__main__":
    sys.exit(main())
