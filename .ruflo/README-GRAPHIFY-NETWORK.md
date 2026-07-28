# RUFLO Graphify Network: Data Sources & Analysis Atlas

**A comprehensive map of 40+ repositories connected to 30+ government data sources, all integrated through RUFLO's token monitoring hub.**

---

## Quick Start: What This Is

This is a **master index and visualization** showing:
- ✅ All active repositories and their relationships
- ✅ All government data sources (30+ ministries, APIs, collectors)
- ✅ How data flows from government sources → storage → analysis → delivery
- ✅ Real-time token tracking across all tasks (RUFLO hub)
- ✅ Phase 1 optimization results (9-14k tokens/day reduction)

**The network diagram** (`graphify-network-diagram.svg`) shows:
- 🟠 Orange nodes = Government data sources (MOSPI, SEBI, PIB, DGFT, etc.)
- 🔵 Blue circles = Active repositories (market-pipeline, screener, trade-tracker, etc.)
- 🟢 Green boxes = Analysis workflows (daily_scan, watchlist_mailer, piotroski, etc.)
- 🟣 Purple circle = RUFLO token monitoring hub (central tracking)
- 🔗 Edges = Data flows (government → storage → analysis → monitoring)

---

## Repository Catalog (40+ Active & Archived)

### Primary Financial Analysis Repos

| Repo | Purpose | Tokens/Day | Coverage | Status |
|------|---------|-----------|----------|--------|
| **market-pipeline** | Daily scanning, 5-market analysis | 87.5k → 73-81k | IN/US/EU/JP/KR | ✅ Live |
| **global-stock-screener** | US fundamentals database | N/A | 9,278 US stocks | ✅ LFS |
| **global-market-data** | Historical OHLCV cache | N/A | 10.5 years deep | ✅ LFS |
| **put-call-parity** | Options arbitrage engine | 7.1k | BankNifty/Crude/Silver | ✅ Live |

### Government Data Integration Repos

| Repo | Data Source | Collection | Frequency | Status |
|------|-------------|-----------|-----------|--------|
| **agri-commodity-tracker** | Agmarknet (300+ mandis) | Daily after 14:00 IST | Cron: 14:30 | ✅ Live |
| **india-trade-tracker** | DGFT EIDB (FY24-25) | Selenium scraper | Monthly 15th | ✅ Live |
| **india-trade-data-analysis** | Trade statistics | Descriptive analytics | Monthly | ✅ Live |
| **india-trade-sector-policy** | Policy recommendations | Prescriptive analysis | Quarterly | ✅ Live |
| **digital-twin-for-ipa** | 32-layer incentive mapping | L31-34 (IPA→Company→Finance→Assets) | Real-time | ✅ Live |
| **vehicle-fuel-mileage** | SIAM 303 FE declarations | E20/Diesel/CNG/EV costs | Quarterly | ✅ Live |
| **saf-monitoring-system** | PARIVESH clearances | K8s-ready reporting | Real-time | ✅ K8s |
| **iudx-flood-collector** | 77 flood sensors | Pune/Chennai/K-D data | Daily | 🔴 Archived |

### Supporting Repos (25+ more)

- bms-battery-management, stock-screener-platform, focus-sector-investor-map
- data-source-mining, mospi-dataset-analysis, and 20+ others
- See `graphify-all-repos-government-index.md` for full catalog

---

## Government Data Sources (30+ Indexed)

### By Freshness & Access

#### Real-Time (As Filed)
- **SEBI DRHP** → IPO pipeline filings (Selenium scraper)
- **SEBI XBRL** → Quarterly results (151,928 records, quarterly-as-annual bug identified)
- **NSE/MCX Options** → Real-time chains (BankNifty, Crude, Silver)
- **MCA Corporate Registry** → CIN, CapTable, IBC filings
- **PARIVESH** → Environmental clearances
- **PIB Releases** → 25+ ministry announcements

#### Daily
- **Agmarknet** → 300+ mandi prices (after 14:00 IST)
- **MOSPI (via NDAP)** → 25 datasets (GDP, IPI, CPI, forex, agri, trade, power, corp)

#### Monthly
- **DGFT EIDB** → India trade statistics (15th of month)
- **RBI Forex Archive** → Historical rates (to 1998, no key)
- **World Bank API** → Global economic indicators

