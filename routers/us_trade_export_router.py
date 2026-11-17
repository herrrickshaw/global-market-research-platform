"""
US Commodity Trade & Export Analysis API Router

FastAPI endpoints for querying US commodity export opportunities,
trade balances, port specialization, and margin analysis.

Usage:
    GET /api/us-trade/opportunities          → Top export opportunities
    GET /api/us-trade/commodities            → Trade balance by commodity
    GET /api/us-trade/ports                  → Port specialization matrix
    GET /api/us-trade/margins?commodity=2710 → Export margins by region
    GET /api/us-trade/refined-products       → Refined petroleum HS code breakdown
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, List
import pandas as pd
from datetime import datetime

router = APIRouter(prefix="/api/us-trade", tags=["us-trade"])

# Load cached analysis data
TRADE_BALANCE_DATA = {
    "Crude Oil (HS 2709)": {
        "us_production_bpd": 13_000_000,
        "us_consumption_bpd": 20_000_000,
        "current_exports_bpd": 500_000,
        "current_imports_bpd": 7_000_000,
        "net_position": "NET IMPORTER",
        "export_potential_bpd": 500_000,
        "trade_balance_usd": -350_000_000_000,
        "margin_opportunity": "Limited (export restrictions)",
    },
    "Refined Petroleum (HS 2710)": {
        "us_production_bpd": 17_000_000,
        "us_consumption_bpd": 18_000_000,
        "current_exports_bpd": 3_500_000,
        "current_imports_bpd": 2_000_000,
        "net_position": "NET EXPORTER",
        "export_potential_bpd": 4_000_000,
        "trade_balance_usd": 75_000_000_000,
        "margin_opportunity": "HIGH - Gasoline, Diesel, Jet Fuel",
    },
    "LNG (HS 271121)": {
        "us_production_bcf_day": 120,
        "us_consumption_bcf_day": 85,
        "current_lng_exports_bcf_day": 12,
        "current_imports_bcf_day": 0,
        "net_position": "NET EXPORTER",
        "export_potential_bcf_day": 15,
        "trade_balance_usd": 50_000_000_000,
        "margin_opportunity": "VERY HIGH - Asian & European demand",
    },
    "Thermal Coal (HS 2701)": {
        "us_production_tons": 500_000_000,
        "us_consumption_tons": 400_000_000,
        "current_exports_tons": 50_000_000,
        "current_imports_tons": 10_000_000,
        "net_position": "NET EXPORTER",
        "export_potential_tons": 75_000_000,
        "trade_balance_usd": 8_000_000_000,
        "margin_opportunity": "MEDIUM - India, Asia demand growing",
    },
}

PORT_DATA = {
    "Port of Houston (TX)": {
        "primary_commodities": ["Crude Oil", "Refined Petroleum", "LNG", "Coke"],
        "annual_export_capacity": {"crude_bpd": 500_000, "refined_bpd": 3_500_000, "lng_bcf_day": 12, "coal_tons": 10_000_000},
        "specialization_score": 98,
        "key_terminals": ["Sabine Pass LNG", "Houston Ship Channel"],
    },
    "Port of Corpus Christi (TX)": {
        "primary_commodities": ["Crude Oil", "LNG", "Refined Petroleum"],
        "annual_export_capacity": {"crude_bpd": 400_000, "refined_bpd": 1_500_000, "lng_bcf_day": 4, "coal_tons": 0},
        "specialization_score": 92,
        "key_terminals": ["Corpus Christi LNG", "Nueces Bay"],
    },
    "Port of Beaumont (TX)": {
        "primary_commodities": ["Refined Petroleum", "Coke"],
        "annual_export_capacity": {"crude_bpd": 0, "refined_bpd": 2_000_000, "lng_bcf_day": 0, "coal_tons": 0},
        "specialization_score": 85,
        "key_terminals": ["Port of Beaumont Refinery Complex"],
    },
    "Port of Los Angeles (CA)": {
        "primary_commodities": ["Coal", "General Cargo"],
        "annual_export_capacity": {"crude_bpd": 0, "refined_bpd": 0, "lng_bcf_day": 0, "coal_tons": 15_000_000},
        "specialization_score": 75,
        "key_terminals": ["Los Angeles Container Terminal", "Coal Export Facility"],
    },
}

EXPORT_MARGINS = {
    "2710": {  # Refined Petroleum
        "Asia": {"margin_usd_bbl": 15.50, "demand_forecast": "HIGH (India, SE Asia)", "logistics_cost_bbl": 3.20},
        "Europe": {"margin_usd_bbl": 18.00, "demand_forecast": "MEDIUM", "logistics_cost_bbl": 5.50},
        "Caribbean": {"margin_usd_bbl": 12.00, "demand_forecast": "MEDIUM", "logistics_cost_bbl": 1.80},
    },
    "271121": {  # LNG
        "Asia": {"margin_usd_mmbtu": 4.20, "demand_forecast": "VERY HIGH", "logistics_cost_mmbtu": 2.50},
        "Europe": {"margin_usd_mmbtu": 3.50, "demand_forecast": "HIGH", "logistics_cost_mmbtu": 3.00},
        "Americas": {"margin_usd_mmbtu": 2.80, "demand_forecast": "GROWING", "logistics_cost_mmbtu": 1.50},
    },
    "2701": {  # Thermal Coal
        "Asia": {"margin_usd_ton": 45.00, "demand_forecast": "HIGH", "logistics_cost_ton": 28.00},
        "Europe": {"margin_usd_ton": 35.00, "demand_forecast": "DECLINING", "logistics_cost_ton": 42.00},
        "Americas": {"margin_usd_ton": 20.00, "demand_forecast": "LOW", "logistics_cost_ton": 12.00},
    },
}

REFINED_PETROLEUM_PRODUCTS = {
    "271011": {"name": "Petroleum oils, not crude", "volume_share": 0.40, "export_volume_bpd": 1400000},
    "271012": {"name": "Light oils & fractions (Gasoline/Naphtha)", "volume_share": 0.35, "export_volume_bpd": 1225000, "margin_rank": 1},
    "271019": {"name": "Other petroleum oils (Diesel/Kerosene)", "volume_share": 0.25, "export_volume_bpd": 875000, "margin_rank": 2},
}


@router.get("/opportunities")
async def get_export_opportunities() -> Dict:
    """Get top US export opportunities ranked by suitability & margin."""
    opportunities = [
        {
            "rank": 1,
            "commodity": "Refined Petroleum (HS 2710)",
            "export_score": 88,
            "current_exports": "3.5M bbl/day",
            "export_potential": "4.0M bbl/day (+500K capacity)",
            "margin_net_per_unit": "$12-15/bbl",
            "annual_opportunity_usd": "$2.2B - $2.7B",
            "key_markets": ["India (+4% YoY demand)", "SE Asia (refinery shortfalls)"],
            "best_ports": ["Port of Houston", "Port of Beaumont"],
            "products": ["Gasoline (HS 271012)", "Diesel (HS 271019)", "Other oils (HS 271011)"],
        },
        {
            "rank": 2,
            "commodity": "LNG (HS 271121)",
            "export_score": 78,
            "current_exports": "12 BCF/day",
            "export_potential": "15 BCF/day (+3 BCF/day)",
            "margin_net_per_unit": "$1.7-$2.7/MMBtu",
            "annual_opportunity_usd": "$8.5B - $12.0B",
            "key_markets": ["Japan (20% of global LNG)", "Korea", "India (growing)"],
            "best_ports": ["Port of Houston", "Port of Corpus Christi"],
            "terminals": ["Sabine Pass (3.8 BCF/day)", "Freeport (2.1 BCF/day)", "Cameron", "Corpus Christi", "Brownsville"],
        },
        {
            "rank": 3,
            "commodity": "Thermal Coal (HS 2701)",
            "export_score": 77,
            "current_exports": "50M tons/year",
            "export_potential": "75M tons/year (+25M tons)",
            "margin_net_per_unit": "$17/ton",
            "annual_opportunity_usd": "$425M",
            "key_markets": ["India (imports 75%, growing +3.2% YoY)"],
            "best_ports": ["Port of Los Angeles", "Port of Long Beach"],
            "note": "Demand pressures from coal transition; mid-term opportunity",
        },
    ]

    return {
        "timestamp": datetime.now().isoformat(),
        "opportunities": opportunities,
        "analysis_period": "2024",
    }


@router.get("/commodities")
async def get_trade_balance(commodity: Optional[str] = Query(None)) -> Dict:
    """Get US trade balance & export potential by commodity."""
    if commodity:
        if commodity not in TRADE_BALANCE_DATA:
            raise HTTPException(status_code=404, detail=f"Commodity '{commodity}' not found")
        data = {commodity: TRADE_BALANCE_DATA[commodity]}
    else:
        data = TRADE_BALANCE_DATA

    result = []
    for name, stats in data.items():
        result.append({
            "commodity": name,
            "trade_position": stats["net_position"],
            "annual_trade_balance_usd": stats["trade_balance_usd"],
            "margin_opportunity": stats["margin_opportunity"],
            "details": stats,
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "commodities": result,
    }


@router.get("/ports")
async def get_port_specialization() -> Dict:
    """Get US port specialization for energy commodity exports."""
    ports_list = []

    for port_name, specs in PORT_DATA.items():
        state = port_name.split("(")[1].rstrip(")")
        ports_list.append({
            "port": port_name,
            "state": state,
            "primary_commodities": specs["primary_commodities"],
            "specialization_score": specs["specialization_score"],
            "export_capacity": specs["annual_export_capacity"],
            "key_terminals": specs.get("key_terminals", []),
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "ports": sorted(ports_list, key=lambda x: x["specialization_score"], reverse=True),
    }


@router.get("/margins")
async def get_export_margins(commodity: str = Query(...)) -> Dict:
    """Get export margins by destination region for a commodity."""
    hs_code_map = {
        "2710": "Refined Petroleum",
        "271121": "LNG",
        "2701": "Thermal Coal",
    }

    if commodity not in EXPORT_MARGINS and commodity not in hs_code_map.values():
        raise HTTPException(status_code=404, detail=f"No margin data for commodity '{commodity}'")

    # Map to HS code if needed
    hs_code = commodity if commodity in EXPORT_MARGINS else \
              [k for k, v in hs_code_map.items() if v == commodity][0]

    margins_data = EXPORT_MARGINS.get(hs_code, {})

    result = []
    for region, margins in margins_data.items():
        net_margin = margins.get("margin_usd_bbl", margins.get("margin_usd_mmbtu", margins.get("margin_usd_ton", 0))) - \
                    margins.get("logistics_cost_bbl", margins.get("logistics_cost_mmbtu", margins.get("logistics_cost_ton", 0)))

        result.append({
            "destination": region,
            "gross_margin": margins.get("margin_usd_bbl", margins.get("margin_usd_mmbtu", margins.get("margin_usd_ton"))),
            "logistics_cost": margins.get("logistics_cost_bbl", margins.get("logistics_cost_mmbtu", margins.get("logistics_cost_ton"))),
            "net_margin": net_margin,
            "demand_forecast": margins["demand_forecast"],
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "hs_code": hs_code,
        "commodity": hs_code_map.get(hs_code, commodity),
        "margins_by_region": sorted(result, key=lambda x: x["net_margin"], reverse=True),
    }


@router.get("/refined-products")
async def get_refined_petroleum_breakdown() -> Dict:
    """Get HS code breakdown of US refined petroleum exports."""
    products = []

    for hs_code, data in REFINED_PETROLEUM_PRODUCTS.items():
        products.append({
            "hs_code": hs_code,
            "product_name": data["name"],
            "export_volume_bpd": data["export_volume_bpd"],
            "percent_of_refined": f"{data['volume_share']*100:.0f}%",
            "margin_rank": f"#{data.get('margin_rank', 'N/A')}",
            "key_markets": "Asia, Europe, Caribbean" if "Light oils" in data["name"] else "Europe, Americas",
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "hs_code_parent": "2710",
        "commodity": "Refined Petroleum",
        "total_export_bpd": 3_500_000,
        "products": products,
    }


@router.get("/tariff-reference")
async def get_tariff_info() -> Dict:
    """Get HS code and tariff duty information for energy commodities."""
    tariff_codes = {
        "2709": {"product": "Crude Oils", "duty_rate": "0%", "notes": "Export restrictions apply (Energy Policy Act)"},
        "2710": {"product": "Refined Petroleum", "duty_rate": "0%", "notes": "Highest export margin; gasoline/diesel prioritized"},
        "271011": {"product": "Petroleum Oils", "duty_rate": "0%"},
        "271012": {"product": "Light Oils (Gasoline)", "duty_rate": "0%", "notes": "Premium markets in Asia"},
        "271019": {"product": "Other Oils (Diesel/Kerosene)", "duty_rate": "0%", "notes": "Highest Asia demand"},
        "271121": {"product": "Liquefied Natural Gas (LNG)", "duty_rate": "0%", "notes": "5 operational terminals"},
        "2701": {"product": "Thermal Coal", "duty_rate": "0%", "notes": "Coal transition headwinds"},
        "2712": {"product": "Petroleum Coke", "duty_rate": "0%", "notes": "Refinery byproduct leverage"},
    }

    return {
        "timestamp": datetime.now().isoformat(),
        "system": "Harmonized System (HS) - Used for US imports/exports",
        "tariff_codes": tariff_codes,
        "note": "All energy commodities have 0% duty under USMCA and bilateral agreements",
    }


@router.get("/summary")
async def get_export_analysis_summary() -> Dict:
    """Get executive summary of US commodity export strategy."""
    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "us_trade_position": {
                "net_exporter_commodities": ["Refined Petroleum", "LNG", "Coal", "Petroleum Coke"],
                "net_importer_commodities": ["Crude Oil"],
                "primary_export_value": "$136.5B annually (energy commodities)",
            },
            "top_ports_by_energy": [
                {"port": "Port of Houston", "score": 98, "specialization": "Energy hub (crude, refined, LNG, coke)"},
                {"port": "Port of Corpus Christi", "score": 92, "specialization": "Energy (LNG, refined, crude)"},
                {"port": "Port of Beaumont", "score": 85, "specialization": "Refined products & coke"},
                {"port": "Port of Los Angeles", "score": 75, "specialization": "Coal (Pacific markets)"},
            ],
            "export_growth_drivers": [
                "Refined petroleum demand from India (+4% YoY)",
                "LNG demand from Asia (Japan 20% of global, growing Korea/India)",
                "Coal imports rising in South Asia despite transition pressures",
                "Petroleum coke use in aluminum & cement industries",
            ],
            "strategic_focus_2024_2025": [
                "Maximize refined petroleum exports to Asia via Port of Houston & Beaumont",
                "Expand LNG terminals at Freeport & Corpus Christi to capture growing Asian demand",
                "Capitalize on coal demand from India (imports 75% of needs, growing +3.2% YoY)",
            ],
        },
    }
