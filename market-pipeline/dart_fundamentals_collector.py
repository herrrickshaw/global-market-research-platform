#!/usr/bin/env python3
"""
DART Fundamentals Collector — Phase 1 Korea
Collects quarterly financial statements for 2,597 KOSPI/KOSDAQ companies
Extracts PE, ROE, ROA, margins, debt ratios → 20-column canonical schema
"""

import os
import sys
import json
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

DART_KEY = os.getenv('DART_KEY', '')

# Korean account name mappings (DART → our 20-column schema)
ACCOUNT_MAPPINGS = {
    # Net income metrics
    '당기순이익': 'net_income',
    '연결당기순이익': 'net_income',

    # Assets
    '총자산': 'total_assets',
    '유동자산': 'current_assets',

    # Equity / Liabilities
    '자본': 'equity',
    '자본금': 'equity',
    '자본총계': 'equity',
    '부채': 'total_liabilities',
    '유동부채': 'current_liabilities',

    # Revenue / Expenses
    '매출액': 'revenue',
    '매출': 'revenue',
    '영업이익': 'operating_income',
    '영업비용': 'operating_expense',

    # Ratios / Metrics
    '주당순이익': 'eps',
    '영업현금흐름': 'operating_cash_flow',
}

class DARTCollector:
    def __init__(self):
        self.results = []
        self.errors = []
        self.korea_symbols = []
        self.start_time = datetime.now()

    def load_korea_symbols(self, cassandra_query=True, sample_only=False):
        """Load 2,597 Korea symbols from Cassandra or from CSV"""
        log.info("Loading Korea symbols...")

        if cassandra_query:
            # Query Cassandra for all Korea symbols
            try:
                import subprocess
                cql = "SELECT yf_ticker FROM herrrickshaw.stock_quotes WHERE market = 'korea' LIMIT 10000;"
                result = subprocess.run(['cqlsh', 'localhost', '-e', cql],
                                       capture_output=True, text=True, timeout=30)

                symbols = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and not any(x in line for x in ['yf_ticker', '---', '(', 'rows']):
                        symbols.append(line)

                self.korea_symbols = symbols
                log.info(f"✅ Loaded {len(symbols)} Korea symbols from Cassandra")
                return symbols
            except Exception as e:
                log.warning(f"Cassandra query failed: {e}. Using fallback...")

        # Fallback: read from CSV
        try:
            df = pd.read_csv('market-pipeline/data/korea_list.csv')
            symbols = df['symbol'].tolist() if 'symbol' in df.columns else df.iloc[:, 0].tolist()
            self.korea_symbols = symbols
            log.info(f"✅ Loaded {len(symbols)} Korea symbols from korea_list.csv")
            return symbols
        except Exception as e:
            log.warning(f"CSV load failed: {e}")

        # Fallback: hardcoded major Korea symbols + DART codes for testing
        # Format: (stock_code, dart_corp_code)
        hardcoded_symbols = [
            ('005930', '00126380'),  # Samsung Electronics
            ('000660', '00056679'),  # LG Electronics
            ('051910', '00114690'),  # LG Chem
            ('035420', '00028174'),  # NAVER
            ('035720', '00038625'),  # Kakao
            ('012330', '00032271'),  # Hyundai Motor
            ('005380', '00044543'),  # Hyundai Motors
            ('207940', '00068606'),  # SM Entertainment
            ('000270', '00079905'),  # KIA
            ('015760', '00009388'),  # SK Hynix
        ]

        self.korea_symbols = hardcoded_symbols
        log.info(f"⚠️  Using {len(hardcoded_symbols)} hardcoded test symbols (Cassandra/CSV unavailable)")
        return hardcoded_symbols

    def get_dart_code(self, stock_code):
        """Map stock code (e.g., 005930.KS or 005930) to DART corp code"""
        try:
            # Strip suffix if present (e.g., .KS, .KQ)
            bare_code = stock_code.split('.')[0] if '.' in stock_code else stock_code

            url = "https://opendart.fss.or.kr/api/company.json"
            params = {
                'crtfc_key': DART_KEY,
                'stock_code': bare_code,  # DART API uses stock_code, not corp_code
                'pageNo': '1'
            }
            resp = requests.get(url, params=params, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == '000' and data.get('list'):
                    corp_code = data['list'][0].get('corp_code')
                    if corp_code:
                        log.debug(f"Mapped {stock_code} → {corp_code}")
                        return corp_code
        except Exception as e:
            log.debug(f"Error mapping {stock_code}: {e}")

        return None

    def fetch_financials(self, dart_code, stock_code):
        """Fetch latest quarterly financial statements from DART"""
        try:
            # Get latest financial statements (latest quarter: reprt_code=11012 for Q2, 11013 for Q3, etc.)
            # Use 11012 for latest available (DART auto-selects most recent)
            url = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
            params = {
                'crtfc_key': DART_KEY,
                'corp_code': dart_code,
                'bsns_year': '2024',
                'reprt_code': '11012',  # Latest quarter
                'fs_div': 'OFS'  # Consolidated
            }

            resp = requests.get(url, params=params, timeout=15)
            time.sleep(0.5)  # Rate limit: 2 req/sec

            if resp.status_code == 200:
                data = resp.json()
                if data.get('status') == '000':
                    accounts = data.get('list', [])

                    # Parse accounts into structured data
                    parsed = self._parse_accounts(accounts)
                    if parsed:
                        return self._calculate_ratios(parsed, stock_code, dart_code)
        except Exception as e:
            log.debug(f"Error fetching DART data for {dart_code}: {e}")
            self.errors.append({'symbol': stock_code, 'error': str(e)})

        return None

    def _parse_accounts(self, accounts):
        """Parse DART account list into structured metrics"""
        parsed = {}

        for account in accounts:
            account_name = account.get('account_nm', '').strip()
            amount_str = account.get('thstrm_amount', '0')

            # Convert amount string (Korean number with commas) to float
            try:
                amount = float(amount_str.replace(',', ''))
            except:
                amount = 0

            # Map Korean account name to our field
            for kr_name, en_name in ACCOUNT_MAPPINGS.items():
                if kr_name in account_name:
                    if en_name not in parsed:
                        parsed[en_name] = amount
                    break

        return parsed if parsed else None

    def _calculate_ratios(self, parsed, stock_code, dart_code):
        """Calculate 20-column fundamentals from parsed accounts"""
        result = {
            'market': 'korea',
            'symbol': stock_code,
            'dart_code': dart_code,
            'source': 'dart'
        }

        # Direct values
        result['market_cap'] = None  # Not in DART direct output
        result['enterprise_val'] = None  # Need to calculate (market cap - net debt)

        # ROE = Net Income / Equity
        if parsed.get('net_income') and parsed.get('equity'):
            result['roe'] = (parsed['net_income'] / parsed['equity']) * 100

        # ROA = Net Income / Total Assets
        if parsed.get('net_income') and parsed.get('total_assets'):
            result['roa'] = (parsed['net_income'] / parsed['total_assets']) * 100

        # NPM = Net Income / Revenue
        if parsed.get('net_income') and parsed.get('revenue'):
            result['npm'] = (parsed['net_income'] / parsed['revenue']) * 100

        # OPM = Operating Income / Revenue
        if parsed.get('operating_income') and parsed.get('revenue'):
            result['opm'] = (parsed['operating_income'] / parsed['revenue']) * 100

        # Debt to Equity
        if parsed.get('total_liabilities') and parsed.get('equity'):
            result['debt_to_equity'] = parsed['total_liabilities'] / parsed['equity']

        # Current Ratio
        if parsed.get('current_assets') and parsed.get('current_liabilities'):
            result['current_ratio'] = parsed['current_assets'] / parsed['current_liabilities']

        # Placeholder for metrics not in DART direct output
        result['pe'] = None  # Requires current stock price
        result['pb'] = None  # Requires market cap
        result['ps'] = None  # Requires market cap
        result['dividend_yield'] = None  # Need separate dividend data
        result['roce'] = None  # Complex calculation
        result['roc'] = None  # ROC = NOPAT / Invested Capital
        result['asset_turnover'] = None  # Requires market cap
        result['revenue_growth'] = None  # Requires year-over-year comparison
        result['eps_growth'] = None  # Requires year-over-year EPS
        result['interest_cov'] = None  # Need interest expense data

        return result

    def collect_all(self, symbols, batch_size=50):
        """Collect fundamentals for all Korea symbols"""
        log.info(f"Starting collection for {len(symbols)} Korea symbols...")

        for i, item in enumerate(symbols):
            if (i + 1) % 100 == 0:
                log.info(f"  Progress: {i+1}/{len(symbols)}")

            # Handle both tuple (symbol, dart_code) and plain symbol
            if isinstance(item, tuple):
                symbol, dart_code = item
            else:
                symbol = item
                # Map symbol to DART code (only if not tuple)
                dart_code = self.get_dart_code(symbol)

            if not dart_code:
                log.debug(f"Could not map {symbol} to DART code")
                continue

            # Fetch and parse financials
            result = self.fetch_financials(dart_code, symbol)
            if result:
                with __import__('threading').Lock():
                    self.results.append(result)

        log.info(f"✅ Collection complete: {len(self.results)} symbols with data")

    def generate_cql(self, output_dir='market-pipeline/code/python_files/reports'):
        """Generate CQL UPDATE statements for Cassandra"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        cql_file = output_dir / f"FUNDAMENTALS_DART_KOREA_{timestamp}.cql"

        statements = []
        for result in self.results:
            symbol = result['symbol'].replace("'", "''")
            set_clauses = []

            # Build SET clauses for non-None values
            for col in ['pe', 'pb', 'ps', 'dividend_yield', 'roe', 'roa', 'opm', 'npm',
                       'roce', 'roc', 'asset_turnover', 'revenue_growth', 'eps_growth',
                       'debt_to_equity', 'current_ratio', 'interest_cov', 'market_cap', 'enterprise_val']:
                value = result.get(col)
                if value is not None:
                    if isinstance(value, str):
                        set_clauses.append(f"{col} = '{value}'")
                    else:
                        set_clauses.append(f"{col} = {value}")

            set_clauses.append("fundamentals_source = 'dart'")
            set_clauses.append("fundamentals_date = toTimestamp(now())")

            cql = f"UPDATE herrrickshaw.stock_quotes SET {', '.join(set_clauses)} WHERE market = 'korea' AND yf_ticker = '{symbol}';\n"
            statements.append(cql)

        with open(cql_file, 'w') as f:
            f.write(f"-- Korea Fundamentals from DART\n")
            f.write(f"-- Generated: {datetime.now()}\n")
            f.write(f"-- Symbols: {len(self.results)}\n\n")
            f.writelines(statements)

        log.info(f"✅ Generated CQL: {cql_file.name} ({len(statements)} statements)")
        return cql_file

    def report(self):
        """Print final report"""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        log.info("")
        log.info("╔════════════════════════════════════════════════════════════╗")
        log.info("║          DART KOREA FUNDAMENTALS COLLECTION COMPLETE       ║")
        log.info("╚════════════════════════════════════════════════════════════╝")
        log.info(f"Total records collected: {len(self.results)}")
        log.info(f"Total errors: {len(self.errors)}")
        log.info(f"Elapsed time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
        log.info("")
        log.info("Coverage:")
        log.info(f"  ROE: {sum(1 for r in self.results if r.get('roe'))} / {len(self.results)}")
        log.info(f"  ROA: {sum(1 for r in self.results if r.get('roa'))} / {len(self.results)}")
        log.info(f"  OPM: {sum(1 for r in self.results if r.get('opm'))} / {len(self.results)}")
        log.info(f"  NPM: {sum(1 for r in self.results if r.get('npm'))} / {len(self.results)}")
        log.info(f"  D/E: {sum(1 for r in self.results if r.get('debt_to_equity'))} / {len(self.results)}")

def main():
    if not DART_KEY:
        log.error("DART_KEY not found in environment")
        return

    log.info("""
╔════════════════════════════════════════════════════════════════╗
║       PHASE 1: DART KOREA FUNDAMENTALS COLLECTOR               ║
║       Collects quarterly financials for 2,597 KOSPI/KOSDAQ     ║
╚════════════════════════════════════════════════════════════════╝
""")

    collector = DARTCollector()

    # Step 1: Load symbols
    symbols = collector.load_korea_symbols(cassandra_query=False)  # Use fallback for initial test

    if not symbols:
        log.error("No symbols loaded. Exiting.")
        return

    # Step 2: Collect fundamentals
    log.info("")
    log.info(f"Starting collection for {len(symbols)} symbols...")
    collector.collect_all(symbols)

    # Step 3: Generate CQL
    if collector.results:
        cql_file = collector.generate_cql()
        log.info(f"Next: Load CQL into Cassandra:")
        log.info(f"  cqlsh localhost < {cql_file}")

    # Step 4: Report
    collector.report()

if __name__ == '__main__':
    main()
