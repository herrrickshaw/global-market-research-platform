# RUFLO All-Repos Graphify Index — Government + Financial Data Integration

## Master Repository Catalog

### Financial Analysis Repos (Live Trading & Research)

#### market-pipeline (primary, public)
- Daily scan (87.5k tokens → 73-81k post-opt)
- 5-market coverage (IN/US/EU/JP/KR)
- Data sources: Cassandra, yfinance, screener.in, EDGAR, XBRL
- Output: signal_outcomes.parquet, daily email (11.9k tokens)

#### global-stock-screener (public, LFS-backed)
- ltm/US.parquet (9,278 stocks, 10.5 years deep)
- Fundamental analytics database
- Connected to: market-pipeline (data source)

#### global-market-data (public, LFS archive)
- cache_seed/*.parquet (10.5-year OHLCV backups)
- Exchange-level survivorship bias verified
- Connected to: market-pipeline (fallback source)

#### put-call-parity (private, trading)
- Options arbitrage engine (BankNifty, Crude, Silver)
- 3-leg execution framework
- 7.1k tokens/day, 6 runs/week
- Connected to: NSE/MCX option chains (real-time)

#### india-trade-data-analysis (public, 2026-07-18)
- DGFT EIDB (India trade statistics)
- Descriptive analytics tier
- Monthly updates (15th of month)
- Connected to: MOSPI trade data, DGFT APIs

#### india-trade-sector-policy-recommendations (public, 2026-07-18)
- Policy prescriptive tier
- CSM (Cooperative Sugar Mill) M&A structures
- Ethanol/CBG/SATAT policy analysis
- Connected to: Government policy databases, Ministry sites

#### bms-battery-management (public, separated 2026-07-13)
- EV battery analysis
- Hyundai/BMS sourcing intelligence
- Connected to: Industry capex databases

#### stock-screener-platform (public, separated 2026-07-13)
- Multi-strategy screening framework
- Connected to: market-pipeline scanners

### Government & Policy Data Repos (Research & Analysis)

#### iudx-flood-collector (public, archived 2026-07-22)
- 77 flood sensors (Pune/Chennai/K-D)
- 3 access requests PENDING
- Daily ingestion (APD auth via raw identity token)
- Connected to: IUDX platform, city disaster management

#### agri-commodity-tracker (public, live)
- Agmarknet mandi prices (daily after 14:00 IST)
- 300+ mandis across India
- Cron: daily 14:30
- Connected to: Department of Agriculture, commodity exchanges

#### india-trade-tracker (public, live)
- DGFT EIDB scraper (Selenium-only, FY24-25 validated)
- Monthly refresh (15th)
- Cron: monthly 15th trade/WB
- Connected to: DGFT, World Bank API

#### digital-twin-for-ipa (public, 32-layer architecture)
- Incentive structure mapping (all 6 schemes)
- L31: IPA sources (WAIPA live-scrape, NDAP loadqa API)
- L32: Company database + 6 verification stages
- L33: Policy-finance (fisheries/PMMSY, bottling fees, duty posture)
- L34: Stressed-assets (rating-distress, IBC/NLMC/SARFAESI land pools)
- Connected to: MCA, GLEIF, EDGAR, 10+ corporate registries

#### vehicle-fuel-mileage (public, nested in $HOME)
- SIAM 303-model FE declarations
- E20/diesel/CNG/EV cost model
- Exchequer study integration
- Connected to: Ministry of Road Transport, SIAM, oil companies

#### focus-sector-investor-map (public, research)
- India-focused PE/VC mapping
- Deal origination (bioenergy, CSM, ethanol)
- Connected to: DPIIT, government incentive schemes

#### data-source-mining (public, archive)
- Historical data collection (various initiatives)
- Connected to: Multiple government sites

---

## Government Data Sources Catalog

### NODES: Government Datasets

#### Department of Agriculture (India)
- **Agmarknet** → Daily mandi prices (300+ mandis)
- **FCI Warehouses** → Food storage, MSP vs MSV
- **PMMSY** → Fisheries policy & financing
- **Agricultural Statistics** → Crop acreage, production, yield
- Freshness: Daily (after 14:00 IST)
- Collector: agri-commodity-tracker

#### Ministry of Commerce & Industry (India)
- **DGFT EIDB** → Export-import data (FY24-25)
- **PLI Scheme** → Production-linked incentives (sector breakdowns)
- **Tariff Schedules** → HSN codes, duty rates
- **Trade Flows** → Bilateral trade statistics
- Freshness: Monthly (15th)
- Collector: india-trade-tracker

#### Ministry of Road Transport (India)
- **SIAM 303 FE Declarations** → Vehicle fuel efficiency
- **Vehicle Registration** → Annual model-wise volumes
- **Driving Incentives** → E20/EV subsidies, tax incentives
- Freshness: Quarterly/Annual
- Connected to: vehicle-fuel-mileage repo

#### SEBI (Securities & Exchange Board of India)
- **DRHP Filings** → IPO pipeline (Selenium scraper)
- **Integrated Filing Results** → XBRL quarterly results (151,928 records)
- **Insider Trading** → Transaction tracking
- Freshness: Real-time (as filed)
- Collector: nse_xbrl_results.py, SEBI_web_scraper.ipynb

#### Ministry of Corporate Affairs (MCA)
- **Corporate Registry** → CIN, CapTable, prospectus
- **IBC Filing** → Insolvency proceedings (SARFAESI land pools)
- **MEIS/SEIS** → Scheme participation
- Freshness: Real-time (as registered)
- Collector: digital-twin-for-ipa (L32 verification)

#### Reserve Bank of India (RBI)
- **Forex Archive** → Historical exchange rates (~13mo stale)
- **RBI.org.in WSSView** → Enumerable archive to 1998 (no key needed)
- **Monetary Policy** → Rate decisions, inflation targets
- **Financial Stability** → Stress testing scenarios
- Freshness: Monthly/Quarterly
- Connected to: market-pipeline macro analysis

#### Ministry of Petroleum & Natural Gas
- **PSC Blocks** → Oil/gas exploration leases
- **Refinery Capacity** → Production, utilization
- **LNG Imports** → Terminal capacity, regasification
- Freshness: Quarterly
- Connected to: energy sector analysis

#### Ministry of Power
- **DISCOM** → Electricity distribution, debt, tariffs
- **Renewable Energy** → Capacity additions, targets
- **Grid Operations** → Frequency, stability data
- Freshness: Daily/Monthly
- Connected to: power sector policy analysis

#### Ministry of Labour & Employment
- **PLI Scheme Factories** → Plant locations, subsidies (E-Shram data)
- **Manufacturing Statistics** → Industry-wise employment
- **Wage Statistics** → Sectoral wage trends
- Freshness: Quarterly/Annual
- Connected to: industrial policy analysis

#### Ministry of Environment, Forest & Climate Change
- **PARIVESH** → Environmental clearances (EC schedule)
- **SEBI Filings** → ESG disclosures (parsed from DRHP)
- **Carbon Credit** → SATAT CBG scheme participation
- Freshness: Real-time (as filed)
- Connected to: saf-monitoring-system (feedstock/blending/airline)

#### Ministry of External Affairs (MEA)
- **Trade Agreements** → FTA text, negotiation status
- **Investment Treaties** → Bilateral investment protection
- **Visa Policy** → Incentive visas for investors
- Freshness: As updated
- Connected to: FDI promotion analysis

#### Lok Sabha & Rajya Sabha (Parliament)
- **PIB Releases** → Official government announcements
- **Parliamentary Questions** → Q&A (Sansad API, 18th-LS indexed)
- **Bills & Acts** → Legislation tracking
- Freshness: Real-time (as announced)
- Collector: pib_index.py, sansad_pq_api

#### NDAP (National Data & Analytics Platform)
- **Loadqa API** → Real-time government datasets
- **25 Datasets** → MOSPI connector (working 2026-07-18)
- Freshness: Daily to Monthly (varies by dataset)
- Connected to: digital-twin-for-ipa (L31 sources)

#### WAIPA (World Association of Investment Promotion Agencies)
- **Live Scrape** → Global incentive scheme directory
- **IPA Profiles** → State-wise investment promotion agencies
- Freshness: Weekly/Monthly
- Connected to: digital-twin-for-ipa (L31 sources)

---

### EDGES: Government Data Relationships

#### ingests_from_government
`Repository` → `Government Source`
- agri-commodity-tracker ingests from: Agmarknet (daily)
- india-trade-tracker ingests from: DGFT EIDB (monthly)
- market-pipeline ingests from: SEBI DRHP (real-time), NSE XBRL (real-time)
- put-call-parity ingests from: NSE/MCX option chains (real-time)
- digital-twin-for-ipa ingests from: MCA, SEBI, DPIIT (real-time/daily)
- vehicle-fuel-mileage ingests from: Ministry of Road Transport SIAM (quarterly)
- saf-monitoring-system ingests from: Ministry of Environment carbon credit (real-time)

#### cross_references_government
`Government Source` → `Government Source`
- SEBI DRHP cross-refs to: MCA CIN, RBI forex rates, Ministry PIB announcements
- DGFT EIDB cross-refs to: RBI forex (FY-average rates for ₹/USD conversion)
- E-Shram employment data cross-refs to: PLI scheme factories (Ministry of Labour)
- PARIVESH EC clearances cross-refs to: Ministry of Environment policy (SATAT, CBG)

#### validates_against_government
`Analysis` → `Government Source`
- Piotroski backtest validates against: SEBI DRHP earnings dates (no look-ahead)
- Valuation reversion validates against: SEBI XBRL fundamentals (quarterly-as-annual bug)
- Portfolio P&L validates against: Exchange statements (NSE/BSE settlement)
- Options parity validates against: NSE option chain (Greeks, settlement prices)

---

## MOSPI Integration (25 Datasets)

### MOSPI Datasets Connected

#### Economic Datasets
1. **Gross Domestic Product (GDP)** → National accounting, growth rates
2. **Industrial Production Index (IPI)** → Manufacturing output
3. **Consumer Price Index (CPI)** → Inflation, sectoral prices
4. **Producer Price Index (PPI)** → Wholesale price movements
5. **Foreign Exchange Reserves** → RBI data pipeline

#### Agricultural Datasets
6. **Agricultural Statistics** → Crop production, acreage
7. **Livestock Production** → Dairy, meat, poultry output
8. **Fisheries Data** → Aquaculture, capture production
9. **Food Security Monitoring** → FCI granaries, MSP tracking
10. **Agricultural Prices** → Mandi-wise, commodity-wise

#### Trade & Exports
11. **Merchandise Trade** → Bilateral, sectoral exports
12. **Services Trade** → IT, BPO, professional services
13. **Trade Agreements** → FTA utilization rates
14. **Export Incentives** → Scheme participation (PLI, MEIS)
15. **Commodity Prices** → Global, domestic correlation

#### Infrastructure & Utilities
16. **Power Generation** → Thermal, renewable, hydro capacity
17. **Renewable Energy** → Wind, solar MW added annually
18. **Railway Traffic** → Freight, passenger data
19. **Port Operations** → Cargo, container throughput
20. **Telecom Subscribers** → Wireless, broadband growth

#### Corporate & Industrial
21. **Stock Market Capitalization** → NSE, BSE indices, sector weights
22. **Corporate Sector Debt** → Bank loans, bond issuance
23. **Fixed Capital Formation** → Capex by sector
24. **Industrial Clusters** → MSME locations, specialization
25. **Labour Force Participation** → Employment, wages by sector

### Collector: mospi_connector.py (2026-07-18)
- Access via: NDAP loadqa API (no key required for MOSPI subset)
- Frequency: Daily to Monthly (varies by dataset)
- Storage: Parquet cache (25 files, one per dataset)
- Connected to: market-pipeline macro analysis, policy recommendations

---

## PIB Integration (Government Announcements)

### PIB Release Index

#### Collector: pib_index.py
- Data source: PIB releases (pib.gov.in)
- SQL index: By date × ministry
- Scope: All 25+ ministries
- Freshness: Real-time (as announced)
- Storage: SQLite index + Parquet (releases with announcements)

#### Connected Ministries (25+)
- Ministry of Commerce & Industry
- Ministry of Finance
- Ministry of External Affairs
- Ministry of Road Transport
- Ministry of Labour & Employment
- Ministry of Environment, Forest & Climate Change
- Ministry of Petroleum & Natural Gas
- Ministry of Power
- Ministry of Food Processing Industries
- Ministry of Agriculture & Farmers Welfare
- Department of Economic Affairs
- Department of Industrial Policy & Promotion (DPIIT)
- And 13+ others

#### Filtering Criteria
- Policy announcements (affects market analysis)
- Scheme launches (PLI, SATAT, CBG, PMMSY)
- Rate decisions (RBI monetary policy)
- Trade policy (tariffs, FTA negotiations)
- Corporate policy (insolvency, GST)

#### Integration Points
- daily_scan: Filter out announcements on earnings dates (look-ahead bias)
- valuation_reversion: Adjust for policy shocks (sector rotation triggers)
- portfolio_analysis: Flag announcement risk (around policy releases)
- put-call-parity: Model implied volatility (around PIB events)

---

## Cross-Repo Data Lineage

```
GOVERNMENT DATA INGESTION:
├─ MOSPI (25 datasets)
│  └─ mospi_connector.py → Parquet cache
│     └─ market-pipeline (macro context)
│
├─ PIB Releases (25+ ministries)
│  └─ pib_index.py → SQLite index
│     └─ All repos (announcement filtering)
│
├─ SEBI (Equities)
│  ├─ DRHP filings → SEBI_web_scraper.ipynb
│  │  └─ digital-twin-for-ipa (IPO pipeline)
│  └─ XBRL results → nse_xbrl_results.py
│     └─ market-pipeline (fundamentals)
│
├─ DGFT (Trade)
│  └─ india-trade-tracker (monthly)
│     └─ india-trade-data-analysis (descriptive)
│        └─ india-trade-sector-policy-recommendations (prescriptive)
│
├─ Agmarknet (Agriculture)
│  └─ agri-commodity-tracker (daily 14:00)
│     └─ market-pipeline (commodity futures context)
│
├─ Ministry of Road Transport (Vehicles)
│  └─ vehicle-fuel-mileage (SIAM FE declarations)
│     └─ Energy policy analysis
│
├─ Ministry of Environment (Environmental)
│  └─ PARIVESH clearances → saf-monitoring-system
│     └─ Feedstock/blending/carbon/airline reporting
│
└─ Corporate Registries (Global)
   ├─ MCA (India) → digital-twin-for-ipa (L32)
   ├─ GLEIF (Global) → digital-twin-for-ipa (L32)
   ├─ EDGAR (US) → global-stock-screener (fundamentals)
   ├─ DART (Korea) → market-pipeline (Korea coverage)
   └─ And 8+ others → corporate-registry-map (44 files)

ANALYSIS TIER:
├─ daily_scan (87.5k tokens)
│  └─ Ingests: Cassandra quotes + MOSPI macro + PIB news filter
│
├─ valuation_reversion_*.md (backtested)
│  └─ Ingests: SEBI XBRL dates + EDGAR SEC dates + MOSPI inflation
│
├─ portfolio_analysis (5.2k tokens)
│  └─ Ingests: yfinance + Agmarknet (commodity holdings context)
│
├─ india-trade-sector-policy-recommendations
│  └─ Ingests: DGFT EIDB + MOSPI IPI + PIB trade policy
│
└─ digital-twin-for-ipa
   └─ Ingests: MCA + GLEIF + SEBI + Ministry policies (32-layer model)

DELIVERY TIER:
├─ watchlist_mailer (11.9k tokens)
│  └─ Output: Daily email with MOSPI macro context
│
├─ signal_outcomes.parquet
│  └─ Validation: Signal accuracy filtered for PIB announcements
│
└─ Policy reports
   └─ Output: Quarterly policy recommendations
```

---

## Graphify Nodes (All Repos + Government)

### Repository Nodes (40+)
- market-pipeline (primary, token-tracked)
- global-stock-screener (US fundamentals, 9,278 stocks)
- global-market-data (10.5-year LFS cache)
- put-call-parity (options trading)
- india-trade-data-analysis (DGFT trade, descriptive)
- india-trade-sector-policy-recommendations (policy prescriptive)
- agri-commodity-tracker (Agmarknet mandi daily)
- india-trade-tracker (DGFT EIDB monthly)
- digital-twin-for-ipa (32-layer incentive model)
- vehicle-fuel-mileage (SIAM FE declarations)
- iudx-flood-collector (77 flood sensors, archived)
- saf-monitoring-system (K8s-ready, feedstock/blending/airline)
- bms-battery-management (EV battery analysis)
- stock-screener-platform (multi-strategy UI)
- focus-sector-investor-map (PE/VC bioenergy)
- And 25+ more (7 supporting repos archived 2026-07-22)

### Government Source Nodes (30+)
- Agmarknet (Department of Agriculture)
- DGFT EIDB (Ministry of Commerce)
- SEBI DRHP (IPO pipeline)
- SEBI XBRL (quarterly results, 151,928 records)
- NSE/MCX Option Chains (real-time)
- RBI Forex Archive (to 1998, no key)
- MCA Corporate Registry (CIN, CapTable)
- PARIVESH (environmental clearances)
- PIB Releases (25+ ministries, real-time)
- Sansad API (Parliamentary Q&A, 18th-LS indexed)
- MOSPI (25 datasets via NDAP)
- WAIPA (incentive schemes, live-scrape)
- And 18+ more (Ministry sites)

### Analysis Workflow Nodes (20+)
- daily_scan (87.5k → 73-81k tokens)
- watchlist_mailer (11.9k tokens)
- portfolio_analysis (5.2k tokens)
- piotroski_backtests (PIT validated)
- valuation_reversion_*.md (sector-relative PE)
- market_correlation_scan (daily 5-market)
- pegu_sarvas_analysis.R (NSE/BSE scoring)
- put_call_parity strategy (3-leg arbitrage)
- saf-monitoring-system (K8s reporting)
- digital-twin-ipa (32-layer model)

### Token Tracking Nodes (RUFLO)
- RUFLO Monitoring (central hub)
- .ruflo/data/token_usage.db (SQLite tracking)
- .ruflo/scripts/token-dashboard.sh (monitoring)
- Phase 1 optimizations (code)
- Week 1 validation (live)
- Phase 2 decision gate (pending)

---

## Graphify Edges (All Repos + Government)

#### ingests_from
`Repository` → `Government Source`
- market-pipeline ingests from: Cassandra, yfinance, SEBI XBRL, DGFT EIDB, MOSPI
- india-trade-tracker ingests from: DGFT EIDB
- agri-commodity-tracker ingests from: Agmarknet
- digital-twin-for-ipa ingests from: MCA, GLEIF, SEBI, DPIIT, WAIPA
- vehicle-fuel-mileage ingests from: Ministry of Road Transport
- saf-monitoring-system ingests from: Ministry of Environment

#### runs_analysis
`Repository` → `Analysis`
- market-pipeline runs: daily_scan, watchlist_mailer, piotroski_backtests
- india-trade-data-analysis runs: trade analysis workflows
- digital-twin-for-ipa runs: 32-layer incentive mapping

#### validates_against
`Analysis` → `Government Source`
- daily_scan validates against: PIB announcements (filter look-ahead bias)
- piotroski_backtests validates against: SEBI XBRL dates
- portfolio_analysis validates against: Exchange settlement data

#### produces_output
`Analysis` → `Delivery`
- daily_scan produces: signal_outcomes.parquet
- watchlist_mailer produces: daily email
- piotroski_backtests produces: backtest report
- digital-twin-ipa produces: policy recommendations

#### tracked_by
`Repository` → `RUFLO`
- market-pipeline tracked by: RUFLO (87.5k → 73-81k tokens/day)
- watchlist_mailer tracked by: RUFLO (11.9k tokens/day)
- portfolio_analysis tracked by: RUFLO (5.2k tokens/day)
- put_call_parity tracked by: RUFLO (7.1k tokens/day)

---

## Connected Analysis: Government + Market

### MOSPI Macro Context → Signal Accuracy

```
MOSPI Inflation (CPI) ↓
  └─ PE ratios compress (nominal earnings growth unchanged)
     └─ Valuation reversion signals ↑ (mean-revert faster)
        └─ market-pipeline: Filter signals by inflation regime
           └─ daily_scan: Adjust thresholds (recession vs growth)

MOSPI IPI (Industrial Production) ↑
  └─ Corporate earnings beat expectations
     └─ Piotroski F-score ↑ (earnings quality improves)
        └─ market-pipeline: Piotroski backtests outperform
           └─ portfolio_analysis: Sector rotation (cyclicals → defensives)

MOSPI Exports ↓ (Trade slowdown)
  └─ india-trade-tracker: DGFT volumes decline
     └─ india-trade-sector-policy-recommendations: Flag policy risk
        └─ market-pipeline: Filter out import-dependent sectors
           └─ Portfolio: Shift to domestic-focused stocks
```

### PIB Announcements → Opportunity Detection

```
PIB: "PLI Scheme Extended to 5 New Sectors"
  └─ digital-twin-for-ipa: L33 (policy-finance) updates
     └─ DPIIT incentive mapping refreshed
        └─ Focus-sector-investor-map: Bioenergy opportunity emerges
           └─ portfolio: New CSM M&A candidates identified
              └─ india-trade-sector-policy-recommendations: Policy brief updated

PIB: "RBI Rate Decision: +50 bps"
  └─ Implied volatility ↑ (options market reprices)
     └─ put-call-parity: Deviation thresholds tighten
        └─ Strategy: 3-leg arb becomes less profitable
           └─ Trade volume: Reduce position sizing, wait for clarity

PIB: "PARIVESH Environmental Clearance Process Streamlined"
  └─ Approval timeline ↓ (capex accelerates)
     └─ saf-monitoring-system: Feedstock/blending timelines improve
        └─ CSM/Distillery capex: Feasibility studies accelerate
           └─ digital-twin-ipa: Stressed-assets layer (land availability) updates
```

---

## Validation Metrics (All Repos)

### Data Quality
- [x] MOSPI 25 datasets indexed (NDAP loadqa API working)
- [x] SEBI XBRL 151,928 records dated (quarterly-as-annual bug identified)
- [x] PIB releases indexed by ministry (18th-LS Rajya Sabha data missing)
- [x] DGFT EIDB FY24-25 validated (Livewire Selenium scraper)
- [ ] Agmarknet 300+ mandis cross-ref to crop zones (seasonal pattern analysis)
- [ ] Corporate registry reconciliation (MCA vs GLEIF vs EDGAR coverage)

### Analysis Accuracy
- [ ] Macro signals (MOSPI inflation vs actual sector returns)
- [ ] Policy impact (PIB announcements → next-day price moves)
- [ ] Trade correlation (India exports vs China CPTPP participation)
- [ ] Incentive timing (PLI scheme announcement → investment flows)

### Integration Completeness
- 40+ repositories catalogued (21 archived, 19 active)
- 30+ government sources indexed (25 ministries)
- 5 markets scanned daily (IN/US/EU/JP/KR)
- 123,007 daily tokens tracked (across all tasks)

---

## Graphify Query Examples (All Repos)

### Find all government sources feeding market-pipeline
```
MATCH (repo:Repository {name: 'market-pipeline'}) 
  ← [ingests_from] ← (gov:GovernmentSource)
RETURN gov.name, gov.ministry, gov.freshness, gov.collector
ORDER BY gov.freshness DESC
```

### Trace PIB announcement impact on signal accuracy
```
MATCH (pib:GovernmentSource {name: 'PIB'}) 
  → [published] → (announcement:Event)
  ← [invalidates] ← (signal:Analysis)
RETURN announcement.date, announcement.ministry, signal.accuracy_before, signal.accuracy_after
WHERE announcement.date >= DATE('now', '-30 days')
```

### Cross-repository incentive scheme tracking
```
MATCH (repo1:Repository) → [tracks] → (scheme:Scheme)
  ← [implements] ← (repo2:Repository)
RETURN scheme.name, repo1.name, repo2.name, scheme.status, scheme.last_updated
ORDER BY scheme.budget_allocation DESC
```

### Model selection across all financial repos
```
MATCH (repo:Repository) → [runs] → (task:Task) 
  → [uses] → (model:Model)
RETURN repo.name, task.name, model.name, model.cost_per_token, model.quality_tier
ORDER BY repo.importance DESC, model.cost_per_token ASC
```

---

## Integration Status

- [x] 40 repos catalogued (market-pipeline, government data, policy)
- [x] 30 government sources indexed (MOSPI, PIB, SEBI, DGFT, Agmarknet)
- [x] 5 market collectors live (daily/monthly ingestion)
- [x] RUFLO token tracking across all tasks
- [x] Phase 1 code optimizations deployed (9-14k tokens/day)
- [x] Week 1 model upgrade live (3.5 Haiku)
- [ ] Graphify network rendering (visual graph all repos + gov sources)
- [ ] Cross-repo macro insights generated (MOSPI → signal filter)
- [ ] Policy impact dashboard (PIB announcements → opportunity detection)
- [ ] Phase 2 decision gate validation (Aug 3-10)

---

Generated: 2026-07-28
Status: All-Repos Graphify Index Ready for Integration
Coverage: 40 repos + 30 government sources + 5 daily collectors

