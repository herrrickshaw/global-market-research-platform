#!/usr/bin/env python3
"""
nse_xbrl_eps.py — stock-level quarterly EPS from NSE XBRL filings.

WHY. Three separate things were blocked today by the absence of stock-level
fundamental HISTORY: fundamental exclusions in smallcap_screener.py, the
Bhojraj-Lee warranted-multiple peer construction, and any P/E band that needs a
stock's own past. `fundamentals.ratios` is a single fiscal year and
`IN_current.parquet` starts 2021 — neither reaches back far enough. The filings
do: 122,457 of the 152,879 index rows carry a real XBRL link, deduping to
**55,223 unique (symbol, fiscal year, quarter)** across 2,680 symbols.

🔴 CONTEXTS ARE THE WHOLE PROBLEM. An XBRL document states the same concept many
times over different periods — this quarter, year-to-date, the prior-year
quarter, the full prior year — distinguished only by `contextRef`. Grabbing the
first `BasicEarningsPerShare` element returns whichever the vendor happened to
serialise first, which is frequently the YEAR-TO-DATE or PRIOR-YEAR figure. A
Q3 YTD EPS is ~3x the quarterly one, so that error does not look like an error
downstream — it looks like a cheap stock. Every fact here is resolved through
its context and kept only when the period is 80-100 days long, i.e. an actual
quarter.

DUPLICATE FILINGS: a symbol files consolidated AND standalone, plus revisions.
Consolidated is preferred where both exist (it is what the market prices), and
ties break to the LATEST filing timestamp.

Usage:
  python3 scripts/nse_xbrl_eps.py --parse-local     # parse what is on disk
  python3 scripts/nse_xbrl_eps.py --fetch           # download missing XMLs
  python3 scripts/nse_xbrl_eps.py --status
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import duckdb
import pandas as pd

CACHE = Path("/Users/umashankar/market-pipeline/market_cache/nse_xbrl")
XMLDIR = CACHE / "xml"
INDEX = CACHE / "results_index.parquet"
DSN = "dbname=market_data host=/tmp user=umashankar"
SCHEMA = "fundamentals"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
WORKERS = 8

# 🔴 THREE FILING FORMATS, THREE VOCABULARIES. The results index mixes them and
# a single tag list silently yields ~0.5%:
#   INDAS      (9,072 local) BasicEarningsLossPerShareFrom*Operations
#   BANKING/NBFC/NONINDAS    BasicEarningsPerShare*ExtraordinaryItems
#   INTEGRATED (5,281 local) NOT A RESULTS FILING AT ALL — it is the corporate
#              governance report (board composition, director appointments,
#              committee meeting dates). 100 distinct tags, zero financial ones.
#              Excluded by prefix rather than left to fail parsing, so the
#              "unusable" count means something.
EPS_TAGS = ("BasicEarningsPerShareAfterExtraordinaryItems",
            "BasicEarningsPerShareBeforeExtraordinaryItems",
            "BasicEarningsLossPerShareFromContinuingOperations",
            "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
            "BasicEarningsLossPerShare")
NON_FINANCIAL_PREFIXES = ("INTEGRATED_",)
PAT_TAGS = ("ProfitLossForThePeriod",
            "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",
            "ProfitLossFromOrdinaryActivitiesAfterTax")
REV_TAGS = ("RevenueFromOperations", "Income", "TotalIncome")

DDL = f"""
CREATE SCHEMA IF NOT EXISTS pg."{SCHEMA}";
CREATE TABLE IF NOT EXISTS pg."{SCHEMA}".india_quarterly (
  symbol VARCHAR, period_start DATE, period_end DATE, consolidated BOOLEAN,
  eps DOUBLE, pat DOUBLE, revenue DOUBLE, filing_date TIMESTAMP, src VARCHAR
);
"""


def local_index() -> pd.DataFrame:
    d = pd.read_parquet(INDEX, columns=["symbol", "filingDate", "financialYear",
                                        "relatingTo", "consolidated", "xbrl"])
    d["fn"] = d.xbrl.str.rsplit("/", n=1).str[-1]
    d = d[d.fn.str.endswith(".xml", na=False)].copy()
    d = d[~d.fn.str.startswith(NON_FINANCIAL_PREFIXES)]
    d["filing_ts"] = pd.to_datetime(d.filingDate, format="mixed", errors="coerce")
    d = d.sort_values("filing_ts")
    # consolidated preferred, then latest filing
    d["cons"] = d.consolidated.astype(str).str.contains("Non", case=False) == False
    d = (d.sort_values(["cons", "filing_ts"])
           .drop_duplicates(["symbol", "financialYear", "relatingTo"], keep="last"))
    return d


def parse_one(path: Path):
    """EPS/PAT/revenue for the QUARTER, resolved through contextRef."""
    try:
        root = ET.parse(path).getroot()
    except Exception:                                     # noqa: BLE001
        return None
    # contextRef -> (start, end); instants are ignored, we want durations
    ctx = {}
    for c in root.iter():
        if not c.tag.endswith("}context"):
            continue
        cid = c.get("id")
        s = e = None
        for x in c.iter():
            if x.tag.endswith("}startDate"):
                s = x.text
            elif x.tag.endswith("}endDate"):
                e = x.text
        if cid and s and e:
            try:
                ctx[cid] = (dt.date.fromisoformat(s.strip()),
                            dt.date.fromisoformat(e.strip()))
            except Exception:                             # noqa: BLE001
                pass
    if not ctx:
        return None

    def pick(tags):
        """Value whose context is 80-100 days long — a real quarter, never YTD."""
        best = None
        for el in root.iter():
            local = el.tag.rsplit("}", 1)[-1]
            if local not in tags or not (el.text or "").strip():
                continue
            per = ctx.get(el.get("contextRef"))
            if not per:
                continue
            days = (per[1] - per[0]).days
            if not (80 <= days <= 100):
                continue
            try:
                v = float(el.text.strip())
            except ValueError:
                continue
            # latest-ending quarter present in the document
            if best is None or per[1] > best[2]:
                best = (v, per[0], per[1])
        return best

    eps = pick(EPS_TAGS)
    if eps is None:
        return None
    pat = pick(PAT_TAGS)
    rev = pick(REV_TAGS)
    return {"eps": eps[0], "period_start": eps[1], "period_end": eps[2],
            "pat": pat[0] if pat else None,
            "revenue": rev[0] if rev else None}


def parse_local(a) -> int:
    idx = local_index()
    have = set(os.listdir(XMLDIR))
    todo = idx[idx.fn.isin(have)]
    print(f"{len(idx):,} unique filings · {len(todo):,} present locally", flush=True)
    rows, bad = [], 0
    for k, r in enumerate(todo.itertuples(), 1):
        got = parse_one(XMLDIR / r.fn)
        if not got:
            bad += 1
            continue
        rows.append({"symbol": r.symbol, **got,
                     "consolidated": bool(r.cons),
                     "filing_date": r.filing_ts, "src": r.fn})
        if k % 2000 == 0:
            print(f"  {k:,}/{len(todo):,} · {len(rows):,} parsed · {bad:,} unusable",
                  flush=True)
    if not rows:
        print("nothing parsed"); return 1
    df = pd.DataFrame(rows)
    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")
    for s in filter(None, (x.strip() for x in DDL.split(";"))):
        con.execute(s)
    con.register("inc", df)
    con.execute(f'DELETE FROM pg."{SCHEMA}".india_quarterly WHERE src IN '
                "(SELECT DISTINCT src FROM inc)")
    con.execute(f'INSERT INTO pg."{SCHEMA}".india_quarterly '
                "SELECT symbol,period_start,period_end,consolidated,eps,pat,"
                "revenue,filing_date,src FROM inc")
    print(f"\nparsed {len(df):,} quarters · {df.symbol.nunique():,} symbols · "
          f"{bad:,} unusable")
    print(f"period_end {df.period_end.min()} -> {df.period_end.max()}")
    return 0


def fetch(a) -> int:
    idx = local_index()
    have = set(os.listdir(XMLDIR))
    todo = idx[~idx.fn.isin(have)]
    if a.limit:
        todo = todo.head(a.limit)
    print(f"{len(todo):,} XMLs to fetch", flush=True)

    def one(r):
        try:
            req = urllib.request.Request(r.xbrl, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as rr:
                b = rr.read()
            if b[:5] != b"<?xml":
                return 0
            (XMLDIR / r.fn).write_bytes(b)
            return 1
        except Exception:                                 # noqa: BLE001
            return 0
    ok = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(one, r) for r in todo.itertuples()]
        for k, f in enumerate(as_completed(futs), 1):
            ok += f.result()
            if k % 1000 == 0:
                print(f"  {k:,}/{len(todo):,} · {ok:,} saved", flush=True)
    print(f"\nfetched {ok:,} of {len(todo):,}")
    return 0


def status(a) -> int:
    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")
    try:
        n, s, mn, mx = con.execute(
            f'SELECT count(*), count(DISTINCT symbol), min(period_end), '
            f'max(period_end) FROM pg."{SCHEMA}".india_quarterly').fetchone()
    except Exception as e:                                # noqa: BLE001
        print(f"table absent: {str(e)[:80]}"); return 1
    print(f"india_quarterly: {n:,} rows · {s:,} symbols · {mn} -> {mx}")
    r = con.execute(f'''SELECT extract(year from period_end) y, count(*) n,
        count(DISTINCT symbol) s FROM pg."{SCHEMA}".india_quarterly
        GROUP BY 1 ORDER BY 1''').fetchall()
    for y, nn, ss in r:
        print(f"   {int(y)}  {nn:>6,} quarters  {ss:>5,} symbols")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parse-local", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.fetch:
        return fetch(a)
    if a.parse_local:
        return parse_local(a)
    return status(a)


if __name__ == "__main__":
    sys.exit(main())
