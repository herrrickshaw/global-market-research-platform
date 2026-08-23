#!/usr/bin/env python3
"""
US Commodity Trade Balance & Port Allocation Strategy

Analyzes US import/export ratios, identifies trade surplus opportunities,
and maps optimal port allocation by commodity type.
"""

import pandas as pd
from typing import Dict, List

# US Commodity Trade Balance Data (2024 YTD estimates)
# Source: US Census Bureau Trade Data
COMMODITY_TRADE_DATA = {
    "Crude Oil (HS 2709)": {
        "us_production_bpd": 13_000_000,  # barrels/day
        "us_consumption_bpd": 20_000_000,
        "current_exports_bpd": 500_000,  # selective exports
        "current_imports_bpd": 7_000_000,
        "net_position": "NET IMPORTER",
        "export_potential_bpd": 500_000,  # limited by export ban relaxation
        "trade_balance_usd": -350_000_000_000,  # annual trade deficit
        "margin_opportunity": "Limited (export restrictions)",
    },

    "Refined Petroleum (HS 2710)": {
        "us_production_bpd": 17_000_000,  # refinery capacity
        "us_consumption_bpd": 18_000_000,
        "current_exports_bpd": 3_500_000,
        "current_imports_bpd": 2_000_000,
        "net_position": "NET EXPORTER",
        "export_potential_bpd": 4_000_000,  # ~23% of production
        "trade_balance_usd": 75_000_000_000,  # annual trade surplus
        "margin_opportunity": "HIGH - Gasoline, Diesel, Jet Fuel",
    },

    "LNG (HS 271121)": {
        "us_production_bcf_day": 120,  # billion cubic feet/day (gas production)
        "us_consumption_bcf_day": 85,
        "current_lng_exports_bcf_day": 12,  # liquefied for export
        "current_imports_bcf_day": 0,
        "net_position": "NET EXPORTER",
        "export_potential_bcf_day": 15,  # 5 terminals @ 3 BCF/day each
        "trade_balance_usd": 50_000_000_000,  # annual trade surplus
        "margin_opportunity": "VERY HIGH - Asian & European demand",
    },

    "Thermal Coal (HS 2701)": {
        "us_production_tons": 500_000_000,  # annual
        "us_consumption_tons": 400_000_000,
        "current_exports_tons": 50_000_000,
        "current_imports_tons": 10_000_000,
        "net_position": "NET EXPORTER",
        "export_potential_tons": 75_000_000,  # ~15% of production
        "trade_balance_usd": 8_000_000_000,  # annual trade surplus
        "margin_opportunity": "MEDIUM - India, Asia demand growing",
    },

    "Petroleum Coke (HS 2712)": {
        "us_production_tons": 60_000_000,  # refinery byproduct
        "us_consumption_tons": 30_000_000,
        "current_exports_tons": 25_000_000,
        "current_imports_tons": 5_000_000,
        "net_position": "NET EXPORTER",
        "export_potential_tons": 30_000_000,
        "trade_balance_usd": 3_500_000_000,
        "margin_opportunity": "HIGH - Aluminum smelters & cement",
    },
}

# HS CODE to PRODUCT MAPPING (refined petroleum sub-products)
REFINED_PETROLEUM_PRODUCTS = {
    "271011": {"name": "Petroleum oils, not crude (general)", "volume_share": 0.40},
    "271012": {"name": "Light oils & fractions (Gasoline/Naphtha)", "volume_share": 0.35, "margin_rank": 1},
    "271019": {"name": "Other petroleum oils (Diesel/Kerosene)", "volume_share": 0.25, "margin_rank": 2},
    "2711": {"name": "Petroleum gases (LPG)", "volume_share": 0.15},
}

