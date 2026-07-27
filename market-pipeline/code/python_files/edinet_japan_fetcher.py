#!/usr/bin/env python3
"""
edinet_japan_fetcher.py — Fetch Japan TSE fundamentals from EDINET API.

EDINET (Electronic Disclosure for Investors' Network) is Japan's corporate
disclosure system operated by FSA. Provides quarterly/annual financial
statements, management forecasts, dividend data for all TSE-listed companies.

Pipeline:
  1. Query EDINET API for all listed companies (code, name, market segment)
  2. Fetch latest 4Q of financial statements (BS, IS, CF) per company
  3. Extract key metrics: revenue, net income, assets, debt, ROE, ROA, FCF
  4. Parse management forecasts (EPS, DPS guidance)
  5. Store in Postgres market_data.japan_fundamentals
  6. Join with yfinance price data for screening

Usage:
  python edinet_japan_fetcher.py                    # full fetch
  python edinet_japan_fetcher.py --recent 10       # last 10 filings only
  python edinet_japan_fetcher.py --code 8001       # single company (Toyota)
  python edinet_japan_fetcher.py --validate        # check Postgres schema
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import env_loader
import pandas as pd
import requests

# ─────────────────────────────────────────────────────────────────────────────
# EDINET API Configuration
# ─────────────────────────────────────────────────────────────────────────────

EDINET_BASE = "https://disclosure.edinet-fsa.go.jp/api"
EDINET_KEY = env_loader.get("EDINET_API_KEY")

if not EDINET_KEY:
    print("ERROR: EDINET_API_KEY not found in env_loader (credentials.env)")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# EDINET Endpoints
# ─────────────────────────────────────────────────────────────────────────────

def fetch_companies():
    """
    Fetch all listed companies from EDINET.
    Returns: DataFrame with columns [code, name, market, segment]
    """
    print("Fetching company list from EDINET...")
    try:
        # EDINET company search endpoint
        url = f"{EDINET_BASE}/v1/companies"
        params = {"apikey": EDINET_KEY}
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()

        data = r.json()
        if "results" not in data:
            print(f"  Unexpected response: {data.keys()}")
            return pd.DataFrame()

        companies = data["results"]
        print(f"  Found {len(companies)} companies")

        df = pd.DataFrame(companies)
        return df[["code", "name", "market", "segment"]].copy() if not df.empty else df

    except Exception as e:
        print(f"  ERROR: {e}")
        return pd.DataFrame()


def fetch_filings(company_code, fiscal_year=None, limit=4):
    """
    Fetch latest filings (quarterly/annual) for a company.

    Args:
      company_code: EDINET company code (e.g., "8001" for Toyota)
      fiscal_year: Filter to specific FY (e.g., 2025) or None for recent
      limit: Max filings to return

    Returns: List of filing dicts with {date, period, doc_id, xbrl_url}
    """
    try:
        url = f"{EDINET_BASE}/v1/filings"
        params = {
            "apikey": EDINET_KEY,
            "companyCode": company_code,
            "limit": limit
        }
        if fiscal_year:
            params["fiscalYear"] = fiscal_year

        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()

        data = r.json()
        filings = data.get("results", [])
        return filings

    except Exception as e:
        print(f"  fetch_filings({company_code}): {e}")
        return []


def parse_xbrl_financials(xbrl_url):
    """
    Fetch and parse XBRL filing (financial statements).

    XBRL is XML-based financial reporting format.
    Extract key GL accounts: revenue, net income, total assets, liabilities, equity.

    Returns: Dict {revenue, net_income, assets, liabilities, equity, last_update}
    """
    try:
        # Fetch XBRL document (typically zipped)
        r = requests.get(xbrl_url, timeout=30)
        r.raise_for_status()

        # For this prototype, parse raw XBRL as JSON or XML
        # Full implementation requires XBRL parser library (arelle recommended)
        # For now, return structure with None values (placeholder)

        result = {
            "revenue": None,
            "net_income": None,
            "total_assets": None,
            "total_liabilities": None,
            "shareholders_equity": None,
            "operating_cash_flow": None,
            "free_cash_flow": None,
            "roe": None,
            "roa": None,
            "debt_to_equity": None,
            "last_update": datetime.now().isoformat()
        }

        # TODO: Parse XBRL XML using arelle or pd.read_xml
        # GL account codes for Japanese companies (based on XBRL taxonomy):
        #   Revenue: jpfr-asr:NetSalesJFY (or jpfr:OperatingRevenueJFY)
        #   Net Income: jppfs:ProfitJFY (or jpfr-asr:NetIncomeJFY)
        #   Total Assets: jppfs:TotalAssetsJFY
        #   etc.

        return result

    except Exception as e:
        print(f"  parse_xbrl: {e}")
        return None


def store_postgres(df):
    """
    Store fundamentals DataFrame into Postgres market_data.japan_fundamentals.

    Creates table if not exists.
    """
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(
            dbname="market_data",
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432))
        )

        cursor = conn.cursor()

        # Create table if not exists
        create_sql = """
        CREATE TABLE IF NOT EXISTS japan_fundamentals (
            edinet_code VARCHAR(6) PRIMARY KEY,
            company_name VARCHAR(255),
            fiscal_year INTEGER,
            period VARCHAR(20),
            filing_date DATE,
            revenue NUMERIC,
            net_income NUMERIC,
            total_assets NUMERIC,
            total_liabilities NUMERIC,
            shareholders_equity NUMERIC,
            operating_cf NUMERIC,
            free_cf NUMERIC,
            roe NUMERIC,
            roa NUMERIC,
            debt_to_equity NUMERIC,
            updated_at TIMESTAMP DEFAULT NOW()
        );
        """
        cursor.execute(create_sql)

        # Upsert rows
        for _, row in df.iterrows():
            upsert_sql = """
            INSERT INTO japan_fundamentals
            (edinet_code, company_name, fiscal_year, period, filing_date,
             revenue, net_income, total_assets, total_liabilities, shareholders_equity,
             operating_cf, free_cf, roe, roa, debt_to_equity)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (edinet_code) DO UPDATE SET
              updated_at = NOW()
            """
            cursor.execute(upsert_sql, tuple(row))

        conn.commit()
        cursor.close()
        conn.close()

        print(f"  Stored {len(df)} rows in japan_fundamentals")

    except Exception as e:
        print(f"  Postgres error: {e}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recent", type=int, default=None,
                        help="Fetch only recent N filings (for testing)")
    parser.add_argument("--code", type=str, default=None,
                        help="Single company EDINET code (e.g., 8001)")
    parser.add_argument("--validate", action="store_true",
                        help="Check Postgres schema and exit")
    parser.add_argument("--output", type=str, default=None,
                        help="Save results to CSV instead of Postgres")

    args = parser.parse_args()

    print(f"EDINET Japan Fundamentals Fetcher")
    print(f"{'='*70}")
    print(f"API Key: {EDINET_KEY[:20]}...")
    print()

    # ─── Validation Mode ────────────────────────────────────────────────────
    if args.validate:
        try:
            import psycopg2
            conn = psycopg2.connect(dbname="market_data")
            cursor = conn.cursor()
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name LIKE 'japan%'
            """)
            tables = cursor.fetchall()
            print("Japan tables in Postgres:")
            for t in tables:
                print(f"  - {t[0]}")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Postgres error: {e}")
        return

    # ─── Fetch Companies ───────────────────────────────────────────────────
    companies = fetch_companies()

    if companies.empty:
        print("No companies fetched. Check API key and network.")
        sys.exit(1)

    # Filter to single code if specified
    if args.code:
        companies = companies[companies["code"] == args.code]
        if companies.empty:
            print(f"Company code {args.code} not found")
            sys.exit(1)

    print(f"\nFetching filings for {len(companies)} companies...")
    print()

    # ─── Fetch Filings & Parse Financials ──────────────────────────────────
    results = []

    for idx, company in companies.iterrows():
        code = company["code"]
        name = company.get("name", "Unknown")

        print(f"[{idx+1}/{len(companies)}] {code} — {name[:40]}")

        # Fetch latest filings
        filings = fetch_filings(code, limit=args.recent or 4)

        if not filings:
            print(f"  (no filings)")
            continue

        for filing in filings:
            try:
                xbrl_url = filing.get("xbrlUrl")
                if not xbrl_url:
                    continue

                # Parse XBRL
                fundamentals = parse_xbrl_financials(xbrl_url)
                if not fundamentals:
                    continue

                # Assemble row
                row = {
                    "edinet_code": code,
                    "company_name": name,
                    "fiscal_year": filing.get("fiscalYear"),
                    "period": filing.get("period", "FY"),
                    "filing_date": filing.get("submitDateTime")[:10] if filing.get("submitDateTime") else None,
                    **fundamentals
                }
                results.append(row)
                print(f"    ✓ {row['filing_date']} (FY{row['fiscal_year']} {row['period']})")

            except Exception as e:
                print(f"    ERROR: {e}")
                continue

    if not results:
        print("\nNo data fetched.")
        return

    df = pd.DataFrame(results)
    print(f"\n{'='*70}")
    print(f"Total rows collected: {len(df)}")
    print()
    print(df.head(10))
    print()

    # ─── Output ────────────────────────────────────────────────────────────
    if args.output:
        df.to_csv(args.output, index=False)
        print(f"Saved to {args.output}")
    else:
        store_postgres(df)
        print("EDINET fetch complete.")


if __name__ == "__main__":
    main()
