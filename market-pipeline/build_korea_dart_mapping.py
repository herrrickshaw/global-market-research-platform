#!/usr/bin/env python3
"""
Build Korea symbol → DART corp code mapping
Source: Query Cassandra for all Korea symbols, then map each to DART corp code
"""

import os
import json
import requests
import subprocess
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DART_KEY = os.getenv('DART_KEY', '')

def get_korea_symbols_from_cassandra():
    """Query Cassandra for all Korea symbols"""
    log.info("Querying Cassandra for Korea symbols...")
    try:
        cql = "SELECT yf_ticker FROM herrrickshaw.stock_quotes WHERE market = 'korea';"
        result = subprocess.run(['cqlsh', 'localhost', '-e', cql],
                               capture_output=True, text=True, timeout=60)

        symbols = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and not any(x in line for x in ['yf_ticker', '---', '(', 'rows', 'Aborted']):
                # Remove suffix if present (.KS, .KQ)
                bare_symbol = line.split('.')[0] if '.' in line else line
                if bare_symbol.isdigit() and len(bare_symbol) == 6:
                    symbols.append(bare_symbol)

        log.info(f"✅ Loaded {len(symbols)} Korea symbols from Cassandra")
        return symbols
    except Exception as e:
        log.error(f"Cassandra query failed: {e}")
        return []

def search_dart_code_by_name(company_name):
    """Search DART for corp code by company name"""
    try:
        url = "https://opendart.fss.or.kr/api/company.json"
        params = {
            'crtfc_key': DART_KEY,
            'corp_name': company_name,
            'pageNo': '1'
        }
        resp = requests.get(url, params=params, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            if data.get('status') == '000' and data.get('list'):
                return data['list'][0].get('corp_code')
    except Exception as e:
        log.debug(f"Error searching for {company_name}: {e}")

    return None

def search_dart_code_by_stock_code(stock_code):
    """Search DART using stock code (requires corp_code as fallback)"""
    # DART requires corp_code, not stock_code
    # We need to search by name or use a pre-built mapping
    return None

def build_mapping(symbols, output_file='korea_dart_mapping.json'):
    """Build symbol → DART corp code mapping"""
    mapping = {}
    failed = []

    for i, symbol in enumerate(symbols):
        if (i + 1) % 100 == 0:
            log.info(f"  Progress: {i+1}/{len(symbols)}")

        # Try searching by stock code first (if we have a way)
        dart_code = search_dart_code_by_stock_code(symbol)

        # Fallback: we'd need to search by company name, but we don't have names
        # For now, mark as unknown
        if not dart_code:
            failed.append(symbol)
            continue

        mapping[symbol] = dart_code

    # Save mapping
    with open(output_file, 'w') as f:
        json.dump(mapping, f, indent=2)

    log.info(f"✅ Mapping complete:")
    log.info(f"  Mapped: {len(mapping)}")
    log.info(f"  Failed: {len(failed)}")
    log.info(f"  Saved to: {output_file}")

    return mapping, failed

def print_summary():
    """Print summary of what we learned"""
    log.info("")
    log.info("╔════════════════════════════════════════════════════════════╗")
    log.info("║  KOREA SYMBOL → DART MAPPING SUMMARY                       ║")
    log.info("╚════════════════════════════════════════════════════════════╝")
    log.info("")
    log.info("⚠️  Challenge: DART API requires corp_code (8-digit DART ID)")
    log.info("    but we only have stock_code (6-digit KRX ticker)")
    log.info("")
    log.info("Solution options:")
    log.info("  1. Build mapping table from DART's company list")
    log.info("  2. Search by company name (need to fetch from KRX)")
    log.info("  3. Use pre-built mapping from trading platform")
    log.info("")
    log.info("For Phase 1 POC: Using hardcoded major symbols mapping")
    log.info("For production: Auto-fetch mapping from DART open data")

if __name__ == '__main__':
    if not DART_KEY:
        log.error("DART_KEY not found")
        exit(1)

    symbols = get_korea_symbols_from_cassandra()

    if symbols:
        mapping, failed = build_mapping(symbols)
    else:
        log.warning("No symbols loaded; showing mapping strategy instead")
        print_summary()