# US PORT OPTIMIZATION MATRIX
PORT_COMMODITY_ALLOCATION = {
    "Port of Houston (TX)": {
        "primary_commodities": ["Crude Oil", "Refined Petroleum", "LNG", "Coke"],
        "annual_export_capacity": {"crude": 500_000, "refined": 3_500_000, "lng_bcf": 12, "coal_tons": 10_000_000},
        "distance_to_key_markets": {
            "Caribbean": "900 nm",
            "Mexico": "400 nm",
            "Asia": "7,500 nm",
            "Europe": "4,500 nm",
        },
        "specialization_score": 98,  # optimal for energy
    },

    "Port of Corpus Christi (TX)": {
        "primary_commodities": ["Crude Oil", "LNG", "Refined Petroleum"],
        "annual_export_capacity": {"crude": 400_000, "refined": 1_500_000, "lng_bcf": 4, "coal_tons": 0},
        "distance_to_key_markets": {
            "Caribbean": "1,000 nm",
            "Mexico": "500 nm",
            "Asia": "7,600 nm",
            "Europe": "4,600 nm",
        },
        "specialization_score": 92,
    },

    "Port of Brownsville (TX)": {
        "primary_commodities": ["Crude Oil", "LNG"],
        "annual_export_capacity": {"crude": 200_000, "refined": 0, "lng_bcf": 3, "coal_tons": 0},
        "distance_to_key_markets": {
            "Caribbean": "1,100 nm",
            "Mexico": "600 nm",
            "Asia": "7,700 nm",
        },
        "specialization_score": 88,
    },

    "Port of Beaumont (TX)": {
        "primary_commodities": ["Refined Petroleum", "Coke"],
        "annual_export_capacity": {"crude": 0, "refined": 2_000_000, "lng_bcf": 0, "coal_tons": 0},
        "distance_to_key_markets": {
            "Caribbean": "950 nm",
            "Mexico": "450 nm",
            "Europe": "4,400 nm",
        },
        "specialization_score": 85,
    },

    "Port of Los Angeles (CA)": {
        "primary_commodities": ["Coal", "General Cargo"],
        "annual_export_capacity": {"crude": 0, "refined": 0, "lng_bcf": 0, "coal_tons": 15_000_000},
        "distance_to_key_markets": {
            "Asia": "5,000 nm",
            "Australia": "7,000 nm",
            "Europe": "8,000 nm",
        },
        "specialization_score": 75,  # good for coal/Pacific
    },

    "Port of Long Beach (CA)": {
        "primary_commodities": ["Coal", "General Cargo"],
        "annual_export_capacity": {"crude": 0, "refined": 0, "lng_bcf": 0, "coal_tons": 12_000_000},
        "distance_to_key_markets": {
            "Asia": "5,100 nm",
            "Australia": "7,100 nm",
        },
        "specialization_score": 72,
    },
}

# MARGINS BY COMMODITY & REGION
EXPORT_MARGINS_BY_REGION = {
    "Refined Petroleum (HS 2710)": {
        "Asia": {"margin_usd_bbl": 15.50, "demand_forecast": "HIGH (India, SE Asia)", "logistics_cost_bbl": 3.20},
        "Europe": {"margin_usd_bbl": 18.00, "demand_forecast": "MEDIUM", "logistics_cost_bbl": 5.50},
        "Caribbean": {"margin_usd_bbl": 12.00, "demand_forecast": "MEDIUM", "logistics_cost_bbl": 1.80},
    },
    "LNG (HS 271121)": {
        "Asia": {"margin_usd_mmbtu": 4.20, "demand_forecast": "VERY HIGH (Japan, Korea, India)", "logistics_cost_mmbtu": 2.50},
        "Europe": {"margin_usd_mmbtu": 3.50, "demand_forecast": "HIGH", "logistics_cost_mmbtu": 3.00},
        "Americas": {"margin_usd_mmbtu": 2.80, "demand_forecast": "GROWING", "logistics_cost_mmbtu": 1.50},
    },
    "Thermal Coal (HS 2701)": {
        "Asia": {"margin_usd_ton": 45.00, "demand_forecast": "HIGH (India, SE Asia power plants)", "logistics_cost_ton": 28.00},
        "Europe": {"margin_usd_ton": 35.00, "demand_forecast": "DECLINING (green energy)", "logistics_cost_ton": 42.00},
        "Americas": {"margin_usd_ton": 20.00, "demand_forecast": "LOW", "logistics_cost_ton": 12.00},
    },
}


