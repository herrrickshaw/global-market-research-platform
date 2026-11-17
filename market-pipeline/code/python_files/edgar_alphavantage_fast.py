#!/usr/bin/env python3
"""
EDGAR Fundamentals via AlphaVantage + Cassandra Direct Load
- Uses AlphaVantage fundamentals API
- Batch processing with proper rate limiting
- Direct CQL generation for Cassandra loading
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

class AlphaVantageExtractor:
    """AlphaVantage fundamentals extractor"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.session = requests.Session()
        self.extracted = []
        self.failed = []
        self.start_time = None
        self.call_count = 0
        self.rate_limit = 5  # 5 calls per minute

    def fetch_fundamentals(self, symbol: str) -> Optional[Dict]:
        """Fetch fundamentals using AlphaVantage OVERVIEW endpoint"""
        try:
            # Rate limiting: AlphaVantage free tier = 5 calls/min
            if self.call_count > 0 and self.call_count % 5 == 0:
                time.sleep(12)  # Wait 12 seconds after every 5 calls

            params = {
                'function': 'OVERVIEW',
                'symbol': symbol,
                'apikey': self.api_key
            }

            resp = self.session.get(self.base_url, params=params, timeout=10)
            resp.raise_for_status()
            self.call_count += 1

            data = resp.json()

            # Check for valid response
            if 'Note' in data or 'Error Message' in data:
                error = data.get('Note', data.get('Error Message', 'Unknown error'))
                self.failed.append({'symbol': symbol, 'error': error})
                return None

            # Extract available fundamentals
            result = {
                'symbol': symbol,
                'pe': self._float_or_none(data.get('PERatio')),
                'pb': self._float_or_none(data.get('PriceToBookRatio')),
                'roe': self._float_or_none(data.get('ReturnOnEquityTTM')),
                'debt_to_equity': self._float_or_none(data.get('DebtToEquityRatio')),
                'opm': self._float_or_none(data.get('OperatingMarginTTM')),
                'market_cap': self._float_or_none(data.get('MarketCapitalization')),
                'dividend_yield': self._float_or_none(data.get('DividendYield')),
                'fetched_at': datetime.utcnow().isoformat()
            }

            if result.get('pe'):  # Only count if PE available
                self.extracted.append(result)
                return result

            return None

        except Exception as e:
            self.failed.append({'symbol': symbol, 'error': str(e)})
            return None

    @staticmethod
    def _float_or_none(val):
        """Convert to float or return None"""
        if val is None or val == 'None':
            return None
        try:
            return float(val)
        except:
            return None

    def extract(self, symbols: List[str]) -> Dict:
        """Main extraction routine"""
        log.info("=" * 80)
        log.info("ALPHAVANTAGE FUNDAMENTALS EXTRACTION")
        log.info("=" * 80)
        log.info(f"Symbols requested: {len(symbols)}")
        log.info("Rate limit: 5 calls/min (need to run overnight or use Tier-A)")
        log.info("")

        self.start_time = time.time()

        for i, symbol in enumerate(symbols, 1):
            self.fetch_fundamentals(symbol)

            if i % 5 == 0:
                elapsed = time.time() - self.start_time
                log.info(f"[{i}/{len(symbols)}] Success: {len(self.extracted)} | Rate: {self.call_count/elapsed:.1f} calls/sec")

        duration = time.time() - self.start_time

        # Report
        log.info("")
        log.info("=" * 80)
        log.info("ALPHAVANTAGE EXTRACTION - REPORT")
        log.info("=" * 80)
        log.info(f"Symbols processed:      {len(symbols)}")
        log.info(f"Successfully extracted: {len(self.extracted)} ({100*len(self.extracted)/len(symbols):.1f}%)")
        log.info(f"Failed/Rate-limited:    {len(self.failed)}")
        log.info(f"Duration:               {duration:.1f} seconds")
        log.info("")
        log.info("⚠️  NOTE: Free tier limited to 5 calls/min. For 2,200 symbols, need ~7 hours.")
        log.info("    Use AWS EC2 + multiple API keys for faster extraction.")
        log.info("")

        return {
            'metadata': {
                'symbols_requested': len(symbols),
                'symbols_extracted': len(self.extracted),
                'success_rate_pct': 100*len(self.extracted)/len(symbols) if symbols else 0,
                'failed': len(self.failed),
                'duration_seconds': duration,
                'api': 'alphavantage'
            },
            'data': self.extracted,
            'failed': self.failed
        }

