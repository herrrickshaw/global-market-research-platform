#!/usr/bin/env python3
"""
japan_aggregate_all.py — Aggregate ALL Japan fundamentals into one master store.

Sources (priority order — higher wins on (ticker, fy_end) conflicts):
  1. edinet_fresh   — freshly downloaded EDINET CSV ZIPs (/tmp/edinet_annual)
  2. edinet_prior   — JP_edinet.parquet   (prior EDINET collection)
  3. jquants        — JP_jquants.parquet  (J-Quants API)
  4. merged_prior   — JP_merged.parquet   (earlier merge)
  5. full_prior     — JP_full.parquet     (broadest earlier set, 2011→)
  6. yf_breadth     — JP_yf_breadth.parquet (yfinance breadth pass)
  7. yf_core        — JP.parquet          (yfinance core)

Outputs:
  - cache_seed/fundamentals_history/JP_master.parquet  (master, deduped)
  - /tmp/japan_master_load.csv → Postgres japan_fundamentals_history via psql \\copy

Run with /usr/bin/python3 (has pandas + pyarrow).
"""

import glob
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd

FUND_DIR = Path('/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history')
EDINET_FRESH_DIR = Path('/tmp/edinet_annual')
MASTER_OUT = FUND_DIR / 'JP_master.parquet'
LOAD_CSV = Path('/tmp/japan_master_load.csv')

CANON_COLS = ['ticker', 'fy_end', 'revenue', 'net_income', 'equity',
              'total_assets', 'eps', 'cfo', 'long_term_debt', 'shares', 'source']

# EDINET element IDs per metric, in preference order (covers JGAAP/IFRS/US-GAAP)
EDINET_ELEMENTS = {
    'revenue': ['jpcrp_cor:NetSalesSummaryOfBusinessResults',
                'jpcrp_cor:RevenueIFRSSummaryOfBusinessResults',
                'jpcrp_cor:RevenuesUSGAAPSummaryOfBusinessResults',
                'jpcrp_cor:OperatingRevenue1SummaryOfBusinessResults',
                'jpcrp_cor:OperatingRevenue2SummaryOfBusinessResults',
                'jppfs_cor:NetSales'],
    'net_income': ['jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults',
                   'jpcrp_cor:ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults',
                   'jpcrp_cor:NetIncomeLossSummaryOfBusinessResults',
                   'jppfs_cor:ProfitLoss'],
    'equity': ['jpcrp_cor:NetAssetsSummaryOfBusinessResults',
               'jpcrp_cor:EquityAttributableToOwnersOfParentIFRSSummaryOfBusinessResults',
               'jppfs_cor:NetAssets'],
    'total_assets': ['jpcrp_cor:TotalAssetsSummaryOfBusinessResults',
                     'jpcrp_cor:TotalAssetsIFRSSummaryOfBusinessResults',
                     'jppfs_cor:Assets'],
    'eps': ['jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults',
            'jpcrp_cor:BasicEarningsPerShareIFRSSummaryOfBusinessResults'],
    'cfo': ['jpcrp_cor:NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults',
            'jpcrp_cor:CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults'],
}


def parse_edinet_zip(path: str):
    """Extract canonical metrics from one EDINET CSV ZIP (type=5 download)."""
    m = re.match(r'(\d{5})_\d+_(\d{4}-\d{2}-\d{2})_', Path(path).name)
    if not m:
        return None
    sec5, period_end = m.groups()
    row = {'ticker': sec5[:4] + '.T', 'fy_end': period_end, 'source': 'edinet_fresh'}
    try:
        with zipfile.ZipFile(path) as z:
            mains = [n for n in z.namelist() if 'jpcrp' in n and n.endswith('.csv')]
            if not mains:
                return None
            df = pd.read_csv(io.BytesIO(z.read(mains[0])), sep='\t', encoding='utf-16')
    except Exception:
        return None

    cur = df[df['コンテキストID'].isin(['CurrentYearDuration', 'CurrentYearInstant',
                                        'CurrentYearDuration_NonConsolidatedMember',
                                        'CurrentYearInstant_NonConsolidatedMember'])]
    # Prefer consolidated rows (no NonConsolidated suffix)
    cons = cur[~cur['コンテキストID'].str.contains('NonConsolidated')]

    def get(elems):
        for scope in (cons, cur):
            for e in elems:
                hit = scope[scope['要素ID'] == e]
                if len(hit):
                    try:
                        return float(hit.iloc[0]['値'])
                    except (ValueError, TypeError):
                        continue
        return None

    for metric, elems in EDINET_ELEMENTS.items():
        row[metric] = get(elems)
    return row


def load_parquet(name: str, source: str) -> pd.DataFrame:
    p = FUND_DIR / name
    if not p.exists():
        print(f"  ⚠ missing: {name}")
        return pd.DataFrame(columns=CANON_COLS)
    df = pd.read_parquet(p)
    df['source'] = source
    for c in CANON_COLS:
        if c not in df.columns:
            df[c] = None
    return df[CANON_COLS]


