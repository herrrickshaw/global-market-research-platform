#!/usr/bin/env python3
"""
korea_aggregate_all.py — Aggregate ALL Korea fundamentals into one master store.

Mirror of japan_aggregate_all.py. Sources (priority order — higher wins on
(ticker, fy_end) conflicts):
  1. dart_fresh   — fresh DART API pulls (/tmp/dart_kr/dart_fundamentals.jsonl)
  2. dart_prior   — KR_dart_joined.parquet (earlier DART collection)
  3. kr_deep      — KR_deep.parquet (deep 2016→ history)
  4. kr_core      — KR.parquet (yfinance core)

Outputs:
  - cache_seed/fundamentals_history/KR_master.parquet
  - Postgres korea_fundamentals_history (via psql \\copy staging)

Run with /usr/bin/python3 (has pandas + pyarrow).
"""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

FUND_DIR = Path('/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history')
DART_JSONL = Path('/tmp/dart_kr/dart_fundamentals.jsonl')
MASTER_OUT = FUND_DIR / 'KR_master.parquet'
LOAD_CSV = Path('/tmp/korea_master_load.csv')

CANON = ['ticker', 'fy_end', 'revenue', 'operating_income', 'net_income',
         'equity', 'total_assets', 'total_liabilities', 'cfo', 'source']


def load_dart_fresh() -> pd.DataFrame:
    if not DART_JSONL.exists():
        print("  ⚠ no fresh DART jsonl")
        return pd.DataFrame(columns=CANON)
    rows = []
    for line in DART_JSONL.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        stock = d['stock_code']
        # KRX yfinance convention: 6-digit + .KS (KOSPI) — we don't know the
        # board from DART, store bare 6-digit; harmonize below.
        rows.append({
            'ticker': stock,
            'fy_end': f"{d['bsns_year']}-12-31",   # KR fiscal years ≈ calendar
            'revenue': d.get('revenue'),
            'operating_income': d.get('operating_income'),
            'net_income': d.get('net_income'),
            'equity': d.get('equity'),
            'total_assets': d.get('total_assets'),
            'total_liabilities': d.get('total_liabilities'),
            'cfo': d.get('cfo'),
            'source': 'dart_fresh',
        })
    return pd.DataFrame(rows, columns=CANON)


def norm_ticker(t: str) -> str:
    """Strip .KS/.KQ suffixes → bare 6-digit code."""
    return str(t).replace('.KS', '').replace('.KQ', '').strip().zfill(6)


def load_parquet(name: str, source: str) -> pd.DataFrame:
    p = FUND_DIR / name
    if not p.exists():
        print(f"  ⚠ missing: {name}")
        return pd.DataFrame(columns=CANON)
    df = pd.read_parquet(p)
    df['source'] = source
    for c in CANON:
        if c not in df.columns:
            df[c] = None
    return df[CANON]


