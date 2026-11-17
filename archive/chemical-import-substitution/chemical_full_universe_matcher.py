#!/usr/bin/env python3
"""
Full Chemical Universe Matcher
==============================
Expand matching from 21 priority chemicals to ALL 1,900+ chemicals in TradeStat EIDB.

Strategy:
1. Extract ALL chemicals from TradeStat import data (all commodity-wise lines)
2. Classify by HSN chapter, import value, growth rate, and trade balance
3. Segment into substitution priority tiers based on:
   - Current import value (high = more forex impact)
   - YoY growth rate (high growth = rising demand/vulnerability)
   - India production capacity (gap = import dependence)
   - Capex project alignment (can be solved by planned projects)
4. Link to capex triggers where applicable
5. Flag quick-win opportunities (high ROI, low capex, low execution risk)

Output: Comprehensive chemical universe with substitution scoring.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# PRIORITY CHEMICALS (Our analysis) - Use for boosting scores
# ============================================================================

PRIORITY_HSN_CODES = {
    "29011100", "29011200", "39021010", "39021030", "39021100",
    "29173600", "29024300", "29053100", "29152100", "39074100",
    "29164000", "29214110", "29214500", "29239090", "32030010",
    "32050000", "38090010", "28301100", "28330000", "28151090", "28320000"
}

# ============================================================================
# HSN CHAPTER CLASSIFICATION
# ============================================================================

HSN_CHAPTERS = {
    "28": {"name": "Inorganic Chemicals", "category": "Basic Chemistry", "priority": "High"},
    "29": {"name": "Organic Chemicals", "category": "Petrochemicals", "priority": "High"},
    "30": {"name": "Pharmaceutical Products", "category": "Pharma", "priority": "Medium"},
    "31": {"name": "Fertilizers", "category": "Agro-chemicals", "priority": "Medium"},
    "32": {"name": "Dyes, Pigments, Paint", "category": "Specialty", "priority": "Medium"},
    "33": {"name": "Essential Oils, Perfume", "category": "Specialty", "priority": "Low"},
    "34": {"name": "Soap, Detergent", "category": "FMCG", "priority": "Low"},
    "35": {"name": "Proteins, Adhesives", "category": "Specialty", "priority": "Medium"},
    "36": {"name": "Explosives, Pyrotechnics", "category": "Specialty", "priority": "Low"},
    "37": {"name": "Photography Chemicals", "category": "Specialty", "priority": "Low"},
    "38": {"name": "Miscellaneous Chemicals", "category": "Auxiliaries", "priority": "Medium"},
    "39": {"name": "Plastics", "category": "Polymers", "priority": "High"},
    "40": {"name": "Rubber", "category": "Elastomers", "priority": "Medium"},
}

# ============================================================================
# PARSE AND CLASSIFY ALL CHEMICALS
# ============================================================================

def parse_tradestat_full(excel_path):
    """
    Parse TradeStat EIDB and extract ALL chemicals with full classification.
    Returns: DataFrame with HSN, Commodity, Imports FY24-25, Imports FY25-26, Growth %, etc.
    """
    try:
        # TradeStat Excel has title in row 0-1, header in row 2
        df = pd.read_excel(excel_path, sheet_name=0, header=2)

        # Clean up: remove the first column if it's just row numbers
        if df.columns[0] in ['S.No.', 'S.No', 'Unnamed: 0']:
            df = df.drop(columns=[df.columns[0]])

        # Remove completely empty rows
        df = df.dropna(how='all')

        # Standardize columns
        # Expected columns: S.No., HSCode, Commodity, 2024 - 2025, %Share, 2025 - 2026, %Share, %Growth
        col_mapping = {
            'S.No.': 'S_No',
            'HSCode': 'HSN_Code',
            'Commodity': 'Commodity',
            '2024 - 2025': 'FY24_25_Value',
            '2025 - 2026': 'FY25_26_Value',
            '%Growth': 'YoY_Growth_Percent'
        }

        # Match columns case-insensitively
        actual_mapping = {}
        for old_col in df.columns:
            for key, new_name in col_mapping.items():
                if old_col == key or old_col.lower() == key.lower():
                    actual_mapping[old_col] = new_name
                    break

        df = df.rename(columns=actual_mapping)

        logger.info(f"Loaded {len(df)} rows after header row 2")

        # Clean HSN codes
        if 'HSN_Code' in df.columns:
            df['HSN_Code'] = df['HSN_Code'].astype(str).str.strip().str.replace(' ', '')
            df['HSN_Chapter'] = df['HSN_Code'].str[:2]
            df['HSN_6digit'] = df['HSN_Code'].str[:6]
            df['HSN_8digit'] = df['HSN_Code'].str[:8]

        # Convert values to numeric
        for col in ['FY24_25_Value', 'FY25_26_Value', 'YoY_Growth_Percent', 'FY24_25_Share', 'FY25_26_Share']:
            if col in df.columns and df[col] is not None:
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                except:
                    pass  # Skip if conversion fails

        # Calculate growth if not present
        if 'YoY_Growth_Percent' not in df.columns and 'FY24_25_Value' in df.columns and 'FY25_26_Value' in df.columns:
            df['YoY_Growth_Percent'] = ((df['FY25_26_Value'] - df['FY24_25_Value']) / df['FY24_25_Value'] * 100).round(2)

        return df
    except Exception as e:
        logger.error(f"Error parsing {excel_path}: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def classify_chemicals(df):
    """
    Classify all chemicals by substitution potential.

    Scoring logic:
    - Base score by chapter (High=3, Medium=2, Low=1)
    - Import value multiplier (>$500mn = 1.5x, >$1bn = 2x)
    - Growth rate bonus (>10% YoY = +1.5x)
    - Priority HSN bonus (+2x if in our priority list)
    - Quick-win bonus (+1.5x if high score + low complexity)
    """

    scoring_results = []

    for _, row in df.iterrows():
        if pd.isna(row.get('HSN_Code')) or pd.isna(row.get('FY25_26_Value')):
            continue

        hsn_code = row['HSN_Code']
        hsn_chapter = row.get('HSN_Chapter', '')
        commodity = row.get('Commodity', 'Unknown')
        import_value = row.get('FY25_26_Value', 0)
        growth_rate = row.get('YoY_Growth_Percent', 0)

        # Base chapter priority
        chapter_info = HSN_CHAPTERS.get(hsn_chapter, {"name": "Other", "priority": "Low"})
        chapter_priority = {"High": 3, "Medium": 2, "Low": 1}.get(chapter_info.get('priority', 'Low'), 1)

        # Import value multiplier (USD millions)
        value_multiplier = 1.0
        if import_value > 1000:
            value_multiplier = 2.0
        elif import_value > 500:
            value_multiplier = 1.5
        elif import_value > 100:
            value_multiplier = 1.2

        # Growth rate bonus (YoY growth signal demand surge)
        growth_bonus = 1.0
        if pd.notna(growth_rate):
            if growth_rate > 20:
                growth_bonus = 1.8
            elif growth_rate > 10:
                growth_bonus = 1.5
            elif growth_rate > 0:
                growth_bonus = 1.1
            # Negative growth (import substitution already happening) = lower priority

        # Priority HSN bonus (from our analysis)
        priority_bonus = 1.0
        if any(hsn_code.startswith(p[:6]) or hsn_code[:6] == p[:6] for p in PRIORITY_HSN_CODES):
            priority_bonus = 2.0

        # Calculate base score
        base_score = chapter_priority * value_multiplier * growth_bonus * priority_bonus

        # Tier assignment (based on composite score)
        if base_score >= 12:
            tier = "Tier 1 (Load-bearing)"
            confidence = 0.85
        elif base_score >= 6:
            tier = "Tier 2 (Dependent)"
            confidence = 0.70
        elif base_score >= 3 and import_value > 50:
            tier = "Tier 2.5 (Quick-win)"
            confidence = 0.80
        elif base_score >= 2:
            tier = "Tier 3 (Specialty)"
            confidence = 0.50
        else:
            tier = "Monitor (Low priority)"
            confidence = 0.30

        # Quick-win flag: high score + low capex complexity (estimate)
        quick_win = False
        if tier in ["Tier 2.5 (Quick-win)"] or (tier == "Tier 2 (Dependent)" and import_value < 200):
            quick_win = True

        # Substitution potential (conservative)
        if tier == "Tier 1 (Load-bearing)":
            sub_potential_percent = 50  # 50-80% achievable via capex
            sub_potential_range = "50-80%"
        elif tier == "Tier 2 (Dependent)":
            sub_potential_percent = 30  # 30-50% via dependent capex
            sub_potential_range = "30-50%"
        elif tier == "Tier 2.5 (Quick-win)":
            sub_potential_percent = 60  # 60-75% via focused investment
            sub_potential_range = "60-75%"
        elif tier == "Tier 3 (Specialty)":
            sub_potential_percent = 15  # 15-30% via specialty capex + tariffs
            sub_potential_range = "15-30%"
        else:
            sub_potential_percent = 5
            sub_potential_range = "5-15%"

        fy30_savings = import_value * (sub_potential_percent / 100)

        scoring_results.append({
            "HSN_Code": hsn_code,
            "HSN_Chapter": hsn_chapter,
            "Chapter_Name": chapter_info.get('name', 'Other'),
            "Commodity": commodity,
            "Import_FY24_25_USDmillions": round(row.get('FY24_25_Value', 0), 2) if pd.notna(row.get('FY24_25_Value')) else None,
            "Import_FY25_26_USDmillions": round(import_value, 2),
            "YoY_Growth_Percent": round(growth_rate, 1) if pd.notna(growth_rate) else None,
            "Base_Score": round(base_score, 2),
            "Chapter_Priority": chapter_info.get('priority'),
            "Tier": tier,
            "Substitution_Potential": sub_potential_range,
            "FY30_Savings_USDmillions": round(fy30_savings, 1),
            "Confidence_Level": confidence,
            "Quick_Win": "Yes" if quick_win else "No",
            "Priority_Chemical": "Yes" if priority_bonus == 2.0 else "No"
        })

    return pd.DataFrame(scoring_results)


def generate_summary_statistics(classified_df):
    """
    Generate tier-wise and chapter-wise summary statistics.
    """
    print("\n" + "=" * 100)
    print("CHEMICAL UNIVERSE SUMMARY")
    print("=" * 100)

    # Total import value
    total_imports = classified_df['Import_FY25_26_USDmillions'].sum()
    print(f"\nTotal Chemical Imports (FY25-26): ${total_imports:,.0f}mn (${total_imports/1000:.1f}bn)")

    # By tier
    print(f"\n{'TIER ANALYSIS':^100}")
    print("-" * 100)
    for tier in ["Tier 1 (Load-bearing)", "Tier 2 (Dependent)", "Tier 2.5 (Quick-win)", "Tier 3 (Specialty)", "Monitor (Low priority)"]:
        tier_data = classified_df[classified_df['Tier'] == tier]
        if not tier_data.empty:
            count = len(tier_data)
            imports_mn = tier_data['Import_FY25_26_USDmillions'].sum()
            savings_mn = tier_data['FY30_Savings_USDmillions'].sum()
            print(f"{tier:40} | Chemicals: {count:4} | Imports: ${imports_mn/1000:7.1f}bn | FY30 Savings: ${savings_mn/1000:6.1f}bn")

    # By chapter
    print(f"\n{'CHAPTER-WISE ANALYSIS (Top 15)':^100}")
    print("-" * 100)
    chapter_summary = classified_df.groupby(['HSN_Chapter', 'Chapter_Name']).agg({
        'Commodity': 'count',
        'Import_FY25_26_USDmillions': 'sum',
        'FY30_Savings_USDmillions': 'sum'
    }).rename(columns={'Commodity': 'Count'}).sort_values('Import_FY25_26_USDmillions', ascending=False).head(15)

    for (chapter, name), row in chapter_summary.iterrows():
        print(f"Ch {chapter} ({name:30}) | Chemicals: {int(row['Count']):4} | Imports: ${row['Import_FY25_26_USDmillions']/1000:7.1f}bn | Savings: ${row['FY30_Savings_USDmillions']/1000:6.1f}bn")

    # Quick wins
    print(f"\n{'QUICK WINS (High ROI, Low Capex)':^100}")
    print("-" * 100)
    quick_wins = classified_df[classified_df['Quick_Win'] == 'Yes'].nlargest(10, 'Import_FY25_26_USDmillions')
    for _, row in quick_wins.iterrows():
        print(f"HSN {row['HSN_Code']:8} | {row['Commodity'][:40]:40} | ${row['Import_FY25_26_USDmillions']:8.0f}mn | Savings: ${row['FY30_Savings_USDmillions']:7.0f}mn")

    # High-growth chemicals (>20% YoY)
    print(f"\n{'HIGH-GROWTH IMPORTS (>20% YoY - Watch for Supply Risk)':^100}")
    print("-" * 100)
    high_growth = classified_df[classified_df['YoY_Growth_Percent'] > 20].nlargest(10, 'YoY_Growth_Percent')
    if not high_growth.empty:
        for _, row in high_growth.iterrows():
            print(f"HSN {row['HSN_Code']:8} | {row['Commodity'][:40]:40} | Growth: {row['YoY_Growth_Percent']:8.1f}% | ${row['Import_FY25_26_USDmillions']:8.0f}mn")
    else:
        print("No chemicals with >20% growth found (or data not available)")

    return {
        "total_imports": total_imports,
        "tier_summary": classified_df.groupby('Tier').agg({'Commodity': 'count', 'FY30_Savings_USDmillions': 'sum'}),
        "total_fy30_savings": classified_df['FY30_Savings_USDmillions'].sum()
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import sys
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Match ALL chemicals in TradeStat to substitution tiers")
    parser.add_argument("--excel-import", type=str, default="/Users/umashankar/Downloads/TradeStat-Eidb-Import-Commodity-wise.xlsx",
                        help="Path to TradeStat import Excel file")
    parser.add_argument("--output", type=str, default="market-pipeline/code/python_files/reports/chemical_universe_full_2026-08-01.csv",
                        help="Output CSV file")
    parser.add_argument("--summary", type=str, default="market-pipeline/code/python_files/reports/chemical_universe_summary_2026-08-01.txt",
                        help="Summary report file")

    args = parser.parse_args()

    print("=" * 100)
    print("FULL CHEMICAL UNIVERSE MATCHER (1900+ Chemicals)")
    print("=" * 100)

    # Parse TradeStat
    print(f"\n→ Parsing TradeStat EIDB from: {args.excel_import}")
    df = parse_tradestat_full(args.excel_import)
    print(f"  Loaded {len(df)} commodity lines")

    # Filter to chapters 28-40 (chemicals)
    df_chemicals = df[df['HSN_Chapter'].astype(str).isin(list(HSN_CHAPTERS.keys()))]
    print(f"  Filtered to chemical chapters (28-40): {len(df_chemicals)} chemicals")

    # Classify
    print(f"\n→ Classifying chemicals by substitution potential...")
    classified = classify_chemicals(df_chemicals)
    print(f"  Classified {len(classified)} chemicals into 5 tiers")

    # Generate statistics
    stats = generate_summary_statistics(classified)

    # Export
    print(f"\n→ Exporting results...")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    classified.to_csv(args.output, index=False)
    print(f"  ✓ Full universe CSV: {args.output}")
    print(f"    ({len(classified)} chemicals, {len(classified.columns)} columns)")

    # Export summary
    with open(args.summary, 'w') as f:
        f.write("=" * 100 + "\n")
        f.write("CHEMICAL IMPORT SUBSTITUTION: FULL UNIVERSE ANALYSIS\n")
        f.write("=" * 100 + "\n")
        f.write(f"\nAnalysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Data Source: TradeStat EIDB (FY2025-26)\n")
        f.write(f"Total Chemicals Analyzed: {len(classified)}\n")
        f.write(f"Total Chemical Imports: ${stats['total_imports']:.1f}bn\n")
        f.write(f"Total FY30 Savings Potential: ${stats['total_fy30_savings']:.1f}bn\n\n")

        f.write("TIER-WISE SUMMARY:\n")
        f.write("-" * 100 + "\n")
        for tier in ["Tier 1 (Load-bearing)", "Tier 2 (Dependent)", "Tier 2.5 (Quick-win)", "Tier 3 (Specialty)", "Monitor (Low priority)"]:
            tier_data = classified[classified['Tier'] == tier]
            if not tier_data.empty:
                count = len(tier_data)
                imports = tier_data['Import_FY25_26_USDmillions'].sum()
                savings = tier_data['FY30_Savings_USDmillions'].sum()
                f.write(f"{tier:40} | {count:4} chemicals | ${imports:7.1f}bn imports | ${savings:6.1f}bn FY30 savings\n")

    print(f"  ✓ Summary report: {args.summary}")

    print(f"\n✓ Processing complete")
    print(f"\nNEXT STEPS:")
    print(f"  1. Review chemical_universe_full_2026-08-01.csv for full 1900+ chemical list")
    print(f"  2. Filter by Tier to identify capex-ready vs. policy-dependent opportunities")
    print(f"  3. Cross-reference Quick-Wins for immediate implementation (60-75% substitution)")
    print(f"  4. Use High-Growth chemicals as supply-risk watchlist")
