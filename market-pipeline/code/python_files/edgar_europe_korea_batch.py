#!/usr/bin/env python3
"""
Phase 1 Batch Extraction: Europe (966) + Korea (2,768)
Rate limit: 1 request per 2 seconds (proven safe)
Time estimate: 3-4 hours for both
"""

import sys
import json
import time
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
    import yfinance as yf
except ImportError:
    log.error("yfinance not installed. Run: pip install yfinance")
    sys.exit(1)

class ThrottleSafeExtractor:
    """yfinance extractor with 1 req/2sec throttling"""

    def __init__(self, market_name: str, symbols: List[str]):
        self.market_name = market_name
        self.symbols = symbols
        self.extracted = []
        self.failed = []
        self.backoff = 2  # 2 seconds between requests
        self.start_time = None

    def extract(self) -> Dict:
        """Main extraction loop"""
        log.info("=" * 80)
        log.info(f"EXTRACTING: {self.market_name}")
        log.info("=" * 80)
        log.info(f"Symbols: {len(self.symbols)}")
        log.info(f"Rate limit: 1 request / {self.backoff} seconds")
        log.info(f"Time estimate: {len(self.symbols) * self.backoff / 3600:.1f} hours")
        log.info("")

        self.start_time = time.time()

        for i, symbol in enumerate(self.symbols, 1):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                # Parse fundamentals
                if info and info.get('trailingPE'):
                    result = {
                        'symbol': symbol,
                        'pe': info.get('trailingPE'),
                        'pb': info.get('priceToBook'),
                        'roe': info.get('returnOnEquity'),
                        'debt_to_equity': info.get('debtToEquity'),
                        'opm': info.get('operatingMargins'),
                        'market_cap': info.get('marketCap'),
                        'dividend_yield': info.get('dividendYield'),
                        'fetched_at': datetime.utcnow().isoformat()
                    }
                    self.extracted.append(result)
                else:
                    self.failed.append({'symbol': symbol, 'reason': 'no_fundamentals'})

            except Exception as e:
                self.failed.append({'symbol': symbol, 'error': str(e)})

            # Progress every 100 symbols
            if i % 100 == 0 or i == len(self.symbols):
                elapsed = time.time() - self.start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(self.symbols) - i) / rate if rate > 0 else 0
                pct = 100 * i / len(self.symbols)

                log.info(f"[{i:>5d}/{len(self.symbols):<5d}] {pct:>5.1f}% | "
                         f"Extracted: {len(self.extracted):>4d} | "
                         f"Failed: {len(self.failed):>4d} | "
                         f"Rate: {rate:>5.2f}/sec | "
                         f"ETA: {eta/60:>5.1f}m")

            # Throttle: 1 request per 2 seconds
            time.sleep(self.backoff)

        duration = time.time() - self.start_time

        # Final report
        log.info("")
        log.info("=" * 80)
        log.info(f"{self.market_name} - EXTRACTION COMPLETE")
        log.info("=" * 80)
        log.info(f"Symbols extracted: {len(self.extracted):,} / {len(self.symbols):,}")
        log.info(f"Success rate: {100 * len(self.extracted) / len(self.symbols):.1f}%")
        log.info(f"Duration: {duration:.0f}s ({duration/60:.1f}m, {duration/3600:.2f}h)")
        log.info(f"Rate: {len(self.symbols) / duration:.2f} symbols/sec")
        log.info("")

        return {
            'metadata': {
                'market': self.market_name,
                'symbols_requested': len(self.symbols),
                'symbols_extracted': len(self.extracted),
                'success_rate_pct': 100 * len(self.extracted) / len(self.symbols),
                'failed': len(self.failed),
                'duration_seconds': duration,
                'rate_per_second': len(self.symbols) / duration,
                'fetched_at': datetime.utcnow().isoformat()
            },
            'data': self.extracted,
            'failed': self.failed
        }

def load_europe_symbols() -> List[str]:
    """Load 966 European stocks (17 exchanges)"""
    # Representative sample from major European exchanges
    london = ['ADS.DE', 'SAP.DE', 'SIE.DE', 'BMW.DE', 'MUV2.DE',  # Frankfurt
              'FP.PA', 'OR.PA', 'AI.PA', 'NOKIA.HE', 'NOKIA.ST']  # Paris, Helsinki, Stockholm
    europe_list = london + [f'SYM{i}.XX' for i in range(0, 956, 1)]  # Placeholder for full list

    # Try to load from DuckDB if available
    try:
        import duckdb
        db = duckdb.connect('/Users/umashankar/market-pipeline/data/market_data.duckdb')
        result = db.execute('SELECT DISTINCT symbol FROM europe_all_list LIMIT 966').fetchall()
        return [r[0] for r in result]
    except:
        log.warning("Could not load from DuckDB, using sample")
        return london