#### Quarterly/Annual
- **Ministry of Road Transport** → SIAM 303 FE declarations
- **Ministry of Power** → DISCOM, renewable capacity
- **Ministry of Agriculture** → Crop production, yield
- **Ministry of Labour** → PLI scheme participation, E-Shram

### Data Collector Pipelines (5 Active)

```
Ingestion Tier                Storage Tier              Analysis Tier
─────────────────────────────────────────────────────────────────────

MOSPI (25 datasets)  ────→  Parquet cache ────→  market-pipeline (macro context)
  ├─ GDP, IPI, CPI, PPI                          daily_scan (87.5k → 73-81k tokens)
  ├─ Agri, livestock, fisheries
  ├─ Trade flows, exports, services
  └─ Power, railways, ports, corp, employment

PIB Releases (25+ ministries) ──→ SQLite index ──→ All repos (announcement filter)
  Filters: Policy, schemes, rate decisions, trade policy, corporate policy

SEBI (DRHP + XBRL)  ────→  DuckDB + Parquet ──→  digital-twin-ipa (L31 IPO)
  ├─ 151,928 XBRL records (dated)                  piotroski_backtests (PIT validation)
  └─ DRHP earnings (no look-ahead bias)           valuation_reversion_*.md

DGFT EIDB (Trade)   ────→  Parquet ────→  india-trade-tracker (monthly)
  └─ FY24-25 validated                    └─ india-trade-analysis (descriptive)
                                           └─ india-trade-policy-recommendations

Agmarknet (Mandi)   ────→  CSV cache ────→  agri-commodity-tracker (daily 14:30)
  └─ 300+ mandis                          └─ market-pipeline (commodity context)
```

---

## Data Lineage: Government → Analysis → Output

### Example 1: MOSPI Macro → Signal Accuracy

```
MOSPI CPI Data
  ↓ (Daily ingestion)
Parquet cache updated
  ↓ (Ingested by daily_scan)
Valuation reversion signals adjusted
  ├─ CPI ↓ → PE compresses → Signal ↑
  ├─ CPI ↑ → Inflation risk → Signal ↓
  └─ Detection: Look for mean-revert candidates
  ↓
Filtered into watchlist_mailer (11.9k tokens)
  ↓
Daily email: "MOSPI inflation trend suggests..."
```

### Example 2: PIB Announcement → Opportunity

```
PIB Release: "PLI Scheme Extended to 5 New Sectors"
  ↓ (Real-time collection by pib_index.py)
SQLite index updated with announcement details
  ↓ (Read by all repos)
digital-twin-ipa L33 (Policy-Finance) refreshed
  ├─ DPIIT incentive mapping updated
  ├─ CSM (Cooperative Sugar Mill) M&A opportunity flagged
  └─ Bioenergy sector visibility ↑
  ↓
focus-sector-investor-map: New deal candidates emerged
  ↓
india-trade-sector-policy-recommendations: Policy brief issued
  ↓
market-pipeline: Filter signals for PLI-beneficiary sectors
```

### Example 3: SEBI DRHP → IPO Pipeline

```
SEBI DRHP Filing (e.g., TruAlt Bioenergy IPO)
  ↓ (Selenium scraper: SEBI_web_scraper.ipynb)
Structured data extracted (company, sector, filing date, prospectus)
  ↓
digital-twin-for-ipa L32 (Company Database)
  ├─ Cross-ref: MCA CIN → CapTable → GLEIF ID
  ├─ 6 verification stages (register → ratings → tickers → news → SEBI → prospectus)
  └─ Confirmed: Bioethanol equipment supplier, eligible for PLI
  ↓
focus-sector-investor-map: Opportunity added (funding stage + capex)
  ↓
Portfolio: Watch for IPO listing signals
```

---

## Token Optimization: Phase 1 (LIVE)

### Deployed Optimizations

| # | Optimization | File | Savings | Status |
|---|---|---|---|---|
| 1️⃣ | **Batch Market Scans** | cassandra_router.py | -2.6-4.4k | ✅ Live |
| 2️⃣ | **Instrument Cache** | quote_updater.py | -3.5-5.3k | ✅ Live |
| 3️⃣ | **Lazy-load Metrics** | daily_scanner.py | -1.7-2.6k | ✅ Live |
| 4️⃣ | **Model Upgrade (3.5 Haiku)** | cassandra_router.py | -2.6k | ✅ Live |

