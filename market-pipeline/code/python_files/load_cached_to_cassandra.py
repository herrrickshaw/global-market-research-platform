#!/usr/bin/env python3
"""
Load cached OHLCV symbols from parquet files to Cassandra.
Fixes CQL string literal quoting issue.
"""

import os
import sys
import json
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

try:
    import pyarrow.parquet as pq
    import pandas as pd
except ImportError:
    log.error("pandas and pyarrow required. Run: pip install pandas pyarrow")
    sys.exit(1)


class CassandraLoaderFromCache:
    """Load cached symbol data to Cassandra"""

    def __init__(self):
        self.cache_dir = Path('/Users/umashankar/market-pipeline/code/python_files/cache_seed')
        self.symbols_loaded = []
        self.cql_statements = []

    def load_cached_symbols(self) -> Dict[str, List[str]]:
        """Load unique symbols from all cached OHLCV parquet files by market"""
        log.info("=" * 80)
        log.info("CASSANDRA LOADER - CACHED SYMBOLS (OHLCV → UNIQUE SYMBOLS)")
        log.info("=" * 80)
        log.info("")

        market_symbols = {}

        # Map parquet files to markets
        file_mappings = {
            'us': 'cleaned_long_US.parquet',
            'china': 'cleaned_long_CN.parquet',
            'japan': 'cleaned_long_JP.parquet',
            'korea': 'cleaned_long_KR.parquet',
            'taiwan': 'cleaned_long_TW.parquet',
            'canada': 'cleaned_long_CA.parquet',
            'australia': 'cleaned_long_AU.parquet',
            'hongkong': 'cleaned_long_HK.parquet',
        }

        total_symbols = 0

        for market, filename in file_mappings.items():
            filepath = self.cache_dir / filename
            if not filepath.exists():
                log.warning(f"  ⚠️  {market.upper()}: File not found - {filename}")
                continue

            try:
                # Read parquet file
                pf = pq.ParquetFile(str(filepath))
                df = pf.read().to_pandas()

                # Extract unique symbols from 'Symbol' column (OHLCV data structure)
                if 'Symbol' in df.columns:
                    symbols = df['Symbol'].unique().tolist()
                elif 'symbol' in df.columns:
                    symbols = df['symbol'].unique().tolist()
                elif 'ticker' in df.columns:
                    symbols = df['ticker'].unique().tolist()
                else:
                    log.warning(f"  ⚠️  {market.upper()}: No symbol column found")
                    continue

                market_symbols[market] = symbols
                total_symbols += len(symbols)

                log.info(f"  ✅ {market.upper():15} {len(symbols):6,} unique symbols from {pf.metadata.num_rows:,} OHLCV rows")

            except Exception as e:
                log.error(f"  ❌ {market.upper()}: Error loading - {e}")

        log.info("")
        log.info(f"Total unique symbols loaded: {total_symbols:,}")
        log.info("")

        return market_symbols

    def generate_cql_inserts(self, market_symbols: Dict[str, List[str]]) -> List[str]:
        """Generate CQL INSERT statements for all symbols"""
        log.info("Generating CQL statements...")
        log.info("")

        cql_statements = []
        timestamp = datetime.now().isoformat()

        for market, symbols in market_symbols.items():
            for symbol in symbols:
                # PROPER CQL: use doubled single quotes for string literals in VALUES
                # INSERT INTO herrrickshaw.stock_quotes (market, yf_ticker, fetched_at)
                # VALUES ('market_value', 'symbol_value', ...)
                #
                # Since we're building a string, we need to escape the quotes:
                # The final CQL should have single quotes around string values

                cql = f"""INSERT INTO herrrickshaw.stock_quotes (market, yf_ticker, fetched_at) VALUES ('{market}', '{symbol}', '{timestamp}');"""
                cql_statements.append(cql)

        log.info(f"Generated {len(cql_statements):,} CQL statements")
        return cql_statements

    def save_cql_file(self, cql_statements: List[str]) -> Path:
        """Save CQL statements to file"""
        reports_dir = Path('/Users/umashankar/market-pipeline/code/python_files/reports')
        reports_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        cql_file = reports_dir / f'load_cached_symbols_cassandra_{timestamp}.cql'

        log.info(f"Writing CQL file: {cql_file.name}")

        with open(cql_file, 'w') as f:
            f.write("-- Load cached symbols to Cassandra\n")
            f.write(f"-- Generated: {datetime.now()}\n")
            f.write(f"-- Total statements: {len(cql_statements):,}\n")
            f.write("-- Source: Local parquet cache\n\n")

            for stmt in cql_statements:
                f.write(stmt + "\n")

        log.info(f"✅ CQL file saved: {cql_file}")
        log.info(f"   Path: {cql_file}")
        log.info("")

        return cql_file

    def load(self):
        """Main load workflow"""
        # Step 1: Load symbols from cache
        market_symbols = self.load_cached_symbols()

        # Step 2: Generate CQL
        cql_statements = self.generate_cql_inserts(market_symbols)

        # Step 3: Save CQL file
        cql_file = self.save_cql_file(cql_statements)

        # Step 4: Next steps
        log.info("=" * 80)
        log.info("✅ NEXT STEPS")
        log.info("=" * 80)
        log.info("")
        log.info("1️⃣  Start Cassandra container:")
        log.info("    colima start  (or docker-compose up)")
        log.info("")
        log.info("2️⃣  Load CQL file:")
        log.info(f"    cqlsh -f {cql_file}")
        log.info("")
        log.info("3️⃣  Verify load:")
        log.info("    cqlsh")
        log.info("    > SELECT COUNT(*) FROM herrrickshaw.stock_quotes WHERE market='us';")
        log.info("")


def main():
    loader = CassandraLoaderFromCache()
    loader.load()


if __name__ == '__main__':
    main()
