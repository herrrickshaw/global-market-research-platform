#!/usr/bin/env python3
"""
collect_nse_index_membership.py — which stock sits in which NSE index.

WHY THIS IS WORTH HAVING. The platform keeps inventing filters and then asking
whether the names that pass are any good. NSE already publishes ~164 indices,
many of them FACTOR indices (Momentum 30, Quality 30, Value 20, Alpha 50, Low
Volatility 50) built by a written, auditable rulebook and marked to market daily.
That makes them a free benchmark: if a screen's picks look nothing like the
matching NSE factor index, that is a question worth answering — either the screen
found something the index misses, or it is measuring something else entirely.

Membership is also a liquidity/quality prior in its own right. Index inclusion
requires a listing history, 100% trading frequency, a turnover floor and an
impact-cost ceiling, so "is it in NIFTY 500" encodes an eligibility screen the
platform would otherwise have to rebuild from bhavcopy.

SOURCE. nsearchives.nseindia.com/content/indices/ind_<slug>list.csv — plain CSVs
carrying Company Name, Industry, Symbol, Series, ISIN Code. 🔴 Deliberately NOT
the quote API: www.nseindia.com/api/quote-equity is 403-gated even with primed
cookies (measured 2026-08-17), while nsearchives serves these unauthenticated
and is the same host the bhavcopy collector already uses — which the GitHub
Actions probe proved reachable from cloud runners.

🔴 ONLY ~30 OF 164 INDICES PUBLISH A CONSTITUENT CSV, and the gap is not random.
Measured 2026-08-17 against the union of two close-all files:

    30   downloadable   broad-market (Nifty 50/100/200/500, Midcap, Smallcap)
                        and the older sector indices (Bank, IT, Auto, FMCG…)
    38   NOT published  FACTOR/strategy — Momentum 30, Quality 30, Value 50,
                        Alpha 50, the Alpha-Quality-Low-Volatility family
    74   NOT published  newer sector (Capital Goods, Chemicals, Cement, Capital
                        Markets) and derivative indices (Arbitrage, Futures, 1D Rate)
    22   n/a            debt/G-Sec, REIT/InvIT, India VIX — no equity members

Every naming variant was probed and 404s: ind_nifty200quality30list.csv,
…_list.csv, ind_niftyquality30list.csv, and the same on niftyindices.com
/IndexConstituent/ (which answers 200 with an HTML page, not a CSV — a 200 that
is not data, so a status-code check alone would record it as success).

That matters for how these are used: the FACTOR indices — the ones directly
comparable to this repo's own screens — are exactly the ones whose holdings are
not free. Their RULES are public though (see below), so they can be reproduced
rather than downloaded.

NSE FACTOR METHODOLOGY, for comparison against this repo's screens:
  * Momentum  (Nifty200 Momentum 30) — normalised momentum score from 6M and 12M
    price return, ADJUSTED FOR VOLATILITY; top 30 of the Nifty 200.
  * Quality   (Nifty200 Quality 30)  — ROE, debt/equity, and EPS growth
    VARIABILITY over the previous 5 years.
  * Value     (Nifty500 Value 50)    — E/P, B/P and S/P.
  * Weighting — factor score × free-float market cap, not equal weight.
  * Eligibility — impact cost <= 0.50% for 90% of observations over 6 months on a
    Rs 10 crore portfolio. This is a stricter, better-specified liquidity gate
    than a turnover floor, and is worth adopting directly.
  * Rebalance — semi-annual, cut-offs 31 Jan / 31 Jul, on 6-month average data.
    Any comparison of a screen against these must respect that cadence; ranking
    monthly against a semi-annually-rebalanced index measures two different things.

    python3 collect_nse_index_membership.py --from-close-file ~/Downloads/ind_close_all_*.csv
    python3 collect_nse_index_membership.py --report
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import io
import os
import re
import subprocess
import sys
import time

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
      "Referer": "https://www.nseindia.com/"}
BASE = "https://nsearchives.nseindia.com/content/indices/ind_{}list.csv"
DB = "market_data"
TABLE = "indices.nse_membership"

DDL = f"""
CREATE SCHEMA IF NOT EXISTS indices;
CREATE TABLE IF NOT EXISTS {TABLE} (
    index_name   text NOT NULL,
    symbol       text NOT NULL,
    company      text,
    industry     text,
    isin         text,
    series       text,
    fetched_at   timestamptz DEFAULT now(),
    PRIMARY KEY (index_name, symbol)
);
CREATE INDEX IF NOT EXISTS idx_nse_membership_symbol ON {TABLE}(symbol);
"""


def log(m: str) -> None:
    print(f"{dt.datetime.now():%H:%M:%S}  {m}", flush=True)


def psql(sql: str, fetch: bool = False) -> str:
    r = subprocess.run(["psql", "-d", DB, "-tAq", "-v", "ON_ERROR_STOP=1", "-c", sql],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"psql: {r.stderr.strip()[:300]}")
    return r.stdout.strip() if fetch else ""


def q(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def slug(name: str) -> str:
    """'Nifty Midcap 150' -> 'niftymidcap150'. Verified against 6 known indices."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# ── niftyindices.com route: the one that reaches the factor indices ──────────