def main():
    frames = []

    # 1. Fresh EDINET downloads
    zips = sorted(glob.glob(str(EDINET_FRESH_DIR / '*.zip')))
    print(f"[1/3] Parsing {len(zips)} fresh EDINET ZIPs …")
    rows, bad = [], 0
    for i, p in enumerate(zips, 1):
        r = parse_edinet_zip(p)
        if r:
            rows.append(r)
        else:
            bad += 1
        if i % 250 == 0:
            print(f"   … {i}/{len(zips)}")
    fresh = pd.DataFrame(rows)
    if len(fresh):
        for c in CANON_COLS:
            if c not in fresh.columns:
                fresh[c] = None
        frames.append(fresh[CANON_COLS])
    print(f"   parsed {len(fresh)} companies ({bad} skipped)")

    # 2. Existing parquets, priority order
    print("[2/3] Loading existing parquets …")
    for name, src in [('JP_edinet.parquet', 'edinet_prior'),
                      ('JP_jquants.parquet', 'jquants'),
                      ('JP_merged.parquet', 'merged_prior'),
                      ('JP_full.parquet', 'full_prior'),
                      ('JP_yf_breadth.parquet', 'yf_breadth'),
                      ('JP.parquet', 'yf_core')]:
        df = load_parquet(name, src)
        print(f"   {src:13s} {len(df):6d} rows")
        frames.append(df)

    allf = pd.concat(frames, ignore_index=True)
    allf['fy_end'] = pd.to_datetime(allf['fy_end']).dt.date
    allf['ticker'] = allf['ticker'].astype(str).str.strip()

    # Dedupe: keep first occurrence == highest priority (frames appended in order)
    before = len(allf)
    allf = allf.drop_duplicates(subset=['ticker', 'fy_end'], keep='first')
    print(f"\n[3/3] Dedupe: {before} → {len(allf)} rows "
          f"({allf['ticker'].nunique()} tickers, "
          f"{allf['fy_end'].min()} → {allf['fy_end'].max()})")
    print(allf['source'].value_counts().to_string())

    # Master parquet
    allf.to_parquet(MASTER_OUT, index=False)
    print(f"\n✓ Master parquet: {MASTER_OUT} ({MASTER_OUT.stat().st_size/1e6:.1f} MB)")

    # Postgres load via psql \copy (avoids driver dependencies)
    pg = allf.rename(columns={'revenue': 'revenue_jpy', 'net_income': 'net_income_jpy',
                              'equity': 'shareholders_equity_jpy',
                              'total_assets': 'total_assets_jpy',
                              'cfo': 'operating_cf_jpy'})
    pg['fiscal_period'] = pd.to_datetime(pg['fy_end']).dt.strftime('FY%Y-%m')
    pg['tse_code'] = pg['ticker'].str.replace('.T', '', regex=False)
    pg['roe'] = (pg['net_income_jpy'] / pg['shareholders_equity_jpy']).round(4)
    pg['roa'] = (pg['net_income_jpy'] / pg['total_assets_jpy']).round(4)
    out = pg[['tse_code', 'fiscal_period', 'fy_end', 'revenue_jpy', 'net_income_jpy',
              'eps', 'total_assets_jpy', 'shareholders_equity_jpy', 'roe', 'roa',
              'operating_cf_jpy', 'source']]
    out.to_csv(LOAD_CSV, index=False)

    sql = f"""
    CREATE TABLE IF NOT EXISTS japan_fundamentals_history (
        id SERIAL PRIMARY KEY, tse_code VARCHAR(6), fiscal_period VARCHAR(20),
        filing_date DATE, revenue_jpy BIGINT, operating_income_jpy BIGINT,
        net_income_jpy BIGINT, eps NUMERIC, total_assets_jpy BIGINT,
        total_liabilities_jpy BIGINT, shareholders_equity_jpy BIGINT,
        book_value NUMERIC, roe NUMERIC, roa NUMERIC, debt_to_equity NUMERIC,
        current_ratio NUMERIC, quick_ratio NUMERIC, operating_cf_jpy BIGINT,
        free_cf_jpy BIGINT, source VARCHAR(50), created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(tse_code, fiscal_period));
    CREATE TEMP TABLE _stage (tse_code TEXT, fiscal_period TEXT, fy_end DATE,
        revenue_jpy NUMERIC, net_income_jpy NUMERIC, eps NUMERIC,
        total_assets_jpy NUMERIC, shareholders_equity_jpy NUMERIC,
        roe NUMERIC, roa NUMERIC, operating_cf_jpy NUMERIC, source TEXT);
    \\copy _stage FROM '{LOAD_CSV}' CSV HEADER
    INSERT INTO japan_fundamentals_history
        (tse_code, fiscal_period, filing_date, revenue_jpy, net_income_jpy, eps,
         total_assets_jpy, shareholders_equity_jpy, roe, roa, operating_cf_jpy, source)
    SELECT DISTINCT ON (tse_code, fiscal_period)
           tse_code, fiscal_period, fy_end, revenue_jpy::BIGINT, net_income_jpy::BIGINT,
           eps, total_assets_jpy::BIGINT, shareholders_equity_jpy::BIGINT,
           roe, roa, operating_cf_jpy::BIGINT, source
    FROM _stage
    ORDER BY tse_code, fiscal_period, fy_end DESC
    ON CONFLICT (tse_code, fiscal_period) DO UPDATE SET
        revenue_jpy = EXCLUDED.revenue_jpy, net_income_jpy = EXCLUDED.net_income_jpy,
        eps = EXCLUDED.eps, total_assets_jpy = EXCLUDED.total_assets_jpy,
        shareholders_equity_jpy = EXCLUDED.shareholders_equity_jpy,
        roe = EXCLUDED.roe, roa = EXCLUDED.roa,
        operating_cf_jpy = EXCLUDED.operating_cf_jpy, source = EXCLUDED.source;
    SELECT source, COUNT(*) FROM japan_fundamentals_history GROUP BY source ORDER BY 2 DESC;
    """
    r = subprocess.run(['psql', '-d', 'market_data', '-v', 'ON_ERROR_STOP=1'],
                       input=sql, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print("✗ Postgres load failed:", r.stderr[-800:])
        sys.exit(1)
    print("✓ Postgres japan_fundamentals_history updated")


if __name__ == '__main__':
    main()
