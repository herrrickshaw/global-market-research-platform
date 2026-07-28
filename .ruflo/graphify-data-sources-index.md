# RUFLO Data Sources & Analysis Index — Graphify Connected Format

## Data Source Catalog

### NODES: Data Sources

#### Market Data Sources (Live)
- **NSE (India)** → OHLCV + fundamentals via yfinance
- **BSE (India)** → Equity listings
- **US (NASDAQ/NYSE)** → OHLCV via yfinance
- **Europe (17 exchanges)** → OHLCV via yfinance
- **Japan (TSE)** → OHLCV via yfinance
- **Korea (KRX)** → OHLCV via yfinance
- **China (A-shares)** → Via akshare

#### Cache/Persistent Storage
- **Cassandra** → Real-time quotes, instrument lists (herrrickshaw keyspace)
- **DuckDB** (`data/market_data.duckdb`) → Reference tables (europe_all_list, london_list, etc.)
- **Parquet Files** (`cache_seed/`) → Historical OHLCV (10.5 years deep)
- **SQLite** (`.ruflo/data/token_usage.db`) → Token monitoring

#### Fundamental Data Sources
- **screener.in** → 10-year India fundamentals (NSE/BSE)
- **SEC EDGAR** → 20+ years US filings
- **yfinance** → 5-year quarterly fundamentals (PE, ROE, D/E, market cap)
- **XBRL results** (`nse_xbrl_results.py`) → India SEBI filings (151,928 records)
- **MCA** → Corporate registry (CapTable, CIN, prospectus)

#### Derivative Data Sources
- **NSE Options Chain** → BankNifty, index options (real-time)
- **MCX** → Crude Oil, Silver futures & options
- **Exchange feeds** → OI, volume, Greeks

#### Market Calendar & Events
- **NSE/BSE Holiday Calendar** → Trading days
- **Economic Events** → RBI, SEBI announcements
- **Earnings Calendar** → Quarterly results
- **IPO Pipeline** → DRHP filings (SEBI scraper)

#### External Datasets (Cross-Border)
- **World Bank API** → GDP, FX, commodity prices
- **IMF** → Fiscal data, IMF rates
- **ECB** → European central bank rates
- **Reuters/Bloomberg** → News feeds (integrated)
- **Agmarknet** → India agricultural commodity mandi prices
- **DGFT** → India trade statistics (EIDB)

#### Collector Pipelines
- **bhavcopy_history.py** → NSE bulk OHLCV (2,681 stocks in 2-3 hours)
- **screener_history_collector.py** → India fundamentals (10y, 151,928 filings)
- **edgar_collector.py** → US SEC EDGAR (20+ years)
- **market_correlation_scan.py** → Daily correlation matrices (5 markets)
- **nse_xbrl_results.py** → India SEBI quarterly filings
- **iudx-flood-collector** → Sensor data (77 flood sensors, 3 cities)
- **agri-commodity-tracker** → Mandi prices (daily after 14:00 IST)
- **india-trade-tracker** → DGFT EIDB data (monthly on 15th)

---

### EDGES: Data Source Relationships

#### ingests_from
`Task` → `Data Source`
- daily_scan ingests from: Cassandra (quotes), DuckDB (europe list)
- watchlist_mailer ingests from: Cassandra (instrument data)
- portfolio_analysis ingests from: Parquet (historical OHLCV)
- bulk_fetcher ingests from: yfinance (live quotes)
- screener_history_collector ingests from: screener.in (10-year fundamentals)
- edgar_collector ingests from: SEC EDGAR (US filings)

#### populates
`Collector` → `Storage`
- bhavcopy_history populates: Parquet (cache_seed/IN_*.parquet)
- screener_history_collector populates: DuckDB (fundamental tables)
- edgar_collector populates: Parquet (US fundamentals)
- bulk_fetcher populates: Cassandra (stock_quotes table)
- nse_xbrl_results populates: DuckDB (india_xbrl_filings)
- market_correlation_scan populates: Parquet (correlation matrices)

#### depends_on
`Source` → `Source`
- Cassandra depends on: yfinance (initial seed), DuckDB (reference tables)
- DuckDB depends on: yfinance (europe list rebuild >30 days old)
- Parquet cache depends on: Direct exchange feeds (bhavcopy, EDGAR)
- Portfolio analysis depends on: Historical OHLCV + fundamentals

#### cross_references
`Source` → `Source`
- India tickers (NSE/BSE) cross-ref to: ISIN, sector, industry
- US tickers cross-ref to: CUSIP, SEDOL, sector
- Europe tickers cross-ref to: ISIN, country, exchange code

---

## Analysis & Computation Index

### NODES: Analysis Workflows