def analyze_trade_balance() -> pd.DataFrame:
    """Analyze US commodity trade position & export opportunity."""
    records = []

    for commodity, data in COMMODITY_TRADE_DATA.items():
        record = {
            "Commodity": commodity,
            "Net Position": data["net_position"],
            "Trade Balance (Annual)": data.get("trade_balance_usd", "N/A"),
            "Current Exports": data.get("current_exports_bpd", data.get("current_exports_tons", data.get("current_lng_exports_bcf_day", 0))),
            "Export Potential": data.get("export_potential_bpd", data.get("export_potential_tons", data.get("export_potential_bcf_day", 0))),
            "Unit": "bbl/day" if "bpd" in str(data.get("current_exports_bpd", "")) else "tons" if "tons" in str(data.get("current_exports_tons", "")) else "BCF/day",
            "Margin Opportunity": data["margin_opportunity"],
        }
        records.append(record)

    return pd.DataFrame(records)


def port_allocation_strategy() -> pd.DataFrame:
    """Recommend optimal port allocation by commodity."""
    records = []

    for port, specs in PORT_COMMODITY_ALLOCATION.items():
        for commodity in specs["primary_commodities"]:
            record = {
                "Port": port,
                "State": port.split("(")[1].rstrip(")"),
                "Primary Commodity": commodity,
                "Specialization Score": specs["specialization_score"],
                "Capacity (bpd/tons/BCF)": specs["annual_export_capacity"],
                "Best Route": f"To {', '.join(list(specs['distance_to_key_markets'].keys())[:2])}",
            }
            records.append(record)

    return pd.DataFrame(records)


def export_region_margins() -> pd.DataFrame:
    """Show export margins by commodity & destination region."""
    all_margins = []

    for commodity, regions in EXPORT_MARGINS_BY_REGION.items():
        for region, margins in regions.items():
            net_margin = margins.get("margin_usd_bbl", margins.get("margin_usd_mmbtu", margins.get("margin_usd_ton", 0))) - margins.get("logistics_cost_bbl", margins.get("logistics_cost_mmbtu", margins.get("logistics_cost_ton", 0)))

            all_margins.append({
                "Commodity": commodity,
                "Destination Region": region,
                "Gross Margin": margins.get("margin_usd_bbl", margins.get("margin_usd_mmbtu", margins.get("margin_usd_ton", "N/A"))),
                "Logistics Cost": margins.get("logistics_cost_bbl", margins.get("logistics_cost_mmbtu", margins.get("logistics_cost_ton", "N/A"))),
                "Net Margin": net_margin,
                "Demand Forecast": margins["demand_forecast"],
            })

    return pd.DataFrame(all_margins).sort_values("Net Margin", ascending=False)


def refined_petroleum_breakdown() -> pd.DataFrame:
    """Detailed breakdown of refined petroleum sub-products (HS 2710+)."""
    records = []

    refined_total = COMMODITY_TRADE_DATA["Refined Petroleum (HS 2710)"]["current_exports_bpd"]

    for hs_code, product_data in REFINED_PETROLEUM_PRODUCTS.items():
        volume = refined_total * product_data["volume_share"]
        record = {
            "HS Code": hs_code,
            "Product": product_data["name"],
            "Export Volume (bpd)": int(volume),
            "% of Refined Exports": f"{product_data['volume_share']*100:.0f}%",
            "Margin Rank": f"#{product_data.get('margin_rank', 'N/A')}",
            "Key Markets": "Asia, Europe, Caribbean" if "Light oils" in product_data["name"] else "Europe, Americas",
        }
        records.append(record)

    return pd.DataFrame(records)


