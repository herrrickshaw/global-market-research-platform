#!/usr/bin/env python3
"""
Fetch all Korea companies from DART API and build symbol → corp_code mapping
DART provides company list with both stock_code and corp_code
"""

import os
import requests
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
log = logging.getLogger(__name__)

DART_KEY = os.getenv('DART_KEY', '')

def fetch_all_companies(output_file='korea_dart_mapping.json'):
    """Fetch all Korea companies from DART and build mapping"""

    mapping = {}
    page_no = 1
    batch_size = 100
    total_fetched = 0

    log.info("Fetching Korea companies from DART...")
    log.info("")

    while True:
        try:
            url = "https://opendart.fss.or.kr/api/companys.json"  # Note: plural
            params = {
                'crtfc_key': DART_KEY,
                'pageNo': str(page_no),
                'pageSize': str(batch_size)
            }

            resp = requests.get(url, params=params, timeout=15)

            if resp.status_code != 200:
                log.error(f"HTTP {resp.status_code}: {resp.text[:200]}")
                break

            data = resp.json()

            # Check status
            if data.get('status') != '000':
                log.warning(f"API error: {data.get('message', 'Unknown')}")
                break

            companies = data.get('list', [])
            if not companies:
                log.info(f"No more companies (reached end at page {page_no})")
                break

            # Extract mapping
            for company in companies:
                stock_code = company.get('stock_code')
                corp_code = company.get('corp_code')

                if stock_code and corp_code:
                    mapping[stock_code] = corp_code

            total_fetched += len(companies)
            log.info(f"  Page {page_no}: {len(companies)} companies | Total: {total_fetched}")

            # Check if there are more pages
            total_count = data.get('total_count', 0)
            if total_fetched >= total_count:
                log.info(f"Reached total count: {total_fetched}/{total_count}")
                break

            page_no += 1

        except Exception as e:
            log.error(f"Error fetching page {page_no}: {e}")
            break

    # Save mapping
    if mapping:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

        log.info("")
        log.info(f"✅ Mapping saved to {output_file}")
        log.info(f"Total mappings: {len(mapping)}")

        # Show sample
        sample_codes = list(mapping.items())[:5]
        log.info("")
        log.info("Sample mappings:")
        for stock_code, corp_code in sample_codes:
            log.info(f"  {stock_code} → {corp_code}")

    return mapping

if __name__ == '__main__':
    if not DART_KEY:
        log.error("DART_KEY not found in environment")
        exit(1)

    log.info("""
╔════════════════════════════════════════════════════════════════╗
║       DART KOREA COMPANY LIST FETCHER                          ║
║       Builds symbol → corp_code mapping for batch collection   ║
╚════════════════════════════════════════════════════════════════╝
""")

    mapping = fetch_all_companies()

    log.info("")
    log.info("Next step: Use mapping with dart_fundamentals_collector.py")
    log.info("  python3 dart_fundamentals_collector.py --mapping korea_dart_mapping.json")