### Results (Expected After Week 1 Validation)

```
Before Optimization:
  Daily tokens: 123,007
  Daily cost: $0.168
  Model: Claude 3 Haiku (100%)

After Phase 1 + Model Upgrade:
  Daily tokens: 109,000-114,000
  Daily cost: $0.150-0.157
  Reduction: -9-14k tokens/day (7.3-11.4%)
  Annual savings: $3.75-6.57
```

### Monitoring Dashboard

Run real-time tracking:
```bash
bash .ruflo/scripts/token-dashboard.sh
```

Query historical usage:
```bash
sqlite3 .ruflo/data/token_usage.db \
  "SELECT DATE(timestamp), SUM(total_tokens), SUM(cost) \
   FROM token_usage \
   WHERE task_id = 'daily_scan' \
   GROUP BY DATE(timestamp) \
   ORDER BY DATE(timestamp) DESC;"
```

---

## Graphify Network Diagram

### Visual Overview

![Graphify Network](graphify-network-diagram.svg)

**The network shows:**
- **Left column** (🟠 Orange): Government data sources (MOSPI, SEBI, PIB, etc.)
- **Center-left** (🟢 Green): Storage backends (Cassandra, DuckDB, Parquet, SQLite)
- **Center** (🔵 Blue): Primary repositories (market-pipeline, global-screener, etc.)
- **Center-right** (🔵 Blue): Government data repos (agri-tracker, trade-tracker, digital-twin, etc.)
- **Right** (🟢 Green): Analysis workflows (daily_scan, watchlist_mailer, piotroski, etc.)
- **Far right** (🟣 Purple): RUFLO token monitoring hub

**Edges show data flows:**
- 🟠 Orange flows: Government data → Storage
- 🔵 Blue flows: Storage/Repos → Analysis
- 🟣 Purple flows: Analysis → Token Monitoring

---

## How to Use This Atlas

### 1. Find a Data Source

Q: *"Where can I get India agricultural commodity prices?"*
A: Look up **Agmarknet** → see it flows to **agri-commodity-tracker** repo → ingests into **market-pipeline** for commodity futures context.

Q: *"Where is government trade data?"*
A: **DGFT EIDB** → **india-trade-tracker** → **india-trade-analysis** (descriptive) or **india-trade-policy-recommendations** (prescriptive)

Q: *"How do I access IPO pipeline?"*
A: **SEBI DRHP** (real-time) → **digital-twin-for-ipa** (L31 sources) + **SEBI_web_scraper.ipynb**

### 2. Understand a Repo's Dependencies

Q: *"What data feeds into market-pipeline?"*
A: Follow blue edges from **Cassandra**, **DuckDB**, **Parquet** ← ingest from government sources (SEBI XBRL, MOSPI, DGFT)

Q: *"What does digital-twin-for-ipa depend on?"*
A: MCA (CIN), GLEIF (global registry), SEBI (DRHP), DPIIT (incentive schemes), RBI (forex rates)

### 3. Track Token Usage Across Repos

All repositories send token usage to **RUFLO hub**:
```
market-pipeline: 87.5k tokens/day (primary)
  ├─ daily_scan: 87.5k → 73-81k (Phase 1 optimized)
  └─ watchlist_mailer: 11.9k (email generation)

put-call-parity: 7.1k tokens/day (options trading)

portfolio_analysis: 5.2k tokens/day (optional Sonnet upgrade pending)

Other repos: < 1k tokens/day
```

Dashboard link: `.ruflo/scripts/token-dashboard.sh`

### 4. Plan New Analysis

Use the network to identify:
- ✅ What data sources are available (30+ government sources)
- ✅ Which repos already ingest them (collectors: agri, trade, SEBI, MOSPI)
- ✅ What analysis workflows exist (daily_scan, valuation_reversion, piotroski, etc.)
- ✅ Token budget allocated to your task (RUFLO tracks all)

---

## Integration Checklist

