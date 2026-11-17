#!/usr/bin/env python3
"""
collect_us_sic.py — official SEC industry classification for US tickers.

WHY SEC AND NOT A VENDOR
────────────────────────
`backtest_ccc.py --sector-relative` needs to demean the cash conversion cycle
within an industry, because a raw CCC quintile is close to a sector bet:
software carries no inventory and is structurally negative, heavy industry is
structurally long. The only sector map in this repo is Europe-only — 955
entries keyed "EU:TICKER" — and covered 0 of 2,039 US tickers, which is how the
sector-relative run silently printed raw quintiles under a sector heading.

SEC assigns every registrant a SIC code and publishes it on the same host this
repo already pulls fundamentals from, under the same 10 req/s budget and the
same descriptive User-Agent. No vendor, no key, no extra rate limit, and the
classification is the one the filings themselves are filed under — so it lines
up with the fundamentals rather than having to be reconciled against them.

SIC is coarser and older than GICS, and its divisions are the ones the
`sicDescription` string already encodes. That is a fair trade for a
sector-demeaning step: the question is only "who are this company's peers", and
a two-digit SIC major group answers it well enough to stop a CCC quintile being
an industry bet.

    collect_us_sic.py                 # every ticker in the US fundamentals store
    collect_us_sic.py --only AAPL WMT
    collect_us_sic.py --refresh-days 90
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

import us_fundamentals_edgar as E

OUT = Path(E.FUND_DIR) / "us_sic.parquet"
RATE = E.RATE

# SIC major groups -> a readable sector. Two digits is the right granularity for
# demeaning: four would leave single-name "peer groups", and one would put
# software and steel together.
_DIVISION = [
    (1, 9, "Agriculture"), (10, 14, "Mining"), (15, 17, "Construction"),
    (20, 39, "Manufacturing"), (40, 49, "Transport & Utilities"),
    (50, 51, "Wholesale"), (52, 59, "Retail"), (60, 67, "Finance & Real Estate"),
    (70, 89, "Services"), (91, 99, "Public Administration"),
]


def sector_of(sic: str | int | None) -> str | None:
    try:
        major = int(str(sic)[:2])
    except (TypeError, ValueError):
        return None
    for lo, hi, name in _DIVISION:
        if lo <= major <= hi:
            return name
    return None


def fetch_sic(cik: int, session: requests.Session) -> tuple[str | None, str | None]:
    """(sic, sicDescription) from the submissions endpoint."""
    url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    r = session.get(url, headers=E.UA, timeout=30)
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    d = r.json()
    return d.get("sic") or None, d.get("sicDescription") or None


def main() -> int:
    ap = argparse.ArgumentParser(description="SEC SIC codes for US tickers")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--refresh-days", type=int, default=90,
                    help="skip tickers collected more recently than this")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    store = pd.read_parquet(E.STORE) if E.STORE.exists() else pd.DataFrame()
    if store.empty:
        print("no fundamentals store — run us_fundamentals_edgar.py first")
        return 1
    want = sorted(set(store["ticker"].astype(str)))
    if a.only:
        want = [t for t in want if t.upper() in {x.upper() for x in a.only}]

    have = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(
        columns=["ticker", "sic", "sic_desc", "sector", "collected_at"])
    fresh: set[str] = set()
    if not have.empty and a.refresh_days:
        cut = (dt.datetime.now(dt.timezone.utc)
               - dt.timedelta(days=a.refresh_days)).isoformat()
        fresh = set(have.loc[have["collected_at"] >= cut, "ticker"].astype(str))

    cik = E.load_cik_map()
    todo = [t for t in want if t.upper() in cik and t not in fresh]
    if a.limit:
        todo = todo[: a.limit]
    print(f"universe {len(want):,} | no CIK {sum(1 for t in want if t.upper() not in cik)} "
          f"| fresh-skip {len(fresh):,} | fetching {len(todo):,}")

    sess = requests.Session()
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    rows, failed = [], 0
    for i, t in enumerate(todo, 1):
        try:
            sic, desc = fetch_sic(cik[t.upper()], sess)
            rows.append({"ticker": t, "sic": sic, "sic_desc": desc,
                         "sector": sector_of(sic), "collected_at": stamp})
        except KeyboardInterrupt:
            print("\ninterrupted — writing what we have"); break
        except Exception as e:
            failed += 1
            if failed <= 5:
                print(f"  ! {t}: {str(e)[:60]}")
        if i % 250 == 0:
            print(f"  {i}/{len(todo)}")
        time.sleep(RATE)

    if rows:
        new = pd.DataFrame(rows)
        # Re-read under the lock rather than merging into `have`, which was
        # loaded before the fetch loop and is stale by whatever another run
        # committed meanwhile. Merging into that stale copy is exactly how the
        # fundamentals store lost rows to a concurrent collection on
        # 2026-08-21 — same shape, same fix, applied here before it bites.
        with E._store_lock("us_sic"):
            disk = pd.read_parquet(OUT) if OUT.exists() else have
            merged = (pd.concat([disk[~disk["ticker"].isin(new["ticker"])], new],
                                ignore_index=True) if not disk.empty else new)
            OUT.parent.mkdir(parents=True, exist_ok=True)
            tmp = OUT.with_suffix(".parquet.tmp")
            merged.to_parquet(tmp, index=False)
            tmp.replace(OUT)
        have = merged

    got = have.dropna(subset=["sector"])
    print(f"done: {len(rows):,} fetched, {failed} failed · store {len(have):,} tickers, "
          f"{len(got):,} with a sector ({len(got) / max(len(have), 1):.0%})")
    if not got.empty:
        for s, n in got["sector"].value_counts().items():
            print(f"    {s:24} {n:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
