#!/usr/bin/env python3
"""
EC2 EDGAR Results → Cassandra Loader
Converts edgar_us_ec2_*.json to CQL UPDATE statements.
"""
import json
import sys
from pathlib import Path

def create_cql_from_json(json_file: Path, output_cql: Path) -> int:
    """Load JSON EDGAR data and generate CQL statements."""
    
    try:
        with open(json_file) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {json_file} not found", file=sys.stderr)
        return 0
    
    cql_lines = ["-- US EDGAR EC2 Extraction Results", "-- Auto-generated CQL for Cassandra loading", ""]
    
    statements = 0
    for item in data.get('data', []):
        symbol = item.get('symbol')
        if not symbol or not item.get('pe'):
            continue
        
        pe = float(item.get('pe') or 0)
        pb = float(item.get('pb') or 0)
        roe = float(item.get('roe') or 0)
        de = float(item.get('debt_to_equity') or 0)
        opm = float(item.get('opm') or 0)
        mc = float(item.get('market_cap') or 0)
        dy = float(item.get('dividend_yield') or 0)
        
        cql = f"""UPDATE herrrickshaw.stock_quotes
SET pe = {pe}, pb = {pb}, roe = {roe}, debt_to_equity = {de},
    opm = {opm}, market_cap = {mc}, dividend_yield = {dy}, fetched_at = toTimestamp(now())
WHERE market = 'us' AND yf_ticker = '{symbol}';
"""
        cql_lines.append(cql)
        statements += 1
    
    with open(output_cql, 'w') as f:
        f.write('\n'.join(cql_lines))
    
    return statements

if __name__ == '__main__':
    input_file = Path('edgar_us_results.json')
    output_file = Path('edgar_us_ec2.cql')
    
    stmt_count = create_cql_from_json(input_file, output_file)
    print(f"✅ CQL generated: {output_file.name}")
    print(f"   Statements: {stmt_count}")
