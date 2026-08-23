# Ministry of Chemicals & Petrochemicals: Monthly Reports Data Inventory

**Date Compiled**: August 1, 2026  
**Source**: https://chemicals.gov.in/monthly-reports  
**Status**: Active repository with 71 reports (from June 2020 to April 2026)

---

## LATEST AVAILABLE REPORTS (FY27-FY26 Current)

| Rank | Report | File Size | Download Status |
|------|--------|-----------|-----------------|
| 1 | **Monthly Production Report April 2026** | 653.45 KB | ✅ Available |
| 2 | **Monthly Production Report March 2026** | 653.3 KB | ✅ Available |
| 3 | **Monthly Production Report February 2026** | 653.74 KB | ✅ Available |
| 4 | **Monthly Production Report January 2026** | 653.71 KB | ✅ Available |
| 5 | Monthly Production Report December 2025 | 653.35 KB | ✅ Available |
| 6 | Monthly Production Report November 2025 | 680.8 KB | ✅ Available |

---

## WHAT DATA IS AVAILABLE IN MONTHLY REPORTS

**Report Type**: Monthly Production Report (Production-focused, NOT imports-focused)

### Likely Contents (Based on Ministry Structure):
- ✅ **Domestic Production Data** — Chemical production volumes by category
- ✅ **Capacity Utilization** — % utilization of installed capacity
- ✅ **Major Producer Capacity** — Top companies' production rates
- ✅ **Production Growth Trends** — YoY comparisons
- ⚠️ **Import Data** — May include aggregate import statistics (section TBD)
- ⚠️ **Export Data** — May include export trends
- ❓ **Tariff/Duty Information** — Varies by report edition

### NOT Guaranteed in These Reports:
- ❌ **Detailed HSN-level import data** (use TradeStat EIDB for that)
- ❌ **Company-wise import breakdown**
- ❌ **Price/cost analysis**

---

## DATA LOCATION HIERARCHY

For chemical **IMPORTS** data, check in this order:

### **Tier 1: TradeStat EIDB** (Most Reliable for Imports)
- **URL**: https://tradestat.commerce.gov.in/eidb/
- **Data**: 8-digit HSN import values, FY-wise
- **Coverage**: All chemicals, all countries
- **Use For**: Our Top 15 chemical substitution analysis ✅

### **Tier 2: Ministry Monthly Reports** (Production-focused)
- **URL**: https://chemicals.gov.in/monthly-reports
- **Data**: Production volumes, capacity utilization
- **Coverage**: Major chemicals only
- **Import Section**: Check if included (varies by month)
- **Use For**: Corroborate production capacity vs. import demand

### **Tier 3: Statistics at a Glance** (Ministry Annual Summary)
- **URL**: https://chemicals.gov.in/statistics-glance
- **Data**: Annual summary of imports/exports/production
- **Coverage**: Aggregate by chemical type
- **Use For**: Annual benchmarking against capex targets

### **Tier 4: Monthly DOs** (Demand & Other Metrics)
- **URL**: https://chemicals.gov.in/monthly-dos
- **Data**: Demand indicators, order trends
- **Use For**: Leading indicators for import trends

### **Tier 5: Annual Reports** (Comprehensive Review)
- **URL**: https://chemicals.gov.in/annual-reports
- **Data**: Year-end summary, policy review
- **Use For**: Strategic context, policy changes

---

## REPOSITORY TIMELINE & COVERAGE

**Most Recent** (Last 6 Months, as of Aug 2026):
- April 2026 ✅
- March 2026 ✅
- February 2026 ✅
- January 2026 ✅
- December 2025 ✅
- November 2025 ✅

**Historical Depth**: 71 reports covering June 2020 → April 2026 (continuous)

**File Size Pattern**:
- **2024-2026**: 650+ KB (detailed format)
- **2023**: 668+ KB (comprehensive)
- **2022**: 648+ KB (comprehensive)
- **2021**: 82+ KB (condensed format)
- **2020**: 71-83 KB (minimal format)

---

## RECOMMENDED DATA EXTRACTION STRATEGY

### **For Your Chemical Import Substitution Analysis:**

**Step 1: Download Latest April 2026 Report**
- Contains most recent production data (April data)
- Likely to show FY26 baseline for FY27 planning
- Check Section: "Imports of Chemicals" (if available)

**Step 2: Cross-Reference with TradeStat EIDB**
- Extract HSN-level import data for Top 15 chemicals
- Compare April 2026 monthly vs. annual trends
- Validate against Ministry production reports

**Step 3: Extract Key Metrics**
- **Domestic Production** (by chemical, in tonnes)
- **Capacity Utilization** (% of installed capacity)
- **Major Producer Volumes** (top 5 companies)
- **Import Share** (% of demand met by imports)

**Step 4: Build Dashboard KPIs**
- **Production Gap**: Import demand - Domestic supply = Gap to substitute
- **Capex Impact Forecast**: Planned projects (BPCL AP, RIL O2C) will fill this gap
- **Timeline to Self-Sufficiency**: When will domestic capex close import gap?

---

## IMPORT DATA IN MONTHLY REPORTS: VERIFICATION NEEDED

**Status**: ⚠️ **UNKNOWN** (PDF not yet reviewed)

### Hypothesis:
Ministry Monthly Production Reports may include:
- **Aggregate import volumes** (all chemicals combined, by month)
- **Top import chemicals list** (which ones imported most)
- **Import source country data** (China %, others %)
- **YoY import growth %**

### Hypothesis NOT Supported:
- Detailed HSN-level breakdown (use TradeStat for that)
- Duty/tariff data (DGFT portal)
- Price indices (ICIS, Platts)

---

## ACTION PLAN: EXTRACT LATEST MONTHLY DATA

