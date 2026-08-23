#!/usr/bin/env python3
"""
Test script for US Trade Export API endpoints
Runs all 7 endpoints and displays results
"""

import sys
sys.path.insert(0, '/Users/umashankar')

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers.us_trade_export_router import router

app = FastAPI()
app.include_router(router)

client = TestClient(app)

print("\n" + "="*100)
print("🧪 TESTING US TRADE EXPORT API ENDPOINTS")
print("="*100)

# Test 1: Opportunities
print("\n[1/7] GET /api/us-trade/opportunities")
print("-" * 100)
response = client.get("/api/us-trade/opportunities")
if response.status_code == 200:
    print("✅ Status: 200 OK")
    data = response.json()
    print(f"Opportunities found: {len(data['opportunities'])}")
    for opp in data['opportunities']:
        print(f"  - {opp['rank']}. {opp['commodity']} (Score: {opp['export_score']}/100)")
        print(f"    Annual Opportunity: {opp['annual_opportunity_usd']}")
else:
    print(f"❌ Status: {response.status_code}")
    print(response.text)

# Test 2: Commodities
print("\n[2/7] GET /api/us-trade/commodities")
print("-" * 100)
response = client.get("/api/us-trade/commodities")
if response.status_code == 200:
    print("✅ Status: 200 OK")
    data = response.json()
    print(f"Commodities found: {len(data['commodities'])}")
    for comm in data['commodities']:
        print(f"  - {comm['commodity']}: {comm['trade_position']}")
        print(f"    Trade Balance: ${comm['annual_trade_balance_usd']:,}")
else:
    print(f"❌ Status: {response.status_code}")

# Test 3: Ports
print("\n[3/7] GET /api/us-trade/ports")
print("-" * 100)
response = client.get("/api/us-trade/ports")
if response.status_code == 200:
    print("✅ Status: 200 OK")
    data = response.json()
    print(f"Ports found: {len(data['ports'])}")
    for port in data['ports'][:3]:
        print(f"  - {port['port']}: Score {port['specialization_score']}/100")
        print(f"    Commodities: {', '.join(port['primary_commodities'][:2])}")
else:
    print(f"❌ Status: {response.status_code}")

# Test 4: Margins - Refined Petroleum
print("\n[4/7] GET /api/us-trade/margins?commodity=2710")
print("-" * 100)
response = client.get("/api/us-trade/margins?commodity=2710")
if response.status_code == 200:
    print("✅ Status: 200 OK")
    data = response.json()
    print(f"Commodity: {data['commodity']} (HS {data['hs_code']})")
    print(f"Regions analyzed: {len(data['margins_by_region'])}")
    for margin in data['margins_by_region']:
        print(f"  - {margin['destination']}: {margin['net_margin']}/unit")
        print(f"    Demand: {margin['demand_forecast']}")
else:
    print(f"❌ Status: {response.status_code}")

# Test 5: Margins - LNG
print("\n[5/7] GET /api/us-trade/margins?commodity=271121")
print("-" * 100)
response = client.get("/api/us-trade/margins?commodity=271121")
if response.status_code == 200:
    print("✅ Status: 200 OK")
    data = response.json()
    print(f"Commodity: {data['commodity']} (HS {data['hs_code']})")
    top_margin = data['margins_by_region'][0]
    print(f"  Best Region: {top_margin['destination']} - ${top_margin['net_margin']}/MMBtu net")
else:
    print(f"❌ Status: {response.status_code}")

# Test 6: Refined Products
print("\n[6/7] GET /api/us-trade/refined-products")
print("-" * 100)
response = client.get("/api/us-trade/refined-products")
if response.status_code == 200:
    print("✅ Status: 200 OK")
    data = response.json()
    print(f"Parent HS Code: {data['hs_code_parent']}")
    print(f"Products: {len(data['products'])}")
    for prod in data['products']:
        print(f"  - HS {prod['hs_code']}: {prod['product_name']}")
        print(f"    Volume: {prod['export_volume_bpd']:,} bbl/day ({prod['percent_of_refined']})")
else:
    print(f"❌ Status: {response.status_code}")

# Test 7: Tariff Reference
print("\n[7/7] GET /api/us-trade/tariff-reference")
print("-" * 100)
response = client.get("/api/us-trade/tariff-reference")
if response.status_code == 200:
    print("✅ Status: 200 OK")
    data = response.json()
    print(f"Tariff System: {data['system']}")
    print(f"HS Codes available: {len(data['tariff_codes'])}")
    print(f"Note: {data['note']}")
else:
    print(f"❌ Status: {response.status_code}")

# Bonus: Summary
print("\n[BONUS] GET /api/us-trade/summary")
print("-" * 100)
response = client.get("/api/us-trade/summary")
if response.status_code == 200:
    print("✅ Status: 200 OK")
    data = response.json()
    summary = data['summary']
    print(f"Net Exporter Commodities: {', '.join(summary['us_trade_position']['net_exporter_commodities'][:2])}")
    print(f"Primary Export Value: {summary['us_trade_position']['primary_export_value']}")
    print(f"Top Ports by Energy: {summary['top_ports_by_energy'][0]['port']} (Score: {summary['top_ports_by_energy'][0]['score']}/100)")
else:
    print(f"❌ Status: {response.status_code}")

print("\n" + "="*100)
print("✅ ALL ENDPOINT TESTS COMPLETED")
print("="*100)
