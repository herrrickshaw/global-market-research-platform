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

import pandas as pd

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import pg_client

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
# ORDER MATTERS — first match wins. The CONTINUING-AND-DISCONTINUED total must
# come first: a filing reports ContinuingOperations, DiscontinuedOperations and
# their TOTAL separately, and a company whose continuing line is 0.00 while the
# discontinued line carries the whole result (AHLUCONT Q1-FY25: 0.00 / 4.56 /
# 4.56) silently recorded 0.00 under the old ordering.
EPS_TAGS = ("BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
            "BasicEarningsPerShareAfterExtraordinaryItems",
            "BasicEarningsPerShareBeforeExtraordinaryItems",
            "BasicEarningsLossPerShareFromContinuingOperations",
            "BasicEarningsLossPerShare",
            "EarningPerShare")          # singular variant, 5 filings

# 🔴 NSE TAGS THE RESULTS TABLE BY COLUMN, NOT BY PERIOD. An Indian quarterly
# results table is: col 1 = current quarter, col 4 = year-to-date. The XBRL
# encodes that as contextRef "OneD" and "FourD" — and in some filings BOTH
# carry the SAME start/end dates, so a duration filter cannot separate them.
# AHLUCONT Q4-FY24 states 29.83 (OneD, the quarter) and 55.95 (FourD, the full
# year) both stamped 2024-01-01..2024-03-31. Sampling 300 filings, these two IDs
# are the ONLY ones carrying EPS facts (847 OneD / 646 FourD), so preferring
# OneD is not a heuristic here, it is the format.
QUARTER_CONTEXT_IDS = ("OneD",)
# 🔴 EXCLUDE ONLY THE GOVERNANCE SUBTYPE. "INTEGRATED_" as a blanket prefix was
# wrong and cost most of 2025-2026: NSE moved to an integrated filing format
# around 2025 and encodes the SUBTYPE in the filename —
#   INTEGRATED_FILING_INDAS_*       20,768  financial results
#   INTEGRATED_FILING_GOVERNANCE_*  16,654  board/committee disclosures only
#   INTEGRATED_FILING_NBFC_INDAS_*   1,491  financial
#   INTEGRATED_FILING_BANKING_*        411  financial
# Sampling a 2024 GOVERNANCE file and generalising to the whole class discarded
# ~22,900 results filings, which is why parsed coverage stopped at 2024-12 and
# LUPIN's TTM ran ~18 months stale (EPS 62.92 against screener.in's implied
# 124.1, i.e. a P/E of 38.3 against a true 19.3). Only GOVERNANCE is skipped now.
NON_FINANCIAL_PREFIXES = ("INTEGRATED_FILING_GOVERNANCE_",)
PAT_TAGS = ("ProfitLossForThePeriod",
            "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",
            "ProfitLossFromOrdinaryActivitiesAfterTax")
REV_TAGS = ("RevenueFromOperations", "Income", "TotalIncome")

DDL = f"""
CREATE SCHEMA IF NOT EXISTS "{SCHEMA}";
CREATE TABLE IF NOT EXISTS "{SCHEMA}".india_quarterly (
  symbol VARCHAR, period_start DATE, period_end DATE, consolidated BOOLEAN,
  eps DOUBLE PRECISION, pat DOUBLE PRECISION, revenue DOUBLE PRECISION,
  filing_date TIMESTAMP, src VARCHAR
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
    # 🔴 DO NOT PRE-DEDUPE ON INDEX METADATA. INTEGRATED filings carry
    # financialYear=None and relatingTo='Original'/'New', so the old key
    # (symbol, financialYear, relatingTo) collapsed EVERY integrated filing for
    # a symbol into ONE row — LUPIN's 19 filings since 2025 became 2, which is
    # why its TTM stayed pinned at 2024-12 and read EPS 62.92 against
    # screener.in's implied 124.1. Dedupe is deferred to AFTER parsing, on the
    # period_end the XML itself reports, which is the only reliable key.
    return d.drop_duplicates(subset=["fn"])


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

    # 🔴 DANGLING contextRef — the single biggest cause of "unusable". Many
    # filings reference `OneD`/`FourD` on the EPS fact while defining ONLY
    # concept-suffixed contexts (OneOperatingExpenses01D,
    # FourItemsThatWillNotBeReclassified01D, ...), so the plain ID resolves to
    # nothing and the fact is discarded. 1,003 of 1,009 EPS facts in a
    # 300-file failure sample died this way.
    # NSE prefixes every column-1 context with "One" and every column-4 with
    # "Four", and in 200 of 200 sampled failures ALL One* contexts shared
    # exactly ONE period — so the column prefix determines the period
    # unambiguously and a dangling ref can be resolved from its siblings.
    col_period: dict[str, set] = {}
    for cid, per in ctx.items():
        for pre in ("One", "Two", "Three", "Four", "Five"):
            if cid.startswith(pre):
                col_period.setdefault(pre, set()).add(per)
                break
    fallback = {pre: next(iter(v)) for pre, v in col_period.items() if len(v) == 1}
    for pre, per in fallback.items():
        ctx.setdefault(pre + "D", per)      # OneD, FourD, ...

    def pick(tags):
        """The CURRENT QUARTER value: right tag, quarter-length context, and
        the current-quarter COLUMN where the format distinguishes columns."""
        for tag in tags:                       # tag priority is meaningful
            cands = []
            for el in root.iter():
                if el.tag.rsplit("}", 1)[-1] != tag or not (el.text or "").strip():
                    continue
                cref = el.get("contextRef")
                per = ctx.get(cref)
                if not per or not (80 <= (per[1] - per[0]).days <= 100):
                    continue
                try:
                    v = float(el.text.strip())
                except ValueError:
                    continue
                cands.append((cref, v, per[0], per[1]))
            if not cands:
                continue
            preferred = [c for c in cands if c[0] in QUARTER_CONTEXT_IDS]
            pool = preferred or cands
            best = max(pool, key=lambda c: c[3])      # latest-ending
            return (best[1], best[2], best[3])
        return None

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
    # dedupe on the PARSED period: consolidated preferred, then latest filing
    df = (df.sort_values(["consolidated", "filing_date"])
            .drop_duplicates(["symbol", "period_end"], keep="last"))
    pg_client.connect()
    pg_client.ensure_schema([s.strip() for s in DDL.split(";") if s.strip()])
    cols = ["symbol", "period_start", "period_end", "consolidated", "eps",
            "pat", "revenue", "filing_date", "src"]
    srcs = sorted(df.src.unique().tolist())
    out_rows = [tuple(None if v != v else v for v in r)   # NaN -> NULL
                for r in df[cols].itertuples(index=False, name=None)]
    pg_client.delete_and_insert(SCHEMA, "india_quarterly", "src = ANY(%s)",
                                (srcs,), out_rows, cols)
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
    pg_client.connect()
    con = pg_client.get_connection()
    try:
        with con.cursor() as cur:
            cur.execute(
                f'SELECT count(*), count(DISTINCT symbol), min(period_end), '
                f'max(period_end) FROM "{SCHEMA}".india_quarterly')
            n, s, mn, mx = cur.fetchone()
    except Exception as e:                                # noqa: BLE001
        con.rollback()
        print(f"table absent: {str(e)[:80]}"); return 1
    print(f"india_quarterly: {n:,} rows · {s:,} symbols · {mn} -> {mx}")
    with con.cursor() as cur:
        cur.execute(f'''SELECT extract(year from period_end) y, count(*) n,
            count(DISTINCT symbol) s FROM "{SCHEMA}".india_quarterly
            GROUP BY 1 ORDER BY 1''')
        r = cur.fetchall()
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
