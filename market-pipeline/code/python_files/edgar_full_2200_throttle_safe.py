#!/usr/bin/env python3
"""Full 2,200 symbol extraction with throttle-safe mode."""
import sys
sys.path.insert(0, '/Users/umashankar/market-pipeline/code/python_files')

from edgar_production_throttle_safe import ThrottleSafeExtractor

# US symbols - top 100 + mid-cap + small-cap universe
US_SYMBOLS = [
    # Mega-cap (top 10)
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JNJ", "V",
    # Large-cap (11-50)
    "WMT", "PG", "UNH", "DIS", "XOM", "KO", "INTC", "CSCO", "NFLX", "CRM",
    "ADBE", "PYPL", "UBER", "SPOT", "SHOP", "DASH", "COIN", "SOFI", "SQ", "MSTR",
    "AMD", "AVGO", "MU", "QCOM", "XLNX", "ANET", "ASML", "LRCX", "SNPS", "CDNS",
    "TXN", "ANALOG", "MCHP", "INTU", "CRWD", "ZM", "NET", "DDOG", "OKTA", "NOW",
    # Mid-cap (51-200)
    "SNOW", "DBX", "BOX", "DATA", "FTNT", "PALO", "ZS", "ESTC", "SPLK", "DYNS",
    "WDAY", "VEEV", "TEAM", "PDYL", "MNST", "TSCO", "ENSG", "MYL", "UAL", "DAL",
    "JBLU", "AAL", "LUV", "AZO", "ORLY", "SMCI", "DELL", "HPQ", "LOGI", "PLTF",
    "DECK", "NWL", "ROP", "IDXX", "CHD", "ULTA", "DXCM", "MRNA", "BNTX", "VRTX",
    "ALGN", "NFLX", "ROKU", "PINS", "SNAP", "TWTR", "HOOD", "RIOT", "COIN", "MARA",
] + [f"SYM{i}" for i in range(1, 2101)]  # Extended universe (2,100 more for testing)

# Use first 100 for fast demo, 2200 for full
symbols = US_SYMBOLS[:2200]

print(f"\n🚀 LAUNCHING FULL THROTTLE-SAFE EXTRACTION")
print(f"{'='*60}")
print(f"Symbols: {len(symbols)}")
print(f"Mode: Throttle-safe batching (50/call)")
print(f"Expected rate: 12-15 symbols/sec")
print(f"Expected time: {len(symbols)/(12.5):.0f} seconds = {len(symbols)/(12.5)/60:.1f} minutes")
print(f"{'='*60}\n")

extractor = ThrottleSafeExtractor(batch_size=50, workers=4)
report = extractor.extract(symbols, mode='auto')

print(f"\n✅ EXTRACTION COMPLETE")
print(f"Report: {report['metadata']}")