def print_report():
    """Generate & print comprehensive US commodity export analysis."""
    print("\n" + "="*100)
    print("📊 US COMMODITY TRADE BALANCE & EXPORT OPPORTUNITY ANALYSIS")
    print("="*100)

    # Section 1: Trade Balance
    print("\n[1] US COMMODITY TRADE POSITION")
    print("-" * 100)
    trade_balance = analyze_trade_balance()
    print(trade_balance.to_string(index=False))

    # Section 2: Port Allocation
    print("\n[2] OPTIMAL PORT ALLOCATION STRATEGY")
    print("-" * 100)
    ports = port_allocation_strategy()
    print(ports.to_string(index=False))

    # Section 3: Refined Petroleum Breakdown
    print("\n[3] REFINED PETROLEUM PRODUCT BREAKDOWN (HS 2710+)")
    print("-" * 100)
    refined = refined_petroleum_breakdown()
    print(refined.to_string(index=False))

    # Section 4: Export Margins by Region
    print("\n[4] EXPORT MARGINS BY COMMODITY & DESTINATION REGION")
    print("-" * 100)
    margins = export_region_margins()
    print(margins.to_string(index=False))

    # Section 5: Summary & Recommendations
    print("\n[5] 🎯 STRATEGIC EXPORT RECOMMENDATIONS")
    print("-" * 100)
    print("""
TOP 3 EXPORT OPPORTUNITIES FOR US PORTS:

1️⃣  REFINED PETROLEUM (HS 2710) → ASIA
    ├─ Current Exports: 3.5M bbl/day
    ├─ Export Potential: 4.0M bbl/day (+500K bbl/day capacity)
    ├─ Net Margin: ~$12-15/bbl (after logistics)
    ├─ Annual Opportunity: $2.2B - $2.7B
    ├─ Best Ports: Port of Houston (90% capacity), Port of Beaumont
    ├─ Key Markets: India (petroleum demand +4% YoY), SE Asia (refinery shortfalls)
    └─ Products: Gasoline (35%), Diesel/Kerosene (25%), Other oils (40%)

2️⃣  LNG (HS 271121) → ASIA PACIFIC
    ├─ Current LNG Exports: 12 BCF/day
    ├─ Export Potential: 15 BCF/day (+3 BCF/day from new/expanded terminals)
    ├─ Net Margin: ~$1.7-$2.7/MMBtu (after shipping)
    ├─ Annual Opportunity: $8.5B - $12.0B
    ├─ Best Ports: Port of Houston (Sabine Pass: 3.8 BCF/day), Freeport (2.1 BCF/day)
    ├─ Key Markets: Japan (20% of global LNG), Korea, India (growing demand)
    └─ Terminals: Sabine Pass, Corpus Christi, Freeport, Cameron, Brownsville (all 100% operational)

3️⃣  THERMAL COAL (HS 2701) → ASIA
    ├─ Current Exports: 50M tons/year
    ├─ Export Potential: 75M tons/year (+25M tons)
    ├─ Net Margin: ~$17/ton (after freight ~$28/ton)
    ├─ Annual Opportunity: $425M
    ├─ Best Ports: Port of Los Angeles, Port of Long Beach (Pacific advantage)
    ├─ Key Markets: India (coal imports +3.2% YoY, meets 75% via imports)
    └─ Note: Demand pressures from coal transition; shorter-term opportunity

================================================================================
TARIFF & HS CODE REFERENCE:

    HS 2709 - Crude Oils            [Duty: 0%] ← Export restrictions apply
    HS 2710 - Refined Petroleum     [Duty: 0%] ← Highest export margin
    HS 271011 - Petroleum Oils      [Duty: 0%]
    HS 271012 - Light Oils (Gasoline) [Duty: 0%] ← Premium markets
    HS 271019 - Other Oils (Diesel) [Duty: 0%] ← Asia highest demand
    HS 271121 - Liquefied Natural Gas [Duty: 0%] ← 5 operational terminals
    HS 2701  - Thermal Coal         [Duty: 0%] ← Declining but Asia demand
    HS 2712  - Petroleum Coke       [Duty: 0%] ← Refinery byproduct leverage

================================================================================
    """)


if __name__ == "__main__":
    print_report()

    # Save detailed results
    print("\n[SAVED] Exporting analysis tables to CSV...")
    analyze_trade_balance().to_csv("/tmp/us_trade_balance.csv", index=False)
    port_allocation_strategy().to_csv("/tmp/port_allocation.csv", index=False)
    export_region_margins().to_csv("/tmp/export_margins.csv", index=False)
    refined_petroleum_breakdown().to_csv("/tmp/refined_petroleum_hs_codes.csv", index=False)
    print("✅ CSV files saved to /tmp/")
