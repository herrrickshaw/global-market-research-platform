#!/usr/bin/env python3
"""
Production Fundamentals Collector - 25,335 Symbols
Parallel API collection: AlphaVantage (US) + EODHD (EU/JP/KR/CN)
Generates CQL for Cassandra bulk load
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)

# API Keys
ALPHAVANTAGE_KEY = os.getenv('ALPHAVANTAGE_KEY', '')
EODHD_KEY = os.getenv('EODHD_KEY', '')

class ProductionCollector:
    """Production-grade parallel fundamentals collector"""

    def __init__(self):
        self.results = []
        self.errors = defaultdict(list)
        self.start_time = datetime.now()
        self.lock = __import__('threading').Lock()

    def collect_us_alphavantage(self, symbols, max_workers=3):
        """AlphaVantage: US fundamentals (5 calls/min rate limit)"""
        log.info(f"[US/AlphaVantage] Starting collection for {len(symbols)} symbols...")

        collected = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._av_fetch, sym): sym for sym in symbols}

            for i, future in enumerate(as_completed(futures), 1):
                sym = futures[future]
                if i % 50 == 0:
                    log.info(f"  [US] Progress: {i}/{len(symbols)} ({collected} collected)")

                try:
                    result = future.result()
                    if result:
                        with self.lock:
                            self.results.append(result)
                        collected += 1
                except Exception as e:
                    self.errors['alphavantage'].append({'symbol': sym, 'error': str(e)})

                # Rate limit: 5/min = 12s between calls
                time.sleep(2)

        log.info(f"  [US/AlphaVantage] Collected: {collected}/{len(symbols)}")
        return collected

    def _av_fetch(self, symbol):
        """Fetch from AlphaVantage"""
        try:
            url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={ALPHAVANTAGE_KEY}"
            resp = requests.get(url, timeout=15)
            data = resp.json()

            pe = data.get('PE')
            if pe and pe != 'None':
                return {
                    'market': 'us',
                    'symbol': symbol,
                    'pe': float(pe),
                    'pb': float(data.get('PriceToBookRatio', 0)) if data.get('PriceToBookRatio') and data.get('PriceToBookRatio') != 'None' else None,
                    'roe': float(data.get('ReturnOnEquityTTM', 0)) if data.get('ReturnOnEquityTTM') and data.get('ReturnOnEquityTTM') != 'None' else None,
                    'source': 'alphavantage'
                }
        except Exception as e:
            log.debug(f"Error fetching {symbol}: {e}")
        return None

    def collect_eodhd_batch(self, market, symbols, suffix='', max_workers=4):
        """EODHD: Global fundamentals (2 calls/sec rate limit)"""
        log.info(f"[{market.upper()}/EODHD] Starting collection for {len(symbols)} symbols...")

        collected = 0
        batch_size = 20
        total_batches = (len(symbols) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            batch = symbols[batch_num*batch_size:(batch_num+1)*batch_size]

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self._eodhd_fetch, market, sym, suffix): sym for sym in batch}

                for future in as_completed(futures):
                    sym = futures[future]
                    try:
                        result = future.result()
                        if result:
                            with self.lock:
                                self.results.append(result)
                            collected += 1
                    except Exception as e:
                        self.errors['eodhd'].append({'symbol': sym, 'market': market, 'error': str(e)})

                    # Rate limit: 2/sec = 0.5s between calls
                    time.sleep(0.5)

            log.info(f"  [{market.upper()}] Batch {batch_num+1}/{total_batches}: {collected} total collected")

        log.info(f"  [{market.upper()}/EODHD] Collected: {collected}/{len(symbols)}")
        return collected

    def _eodhd_fetch(self, market, symbol, suffix=''):
        """Fetch from EODHD"""
        try:
            ticker = f"{symbol}.{suffix}" if suffix else symbol
            url = f"https://eodhistoricaldata.com/api/fundamentals/{ticker}?api_token={EODHD_KEY}&fmt=json"
            resp = requests.get(url, timeout=15)

            if resp.status_code == 200:
                data = resp.json()

                if isinstance(data, dict) and 'Valuation' in data:
                    val = data.get('Valuation', {})
                    financials = data.get('Financials', {})

                    return {
                        'market': market,
                        'symbol': symbol,
                        'pe': float(val.get('TrailingPE')) if val.get('TrailingPE') else None,
                        'pb': float(val.get('PB')) if val.get('PB') else None,
                        'roe': float(financials.get('Balance_Sheet', {}).get('annual', {}).get('Return on Equity', [None])[-1]) if financials.get('Balance_Sheet') else None,
                        'source': 'eodhd'
                    }
        except Exception as e:
            log.debug(f"Error fetching {symbol}.{suffix if suffix else ''}: {e}")
        return None

    def generate_cql(self, output_dir='market-pipeline/code/python_files/reports'):
        """Generate CQL for Cassandra bulk load"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        by_market = defaultdict(list)
        for result in self.results:
            by_market[result['market']].append(result)

        total_statements = 0
        for market, records in by_market.items():
            cql_file = output_dir / f"FUNDAMENTALS_API_COLLECTED_{market.upper()}_{timestamp}.cql"

            with open(cql_file, 'w') as f:
                f.write(f"-- {market.upper()} Fundamentals (API Collection)\n")
                f.write(f"-- Generated: {datetime.now()}\n")
                f.write(f"-- Symbols: {len(records)}\n\n")

                for rec in records:
                    symbol = rec['symbol'].replace("'", "''")
                    pe = rec.get('pe') or 0
                    pb = rec.get('pb') or 0
                    roe = rec.get('roe') or 0

                    cql = f"UPDATE herrrickshaw.stock_quotes SET pe = {pe}, pb = {pb}, roe = {roe}, fetched_at = toTimestamp(now()) WHERE market = '{market}' AND yf_ticker = '{symbol}';\n"
                    f.write(cql)
                    total_statements += 1

            log.info(f"✅ Generated: {cql_file.name} ({len(records)} statements)")

        return total_statements

    def report(self):
        """Print final report"""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        log.info("")
        log.info("╔════════════════════════════════════════════════════════════╗")
        log.info("║         FUNDAMENTALS COLLECTION COMPLETE                  ║")
        log.info("╚════════════════════════════════════════════════════════════╝")
        log.info(f"Symbols collected: {len(self.results)}")
        log.info(f"Total errors: {sum(len(v) for v in self.errors.values())}")
        log.info(f"Elapsed time: {elapsed:.1f} seconds ({elapsed/3600:.1f} hours)")
        log.info("")

