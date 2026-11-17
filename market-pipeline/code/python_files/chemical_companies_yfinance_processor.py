#!/usr/bin/env python3
"""
Chemical Companies YFinance Processor
=====================================
Fast ticker-based processing for chemical companies & capex projects.
Integrates yfinance company data with HSN chemical mapping.

Usage:
    python chemical_companies_yfinance_processor.py
    python chemical_companies_yfinance_processor.py --market india --segment tier1
"""

import yfinance as yf
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# COMPANY DATABASE: Mapped to yfinance tickers
# ============================================================================

CHEMICAL_COMPANIES = {
    # TIER 1: LOAD-BEARING (Capex-Triggered)
    "india": {
        "tier1": [
            {
                "name": "Reliance Industries",
                "ticker": "RELIANCE.NS",
                "market": "NSE",
                "segment": "Petrochemicals",
                "capacity_ktpa": 4000,
                "key_products": ["Ethylene", "Propylene", "PP", "PE", "TPA"],
                "capex_project": "RIL O2C",
                "capex_value_cr": 75000,
                "capex_timeline": "FY28-30",
                "hsn_codes": ["29011100", "29011200", "39021010", "39021030", "39021100", "29173600"]
            },
            {
                "name": "Indian Oil Corporation",
                "ticker": "IOCL.NS",
                "market": "NSE",
                "segment": "Petrochemicals",
                "capacity_ktpa": 1500,
                "key_products": ["Ethylene", "Propylene", "PP"],
                "capex_project": "Panipat/Mathura Integration",
                "capex_value_cr": 15000,
                "capex_timeline": "FY27-29",
                "hsn_codes": ["29011100", "29011200", "39021100"]
            },
            {
                "name": "Bharat Petroleum",
                "ticker": "BPCL.NS",
                "market": "NSE",
                "segment": "Petrochemicals",
                "capacity_ktpa": 900,
                "key_products": ["Ethylene", "Propylene", "PP"],
                "capex_project": "BPCL AP Cracker + Kochi PP",
                "capex_value_cr": 100000,
                "capex_timeline": "FY27-28 (AP), FY26 (Kochi done)",
                "hsn_codes": ["29011100", "29011200", "39021100"],
                "risk_flags": ["AP EC not filed (Jul 2026)"]
            },
            {
                "name": "Hindustan Petroleum",
                "ticker": "HPCL.NS",
                "market": "NSE",
                "segment": "Petrochemicals",
                "capacity_ktpa": 400,
                "key_products": ["Ethylene", "Propylene"],
                "capex_project": "Minor upgrades",
                "capex_value_cr": 2500,
                "capex_timeline": "FY27-28",
                "hsn_codes": ["29011100", "29011200"]
            }
        ],
        "tier2": [
            {
                "name": "Jindal Polyester",
                "ticker": "JINDALP.NS",
                "market": "NSE",
                "segment": "Polyester/TPA",
                "capacity_ktpa": 400,
                "key_products": ["TPA", "PET"],
                "capex_project": "TPA capacity expansion",
                "capex_value_cr": 3000,
                "capex_timeline": "FY27-28",
                "hsn_codes": ["29173600", "39074100"]
            },
            {
                "name": "Lupin Ltd (Acrylic)",
                "ticker": "LUPIN.NS",
                "market": "NSE",
                "segment": "Specialty Chemicals",
                "capacity_ktpa": 50,
                "key_products": ["Acrylic Acid", "Derivatives"],
                "capex_project": "Acrylic acid backward integration",
                "capex_value_cr": 500,
                "capex_timeline": "FY27-28",
                "hsn_codes": ["29164000"]
            }
        ],
        "tier2_5_quick_wins": [
            {
                "name": "Adani Wilmar",
                "ticker": "ADANIWD.NS",
                "market": "NSE",
                "segment": "Oilseed Processing",
                "capacity_ktpa": 500,
                "key_products": ["Lecithin", "Soya Oil"],
                "capex_project": "Lecithin extraction expansion",
                "capex_value_cr": 200,
                "capex_timeline": "FY27",
                "hsn_codes": ["29239090"],
                "quick_win": True
            },
            {
                "name": "Cargill India",
                "ticker": None,  # Private company
                "market": "Private",
                "segment": "Oilseed Processing",
                "capacity_ktpa": 300,
                "key_products": ["Lecithin", "Plant Oils"],
                "capex_project": "Lecithin capacity +50 KTPA",
                "capex_value_cr": 150,
                "capex_timeline": "FY27-28",
                "hsn_codes": ["29239090"],
                "quick_win": True
            }
        ],
        "tier3_specialty": [
            {
                "name": "Sumitomo Chemical",
                "ticker": None,  # Global, India subsidiary
                "market": "Global",
                "segment": "Dyes & Pigments",
                "capacity_ktpa": 120,
                "key_products": ["Disperse Dyes", "Reactive Dyes"],
                "capex_project": "Dye facility upgrade",
                "capex_value_cr": 400,
                "capex_timeline": "FY28-29",
                "hsn_codes": ["32030010"],
                "market_share_india": 0.15
            },
            {
                "name": "Archroma India",
                "ticker": None,  # Global, India subsidiary
                "market": "Global",
                "segment": "Dyes & Chemicals",
                "capacity_ktpa": 80,
                "key_products": ["Dyes", "Auxiliaries"],
                "capex_project": "Auxiliary chemicals expansion",
                "capex_value_cr": 250,
                "capex_timeline": "FY28-30",
                "hsn_codes": ["32030010", "38090010"],
                "market_share_india": 0.12
            }
        ]
    },

    # GLOBAL COMPETITORS (Exporters to India)
    "global_competitors": {
        "middle_east_saudi": [
            {
                "name": "Saudi Aramco",
                "ticker": "2222.SA",
                "market": "Tadawul",
                "segment": "Integrated Oil & Gas",
                "india_export_share": 0.30,
                "key_exports_to_india": ["Ethylene", "Propylene", "Polyolefins"],
                "hsn_codes": ["29011100", "29011200", "39021010", "39021100"]
            },
            {
                "name": "SABIC",
                "ticker": None,  # Subsidiary of Saudi Aramco
                "market": "Global",
                "segment": "Petrochemicals",
                "india_export_share": 0.35,
                "key_exports_to_india": ["PP", "PE", "Specialty Polymers"],
                "hsn_codes": ["39021010", "39021030", "39021100"]
            }
        ],
        "china": [
            {
                "name": "Sinopec",
                "ticker": "600028.SS",  # Shanghai
                "market": "Shanghai",
                "segment": "Petrochemicals",
                "india_export_share": 0.45,
                "key_exports_to_india": ["TPA", "Azo Dyes", "Disperse Dyes"],
                "hsn_codes": ["29173600", "32030010"]
            },
            {
                "name": "CNPC",
                "ticker": "PTR",  # ADR
                "market": "NYSE",
                "segment": "Oil & Petrochemicals",
                "india_export_share": 0.40,
                "key_exports_to_india": ["Chemicals", "Polymers"],
                "hsn_codes": ["29000000", "39000000"]
            }
        ],
        "us_eu": [
            {
                "name": "ExxonMobil",
                "ticker": "XOM",
                "market": "NYSE",
                "segment": "Integrated Oil & Gas",
                "india_export_share": 0.08,
                "key_exports_to_india": ["Specialty Polymers", "Chemicals"],
                "hsn_codes": ["39021000", "39074000"]
            },
            {
                "name": "Dow Inc",
                "ticker": "DOW",
                "market": "NYSE",
                "segment": "Specialty Chemicals",
                "india_export_share": 0.12,
                "key_exports_to_india": ["Polyurethane", "Adhesives", "Coatings"],
                "hsn_codes": ["39069090", "39072990"]
            },
            {
                "name": "LyondellBasell",
                "ticker": "LYB",
                "market": "NYSE",
                "segment": "Petrochemicals",
                "india_export_share": 0.10,
                "key_exports_to_india": ["Polyolefins", "Styrenics"],
                "hsn_codes": ["39021000", "39071000"]
            }
        ]
    }
}

