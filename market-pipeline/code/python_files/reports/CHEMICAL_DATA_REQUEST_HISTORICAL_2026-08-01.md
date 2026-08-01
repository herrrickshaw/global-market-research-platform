# Chemical Import Substitution: Historical Data Request

**Date**: August 1, 2026  
**Purpose**: Enhance full universe analysis (2,719 chemicals) with historical trend analysis

## Summary
Current analysis covers FY2025-26 (point-in-time). To enable:
- 5-year trend analysis for supply-risk detection
- Capex project impact forecasting
- Government policy effectiveness tracking
- Quarterly monitoring dashboards

---

## Data Sources to Retrieve from Knowledge Graph / Repos

### TIER 1: HIGH-PRIORITY HISTORICAL DATA

#### 1. **Indian Market Data Database (15-Year Historical)**
**Location**: `global_expansion_screener_framework/INDIAN_MARKET_DATA_DB.md`  
**Scope**: Annual imports/exports for key chapters (28, 29, 31, 39, 40)  
**Timeline**: FY2010-11 → FY2025-26 (15 years)  
**Data Points Needed**:
- HSN 6-digit import values (USD)
- Import growth rates (YoY, CAGR)
- Export volumes (for trade balance)
- Price trends (unit value analysis)

**Action**:
```bash
# Extract from memory
grep -r "India.*import.*FY.*history" ~/.ruflo/data/ 
# Or load from parquet if available
python3 -c "import pandas as pd; df = pd.read_parquet('path/'); print(df[['HSN', 'FY', 'Import_USD']])"
```

#### 2. **Petrochemical Imports Substitution Tree (ICIS Data)**
**Location**: `refining/outputs/petchem_import_substitution.md`  
**Scope**: Ethylene, Propylene, PE, PP, TPA, PX family  
**Timeline**: FY2015-16 → FY2025-26 (full history)  
**Data Points Needed**:
- Chemical-wise import growth (to prioritize capex urgency)
- Capex project announcements + execution timelines
- India production capacity by chemical (to calculate gap)
- Import dependency ratios (% of supply from imports)

**Action**:
```bash
# Read ICIS tree summary
cat refining/outputs/petchem_import_substitution.md | grep -A 20 "Ethylene\|Propylene\|TPA"
```

#### 3. **Trade Price Parity Analysis (FY2023-24 → FY2025-26)**
**Location**: `report/trade-price-parity.md`  
**Scope**: Price indices for chemical commodities  
**Timeline**: Last 3 fiscal years (FY23-24, FY24-25, FY25-26)  
**Data Points Needed**:
- Unit value trends (USD/MT) for major chemicals
- Price volatility (standard deviation)
- Exchange rate impact on imports (INR/USD)
- Seasonal patterns (if monthly data available)

**Action**:
```bash
# Extract price trends
python3 << 'EOF'
import pandas as pd
df = pd.read_csv("report/trade-price-parity.md")
chemicals = ["Ethylene", "Propylene", "PE", "PP", "TPA"]
for chem in chemicals:
    print(f"{chem}: {df[df['Chemical']==chem][['FY', 'Unit_Value_USD_MT']].to_string()}")
EOF
```

---

### TIER 2: SUPPORTING HISTORICAL DATA

#### 4. **NSE/BSE Chemical Company Financials (Capex Tracking)**
**Source**: SEBI XBRL filings (nse_xbrl_results.py pipeline)  
**Scope**: RIL, IOCL, BPCL, HPCL capex announcements + actual spend  
**Timeline**: FY2022-23 → FY2025-26 (and guidance to FY2030)  
**Data Points**:
- Annual capex by project (BPCL AP, RIL O2C, L&T Bina, BHAVYA Parks)
- Actual vs. guidance variance (execution risk tracking)
- Capacity ramp timelines (from MD statements)

**Action**:
```python
# Extract from market-pipeline finials pipeline
python3 << 'EOF'
import yfinance as yf
companies = ["RELIANCE.NS", "IOCL.NS", "BPCL.NS", "HPCL.NS"]
for ticker in companies:
    info = yf.Ticker(ticker).quarterly_financials
    capex = info.loc['Capital Expenditures'] if 'Capital Expenditures' in info.index else None
    print(f"{ticker}: {capex}")
EOF
```

#### 5. **Government Policy Timeline & Incentives**
**Source**: PIB Press Releases (parliament-tracking pipeline)  
**Scope**: PLI scheme announcements, anti-dumping duty dates, GST changes  
**Timeline**: FY2020-21 → FY2025-26  
**Data Points**:
- PLI subsidy % by chemical family
- Anti-dumping duty implementation dates (dyes, TPA, etc.)
- PARIVESH environmental clearance timelines (for capex risk)
- Ministry announcements (DCPC targets, production targets)