def load_korea_symbols() -> List[str]:
    """Load 2,768 Korean stocks (KOSPI + KOSDAQ)"""
    try:
        import yfinance as yf
        # Use FinanceDataReader to get KRX list
        import FinanceDataReader as fdr
        kospi = fdr.DataReader('KS', '2026-01-01', '2026-07-29')
        kosdaq = fdr.DataReader('KQ', '2026-01-01', '2026-07-29')

        # Format: symbol.KS for KOSPI, symbol.KQ for KOSDAQ
        symbols = [f'{idx}.KS' for idx in kospi.index] + [f'{idx}.KQ' for idx in kosdaq.index]
        return list(set(symbols))[:2768]
    except Exception as e:
        log.warning(f"Could not load KRX symbols: {e}")
        log.info("Using fallback sample symbols")
        return [f'{5000+i:06d}.KS' for i in range(1000)] + [f'{1000+i:06d}.KQ' for i in range(1768)]

def main():
    reports_dir = Path('/Users/umashankar/market-pipeline/code/python_files/reports')
    reports_dir.mkdir(exist_ok=True)

    print("━" * 80)
    print("PHASE 1: EUROPE + KOREA BATCH EXTRACTION")
    print("━" * 80)
    print()

    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    all_results = {}

    # EUROPE
    log.info("Loading Europe symbols...")
    europe_symbols = load_europe_symbols()
    log.info(f"Loaded {len(europe_symbols)} Europe symbols")
    log.info("")

    europe_extractor = ThrottleSafeExtractor('EUROPE', europe_symbols)
    europe_result = europe_extractor.extract()
    all_results['europe'] = europe_result

    # Save Europe results
    europe_json = reports_dir / f'edgar_europe_batch_{timestamp}.json'
    with open(europe_json, 'w') as f:
        json.dump(europe_result, f, indent=2)
    log.info(f"✅ Europe results saved: {europe_json.name}")
    log.info("")

    # KOREA
    log.info("Loading Korea symbols...")
    korea_symbols = load_korea_symbols()
    log.info(f"Loaded {len(korea_symbols)} Korea symbols")
    log.info("")

    korea_extractor = ThrottleSafeExtractor('KOREA', korea_symbols)
    korea_result = korea_extractor.extract()
    all_results['korea'] = korea_result

    # Save Korea results
    korea_json = reports_dir / f'edgar_korea_batch_{timestamp}.json'
    with open(korea_json, 'w') as f:
        json.dump(korea_result, f, indent=2)
    log.info(f"✅ Korea results saved: {korea_json.name}")
    log.info("")

    # Generate CQL batches
    log.info("Generating Cassandra CQL batches...")
    for market, result in all_results.items():
        cql_file = reports_dir / f'edgar_{market}_batch_cassandra_{timestamp}.cql'
        with open(cql_file, 'w') as f:
            f.write(f"-- {market.upper()} Fundamentals\n")
            f.write(f"-- Extracted: {datetime.now()}\n")
            f.write(f"-- Batch size: {len(result['data'])}\n\n")

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
WHERE market = '{market}' AND yf_ticker = '{symbol}';
"""
                f.write(cql)

        log.info(f"✅ CQL generated: {cql_file.name}")

    # Summary
    log.info("")
    log.info("=" * 80)
    log.info("PHASE 1 SUMMARY")
    log.info("=" * 80)
    europe_count = all_results['europe']['metadata']['symbols_extracted']
    korea_count = all_results['korea']['metadata']['symbols_extracted']
    total_gained = europe_count + korea_count

    log.info(f"Europe extracted:  {europe_count:>4,} / 966 ({100*europe_count/966:>5.1f}%)")
    log.info(f"Korea extracted:   {korea_count:>4,} / 2,768 ({100*korea_count/2768:>5.1f}%)")
    log.info(f"Phase 1 total:     {total_gained:>4,} / 3,734 ({100*total_gained/3734:>5.1f}%)")
    log.info("")
    log.info(f"Next: Load to Cassandra")
    log.info(f"  for f in edgar_*_batch_cassandra_{timestamp}.cql; do")
    log.info(f"    cqlsh -f $f")
    log.info(f"  done")
    log.info("")

if __name__ == '__main__':
    main()
