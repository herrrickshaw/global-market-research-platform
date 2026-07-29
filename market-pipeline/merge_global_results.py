#!/usr/bin/env python3
"""
Merge the GLOBAL yfinance gap-fill checkpoint into Cassandra with a strict
null-only-fill policy: a column is written only if it is currently NULL in
Cassandra, so statement-derived values (sec_edgar/dart/jp_master/eastmoney/
screener_in/eu_union) are never overwritten by yfinance approximations.
"""

import csv
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, '/Users/umashankar/market-pipeline')
from merge_gap_results import NUM_COLS, TXT_COLS
import complete_india_us_fundamentals as base

SCRATCH = Path('/private/tmp/claude-501/-Users-umashankar/fce772c6-1b5d-436e-a845-f7e0585e07e4/scratchpad')


def export_state():
    out = SCRATCH / 'global_merge_state.csv'
    if out.exists():
        out.unlink()
    cols = ', '.join(['market', 'yf_ticker'] + NUM_COLS + TXT_COLS)
    cmd = f"COPY herrrickshaw.stock_quotes ({cols}) TO '{out}' WITH HEADER=true;"
    subprocess.run(['cqlsh', 'localhost', '-e', cmd], capture_output=True, timeout=300)
    return out


def main():
    state = {}
    with open(export_state()) as f:
        for r in csv.DictReader(f):
            state[(r['market'], r['yf_ticker'])] = r

    out_file = Path('/Users/umashankar/market-pipeline/reports_local/FUNDAMENTALS_GLOBAL_GAP_FILL.cql')
    counts = defaultdict(int)
    n = skipped_cols = 0
    with open(SCRATCH / 'yf_gap_global_results.csv') as f, open(out_file, 'w') as out:
        out.write("-- global yfinance gap fill: null-only columns\n")
        for r in csv.DictReader(f):
            key = (r['market'], r['yf_ticker'])
            cur = state.get(key)
            if cur is None:
                continue
            parts = []
            for c in NUM_COLS:
                v = base.fnum(r.get(c))
                if v is None:
                    continue
                if cur[c]:           # already has a (statement) value
                    skipped_cols += 1
                    continue
                parts.append(f"{c} = {v:.6f}")
                counts[c] += 1
            for c in TXT_COLS:
                v = (r.get(c) or '').strip()
                if v and not cur[c]:
                    parts.append(f"{c} = '{v.replace(chr(39), chr(39)*2)}'")
                    counts[c] += 1
            if parts:
                safe = r['yf_ticker'].replace("'", "''")
                out.write(f"UPDATE herrrickshaw.stock_quotes SET {', '.join(parts)} "
                          f"WHERE market = '{r['market']}' AND yf_ticker = '{safe}';\n")
                n += 1
    print(f"CQL: {out_file} ({n} statements; {skipped_cols} column-writes skipped "
          f"to protect statement values)")
    for c, k in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {c:16} {k}")


if __name__ == '__main__':
    main()
