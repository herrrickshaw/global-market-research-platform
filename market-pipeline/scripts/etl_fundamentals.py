#!/usr/bin/env python3
"""
etl_fundamentals.py — DBMS-friendly ETL for all fundamentals sources.

Replaces the ad-hoc merge-script pattern with a proper staged load:

  extract (per-source adapter)          reuses global_fundamentals_merge loaders
      → stage  (etl.stage_fundamentals, UNLOGGED, batch-scoped)
      → validate (SQL quality gates; a failing batch never touches canonical)
      → merge  (priority-balanced upsert into public.global_fundamentals)
      → record (etl.load_batches lineage: rows in/upserted/rejected, watermark)

Source balancing: every source has a priority in etl.source_registry. The
canonical upsert only overwrites a row when the incoming source's priority is
>= the stored row's src_priority — so an official filing (EDINET/DART/EDGAR/
Eastmoney) can overwrite yfinance, but a later yfinance batch can never
clobber official data. That rule lives in SQL, not in script ordering.

Incremental: --incremental stages only rows with fy_end > the source's last
watermark (max fy_end in its previous successful batch). --full reloads all.

Usage:
  /usr/bin/python3 scripts/etl_fundamentals.py --full          # first load / rebuild
  /usr/bin/python3 scripts/etl_fundamentals.py --incremental   # daily/weekly delta
  /usr/bin/python3 scripts/etl_fundamentals.py --status        # batch history
"""

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('gfm', SCRIPTS / 'global_fundamentals_merge.py')
gfm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gfm)

DB = 'market_data'
STAGE_CSV = Path('/tmp/etl_stage_fundamentals.csv')

# ── source registry ──────────────────────────────────────────────────────────
# (source, market, priority). Higher priority wins on (market,ticker,period)
# conflicts. Official regulatory sources = 90s, structured commercial = 70s,
# scraped/derived = 50s, yfinance breadth = 30s.
SOURCES = [
    ('sec_edgar',   'US', 95),
    ('jp_master',   'JP', 90),   # EDINET-dominated master
    ('kr_master',   'KR', 90),   # DART-dominated master
    ('eastmoney',   'CN', 85),
    ('screener_in', 'IN', 80),
    ('baostock',    'CN', 55),
    ('cn_full',     'CN', 50),
    ('eu_union',    'EU', 40),
    ('yfinance',    'AU', 30), ('yfinance', 'CA', 30), ('yfinance', 'DE', 30),
    ('yfinance',    'DK', 30), ('yfinance', 'FI', 30), ('yfinance', 'HK', 30),
    ('yfinance',    'SA', 30), ('yfinance', 'TW', 30),
]

DDL = """
CREATE SCHEMA IF NOT EXISTS etl;

CREATE TABLE IF NOT EXISTS etl.source_registry (
    source VARCHAR(30), market VARCHAR(4), priority SMALLINT NOT NULL,
    active BOOLEAN DEFAULT TRUE, PRIMARY KEY (source, market));

CREATE TABLE IF NOT EXISTS etl.load_batches (
    batch_id SERIAL PRIMARY KEY,
    source VARCHAR(30), market VARCHAR(4), mode VARCHAR(12),
    rows_staged INT, rows_upserted INT, rows_rejected INT,
    watermark_fy_end DATE,
    started TIMESTAMP DEFAULT NOW(), finished TIMESTAMP,
    status VARCHAR(12) DEFAULT 'running',   -- running|ok|failed|rejected
    detail TEXT);

CREATE UNLOGGED TABLE IF NOT EXISTS etl.stage_fundamentals (
    batch_id INT, market VARCHAR(4), ticker VARCHAR(20),
    fiscal_period VARCHAR(20), fy_end DATE, filed DATE,
    revenue NUMERIC, gross_profit NUMERIC, ebit NUMERIC, net_income NUMERIC,
    equity NUMERIC, total_assets NUMERIC, total_liabilities NUMERIC,
    current_assets NUMERIC, current_liabilities NUMERIC, long_term_debt NUMERIC,
    cfo NUMERIC, shares NUMERIC, eps NUMERIC, roe NUMERIC, roa NUMERIC,
    currency VARCHAR(6), fx_usd NUMERIC, source VARCHAR(30));

ALTER TABLE global_fundamentals ADD COLUMN IF NOT EXISTS src_priority SMALLINT DEFAULT 0;
ALTER TABLE global_fundamentals ADD COLUMN IF NOT EXISTS batch_id INT;
"""