#### Scanning & Screening
- **daily_scanner.py** → Darvas Box (real-time) + Piotroski (with fundamentals)
- **coffee_can.py** → Coffee Can buy-and-hold (ROE + durability)
- **piotroski.py** → Full 9-point Piotroski (requires Screener CSV)
- **screener_kit.py** → Multi-scanner orchestration

#### Fundamental Analysis
- **pegu_sarvas_analysis.R** → Pegu score + Sarvas momentum (NSE/BSE)
- **data_validator.py** → Data quality checks (leakage, distributions)
- **price_adjuster_global.py** → Stock split/dividend adjustment (JP/KR verified)
- **valuation_reversion_*.md** → Sector-relative PE reversion (India, US, EU, KR)

#### Portfolio & Risk
- **portfolio_analysis.py** → P&L, RSI signals, dividend history
- **risk_management.csv** → Position sizing, Greeks for options
- **strategy_matrix.py** → Market character suitability (IN momentum, KR mean-revert)
- **cost_vs_edge.py** → Illiquidity edge analysis (Corwin-Schultz + Amihud)

#### Options & Derivatives
- **put_call_parity.strategy** → 3-leg arbitrage (BankNifty, Crude, Silver)
- **option_chain_snapshot.json** → Historical options data for backtesting
- **parity_engine.py** → Deviation detection & cost-adjusted signals

#### Cross-Market & Macro
- **market_performance.py** → YoY returns by market (India/US/EU/JP/KR)
- **market_correlation_scan.py** → Daily correlations (5 markets)
- **liquidity_scan_*.py** → Liquidity predicts quality & returns (split by scan type)
- **global_strategy_analysis.py** → 7-market variance (Piotroski dominates? Not really.)

#### Data Quality & Completeness
- **data_check_2026-07-25.md** → Reconciliation report (OHLCV, fundamentals)
- **ticker_freshness.csv** → Age of last quote (21,279 tickers tracked)
- **data_completeness_audit.py** → % coverage by market (validates global_stock_screener vs global_market_data)

#### Backtesting & Validation
- **piotroski_backtests.parquet** → Point-in-time results (US EDGAR, India screener.in)
- **valuation_reversion_[market].md** → PIT backtest reports (validated)
- **liquidity_vs_scan_pass.md** → Liquidity impact on scan results (single-day cross-sections only)
- **signal_outcomes.parquet** → Real signals vs realized returns (validation database)

#### Reporting & Delivery
- **build_mailer.py** → Daily market brief assembly (10 sections)
- **send_mailer.py** → Email dispatch via n8n (06:00 workflow)
- **darvas_breakouts.py** → Fresh breakout detection (India/US/Europe only)
- **news_picks.py** → Headline-driven sentiment picks

---

### EDGES: Analysis Workflows

#### transforms
`Source Data` → `Analysis`
- Cassandra quotes → daily_scan
- Screener CSV → piotroski.py, coffee_can.py, darvas.py
- 10-year parquet → valuation_reversion_*.md
- NSE/BSE yfinance → pegu_sarvas_analysis.R

#### validates
`Analysis` → `Quality Gate`
- daily_scanner output → Match rate check (BUY signals vs realized moves)
- piotroski backtest → PIT validation (EDGAR/screener.in dates exact)
- portfolio_analysis → P&L reconciliation (vs broker statements)
- market_correlation → Sanity checks (correlation bounds, diversification)

#### produces
`Analysis` → `Output Artifact`
- daily_scan → signal_outcomes.parquet (log for validation)
- piotroski_backtests → piotroski_backtests.parquet
- valuation_reversion → *.md reports + charts
- build_mailer → HTML email + plain-text summary

#### depends_on
`Analysis` → `Data Source`
- daily_scan depends on: Cassandra (real-time quotes)
- piotroski.py depends on: Screener CSV (fundamentals required)
- portfolio_analysis depends on: yfinance (historical prices, dividends)
- put_call_parity depends on: Exchange option chain API

---

## Repository-to-Analysis Mapping

### NODES: Repository Contexts

#### market-pipeline (primary)
```
market-pipeline/
├── daily_pipeline.sh ← Orchestrates daily tasks
├── run_pegu_sarvas.sh ← R pipeline for scoring
├── run_app.sh ← Backend + frontend startup
└── code/python_files/
    ├── build_mailer.py → Outputs daily email (11.9k tokens/day)
    ├── screener_kit.py → Multi-scanner UI
    ├── portfolio_analysis.py → P&L analysis (5.2k tokens/day)
    ├── daily_scanner.py → Darvas/Piotroski (3 variants)
    ├── pegu_sarvas_analysis.R → Scoring pipeline
    ├── market_performance.py → YoY returns
    ├── market_correlation_scan.py → Daily correlations
    ├── liquidity.py → Liquidity annotations
    ├── stock_metrics_nse.py → NSE-specific metrics
    ├── nse_bse_extractor.py → Instrument list refresh
    ├── bhavcopy_history.py → Bulk NSE OHLCV
    ├── screener_history_collector.py → 10-year fundamentals
    ├── data_validator.py → Quality framework
    ├── price_adjuster_global.py → JP/KR split validation
    └── reports/ ← Output artifacts
        ├── piotroski_backtests.parquet
        ├── signal_outcomes.parquet
        ├── ticker_freshness.csv
        └── valuation_reversion_*.md
```

