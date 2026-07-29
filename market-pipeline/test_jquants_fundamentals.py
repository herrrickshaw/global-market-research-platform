#!/usr/bin/env python3
"""
Test J-Quants API for Japan fundamentals collection
J-Quants: Japanese market fundamentals, free tier, 1 req/sec
"""

import os
import requests
import json
from datetime import datetime

JQUANTS_API_KEY = os.getenv('JQUANTS_API_KEY', '')

def test_jquants():
    """Test J-Quants capabilities for our 20-column schema"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  J-QUANTS API FUNDAMENTALS TEST (Japan)                    ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")

    if not JQUANTS_API_KEY:
        print("❌ JQUANTS_API_KEY not found in environment")
        return

    print(f"✅ Using key: {JQUANTS_API_KEY[:20]}...")
    print("")

    # J-Quants API endpoints to test
    base_url = "https://api.jquants.com/v1"

    # Test 1: Authentication
    print("TEST 1: Authentication handshake...")
    try:
        headers = {'Authorization': f'Bearer {JQUANTS_API_KEY}'}
        resp = requests.get(f"{base_url}/listed", headers=headers, timeout=10)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Auth successful")
            print(f"  Response keys: {list(data.keys())}")
            if 'pagination' in data:
                print(f"  Pagination: {data['pagination']}")
        elif resp.status_code == 401:
            print(f"  ❌ Authentication failed: {resp.text[:200]}")
        else:
            print(f"  Status {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("TEST 2: Stock information endpoint...")
    try:
        headers = {'Authorization': f'Bearer {JQUANTS_API_KEY}'}
        # Toyota symbol: 7203
        resp = requests.get(f"{base_url}/listed/info?code=7203", headers=headers, timeout=10)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Stock info retrieved for 7203 (Toyota)")
            print(f"  Fields: {list(data.keys()) if isinstance(data, dict) else 'array'}")
            if isinstance(data, dict):
                print(f"  Sample: {json.dumps(data, indent=2)[:800]}...")
            elif isinstance(data, list) and len(data) > 0:
                print(f"  Sample: {json.dumps(data[0], indent=2)[:800]}...")
        else:
            print(f"  Error: {resp.text[:300]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("TEST 3: Fundamentals/Valuation endpoint...")
    try:
        headers = {'Authorization': f'Bearer {JQUANTS_API_KEY}'}
        resp = requests.get(f"{base_url}/stocks/valuation?code=7203", headers=headers, timeout=10)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Valuation data retrieved")
            print(f"  Fields: {list(data.keys()) if isinstance(data, dict) else 'check structure'}")
            if isinstance(data, dict):
                print(f"  Sample: {json.dumps(data, indent=2)[:1000]}...")
        else:
            print(f"  Error: {resp.text[:300]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("TEST 4: Fin statements endpoint...")
    try:
        headers = {'Authorization': f'Bearer {JQUANTS_API_KEY}'}
        resp = requests.get(f"{base_url}/stocks/fin_statements?code=7203", headers=headers, timeout=10)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Financial statements retrieved")
            if isinstance(data, dict):
                print(f"  Keys: {list(data.keys())}")
                for k, v in list(data.items())[:3]:
                    print(f"    {k}: {type(v).__name__}")
            print(f"  Sample: {json.dumps(data, indent=2, default=str)[:1200]}...")
        else:
            print(f"  Error: {resp.text[:300]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("TEST 5: Prices endpoint (for price-based metrics)...")
    try:
        headers = {'Authorization': f'Bearer {JQUANTS_API_KEY}'}
        resp = requests.get(f"{base_url}/prices?code=7203&pagination_token=2024-07-01", headers=headers, timeout=10)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ Price data retrieved")
            if 'data' in data and len(data['data']) > 0:
                sample = data['data'][0]
                print(f"  Fields: {list(sample.keys())}")
                print(f"  Sample: {json.dumps(sample, indent=2)[:600]}...")
        else:
            print(f"  Error: {resp.text[:300]}")
    except Exception as e:
        print(f"  ❌ Exception: {e}")

    print("")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  CONCLUSION                                                ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")
    print("If tests 2-5 pass, J-Quants is VIABLE for:")
    print("  ✓ PE, PB ratios")
    print("  ✓ ROE, ROA from fin statements")
    print("  ✓ Dividend yield")
    print("  ✓ Market cap, enterprise value")
    print("")
    print("Next: Build batch collector for 3,083 Japan symbols")

if __name__ == '__main__':
    test_jquants()
