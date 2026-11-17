#!/usr/bin/env python3
"""
US Commodity Trade & Export Analyzer

Identifies key US import/export products using EIA + US Census trade data,
maps to HS codes, and scores export suitability from major US ports.

Key commodities:
- Crude oil (HS 2709)
- Refined petroleum products (HS 2710, 2711)
- Natural gas (HS 2711)
- Coal (HS 2701)
- Liquified natural gas/LNG (HS 2711)
"""

import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import duckdb
from pathlib import Path

# Load credentials from consolidated credential store
def load_credentials():
    cred_file = Path.home() / ".config" / "market-secrets" / "credentials.env"
    creds = {}
    if cred_file.exists():
        with open(cred_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    creds[key.strip()] = val.strip().strip('"').strip("'")
    return creds

creds = load_credentials()

# EIA API Configuration
EIA_BASE_URL = "https://api.eia.gov/v2"
EIA_API_KEY = creds.get("EIA_API_KEY", "")
FRED_API_KEY = creds.get("FRED_API_KEY", "")

# US HS Code Commodity Mappings (4-6 digit HS codes)
HS_CODE_MAPPING = {
    # Energy Commodities
    "2701": {"name": "Coal", "category": "Energy", "type": "solid"},
    "2707": {"name": "Coal tar", "category": "Energy", "type": "byproduct"},
    "2709": {"name": "Crude oil", "category": "Energy", "type": "liquid"},
    "2710": {"name": "Refined petroleum products (gasoline, diesel, kerosene, fuel oil)", "category": "Energy", "type": "liquid"},
    "271011": {"name": "Petroleum oils, not crude", "category": "Energy", "type": "liquid"},
    "271012": {"name": "Light oils (gasoline/naphtha)", "category": "Energy", "type": "liquid"},
    "271019": {"name": "Other petroleum oils", "category": "Energy", "type": "liquid"},
    "2711": {"name": "Natural gas & LNG", "category": "Energy", "type": "gas"},

    # LNG Specific
    "271121": {"name": "Liquefied natural gas", "category": "Energy", "type": "gas"},

    # Chemicals from Petroleum
    "2712": {"name": "Petroleum coke", "category": "Energy", "type": "solid"},
    "2713": {"name": "Petroleum bitumen", "category": "Energy", "type": "solid"},

    # Base Metals (US exports)
    "2603": {"name": "Copper ore", "category": "Metals", "type": "solid"},
    "2614": {"name": "Molybdenum ore", "category": "Metals", "type": "solid"},
    "2818": {"name": "Aluminum oxide", "category": "Metals", "type": "solid"},
    "7601": {"name": "Aluminum unwrought", "category": "Metals", "type": "solid"},

    # Agricultural (US export strength)
    "1001": {"name": "Wheat", "category": "Agriculture", "type": "solid"},
    "1005": {"name": "Maize (corn)", "category": "Agriculture", "type": "solid"},
    "1201": {"name": "Soybeans", "category": "Agriculture", "type": "solid"},
    "2304": {"name": "Soybean meal", "category": "Agriculture", "type": "solid"},
}

# Major US Ports by Volume
US_PORTS = {
    "Port of Houston": {"state": "TX", "type": "deep-water", "capacity_20ft_teu": 46_000_000, "commodities": ["crude", "refined", "lng", "chemicals"]},
    "Port of Los Angeles": {"state": "CA", "type": "deep-water", "capacity_20ft_teu": 8_800_000, "commodities": ["containers", "autos", "coal"]},
    "Port of Long Beach": {"state": "CA", "type": "deep-water", "capacity_20ft_teu": 8_000_000, "commodities": ["containers", "autos"]},
    "Port of New York/New Jersey": {"state": "NJ", "type": "deep-water", "capacity_20ft_teu": 6_800_000, "commodities": ["containers", "general-cargo"]},
    "Port of Corpus Christi": {"state": "TX", "type": "deep-water", "capacity_20ft_teu": 3_600_000, "commodities": ["crude", "refined", "lng"]},
    "Port of Beaumont": {"state": "TX", "type": "inland", "capacity_20ft_teu": 2_500_000, "commodities": ["refined", "chemicals"]},
    "Port of Brownsville": {"state": "TX", "type": "deep-water", "capacity_20ft_teu": 1_500_000, "commodities": ["crude", "lng"]},
}


def fetch_fred_commodity_data(fred_series: str) -> pd.DataFrame:
    """Fetch commodity prices from FRED (more reliable than EIA for this purpose)."""
    params = {
        "series_id": fred_series,
        "api_key": FRED_API_KEY,
        "units": "lin",  # linear
        "frequency": "m",  # monthly
        "limit": 120,
    }

    try:
        response = requests.get("https://api.stlouisfed.org/fred/series/observations", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "observations" not in data:
            return pd.DataFrame()

        records = []
        for obs in data["observations"]:
            if obs.get("value") != ".":
                records.append({
                    "date": obs["date"],
                    "value": float(obs["value"]),
                    "series_id": fred_series
                })

        return pd.DataFrame(records)
    except Exception as e:
        print(f"⚠️ FRED API error for {fred_series}: {e}")
        return pd.DataFrame()


def fetch_eia_data(series_id: str, freq: str = "monthly") -> pd.DataFrame:
    """
    Fetch EIA API data for a specific series.

    Common series_ids:
    - SRUCRSP: Crude oil spot price (WTI) $/bbl
    - GASDESW: US gasoline sales (weekly)
    - DHHNGSP: Henry Hub natural gas spot price $/MMBtu
    - COAL.PRICE_N_USA_COALMINE.M: Coal prices
    - LNG export volumes
    """
    # Try FRED first (more reliable for commodity prices)
    fred_mapping = {
        "DHHNGSP": "MMNRNJ",  # Henry Hub Natural Gas Spot Price
        "SRUCRSP": "MCOILWTICO",  # WTI Crude Oil Spot Price
    }

    if series_id in fred_mapping:
        return fetch_fred_commodity_data(fred_mapping[series_id])

    params = {
        "series_ids": series_id,
        "frequency": freq,
        "limit": 500,
        "api_key": EIA_API_KEY,
    }

    try:
        response = requests.get(f"{EIA_BASE_URL}/series/{series_id}", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "response" not in data or "data" not in data["response"]:
            print(f"⚠️ No data for {series_id}")
            return pd.DataFrame()

        records = []
        for item in data["response"]["data"]:
            records.append({
                "date": item[0],
                "value": float(item[1]) if item[1] is not None else None,
                "series_id": series_id
            })

        return pd.DataFrame(records)
    except Exception as e:
        print(f"⚠️ EIA API error for {series_id}: {e}")
        return pd.DataFrame()


def get_key_us_commodities() -> Dict[str, Dict]:
    """
    Fetch key US export commodity data from EIA/FRED APIs.
    Returns: commodity -> {price, volume, trend, margin_opportunity}

    Fallback to 2024 market data if APIs fail.
    """
    commodities = {}

    # 1. Crude Oil (WTI)
    print("📊 Fetching WTI Crude Oil prices...")
    wti_data = fetch_eia_data("SRUCRSP")
    if not wti_data.empty:
        latest_price = wti_data.iloc[-1]["value"]
        price_30d = wti_data.tail(30)["value"].mean()
        commodities["Crude Oil (WTI)"] = {
            "hs_code": "2709",
            "current_price": latest_price,
            "price_avg_30d": price_30d,
            "unit": "USD/bbl",
            "export_strength": "Very High",
            "us_world_share": "~13% of global crude market",
        }
    else:
        # Fallback: ~Aug 2026 WTI ~$75/bbl
        commodities["Crude Oil (WTI)"] = {
            "hs_code": "2709",
            "current_price": 75.50,
            "price_avg_30d": 74.20,
            "unit": "USD/bbl",
            "export_strength": "Very High",
            "us_world_share": "~13% of global crude market",
            "_source": "fallback",
        }

    # 2. Refined Petroleum
    print("📊 Fetching Refined Petroleum data...")
    refined_data = fetch_eia_data("GASDESW")
    if not refined_data.empty:
        latest_vol = refined_data.iloc[-1]["value"]
        commodities["Refined Petroleum"] = {
            "hs_code": "2710",
            "current_volume": latest_vol,
            "unit": "thousand bbl/day",
            "export_strength": "Very High",
            "us_world_share": "~6-8% of global refined product exports",
            "products": ["Gasoline (HS 271012)", "Diesel (HS 271019)", "Fuel Oil", "Jet Fuel"],
        }
    else:
        # Fallback: ~3.5M bbl/day exports
        commodities["Refined Petroleum"] = {
            "hs_code": "2710",
            "current_volume": 3500,
            "unit": "thousand bbl/day",
            "export_strength": "Very High",
            "us_world_share": "~6-8% of global refined product exports",
            "products": ["Gasoline (HS 271012)", "Diesel (HS 271019)", "Fuel Oil", "Jet Fuel"],
            "_source": "fallback",
        }

    # 3. Natural Gas & LNG
    print("📊 Fetching Natural Gas & LNG data...")
    ng_data = fetch_eia_data("DHHNGSP")
    if not ng_data.empty:
        latest_price = ng_data.iloc[-1]["value"]
        commodities["LNG Exports"] = {
            "hs_code": "271121",
            "current_price": latest_price,
            "unit": "USD/MMBtu",
            "export_strength": "Very High",
            "us_world_share": "~15-20% of global LNG",
            "major_terminals": ["Sabine Pass (LA)", "Corpus Christi (TX)", "Freeport (TX)", "Cameron (LA)"],
        }
    else:
        # Fallback: ~$3.20/MMBtu (Aug 2026)
        commodities["LNG Exports"] = {
            "hs_code": "271121",
            "current_price": 3.20,
            "unit": "USD/MMBtu",
            "export_strength": "Very High",
            "us_world_share": "~15-20% of global LNG",
            "major_terminals": ["Sabine Pass (LA)", "Corpus Christi (TX)", "Freeport (TX)", "Cameron (LA)"],
            "_source": "fallback",
        }

    # 4. Coal
    print("📊 Fetching Coal data...")
    coal_data = fetch_eia_data("COAL.PRICE_N_USA_COALMINE.M")
    if not coal_data.empty:
        latest_price = coal_data.iloc[-1]["value"]
        commodities["Thermal Coal"] = {
            "hs_code": "2701",
            "current_price": latest_price,
            "unit": "USD/ton (coalmine)",
            "export_strength": "Medium-High",
            "us_world_share": "~2-3% of global coal market",
        }
    else:
        # Fallback: ~$55/ton thermal coal
        commodities["Thermal Coal"] = {
            "hs_code": "2701",
            "current_price": 55.00,
            "unit": "USD/ton (coalmine)",
            "export_strength": "Medium-High",
            "us_world_share": "~2-3% of global coal market",
            "_source": "fallback",
        }

    return commodities


def fetch_us_census_trade_data(hs_code: str) -> Dict:
    """
    Fetch US Census Bureau trade data for an HS code.
    Uses USA Trade Online API (public endpoint).

    Returns: import/export volumes, top trading partners, margins
    """
    # USA Trade Online public API endpoint
    url = "https://api.census.gov/data/timeseries/intl/trade/hs"

    params = {
        "get": "CTY_CODE,CTY_NAME,ALL_VAL_MO",  # Country code, name, value
        "for": f"hs:{hs_code}",  # HS code filter
        "time": "latest",
        "api_key": "",  # Census API can be used without key for basic queries
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if len(data) < 2:
            return {}

        # Parse response (first row is headers)
        headers = data[0]
        records = []
        for row in data[1:]:
            record = {headers[i]: row[i] for i in range(len(headers))}
            records.append(record)

        return {"hs_code": hs_code, "data": records}
    except Exception as e:
        print(f"⚠️ Census API error for HS {hs_code}: {e}")
        return {}


def score_export_suitability(commodity: str, hs_code: str, price: float,
                            volume: float, world_share: str) -> Dict:
    """
    Score export suitability on multiple dimensions:
    - Price volatility → margin opportunity
    - Global market share → competitive position
    - Port infrastructure → logistics feasibility
    - Transport mode → cost efficiency (tanker, container, bulk)
    """
    score = 0
    factors = {}

    # Factor 1: Global Market Position (0-30 pts)
    if "Very High" in world_share or "15-20%" in world_share or "13%" in world_share:
        market_score = 30
        factors["Market Position"] = f"30/30 ({world_share})"
    elif "6-8%" in world_share or "Medium-High" in world_share:
        market_score = 20
        factors["Market Position"] = f"20/30 ({world_share})"
    else:
        market_score = 10
        factors["Market Position"] = f"10/30 (Low)"
    score += market_score

    # Factor 2: Price Level & Trend (0-25 pts)
    # Higher commodity prices = better export margins
    if price and price > 50:  # $/bbl or $/MMBtu or $/ton
        price_score = 25
        factors["Price Level"] = f"25/25 (High: ${price:.2f})"
    elif price and price > 20:
        price_score = 15
        factors["Price Level"] = f"15/25 (Medium: ${price:.2f})"
    else:
        price_score = 5
        factors["Price Level"] = f"5/25 (Low)"
    score += price_score

    # Factor 3: Port Infrastructure Match (0-20 pts)
    port_score = 0
    matching_ports = [p for p, specs in US_PORTS.items()
                     if any(c in " ".join(specs["commodities"]) for c in
                           [hs_code[:4].lower(), "crude", "refined", "lng", "coal"])]
    if len(matching_ports) >= 3:
        port_score = 20
        factors["Port Infrastructure"] = f"20/20 ({len(matching_ports)} major ports)"
    elif len(matching_ports) > 0:
        port_score = 15
        factors["Port Infrastructure"] = f"15/20 ({len(matching_ports)} ports)"
    else:
        port_score = 5
        factors["Port Infrastructure"] = "5/20 (Limited)"
    score += port_score

    # Factor 4: Transport Efficiency (0-15 pts)
    # Tanker/bulk = lower per-unit cost; container = higher flexibility
    if hs_code in ["2709", "2710", "271121"]:  # Crude, refined, LNG = tanker-friendly
        transport_score = 15
        factors["Transport Mode"] = "15/15 (Tanker/Bulk optimized)"
    elif hs_code == "2701":  # Coal = bulk
        transport_score = 14
        factors["Transport Mode"] = "14/15 (Bulk cargo optimized)"
    else:
        transport_score = 10
        factors["Transport Mode"] = "10/15 (Container compatible)"
    score += transport_score

    # Factor 5: Export Diversification Opportunity (0-10 pts)
    # Can this product be re-exported to multiple regions?
    export_score = 8
    factors["Export Reach"] = "8/10 (Multi-region demand)"
    score += export_score

    overall_suitability = "Excellent" if score >= 85 else "Good" if score >= 70 else "Fair" if score >= 50 else "Poor"

    return {
        "commodity": commodity,
        "hs_code": hs_code,
        "total_score": score,
        "suitability": overall_suitability,
        "factors": factors,
        "price_usd": price,
        "volume": volume,
    }


def analyze_port_specialization() -> pd.DataFrame:
    """
    Map US ports to commodity specialization and throughput capacity.
    """
    port_data = []
    for port, specs in US_PORTS.items():
        port_data.append({
            "Port": port,
            "State": specs["state"],
            "Type": specs["type"],
            "TEU Capacity": specs["capacity_20ft_teu"],
            "Commodities": ", ".join(specs["commodities"]),
            "Best For": "Energy" if any(c in specs["commodities"] for c in ["crude", "refined", "lng"])
                       else "General Cargo" if "containers" in specs["commodities"]
                       else "Bulk/Coal",
        })

    return pd.DataFrame(port_data)


def build_export_matrix() -> pd.DataFrame:
    """
    Build a comprehensive export opportunity matrix:
    - Commodity x Port specialization
    - Margin opportunity scoring
    - Logistics feasibility
    """
    commodities = get_key_us_commodities()
    results = []

    if not commodities:
        print("⚠️ No commodities fetched, using fallback data...")
        return pd.DataFrame()

    for commodity, data in commodities.items():
        hs_code = data["hs_code"]
        price = data.get("current_price", data.get("current_volume", 0))
        volume = data.get("current_volume", 0)
        world_share = data.get("us_world_share", "Unknown")

        # Score this commodity
        scored = score_export_suitability(commodity, hs_code, price, volume, world_share)

        # Find best ports
        best_ports = [p for p, specs in US_PORTS.items()
                     if any(c in " ".join(specs["commodities"]) for c in [hs_code[:4], "crude", "refined", "lng", "coal"])]

        scored["Best Ports"] = ", ".join(best_ports[:2]) if best_ports else "General cargo ports"
        scored["World Market Share"] = world_share

        results.append(scored)

    if not results:
        print("⚠️ No results to build matrix...")
        return pd.DataFrame()

    df = pd.DataFrame(results)
    if "total_score" not in df.columns:
        return df
    return df.sort_values("total_score", ascending=False)


def export_to_duckdb(df: pd.DataFrame, table_name: str = "us_export_opportunities"):
    """Save analysis to DuckDB."""
    db_path = "/Users/umashankar/data/market_data.duckdb"
    conn = duckdb.connect(db_path)

    try:
        # Add analysis timestamp
        df["analysis_date"] = datetime.now().isoformat()

        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        print(f"✅ Exported to {table_name} in {db_path}")

        # Verify
        result = conn.execute(f"SELECT COUNT(*) as row_count FROM {table_name}").fetchall()
        print(f"   Rows: {result[0][0]}")
    finally:
        conn.close()


def main():
    print("🚀 US Commodity Export Analyzer")
    print("=" * 80)

    # 1. Get key commodities & EIA data
    print("\n[1/4] Fetching EIA commodity data...")
    commodities = get_key_us_commodities()
    print(f"✅ Retrieved {len(commodities)} commodities")

    # 2. Build export matrix
    print("\n[2/4] Building export opportunity matrix...")
    export_matrix = build_export_matrix()
    print("\n" + export_matrix.to_string())

    # 3. Analyze port specialization
    print("\n[3/4] Analyzing US port infrastructure...")
    port_analysis = analyze_port_specialization()
    print("\n" + port_analysis.to_string(index=False))

    # 4. Save to database
    print("\n[4/4] Saving to DuckDB...")
    export_to_duckdb(export_matrix)

    # Summary
    print("\n" + "=" * 80)
    print("🎯 TOP EXPORT OPPORTUNITIES:")
    top_3 = export_matrix.head(3)
    for idx, row in top_3.iterrows():
        print(f"\n{idx+1}. {row['commodity']} (HS {row['hs_code']})")
        print(f"   Score: {row['total_score']}/100 ({row['suitability']})")
        print(f"   Best Ports: {row['Best Ports']}")
        for factor, value in row['factors'].items():
            print(f"   → {factor}: {value}")

    return export_matrix, port_analysis


if __name__ == "__main__":
    export_matrix, port_analysis = main()
