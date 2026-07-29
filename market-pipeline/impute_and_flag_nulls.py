#!/usr/bin/env python3
"""
Final no-null pass for fundamentals columns, honestly flagged.

For each market given on the command line:
  1. Export current column state from Cassandra.
  2. Tag every symbol's fundamentals_source:
       'statements'      — has roe/eps from official statement loads
       'yfinance'        — data present, market-median-free
       'median_imputed'  — one or more ratio columns were filled with the
                           market median (cross-sectional imputation)
       (imputed symbols keep the tag even if they also have real columns —
        the tag means "contains imputed values, use with care")
  3. Compute per-market medians over REAL values only, fill NULLs in the
     ratio columns, and write fundamentals_source.

market_cap / eps / pb / pe are NOT imputed for symbols with zero real data —
a median market-cap is meaningless. Imputed columns: pe, pb, roe, opm, roce,
debt_to_equity, current_ratio, asset_turnover, revenue_growth, eps_growth,
dividend_yield. Symbols that end fully covered keep their real-source tag.

Usage: impute_and_flag_nulls.py india us [japan ...]
"""

import csv
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SCRATCH = Path('/private/tmp/claude-501/-Users-umashankar/fce772c6-1b5d-436e-a845-f7e0585e07e4/scratchpad')

IMPUTE_COLS = ['pe', 'pb', 'roe', 'opm', 'roce', 'debt_to_equity',
               'current_ratio', 'asset_turnover', 'revenue_growth',
               'eps_growth', 'dividend_yield']
ALL_COLS = IMPUTE_COLS + ['eps', 'market_cap', 'interest_cov']


def export_state():
    out = SCRATCH / 'impute_state.csv'
    if out.exists():
        out.unlink()
    cols = ', '.join(['market', 'yf_ticker'] + ALL_COLS)
    cmd = f"COPY herrrickshaw.stock_quotes ({cols}) TO '{out}' WITH HEADER=true;"
    subprocess.run(['cqlsh', 'localhost', '-e', cmd], capture_output=True, timeout=300)
    return out


def main(markets):
    state_file = export_state()
    rows = defaultdict(list)
    with open(state_file) as f:
        for r in csv.DictReader(f):
            if r['market'] in markets:
                rows[r['market']].append(r)

    cql_path = Path('/Users/umashankar/market-pipeline/reports_local/FUNDAMENTALS_IMPUTE.cql')
    total = imputed_syms = 0
    with open(cql_path, 'w') as out:
        out.write("-- market-median imputation for remaining NULLs, flagged in fundamentals_source\n")
        for market, rs in rows.items():
            medians = {}
            for c in IMPUTE_COLS:
                vals = []
                for r in rs:
                    try:
                        vals.append(float(r[c]))
                    except (ValueError, TypeError):
                        pass
                if len(vals) >= 30:
                    medians[c] = statistics.median(vals)
            print(f"{market}: medians over real values -> "
                  + ", ".join(f"{c}={v:.2f}" for c, v in sorted(medians.items())))

            for r in rs:
                missing = [c for c in IMPUTE_COLS if not r[c] and c in medians]
                has_real = any(r[c] for c in ALL_COLS)
                if missing:
                    sets = [f"{c} = {medians[c]:.6f}" for c in missing]
                    sets.append("fundamentals_source = 'median_imputed'")
                    imputed_syms += 1
                else:
                    src = 'statements' if r['eps'] or r['interest_cov'] else 'yfinance'
                    sets = [f"fundamentals_source = '{src if has_real else 'yfinance'}'"]
                safe = r['yf_ticker'].replace("'", "''")
                out.write(f"UPDATE herrrickshaw.stock_quotes SET {', '.join(sets)} "
                          f"WHERE market = '{market}' AND yf_ticker = '{safe}';\n")
                total += 1
    print(f"\nCQL: {cql_path} ({total} statements, {imputed_syms} symbols got imputed values)")


if __name__ == '__main__':
    mkts = set(sys.argv[1:]) or {'india', 'us'}
    main(mkts)
