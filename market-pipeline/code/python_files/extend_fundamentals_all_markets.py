#!/usr/bin/env python3
"""
Extend fundamentals coverage by extracting from ALL Dropbox parquet files
Strategy: Use factorial_screener_signals_*.parquet for each market
These contain pre-computed fundamental scores (Piotroski, ROCE, margins, etc)
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger(__name__)


class ExtendedFundamentalsLoader:
    """Extract fundamentals from all factorial screener parquets"""

    def __init__(self):
        self.dropbox = Path("/Users/umashankar/Library/CloudStorage/Dropbox")
        self.extracted = {"us": [], "europe": [], "japan": [], "korea": [], "india": []}
        self.failed = []

    def load_market_screener_signals(self, market: str, pattern: str) -> int:
        """Load screener signals for a specific market"""
        log.info(f"Loading {market.upper()} factorial screener signals...")

        count = 0
        for parquet_file in self.dropbox.glob(f"**/*{pattern}*.parquet"):
            size_mb = parquet_file.stat().st_size / (1024*1024)

            # Skip very large files (>200MB) to save memory
            if size_mb > 200:
                log.info(f"  ⏭️  Skipping {parquet_file.name} ({size_mb:.0f}MB - too large)")
                continue

            if size_mb < 0.1:
                continue

            try:
                df = pd.read_parquet(parquet_file)
                log.info(f"  📖 Reading: {parquet_file.name} ({size_mb:.1f}MB, {len(df):,} rows)")

                # Extract ticker and fundamental columns
                ticker_col = None
                for col in ['ticker', 'symbol', 'Symbol']:
                    if col in df.columns:
                        ticker_col = col
                        break

                if not ticker_col:
                    log.warning(f"     ⚠️  No ticker column found")
                    continue

                # Get sample of rows with fundamentals
                sample_size = min(len(df), 5000)
                for _, row in df.head(sample_size).iterrows():
                    ticker = str(row.get(ticker_col, '')).strip()
                    if not ticker:
                        continue

                    # Extract any available fundamentals
                    fundamental = {
                        'symbol': ticker,
                        'market': market,
                        'piotroski': row.get('piotroski') or row.get('f_score') or row.get('canonical'),
                        'roce': row.get('roce') or row.get('roace'),
                        'roe': row.get('roe') or row.get('roa'),
                        'debt_ratio': row.get('debt_ratio') or row.get('leverage'),
                        'margin': row.get('margin') or row.get('opm'),
                        'fetched_at': datetime.utcnow().isoformat()
                    }

                    # Only add if has at least one fundamental metric
                    if any(v for v in [fundamental['piotroski'], fundamental['roce'], fundamental['roe'], fundamental['debt_ratio'], fundamental['margin']]):
                        self.extracted[market].append(fundamental)
                        count += 1

                log.info(f"     ✅ Extracted: {count} symbols so far")

                # If we have enough, break to save memory
                if count > 5000:
                    break

            except Exception as e:
                log.warning(f"  ❌ Error reading {parquet_file.name}: {e}")
                continue

        log.info(f"  ✅ Total {market.upper()}: {len(self.extracted[market]):,} symbols")
        return len(self.extracted[market])

    def load_all(self):
        """Load fundamentals from all markets"""
        log.info("=" * 80)
        log.info("EXTENDED FUNDAMENTALS LOADER - ALL MARKETS")
        log.info("=" * 80)
        log.info("")

        # Load each market's factorial screener signals
        self.load_market_screener_signals("us", "factorial_screener_signals_us")
        log.info("")

        self.load_market_screener_signals("europe", "factorial_screener_signals.*EU")
        log.info("")

        self.load_market_screener_signals("japan", "factorial_screener_signals_JP")
        log.info("")

        self.load_market_screener_signals("korea", "factorial_screener_signals_KR")
        log.info("")

        self.load_market_screener_signals("india", "factorial_screener_signals_IN")
        log.info("")

        # Summary
        total = sum(len(v) for v in self.extracted.values())
        log.info("=" * 80)
        log.info("SUMMARY")
        log.info("=" * 80)
        log.info("")
        for market, records in self.extracted.items():
            if records:
                log.info(f"  {market.upper():10} {len(records):6,} symbols with fundamentals")

        log.info("")
        log.info(f"  TOTAL: {total:,} extended fundamentals")
        log.info("")

        return total

    def generate_cql(self) -> str:
        """Generate CQL UPDATE statements"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        reports_dir = Path('/Users/umashankar/market-pipeline/code/python_files/reports')
        reports_dir.mkdir(exist_ok=True)

        cql_file = reports_dir / f'extend_fundamentals_all_markets_{timestamp}.cql'

        log.info("Generating CQL statements...")

        with open(cql_file, 'w') as f:
            f.write("-- Extended Fundamentals for All Markets (Dropbox factorial screener signals)\n")
            f.write(f"-- Generated: {datetime.now()}\n")
            f.write("-- Source: factorial_screener_signals_*.parquet for all markets\n")
            f.write("-- Strategy: Load Piotroski, ROCE, ROE, debt_ratio, margin\n")
            f.write("\n")

            total = 0
            for market, records in self.extracted.items():
                f.write(f"-- {market.upper()}: {len(records)} symbols\n")

                for rec in records:
                    symbol = rec['symbol']
                    market_name = rec['market']
                    piotroski = rec.get('piotroski') or 0
                    roce = rec.get('roce') or 0
                    roe = rec.get('roe') or 0
                    debt = rec.get('debt_ratio') or 0
                    margin = rec.get('margin') or 0

                    cql = f"""UPDATE herrrickshaw.stock_quotes SET piotroski = {piotroski}, roce = {roce}, roe = {roe}, debt_to_equity = {debt}, opm = {margin}, fetched_at = toTimestamp(now()) WHERE market = '{market_name}' AND yf_ticker = '{symbol}';\n"""
                    f.write(cql)
                    total += 1

            f.write(f"\n-- Total: {total} UPDATE statements\n")

        log.info(f"✅ CQL file: {cql_file.name}")
        log.info(f"   Statements: {total}")
        log.info("")

        return str(cql_file)


def main():
    loader = ExtendedFundamentalsLoader()
    total = loader.load_all()

    if total > 0:
        cql_file = loader.generate_cql()

        log.info("=" * 80)
        log.info("✅ READY TO EXTEND CASSANDRA")
        log.info("=" * 80)
        log.info("")
        log.info(f"Load command:")
        log.info(f"  cqlsh -f {cql_file}")
        log.info("")
    else:
        log.error("No fundamentals extracted")


if __name__ == '__main__':
    main()
