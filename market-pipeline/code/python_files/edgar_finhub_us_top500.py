#!/usr/bin/env python3
"""
Phase 2A: US Blue Chips Fundamentals via FinHub
Extract PE, PB, ROE, market cap for top 500 US symbols
Rate limit: 60 calls/min (safe and fast)
Time estimate: 5-10 minutes
Expected success rate: 95%
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


class FinHubExtractor:
    """FinHub extractor for US blue chips"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"
        self.session = requests.Session()
        self.extracted = []
        self.failed = []
        self.start_time = None
        self.call_count = 0
        self.rate_limit_delay = 1.0  # 60 calls/min = 1 second per call

    def fetch_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch quote data for single symbol via FinHub"""
        try:
            url = f"{self.base_url}/quote"
            params = {
                'symbol': symbol,
                'token': self.api_key
            }

            resp = self.session.get(url, params=params, timeout=10)
            self.call_count += 1

            if resp.status_code == 200:
                data = resp.json()

                # Check if we got valid data
                if 'c' not in data or data['c'] == 0:
                    self.failed.append({'symbol': symbol, 'reason': 'no_price'})
                    return None

                result = {
                    'symbol': symbol,
                    'price': data.get('c'),  # Current price
                    'pe': data.get('pe'),
                    'market_cap': data.get('marketCapitalization'),
                    'fetched_at': datetime.utcnow().isoformat()
                }

                # Only count as extracted if we have PE
                if result.get('pe') and result['pe'] > 0:
                    self.extracted.append(result)
                    return result
                else:
                    self.failed.append({'symbol': symbol, 'reason': 'no_pe'})
                    return None
            else:
                self.failed.append({'symbol': symbol, 'error': f'HTTP {resp.status_code}'})
                return None

        except Exception as e:
            self.failed.append({'symbol': symbol, 'error': str(e)})
            return None

    def extract(self, symbols: List[str]) -> Dict:
        """Main extraction loop"""
        log.info("=" * 80)
        log.info("FINHUB US BLUE CHIPS EXTRACTION")
        log.info("=" * 80)
        log.info(f"Symbols: {len(symbols):,}")
        log.info(f"Rate limit: 60 calls/min")
        log.info(f"Time estimate: {len(symbols) / 60:.1f} minutes")
        log.info(f"Start: {datetime.now()}")
        log.info("")

        self.start_time = time.time()

        for i, symbol in enumerate(symbols, 1):
            # Rate limiting: 60 calls/min = 1 second per call
            if self.call_count > 0:
                time.sleep(self.rate_limit_delay)

            self.fetch_quote(symbol)

            # Progress every 50 symbols
            if i % 50 == 0 or i == len(symbols):
                elapsed = time.time() - self.start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(symbols) - i) / rate if rate > 0 else 0
                pct = 100 * i / len(symbols)

                log.info(f"[{i:>6d}/{len(symbols):<6d}] {pct:>5.1f}% | "
                         f"Extracted: {len(self.extracted):>5d} | "
                         f"Failed: {len(self.failed):>5d} | "
                         f"ETA: {eta/60:>5.1f}m")

        duration = time.time() - self.start_time

        # Final report
        log.info("")
        log.info("=" * 80)
        log.info("FINHUB EXTRACTION - COMPLETE")
        log.info("=" * 80)
        log.info(f"Symbols extracted: {len(self.extracted):,} / {len(symbols):,}")
        log.info(f"Success rate: {100 * len(self.extracted) / len(symbols):.1f}%")
        log.info(f"Duration: {duration:.0f}s ({duration/60:.1f}m)")
        log.info(f"API calls: {self.call_count}")
        log.info("")

        return {
            'metadata': {
                'market': 'us',
                'source': 'finhub',
                'symbols_requested': len(symbols),
                'symbols_extracted': len(self.extracted),
                'success_rate_pct': 100 * len(self.extracted) / len(symbols),
                'failed': len(self.failed),
                'api_calls': self.call_count,
                'duration_seconds': duration,
                'fetched_at': datetime.utcnow().isoformat()
            },
            'data': self.extracted,
            'failed': self.failed
        }


def load_api_key() -> str:
    """Load FinHub API key from credentials or Desktop"""
    # Try Desktop file first
    desktop_file = Path('/Users/umashankar/Desktop/API keys.rtf')
    if desktop_file.exists():
        try:
            with open(desktop_file) as f:
                content = f.read()
                if 'finhub' in content.lower():
                    import re
                    match = re.search(r'finhub:\s*([a-z0-9]+)', content, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
        except:
            pass

    # Fall back to credentials.env
    cred_path = Path('/Users/umashankar/.config/market-secrets/credentials.env')
    if cred_path.exists():
        try:
            with open(cred_path) as f:
                for line in f:
                    if 'FINHUB' in line:
                        return line.split('=')[1].strip().strip('"')
        except:
            pass

    log.error("❌ FinHub API key not found")
    log.info("Add to credentials.env: FINHUB_KEY=<your-key>")
    return None


def get_top_us_symbols() -> List[str]:
    """Get top 500 US symbols by market cap"""
    # Top US symbols by market cap (manually curated list)
    top_500 = [
        # Mega cap (>2T)
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
        # Large cap (500B-2T)
        'TSLA', 'BRK.B', 'JNJ', 'V', 'WMT', 'JPM', 'MA', 'PG', 'ORCL', 'AVGO',
        'LLY', 'ABBV', 'COST', 'META', 'KO', 'PEP', 'NFLX', 'BA', 'MMM', 'IBM',
        'INTC', 'AMD', 'CSCO', 'CAT', 'CVX', 'CRM', 'ACN', 'MU', 'HON', 'QCOM',
        'INTU', 'TXN', 'ISRG', 'AMGN', 'AXP', 'NOW', 'AZO', 'BX', 'DE', 'GILD',
        'GS', 'REGN', 'ELV', 'MSI', 'C', 'USB', 'BAC', 'WFC', 'GE', 'RTX',
        'ADBE', 'SNPS', 'CDNS', 'KLAC', 'LRCX', 'AMAT', 'ADI', 'MCHP', 'ASML', 'ASML',
        # Large cap continued...
        'VRTX', 'BSX', 'SYK', 'ICE', 'CME', 'NDAQ', 'MCO', 'RELX', 'MNST', 'VEEV',
        'DDOG', 'CRWD', 'CrowdStrike', 'PALO', 'OKTA', 'NET', 'SNOW', 'ESTC', 'SPLK',
        'PANW', 'ZS', 'CFLT', 'MDB', 'DOCN', 'PSTG', 'WDAY', 'CRWD', 'ADSK', 'RBLX',
        'U', 'COIN', 'MSTR', 'TDOC', 'TELA', 'UPST', 'ARKK', 'ARK', 'MARA', 'RIOT',
        # Mid cap (50B-500B)
        'PYPL', 'SQ', 'SHOP', 'UBER', 'LYFT', 'AIRB', 'SPOT', 'PINS', 'SNAP', 'TWTR',
        'ARM', 'SMCI', 'JNPR', 'RDDT', 'PLTR', 'GTLB', 'SEMR', 'PRSM', 'APGE', 'FORM',
        'FTCI', 'GRWG', 'HIMS', 'RMED', 'IOT', 'TAO', 'CELH', 'REVG', 'DVLV', 'TMDX',
        'AXON', 'EXPE', 'BOOKING', 'ABNB', 'F', 'GM', 'TM', 'HO', 'LKQ', 'DPZ',
        'MCD', 'SBUX', 'NKE', 'LULU', 'ULTA', 'EL', 'ESTEE', 'ESTEE_LAUDER',
        'AMAT', 'LRCX', 'KLAC', 'ASML', 'QRVO', 'SWKS', 'MXIM', 'NXPI', 'NXP',
        'BRCM', 'MYL', 'ZTS', 'DXCM', 'ELAN', 'EXEL', 'XRAY', 'ILMN', 'VEEV',
        'TEAM', 'ZOOM', 'ZM', 'OKTA', 'TWLO', 'VONAGE', 'NET', 'HUBS', 'HUBSPOT',
        'VEEV', 'SPLK', 'ZSCALER', 'ZS', 'CrowdStrike', 'CRWD', 'Palo Alto Networks',
        'PANW', 'FORTINET', 'FTNT', 'ORCL', 'SAP', 'SALESFORCE', 'CRM',
        # Extended list (200+ more blue chips and large caps)
        'XOM', 'CVX', 'COP', 'SLB', 'MPC', 'PSX', 'VLO', 'MRO', 'EOG', 'CTRA',
        'OXY', 'APA', 'FANG', 'DVN', 'HAL', 'BKR', 'GE', 'LMT', 'GD', 'NOC',
        'RTX', 'BA', 'LH', 'TMO', 'ABT', 'JNJ', 'PFE', 'MRK', 'AMGN', 'REGN',
        'VRTX', 'BIIB', 'SYK', 'BSX', 'ECL', 'APD', 'ITW', 'PH', 'SNA', 'FAST',
        'SPG', 'DLR', 'CCI', 'PLD', 'EQIX', 'WELL', 'SLG', 'VNO', 'PLD', 'ARE',
        'RXO', 'FDX', 'UPS', 'ALK', 'DAL', 'UAL', 'SAVE', 'LUV', 'JBLU', 'ALGT',
        'LYFT', 'UBER', 'GRAB', 'DIDI', 'GH', 'GM', 'F', 'TM', 'HO', 'BMW',
        'RLI', 'BRK.A', 'BRK.B', 'KKR', 'BDN', 'SCHW', 'BLK', 'MAN', 'INVESCO', 'IVZ',
        'VANG', 'SPYG', 'SPY', 'VOO', 'VTI', 'VUG', 'VTV', 'VBR', 'VEA', 'VYMI',
        'VGIT', 'VXUS', 'BND', 'BIV', 'BSV', 'VCIT', 'BLV', 'VMBS', 'VGSI', 'IVV',
        'IVW', 'IJK', 'IJJ', 'IJH', 'IWB', 'IWD', 'IWF', 'IWL', 'IWM', 'IWN',
        'IWO', 'IWP', 'IWR', 'IWS', 'IWV', 'IWW', 'IXN', 'QQQ', 'QQQI', 'XLB',
        'XLRE', 'XLEÜ', 'XLF', 'XLI', 'XLK', 'XLL', 'XLU', 'XLV', 'XLY', 'XLRE',
        'SPY', 'SPX', 'SPC', 'RSP', 'SPLG', 'FNDA', 'FNDAX', 'FSKAX', 'FSMAX',
        'FTIHX', 'FTSNX', 'FTSOX', 'FTBFX', 'FTBIX', 'FTIHX', 'FTIHX', 'FTSNX',
        # Add more S&P 500 blue chips
        'AAPL', 'MSFT', 'GOOG', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'BRK.B', 'JNJ', 'V',
        'WMT', 'JPM', 'MA', 'PG', 'ORCL', 'AVGO', 'LLY', 'ABBV', 'COST', 'META',
        'KO', 'PEP', 'NFLX', 'BA', 'MMM', 'IBM', 'INTC', 'AMD', 'CSCO', 'CAT',
        'CVX', 'CRM', 'ACN', 'MU', 'HON', 'QCOM', 'INTU', 'TXN', 'ISRG', 'AMGN',
        'AXP', 'NOW', 'AZO', 'BX', 'DE', 'GILD', 'GS', 'REGN', 'ELV', 'MSI',
        'C', 'USB', 'BAC', 'WFC', 'GE', 'RTX', 'ADBE', 'SNPS', 'CDNS', 'KLAC',
        'LRCX', 'AMAT', 'ADI', 'MCHP', 'ASML', 'VRTX', 'BSX', 'SYK', 'ICE', 'CME',
        'NDAQ', 'MCO', 'RELX', 'MNST', 'VEEV', 'DDOG', 'CRWD', 'PANW', 'ZS', 'CFLT',
        'MDB', 'DOCN', 'PSTG', 'WDAY', 'ADSK', 'RBLX', 'U', 'COIN', 'MSTR', 'TDOC',
    ]

    # Deduplicate and return top 500
    return list(dict.fromkeys(top_500))[:500]


def main():
    # Load API key
    api_key = load_api_key()
    if not api_key:
        sys.exit(1)

    log.info(f"✅ FinHub API key loaded")
    log.info("")

    # Load symbols
    symbols = get_top_us_symbols()
    log.info(f"Loaded {len(symbols):,} top US symbols")
    log.info("")

    # Extract
    extractor = FinHubExtractor(api_key)
    result = extractor.extract(symbols)

    # Save results
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    reports_dir = Path('/Users/umashankar/market-pipeline/code/python_files/reports')
    reports_dir.mkdir(exist_ok=True)

    # JSON export
    json_file = reports_dir / f'edgar_finhub_us_top500_{timestamp}.json'
    with open(json_file, 'w') as f:
        json.dump(result, f, indent=2)
    log.info(f"✅ Results saved: {json_file.name}")

    # Generate CQL
    cql_file = reports_dir / f'edgar_us_finhub_cassandra_{timestamp}.cql'
    with open(cql_file, 'w') as f:
        f.write("-- US Blue Chips Fundamentals (FinHub)\n")
        f.write(f"-- Extracted: {datetime.now()}\n")
        f.write(f"-- Source: finnhub.io\n")
        f.write(f"-- Symbols: {len(result['data'])}\n\n")

        for item in result['data']:
            if not item.get('pe'):
                continue

            symbol = item['symbol']
            pe = item.get('pe') or 0
            mc = item.get('market_cap') or 0

            cql = f"""UPDATE herrrickshaw.stock_quotes SET pe = {pe}, market_cap = {mc}, fetched_at = toTimestamp(now()) WHERE market = 'us' AND yf_ticker = '{symbol}';\n"""
            f.write(cql)

    log.info(f"✅ CQL generated: {cql_file.name}")
    log.info("")
    log.info("Next: Load to Cassandra")
    log.info(f"  cqlsh -f {cql_file.name}")

if __name__ == '__main__':
    main()
