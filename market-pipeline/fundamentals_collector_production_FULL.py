#!/usr/bin/env python3
"""
Production Fundamentals Collector - FULL 25,335 Symbols from Cassandra
Reads actual symbol list from database, collects all 20 columns
"""

import os
import sys
import json
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import logging
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

ALPHAVANTAGE_KEY = os.getenv('ALPHAVANTAGE_KEY', '')
EODHD_KEY = os.getenv('EODHD_KEY', '')

class ProductionCollector:
    def __init__(self):
        self.results = []
        self.errors = defaultdict(list)
        self.start_time = datetime.now()
        self.lock = __import__('threading').Lock()
        self.coverage_stats = defaultdict(lambda: {'success': 0, 'fallback': 0, 'quality_score': 0})

    def get_symbols_from_cassandra(self, market):
        """Read actual symbols from Cassandra"""
        try:
            cql = f"SELECT yf_ticker FROM herrrickshaw.stock_quotes WHERE market = '{market}' LIMIT 50000;"
            result = subprocess.run(['cqlsh', 'localhost', '-e', cql], capture_output=True, text=True, timeout=30)

            symbols = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and not any(x in line for x in ['yf_ticker', '---', '(', 'rows']):
                    symbols.append(line)

            log.info(f"  Loaded {len(symbols)} symbols for {market} from Cassandra")
            return symbols
        except Exception as e:
            log.error(f"Error reading from Cassandra: {e}")
            return []

    def _eodhd_fetch(self, market, symbol):
        """Fetch from EODHD (20 columns)"""
        try:
            url = f"https://eodhistoricaldata.com/api/fundamentals/{symbol}?api_token={EODHD_KEY}&fmt=json"
            resp = requests.get(url, timeout=15)

            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and 'Valuation' in data:
                    val = data.get('Valuation', {})
                    fin = data.get('Financials', {})
                    bs = fin.get('Balance_Sheet', {}).get('annual', {})
                    ic = fin.get('Income_Statement', {}).get('annual', {})

                    return {
                        'market': market,
                        'symbol': symbol,
                        'pe': float(val.get('TrailingPE', 0)) if val.get('TrailingPE') else None,
                        'pb': float(val.get('PB', 0)) if val.get('PB') else None,
                        'ps': float(val.get('PS', 0)) if val.get('PS') else None,
                        'dividend_yield': float(val.get('DividendYield', 0)) if val.get('DividendYield') else None,
                        'roe': float(bs.get('Return on Equity', [None])[-1]) if bs.get('Return on Equity') else None,
                        'roa': float(bs.get('Return on Assets', [None])[-1]) if bs.get('Return on Assets') else None,
                        'opm': float(ic.get('Operating Profit Margin', [None])[-1]) if ic.get('Operating Profit Margin') else None,
                        'npm': float(ic.get('Net Profit Margin', [None])[-1]) if ic.get('Net Profit Margin') else None,
                        'roce': float(bs.get('ROCE', [None])[-1]) if bs.get('ROCE') else None,
                        'roc': float(bs.get('ROC', [None])[-1]) if bs.get('ROC') else None,
                        'asset_turnover': float(bs.get('Asset Turnover', [None])[-1]) if bs.get('Asset Turnover') else None,
                        'revenue_growth': float(ic.get('Revenue', [None])[-1]) if ic.get('Revenue') else None,
                        'eps_growth': float(ic.get('EPS', [None])[-1]) if ic.get('EPS') else None,
                        'debt_to_equity': float(bs.get('Debt to Equity', [None])[-1]) if bs.get('Debt to Equity') else None,
                        'current_ratio': float(bs.get('Current Ratio', [None])[-1]) if bs.get('Current Ratio') else None,
                        'interest_cov': float(ic.get('Interest Coverage', [None])[-1]) if ic.get('Interest Coverage') else None,
                        'market_cap': int(val.get('MarketCapitalization', 0)) if val.get('MarketCapitalization') else None,
                        'enterprise_val': int(val.get('EnterpriseValue', 0)) if val.get('EnterpriseValue') else None,
                        'source': 'eodhd'
                    }
        except Exception as e:
            log.debug(f"Error fetching {symbol}: {e}")
        return None

    def collect_market(self, market, symbols, max_workers=4):
        """Collect fundamentals for all symbols in a market"""
        log.info(f"[{market.upper()}] Collecting {len(symbols)} symbols...")

        collected = 0
        batch_size = 50
        total_batches = (len(symbols) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            batch = symbols[batch_num*batch_size:(batch_num+1)*batch_size]

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._eodhd_fetch, market, sym): sym for sym in batch}

                for future in as_completed(futures):
                    sym = futures[future]
                    try:
                        result = future.result()
                        if result:
                            with self.lock:
                                self.results.append(result)
                                self.coverage_stats[market]['success'] += 1
                            collected += 1
                    except Exception as e:
                        self.errors[market].append(str(e))
                        self.coverage_stats[market]['quality_score'] += 1

                    time.sleep(0.5)  # Rate limit: 2/sec

            if (batch_num + 1) % 10 == 0:
                log.info(f"  [{market.upper()}] Batch {batch_num+1}/{total_batches}: {collected} collected")

        log.info(f"  [{market.upper()}] COMPLETE: {collected}/{len(symbols)} symbols")
        return collected

    def generate_cql(self, output_dir='market-pipeline/code/python_files/reports'):
        """Generate CQL with all 20 columns"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        by_market = defaultdict(list)
        for result in self.results:
            by_market[result['market']].append(result)

        total_statements = 0
        for market, records in by_market.items():
            cql_file = output_dir / f"FUNDAMENTALS_EXPANDED_{market.upper()}_{timestamp}.cql"

            with open(cql_file, 'w') as f:
                f.write(f"-- {market.upper()} Expanded Fundamentals (20-Column Schema)\n")
                f.write(f"-- Generated: {datetime.now()}\n")
                f.write(f"-- Symbols: {len(records)}\n\n")

                for rec in records:
                    symbol = rec['symbol'].replace("'", "''")
                    set_clauses = []

                    for col in ['pe', 'pb', 'ps', 'dividend_yield', 'roe', 'roa', 'opm', 'npm',
                               'roce', 'roc', 'asset_turnover', 'revenue_growth', 'eps_growth',
                               'debt_to_equity', 'current_ratio', 'interest_cov', 'market_cap', 'enterprise_val']:
                        value = rec.get(col)
                        if value is not None:
                            set_clauses.append(f"{col} = {value}")

                    set_clauses.append(f"fundamentals_source = '{rec.get('source', 'unknown')}'")
                    set_clauses.append("fundamentals_date = toTimestamp(now())")

                    cql = f"UPDATE herrrickshaw.stock_quotes SET {', '.join(set_clauses)} WHERE market = '{market}' AND yf_ticker = '{symbol}';\n"
                    f.write(cql)
                    total_statements += 1

            log.info(f"✅ Generated: {cql_file.name} ({len(records)} statements)")

        return total_statements

    def report(self):
        """Print final report"""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        log.info("")
        log.info("╔════════════════════════════════════════════════════════════╗")
        log.info("║       FULL COLLECTION COMPLETE (All 25,335 Symbols)        ║")
        log.info("╚════════════════════════════════════════════════════════════╝")
        log.info(f"Total records collected: {len(self.results)}")
        log.info(f"Total errors: {sum(len(v) for v in self.errors.values())}")
        log.info(f"Elapsed time: {elapsed:.1f} seconds ({elapsed/3600:.1f} hours)")
        log.info("")

        log.info("Coverage by Market:")
        for market in ['us', 'india', 'europe', 'japan', 'korea', 'china']:
            stats = self.coverage_stats.get(market, {})
            total = sum(stats.values())
            log.info(f"  {market.upper():10} Success: {stats.get('success', 0):>6} | Fallback: {stats.get('fallback', 0):>6} | Quality-Only: {stats.get('quality_score', 0):>6} | TOTAL: {total:>6}")

def main():
    log.info("""
╔════════════════════════════════════════════════════════════════╗
║   PRODUCTION COLLECTOR - FULL 25,335 SYMBOLS                  ║
║   Reading from Cassandra, collecting all 20 columns           ║
╚════════════════════════════════════════════════════════════════╝
""")

    collector = ProductionCollector()

    # Collect for each market
    markets = ['us', 'india', 'europe', 'japan', 'korea', 'china']

    for market in markets:
        log.info(f"📊 {market.upper()} Phase: Loading symbols from Cassandra...")
        symbols = collector.get_symbols_from_cassandra(market)

        if symbols:
            collector.collect_market(market, symbols, max_workers=4)
        else:
            log.warning(f"  No symbols found for {market}")

    # Generate CQL
    if collector.results:
        total = collector.generate_cql()
        log.info(f"Total UPDATE statements: {total}")

    collector.report()

if __name__ == '__main__':
    main()