**Action**:
```bash
# Extract from PIB archive
python3 ~/.ruflo/scripts/pib_index.py --query "chemical" --date-range "2020-01-01:2026-08-01"
```

---

### TIER 3: SUPPLEMENTARY DATA (Lower Priority)

#### 6. **Global Chemical Price Benchmarks**
**Source**: ICIS, Platts, Chemical Market Analytics (external)  
**Scope**: Global price indices for major chemical commodities  
**Timeline**: FY2020-21 → FY2025-26  
**Action**: Monitor public databases (CEIC, World Bank Commodity Prices)

#### 7. **Supply Chain Disruption Events**
**Source**: News archives, logistics databases  
**Scope**: COVID impacts, shipping rate spikes, sanctions on chemical suppliers  
**Timeline**: FY2020-21 → FY2025-26 (post-COVID analysis)

---

## Proposed Integration into Dashboards

### Analysis 1: Import Substitution Trajectory (5-Year Trend)
**Input**: Historical import values (Tier 1) + Current FY25-26  
**Output**: Regression forecasting (linear + polynomial) for FY30 baseline  
**Dashboard**: "Tier-wise Import Trends" (by chapter, commodity, growth rate)

**SQL Query Template**:
```sql
SELECT hsn_code, commodity, FY, import_value_usd
FROM historical_imports
WHERE chapter IN ('28', '29', '31', '39', '40')
  AND FY BETWEEN '2015-16' AND '2025-26'
  AND hsn_code IN (SELECT hsn_code FROM priority_chemicals)
ORDER BY FY, hsn_code;
```

### Analysis 2: Capex Project Impact Model (Before/After)
**Input**: Historical production capacity + announced capex + guidance  
**Output**: Capacity gap closure timeline (% substitution by year)  
**Dashboard**: "Capex Project Roadmap" (execution tracking, risk flags)

### Analysis 3: Supply Risk Index (Multi-Factor)
**Input**: Import growth (5y CAGR) + Price volatility + Concentration (% from single partner)  
**Output**: Risk-scored chemical watchlist  
**Dashboard**: "High-Risk Chemicals Monitor" (real-time, quarterly refresh)

---

## Data Collection Checklist

- [ ] **Retrieve 15-Year Import History** (by HSN 6-digit, annual)
  - Source: TradeStat EIDB historical export / World Bank / WITS
  - Action: `graphify path "Indian Market Data Database"`
  
- [ ] **Extract ICIS Petrochemical Tree** (Eth, Prop, PE, PP, TPA)
  - Source: Knowledge graph (`petchem_import_substitution.md`)
  - Action: Read markdown file + cross-ref ICIS cost curves
  
- [ ] **Pull Company Capex Guidance** (RIL, IOCL, BPCL, HPCL)
  - Source: SEBI XBRL filings (nse_xbrl_results.py) or Investor Presentations
  - Action: Parse Q4-FY26 earnings transcripts for FY27-30 guidance
  
- [ ] **Fetch PIB Announcements** (Chemicals, PLI, Anti-dumping)
  - Source: PIB API or pib_index.py snapshot
  - Action: Filter by "chemical" + "import" + "substitution" keywords
  
- [ ] **Gather Global Price Benchmarks** (Optional)
  - Source: CEIC, World Bank, ICIS public data
  - Action: Web scrape or load from CSV if saved locally

---

## Expected Outputs After Data Integration

1. **5-Year Import Trend Chart** (by tier, showing FY20-21 → FY25-26)
2. **Capex Impact Forecast** (% substitution by FY, for each project)
3. **Supply Risk Heatmap** (high-growth + concentrated supply = red flag)
4. **Quarterly Tracking Dashboard** (capex spend vs. guidance, timeline adherence)
5. **Policy Effectiveness Report** (PLI uptake, anti-dumping impact on volumes)

---

## Timeline

- **Immediate** (This week): Retrieve Tier 1 historical imports + ICIS tree
- **Short-term** (2 weeks): Integrate capex guidance + PIB announcements
- **Medium-term** (1 month): Build dashboard + risk index
- **Ongoing**: Quarterly refresh of imports, capex tracking, policy updates

---

## Contact & Notes

- All data sources to be validated against official TradeStat EIDB (spot checks)
- Confidentiality: Use only public/FOIA data (no proprietary ICIS subscriptions without license)
- Version Control: Save all historical datasets to `market-pipeline/data/chemical_history/` with timestamps

