#!/usr/bin/env python3
"""
japan_data_consolidator.py — Consolidate Japan historical data from multiple sources.

Strategy:
  1. Extract existing scan data (yfinance prices + Darvas + Quality scores)
  2. Seed Postgres with current snapshot
  3. Merge with EDINET fundamentals as they arrive
  4. Build unified Japan fundamental + technical dataset

Sources:
  - yfinance: Real-time prices, current P/E, ROE (200 companies)
  - Darvas: Box signals from daily pipeline
  - EDINET: Quarterly financial statements (all companies, after download)

Postgres Schema:
  japan_current     — Latest snapshot (prices + signals + available fundamentals)
  japan_fundamentals_history  — Historical quarterly data (from EDINET)
  japan_price_history — Daily prices (optional, for backtesting)

Usage:
  python japan_data_consolidator.py --load-scan         # Load latest scan into Postgres
  python japan_data_consolidator.py --validate          # Check Postgres
  python japan_data_consolidator.py --export csv        # Export to CSV
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import env_loader
import pandas as pd
import psycopg2
import psycopg2.extras


def load_latest_scan() -> pd.DataFrame:
    """Load latest Japan market scan workbook."""
    scan_dir = Path('/Users/umashankar/market-pipeline/code/python_files/japan_scan')

    if not scan_dir.exists():
        print(f"✗ Scan directory not found: {scan_dir}")
        return pd.DataFrame()

    # Find latest xlsx
    scans = sorted(scan_dir.glob('japan_market_scan_*.xlsx'), reverse=True)

    if not scans:
        print("✗ No scan files found")
        return pd.DataFrame()

    latest = scans[0]
    print(f"Loading: {latest.name}")

    try:
        # Load All_Stocks sheet (has all 2937 companies)
        df = pd.read_excel(latest, sheet_name='All_Stocks')
        print(f"  All_Stocks: {len(df)} rows, {len(df.columns)} columns")

        # Load Fundamentals sheet (200 companies with detailed data)
        try:
            fund_df = pd.read_excel(latest, sheet_name='Fundamentals')
            print(f"  Fundamentals: {len(fund_df)} rows")

            # Merge fundamentals into main df
            # Join on Code column
            df = df.merge(fund_df[['Code', 'ROE', 'Revenue', 'NetIncome', 'Debt', 'PE', 'PB']],
                         on='Code', how='left', suffixes=('', '_detail'))
            print(f"  After merge: {df.shape}")
        except Exception as e:
            print(f"  Warning: Could not load Fundamentals sheet: {e}")

        return df

    except Exception as e:
        print(f"✗ Error loading scan: {e}")
        return pd.DataFrame()


def create_schema(cursor):
    """Create Postgres schema for Japan data."""

    sql = """
    -- Current snapshot (real-time prices + signals)
    CREATE TABLE IF NOT EXISTS japan_current (
        id SERIAL PRIMARY KEY,
        tse_code VARCHAR(6) UNIQUE NOT NULL,
        yf_ticker VARCHAR(10),
        company_name VARCHAR(255),
        sector VARCHAR(100),
        ltp_jpy NUMERIC,
        change_pct NUMERIC,
        turnover_usd NUMERIC,
        liquidity_tier VARCHAR(20),

        -- Darvas signals
        darvas_signal VARCHAR(20),
        box_top NUMERIC,
        box_bottom NUMERIC,
        upside_to_top_pct NUMERIC,

        -- Quality / Technical
        quality_score NUMERIC,
        quality_grade VARCHAR(5),
        ema50 NUMERIC,
        dma50 NUMERIC,
        dma200 NUMERIC,
        gc_signal VARCHAR(20),

        -- Fundamentals (from yfinance or EDINET)
        pe_ratio NUMERIC,
        pb_ratio NUMERIC,
        roe NUMERIC,
        roa NUMERIC,
        debt_to_equity NUMERIC,

        -- Financial statement data (from EDINET when available)
        revenue_jpy BIGINT,
        net_income_jpy BIGINT,
        total_assets_jpy BIGINT,
        total_debt_jpy BIGINT,

        -- Metadata
        data_source VARCHAR(50),  -- 'yfinance', 'edinet', 'hybrid'
        last_price_date DATE,
        last_fundamental_date DATE,
        updated_at TIMESTAMP DEFAULT NOW()
    );

    -- Historical quarterly fundamentals (from EDINET)
    CREATE TABLE IF NOT EXISTS japan_fundamentals_history (
        id SERIAL PRIMARY KEY,
        tse_code VARCHAR(6),
        fiscal_period VARCHAR(20),  -- 'FY2024Q3', 'FY2023'
        filing_date DATE,

        -- Income statement
        revenue_jpy BIGINT,
        operating_income_jpy BIGINT,
        net_income_jpy BIGINT,
        eps NUMERIC,

        -- Balance sheet
        total_assets_jpy BIGINT,
        total_liabilities_jpy BIGINT,
        shareholders_equity_jpy BIGINT,
        book_value NUMERIC,

        -- Ratios
        roe NUMERIC,
        roa NUMERIC,
        debt_to_equity NUMERIC,
        current_ratio NUMERIC,
        quick_ratio NUMERIC,

        -- Cash flow
        operating_cf_jpy BIGINT,
        free_cf_jpy BIGINT,

        -- Metadata
        source VARCHAR(50),  -- 'edinet', 'yfinance'
        created_at TIMESTAMP DEFAULT NOW(),

        UNIQUE(tse_code, fiscal_period)
    );

    CREATE INDEX IF NOT EXISTS idx_japan_hist_code ON japan_fundamentals_history(tse_code);
    CREATE INDEX IF NOT EXISTS idx_japan_hist_period ON japan_fundamentals_history(fiscal_period);

    CREATE INDEX IF NOT EXISTS idx_japan_current_code ON japan_current(tse_code);
    CREATE INDEX IF NOT EXISTS idx_japan_current_signal ON japan_current(darvas_signal);
    CREATE INDEX IF NOT EXISTS idx_japan_current_updated ON japan_current(updated_at);
    """

    for stmt in sql.split(';'):
        if stmt.strip():
            cursor.execute(stmt)


def insert_snapshot(cursor, df: pd.DataFrame):
    """Insert/update current snapshot from latest scan."""

    print(f"Inserting {len(df)} rows into japan_current...")

    insert_sql = """
    INSERT INTO japan_current (
        tse_code, yf_ticker, company_name, sector, ltp_jpy, change_pct,
        turnover_usd, liquidity_tier, darvas_signal, box_top, box_bottom,
        upside_to_top_pct, quality_score, ema50, dma50, dma200, gc_signal,
        pe_ratio, roe, revenue_jpy, net_income_jpy, data_source, last_price_date, updated_at
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (tse_code) DO UPDATE SET
        ltp_jpy = EXCLUDED.ltp_jpy,
        darvas_signal = EXCLUDED.darvas_signal,
        quality_score = EXCLUDED.quality_score,
        roe = EXCLUDED.roe,
        updated_at = EXCLUDED.updated_at
    """

    rows_inserted = 0

    for _, row in df.iterrows():
        try:
            values = (
                str(row.get('Code', '')),                 # tse_code
                row.get('YF_Ticker', None),               # yf_ticker
                row.get('Name', ''),                      # company_name
                row.get('Sector', ''),                    # sector
                row.get('LTP_JPY'),                       # ltp_jpy
                row.get('Change%'),                       # change_pct
                row.get('Turnover_USD'),                  # turnover_usd
                row.get('Liquidity_Tier'),                # liquidity_tier
                row.get('Darvas_Signal'),                 # darvas_signal
                row.get('Box_Top'),                       # box_top
                row.get('Box_Bottom'),                    # box_bottom
                row.get('Upside_to_Top%'),                # upside_to_top_pct
                row.get('Quality_Score'),                 # quality_score
                row.get('EMA50'),                         # ema50
                row.get('DMA50'),                         # dma50
                row.get('DMA200'),                        # dma200
                row.get('GC_Signal'),                     # gc_signal
                row.get('PE'),                            # pe_ratio
                row.get('ROE'),                           # roe
                row.get('Revenue'),                       # revenue_jpy
                row.get('NetIncome'),                     # net_income_jpy
                'yfinance+darvas',                        # data_source
                pd.Timestamp.now().date(),                # last_price_date
                datetime.now(),                           # updated_at
            )

            cursor.execute(insert_sql, values)
            rows_inserted += 1

            if rows_inserted % 500 == 0:
                print(f"  [{rows_inserted}/{len(df)}]", end=" ", flush=True)

        except Exception as e:
            print(f"\n  Error inserting {row.get('Code')}: {e}")
            continue

    print(f"\n✓ Inserted {rows_inserted} rows")


def validate_postgres():
    """Check Postgres tables."""
    try:
        conn = psycopg2.connect(dbname="market_data")
        cursor = conn.cursor()

        print("\n=== Japan Tables in Postgres ===")

        cursor.execute("SELECT COUNT(*) FROM japan_current")
        count = cursor.fetchone()[0]
        print(f"japan_current: {count} companies")

        cursor.execute("""
            SELECT darvas_signal, COUNT(*)
            FROM japan_current
            GROUP BY darvas_signal
            ORDER BY COUNT(*) DESC
        """)
        signals = cursor.fetchall()
        print(f"  Darvas distribution:")
        for signal, cnt in signals:
            print(f"    {signal}: {cnt}")

        cursor.execute("SELECT COUNT(*) FROM japan_fundamentals_history")
        hist_count = cursor.fetchone()[0]
        print(f"\njapan_fundamentals_history: {hist_count} historical quarters (will populate from EDINET)")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load-scan", action="store_true",
                        help="Load latest Japan scan into Postgres")
    parser.add_argument("--validate", action="store_true",
                        help="Check Postgres tables")
    parser.add_argument("--export", type=str, choices=['csv', 'parquet'],
                        help="Export japan_current to file")

    args = parser.parse_args()

    print("=" * 70)
    print("Japan Data Consolidator")
    print("=" * 70)
    print()

    if args.validate:
        validate_postgres()
        return

    if args.load_scan:
        print("Loading latest Japan scan...")
        df = load_latest_scan()

        if df.empty:
            print("✗ Failed to load scan")
            return

        # Connect to Postgres
        try:
            conn = psycopg2.connect(dbname="market_data")
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # Create schema
            print("\nCreating Postgres schema...")
            create_schema(cursor)

            # Insert data
            print("\nInserting data...")
            insert_snapshot(cursor, df)

            cursor.close()
            conn.close()

            print("\n✓ Consolidation complete")
            validate_postgres()

        except Exception as e:
            print(f"✗ Postgres error: {e}")
            sys.exit(1)

    if args.export:
        print(f"Exporting to {args.export}...")
        try:
            conn = psycopg2.connect(dbname="market_data")
            df = pd.read_sql("SELECT * FROM japan_current", conn)

            if args.export == 'csv':
                df.to_csv('/tmp/japan_current.csv', index=False)
                print(f"✓ Exported to /tmp/japan_current.csv")
            elif args.export == 'parquet':
                df.to_parquet('/tmp/japan_current.parquet', index=False)
                print(f"✓ Exported to /tmp/japan_current.parquet")

            conn.close()
        except Exception as e:
            print(f"✗ Error: {e}")


if __name__ == "__main__":
    main()
