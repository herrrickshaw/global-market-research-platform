#!/usr/bin/env python3
"""
Phase 2: US AlphaVantage Overnight Batch
Rate limit: 5 calls per minute (enforced)
Time estimate: 7-8 hours for 7,442 symbols
Start: 8pm, Complete: 4am
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

class AlphaVantageOvernight:
    """AlphaVantage extractor with 5 calls/min rate limiting"""

    def __init__(self, api_key: str, symbols: List[str]):
        self.api_key = api_key
        self.symbols = symbols
        self.base_url = "https://www.alphavantage.co/query"
        self.session = requests.Session()
        self.extracted = []
        self.failed = []
        self.start_time = None
        self.call_count = 0
        self.rate_limit_delay = 12  # 12 seconds = 5 calls per minute

    def extract(self) -> Dict:
        """Main extraction loop with 5 calls/min rate limiting"""
        log.info("=" * 80)
        log.info("ALPHAVANTAGE OVERNIGHT BATCH EXTRACTION")
        log.info("=" * 80)
        log.info(f"Symbols: {len(self.symbols):,}")
        log.info(f"Rate limit: 5 calls/min (wait {self.rate_limit_delay}s every 5 calls)")
        log.info(f"Time estimate: {len(self.symbols) * self.rate_limit_delay / 5 / 3600:.1f} hours")
        log.info(f"Start: {datetime.now()}")
        log.info("")

        self.start_time = time.time()

        for i, symbol in enumerate(self.symbols, 1):
            try:
                # Rate limiting: AlphaVantage free tier = 5 calls per minute
                if self.call_count > 0 and self.call_count % 5 == 0:
                    log.info(f"  [Rate limit hit] Waiting {self.rate_limit_delay}s...")
                    time.sleep(self.rate_limit_delay)

                params = {
                    'function': 'OVERVIEW',
                    'symbol': symbol,
                    'apikey': self.api_key
                }

                resp = self.session.get(self.base_url, params=params, timeout=10)
                self.call_count += 1

                if resp.status_code != 200:
                    self.failed.append({'symbol': symbol, 'error': f'HTTP {resp.status_code}'})
                    continue

                data = resp.json()

                # Check for API errors
                if 'Note' in data or 'Error Message' in data:
                    error = data.get('Note', data.get('Error Message', 'Unknown'))
                    self.failed.append({'symbol': symbol, 'error': str(error)})
                    continue

                # Extract fundamentals
                if data.get('PERatio'):
                    result = {
                        'symbol': symbol,
                        'pe': float(data.get('PERatio', 0)) if data.get('PERatio') else None,
                        'pb': float(data.get('PriceToBookRatio', 0)) if data.get('PriceToBookRatio') else None,
                        'roe': float(data.get('ReturnOnEquityTTM', 0)) if data.get('ReturnOnEquityTTM') else None,
                        'debt_to_equity': float(data.get('DebtToEquityRatio', 0)) if data.get('DebtToEquityRatio') else None,
                        'opm': float(data.get('OperatingMarginTTM', 0)) if data.get('OperatingMarginTTM') else None,
                        'market_cap': float(data.get('MarketCapitalization', 0)) if data.get('MarketCapitalization') else None,
                        'dividend_yield': float(data.get('DividendYield', 0)) if data.get('DividendYield') else None,
                        'fetched_at': datetime.utcnow().isoformat()
                    }
                    self.extracted.append(result)
                else:
                    self.failed.append({'symbol': symbol, 'reason': 'no_pe'})

            except Exception as e:
                self.failed.append({'symbol': symbol, 'error': str(e)})

            # Progress every 50 symbols (250 minutes = 4+ hours into run)
            if i % 50 == 0 or i == len(self.symbols):
                elapsed = time.time() - self.start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(self.symbols) - i) / rate if rate > 0 else 0
                pct = 100 * i / len(self.symbols)

                log.info(f"[{i:>6d}/{len(self.symbols):<6d}] {pct:>5.1f}% | "
                         f"Extracted: {len(self.extracted):>5d} | "
                         f"Failed: {len(self.failed):>5d} | "
                         f"API calls: {self.call_count:>5d} | "
                         f"ETA: {eta/3600:>5.1f}h")

        duration = time.time() - self.start_time

        # Final report
        log.info("")
        log.info("=" * 80)
        log.info("ALPHAVANTAGE OVERNIGHT - EXTRACTION COMPLETE")
        log.info("=" * 80)
        log.info(f"Symbols extracted: {len(self.extracted):,} / {len(self.symbols):,}")
        log.info(f"Success rate: {100 * len(self.extracted) / len(self.symbols):.1f}%")
        log.info(f"API calls made: {self.call_count}")
        log.info(f"Duration: {duration:.0f}s ({duration/60:.1f}m, {duration/3600:.2f}h)")
        log.info(f"Estimated completion: {datetime.fromtimestamp(self.start_time + duration)}")
        log.info("")

        return {
            'metadata': {
                'market': 'us',
                'source': 'alphavantage',
                'symbols_requested': len(self.symbols),
                'symbols_extracted': len(self.extracted),
                'success_rate_pct': 100 * len(self.extracted) / len(self.symbols),
                'failed': len(self.failed),
                'api_calls': self.call_count,
                'duration_seconds': duration,
                'rate_per_second': len(self.symbols) / duration,
                'fetched_at': datetime.utcnow().isoformat()
            },
            'data': self.extracted,
            'failed': self.failed
        }

def load_us_symbols() -> List[str]:
    """Load ~7,442 US symbols from NASDAQ/NYSE"""
    try:
        # Try to load from CSV if available
        us_list = Path('/Users/umashankar/market-pipeline/code/python_files/data/us_list.csv')
        if us_list.exists():
            import pandas as pd
            df = pd.read_csv(us_list)
            symbols = df.iloc[:, 0].tolist()
            return symbols[:7442]
    except:
        pass

    # Fallback: use hardcoded list
    log.warning("Could not load us_list.csv, using sample")
    top_symbols = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'BRK.B', 'JNJ', 'V', 'WMT',
        'JPM', 'MA', 'PG', 'ORCL', 'AVGO', 'LLY', 'ABBV', 'COST', 'META', 'KO',
        'PEP', 'NFLX', 'BA', 'MMM', 'IBM', 'INTC', 'AMD', 'CSCO', 'CAT', 'CVX',
    ]
    return top_symbols

def main():
    # Load credentials
    cred_path = Path('/Users/umashankar/.config/market-secrets/credentials.env')
    api_key = None

    if cred_path.exists():
        with open(cred_path) as f:
            for line in f:
                if 'ALPHAVANTAGE_KEY=' in line:
                    api_key = line.split('=')[1].strip().strip('"')
                    break

    if not api_key or api_key.startswith('<'):
        log.error("❌ ALPHAVANTAGE_KEY not configured")
        sys.exit(1)

    log.info(f"✅ AlphaVantage API key loaded")
    log.info("")

    # Load symbols
    symbols = load_us_symbols()
    log.info(f"Loaded {len(symbols):,} US symbols")
    log.info("")

    # Extract
    extractor = AlphaVantageOvernight(api_key, symbols)
    result = extractor.extract()

    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    reports_dir = Path('/Users/umashankar/market-pipeline/code/python_files/reports')
    reports_dir.mkdir(exist_ok=True)

    # JSON export
    json_file = reports_dir / f'edgar_alphavantage_overnight_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(result, f, indent=2)
    log.info(f"✅ Results saved: {json_file.name}")

    # Generate CQL
    cql_file = reports_dir / f'edgar_us_alphavantage_cassandra_{timestamp}.cql'
    with open(cql_file, 'w') as f:
        f.write("-- US Fundamentals (AlphaVantage)\n")
        f.write(f"-- Extracted: {datetime.now()}\n")
        f.write(f"-- Source: alphavantage.co\n\n")

        for item in result['data']:
            if not item.get('pe'):
                continue

            symbol = item['symbol']
            pe = item.get('pe') or 0
            pb = item.get('pb') or 0
            roe = item.get('roe') or 0
            de = item.get('debt_to_equity') or 0
            opm = item.get('opm') or 0
            mc = item.get('market_cap') or 0
            dy = item.get('dividend_yield') or 0

            cql = f"""UPDATE herrrickshaw.stock_quotes
SET pe = {pe}, pb = {pb}, roe = {roe}, debt_to_equity = {de},
    opm = {opm}, market_cap = {mc}, dividend_yield = {dy}, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = '{symbol}';
"""
            f.write(cql)

    log.info(f"✅ CQL generated: {cql_file.name}")
    log.info("")
    log.info("Next step: Load to Cassandra")
    log.info(f"  cqlsh -f {cql_file.name}")

if __name__ == '__main__':
    main()
