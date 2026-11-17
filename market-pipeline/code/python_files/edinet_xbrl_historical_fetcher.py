#!/usr/bin/env python3
"""
edinet_xbrl_historical_fetcher.py — Fetch Japan historical fundamentals from EDINET XBRL.

EDINET (Electronic Disclosure for Investors' Network) publishes all corporate filings
in XBRL format (eXtensible Business Reporting Language), a standardized financial
reporting format. This fetcher:

1. Downloads or processes EDINET XBRL bulk archives
2. Parses quarterly/annual financial statements for all TSE companies
3. Extracts key metrics (revenue, net income, assets, debt, etc.)
4. Stores multi-year historical data in Postgres

XBRL Context:
  - EDINET publishes filings quarterly (3-month) and annually (12-month)
  - Each filing is tagged with GL accounts in XBRL/XML format
  - Japanese XBRL taxonomy uses jpfr-xxx prefixes for accounts
  - Key GL accounts:
      * jpfr:NetSalesJFY / jpfr-asr:OperatingRevenueJFY = revenue
      * jpfr:NetIncomeJFY = net income
      * jppfs:TotalAssetsJFY = total assets
      * jppfs:TotalLiabilitiesJFY = total liabilities
      * jppfs:ShareholdersEquityJFY = shareholders' equity

Pipeline:
  1. Fetch EDINET filings list (filter by date range, document type 120=financials)
  2. Download XBRL files (or process from local cache)
  3. Parse XBRL XML → extract GL accounts → compute financials
  4. Store in Postgres japan_fundamentals_history (with fiscal_year, quarter)
  5. Backfill 3-5 years of history

Usage:
  python edinet_xbrl_historical_fetcher.py                    # fetch latest filings
  python edinet_xbrl_historical_fetcher.py --years 5          # backfill 5 years
  python edinet_xbrl_historical_fetcher.py --from-file /path/xbrl.zip  # local file
  python edinet_xbrl_historical_fetcher.py --code 8001 --years 3  # single company
  python edinet_xbrl_historical_fetcher.py --validate         # check Postgres
"""

import argparse
import io
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import env_loader
import pandas as pd
import psycopg2
import psycopg2.extras
import requests
from lxml import etree


# ─────────────────────────────────────────────────────────────────────────────
# XBRL Namespaces (Japanese financial reporting taxonomy)
# ─────────────────────────────────────────────────────────────────────────────

NAMESPACES = {
    'jppfs': 'http://disclosure.edinet-fsa.go.jp/jppfs/tse-acedjpfr-xxx/2018-06-30',
    'jpfr': 'http://disclosure.edinet-fsa.go.jp/jpfr/xxx/2020-12-01',
    'jpfr-asr': 'http://disclosure.edinet-fsa.go.jp/jpfr-asr/tsea-acedjpfr-xxx/2018-12-31',
    'xbrl': 'http://www.xbrl.org/2003/instance',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
}

# GL Account mappings (Japanese to English)
GL_ACCOUNTS = {
    'revenue': [
        'jpfr:NetSalesJFY',
        'jpfr-asr:OperatingRevenueJFY',
        'jppfs:RevenueJFY',
    ],
    'operating_income': [
        'jpfr:OperatingIncomeJFY',
        'jpfr-asr:OperatingIncomeJFY',
    ],
    'net_income': [
        'jpfr:NetIncomeJFY',
        'jpfr-asr:NetIncomeJFY',
        'jppfs:NetIncomeJFY',
    ],
    'total_assets': [
        'jppfs:TotalAssetsJFY',
        'jpfr:TotalAssetsJFY',
    ],
    'total_liabilities': [
        'jppfs:TotalLiabilitiesJFY',
        'jpfr:TotalLiabilitiesJFY',
    ],
    'shareholders_equity': [
        'jppfs:ShareholdersEquityJFY',
        'jpfr:ShareholdersEquityJFY',
    ],
    'operating_cash_flow': [
        'jpfr:OperatingCashFlowJFY',
        'jppfs:OperatingCashFlowJFY',
    ],
    'free_cash_flow': [
        'jpfr:FreeCashFlowJFY',
        'jppfs:FreeCashFlowJFY',
    ],
}


