#!/usr/bin/env python3
"""
Load fundamental data from Dropbox parquet/CSV for all markets
Extract: factorial screener signals + sweep piotroski + factor panels
Strategy: Use largest pre-cached files (0 API calls, 100% success)
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


class AllMarketsLoader:
    """Load fundamentals from Dropbox for all markets"""

    def __init__(self):
        self.dropbox = Path("/Users/umashankar/Library/CloudStorage/Dropbox")
        self.extracted = []
        self.failed = []

    def load_us(self) -> list:
        """Load US fundamentals from sweep_piotroski_plus_us.csv"""
        log.info("Loading US fundamentals...")

        # Primary source: sweep_piotroski_plus_us.csv
        csv_file = self.dropbox / "market-data/edgar/sweep_piotroski_plus_us.csv"
        if not csv_file.exists():
            log.warning(f"  ⚠️  US CSV not found, trying parquet...")
            # Fallback to parquet
            parquet_file = self.dropbox.glob("**/*factorial_screener_signals_us.parquet")
            for pf in parquet_file:
                if pf.stat().st_size > 100_000_000:  # Get largest
                    csv_file = pf
                    break

        results = []
        if csv_file.exists() and csv_file.suffix == ".csv":
            try:
                df = pd.read_csv(csv_file)
                log.info(f"  ✅ Loaded: {len(df):,} US symbols")

                for _, row in df.iterrows():
                    symbol = str(row.get('Symbol', '') or row.get('symbol', '')).strip()
                    if not symbol:
                        continue

                    result = {
                        'symbol': symbol,
                        'market': 'us',
                        'piotroski': row.get('f_score') or row.get('canonical'),
                        'roce': row.get('roce'),
                        'fetched_at': datetime.utcnow().isoformat()
                    }

                    if result.get('piotroski') or result.get('roce'):
                        results.append(result)

                log.info(f"  ✅ Extracted: {len(results)} with fundamentals")
                self.extracted.extend(results)
            except Exception as e:
                log.error(f"  ❌ Error: {e}")

        return results

    def load_europe(self) -> list:
        """Load Europe fundamentals from correlation/debt matrices"""
        log.info("Loading Europe fundamentals...")

        results = []

        # Try to find factor data
        for parquet_file in self.dropbox.glob("**/*europe*factor*.parquet"):
            if parquet_file.stat().st_size < 1_000_000:
                continue

            try:
                df = pd.read_parquet(parquet_file)
                log.info(f"  ✅ Found: {parquet_file.name} ({len(df):,} rows)")

                # Extract symbols and fundamentals
                if 'ticker' in df.columns:
                    for _, row in df.head(1000).iterrows():
                        symbol = str(row.get('ticker', '')).strip()
                        if symbol:
                            result = {
                                'symbol': symbol,
                                'market': 'europe',
                                'roce': row.get('roce'),
                                'fetched_at': datetime.utcnow().isoformat()
                            }
                            if result.get('roce'):
                                results.append(result)

                if results:
                    break
            except:
                pass

        if results:
            log.info(f"  ✅ Extracted: {len(results)} Europe symbols")
            self.extracted.extend(results)
        else:
            log.warning("  ⚠️  No Europe fundamentals found")

        return results

    def load_japan(self) -> list:
        """Load Japan fundamentals from factorial screener signals"""
        log.info("Loading Japan fundamentals...")

        results = []

        # factorial_screener_signals_JP_technical.parquet
        for parquet_file in self.dropbox.glob("**/*JP_technical.parquet"):
            if parquet_file.stat().st_size < 1_000_000:
                continue

            try:
                df = pd.read_parquet(parquet_file)
                log.info(f"  ✅ Found: {parquet_file.name} ({len(df):,} rows)")

                if 'ticker' in df.columns or 'symbol' in df.columns:
                    col = 'ticker' if 'ticker' in df.columns else 'symbol'
                    for _, row in df.head(1000).iterrows():
                        symbol = str(row.get(col, '')).strip()
                        if symbol:
                            result = {
                                'symbol': symbol,
                                'market': 'japan',
                                'piotroski': row.get('piotroski') or row.get('f_score'),
                                'roce': row.get('roce'),
                                'fetched_at': datetime.utcnow().isoformat()
                            }
                            if result.get('piotroski') or result.get('roce'):
                                results.append(result)

                if results:
                    break
            except:
                pass

        if results:
            log.info(f"  ✅ Extracted: {len(results)} Japan symbols")
            self.extracted.extend(results)
        else:
            log.warning("  ⚠️  No Japan fundamentals found")

        return results

    def load_korea(self) -> list:
        """Load Korea fundamentals from factorial screener signals"""
        log.info("Loading Korea fundamentals...")

        results = []

        # factorial_screener_signals_KR_technical.parquet
        for parquet_file in self.dropbox.glob("**/*KR_technical.parquet"):
            if parquet_file.stat().st_size < 1_000_000:
                continue

            try:
                df = pd.read_parquet(parquet_file)
                log.info(f"  ✅ Found: {parquet_file.name} ({len(df):,} rows)")

                if 'ticker' in df.columns or 'symbol' in df.columns:
                    col = 'ticker' if 'ticker' in df.columns else 'symbol'
                    for _, row in df.head(1000).iterrows():
                        symbol = str(row.get(col, '')).strip()
                        if symbol:
                            result = {
                                'symbol': symbol,
                                'market': 'korea',
                                'piotroski': row.get('piotroski') or row.get('f_score'),
                                'roce': row.get('roce'),
                                'fetched_at': datetime.utcnow().isoformat()
                            }
                            if result.get('piotroski') or result.get('roce'):
                                results.append(result)

                if results:
                    break
            except:
                pass

        if results:
            log.info(f"  ✅ Extracted: {len(results)} Korea symbols")
            self.extracted.extend(results)
        else:
            log.warning("  ⚠️  No Korea fundamentals found")

        return results

    def generate_cql(self) -> str:
        """Generate CQL UPDATE statements"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        reports_dir = Path('/Users/umashankar/market-pipeline/code/python_files/reports')
        reports_dir.mkdir(exist_ok=True)

        cql_file = reports_dir / f'load_all_markets_fundamentals_{timestamp}.cql'

        with open(cql_file, 'w') as f:
            f.write("-- All Markets Fundamentals (Dropbox CSV/Parquet sources)\n")
            f.write(f"-- Generated: {datetime.now()}\n")
            f.write(f"-- Source: sweep_piotroski + factorial screener signals\n")
            f.write(f"-- Symbols: {len(self.extracted)}\n\n")

            for result in self.extracted:
                symbol = result['symbol']
                market = result['market']
                piotroski = result.get('piotroski') or 0
                roce = result.get('roce') or 0

                cql = f"""UPDATE herrrickshaw.stock_quotes SET piotroski = {piotroski}, roce = {roce}, fetched_at = toTimestamp(now()) WHERE market = '{market}' AND yf_ticker = '{symbol}';\n"""
                f.write(cql)

        return str(cql_file)

    def load(self):
        """Main workflow"""
        log.info("=" * 80)
        log.info("DROPBOX MULTI-MARKET FUNDAMENTALS LOADER")
        log.info("=" * 80)
        log.info("")

        # Load all markets
        self.load_us()
        self.load_europe()
        self.load_japan()
        self.load_korea()

        log.info("")
        log.info(f"Total extracted: {len(self.extracted):,} symbols across all markets")
        log.info("")

        if self.extracted:
            cql_file = self.generate_cql()

            log.info("=" * 80)
            log.info("✅ READY TO LOAD TO CASSANDRA")
            log.info("=" * 80)
            log.info("")
            log.info(f"Load command:")
            log.info(f"  cqlsh -f {cql_file}")
            log.info("")
        else:
            log.error("No fundamentals found")


def main():
    loader = AllMarketsLoader()
    loader.load()


if __name__ == '__main__':
    main()