def load_top_us_symbols() -> List[str]:
    """Load top 200 US symbols (demo mode for rate-limited API)"""
    # Top 200 liquid US stocks
    return [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'BRK.B', 'JNJ', 'V', 'WMT',
        'JPM', 'MA', 'PG', 'ORCL', 'AVGO', 'LLY', 'ABBV', 'COST', 'META', 'KO',
        'PEP', 'NFLX', 'BA', 'MMM', 'IBM', 'INTC', 'AMD', 'CSCO', 'CAT', 'CVX',
        'XOM', 'PM', 'TMO', 'HON', 'ADBE', 'QCOM', 'CRM', 'NOW', 'SNOW', 'AZO',
        'INTU', 'VRTX', 'MU', 'TXN', 'PAYX', 'ENPH', 'ROP', 'WDAY', 'DIS', 'UBER',
        'GE', 'CNBC', 'CMCSA', 'NEE', 'ED', 'SO', 'DUK', 'EXC', 'TSM', 'ASML',
        'SAP', 'NOVO', 'BABA', 'JD', 'BILI', 'SPOT', 'ROKU', 'PINS', 'SNAP', 'TTD',
        'TWTR', 'WORK', 'OKTA', 'ZM', 'CRWD', 'NET', 'PALO', 'ZSCALER', 'ESTC', 'FSLY',
        'DDOG', 'UPWK', 'ETSY', 'ZI', 'MNDY', 'LEMON', 'NEWR', 'PRPL', 'UPST', 'RBLX',
        'PTON', 'DASH', 'LYFT', 'RIDE', 'VIE', 'COIN', 'AFRM', 'MSTR', 'SQ', 'PYPL',
        'SHOP', 'GDDY', 'CHWY', 'ABNB', 'DOOR', 'GRUB', 'GLUE', 'YELP', 'ANGI', 'RSVT',
        'TRIP', 'EXPE', 'BKNG', 'JETS', 'CCL', 'RCL', 'NCLH', 'UAL', 'ALK', 'DAL',
        'AAL', 'LUV', 'ALGT', 'JBLU', 'MGM', 'WYNN', 'VICI', 'PENN', 'DKNG', 'GENI',
        'FLYT', 'PLYA', 'PEB', 'KKR', 'APO', 'BX', 'PSP', 'CASY', 'VSCO', 'SCPL',
        'COHR', 'LCID', 'NIO', 'XPev', 'RIVN', 'BLDR', 'LEN', 'DHI', 'TOL', 'PVT',
        'RYL', 'PHM', 'NVR', 'HOV', 'MTH', 'LGIH', 'MHO', 'LGF', 'KMX', 'ORI',
        'LAUR', 'WTFC', 'VOYA', 'PRU', 'LEG', 'TPH', 'NYT', 'NWSA', 'FOX', 'FOX',
        'TKO', 'CMPR', 'PLC', 'AMRX', 'IMTX', 'DEX', 'SJ', 'SAIA', 'FWRD', 'TEX',
        'MLR', 'ROK', 'ETN', 'ITW', 'CARR', 'EEX', 'AIZ', 'RLI', 'XL', 'ODD',
        'MCK', 'CAH', 'JWN', 'RL', 'NKE', 'UA', 'DECK', 'LB', 'KSS', 'DMVK',
    ]

def main():
    # Load API key from credentials.env
    cred_path = Path('/Users/umashankar/.config/market-secrets/credentials.env')
    api_key = None

    if cred_path.exists():
        with open(cred_path) as f:
            for line in f:
                if line.startswith('ALPHAVANTAGE_KEY='):
                    api_key = line.split('=')[1].strip().strip('"')
                    break

    if not api_key or api_key.startswith('<'):
        log.error("❌ ALPHAVANTAGE_KEY not configured")
        sys.exit(1)

    log.info(f"✅ AlphaVantage API key loaded (key=***{api_key[-10:]})")
    log.info("")

    # Load symbols (top 200 for demo, as AlphaVantage free tier = 5 calls/min)
    symbols = load_top_us_symbols()

    # Run extraction
    extractor = AlphaVantageExtractor(api_key)
    results = extractor.extract(symbols)

    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')

    # JSON export
    json_file = Path('/Users/umashankar/market-pipeline/code/python_files/reports') / f'edgar_alphavantage_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    log.info(f"✅ JSON export: {json_file.name}")

    # Generate CQL for Cassandra
    if results['data']:
        cql_file = Path('/Users/umashankar/market-pipeline/code/python_files/reports') / f'edgar_alphavantage_cassandra_{timestamp}.cql'
        with open(cql_file, 'w') as f:
            f.write("-- AlphaVantage Fundamentals\n")
            f.write(f"-- Extracted: {datetime.now()}\n\n")

            for item in results['data']:
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
WHERE market = 'us' AND yf_ticker = '{symbol}';"""

                f.write(cql + "\n\n")

        log.info(f"✅ CQL export: {cql_file.name}")

    log.info("")
    log.info(f"📊 Extracted: {results['metadata']['symbols_extracted']} / {results['metadata']['symbols_requested']}")

if __name__ == '__main__':
    main()