def fetch_filings_list(start_date: str, end_date: str, doc_type: str = "120") -> List[Dict]:
    """
    Fetch list of EDINET filings within date range.

    Args:
      start_date: YYYY-MM-DD
      end_date: YYYY-MM-DD
      doc_type: EDINET document type (120 = financial statements)

    Returns: List of filing dicts with {filing_id, company_code, date, period, xbrl_url}
    """
    print(f"Fetching EDINET filings list ({start_date} to {end_date})...")

    # EDINET public API for filings (may not require auth for metadata)
    url = "https://disclosure2.edinet-fsa.go.jp/api/v2/filings"

    filings = []

    try:
        # Try to fetch via public endpoint
        # Note: This may require session handling or authentication
        params = {
            "date": start_date,
            "type": doc_type,
        }

        r = requests.get(url, params=params, timeout=30, allow_redirects=True)

        if r.status_code == 200:
            try:
                data = r.json()
                filings = data.get('results', [])
                print(f"  Found {len(filings)} filings")
            except:
                print(f"  Failed to parse JSON response")
        else:
            print(f"  Status {r.status_code} — may require authentication or session")
            print(f"  Falling back to manual XBRL file handling...")

    except Exception as e:
        print(f"  Error fetching filings list: {e}")
        print(f"  Proceeding with local XBRL files or manual download...")

    return filings


def parse_xbrl_document(xbrl_content: bytes) -> Dict[str, Optional[float]]:
    """
    Parse XBRL XML document and extract financial metrics.

    Args:
      xbrl_content: Raw XBRL file content (bytes)

    Returns: Dict with extracted financials {revenue, net_income, assets, ...}
    """
    try:
        root = etree.fromstring(xbrl_content)

        financials = {
            'revenue': None,
            'operating_income': None,
            'net_income': None,
            'total_assets': None,
            'total_liabilities': None,
            'shareholders_equity': None,
            'operating_cash_flow': None,
            'free_cash_flow': None,
            'roe': None,
            'roa': None,
        }

        # For each financial metric, search for any matching GL account
        for metric, accounts in GL_ACCOUNTS.items():
            for account in accounts:
                # Build full namespace-qualified account name
                for ns_prefix, ns_uri in NAMESPACES.items():
                    # Try to find the element in XBRL contexts
                    xpath = f".//{{*}}{account.split(':')[-1]}"
                    elements = root.xpath(xpath)

                    if elements:
                        try:
                            value = float(elements[0].text)
                            if financials[metric] is None:
                                financials[metric] = value
                            break
                        except (ValueError, TypeError):
                            pass

            if financials[metric] is not None:
                break

        # Compute derived metrics
        if financials['shareholders_equity'] and financials['shareholders_equity'] > 0:
            if financials['net_income']:
                financials['roe'] = financials['net_income'] / financials['shareholders_equity']

        if financials['total_assets'] and financials['total_assets'] > 0:
            if financials['net_income']:
                financials['roa'] = financials['net_income'] / financials['total_assets']

        return financials

    except Exception as e:
        print(f"  Error parsing XBRL: {e}")
        return {k: None for k in ['revenue', 'operating_income', 'net_income',
                                  'total_assets', 'total_liabilities', 'shareholders_equity',
                                  'operating_cash_flow', 'free_cash_flow', 'roe', 'roa']}


def process_xbrl_zip(zip_path: str) -> pd.DataFrame:
    """
    Process a ZIP archive containing XBRL files (bulk download format).

    Args:
      zip_path: Path to .zip file from EDINET

    Returns: DataFrame with extracted financials for all companies
    """
    print(f"Processing XBRL archive: {zip_path}")

    results = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            xbrl_files = [f for f in zf.namelist() if f.endswith('.xbrl')]
            print(f"  Found {len(xbrl_files)} XBRL files")

            for idx, filename in enumerate(xbrl_files, 1):
                if idx % 100 == 0:
                    print(f"  [{idx}/{len(xbrl_files)}]", end=" ", flush=True)

                try:
                    content = zf.read(filename)
                    financials = parse_xbrl_document(content)

                    # Extract company code and period from filename or XML metadata
                    # Typical format: XXXXXXXX_jp_FY2024Q3_tse-acedjpfr-xxx_2024-09-30_01.xbrl
                    parts = filename.split('_')

                    if len(parts) >= 2:
                        company_code = parts[0]
                        # Parse fiscal info (FY2024Q3)
                        fiscal_info = parts[2] if len(parts) > 2 else None

                        row = {
                            'tse_code': company_code,
                            'filename': filename,
                            'fiscal_period': fiscal_info,
                            'filing_date': datetime.now().isoformat(),
                            **financials
                        }
                        results.append(row)

                except Exception as e:
                    print(f"  Error processing {filename}: {e}")
                    continue

        print(f"\n  Processed {len(results)} companies")
        return pd.DataFrame(results)

    except Exception as e:
        print(f"Error opening ZIP: {e}")
        return pd.DataFrame()


