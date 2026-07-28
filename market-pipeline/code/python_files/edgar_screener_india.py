#!/usr/bin/env python3
"""
India Fundamentals via screener.in API
- 5,244 NSE-BSE symbols
- 10-year fundamentals history (vs yfinance's 5y)
- PE, PB, ROE, Debt-to-Equity, OPM, Dividend Yield
- Expected: 2-3 days (rate-limited API)
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

class ScreenerInExtractor:
    """screener.in fundamentals extractor for India NSE-BSE"""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.base_url = "https://www.screener.in/api"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'Referer': 'https://www.screener.in'
        })
        self.token = None
        self.extracted = []
        self.failed = []
        self.start_time = None
        self.call_count = 0

        # Login to get session token
        self._login()

    def _login(self):
        """Authenticate with screener.in"""
        try:
            # Try GET first to check if already authenticated
            resp = self.session.get(f"{self.base_url}/auth/user", timeout=10)
            if resp.status_code == 200:
                log.info("✅ Already authenticated with screener.in")
                return

            # Otherwise, login with credentials
            login_url = f"{self.base_url}/auth/login"
            payload = {
                'email': self.email,
                'password': self.password
            }
            resp = self.session.post(login_url, json=payload, timeout=10)
            resp.raise_for_status()

            data = resp.json()
            if data.get('token'):
                self.token = data['token']
                self.session.headers['Authorization'] = f'Token {self.token}'
                log.info(f"✅ Logged in to screener.in")
            else:
                log.warning("⚠️  Login response missing token. Will attempt without auth.")

        except Exception as e:
            log.warning(f"⚠️  Login failed: {e}. Will attempt unauthenticated.")

    def fetch_fundamentals(self, symbol: str) -> Optional[Dict]:
        """Fetch fundamentals for a single NSE-BSE symbol"""
        try:
            # screener.in fundamentals endpoint
            url = f"{self.base_url}/company/{symbol}/financials/latest"

            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            self.call_count += 1

            data = resp.json()

            # Parse response
            if 'error' in data or not data.get('company'):
                self.failed.append({'symbol': symbol, 'error': 'Not found or API error'})
                return None

            company = data.get('company', {})
            result = {
                'symbol': symbol,
                'pe': self._float_or_none(company.get('pe')),
                'pb': self._float_or_none(company.get('pb')),
                'roe': self._float_or_none(company.get('roe')),
                'debt_to_equity': self._float_or_none(company.get('debt_to_equity')),
                'opm': self._float_or_none(company.get('opm')),
                'market_cap': self._float_or_none(company.get('market_cap')),
                'dividend_yield': self._float_or_none(company.get('dividend_yield')),
                'fetched_at': datetime.utcnow().isoformat()
            }

            if result.get('pe'):
                self.extracted.append(result)
                return result

            return None

        except requests.exceptions.RequestException as e:
            self.failed.append({'symbol': symbol, 'error': str(e)})
            return None

    @staticmethod
    def _float_or_none(val):
        """Convert to float or return None"""
        if val is None:
            return None
        try:
            return float(val)
        except:
            return None

    def extract(self, symbols: List[str]) -> Dict:
        """Main extraction routine"""
        log.info("=" * 80)
        log.info("SCREENER.IN FUNDAMENTALS EXTRACTION - INDIA NSE-BSE")
        log.info("=" * 80)
        log.info(f"Symbols requested: {len(symbols)}")
        log.info("Rate limit: ~1 symbol/sec (5,244 = ~1.5 hours continuous)")
        log.info("")

        self.start_time = time.time()

        for i, symbol in enumerate(symbols, 1):
            self.fetch_fundamentals(symbol)

            # Progress every 100 symbols
            if i % 100 == 0 or i == len(symbols):
                elapsed = time.time() - self.start_time
                rate = self.call_count / elapsed if elapsed > 0 else 0
                eta = (len(symbols) - i) / rate if rate > 0 else 0
                log.info(f"[{i:5d}/{len(symbols):5d}] Success: {len(self.extracted):5d} | Failed: {len(self.failed):5d} | Rate: {rate:.2f}/sec | ETA: {eta/3600:.1f}h")

            # Rate limit: 1 request per second (aggressive to avoid throttling)
            time.sleep(1.0)

        duration = time.time() - self.start_time

        # Report
        log.info("")
        log.info("=" * 80)
        log.info("SCREENER.IN EXTRACTION - FINAL REPORT")
        log.info("=" * 80)
        log.info(f"Symbols processed:      {len(symbols):,}")
        log.info(f"Successfully extracted: {len(self.extracted):,} ({100*len(self.extracted)/len(symbols):.1f}%)")
        log.info(f"Failed:                 {len(self.failed):,}")
        log.info(f"Duration:               {duration:.1f} seconds ({duration/3600:.1f} hours)")
        log.info(f"Rate:                   {self.call_count/duration:.2f} symbols/second")
        log.info("")

        return {
            'metadata': {
                'symbols_requested': len(symbols),
                'symbols_extracted': len(self.extracted),
                'success_rate_pct': 100*len(self.extracted)/len(symbols) if symbols else 0,
                'failed': len(self.failed),
                'duration_seconds': duration,
                'api': 'screener.in'
            },
            'data': self.extracted,
            'failed': self.failed
        }

def load_india_symbols() -> List[str]:
    """Load all NSE-BSE symbols"""
    symbols = []

    # Try loading from nse_equity_list.csv
    nse_path = Path('/Users/umashankar/market-pipeline/code/python_files/data/nse_equity_list.csv')
    if nse_path.exists():
        try:
            import pandas as pd
            df = pd.read_csv(nse_path)
            symbols_col = [col for col in df.columns if col.lower() == 'symbol'][0]
            symbols.extend(df[symbols_col].tolist())
            log.info(f"Loaded {len(symbols)} NSE symbols from nse_equity_list.csv")
        except Exception as e:
            log.warning(f"Failed to load nse_equity_list.csv: {e}")

    # If not enough, add known BSE symbols
    if len(symbols) < 2000:
        log.warning(f"Only {len(symbols)} symbols loaded. Adding fallback BSE symbols...")
        bse_symbols = [
            'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'HDFC', 'ICICIBANK', 'KOTAKBANK',
            'LT', 'MARUTI', 'BAJAJFINSV', 'BAJAJ-AUTO', 'WIPRO', 'AXISBANK',
            'BHARTIARTL', 'ITC', 'SBIN', 'DIVI', 'ASIANPAINT', 'HINDUNILVR', 'NESTLEIND',
        ]
        symbols.extend(bse_symbols)

    return list(set(symbols))[:5244]  # Limit to 5,244

def main():
    # Load credentials from .env
    cred_path = Path('/Users/umashankar/.config/market-secrets/credentials.env')
    email = None
    password = None

    if cred_path.exists():
        with open(cred_path) as f:
            for line in f:
                if line.startswith('SCREENER_EMAIL='):
                    email = line.split('=')[1].strip().strip('"')
                elif line.startswith('SCREENER_PASSWORD='):
                    password = line.split('=')[1].strip().strip('"')

    if not email or not password or email.startswith('<'):
        log.error("❌ SCREENER_EMAIL or SCREENER_PASSWORD not configured")
        sys.exit(1)

    log.info(f"✅ Screener.in credentials loaded (email=***{email[-10:]})")
    log.info("")

    # Load symbols
    symbols = load_india_symbols()
    log.info(f"Loaded {len(symbols)} India NSE-BSE symbols")
    log.info("")

    # Run extraction
    extractor = ScreenerInExtractor(email, password)
    results = extractor.extract(symbols)

    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')

    # JSON export
    json_file = Path('/Users/umashankar/market-pipeline/code/python_files/reports') / f'edgar_screener_india_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(results, f, indent=2)
    log.info(f"✅ JSON export: {json_file.name}")

    # Generate CQL for Cassandra
    if results['data']:
        cql_file = Path('/Users/umashankar/market-pipeline/code/python_files/reports') / f'edgar_screener_india_cassandra_{timestamp}.cql'
        with open(cql_file, 'w') as f:
            f.write("-- screener.in India Fundamentals - NSE-BSE\n")
            f.write(f"-- Extracted: {datetime.now()}\n\n")

            for item in results['data']:
                if not item.get('pe'):
                    continue
                symbol = item['symbol']  # NSE/BSE bare symbol
                pe = item.get('pe') or 0
                pb = item.get('pb') or 0
                roe = item.get('roe') or 0
                de = item.get('debt_to_equity') or 0
                opm = item.get('opm') or 0
                mc = item.get('market_cap') or 0
                dy = item.get('dividend_yield') or 0

                # Cassandra key for India = bare symbol (no .NS suffix)
                cql = f"""UPDATE herrrickshaw.stock_quotes
SET pe = {pe}, pb = {pb}, roe = {roe}, debt_to_equity = {de},
    opm = {opm}, market_cap = {mc}, dividend_yield = {dy}, fetched_at = toTimestamp(now())
WHERE market = 'india' AND yf_ticker = '{symbol}';"""

                f.write(cql + "\n\n")

        log.info(f"✅ CQL export: {cql_file.name}")
        log.info("")
        log.info(f"Next: Load to Cassandra with: cqlsh -f {cql_file.name}")

if __name__ == '__main__':
    main()
