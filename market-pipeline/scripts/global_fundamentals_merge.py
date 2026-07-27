#!/usr/bin/env python3
"""
global_fundamentals_merge.py — One consistent fundamentals layer for ALL markets.

Reads every per-market parquet in global-stock-screener/cache_seed/fundamentals_history,
maps each to one canonical schema, and loads Postgres `global_fundamentals`
keyed (market, ticker, fiscal_period). Values stay in local currency; `filed`
is kept where the source is point-in-time (US SEC EDGAR, KR_deep, etc.).

Market-specific mappings:
  IN  screener.in schema → equity = equity_capital + reserves, debt = borrowings
  JP  JP_master.parquet (today's EDINET aggregate)
  KR  KR_master.parquet if present (DART run), else deep+dart_joined+core
  CN  CN_baostock (fields) + CN_full (eps/roe supplement)
  US/EU/AU/…  canonical yfinance/EDGAR columns pass through

Also prints a consistency report: rows, tickers, date range, key-field fill
rates, and duplicate counts per market.

Run with /usr/bin/python3 (pandas + pyarrow).
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd

FUND = Path('/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history')
LOAD_CSV = Path('/tmp/global_fundamentals_load.csv')
MASTER_OUT = FUND / 'GLOBAL_master.parquet'

CANON = ['market', 'ticker', 'fy_end', 'filed', 'revenue', 'gross_profit', 'ebit',
         'net_income', 'equity', 'total_assets', 'total_liabilities',
         'current_assets', 'current_liabilities', 'long_term_debt', 'cfo',
         'shares', 'eps', 'roe', 'roa', 'currency', 'source']

CURRENCY = {'US': 'USD', 'IN': 'INR', 'JP': 'JPY', 'KR': 'KRW', 'CN': 'CNY',
            'EU': 'local', 'AU': 'AUD', 'BR': 'BRL', 'CA': 'CAD', 'CH': 'CHF',
            'DE': 'EUR', 'DK': 'DKK', 'FI': 'EUR', 'HK': 'HKD', 'SA': 'SAR',
            'SE': 'SEK', 'SG': 'SGD', 'TW': 'TWD', 'ZA': 'ZAR'}


def canonize(df: pd.DataFrame, market: str, source: str) -> pd.DataFrame:
    out = pd.DataFrame()
    out['ticker'] = df['ticker'].astype(str).str.strip()
    out['fy_end'] = pd.to_datetime(df['fy_end'], errors='coerce')
    for c in ['filed', 'revenue', 'gross_profit', 'ebit', 'net_income', 'equity',
              'total_assets', 'total_liabilities', 'current_assets',
              'current_liabilities', 'long_term_debt', 'cfo', 'shares', 'eps',
              'roe', 'roa']:
        out[c] = df[c] if c in df.columns else None
    out['market'] = market
    out['currency'] = CURRENCY.get(market, 'local')
    out['source'] = source
    return out[CANON].dropna(subset=['fy_end'])


def load_market(market: str) -> pd.DataFrame:
    """Load + map one market. Returns canonical frame (may concat sources)."""
    frames = []

    if market == 'JP':
        df = pd.read_parquet(FUND / 'JP_master.parquet')
        frames.append(canonize(df, 'JP', 'jp_master'))

    elif market == 'KR':
        if (FUND / 'KR_master.parquet').exists():
            frames.append(canonize(pd.read_parquet(FUND / 'KR_master.parquet'),
                                   'KR', 'kr_master'))
        else:
            for name, src in [('KR_dart_joined.parquet', 'dart'),
                              ('KR_deep.parquet', 'kr_deep'),
                              ('KR.parquet', 'kr_core')]:
                if (FUND / name).exists():
                    frames.append(canonize(pd.read_parquet(FUND / name), 'KR', src))

    elif market == 'IN':
        df = pd.read_parquet(FUND / 'IN_screener_only_backup.parquet')
        m = pd.DataFrame()
        m['ticker'] = df['ticker']
        m['fy_end'] = df['fy_end']
        m['revenue'] = df.get('revenue')
        m['gross_profit'] = df.get('gross_profit')
        m['ebit'] = df.get('ebit')
        m['net_income'] = df.get('net_income')
        m['equity'] = df.get('equity_capital', 0).fillna(0) + df.get('reserves', 0).fillna(0)
        m['long_term_debt'] = df.get('borrowings')
        m['cfo'] = df.get('cfo')
        m['shares'] = df.get('shares')
        frames.append(canonize(m, 'IN', 'screener_in'))

    elif market == 'CN':
        # CN_em (Eastmoney bulk, full statements) wins; ratio-only sources fill gaps
        if (FUND / 'CN_em.parquet').exists():
            em = pd.read_parquet(FUND / 'CN_em.parquet')
            frames.append(canonize(em, 'CN', 'eastmoney'))
        if (FUND / 'CN_baostock.parquet').exists():
            bs = pd.read_parquet(FUND / 'CN_baostock.parquet')
            frames.append(canonize(bs, 'CN', 'baostock'))
        if (FUND / 'CN_full.parquet').exists():
            cf = pd.read_parquet(FUND / 'CN_full.parquet')
            frames.append(canonize(cf, 'CN', 'cn_full'))

    elif market == 'EU':
        df = pd.read_parquet(FUND / 'EU_union.parquet')
        frames.append(canonize(df, 'EU', 'eu_union'))

    else:  # US and all canonical shallow markets
        p = FUND / f'{market}.parquet'
        if p.exists():
            src = 'sec_edgar' if market == 'US' else 'yfinance'
            frames.append(canonize(pd.read_parquet(p), market, src))

    if not frames:
        return pd.DataFrame(columns=CANON)
    return pd.concat(frames, ignore_index=True)


def main():
    markets = ['US', 'IN', 'JP', 'KR', 'CN', 'EU',
               'AU', 'BR', 'CA', 'CH', 'DE', 'DK', 'FI', 'HK', 'SA', 'SE',
               'SG', 'TW', 'ZA']

    all_frames = []
    print(f"{'mkt':4s} {'rows':>7s} {'tickers':>7s}  {'range':23s} "
          f"{'rev%':>5s} {'ni%':>5s} {'eq%':>5s} {'filed%':>6s}")
    print('-' * 72)

    for mkt in markets:
        df = load_market(mkt)
        if df.empty:
            print(f"{mkt:4s} {'—':>7s}")
            continue
        # Dedupe within market: first source wins (frames appended in priority order)
        df = df.drop_duplicates(subset=['ticker', 'fy_end'], keep='first')
        fill = {c: df[c].notna().mean() * 100 for c in ['revenue', 'net_income', 'equity', 'filed']}
        rng = f"{df['fy_end'].min().date()} → {df['fy_end'].max().date()}"
        print(f"{mkt:4s} {len(df):7d} {df['ticker'].nunique():7d}  {rng:23s} "
              f"{fill['revenue']:5.0f} {fill['net_income']:5.0f} {fill['equity']:5.0f} "
              f"{fill['filed']:6.0f}")
        all_frames.append(df)

    g = pd.concat(all_frames, ignore_index=True)
    g['filed'] = pd.to_datetime(g['filed'], errors='coerce')
    # roe/roa where computable and absent
    ni = pd.to_numeric(g['net_income'], errors='coerce')
    eq = pd.to_numeric(g['equity'], errors='coerce')
    ta = pd.to_numeric(g['total_assets'], errors='coerce')
    g['roe'] = pd.to_numeric(g['roe'], errors='coerce').fillna((ni / eq).where(eq != 0)).round(4)
    g['roa'] = pd.to_numeric(g['roa'], errors='coerce').fillna((ni / ta).where(ta != 0)).round(4)
    g['fiscal_period'] = g['fy_end'].dt.strftime('FY%Y-%m')

    print('-' * 72)
    print(f"TOTAL {len(g):,} rows · {g.groupby('market')['ticker'].nunique().sum():,} "
          f"market-tickers · {g['market'].nunique()} markets")

    g.to_parquet(MASTER_OUT, index=False)
    print(f"✓ {MASTER_OUT.name} ({MASTER_OUT.stat().st_size/1e6:.1f} MB)")

    cols = ['market', 'ticker', 'fiscal_period', 'fy_end', 'filed', 'revenue',
            'gross_profit', 'ebit', 'net_income', 'equity', 'total_assets',
            'total_liabilities', 'current_assets', 'current_liabilities',
            'long_term_debt', 'cfo', 'shares', 'eps', 'roe', 'roa', 'currency', 'source']
    g[cols].to_csv(LOAD_CSV, index=False)

    sql = f"""
    CREATE TABLE IF NOT EXISTS global_fundamentals (
        id SERIAL PRIMARY KEY, market VARCHAR(4), ticker VARCHAR(20),
        fiscal_period VARCHAR(20), fy_end DATE, filed DATE,
        revenue NUMERIC, gross_profit NUMERIC, ebit NUMERIC, net_income NUMERIC,
        equity NUMERIC, total_assets NUMERIC, total_liabilities NUMERIC,
        current_assets NUMERIC, current_liabilities NUMERIC, long_term_debt NUMERIC,
        cfo NUMERIC, shares NUMERIC, eps NUMERIC, roe NUMERIC, roa NUMERIC,
        currency VARCHAR(6), source VARCHAR(30), created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(market, ticker, fiscal_period));
    CREATE INDEX IF NOT EXISTS idx_gf_market ON global_fundamentals(market);
    CREATE INDEX IF NOT EXISTS idx_gf_ticker ON global_fundamentals(market, ticker);
    CREATE TEMP TABLE _st (market TEXT, ticker TEXT, fiscal_period TEXT, fy_end DATE,
        filed DATE, revenue NUMERIC, gross_profit NUMERIC, ebit NUMERIC,
        net_income NUMERIC, equity NUMERIC, total_assets NUMERIC,
        total_liabilities NUMERIC, current_assets NUMERIC, current_liabilities NUMERIC,
        long_term_debt NUMERIC, cfo NUMERIC, shares NUMERIC, eps NUMERIC,
        roe NUMERIC, roa NUMERIC, currency TEXT, source TEXT);
    \\copy _st FROM '{LOAD_CSV}' CSV HEADER
    INSERT INTO global_fundamentals
        (market, ticker, fiscal_period, fy_end, filed, revenue, gross_profit, ebit,
         net_income, equity, total_assets, total_liabilities, current_assets,
         current_liabilities, long_term_debt, cfo, shares, eps, roe, roa,
         currency, source)
    SELECT DISTINCT ON (market, ticker, fiscal_period) market, ticker, fiscal_period,
        fy_end, filed, revenue, gross_profit, ebit, net_income, equity, total_assets,
        total_liabilities, current_assets, current_liabilities, long_term_debt,
        cfo, shares, eps, roe, roa, currency, source
    FROM _st ORDER BY market, ticker, fiscal_period, fy_end DESC
    ON CONFLICT (market, ticker, fiscal_period) DO UPDATE SET
        filed = EXCLUDED.filed, revenue = EXCLUDED.revenue,
        gross_profit = EXCLUDED.gross_profit, ebit = EXCLUDED.ebit,
        net_income = EXCLUDED.net_income, equity = EXCLUDED.equity,
        total_assets = EXCLUDED.total_assets,
        total_liabilities = EXCLUDED.total_liabilities,
        current_assets = EXCLUDED.current_assets,
        current_liabilities = EXCLUDED.current_liabilities,
        long_term_debt = EXCLUDED.long_term_debt, cfo = EXCLUDED.cfo,
        shares = EXCLUDED.shares, eps = EXCLUDED.eps, roe = EXCLUDED.roe,
        roa = EXCLUDED.roa, source = EXCLUDED.source;
    SELECT market, COUNT(*) rows, COUNT(DISTINCT ticker) tickers,
           MIN(fy_end) min_fy, MAX(fy_end) max_fy
    FROM global_fundamentals GROUP BY market ORDER BY rows DESC;
    """
    r = subprocess.run(['psql', '-d', 'market_data', '-v', 'ON_ERROR_STOP=1'],
                       input=sql, capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print('✗ Postgres load failed:', r.stderr[-600:])
        sys.exit(1)
    print('✓ Postgres global_fundamentals updated')


if __name__ == '__main__':
    main()