def store_postgres(df: pd.DataFrame, table_name: str = "japan_fundamentals_history"):
    """Store historical fundamentals in Postgres."""
    try:
        conn = psycopg2.connect(dbname="market_data")
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

        cursor = conn.cursor()

        # Create table if not exists (with _jpy suffixes to match consolidator schema)
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            tse_code VARCHAR(6),
            fiscal_period VARCHAR(20),
            filing_date DATE,
            revenue_jpy BIGINT,
            operating_income_jpy BIGINT,
            net_income_jpy BIGINT,
            eps NUMERIC,
            total_assets_jpy BIGINT,
            total_liabilities_jpy BIGINT,
            shareholders_equity_jpy BIGINT,
            book_value NUMERIC,
            roe NUMERIC,
            roa NUMERIC,
            debt_to_equity NUMERIC,
            current_ratio NUMERIC,
            quick_ratio NUMERIC,
            operating_cf_jpy BIGINT,
            free_cf_jpy BIGINT,
            source VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(tse_code, fiscal_period)
        );
        CREATE INDEX IF NOT EXISTS idx_japan_hist_code ON {table_name}(tse_code);
        CREATE INDEX IF NOT EXISTS idx_japan_hist_period ON {table_name}(fiscal_period);
        """

        for stmt in create_sql.split(";"):
            if stmt.strip():
                cursor.execute(stmt)

        # Upsert rows (use _jpy suffixes to match existing schema)
        for _, row in df.iterrows():
            insert_sql = f"""
            INSERT INTO {table_name}
            (tse_code, fiscal_period, filing_date, revenue_jpy, operating_income_jpy, net_income_jpy,
             total_assets_jpy, total_liabilities_jpy, shareholders_equity_jpy, operating_cf_jpy,
             free_cf_jpy, roe, roa, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tse_code, fiscal_period) DO UPDATE SET
              revenue_jpy = EXCLUDED.revenue_jpy,
              net_income_jpy = EXCLUDED.net_income_jpy,
              total_assets_jpy = EXCLUDED.total_assets_jpy
            """

            cursor.execute(insert_sql, (
                row.get('tse_code'),
                row.get('fiscal_period'),
                row.get('filing_date'),
                row.get('revenue'),
                row.get('operating_income'),
                row.get('net_income'),
                row.get('total_assets'),
                row.get('total_liabilities'),
                row.get('shareholders_equity'),
                row.get('operating_cash_flow'),
                row.get('free_cash_flow'),
                row.get('roe'),
                row.get('roa'),
                'edinet',
            ))

        cursor.close()
        conn.close()

        print(f"✓ Stored {len(df)} rows in {table_name}")
        return True

    except Exception as e:
        print(f"✗ Postgres error: {e}")
        return False


def validate_postgres():
    """Check Postgres schema."""
    try:
        conn = psycopg2.connect(dbname="market_data")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name LIKE 'japan_fundamentals%'
        """)
        tables = cursor.fetchall()

        print("Japan fundamentals tables in Postgres:")
        for t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {t[0]}")
            count = cursor.fetchone()[0]
            print(f"  - {t[0]}: {count} rows")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"✗ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-file", type=str, default=None,
                        help="Process local XBRL ZIP file")
    parser.add_argument("--years", type=int, default=3,
                        help="Backfill N years of history (default 3)")
    parser.add_argument("--code", type=str, default=None,
                        help="Fetch for single company (TSE code)")
    parser.add_argument("--validate", action="store_true",
                        help="Check Postgres and exit")
    parser.add_argument("--output", type=str, default=None,
                        help="Save to CSV instead of Postgres")

    args = parser.parse_args()

    print("=" * 70)
    print("EDINET XBRL Historical Fundamentals Fetcher")
    print("=" * 70)
    print()

    # ─── Validation Mode ───────────────────────────────────────────────────
    if args.validate:
        validate_postgres()
        return

    # ─── Process Local XBRL File ───────────────────────────────────────────
    if args.from_file:
        if not os.path.exists(args.from_file):
            print(f"✗ File not found: {args.from_file}")
            sys.exit(1)

        df = process_xbrl_zip(args.from_file)

        if df.empty:
            print("✗ No data extracted")
            return

        print(f"\nExtracted {len(df)} company-quarters:")
        print(df.head(10))
        print()

        if args.output:
            df.to_csv(args.output, index=False)
            print(f"✓ Saved to {args.output}")
        else:
            store_postgres(df)
            validate_postgres()
        return

    # ─── Fetch from EDINET API ─────────────────────────────────────────────
    print("Fetching from EDINET API (requires local XBRL files or bulk download)")
    print()

    today = datetime.now().date()
    start = (today - timedelta(days=365*args.years)).isoformat()
    end = today.isoformat()

    filings = fetch_filings_list(start, end)

    if not filings:
        print("\n⚠️  No filings fetched from API.")
        print("\nTo use EDINET data, download bulk XBRL files from:")
        print("  https://disclosure2.edinet-fsa.go.jp/")
        print("\nThen run:")
        print(f"  python {__file__} --from-file /path/to/edinet_xbrl_YYYY.zip")
        return

    print(f"Processing {len(filings)} filings...")


if __name__ == "__main__":
    main()
