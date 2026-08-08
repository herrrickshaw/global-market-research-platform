#!/usr/bin/env python3
"""
Chemical Import Substitution Matcher
====================================
Cross-reference 1900 monitored chemicals (from Executive Summary)
against TradeStat EIDB trade data to identify substitution opportunities.

Usage:
    python chemical_import_substitution_matcher.py \
        --excel-import "path_to_import_excel" \
        --excel-export "path_to_export_excel" \
        --output report.csv
"""

import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

# ============================================================================
# TARGET HSN CODES FROM ANALYSIS
# ============================================================================

TARGET_HSN_CODES = {
    # TIER 1: LOAD-BEARING (FY30 Savings: $6.1bn)
    "tier1": {
        "29011100": {"name": "Ethylene", "import_usd_mn": 2800, "fy30_target_percent": 35, "capex_trigger": "BPCL AP + RIL O2C"},
        "29011200": {"name": "Propylene", "import_usd_mn": 1400, "fy30_target_percent": 40, "capex_trigger": "BPCL AP + RIL O2C"},
        "39021010": {"name": "HDPE", "import_usd_mn": 2800, "fy30_target_percent": 68, "capex_trigger": "RIL O2C + L&T Bina"},
        "39021030": {"name": "LDPE/LLDPE", "import_usd_mn": 2900, "fy30_target_percent": 65, "capex_trigger": "L&T Bina"},
        "39021100": {"name": "Polypropylene", "import_usd_mn": 1372, "fy30_target_percent": 80, "capex_trigger": "BPCL Kochi + AP"},
        "29173600": {"name": "TPA", "import_usd_mn": 1469, "fy30_target_percent": 65, "capex_trigger": "RIL polyester"},
        "29024300": {"name": "para-Xylene", "import_usd_mn": 721, "fy30_target_percent": 50, "capex_trigger": "RIL aromatic"},
    },

    # TIER 2: DEPENDENT (FY30 Savings: $1.2bn)
    "tier2": {
        "29053100": {"name": "Ethylene Glycol", "import_usd_mn": 650, "fy30_target_percent": 45, "capex_trigger": "Petrochemical integration"},
        "29152100": {"name": "Acetic Acid", "import_usd_mn": 490, "fy30_target_percent": 60, "capex_trigger": "Ethylene cracker integration"},
        "39074100": {"name": "PET", "import_usd_mn": 611, "fy30_target_percent": 50, "capex_trigger": "Polyester feedstock"},
        "29164000": {"name": "Acrylic Acid", "import_usd_mn": 250, "fy30_target_percent": 40, "capex_trigger": "Specialty chemical capex"},
        "29214110": {"name": "Aniline", "import_usd_mn": 352, "fy30_target_percent": 35, "capex_trigger": "Benzene integration"},
        "29214500": {"name": "Caprolactam", "import_usd_mn": 250, "fy30_target_percent": 30, "capex_trigger": "Specialty chemical complex"},
    },

    # TIER 2.5: QUICK WINS (FY30 Savings: $75–80mn)
    "tier2_5": {
        "29239090": {"name": "Lecithin", "import_usd_mn": 100, "fy30_target_percent": 75, "capex_trigger": "Oilseed processor expansion"},
    },

    # TIER 3: SPECIALTY (FY30 Savings: $0.9bn)
    "tier3": {
        "32030010": {"name": "Dyes (Azo/Disperse)", "import_usd_mn": 1400, "fy30_target_percent": 30, "capex_trigger": "BHAVYA Parks + anti-dumping duty"},
        "32050000": {"name": "Pigments", "import_usd_mn": 600, "fy30_target_percent": 25, "capex_trigger": "BHAVYA Parks (TiO2 raw-material constrained)"},
        "38090010": {"name": "Textile Auxiliaries", "import_usd_mn": 500, "fy30_target_percent": 35, "capex_trigger": "Auxiliary specialty complex"},
        "28301100": {"name": "Sulfuric Acid", "import_usd_mn": 1650, "fy30_target_percent": 20, "capex_trigger": "Mineral acid plant"},
        "28330000": {"name": "Nitric Acid", "import_usd_mn": 580, "fy30_target_percent": 15, "capex_trigger": "Specialty chemical"},
    },

    # ADDITIONAL CHEMICALS (Inorganic, Chapter 28)
    "inorganic": {
        "28151090": {"name": "Ammonia", "import_usd_mn": 1820, "fy30_target_percent": 10, "capex_trigger": "Fertilizer integration"},
        "28320000": {"name": "Phosphoric Acid", "import_usd_mn": 1420, "fy30_target_percent": 15, "capex_trigger": "Phosphate rock processing"},
    }
}

# ============================================================================
# PARSE TRADESTAT DATA
# ============================================================================

