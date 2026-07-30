#!/usr/bin/env python3
"""
nse_index_tri.py — official NIFTY Total Return Index series.

WHY. The fund-vs-segment comparison that produced today's only surviving
fund-category alpha (small-cap active +2.22pp/yr over ten years, 92% of funds
beating) rests on a RECONSTRUCTED total return: the daily index archive
publishes PRICE indices, so dividends were added back by accruing the archive's
own trailing `div_yield` daily. That is an approximation — real dividends are
lumpy and the yield column is trailing — and it sits underneath a headline
number, which is the wrong place for an approximation to live.

NIFTY publishes the real thing. `/BackPage/getTotalReturnIndexString` returns
the official TRI, and it serves the entire 2016-08 -> 2026-07 window in a single
request per index (2,474 observations). Found by reading the site's own
IISLComponet.js after the documented pages turned out to be an SPA shell.

🔴 WHAT THIS FILE DOES NOT SOLVE: point-in-time index CONSTITUENTS. NSE
publishes only the current membership list, and no constituent-change or
press-release endpoint exists in the site's JavaScript — the guessed
BackPage/getPressReleaseData and getIndexMaintenance both 302, and the NSE
circular archive patterns 404. Rolling today's list backwards through a change
log remains the only route to real historical membership, and the change log is
not machine-readable from any source reachable here. smallcap_screener.py's
turnover-rank band proxy therefore stands, with its ~43% match to the real index
stated rather than hidden.

Usage:
  python3 scripts/nse_index_tri.py --build
  python3 scripts/nse_index_tri.py --status
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request

import sys

import pandas as pd

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import pg_client

DSN = "dbname=market_data host=/tmp user=umashankar"
SCHEMA = "indices"
URL = "https://www.niftyindices.com/BackPage/getTotalReturnIndexString"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
INDICES = ["NIFTY 50", "NIFTY NEXT 50", "NIFTY 100", "NIFTY 500",
           "NIFTY MIDCAP 150", "NIFTY SMALLCAP 250", "NIFTY MIDCAP 100",
           "NIFTY SMALLCAP 100", "NIFTY MICROCAP 250"]

# Native Postgres DDL for pg_client.ensure_schema() — no `pg.` ATTACH-alias
# prefix, Postgres type names (DOUBLE PRECISION not DuckDB's bare DOUBLE).
DDL = f"""
CREATE SCHEMA IF NOT EXISTS "{SCHEMA}";
CREATE TABLE IF NOT EXISTS "{SCHEMA}".nse_tri (
  index_name VARCHAR, index_date DATE, tri DOUBLE PRECISION
);
CREATE UNIQUE INDEX IF NOT EXISTS nse_tri_pk
  ON "{SCHEMA}".nse_tri (index_name, index_date);
"""


def fetch(idx: str, frm: str, to: str) -> pd.DataFrame:
    payload = {"cinfo": json.dumps({"name": idx, "startDate": frm,
                                    "endDate": to, "indexName": idx})}
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=UTF-8",
                 "User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
                 "Referer": "https://www.niftyindices.com/reports/historical-data"})
    with urllib.request.urlopen(req, timeout=90) as r:
        rows = json.loads(r.read().decode())
    if not rows:
        return pd.DataFrame(columns=["index_name", "index_date", "tri"])
    d = pd.DataFrame(rows)
    d = d.rename(columns={"Index Name": "index_name", "Date": "index_date",
                          "TotalReturnsIndex": "tri"})
    d["index_date"] = pd.to_datetime(d.index_date, format="%d %b %Y",
                                     errors="coerce").dt.date
    d["tri"] = pd.to_numeric(d.tri.astype(str).str.replace(",", "", regex=False),
                             errors="coerce")
    return d[["index_name", "index_date", "tri"]].dropna()


def connect():
    pg_client.connect()
    pg_client.ensure_schema([s.strip() for s in DDL.split(";") if s.strip()])
    return pg_client.get_connection()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--from", dest="frm", default="01-Aug-2016")
    ap.add_argument("--to", dest="to", default="27-Jul-2026")
    a = ap.parse_args()
    con = connect()

    if a.status or not a.build:
        with con.cursor() as cur:
            cur.execute(f'''SELECT index_name, count(*), min(index_date),
                                max(index_date) FROM "{SCHEMA}".nse_tri
                                GROUP BY 1 ORDER BY 1''')
            r = cur.fetchall()
        print(f"=== NSE TOTAL RETURN INDICES ({len(r)}) ===")
        for n, c, f, l in r:
            print(f"  {n:24s} {c:>5,} obs  {f} -> {l}")
        return 0

    total_new = 0
    for idx in INDICES:
        try:
            d = fetch(idx, a.frm, a.to)
        except Exception as e:                        # noqa: BLE001
            print(f"  {idx:24s} FAILED — {str(e)[:60]}")
            continue
        if d.empty:
            print(f"  {idx:24s} no data")
            continue
        d = d.drop_duplicates(["index_name", "index_date"], keep="last")
        # Anti-join in pandas (was a DuckDB LEFT JOIN against the attached
        # table). Keyed on the FETCHED DATA's own index_name column, not the
        # requested `idx` string — niftyindices.com's API normalises casing
        # in its response ("Nifty 50") independently of what's requested
        # ("NIFTY 50"), and the table already carries both as distinct rows
        # from before this migration. Filtering existing rows by `idx`
        # instead of d.index_name's actual values missed the already-loaded
        # "Nifty 50" rows and produced a UniqueViolation on re-insert.
        with con.cursor() as cur:
            cur.execute(
                f'SELECT index_name, index_date FROM "{SCHEMA}".nse_tri '
                "WHERE index_name = ANY(%s)",
                (list(d.index_name.unique()),),
            )
            have = set(cur.fetchall())
        key = list(zip(d.index_name, d.index_date))
        novel = d[[k not in have for k in key]]
        n = len(novel)
        if n:
            rows = pg_client.to_rows(novel, ["index_name", "index_date", "tri"])
            pg_client.append_rows(SCHEMA, "nse_tri",
                                  ["index_name", "index_date", "tri"], rows)
        total_new += n
        print(f"  {idx:24s} {len(d):>5,} obs · {n:>5,} new", flush=True)
        time.sleep(1.0)
    print(f"\nappended {total_new:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