# Quality gates run against the staged batch. Any failure → batch rejected.
GATES = [
    ("rows > 0",
     "SELECT COUNT(*) FROM etl.stage_fundamentals WHERE batch_id={b}"),
    ("no null tickers",
     "SELECT COUNT(*) = (SELECT COUNT(*) FROM etl.stage_fundamentals WHERE batch_id={b} AND ticker IS NOT NULL AND ticker <> '') FROM etl.stage_fundamentals WHERE batch_id={b}"),
    ("fy_end sane (1980..today+1y)",
     "SELECT bool_and(fy_end BETWEEN DATE '1980-01-01' AND CURRENT_DATE + INTERVAL '1 year') FROM etl.stage_fundamentals WHERE batch_id={b}"),
    ("net_income fill >= 50%",
     "SELECT (COUNT(net_income)::float / GREATEST(COUNT(*),1)) >= 0.5 FROM etl.stage_fundamentals WHERE batch_id={b}"),
]

MERGE_SQL = """
INSERT INTO global_fundamentals
    (market, ticker, fiscal_period, fy_end, filed, revenue, gross_profit, ebit,
     net_income, equity, total_assets, total_liabilities, current_assets,
     current_liabilities, long_term_debt, cfo, shares, eps, roe, roa,
     currency, fx_usd, source, src_priority, batch_id)
SELECT DISTINCT ON (market, ticker, fiscal_period)
    market, ticker, fiscal_period, fy_end, filed, revenue, gross_profit, ebit,
    net_income, equity, total_assets, total_liabilities, current_assets,
    current_liabilities, long_term_debt, cfo, shares, eps, roe, roa,
    currency, fx_usd, source, {prio}, {b}
FROM etl.stage_fundamentals WHERE batch_id={b}
ORDER BY market, ticker, fiscal_period, fy_end DESC
ON CONFLICT (market, ticker, fiscal_period) DO UPDATE SET
    fy_end = EXCLUDED.fy_end, filed = EXCLUDED.filed,
    revenue = EXCLUDED.revenue, gross_profit = EXCLUDED.gross_profit,
    ebit = EXCLUDED.ebit, net_income = EXCLUDED.net_income,
    equity = EXCLUDED.equity, total_assets = EXCLUDED.total_assets,
    total_liabilities = EXCLUDED.total_liabilities,
    current_assets = EXCLUDED.current_assets,
    current_liabilities = EXCLUDED.current_liabilities,
    long_term_debt = EXCLUDED.long_term_debt, cfo = EXCLUDED.cfo,
    shares = EXCLUDED.shares, eps = EXCLUDED.eps,
    roe = EXCLUDED.roe, roa = EXCLUDED.roa, currency = EXCLUDED.currency,
    fx_usd = EXCLUDED.fx_usd, source = EXCLUDED.source,
    src_priority = EXCLUDED.src_priority, batch_id = EXCLUDED.batch_id
WHERE EXCLUDED.src_priority >= global_fundamentals.src_priority;
"""