def parse_tradestat_excel(excel_path):
    """
    Parse TradeStat EIDB Excel file and extract:
    - HSN code
    - Commodity description
    - FY2025-26 import value (USD)
    """
    try:
        # Read Excel without header, then find actual header row
        df = pd.read_excel(excel_path, sheet_name=0, header=None)

        # Find header row (usually contains 'HSCode', 'Commodity', etc.)
        header_row = None
        for idx, row in df.iterrows():
            if any(str(val).lower() in ['hscode', 'commodity', 's.no.'] for val in row if pd.notna(val)):
                header_row = idx
                break

        if header_row is None:
            print(f"Warning: Could not find header row in {excel_path}")
            return pd.DataFrame()

        # Re-read with correct header
        df = pd.read_excel(excel_path, sheet_name=0, header=header_row)

        # Standardize column names
        col_mapping = {
            'HSCode': 'HSN_Code',
            'HS Code': 'HSN_Code',
            'Commodity': 'Commodity',
            '2025 - 2026': 'FY25_26_Value',
            '2024 - 2025': 'FY24_25_Value'
        }

        # Apply mapping (case-insensitive)
        new_cols = {}
        for old_col in df.columns:
            for key, val in col_mapping.items():
                if key.lower() in old_col.lower():
                    new_cols[old_col] = val
                    break
            if old_col not in new_cols:
                new_cols[old_col] = old_col

        df = df.rename(columns=new_cols)

        # Clean HSN codes
        if 'HSN_Code' in df.columns:
            df['HSN_Code'] = df['HSN_Code'].astype(str).str.strip().str.replace(' ', '')
            # Extract first 8 digits only (for matching)
            df['HSN_8digit'] = df['HSN_Code'].str[:8]

        return df
    except Exception as e:
        print(f"Error parsing {excel_path}: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def match_chemicals(tradestat_df):
    """
    Cross-match TradeStat data against TARGET_HSN_CODES.
    Returns: DataFrame with substitution opportunity scoring.
    """
    results = []

    for tier, chemicals in TARGET_HSN_CODES.items():
        for hsn_code, chemical_info in chemicals.items():
            # Find matching HSN in TradeStat (first 6-8 digits)
            matched_value = None
            matched_commodity = None

            if not tradestat_df.empty and 'HSN_8digit' in tradestat_df.columns:
                # Try exact 8-digit match first
                matches = tradestat_df[tradestat_df['HSN_8digit'] == hsn_code]

                if matches.empty:
                    # Try 6-digit match
                    matches = tradestat_df[tradestat_df['HSN_8digit'].str[:6] == hsn_code[:6]]

                if not matches.empty:
                    match_row = matches.iloc[0]
                    if 'FY25_26_Value' in match_row:
                        try:
                            matched_value = float(match_row['FY25_26_Value'])
                        except:
                            pass
                    if 'Commodity' in match_row:
                        matched_commodity = match_row['Commodity']

            # Use matched value or fallback to estimate
            import_value = matched_value if matched_value else chemical_info['import_usd_mn']
            status = "MATCHED" if matched_value else "ESTIMATE"

            # Calculate FY30 substitution quantum
            fy30_savings = import_value * (chemical_info['fy30_target_percent'] / 100)

            results.append({
                "HSN Code": hsn_code,
                "Chemical": chemical_info['name'],
                "Commodity (TradeStat)": matched_commodity if matched_commodity else "N/A",
                "Tier": tier,
                "CY2024 Imports (USD mn)": chemical_info['import_usd_mn'],
                "TradeStat FY25-26 (USD mn)": round(import_value, 2),
                "FY30 Substitution Target %": chemical_info['fy30_target_percent'],
                "FY30 Savings (USD mn)": round(fy30_savings, 0),
                "Capex Trigger": chemical_info['capex_trigger'],
                "Status": status
            })

    return pd.DataFrame(results)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Match chemicals against TradeStat trade data")
    parser.add_argument("--excel-import", type=str, help="Path to TradeStat import Excel file")
    parser.add_argument("--output", type=str, default="chemical_import_substitution_list.csv", help="Output CSV file")

    args = parser.parse_args()

    print("=" * 80)
    print("CHEMICAL IMPORT SUBSTITUTION MATCHER")
    print("=" * 80)

    # Load TradeStat data if provided
    if args.excel_import and Path(args.excel_import).exists():
        print(f"\n→ Loading TradeStat data from: {args.excel_import}")
        tradestat_df = parse_tradestat_excel(args.excel_import)
        print(f"  Loaded {len(tradestat_df)} commodity lines")
    else:
        print(f"\n→ Using default HSN codes (no TradeStat file provided)")
        tradestat_df = pd.DataFrame()

    # Match chemicals
    print(f"\n→ Matching {len(TARGET_HSN_CODES)} chemical tiers...")
    result_df = match_chemicals(tradestat_df)

    # Summary by tier
    print(f"\n" + "=" * 80)
    print("SUMMARY BY TIER")
    print("=" * 80)

    for tier in result_df['Tier'].unique():
        tier_data = result_df[result_df['Tier'] == tier]
        total_fy30_savings = tier_data['FY30 Savings (USD mn)'].sum()
        count = len(tier_data)
        print(f"\n{tier.upper()}")
        print(f"  Chemicals: {count}")
        print(f"  FY30 Savings: ${total_fy30_savings:,.0f}mn")

    # Overall summary
    total_fy30_savings = result_df['FY30 Savings (USD mn)'].sum()
    print(f"\n" + "=" * 80)
    print(f"TOTAL FY30 SAVINGS POTENTIAL: ${total_fy30_savings:,.0f}mn (${total_fy30_savings/1000:.1f}bn)")
    print("=" * 80)

    # Export
    output_file = args.output
    result_df.to_csv(output_file, index=False)
    print(f"\n✓ Exported: {output_file}")

    # Display sample
    print(f"\n→ Sample (Top 10 by FY30 savings):\n")
    display_df = result_df.nlargest(10, 'FY30 Savings (USD mn)')[
        ['HSN Code', 'Chemical', 'Tier', 'CY2024 Imports (USD mn)', 'FY30 Savings (USD mn)', 'Capex Trigger']
    ]
    print(display_df.to_string(index=False))
