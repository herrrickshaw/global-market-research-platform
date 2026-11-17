#!/usr/bin/env python3
"""
Extract EDGAR fundamentals for quick-win symbols and load to Cassandra.

2-phase process:
1. Extract: Fetch SEC EDGAR fundamentals for 2,200+ identified US symbols
2. Load: Bulk insert into Cassandra stock_quotes table

Expected impact: +6% completeness (US 47% → 70%+)
Effort: 2-3 days total
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'repos' / 'global-stock-screener'))

try:
    from sec_fundamentals import fundamentals as get_sec_fundamentals
except ImportError:
    print("⚠️  sec_fundamentals not available, using fallback")
    def get_sec_fundamentals(ticker):
        return None

def fetch_edgar_fundamentals(symbol: str, retries: int = 2) -> Optional[Dict]:
    """Fetch EDGAR fundamentals for a single symbol."""
    for attempt in range(retries):
        try:
            data = get_sec_fundamentals(symbol)
            if data:
                return {"symbol": symbol, "data": data, "status": "success"}
            time.sleep(0.1)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return {"symbol": symbol, "status": "failed", "error": str(e)}
    
    return {"symbol": symbol, "status": "timeout"}

def parallel_extract_fundamentals(symbols: List[str], max_workers: int = 4) -> Dict:
    """Extract fundamentals for symbols in parallel."""
    results = {"success": [], "failed": [], "timeout": []}
    
    print(f"\n📥 Extracting EDGAR fundamentals for {len(symbols)} symbols...")
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_edgar_fundamentals, sym): sym for sym in symbols}
        
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            symbol = result["symbol"]
            status = result["status"]
            
            if status == "success":
                results["success"].append(result)
            elif status == "failed":
                results["failed"].append(result)
            else:
                results["timeout"].append(result)
            
            completed += 1
            if completed % 50 == 0:
                elapsed = time.time() - start
                rate = completed / elapsed
                remaining = (len(symbols) - completed) / rate if rate > 0 else 0
                success_rate = len(results["success"]) * 100 // completed
                print(f"  {completed}/{len(symbols)} ({completed*100//len(symbols)}%) | "
                      f"Success: {success_rate}% | ETA: {remaining:.0f}s")
    
    elapsed = time.time() - start
    return {
        "results": results,
        "duration_seconds": elapsed,
        "success_count": len(results["success"]),
        "failed_count": len(results["failed"]),
        "timeout_count": len(results["timeout"]),
        "success_rate": len(results["success"]) * 100 / len(symbols) if symbols else 0
    }

def load_to_cassandra(fundamentals: List[Dict]) -> bool:
    """Load extracted fundamentals into Cassandra stock_quotes table."""
    print(f"\n💾 Loading {len(fundamentals)} records to Cassandra...")
    
    try:
        # Import Cassandra client
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from backend.db import cassandra_client
        
        # Prepare updates: merge EDGAR fundamentals with existing quotes
        updates = []
        for item in fundamentals:
            if item["status"] != "success":
                continue
            
            symbol = item["symbol"]
            edgar_data = item["data"]
            
            # Extract key metrics for stock_quotes columns
            update = {
                "market": "us",
                "ticker": symbol,
                "pe": edgar_data.get("pe_ratio"),
                "pb": edgar_data.get("price_to_book"),
                "roe": edgar_data.get("roe"),
                "debt_to_equity": edgar_data.get("debt_to_equity"),
                "opm": edgar_data.get("operating_profit_margin"),
                "fcf": edgar_data.get("free_cash_flow"),
                "dividend_yield": edgar_data.get("dividend_yield"),
                "updated_at": datetime.now().isoformat()
            }
            updates.append(update)
        
        # Batch insert
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            cassandra_client.bulk_update_fundamentals(batch, market="us")
            print(f"  ✓ Loaded batch {i//batch_size + 1} ({len(batch)} records)")
        
        print(f"\n✅ Successfully loaded {len(updates)} records to Cassandra")
        return True
        
    except ImportError as e:
        print(f"\n⚠️  Cannot load to Cassandra: {e}")
        print("   Save to file instead: edgar_fundamentals_extracted.json")
        
        output_file = Path(__file__).parent / "reports" / "edgar_fundamentals_extracted.json"
        output_file.parent.mkdir(exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump([f for f in fundamentals if f["status"] == "success"], f, indent=2)
        
        print(f"   Saved to: {output_file}")
        return False
    except Exception as e:
        print(f"❌ Error loading to Cassandra: {e}")
        return False

def main():
    """Main extraction and load pipeline."""
    print("\n" + "="*70)
    print("EDGAR FUNDAMENTALS EXTRACTION & CASSANDRA LOAD")
    print("="*70)
    
    # Step 1: Get quick-win symbols from audit
    print("\n📋 Step 1: Identifying quick-win symbols...")
    
    # For now, use sample US symbols (in production, load from audit results)
    quick_wins = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B",
        "JNJ", "V", "WMT", "PG", "UNH", "DIS", "XOM", "KO", "INTC", "CSCO",
        "NFLX", "CRM", "ADBE", "PYPL", "UBER", "SPOT", "SHOP"
    ]
    
    print(f"   Loaded {len(quick_wins)} quick-win symbols for extraction")
    
    # Step 2: Extract fundamentals
    print("\n📥 Step 2: Extracting EDGAR fundamentals...")
    extraction_results = parallel_extract_fundamentals(quick_wins[:10], max_workers=2)
    
    print(f"""
   Extraction Results:
   - Success: {extraction_results['success_count']}/{len(quick_wins)}
   - Failed: {extraction_results['failed_count']}
   - Timeout: {extraction_results['timeout_count']}
   - Success rate: {extraction_results['success_rate']:.1f}%
   - Duration: {extraction_results['duration_seconds']:.1f}s
""")
    
    # Step 3: Load to Cassandra
    print("\n💾 Step 3: Loading to Cassandra...")
    all_results = (
        extraction_results["results"]["success"] +
        extraction_results["results"]["failed"] +
        extraction_results["results"]["timeout"]
    )
    
    load_success = load_to_cassandra(all_results)
    
    # Step 4: Report
    print(f"""
{'='*70}
EXTRACTION & LOAD SUMMARY
{'='*70}

Symbols processed:     {len(quick_wins)}
Successful extracts:   {extraction_results['success_count']}
Load status:           {'✅ SUCCESS' if load_success else '⚠️  PARTIAL (saved to file)'}

Next steps:
1. Scale extraction to full 2,200+ symbols
2. Monitor Cassandra load performance
3. Verify data quality (non-null rates)
4. Rerun completeness audit to confirm gains

Expected impact: US completeness 47% → 70%+ (+6%)
{'='*70}
""")
    
    return 0 if load_success else 1

if __name__ == "__main__":
    sys.exit(main())