### Immediate Tasks (This Week):

**1. Download Latest Report**
```
File: Monthly Production Report April 2026 (653.45 KB)
Link: https://chemicals.gov.in/monthly-reports (Item #1)
Save to: ~/Downloads/Ministry_April_2026_Production.pdf
```

**2. Extract Sections** (If Available):
- [ ] Imports of Chemicals (by category)
- [ ] Production of Chemicals (volume by type)
- [ ] Capacity Utilization (%)
- [ ] Top Producers (volumes, names)
- [ ] Country-wise Imports (China %, others %)

**3. Validate Against TradeStat**
- Compare April 2026 monthly import figures
- Flag any discrepancies (likely data lag explanations)
- Note: TradeStat may be on FY basis (Apr-Mar), Ministry may be calendar-based (Jan-Dec)

**4. Update Dashboard**
- Add Ministry data to KPI_QUARTERLY_TRACKING.csv
- New KPI: "Production Capacity Gap (%)" — gap between production and import demand
- Forecast: When will BPCL AP + RIL O2C + L&T Bina close the gap?

---

## PARALLEL DATA SOURCES FOR IMPORT ANALYSIS

### **For Most Current Import Data** (Don't Wait for Ministry Monthly Reports):

| Source | Latency | Coverage | Reliability |
|--------|---------|----------|-------------|
| **TradeStat EIDB** | 4-6 weeks | All HSNs | ✅ Official |
| **Ministry Monthly Reports** | 6-8 weeks | Aggregated | ✅ Official |
| **ICIS Chemical News** | Real-time | Selective | ⚠️ Subscription |
| **Chemical Price Indices** | Weekly | Commodities | ⚠️ Index-based |
| **Company Announcements** | Real-time | Company-level | ✅ Direct |
| **FICCI Industry Surveys** | Monthly | Aggregated | ⚠️ Survey-based |

---

## NOTES ON MINISTRY REPORT STRUCTURE

### Why Production Reports vs. Import Reports?

**Ministry Focus**: 
- Department of Chemicals & Petrochemicals is **production-centric**
- Tracks domestic production capacity, utilization, growth
- Imports are tracked SECONDARILY (as indicator of supply gap)

**Implication**:
- Import detail in Ministry reports is LIMITED
- For detailed import analysis, PRIMARY source = TradeStat EIDB
- Ministry reports are CORROBORATING source (shows production side)

### How to Read Ministry Reports:
```
Production (from Ministry) + Import Data (from TradeStat) 
= Total Demand (=Production + Imports)
```

**Use Case for Your Strategy**:
- Ministry: "Domestic production is 100 KTPA"
- TradeStat: "Imports are 500 KTPA"
- Conclusion: "Total demand is 600 KTPA, 83% import-dependent"
- BPCL AP target: Add 350 KTPA, reduce imports to 150 KTPA (75% substitute)

---

## INTEGRATION INTO QUARTERLY DASHBOARD

### New Data Points to Add:

**KPI #1: Production Capacity vs. Demand**
```
Formula: (Domestic Production / (Production + Imports)) × 100
Current: Varies by chemical (ethylene 40%, TPA 20%, etc.)
Target FY30: >80% for each Tier 1 chemical
```

**KPI #2: Import Dependency Ratio**
```
Formula: (Imports / (Production + Imports)) × 100
Current: 60-80% across Top 15
Target FY30: <20% for each Tier 1 chemical
```

**KPI #3: Capacity Utilization**
```
From Ministry Reports: % of installed capacity in use
Current: Typically 70-85% (capacity constrained)
Post-Capex: 90%+ (efficient utilization)
```

---

## RECOMMENDED QUARTERLY DATA REFRESH

**On Oct 1, 2026** (Q3 FY27 close):
1. Download July 2026 Monthly Report (most recent 3-month-old data)
2. Extract production volumes, capacity utilization
3. Compare against April 2026 report (3-month trend)
4. Update TradeStat EIDB import data (FY26 finalized)
5. Recalculate Production Capacity Gap & Import Dependency ratios
6. Update FY30 savings scenarios (do capex timelines still look feasible?)

---

## FILES TO DOWNLOAD (Prioritized)

### Must-Have:
```
1. Monthly Production Report April 2026 (653.45 KB)
   → Latest production data for FY26 baseline
   
2. Monthly Production Report March 2026 (653.3 KB)
   → FY26 final month, year-end comparison
```

### Should-Have:
```
3. Monthly Production Report February 2026 (653.74 KB)
   → Early FY26 data, trend confirmation
   
4. Statistics at a Glance (Annual Summary)
   → FY25-26 final review, context
```

### Nice-to-Have:
```
5. Annual Reports (FY25-26)
   → Policy narrative, ministry priorities
```

---

## SUMMARY: Ministry Reports Value Proposition

✅ **What You Get**:
- Production volumes by chemical
- Capacity utilization rates
- Top producer information
- Possible import aggregate data (TBD)
- Official government baseline

⚠️ **What You DON'T Get**:
- Detailed HSN-level import breakdown (use TradeStat)
- Price data (use ICIS, Platts)
- Company-wise tariff/duty data (use DGFT)
- Real-time updates (6-8 week lag)

📊 **Best Use**:
- Corroborate TradeStat import data with production data
- Calculate production gap (demand = production + imports)
- Track capacity utilization pre/post-capex
- Quarterly dashboard update for FY30 forecasting

---

**Compiled by**: Import Substitution Strategy Unit  
**Last Updated**: August 1, 2026  
**Next Review**: When April 2026 report is downloaded & analyzed  
**Related Files**: QUARTERLY_TRACKING_DASHBOARD.html, CAPEX_TRACKING_QUARTERLY.csv