def main():
    frames = []

    print("[1/3] Loading fresh DART pulls …")
    fresh = load_dart_fresh()
    print(f"   dart_fresh    {len(fresh):6d} rows")
    frames.append(fresh)

    print("[2/3] Loading existing parquets …")
    for name, src in [('KR_dart_joined.parquet', 'dart_prior'),
                      ('KR_deep.parquet', 'kr_deep'),
                      ('KR.parquet', 'kr_core')]:
        df = load_parquet(name, src)
        print(f"   {src:13s} {len(df):6d} rows")
        frames.append(df)

    allf = pd.concat(frames, ignore_index=True)
    allf['ticker'] = allf['ticker'].map(norm_ticker)
    allf['fy_end'] = pd.to_datetime(allf['fy_end']).dt.date

    before = len(allf)
    allf = allf.drop_duplicates(subset=['ticker', 'fy_end'], keep='first')
    print(f"\n[3/3] Dedupe: {before} → {len(allf)} rows "
          f"({allf['ticker'].nunique()} tickers, "
          f"{allf['fy_end'].min()} → {allf['fy_end'].max()})")
    print(allf['source'].value_counts().to_string())

    allf.to_parquet(MASTER_OUT, index=False)
    print(f"\n✓ Master parquet: {MASTER_OUT} ({MASTER_OUT.stat().st_size/1e6:.1f} MB)")

    pg = allf.rename(columns={
        'revenue': 'revenue_krw', 'operating_income': 'operating_income_krw',
        'net_income': 'net_income_krw', 'equity': 'equity_krw',
        'total_assets': 'total_assets_krw', 'total_liabilities': 'total_liabilities_krw',
        'cfo': 'operating_cf_krw'})
    pg['fiscal_period'] = pd.to_datetime(pg['fy_end']).dt.strftime('FY%Y-%m')
    pg['roe'] = (pg['net_income_krw'] / pg['equity_krw']).round(4)
    pg['roa'] = (pg['net_income_krw'] / pg['total_assets_krw']).round(4)
    out = pg[['ticker', 'fiscal_period', 'fy_end', 'revenue_krw', 'operating_income_krw',
              'net_income_krw', 'total_assets_krw', 'total_liabilities_krw',
              'equity_krw', 'roe', 'roa', 'operating_cf_krw', 'source']]
    out.to_csv(LOAD_CSV, index=False)

    sql = f"""
    CREATE TABLE IF NOT EXISTS korea_fundamentals_history (
        id SERIAL PRIMARY KEY, krx_code VARCHAR(6), fiscal_period VARCHAR(20),
        fy_end DATE, revenue_krw BIGINT, operating_income_krw BIGINT,
        net_income_krw BIGINT, total_assets_krw BIGINT, total_liabilities_krw BIGINT,
        equity_krw BIGINT, roe NUMERIC, roa NUMERIC, operating_cf_krw BIGINT,
        source VARCHAR(50), created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(krx_code, fiscal_period));
    CREATE TEMP TABLE _stage (krx_code TEXT, fiscal_period TEXT, fy_end DATE,
        revenue_krw NUMERIC, operating_income_krw NUMERIC, net_income_krw NUMERIC,
        total_assets_krw NUMERIC, total_liabilities_krw NUMERIC, equity_krw NUMERIC,
        roe NUMERIC, roa NUMERIC, operating_cf_krw NUMERIC, source TEXT);
    \\copy _stage FROM '{LOAD_CSV}' CSV HEADER
    INSERT INTO korea_fundamentals_history
        (krx_code, fiscal_period, fy_end, revenue_krw, operating_income_krw,
         net_income_krw, total_assets_krw, total_liabilities_krw, equity_krw,
         roe, roa, operating_cf_krw, source)
    SELECT DISTINCT ON (krx_code, fiscal_period)
           krx_code, fiscal_period, fy_end, revenue_krw::BIGINT,
           operating_income_krw::BIGINT, net_income_krw::BIGINT,
           total_assets_krw::BIGINT, total_liabilities_krw::BIGINT,
           equity_krw::BIGINT, roe, roa, operating_cf_krw::BIGINT, source
    FROM _stage
    ORDER BY krx_code, fiscal_period, fy_end DESC
    ON CONFLICT (krx_code, fiscal_period) DO UPDATE SET
        revenue_krw = EXCLUDED.revenue_krw,
        operating_income_krw = EXCLUDED.operating_income_krw,
        net_income_krw = EXCLUDED.net_income_krw,
        total_assets_krw = EXCLUDED.total_assets_krw,
        total_liabilities_krw = EXCLUDED.total_liabilities_krw,
        equity_krw = EXCLUDED.equity_krw, roe = EXCLUDED.roe, roa = EXCLUDED.roa,
        operating_cf_krw = EXCLUDED.operating_cf_krw, source = EXCLUDED.source;
    SELECT source, COUNT(*) FROM korea_fundamentals_history GROUP BY source ORDER BY 2 DESC;
    """
    r = subprocess.run(['psql', '-d', 'market_data', '-v', 'ON_ERROR_STOP=1'],
                       input=sql, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print("✗ Postgres load failed:", r.stderr[-800:])
        sys.exit(1)
    print("✓ Postgres korea_fundamentals_history updated")


if __name__ == '__main__':
    main()
