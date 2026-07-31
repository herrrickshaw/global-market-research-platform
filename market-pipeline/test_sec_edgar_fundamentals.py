#!/usr/bin/env python3
"""
Test SEC EDGAR API for US fundamentals collection
SEC EDGAR: US public company filings (10-K/10-Q), free & unlimited
"""

import requests
import json
from datetime import datetime

def test_sec_edgar():
    """Test SEC EDGAR capabilities for our 20-column schema"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  SEC EDGAR API FUNDAMENTALS TEST (US)                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")

    # SEC EDGAR endpoints
    tickers = ['AAPL', 'MSFT', 'JPM', 'JNJ']  # Sample test symbols

    # Step 1: Get CIK (Central Index Key) from ticker
    print("STEP 1: Map tickers to CIK (SEC identifier)...")
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        resp = requests.get(url, timeout=15)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            ticker_map = resp.json()
            print(f"  ✅ Company ticker list retrieved ({len(ticker_map)} entries)")

            # Show sample mapping
            for ticker in tickers[:2]:
                for entry in ticker_map.values():
                    if entry.get('ticker') == ticker:
                        print(f"    {ticker}: CIK {entry.get('cik_str'):>10} ({entry.get('title')})")
                        break
        else:
            print(f"  ❌ Error: {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("STEP 2: Fetch recent 10-Q filing for sample company (AAPL)...")
    try:
        # AAPL CIK: 320193
        cik = "0000320193"
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = requests.get(url, timeout=15)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ AAPL filings retrieved")

            # Get recent filings
            if 'filings' in data and 'recent' in data['filings']:
                recent = data['filings']['recent']
                print(f"  Recent filings count: {len(recent.get('accessionNumber', []))}")

                # Show latest 10-Q
                for i, form_type in enumerate(recent.get('form', [])):
                    if form_type == '10-Q':
                        accession = recent['accessionNumber'][i]
                        date = recent['filingDate'][i]
                        print(f"    Latest 10-Q: {date} (accession: {accession})")
                        break
        else:
            print(f"  ❌ Error: {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("STEP 3: Fetch XBRL financial data from latest 10-Q...")
    try:
        # Use pre-built XBRL instance document (10-Q for AAPL, recent)
        # Format: https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&accession_number={accession}&xbrl_type=v

        # Simpler approach: Use sec-edgar-downloader to parse
        print("  (Attempting XBRL retrieval — requires sec-edgar-downloader library)")

        try:
            from sec_edgar_downloader import Downloader
            print("  ✅ sec-edgar-downloader available")
            print("  → Can download & parse 10-K/10-Q XBRL documents")
            print("  → Fundamentals extractable: PE, ROE, margins, debt ratios, cash flow")
        except ImportError:
            print("  ⚠️ sec-edgar-downloader not installed")
            print("  → Install: pip install sec-edgar-downloader")
            print("  → Alternative: sec-api.io offers parsed XBRL data (free tier: 50 requests/month)")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("STEP 4: SEC FACTS API (experimental — may have fundamentals)...")
    try:
        cik = "0000320193"  # AAPL
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        resp = requests.get(url, timeout=15)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Company facts retrieved (XBRL taxonomy data)")

            # Explore available metrics
            if 'facts' in data and 'us-gaap' in data['facts']:
                gaap = data['facts']['us-gaap']
                gaap_keys = list(gaap.keys())[:10]
                print(f"  Available GAAP facts (sample): {gaap_keys}")

                # Check for PE, ROE-related fields
                target_fields = ['EarningsPerShareBasic', 'NetIncomeLoss', 'Assets', 'StockholdersEquity',
                                'Revenues', 'OperatingExpenses', 'NetCashProvidedByOperatingActivities']

                found = []
                for field in target_fields:
                    if field in gaap:
                        found.append(field)

                if found:
                    print(f"  ✅ Found fundamental fields: {found}")

                    # Show sample data for first found field
                    sample_field = found[0]
                    sample_data = gaap[sample_field]['units'].get('USD', [])
                    if sample_data:
                        latest = sample_data[-1]
                        print(f"  Sample ({sample_field}): {json.dumps(latest, indent=4)[:400]}...")
        else:
            print(f"  ❌ Error: {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  CONCLUSION                                                ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")
    print("SEC EDGAR Capabilities:")
    print("  ✅ Free & unlimited API access")
    print("  ✅ CIK mapping from tickers (via company_tickers.json)")
    print("  ✅ Filings metadata + accession numbers (via submissions JSON)")
    print("  ✅ XBRL company facts API (raw financial data)")
    print("")
    print("Recommended approach:")
    print("  1. Use sec-edgar-downloader to download 10-Q XBRL instances")
    print("  2. Parse XBRL XML to extract PE, ROE, margins, debt ratios")
    print("  3. Map to our 20-column canonical schema")
    print("")
    print("Alternative (faster, less accurate):")
    print("  1. Use sec-api.io (50 free requests/month) for parsed XBRL")
    print("  2. Or use existing yfinance + SEC facts API hybrid")

if __name__ == '__main__':
    test_sec_edgar()
