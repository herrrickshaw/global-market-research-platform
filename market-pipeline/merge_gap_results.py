#!/usr/bin/env python3
"""
Merge gap-fill results into Cassandra:
  1. yfinance gap-filler checkpoint (yf_gap_results.csv) — numeric fields were
     already sanity-guarded at extraction; sector/industry are text columns.
  2. Newly screener.in-collected India tickers (fresh rows in IN.parquet for
     symbols from remaining_india.txt) — run through the same crore-aware
     ratio math as complete_india_us_fundamentals (imported).

Emits one CQL file for cqlsh -f.
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

import pandas as pd
import psycopg2

sys.path.insert(0, '/Users/umashankar/market-pipeline')
import complete_india_us_fundamentals as base

SCRATCH = Path('/private/tmp/claude-501/-Users-umashankar/fce772c6-1b5d-436e-a845-f7e0585e07e4/scratchpad')
IN_PARQUET = '/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/IN.parquet'

NUM_COLS = ['pe', 'pb', 'roe', 'opm', 'market_cap', 'dividend_yield',
            'debt_to_equity', 'current_ratio', 'eps', 'revenue_growth', 'eps_growth']
TXT_COLS = ['sector', 'industry']


def yf_rows():
    out = defaultdict(dict)
    with open(SCRATCH / 'yf_gap_results.csv') as f:
        for r in csv.DictReader(f):
            m = {}
            for c in NUM_COLS:
                v = base.fnum(r.get(c))
                if v is not None:
                    m[c] = v
            for c in TXT_COLS:
                v = (r.get(c) or '').strip()
                if v:
                    m[c] = v
            if m:
                out[(r['market'], r['yf_ticker'])] = m
    return out


def new_screener_rows():
    remaining = set(open(SCRATCH / 'remaining_india.txt').read().split())
    df = pd.read_parquet(IN_PARQUET)
    df = df[df['ticker'].isin(remaining)]
    if df.empty:
        return {}
    # reuse base's india math on just these tickers
    conn = psycopg2.connect(dbname='market_data')
    prices = base.load_prices(conn, 'india')
    conn.close()
    shares_map = base.india_shares_map()

    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.parquet', delete=False)
    df.to_parquet(tmp.name)
    orig = base.SCREENER
    base.SCREENER = tmp.name
    try:
        res = base.india_from_screener(prices, shares_map)
    finally:
        base.SCREENER = orig
    return {('india', t): m for t, m in res.items()}


def main():
    yf = yf_rows()
    print(f"yfinance rows with data: {len(yf)}")
    scr = new_screener_rows()
    print(f"newly screener-collected india tickers: {len(scr)}")

    # screener (statement-based) wins over yfinance for overlapping tickers
    merged = dict(yf)
    for k, m in scr.items():
        if k in merged:
            merged[k].update(m)
        else:
            merged[k] = m

    out = Path('/Users/umashankar/market-pipeline/reports_local/FUNDAMENTALS_GAP_FILL.cql')
    counts = defaultdict(int)
    n = 0
    with open(out, 'w') as f:
        f.write("-- yfinance + screener.in gap fill for remaining india/us tickers\n")
        for (market, ticker), m in merged.items():
            parts = []
            for c, v in m.items():
                counts[c] += 1
                if isinstance(v, str):
                    parts.append(f"{c} = '{v.replace(chr(39), chr(39)*2)}'")
                else:
                    parts.append(f"{c} = {v:.6f}")
            safe = ticker.replace("'", "''")
            f.write(f"UPDATE herrrickshaw.stock_quotes SET {', '.join(parts)} "
                    f"WHERE market = '{market}' AND yf_ticker = '{safe}';\n")
            n += 1
    print(f"CQL: {out} ({n} statements)")
    for c, k in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {c:16} {k}")


if __name__ == '__main__':
    main()
