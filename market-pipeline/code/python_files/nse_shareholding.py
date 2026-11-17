#!/usr/bin/env python3
"""
nse_shareholding.py — promoter/public shareholding for the full NSE equity universe.

WHY THIS EXISTS
---------------
`ownership_behaviour_india.py` had to stop at 347 companies because screener.in
rate-limited and began refusing connections after ~800 requests. NSE publishes
the same filing itself, and it is a better source in every respect that matters
here except one:

    source        promoter/public  FII/DII  history    throughput      limit hit
    screener.in   yes              YES      13 quarters ~1-2 s/symbol   blocked ~800
    NSE master    yes              no       22 quarters 0.37 s/symbol   none observed

VALIDATED BEFORE USE: RELIANCE Jun 2026 reads 50.48% promoter from NSE and 50.48%
from screener.in, independently. The two agree, so this is a substitution rather
than a different measurement.

WHAT IS LOST: the FII/DII split. That matters — DII holding was the STRONGEST
result in the study (volatility t=-9.9 with controls), and NSE cannot extend it.
What NSE can extend is PUBLIC FLOAT, which is the result that most needs a bigger
sample: two-thirds of its raw volatility effect turned out to be liquidity, so it
is the one where 13x the companies and far more liquidity range actually changes
what can be claimed.

🔴 THROUGHPUT IS UNPROVEN AT SCALE. 15/15 succeeded in a burst; that says nothing
about symbol 500. NSE also requires the same cookie handshake as fiidiiTradeReact
and is known to drop sessions. So: checkpoint every 50, re-handshake on failure,
and BACK OFF on a run of non-200s rather than hammering through them.

    nse_shareholding.py --collect          # full NSE equity universe
    nse_shareholding.py --collect --limit 200
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache_seed"
PANEL = CACHE / "india_shareholding_nse.parquet"

API = ("https://www.nseindia.com/api/corporate-share-holdings-master"
       "?index=equities&symbol={sym}")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
CHECKPOINT = 50
MAX_CONSEC_FAIL = 25       # a run this long means blocked, not unlucky symbols


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json",
                      "Accept-Language": "en-US,en;q=0.9"})
    s.get("https://www.nseindia.com", timeout=20)      # cookie handshake
    return s


def _universe(limit: int) -> list:
    """Every bhavcopy symbol the ticker reference calls an India equity.

    Same rule as ownership_behaviour_india: membership by lookup, never by ticker
    shape — 3MINDIA and 63MOONS start with digits and are equities, 0ANSPL28 is
    debt, and no regex separates them.
    """
    import screener_kit as kit
    ref = pd.read_parquet(CACHE / "ticker_exchange_reference.parquet")
    eq = set(ref[ref["country"] == "IN"]["base_ticker"].astype(str).str.upper())
    return sorted(set(kit.load("IN")) & eq)[:limit]


def collect(limit: int = 6000, sleep: float = 0.3) -> int:
    universe = _universe(limit)
    rows, have = [], set()
    if PANEL.exists():
        old = pd.read_parquet(PANEL)
        rows = old.to_dict("records")
        have = set(old["symbol"].unique())
        print(f"  resuming: {len(have):,} symbols already stored")
    todo = [s for s in universe if s not in have]
    print(f"  universe {len(universe):,} equities, to fetch {len(todo):,}")

    s = _session()
    consec, got, missing = 0, 0, 0
    for i, sym in enumerate(todo, 1):
        try:
            r = s.get(API.format(sym=sym), timeout=20)
            if r.status_code != 200:
                raise RuntimeError(f"http {r.status_code}")
            data = r.json()
            consec = 0
        except Exception:
            consec += 1
            if consec in (5, 12):
                # Re-handshake before concluding anything: NSE drops sessions,
                # and a dropped cookie looks exactly like a block.
                print(f"    {consec} consecutive failures — re-handshaking")
                time.sleep(5)
                try:
                    s = _session()
                except Exception:
                    pass
            if consec >= MAX_CONSEC_FAIL:
                print(f"  🔴 {consec} consecutive failures at {sym} — treating as BLOCKED "
                      f"and stopping. {got:,} symbols collected this run.")
                break
            time.sleep(sleep)
            continue

        if not data:
            missing += 1
        for rec in (data or []):
            pro, pub = rec.get("pr_and_prgrp"), rec.get("public_val")
            if pro is None and pub is None:
                continue
            rows.append({
                "symbol": sym, "date": rec.get("date"),
                "promoter_pct": pd.to_numeric(pro, errors="coerce"),
                "public_pct": pd.to_numeric(pub, errors="coerce"),
                "employee_trusts_pct": pd.to_numeric(rec.get("employeeTrusts"), errors="coerce"),
                "isin": rec.get("isin"), "industry": rec.get("industry"),
            })
        got += 1
        if i % CHECKPOINT == 0:
            pd.DataFrame(rows).to_parquet(PANEL, compression="zstd", index=False)
            print(f"    {i:,}/{len(todo):,}  stored={got:,}  empty={missing:,}")
        time.sleep(sleep)

    d = pd.DataFrame(rows)
    CACHE.mkdir(parents=True, exist_ok=True)
    d.to_parquet(PANEL, compression="zstd", index=False)
    print(f"  -> {PANEL.name}: {d.symbol.nunique():,} symbols, {len(d):,} symbol-quarters")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--limit", type=int, default=6000)
    ap.add_argument("--sleep", type=float, default=0.3)
    a = ap.parse_args()
    if not a.collect:
        ap.print_help(); return 1
    return collect(limit=a.limit, sleep=a.sleep)


if __name__ == "__main__":
    sys.exit(main())
