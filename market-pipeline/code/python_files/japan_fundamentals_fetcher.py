#!/usr/bin/env python3
"""
japan_fundamentals_fetcher.py — Fetch Japan TSE fundamentals via yfinance.

Pulls latest fundamentals for all Japan stocks from yfinance (which aggregates
data from multiple sources including EDINET filings). Stores in Postgres.

Pipeline:
  1. Load TSE stock list (from JPX or cached japan_list.csv)
  2. Batch fetch via yfinance (parallel, rate-limit aware)
  3. Extract fundamentals: P/E, ROE, debt, market cap, dividend, FCF, etc.
  4. Store in Postgres market_data.japan_fundamentals
  5. Join with price data for screening

Usage:
  python japan_fundamentals_fetcher.py                  # full fetch
  python japan_fundamentals_fetcher.py --limit 50      # first 50 only
  python japan_fundamentals_fetcher.py --tickers 8001,8002,8008  # specific
  python japan_fundamentals_fetcher.py --validate      # check Postgres
  python japan_fundamentals_fetcher.py --output ~/japan_fund.csv  # CSV export
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras
import yfinance as yf


# ─────────────────────────────────────────────────────────────────────────────
# TSE Stock List (manually curated from JPX prime/standard markets)
# ─────────────────────────────────────────────────────────────────────────────

TSE_STOCKS = [
    # Nikkei 225 core (top 50)
    "8001", "8002", "8008",  # Toyota, Mazda, Mitsubishi Motors
    "7203", "7267",           # Toyota, Honda
    "6954", "6981",           # Nidec, Murata
    "8031", "8058",           # Mitsumitsubishi UFJ, Nomura
    "8411", "8306",           # Mizuho, Mitsubishi UFJ
    "9101", "9107", "9201",   # Nippon Steel, U.S. Steel, ANA
    "9202", "9020",           # All Nippon, Japan Airlines
    "4502", "4503",           # Takeda, Shionogi
    "8766", "8795",           # Tokio Marine, Dai-ichi Life
    "9983", "2768",           # SoftBank, Don Quijote
    "6861", "7974", "8309",   # Keyence, Nintendo, Sumitomo Mitsui
    "9984", "4689",           # SoftBank Group, Z Holdings
    "2914", "5108",           # JT, Nissan Chem
    "2801", "2802",           # Komatsu, Sumitomo Electric
    "7182",                   # Japan Post Holdings
    # Add more as needed — this is a sample
]


def load_tse_stocks(limit=None):
    """
    Load TSE stock codes.

    Returns: List of codes (e.g., ["8001", "8002", ...])
    """
    stocks = TSE_STOCKS.copy()
    if limit:
        stocks = stocks[:limit]
    return stocks


def fetch_fundamentals(code, workers=4):
    """
    Fetch fundamentals for a single stock via yfinance.

    Args:
      code: TSE code (e.g., "8001")

    Returns: Dict with fundamentals or None if fetch fails
    """
    ticker_str = f"{code}.T"  # yfinance suffix for Tokyo Stock Exchange

    try:
        stock = yf.Ticker(ticker_str)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return None

        # Extract fundamentals (many may be None)
        fundamentals = {
            "tse_code": code,
            "name": info.get("longName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "price": info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "dividend_rate": info.get("dividendRate"),
            "pe_ratio": info.get("trailingPE"),
            "pb_ratio": info.get("priceToBook"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "total_debt": info.get("totalDebt"),
            "total_assets": info.get("totalAssets"),
            "total_equity": info.get("totalEquity"),
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            "revenue": info.get("totalRevenue"),
            "net_income": info.get("netIncome"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "book_value": info.get("bookValue"),
            "enterprise_value": info.get("enterpriseValue"),
            "eps": info.get("trailingEps"),
            "beta": info.get("beta"),
            "avg_volume": info.get("averageVolume"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "updated_at": datetime.now().isoformat()
        }

        return fundamentals

    except Exception as e:
        print(f"    Error fetching {ticker_str}: {e}")
        return None


def store_postgres(df):
    """
    Store fundamentals DataFrame into Postgres.

    Creates table if not exists.
    """
    try:
        conn = psycopg2.connect(
            dbname="market_data",
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432))
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

        cursor = conn.cursor()

        # Create table if not exists
        create_sql = """
        CREATE TABLE IF NOT EXISTS japan_fundamentals (
            tse_code VARCHAR(6) PRIMARY KEY,
            name VARCHAR(255),
            sector VARCHAR(100),
            industry VARCHAR(100),
            price NUMERIC,
            market_cap BIGINT,
            dividend_rate NUMERIC,
            pe_ratio NUMERIC,
            pb_ratio NUMERIC,
            roe NUMERIC,
            roa NUMERIC,
            total_debt BIGINT,
            total_assets BIGINT,
            total_equity BIGINT,
            free_cash_flow BIGINT,
            operating_cash_flow BIGINT,
            revenue BIGINT,
            net_income BIGINT,
            debt_to_equity NUMERIC,
            current_ratio NUMERIC,
            quick_ratio NUMERIC,
            book_value NUMERIC,
            enterprise_value BIGINT,
            eps NUMERIC,
            beta NUMERIC,
            avg_volume BIGINT,
            fifty_two_week_high NUMERIC,
            fifty_two_week_low NUMERIC,
            updated_at TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_japan_fund_code ON japan_fundamentals(tse_code);
        CREATE INDEX IF NOT EXISTS idx_japan_fund_updated ON japan_fundamentals(updated_at);
        """
        for stmt in create_sql.split(";"):
            if stmt.strip():
                cursor.execute(stmt)

        # Upsert rows
        insert_sql = """
        INSERT INTO japan_fundamentals VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                               %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                               %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tse_code) DO UPDATE SET
          name = EXCLUDED.name,
          price = EXCLUDED.price,
          market_cap = EXCLUDED.market_cap,
          pe_ratio = EXCLUDED.pe_ratio,
          roe = EXCLUDED.roe,
          total_debt = EXCLUDED.total_debt,
          updated_at = EXCLUDED.updated_at
        """

        cols = [
            'tse_code', 'name', 'sector', 'industry', 'price', 'market_cap',
            'dividend_rate', 'pe_ratio', 'pb_ratio', 'roe', 'roa', 'total_debt',
            'total_assets', 'total_equity', 'free_cash_flow', 'operating_cash_flow',
            'revenue', 'net_income', 'debt_to_equity', 'current_ratio', 'quick_ratio',
            'book_value', 'enterprise_value', 'eps', 'beta', 'avg_volume',
            'fifty_two_week_high', 'fifty_two_week_low', 'updated_at'
        ]

        for _, row in df.iterrows():
            values = tuple(row[col] for col in cols)
            cursor.execute(insert_sql, values)

        conn.commit()
        cursor.close()
        conn.close()

        print(f"✓ Stored {len(df)} rows in japan_fundamentals")

    except Exception as e:
        print(f"✗ Postgres error: {e}")
        return False

    return True


def validate_postgres():
    """Check Postgres schema for Japan fundamentals."""
    try:
        conn = psycopg2.connect(dbname="market_data")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'japan_fundamentals'
        """)
        exists = cursor.fetchone()

        if exists:
            cursor.execute("SELECT COUNT(*) FROM japan_fundamentals")
            count = cursor.fetchone()[0]
            print(f"✓ japan_fundamentals table exists ({count} rows)")

            cursor.execute("""
                SELECT MAX(updated_at) FROM japan_fundamentals
            """)
            last_update = cursor.fetchone()[0]
            print(f"  Last update: {last_update}")
        else:
            print("✗ japan_fundamentals table does not exist")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"✗ Postgres error: {e}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None,
                        help="Fetch only first N stocks")
    parser.add_argument("--tickers", type=str, default=None,
                        help="Comma-separated TSE codes (e.g., 8001,8002)")
    parser.add_argument("--validate", action="store_true",
                        help="Check Postgres schema and exit")
    parser.add_argument("--output", type=str, default=None,
                        help="Save to CSV instead of Postgres")
    parser.add_argument("--workers", type=int, default=4,
                        help="Parallel fetch workers (default 4)")

    args = parser.parse_args()

    print("=" * 70)
    print("Japan Fundamentals Fetcher (yfinance + Postgres)")
    print("=" * 70)
    print()

    # ─── Validation Mode ───────────────────────────────────────────────────
    if args.validate:
        validate_postgres()
        return

    # ─── Load Stock Codes ──────────────────────────────────────────────────
    if args.tickers:
        stocks = args.tickers.split(",")
    else:
        stocks = load_tse_stocks(limit=args.limit)

    print(f"Fetching fundamentals for {len(stocks)} stocks...")
    print()

    # ─── Parallel Fetch ────────────────────────────────────────────────────
    results = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_fundamentals, code): code for code in stocks}

        for idx, future in enumerate(as_completed(futures), 1):
            code = futures[future]
            try:
                fund = future.result()
                if fund:
                    results.append(fund)
                    print(f"[{idx}/{len(stocks)}] {code}  ✓ {fund.get('name', '')[:40]}")
                else:
                    print(f"[{idx}/{len(stocks)}] {code}  — (no data)")
            except Exception as e:
                print(f"[{idx}/{len(stocks)}] {code}  ✗ {e}")

    if not results:
        print("\n✗ No data fetched.")
        return

    df = pd.DataFrame(results)
    print(f"\n{'='*70}")
    print(f"Total rows: {len(df)}")
    print(f"Columns with data:")
    for col in df.columns:
        non_null = df[col].notna().sum()
        if non_null > 0:
            print(f"  {col}: {non_null}/{len(df)}")
    print()

    # ─── Output ────────────────────────────────────────────────────────────
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"✓ Saved to {args.output}")
    else:
        if store_postgres(df):
            print(f"✓ Japan fundamentals updated.")
            validate_postgres()


if __name__ == "__main__":
    main()
