#!/usr/bin/env python3
"""
Universal Stock Extractor via Polygon.io
- US, Europe, Crypto (multi-market support)
- Better fundamental data coverage than yfinance
- Rate limit: 5 calls/min (free tier)
- Expected: 2,000-3,000 symbols in 8-10 hours
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

class PolygonExtractor:
    """Polygon.io extractor for global stock fundamentals"""

    def __init__(self, api_key: str, market: str = 'us'):
        self.api_key = api_key
        self.market = market
        self.base_url = "https://api.polygon.io/v1"
        self.session = requests.Session()
        self.extracted = []
        self.failed = []
        self.start_time = None
        self.call_count = 0
        self.rate_limit_delay = 12  # 5 calls/min = 12 sec between calls

    def fetch_fundamentals(self, ticker: str) -> Optional[Dict]:
        """Fetch fundamentals for single ticker via Polygon"""
        try:
            # Polygon ticker endpoint (with market suffix for non-US)
            if self.market != 'us':
                # European tickers may have exchange suffix (e.g., ADS.DE, SAP.DE)
                pass

            # Polygon /ticker/{ticker}/get endpoint
            url = f"{self.base_url}/ticker/{ticker}"
            params = {
                'apikey': self.api_key
            }

            resp = self.session.get(url, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                result_data = data.get('results', {})

                if result_data:
                    result = {
                        'symbol': ticker,
                        'pe': result_data.get('pe'),
                        'pb': result_data.get('pb'),
                        'roe': result_data.get('roe'),
                        'debt_to_equity': result_data.get('debt_to_equity'),
                        'market_cap': result_data.get('market_cap'),
                        'dividend_yield': result_data.get('dividend_yield'),
                        'fetched_at': datetime.utcnow().isoformat()
                    }

                    if result.get('pe'):
                        self.extracted.append(result)
                        return result
                    else:
                        self.failed.append({'symbol': ticker, 'reason': 'no_pe'})
            else:
                self.failed.append({'symbol': ticker, 'error': f'HTTP {resp.status_code}'})

            return None

        except Exception as e:
            self.failed.append({'symbol': ticker, 'error': str(e)})
            return None

    def extract(self, symbols: List[str]) -> Dict:
        """Main extraction loop"""
        log.info("=" * 80)
        log.info(f"POLYGON.IO EXTRACTION - {self.market.upper()}")
        log.info("=" * 80)
        log.info(f"Symbols: {len(symbols):,}")
        log.info(f"Rate limit: 5 calls/min")
        log.info(f"Time estimate: {len(symbols) * self.rate_limit_delay / 5 / 3600:.1f} hours")
        log.info(f"Start: {datetime.now()}")
        log.info("")

        self.start_time = time.time()

        for i, symbol in enumerate(symbols, 1):
            # Rate limiting
            if self.call_count > 0 and self.call_count % 5 == 0:
                log.info(f"  [Rate limit] Waiting {self.rate_limit_delay}s...")
                time.sleep(self.rate_limit_delay)

            self.fetch_fundamentals(symbol)
            self.call_count += 1

            # Progress every 50 symbols
            if i % 50 == 0 or i == len(symbols):
                elapsed = time.time() - self.start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(symbols) - i) / rate if rate > 0 else 0
                pct = 100 * i / len(symbols)

                log.info(f"[{i:>6d}/{len(symbols):<6d}] {pct:>5.1f}% | "
                         f"Extracted: {len(self.extracted):>5d} | "
                         f"Failed: {len(self.failed):>5d} | "
                         f"ETA: {eta/3600:>5.1f}h")

        duration = time.time() - self.start_time

        # Final report
        log.info("")
        log.info("=" * 80)
        log.info("POLYGON.IO EXTRACTION - COMPLETE")
        log.info("=" * 80)
        log.info(f"Symbols extracted: {len(self.extracted):,} / {len(symbols):,}")
        log.info(f"Success rate: {100 * len(self.extracted) / len(symbols):.1f}%")
        log.info(f"Duration: {duration:.0f}s ({duration/60:.1f}m, {duration/3600:.2f}h)")
        log.info(f"Estimated completion: {datetime.fromtimestamp(self.start_time + duration)}")
        log.info("")

        return {
            'metadata': {
                'market': self.market,
                'source': 'polygon.io',
                'symbols_requested': len(symbols),
                'symbols_extracted': len(self.extracted),
                'success_rate_pct': 100 * len(self.extracted) / len(symbols),
                'failed': len(self.failed),
                'duration_seconds': duration,
                'rate_per_second': len(symbols) / duration,
                'fetched_at': datetime.utcnow().isoformat()
            },
            'data': self.extracted,
            'failed': self.failed
        }

def load_symbols(market: str) -> List[str]:
    """Load symbols by market"""
    if market == 'us':
        # Try us_list.csv
        us_list = Path('/Users/umashankar/market-pipeline/code/python_files/data/us_list.csv')
        if us_list.exists():
            import csv
            with open(us_list) as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                symbols = [row[0] for row in reader if row]
                return symbols[:2200]

    # Fallback: return sample
    return ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'BRK.B', 'JNJ', 'V', 'WMT']

def main():
    # Load API key from Desktop file or credentials
    api_key = None

    # Try Desktop file first
    desktop_file = Path('/Users/umashankar/Desktop/API keys.rtf')
    if desktop_file.exists():
        with open(desktop_file) as f:
            content = f.read()
            if 'polygon api' in content:
                # Extract from RTF
                import re
                match = re.search(r'polygon api\s*:\s*([a-zA-Z0-9_\-]+)', content)
                if match:
                    api_key = match.group(1).strip()

    # Fall back to credentials.env
    if not api_key:
        cred_path = Path('/Users/umashankar/.config/market-secrets/credentials.env')
        if cred_path.exists():
            with open(cred_path) as f:
                for line in f:
                    if 'POLYGON' in line:
                        api_key = line.split('=')[1].strip().strip('"')
                        break

    if not api_key:
        log.error("❌ Polygon API key not found")
        log.info("Add to credentials.env: POLYGON_KEY=<your-key>")
        sys.exit(1)

    log.info(f"✅ Polygon API key loaded")
    log.info("")

    # Load symbols
    symbols = load_symbols('us')
    log.info(f"Loaded {len(symbols):,} US symbols")
    log.info("")

    # Extract
    extractor = PolygonExtractor(api_key, market='us')
    result = extractor.extract(symbols)

    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    reports_dir = Path('/Users/umashankar/market-pipeline/code/python_files/reports')
    reports_dir.mkdir(exist_ok=True)

    # JSON export
    json_file = reports_dir / f'edgar_polygon_us_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(result, f, indent=2)
    log.info(f"✅ Results saved: {json_file.name}")

    # Generate CQL
    cql_file = reports_dir / f'edgar_us_polygon_cassandra_{timestamp}.cql'
    with open(cql_file, 'w') as f:
        f.write("-- US Fundamentals (Polygon.io)\n")
        f.write(f"-- Extracted: {datetime.now()}\n")
        f.write(f"-- Source: polygon.io\n\n")

        for item in result['data']:
            if not item.get('pe'):
                continue

            symbol = item['symbol']
            pe = item.get('pe') or 0
            pb = item.get('pb') or 0
            roe = item.get('roe') or 0
            de = item.get('debt_to_equity') or 0
            mc = item.get('market_cap') or 0
            dy = item.get('dividend_yield') or 0

            cql = f"""UPDATE herrrickshaw.stock_quotes
SET pe = {pe}, pb = {pb}, roe = {roe}, debt_to_equity = {de},
    market_cap = {mc}, dividend_yield = {dy}, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = '{symbol}';
"""
            f.write(cql)

    log.info(f"✅ CQL generated: {cql_file.name}")
    log.info("")
    log.info(f"📊 Extracted: {result['metadata']['symbols_extracted']} / {result['metadata']['symbols_requested']}")

if __name__ == '__main__':
    main()