#
# 🔴 THE FILENAME CANNOT BE DERIVED, SO DO NOT TRY. nsearchives uses
# `ind_nifty50list.csv` (lowercase, "list" suffix); niftyindices.com uses
# `ind_Nifty50_Value20.csv` — CamelCase, underscores, no suffix — and the two do
# not agree on where the underscore goes: ind_Nifty200_Momentum30.csv is a 404
# while ind_Nifty50_Value20.csv is real. Guessing produced 100% failures across
# every variant tried.
#
# 🔴 AND A 404 HERE ANSWERS 200. niftyindices.com serves its not-found page with
# HTTP 200 and a text/html body, so `r.status_code == 200` is not evidence of a
# file — the header must be checked. That is why the first sweep recorded 134
# indices as "no constituent file" when some of them do publish one.
#
# So: read the link off each index page. One extra request per index, and it is
# correct by construction rather than by pattern-matching luck.

NIFTY_BASE = "https://www.niftyindices.com"
CATEGORIES = ("broad-based-indices", "sectoral-indices", "strategy-indices",
              "thematic-indices")


def discover_index_pages(polite: float = 0.6) -> list[str]:
    """Every /indices/equity/<category>/<slug> page linked from the site."""
    seen: set[str] = set()
    for src in (f"{NIFTY_BASE}/reports/daily-reports",
                *(f"{NIFTY_BASE}/indices/equity/{c}" for c in CATEGORIES)):
        try:
            r = requests.get(src, headers=UA, timeout=45)
            time.sleep(polite)
        except Exception:                                          # noqa: BLE001
            continue
        if r.status_code != 200:
            continue
        seen |= {m for m in re.findall(r'/indices/equity/[A-Za-z-]+/[A-Za-z0-9\-]+', r.text)}
    return sorted(seen)


def constituent_url(page_path: str, polite: float = 0.5) -> str | None:
    """Pull the IndexConstituent CSV link out of one index page."""
    try:
        r = requests.get(f"{NIFTY_BASE}{page_path}", headers=UA, timeout=45)
    except Exception:                                              # noqa: BLE001
        return None
    finally:
        time.sleep(polite)
    if r.status_code != 200:
        return None
    m = re.search(r'https?://[^"\']*/IndexConstituent/[^"\']+\.csv', r.text, re.I)
    return m.group(0) if m else None


def fetch_csv(url: str, polite: float = 0.5) -> pd.DataFrame | None:
    try:
        r = requests.get(url, headers=UA, timeout=45)
    except Exception:                                              # noqa: BLE001
        return None
    finally:
        time.sleep(polite)
    # Header check, NOT status check — see the note above.
    if r.status_code != 200 or "Symbol" not in r.text[:400]:
        return None
    d = pd.read_csv(io.StringIO(r.text))
    d.columns = [c.strip() for c in d.columns]
    return d if "Symbol" in d.columns else None


def collect_niftyindices() -> None:
    """Walk every index page and store whatever constituent list it publishes."""
    psql(DDL)
    pages = discover_index_pages()
    log(f"{len(pages)} index pages discovered across {len(CATEGORIES)} categories")
    got = rows = 0
    nolist: list[str] = []
    for i, p in enumerate(pages, 1):
        name = p.rsplit("/", 1)[-1]
        url = constituent_url(p)
        d = fetch_csv(url) if url else None
        if d is None or d.empty:
            nolist.append(name)
            continue
        # Index name from the CSV filename, which is NSE's own label for it.
        idx = re.sub(r"^ind_|\.csv$", "", url.rsplit("/", 1)[-1])
        vals = ",".join(
            f"({q(idx)},{q(str(r.Symbol).strip().upper())},{q(getattr(r,'Company_Name',None))},"
            f"{q(getattr(r,'Industry',None))},{q(getattr(r,'ISIN_Code',None))},"
            f"{q(getattr(r,'Series',None))},now())"
            for r in d.rename(columns=lambda c: c.replace(" ", "_")).itertuples())
        psql(f"INSERT INTO {TABLE} (index_name,symbol,company,industry,isin,series,fetched_at) "
             f"VALUES {vals} ON CONFLICT (index_name,symbol) DO UPDATE SET "
             f"company=EXCLUDED.company, industry=EXCLUDED.industry, isin=EXCLUDED.isin, "
             f"series=EXCLUDED.series, fetched_at=EXCLUDED.fetched_at")
        got += 1
        rows += len(d)
        if i % 20 == 0:
            log(f"  {i}/{len(pages)}  with-list={got} rows={rows} no-list={len(nolist)}")
    log(f"niftyindices: {got} indices with constituents, {rows:,} memberships, "
        f"{len(nolist)} without")
    if nolist:
        log(f"  no list published: {', '.join(nolist[:12])}"
            + (f" … +{len(nolist)-12}" if len(nolist) > 12 else ""))


