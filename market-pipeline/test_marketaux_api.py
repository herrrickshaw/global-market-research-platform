#!/usr/bin/env python3
"""
Test MarketAux API for fundamentals data capability
"""

import os
import requests
import json

MARKETAUX_KEY = os.getenv('MARKETAUX_KEY', '')

def test_marketaux():
    """Test what MarketAux can provide"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  MARKETAUX API CAPABILITY TEST                             ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")

    if not MARKETAUX_KEY:
        print("❌ MARKETAUX_KEY not found in environment")
        return

    print(f"✅ Using key: {MARKETAUX_KEY[:20]}...")
    print("")

    # Test 1: Query with fundamentals
    print("TEST 1: Trying fundamentals endpoint...")
    try:
        url = "https://api.marketaux.com/v1/fundamentals"
        params = {
            'symbols': 'AAPL',
            'api_token': MARKETAUX_KEY
        }
        resp = requests.get(url, params=params, timeout=10)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response keys: {list(data.keys())}")
            if 'data' in data:
                print(f"  Data structure: {json.dumps(data['data'][:1], indent=2)[:500]}...")
        else:
            print(f"  Error: {resp.text[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

    print("")
    print("TEST 2: Entity query (generic)...")
    try:
        url = "https://api.marketaux.com/v1/entity/news"
        params = {
            'symbols': 'AAPL',
            'api_token': MARKETAUX_KEY
        }
        resp = requests.get(url, params=params, timeout=10)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response keys: {list(data.keys())}")
        else:
            print(f"  Error: {resp.text[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

    print("")
    print("TEST 3: Market moving endpoint (to see structure)...")
    try:
        url = "https://api.marketaux.com/v1/last_news"
        params = {
            'api_token': MARKETAUX_KEY,
            'limit': 5
        }
        resp = requests.get(url, params=params, timeout=10)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"  Response keys: {list(data.keys())}")
            if 'data' in data:
                print(f"  Sample: {json.dumps(data['data'][0], indent=2)[:600]}...")
        else:
            print(f"  Error: {resp.text[:200]}")
    except Exception as e:
        print(f"  Exception: {e}")

    print("")
    print("CONCLUSION: MarketAux appears to be a NEWS/SENTIMENT API, not fundamentals")

if __name__ == '__main__':
    test_marketaux()