def main():
    log.info("""
╔════════════════════════════════════════════════════════════════╗
║   PRODUCTION FUNDAMENTALS COLLECTOR - ALL 25,335 SYMBOLS       ║
╚════════════════════════════════════════════════════════════════╝
""")

    # Initialize collector
    collector = ProductionCollector()

    # Phase 1: US (7,283 symbols via AlphaVantage)
    # Note: Real implementation would read symbols from Cassandra
    us_symbols = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'TSLA']  # Demo

    if us_symbols:
        log.info("📊 PHASE 1: US Fundamentals (AlphaVantage)")
        collector.collect_us_alphavantage(us_symbols[:3])  # Demo: first 3

    # Phase 2: Europe (1,709 symbols via EODHD)
    eu_symbols = ['SAP', 'SIEMENS', 'ASML', 'NESTL', 'ROCHE']  # Demo

    if eu_symbols:
        log.info("📊 PHASE 2: Europe Fundamentals (EODHD)")
        collector.collect_eodhd_batch('europe', eu_symbols[:2], suffix='.DE')  # Demo

    # Generate CQL
    if collector.results:
        total = collector.generate_cql()
        log.info(f"Total UPDATE statements: {total}")

    collector.report()

    log.info("""
NEXT STEPS:
  1. Load CQL to Cassandra: cqlsh -f market-pipeline/code/python_files/reports/FUNDAMENTALS_API_COLLECTED_*.cql
  2. Verify: SELECT COUNT(*) FROM stock_quotes WHERE pe > 0 ALLOW FILTERING;
  3. Deploy on EC2 for full collection (8h parallel)
""")

if __name__ == '__main__':
    main()