def psql(sql: str, capture=True) -> str:
    r = subprocess.run(['psql', '-d', DB, '-v', 'ON_ERROR_STOP=1', '-t', '-A'],
                       input=sql, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    return r.stdout.strip() if capture else ''


def extract_for(source: str, market: str) -> pd.DataFrame:
    """One canonical frame for (source, market), reusing merge-script loaders."""
    df = gfm.load_market(market)
    if df.empty:
        return df
    df = df[df['source'] == source].drop_duplicates(
        subset=['ticker', 'fy_end'], keep='first').copy()
    df['fiscal_period'] = pd.to_datetime(df['fy_end']).dt.strftime('FY%Y-%m')
    df['fx_usd'] = df['currency'].map(gfm.FX_USD)
    # Derive roe/roa where the source didn't provide them (same rule as the
    # merge script's main() — the ETL path must not lose this).
    ni = pd.to_numeric(df['net_income'], errors='coerce')
    eq = pd.to_numeric(df['equity'], errors='coerce')
    ta = pd.to_numeric(df['total_assets'], errors='coerce')
    df['roe'] = pd.to_numeric(df['roe'], errors='coerce').fillna((ni / eq).where(eq != 0)).round(4)
    df['roa'] = pd.to_numeric(df['roa'], errors='coerce').fillna((ni / ta).where(ta != 0)).round(4)
    return df


def run_batch(source: str, market: str, priority: int, mode: str) -> dict:
    df = extract_for(source, market)
    if df.empty:
        return {'source': source, 'market': market, 'status': 'empty', 'staged': 0}

    if mode == 'incremental':
        wm = psql(f"SELECT MAX(watermark_fy_end) FROM etl.load_batches "
                  f"WHERE source='{source}' AND market='{market}' AND status='ok'")
        if wm:
            df = df[pd.to_datetime(df['fy_end']) > pd.Timestamp(wm)]
        if df.empty:
            return {'source': source, 'market': market, 'status': 'up-to-date', 'staged': 0}

    b = int(psql(f"INSERT INTO etl.load_batches (source, market, mode) "
                 f"VALUES ('{source}','{market}','{mode}') RETURNING batch_id"
                 ).splitlines()[0])

    cols = ['market', 'ticker', 'fiscal_period', 'fy_end', 'filed', 'revenue',
            'gross_profit', 'ebit', 'net_income', 'equity', 'total_assets',
            'total_liabilities', 'current_assets', 'current_liabilities',
            'long_term_debt', 'cfo', 'shares', 'eps', 'roe', 'roa',
            'currency', 'fx_usd', 'source']
    stage = df[cols].copy()
    stage.insert(0, 'batch_id', b)
    stage.to_csv(STAGE_CSV, index=False)
    psql(f"\\copy etl.stage_fundamentals FROM '{STAGE_CSV}' CSV HEADER", capture=False)

    # Quality gates
    for name, q in GATES:
        ok = psql(q.format(b=b))
        if ok in ('f', '0', 'false', ''):
            psql(f"UPDATE etl.load_batches SET status='rejected', finished=NOW(), "
                 f"detail='gate failed: {name}' WHERE batch_id={b}")
            psql(f"DELETE FROM etl.stage_fundamentals WHERE batch_id={b}")
            return {'source': source, 'market': market, 'status': f'REJECTED ({name})',
                    'staged': len(stage)}

    upserted = psql(MERGE_SQL.format(b=b, prio=priority) +
                    f"\nSELECT COUNT(*) FROM global_fundamentals WHERE batch_id={b};"
                    ).splitlines()[-1]
    psql(f"""UPDATE etl.load_batches SET status='ok', finished=NOW(),
             rows_staged={len(stage)}, rows_upserted={upserted or 0},
             watermark_fy_end=(SELECT MAX(fy_end) FROM etl.stage_fundamentals
                               WHERE batch_id={b})
             WHERE batch_id={b}""")
    psql(f"DELETE FROM etl.stage_fundamentals WHERE batch_id={b}")
    return {'source': source, 'market': market, 'status': 'ok',
            'staged': len(stage), 'upserted': int(upserted or 0)}


def show_status():
    print(psql("""SELECT batch_id, source, market, mode, status, rows_staged,
                  rows_upserted, watermark_fy_end,
                  to_char(finished - started, 'MI:SS') AS took
                  FROM etl.load_batches ORDER BY batch_id DESC LIMIT 20""",
               capture=True).replace('|', '  '))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--full', action='store_true')
    g.add_argument('--incremental', action='store_true')
    g.add_argument('--status', action='store_true')
    args = p.parse_args()

    psql(DDL, capture=False)
    for s, m, pr in SOURCES:
        psql(f"INSERT INTO etl.source_registry (source, market, priority) "
             f"VALUES ('{s}','{m}',{pr}) ON CONFLICT (source, market) "
             f"DO UPDATE SET priority = EXCLUDED.priority")

    if args.status:
        show_status()
        return

    mode = 'full' if args.full else 'incremental'
    print(f"{'source':13s} {'mkt':4s} {'prio':>4s}  result")
    print('-' * 60)
    for source, market, prio in SOURCES:
        try:
            r = run_batch(source, market, prio, mode)
            extra = f" staged={r.get('staged',0)} upserted={r.get('upserted','-')}"
            print(f"{source:13s} {market:4s} {prio:4d}  {r['status']}{extra}")
        except Exception as e:
            print(f"{source:13s} {market:4s} {prio:4d}  ERROR: {e}")

    print()
    print(psql("SELECT market || ': ' || COUNT(*) || ' rows, prio>=' || "
               "MIN(src_priority) FROM global_fundamentals "
               "GROUP BY market ORDER BY COUNT(*) DESC"))


if __name__ == '__main__':
    main()
