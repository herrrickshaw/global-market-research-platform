#!/usr/bin/env python3
"""
cn_fundamentals_bulk.py — Real China A-share fundamentals via akshare/Eastmoney.

Fixes the CN gap (baostock gave only eps/roe ratios). Eastmoney's report-date
endpoints return ALL ~5,200 A-shares per call — 3 statements × N years ≈ 3N
requests total, no per-stock loop:

  stock_lrb_em(date)   income statement  (营业总收入 revenue, 净利润 net income, 营业利润 op income)
  stock_zcfz_em(date)  balance sheet     (资产-总资产, 负债-总负债, 股东权益合计)
  stock_xjll_em(date)  cash flow         (经营性现金流-现金流量净额 CFO)

Output: cache_seed/fundamentals_history/CN_em.parquet (canonical schema).
Then rerun global_fundamentals_merge.py to fold into Postgres.

Usage:
  python3 cn_fundamentals_bulk.py --years 2018,2019,2020,2021,2022,2023,2024
"""

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

OUT = Path('/Users/umashankar/repos/global-stock-screener/cache_seed/'
           'fundamentals_history/CN_em.parquet')


def fetch_year(ak, year: str) -> pd.DataFrame:
    date = f"{year}1231"
    print(f"[{year}] fetching income / balance / cashflow …", flush=True)

    lrb = ak.stock_lrb_em(date=date)
    time.sleep(1)
    zcfz = ak.stock_zcfz_em(date=date)
    time.sleep(1)
    xjll = ak.stock_xjll_em(date=date)
    time.sleep(1)

    inc = lrb[['股票代码', '股票简称', '营业总收入', '营业利润', '净利润']].rename(columns={
        '股票代码': 'ticker', '股票简称': 'name', '营业总收入': 'revenue',
        '营业利润': 'operating_income', '净利润': 'net_income'})
    bal = zcfz[['股票代码', '资产-总资产', '负债-总负债', '股东权益合计']].rename(columns={
        '股票代码': 'ticker', '资产-总资产': 'total_assets',
        '负债-总负债': 'total_liabilities', '股东权益合计': 'equity'})
    cf = xjll[['股票代码', '经营性现金流-现金流量净额']].rename(columns={
        '股票代码': 'ticker', '经营性现金流-现金流量净额': 'cfo'})

    df = inc.merge(bal, on='ticker', how='outer').merge(cf, on='ticker', how='outer')
    df['fy_end'] = f"{year}-12-31"
    print(f"[{year}] {len(df)} companies", flush=True)
    return df


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--years', default='2018,2019,2020,2021,2022,2023,2024')
    args = p.parse_args()

    import akshare as ak

    years = [y.strip() for y in args.years.split(',')]
    frames = []
    for y in years:
        for attempt in (1, 2):
            try:
                frames.append(fetch_year(ak, y))
                break
            except Exception as e:
                print(f"[{y}] attempt {attempt} failed: {e}")
                time.sleep(5)

    if not frames:
        print("✗ nothing fetched")
        sys.exit(1)

    allf = pd.concat(frames, ignore_index=True)
    allf['ticker'] = allf['ticker'].astype(str).str.zfill(6)
    for c in ['revenue', 'operating_income', 'net_income', 'total_assets',
              'total_liabilities', 'equity', 'cfo']:
        allf[c] = pd.to_numeric(allf[c], errors='coerce')
    allf = allf.dropna(subset=['net_income', 'revenue'], how='all')
    allf = allf.drop_duplicates(subset=['ticker', 'fy_end'])

    try:
        allf.to_parquet(OUT, index=False)
    except ImportError:
        csv_out = OUT.with_suffix('.csv')  # pyarrow missing — never lose the fetch
        allf.to_csv(csv_out, index=False)
        print(f"⚠ pyarrow missing — wrote {csv_out} instead")
    filled = allf['revenue'].notna().mean() * 100
    print(f"\n✓ {OUT.name}: {len(allf)} rows, {allf['ticker'].nunique()} tickers, "
          f"{len(years)} years, revenue fill {filled:.0f}% "
          f"({OUT.stat().st_size/1e6:.1f} MB)")
    print("Next: /usr/bin/python3 scripts/global_fundamentals_merge.py")


if __name__ == '__main__':
    main()