# ============================================================================
# FETCH COMPANY DATA FROM YFINANCE
# ============================================================================

def fetch_company_data(ticker, retry_count=0):
    """
    Fetch company fundamentals from yfinance.
    Returns: dict with market_cap, pe, pb, roe, debt_to_equity, sector, industry
    """
    if not ticker:
        return None

    try:
        company = yf.Ticker(ticker)
        info = company.info

        if info.get("longName"):  # Valid response
            return {
                "ticker": ticker,
                "name": info.get("longName"),
                "market_cap_usd": info.get("marketCap"),
                "market_cap_bn": info.get("marketCap", 0) / 1e9 if info.get("marketCap") else None,
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "roe": info.get("returnOnEquity"),
                "debt_to_equity": info.get("debtToEquity"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "employees": info.get("fullTimeEmployees"),
                "website": info.get("website"),
                "currency": info.get("currency")
            }
    except Exception as e:
        pass  # Silently skip unavailable tickers

    return None


def process_chemical_companies(market="india", segment=None, batch_fetch=True):
    """
    Process chemical companies from database with yfinance data.

    Args:
        market: "india" or "global_competitors"
        segment: "tier1", "tier2", "tier3", "tier2_5_quick_wins" (optional)
        batch_fetch: Fetch all tickers in batch

    Returns:
        DataFrame with enriched company data
    """

    companies_to_process = []

    if market == "india":
        db = CHEMICAL_COMPANIES["india"]
        if segment:
            if segment in db:
                companies_to_process = db[segment]
        else:
            for tier in db.values():
                if isinstance(tier, list):
                    companies_to_process.extend(tier)
    elif market == "global_competitors":
        db = CHEMICAL_COMPANIES["global_competitors"]
        for region in db.values():
            companies_to_process.extend(region)

    logger.info(f"Processing {len(companies_to_process)} companies from {market}")

    # Collect tickers for batch fetch
    tickers_with_data = []

    for company in companies_to_process:
        ticker = company.get("ticker")

        # Fetch yfinance data if ticker available
        yf_data = {}
        if ticker:
            yf_data = fetch_company_data(ticker) or {}

        # Merge company info with yfinance data
        enriched = {**company, **yf_data}
        tickers_with_data.append(enriched)

    df = pd.DataFrame(tickers_with_data)
    return df


# ============================================================================
# FAST SCREENING & ANALYSIS
# ============================================================================

def screen_chemicals_by_tier(market="india"):
    """
    Fast screening: Market cap, capex, HSN coverage by tier.
    """
    results = {}

    for tier in ["tier1", "tier2", "tier2_5_quick_wins", "tier3_specialty"]:
        df = process_chemical_companies(market=market, segment=tier)

        if not df.empty:
            results[tier] = {
                "count": len(df),
                "total_capacity_ktpa": df.get("capacity_ktpa", 0).sum() if "capacity_ktpa" in df else 0,
                "total_capex_cr": df.get("capex_value_cr", 0).sum() if "capex_value_cr" in df else 0,
                "avg_market_cap_bn": df.get("market_cap_bn", 0).mean() if "market_cap_bn" in df else 0,
                "companies": df["name"].tolist(),
                "hsn_coverage": []
            }

            # Aggregate HSN codes
            all_hsn = []
            for hsn_list in df.get("hsn_codes", [[]]):
                if isinstance(hsn_list, list):
                    all_hsn.extend(hsn_list)
            results[tier]["hsn_coverage"] = list(set(all_hsn))

    return results


def fast_capex_summary(market="india"):
    """
    Fast capex summary: Total investment, timeline, risk flags.
    """
    df = process_chemical_companies(market=market)

    summary = {
        "total_capex_cr": df.get("capex_value_cr", 0).sum(),
        "total_capex_usd_bn": df.get("capex_value_cr", 0).sum() / 85,  # Approx 1 USD = 85 INR
        "projects_by_timeline": {},
        "risk_projects": [],
        "total_capacity_addition_ktpa": df.get("capacity_ktpa", 0).sum()
    }

    # Group by timeline
    for _, row in df.iterrows():
        timeline = row.get("capex_timeline", "Unknown")
        if timeline not in summary["projects_by_timeline"]:
            summary["projects_by_timeline"][timeline] = []
        summary["projects_by_timeline"][timeline].append(row["name"])

        # Flag risks
        if row.get("risk_flags"):
            summary["risk_projects"].append({
                "company": row["name"],
                "risks": row["risk_flags"]
            })

    return summary


def export_analysis(market="india", output_format="csv"):
    """
    Export enriched company data for downstream analysis.
    """
    df = process_chemical_companies(market=market)

    output_dir = Path("/Users/umashankar/market-pipeline/code/python_files/reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")

    if output_format == "csv":
        output_file = output_dir / f"chemical_companies_{market}_{timestamp}.csv"
        df.to_csv(output_file, index=False)
        logger.info(f"Exported CSV: {output_file}")
        return str(output_file)

    elif output_format == "json":
        output_file = output_dir / f"chemical_companies_{market}_{timestamp}.json"
        df.to_json(output_file, orient="records", indent=2)
        logger.info(f"Exported JSON: {output_file}")
        return str(output_file)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import sys

    print("=" * 80)
    print("CHEMICAL COMPANIES YFINANCE PROCESSOR")
    print("=" * 80)

    # Default: India Tier 1
    market = "india"
    segment = "tier1"

    if len(sys.argv) > 1:
        market = sys.argv[1]
    if len(sys.argv) > 2:
        segment = sys.argv[2]

    # TIER 1 PROCESSING
    print(f"\n>>> TIER 1 COMPANIES (India)\n")
    tier1_df = process_chemical_companies(market="india", segment="tier1")
    print(tier1_df[["name", "ticker", "capacity_ktpa", "capex_value_cr", "capex_timeline"]].to_string())

    # CAPEX SUMMARY
    print(f"\n>>> CAPEX SUMMARY (All Tiers)\n")
    capex_summary = fast_capex_summary(market="india")
    print(f"Total Capex (FY26-30): ₹{capex_summary['total_capex_cr']:,.0f} crore (~${capex_summary['total_capex_usd_bn']:.1f}bn)")
    print(f"Total Capacity Addition: {capex_summary['total_capacity_addition_ktpa']:,.0f} KTPA")
    print(f"\nCapex by Timeline:")
    for timeline, projects in capex_summary['projects_by_timeline'].items():
        project_names = [str(p) for p in projects if pd.notna(p)]
        print(f"  {timeline}: {', '.join(project_names)}")

    # RISK FLAGS
    if capex_summary['risk_projects']:
        print(f"\n⚠️  RISK FLAGS:")
        for risk in capex_summary['risk_projects']:
            risks_str = ', '.join(risk['risks']) if isinstance(risk['risks'], list) else str(risk['risks'])
            print(f"  {risk['company']}: {risks_str}")

    # GLOBAL COMPETITORS
    print(f"\n>>> GLOBAL COMPETITORS (Export Share to India)\n")
    global_df = process_chemical_companies(market="global_competitors")
    if not global_df.empty:
        print(global_df[["name", "ticker", "india_export_share", "key_exports_to_india"]].to_string())

    # EXPORT
    print(f"\n>>> EXPORTING DATA...\n")
    export_analysis(market="india", output_format="csv")
    export_analysis(market="global_competitors", output_format="csv")

    print("\n✓ Processing complete")