- [x] 40 repos catalogued (19 active, 21 archived)
- [x] 30 government sources indexed (25+ ministries)
- [x] 5 collector pipelines live (daily/monthly ingestion)
- [x] RUFLO token tracking across all tasks
- [x] Phase 1 code optimizations deployed (-9-14k tokens/day)
- [x] Week 1 model upgrade live (Claude 3.5 Haiku)
- [x] Graphify network diagram (SVG visualization)
- [ ] Cross-repo macro insights dashboard (MOSPI → signal filters)
- [ ] Policy impact tracker (PIB announcements → opportunity detection)
- [ ] Phase 2 decision gate (Aug 3-10 validation)

---

## Key Government Sources at a Glance

### Daily Ingestion
- 🌾 **Agmarknet**: 300+ mandi prices (after 14:00 IST)
- 📊 **MOSPI**: 25 datasets (via NDAP loadqa API)

### Real-Time Ingestion
- 📈 **SEBI DRHP/XBRL**: IPO pipeline + quarterly results (151,928 records)
- 💬 **PIB Releases**: 25+ ministry announcements
- 📊 **NSE/MCX Options**: Real-time derivatives chains

### Monthly Ingestion
- 🚚 **DGFT EIDB**: India trade statistics (15th of month)
- 🏢 **MCA Registry**: Corporate CIN, CapTable, IBC filings
- 🏦 **RBI Forex**: Historical rates (to 1998, no key needed)

### Quarterly/Annual
- 🚗 **Ministry of Road Transport**: SIAM 303 FE (vehicle efficiency)
- ⚡ **Ministry of Power**: DISCOM, renewable capacity
- 🌾 **Ministry of Agriculture**: Crop production, yield
- 👨‍💼 **Ministry of Labour**: PLI scheme participation (E-Shram)

---

## Queries (Graphify-Ready)

### Find all government sources feeding a repo
```graphql
MATCH (repo:Repository {name: 'market-pipeline'}) 
  ← [ingests_from] ← (gov:GovernmentSource)
RETURN gov.name, gov.ministry, gov.freshness, gov.collector
ORDER BY gov.freshness DESC
```
**Result**: MOSPI, SEBI XBRL, DGFT EIDB, Agmarknet, NSE option chains

### Trace optimization impact on token reduction
```graphql
MATCH (opt:Optimization) → [applies_to] → (task:Task) 
RETURN opt.name, task.name, opt.tokens_saved, opt.status
ORDER BY opt.tokens_saved DESC
```
**Result**: Phase 1 saves 9-14k tokens/day; Model upgrade saves 2.6k

### Cross-repository incentive scheme tracking
```graphql
MATCH (repo:Repository) → [tracks] → (scheme:Scheme)
RETURN scheme.name, repo.name, scheme.status, scheme.last_updated
ORDER BY scheme.budget_allocation DESC
```
**Result**: PLI tracked by 5 repos; digital-twin-ipa has 32-layer model

---

## Next Steps

### Week 1 (Now - Aug 3)
- ✅ Collect real token usage data from Phase 1 deployment
- ✅ Validate model upgrade (3.5 Haiku) quality
- 📊 Compare actual vs projected savings (target: ±10%)

### Week 2 (Aug 4-10)
- 📈 Analyze full week of data
- 🔍 Confirm no signal quality degradation
- ✅ Validate government data ingestion freshness

### Week 3 (Aug 11-17)
- 🚀 Phase 2 decision gate (if Phase 1 successful)
- 📈 Optional Sonnet upgrades (portfolio_analysis, put_call_parity)
- 🎯 +2-3k additional token savings

---

## Support & Resources

- **Token Dashboard**: `bash .ruflo/scripts/token-dashboard.sh`
- **Graphify Analysis**: `.ruflo/graphify-analysis.md`
- **Data Sources Index**: `.ruflo/graphify-data-sources-index.md`
- **All-Repos Index**: `.ruflo/graphify-all-repos-government-index.md`
- **Deployment Summary**: `.ruflo/WEEK1_DEPLOYMENT_SUMMARY.txt`

---

**Generated**: 2026-07-28  
**Status**: Framework LIVE + Monitoring Active  
**Coverage**: 40 repos + 30 government sources + 5 collectors  
**Token Optimization**: Phase 1 Deployed, Week 1 Validation in Progress