def index_names(close_files: list[str]) -> list[str]:
    """Index universe from NSE's daily close-all files.

    🔴 UNION, NOT THE NEWEST FILE. Measured 2026-08-17: that day's close-all
    carried 146 indices while 14-08 carried 164 — a strict subset, 18 missing
    (Nifty Capital Goods, Insurance, NBFC, Power among them) and none added.
    Taking only the latest file would silently drop a tenth of the universe, and
    nothing in the file says it is partial.
    """
    names: set[str] = set()
    for f in close_files:
        d = pd.read_csv(f)
        d.columns = [c.strip() for c in d.columns]
        names |= set(d["Index Name"].astype(str).str.strip())
    return sorted(n for n in names if n and n.lower() != "nan")


def fetch_index(name: str, polite: float = 0.7) -> pd.DataFrame | None:
    url = BASE.format(slug(name))
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as exc:                                       # noqa: BLE001
        log(f"  {name}: {type(exc).__name__}")
        return None
    finally:
        time.sleep(polite)
    if r.status_code != 200 or "Symbol" not in r.text[:400]:
        return None
    d = pd.read_csv(io.StringIO(r.text))
    d.columns = [c.strip() for c in d.columns]
    if "Symbol" not in d.columns:
        return None
    d["index_name"] = name
    return d


def collect(close_files: list[str]) -> None:
    psql(DDL)
    names = index_names(close_files)
    log(f"{len(names)} indices in the union of {len(close_files)} close-all file(s)")
    got = miss = rows = 0
    missing: list[str] = []
    for i, n in enumerate(names, 1):
        d = fetch_index(n)
        if d is None or d.empty:
            miss += 1
            missing.append(n)
            continue
        vals = ",".join(
            f"({q(n)},{q(str(r.Symbol).strip().upper())},{q(getattr(r,'Company_Name',None) or getattr(r,'_1',None))},"
            f"{q(getattr(r,'Industry',None))},{q(getattr(r,'ISIN_Code',None))},{q(getattr(r,'Series',None))},now())"
            for r in d.rename(columns=lambda c: c.replace(" ", "_")).itertuples())
        psql(f"INSERT INTO {TABLE} (index_name,symbol,company,industry,isin,series,fetched_at) "
             f"VALUES {vals} ON CONFLICT (index_name,symbol) DO UPDATE SET "
             f"company=EXCLUDED.company, industry=EXCLUDED.industry, "
             f"isin=EXCLUDED.isin, series=EXCLUDED.series, fetched_at=EXCLUDED.fetched_at")
        got += 1
        rows += len(d)
        if i % 20 == 0:
            log(f"  {i}/{len(names)}  indices={got} rows={rows} no-list={miss}")
    log(f"collected {got} indices, {rows:,} memberships, {miss} without a constituent file")
    if missing:
        # Named, not just counted: an index with no downloadable list is usually
        # a derived/strategy index whose members NSE does not publish this way —
        # worth knowing which, rather than reading the gap as a fetch failure.
        log(f"  no constituent file: {', '.join(missing[:15])}"
            + (f" … +{len(missing)-15} more" if len(missing) > 15 else ""))


def report() -> None:
    print(psql(f"""
      SELECT 'indices: '||count(DISTINCT index_name)||'   unique symbols: '||
             count(DISTINCT symbol)||'   memberships: '||count(*) FROM {TABLE}""", fetch=True))
    print("\n  largest indices:")
    print(psql(f"""SELECT '   '||rpad(index_name,34)||lpad(count(*)::text,5)
                   FROM {TABLE} GROUP BY index_name ORDER BY count(*) DESC LIMIT 10""", fetch=True))
    print("\n  most-indexed stocks (a membership count is a crude quality/liquidity prior):")
    print(psql(f"""SELECT '   '||rpad(symbol,16)||lpad(count(*)::text,4)||'  '||
                   left(string_agg(index_name,', ' ORDER BY index_name),70)
                   FROM {TABLE} GROUP BY symbol ORDER BY count(*) DESC LIMIT 8""", fetch=True))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from-close-file", nargs="*", default=[],
                   help="NSE ind_close_all_*.csv files; union is used")
    p.add_argument("--report", action="store_true")
    p.add_argument("--niftyindices", action="store_true",
                   help="walk niftyindices.com index pages — the only route that "
                        "reaches the factor/strategy indices")
    a = p.parse_args()
    if a.report:
        report(); return 0
    if a.niftyindices:
        collect_niftyindices(); report(); return 0
    files = [f for pat in (a.from_close_file or
                           [os.path.expanduser("~/Downloads/ind_close_all_*.csv")])
             for f in glob.glob(pat)]
    if not files:
        log("no close-all files found"); return 1
    collect(files)
    report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