#### backend (FastAPI)
```
backend/
├── routers/
│   ├── cassandra_router.py → daily_scan (87.5k → 73-81k tokens/day)
│   ├── live.py → yfinance fetch
│   ├── portfolio.py → Portfolio P&L
│   ├── scan.py → Screener CSV scan
│   └── sectors.py → Damodaran benchmarks
├── db/
│   ├── cassandra_client.py → Connection pool
│   ├── quote_updater.py → Stock quote writes (+ instrument cache Phase 1)
│   ├── bulk_fetcher.py → yfinance batch fetch
│   └── seeder.py → Instrument list load
└── scanners/
    ├── daily_scanner.py → Core Darvas+Piotroski (+ lazy-load Phase 1)
    └── coffee_can.py → Coffee Can filter
```

#### put-call-parity (specialized)
```
put-call-parity/
├── main.py → Entry point (live or --backtest)
├── config.py → Credentials, thresholds (live 6 runs/week, 7.1k tokens/day)
├── parity_engine.py → Deviation math
├── strategy.py → Expiry selection, OI filtering
├── trade_manager.py → 3-leg execution
├── broker.py → KiteBroker, UpstoxBroker, AngelBroker adapters
├── option_chain_snapshot.json ← Backtest data
└── positions.json ← Active positions (persisted)
```

