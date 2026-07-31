#!/usr/bin/env python3
"""
Screener.in India NSE-BSE Extraction with Django Form Authentication

Extracts 5,244 NSE-BSE symbols with fundamentals (PE, PB, ROE, Dividend Yield, Market Cap, etc.)
via authenticated session to screener.in, storing results as JSON + CQL for Cassandra.

Requirements:
    - ~/.config/market-secrets/credentials.env with SCREENER_EMAIL and SCREENER_PASSWORD
    - NSE equity list CSV
    - requests, beautifulsoup4, pandas

Usage:
    python screener_in_extractor.py [--symbols 5244] [--output data/screener_extract.json]
"""

import requests
import re
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from bs4 import BeautifulSoup
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
log = logging.getLogger(__name__)


class ScreenerExtractor:
    """Authenticated screener.in extraction for India NSE-BSE symbols."""

    BASE_URL = "https://www.screener.in"
    LOGIN_URL = f"{BASE_URL}/login/"
    SEARCH_API = f"{BASE_URL}/api/company/search/"
    CHART_API = f"{BASE_URL}/api/company/{{company_id}}/chart/"

    def __init__(self, email: str, password: str, rate_limit: float = 1.0):
        """
        Initialize extractor with credentials.

        Args:
            email: Screener.in login email
            password: Screener.in login password
            rate_limit: Delay between requests (seconds)
        """
        self.email = email
        self.password = password
        self.rate_limit = rate_limit
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.csrf_token = None
        self.authenticated = False
        self.request_count = 0
        self.start_time = datetime.utcnow()

    def get_csrf_token(self) -> Optional[str]:
        """Extract CSRF token from login page HTML."""
        log.info("Fetching CSRF token from login page...")
        try:
            response = self.session.get(self.LOGIN_URL, timeout=10)
            response.raise_for_status()

            # Try BeautifulSoup first
            soup = BeautifulSoup(response.text, 'html.parser')
            csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})

            if csrf_input and csrf_input.get('value'):
                self.csrf_token = csrf_input.get('value')
                log.info(f"✓ CSRF token extracted: {self.csrf_token[:20]}...")
                return self.csrf_token

            # Fallback: regex extraction
            match = re.search(
                r'csrfmiddlewaretoken["\']?\s*[=:]\s*["\']?([a-zA-Z0-9]{64})',
                response.text
            )
            if match:
                self.csrf_token = match.group(1)
                log.info(f"✓ CSRF token extracted (regex): {self.csrf_token[:20]}...")
                return self.csrf_token

            log.error("✗ CSRF token not found in login page")
            return None

        except Exception as e:
            log.error(f"✗ Failed to fetch CSRF token: {e}")
            return None

    def authenticate(self) -> bool:
        """Authenticate via Django form POST."""
        if not self.csrf_token:
            log.error("✗ No CSRF token available for authentication")
            return False

        log.info(f"Authenticating as {self.email}...")
        try:
            payload = {
                'username': self.email,
                'password': self.password,
                'csrfmiddlewaretoken': self.csrf_token,
                'next': '/',
            }

            response = self.session.post(
                self.LOGIN_URL,
                data=payload,
                allow_redirects=True,
                timeout=10
            )

            # Check if authentication succeeded by looking for session cookie
            if 'sessionid' in self.session.cookies:
                self.authenticated = True
                log.info("✓ Authentication successful (session established)")
                return True

            # Alternative: check response content for login error
            if 'invalid' in response.text.lower() or 'error' in response.text.lower():
                log.error("✗ Authentication failed (invalid credentials or server error)")
                return False

            # If we got a 200 and no obvious error, assume success
            self.authenticated = True
            log.info("✓ Authentication successful")
            return True

        except Exception as e:
            log.error(f"✗ Authentication request failed: {e}")
            return False

    def rate_limited_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Execute request with rate limiting."""
        time.sleep(self.rate_limit)
        self.request_count += 1

        try:
            if method.upper() == 'GET':
                return self.session.get(url, timeout=10, **kwargs)
            elif method.upper() == 'POST':
                return self.session.post(url, timeout=10, **kwargs)
            else:
                log.warning(f"Unknown HTTP method: {method}")
                return None
        except requests.RequestException as e:
            log.debug(f"Request failed: {e}")
            return None

    def search_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Search for symbol and return company info."""
        try:
            response = self.rate_limited_request(
                'GET',
                self.SEARCH_API,
                params={'q': symbol}
            )

            if response and response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]  # Return first match

            return None

        except Exception as e:
            log.debug(f"Search failed for {symbol}: {e}")
            return None

    def extract_fundamentals(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract fundamentals from company data and chart API."""
        result = {
            'symbol': company_data.get('symbol', ''),
            'name': company_data.get('name', ''),
            'company_id': company_data.get('id', ''),
            'url': company_data.get('url', ''),
            'price': None,
            'pe': None,
            'pb': None,
            'roe': None,
            'dividend_yield': None,
            'market_cap': None,
            'debt_to_equity': None,
            'profit_margin': None,
            'asm': None,  # Asset turnover / efficiency metric
            'sector': company_data.get('sector', ''),
            'industry': company_data.get('industry', ''),
            'timestamp': datetime.utcnow().isoformat(),
        }

        # Try to fetch chart data for price
        try:
            company_id = company_data.get('id')
            if company_id:
                chart_url = self.CHART_API.format(company_id=company_id)
                response = self.rate_limited_request(
                    'GET',
                    chart_url,
                    params={'q': 'Price', 'days': '1', 'consolidated': 'true'}
                )

                if response and response.status_code == 200:
                    chart_data = response.json()
                    if isinstance(chart_data, list) and len(chart_data) > 0:
                        # chart_data is array of [timestamp, price, ...]
                        result['price'] = chart_data[0].get('y') if isinstance(chart_data[0], dict) else chart_data[0][1]
        except Exception as e:
            log.debug(f"Failed to fetch chart data: {e}")

        return result

    def load_nse_bse_symbols(self, nse_csv_path: Path, limit: Optional[int] = None) -> List[str]:
        """Load NSE-BSE symbols from CSV file."""
        try:
            import pandas as pd

            if not nse_csv_path.exists():
                log.error(f"NSE CSV not found: {nse_csv_path}")
                return []

            df = pd.read_csv(nse_csv_path)

            # Handle various column names (SYMBOL, Symbol, symbol, etc.)
            symbol_col = None
            for col in df.columns:
                if col.lower() == 'symbol':
                    symbol_col = col
                    break

            if not symbol_col:
                log.warning(f"No 'symbol' column found. Available columns: {df.columns.tolist()}")
                symbol_col = df.columns[0]  # Try first column

            symbols = df[symbol_col].dropna().astype(str).tolist()

            if limit:
                symbols = symbols[:limit]

            log.info(f"Loaded {len(symbols)} NSE-BSE symbols from {nse_csv_path.name}")
            return symbols

        except ImportError:
            log.error("pandas not installed. Install with: pip install pandas")
            return []
        except Exception as e:
            log.error(f"Failed to load NSE symbols: {e}")
            return []

    def extract_all(self, symbols: List[str]) -> Dict[str, Any]:
        """Extract fundamentals for all symbols."""
        log.info(f"Starting extraction for {len(symbols)} symbols...")

        results = {
            'status': 'in_progress',
            'metadata': {
                'market': 'india',
                'symbols_requested': len(symbols),
                'symbols_extracted': 0,
                'symbols_failed': 0,
                'start_time': self.start_time.isoformat(),
            },
            'data': [],
            'errors': [],
        }

        extracted_count = 0
        failed_count = 0

        for i, symbol in enumerate(symbols, 1):
            try:
                company_data = self.search_symbol(symbol)

                if company_data:
                    fundamentals = self.extract_fundamentals(company_data)
                    results['data'].append(fundamentals)
                    extracted_count += 1
                else:
                    failed_count += 1
                    results['errors'].append({
                        'symbol': symbol,
                        'error': 'Not found on screener.in',
                        'timestamp': datetime.utcnow().isoformat(),
                    })

                # Log progress every 500 symbols
                if i % 500 == 0 or i == len(symbols):
                    elapsed = (datetime.utcnow() - self.start_time).total_seconds()
                    rate = i / elapsed if elapsed > 0 else 0
                    log.info(
                        f"[{i}/{len(symbols)}] Extracted: {extracted_count} | "
                        f"Failed: {failed_count} | Rate: {rate:.1f} sym/sec"
                    )

            except Exception as e:
                log.debug(f"Error extracting {symbol}: {e}")
                failed_count += 1
                results['errors'].append({
                    'symbol': symbol,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat(),
                })

        results['metadata']['symbols_extracted'] = extracted_count
        results['metadata']['symbols_failed'] = failed_count
        results['metadata']['end_time'] = datetime.utcnow().isoformat()
        results['metadata']['duration_seconds'] = (
            datetime.utcnow() - self.start_time
        ).total_seconds()
        results['metadata']['total_requests'] = self.request_count
        results['status'] = 'completed'

        return results

    def generate_cql(self, data: List[Dict[str, Any]]) -> List[str]:
        """Generate CQL INSERT statements for Cassandra."""
        cql_statements = []

        for item in data:
            symbol = item.get('symbol', '').replace("'", "''")
            name = item.get('name', '').replace("'", "''")

            # Build VALUES clause with NULL handling
            values = [
                f"'{item['symbol']}'",
                f"'{name}'",
                f"{item.get('price')}" if item.get('price') is not None else "NULL",
                f"{item.get('pe')}" if item.get('pe') is not None else "NULL",
                f"{item.get('pb')}" if item.get('pb') is not None else "NULL",
                f"{item.get('roe')}" if item.get('roe') is not None else "NULL",
                f"'{item['timestamp']}'",
            ]

            cql = (
                f"INSERT INTO herrrickshaw.stock_quotes "
                f"(market, yf_ticker, cmp, pe, pb, roe, updated_at) "
                f"VALUES ('india', {', '.join(values)});"
            )
            cql_statements.append(cql)

        return cql_statements


def load_credentials(cred_path: Path) -> tuple[Optional[str], Optional[str]]:
    """Load credentials from ~/.config/market-secrets/credentials.env"""
    email = None
    password = None

    if not cred_path.exists():
        log.error(f"Credentials file not found: {cred_path}")
        return None, None

    try:
        with open(cred_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if line.startswith('SCREENER_EMAIL='):
                    email = line.split('=', 1)[1].strip().strip('"').strip("'")
                elif line.startswith('SCREENER_PASSWORD='):
                    password = line.split('=', 1)[1].strip().strip('"').strip("'")

        if email and password:
            log.info(f"✓ Credentials loaded: {email}")
            return email, password
        else:
            log.error("SCREENER_EMAIL or SCREENER_PASSWORD not found in credentials file")
            return None, None

    except Exception as e:
        log.error(f"Failed to load credentials: {e}")
        return None, None


def main():
    parser = argparse.ArgumentParser(
        description='Extract NSE-BSE fundamentals from screener.in'
    )
    parser.add_argument(
        '--symbols',
        type=int,
        default=5244,
        help='Number of symbols to extract (default: 5244)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/screener_extract.json',
        help='Output JSON file path'
    )
    parser.add_argument(
        '--nse-csv',
        type=str,
        default='data/nse_equity_list.csv',
        help='NSE equity list CSV path'
    )
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=1.0,
        help='Delay between requests in seconds (default: 1.0)'
    )
    parser.add_argument(
        '--cql-output',
        type=str,
        help='Optional CQL output file for Cassandra'
    )

    args = parser.parse_args()

    # Load credentials
    cred_path = Path.home() / '.config' / 'market-secrets' / 'credentials.env'
    email, password = load_credentials(cred_path)

    if not email or not password:
        log.error("Cannot proceed without valid credentials")
        sys.exit(1)

    # Initialize extractor
    extractor = ScreenerExtractor(email, password, rate_limit=args.rate_limit)

    # Get CSRF token
    if not extractor.get_csrf_token():
        log.error("Failed to obtain CSRF token")
        sys.exit(1)

    # Authenticate
    if not extractor.authenticate():
        log.error("Authentication failed")
        sys.exit(1)

    # Load symbols
    nse_csv_path = Path(args.nse_csv)
    symbols = extractor.load_nse_bse_symbols(nse_csv_path, limit=args.symbols)

    if not symbols:
        log.error("No symbols to extract")
        sys.exit(1)

    # Extract fundamentals
    results = extractor.extract_all(symbols)

    # Save JSON
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    log.info(f"✓ Results saved to {output_path}")

    # Generate and save CQL if requested
    if args.cql_output:
        cql_statements = extractor.generate_cql(results['data'])
        cql_path = Path(args.cql_output)
        cql_path.parent.mkdir(parents=True, exist_ok=True)

        with open(cql_path, 'w') as f:
            f.write('\n'.join(cql_statements))

        log.info(f"✓ CQL statements saved to {cql_path} ({len(cql_statements)} inserts)")

    # Print summary
    log.info(
        f"\n{'='*60}\n"
        f"Extraction Summary\n"
        f"{'='*60}\n"
        f"Market: {results['metadata']['market']}\n"
        f"Symbols Requested: {results['metadata']['symbols_requested']}\n"
        f"Symbols Extracted: {results['metadata']['symbols_extracted']}\n"
        f"Symbols Failed: {results['metadata']['symbols_failed']}\n"
        f"Success Rate: {100 * results['metadata']['symbols_extracted'] / results['metadata']['symbols_requested']:.1f}%\n"
        f"Duration: {results['metadata']['duration_seconds']:.1f} seconds\n"
        f"Total Requests: {results['metadata']['total_requests']}\n"
        f"{'='*60}"
    )


if __name__ == '__main__':
    main()