#### Supporting Repos
- **global-stock-screener** → ltm/US.parquet (9,278 stocks)
- **global-market-data** → cache_seed/*.parquet (10.5-year LFS backups)
- **repo-traffic-analytics** → GitHub clone/view snapshots (40 repos tracked)
- **india-trade-data-analysis** → DGFT EIDB (descriptive)
- **india-trade-sector-policy-recommendations** → Policy tier
- **agri-commodity-tracker** → Agmarknet mandi daily
- **saf-monitoring-system** → Feedstock/blending/carbon/airline reporting (K8s-ready)

---

## Connected Data Flow: End-to-End

```
INGESTION TIER (24h cycle):
  Exchange APIs
    ├─→ yfinance (all markets)
    ├─→ NSE bhavcopy bulk (2,681 stocks)
    ├─→ SEC EDGAR (quarterly filings)
    ├─→ screener.in export (India fundamentals)
    └─→ MCX/NSE options chains
       │
       ↓
  Collectors (bhavcopy_history.py, edgar_collector.py, etc.)
       │
       ↓
  STORAGE TIER
    ├─ Cassandra (real-time, seeded daily)
    ├─ DuckDB (reference tables, europe_all_list rebuild >30d)
    ├─ Parquet cache_seed/ (10.5y OHLCV, LFS-backed)
    └─ Parquet reports/ (backtest results, signals)
       │
       ↓
SCANNING TIER (07:00 IST daily)
  daily_scan (all 5 markets, 87.5k tokens)
    ├─ Phase 1: OHLCV+RSI-compatible Darvas
    ├─ Lazy-load metrics (Phase 1 opt)
    ├─ Output: BUY/WATCH/HOLD per ticker
    └─ → signal_outcomes.parquet (validation log)
       │
       ├─→ watchlist_mailer (11.9k tokens)
       │   └─ 10-section HTML email
       │      (1. Snapshot, 2. Screener picks, 3-10. Markets/news/correlation)
       │
       └─→ portfolio_analysis (5.2k tokens, optional)
           └─ P&L, dividends, RSI signals
       │
       ↓
DELIVERY TIER (06:00 & 08:30 IST)
  send_mailer → umashankartd1991@gmail.com
    └─ Via n8n workflow (Sun-09:00 monitor live)
       │
       ├─→ Put-call arbitrage scanning (7.1k tokens)
       │   └─ 3-leg order execution (if >0.3% deviation post-cost)
       │
       └─→ Reports & backtest validation
           ├─ valuation_reversion_*.md (PIT validated)
           ├─ piotroski_backtests.parquet
           └─ signal_outcomes.parquet (accuracy tracking)

MONITORING TIER (continuous via RUFLO)
  Token tracking (.ruflo/data/token_usage.db)
    ├─ daily_scan: 87.5k → 73-81k tokens/day (post-optimization)
    ├─ watchlist_mailer: 11.9k tokens/day (stable)
    ├─ portfolio_analysis: 5.2k tokens/day
    ├─ put_call_parity: 7.1k tokens/day
    └─ Alert thresholds: 70% (warn), 85% (critical), soft limit 160k
       │
       └─→ Dashboard: bash .ruflo/scripts/token-dashboard.sh
```

---

## Graphify Connected Format: Master Index

### Central Hub Nodes
1. **RUFLO Monitoring** (center)
   - Connects to: All tasks, all models, all repositories
   - Tracks: Real-time token usage, cost, quality metrics
   - Outputs: Dashboard, alerts, optimization decisions

2. **Cassandra Data Store** (hub)
   - Serves: daily_scan, portfolio_analysis, search API
   - Updated by: bulk_fetcher, quote_updater, bhavcopy_history
   - Metrics: 2,681 instruments × 5 markets = 13,405 live quotes

3. **market-pipeline** (primary orchestrator)
   - Runs: daily_scan (87.5k tokens), watchlist_mailer (11.9k tokens)
   - Depends on: Cassandra, DuckDB, Parquet cache
   - Delivers: Signal database, daily email, correlation reports

### Optimization Journey (Connected)

```
Data Source → Analysis → Output
    ↓           ↓          ↓
Cassandra → daily_scan → signals
  (quotes)    (87.5k)    (71% of budget)
                │
                ├─ Phase 1: Batch optimization (-2.6-4.4k)
                ├─ Phase 1: Cache optimization (-3.5-5.3k)
                ├─ Phase 1: Lazy-load optimization (-1.7-2.6k)
                └─ Week 1: Model upgrade 3.5 Haiku (-2.6k)
                           ↓
                    Total: -9-14k/day savings
                           ↓
                    New baseline: 73-81k tokens/day

watchlist_mailer
    (11.9k)
    ├─ Week 1: Model upgrade 3.5 Haiku (-0.5k)
    │          ↓ Quality boost
    └─ Stable output (email format unchanged)

VALIDATION GATE (Week 1-3):
  ├─ If actual ≥ 8.5k reduction: Proceed to Phase 2
  │   └─ Sonnet upgrades (portfolio_analysis, put_call_parity)
  │       ├─ +1.5k (portfolio) for better multi-factor analysis
  │       └─ +1.8k (options) for better arbitrage detection
  │
  └─ If actual < 8.5k: Debug & refine Phase 1
```

---

## Success Metrics & Validation

### Data Quality
- [x] Price continuity checked (JP/KR splits validated)
- [x] Fundamentals dated (screener.in, EDGAR, XBRL exact)
- [x] Survivorship bias assessed (10.5-year deep = realistic)
- [ ] Correlation reconciliation (daily matrices vs. point-in-time)

### Analysis Accuracy
- [ ] Signal match rate (BUY signals vs. realized moves in +3M, +6M windows)
- [ ] Backtest point-in-time (no look-ahead bias, earnings before fundamental use)
- [ ] Portfolio P&L reconciliation (vs. broker statements)
- [ ] Options parity deviation (cost-adjusted profit margin > 0.3%)

### Completeness
- 21,279 tickers tracked (market_daily.ticker_freshness)
- 95% sector coverage (fundamentals-vs-speculation)
- 5 markets scanned daily (IN/US/EU/JP/KR)
- 2-3 hour daily pipeline (refresh schedule)

---

## Query Examples (Graphify-Ready)

### Find data sources feeding a task
```
MATCH (task:Task {name: 'daily_scan'}) 
  ← [ingests_from] ← (source:DataSource)
RETURN source.name, source.type, source.freshness
ORDER BY source.importance DESC
```

### Trace optimization impact on data flow
```
MATCH (opt:Optimization) → [applies_to] → (task:Task) 
  ← [ingests_from] ← (source:DataSource)
RETURN opt.name, task.name, opt.tokens_saved, source.update_frequency
```

### Cross-repository analysis dependencies
```
MATCH (repo1:Repository) → [runs] → (task1:Task) 
  → [depends_on] → (task2:Task) ← [runs] ← (repo2:Repository)
RETURN repo1.name, repo2.name, task1.name, task2.name
```

### Model selection impact on quality
```
MATCH (task:Task) → [uses_model] → (model:Model)
RETURN task.name, model.name, model.cost_per_token, model.quality_score
ORDER BY model.quality_score DESC, model.cost_per_token ASC
```

---

## Integration Checklist

- [x] Data sources indexed (market feeds, collectors, storage)
- [x] Analysis workflows mapped (scanning, scoring, validation)
- [x] Repository contexts documented (market-pipeline, backend, put-call-parity)
- [x] Token tracking integrated (RUFLO → SQLite → Dashboard)
- [x] Optimization timeline established (Phase 1 deployed, Week 1 validation)
- [ ] Graphify connections rendered (visual network graph)
- [ ] Cross-repository insights generated (what feeds what)
- [ ] Phase 2 decision gate defined (validation criteria)

---

Generated: 2026-07-28
Status: Data Source Index Ready for Graphify Visualization

