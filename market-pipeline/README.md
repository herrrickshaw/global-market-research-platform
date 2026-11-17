# Market Pipeline: Multi-Market Trading Analytics Platform

Full-stack investment research platform covering India (NSE/BSE), US (NASDAQ/NYSE), Europe (17 exchanges), Japan (TSE), and Korea (KRX).

**Latest**: Phase 1 token optimization deployed (9-14k tokens/day savings), token monitoring live, data library cataloguing 10,528 datasets.

---

## Quick Start

```bash
./run_app.sh          # Start backend :8000 + frontend :5173
```

See [CLAUDE.md](/Users/umashankar/CLAUDE.md) for full platform architecture, API reference, and CLI commands.

---

## 📊 Data Discovery

This repository is part of the **Global Data Library** — a unified catalog of 10,528 datasets across 40+ repositories with real-time freshness tracking and gap identification.

### Access the Data Library

- **[Global Data Library README](.ruflo/DATA_LIBRARY_README.md)** — Full catalog, search API, usage examples
- **[Data Library Python Interface](.ruflo/data-library/)** — Query datasets programmatically
- **[Repository Scanner](.ruflo/data-library/repo_scanner.py)** — Reindex all repos

### Quick Example: Find & Use Data

```python
from data_library import DataLibrary

lib = DataLibrary()

# Find India OHLCV data
results = lib.search("india ohlcv", market="india")

# Get optimal storage path (fastest + freshest)
optimal = lib.get_optimal("india ohlcv", latency="<100ms", freshness="<1day")
# Returns: {"storage_tier": "cassandra", "path": "herrrickshaw.stock_quotes"}

# Check completeness
gaps = lib.gaps("india", date_from="2026-01-01")
# Returns: {"missing_symbols": 8, "completeness_pct": 97.3}

# Load data (auto-routes to optimal source)
if optimal['storage_tier'] == 'cassandra':
    df = cassandra_client.get_market_quotes_df('india')
```

### Browse Full Catalog

**Markets Indexed** (5 markets, 21,279 symbols):
- India: NSE (2,364) + BSE (317) equities
- US: NASDAQ (6,500) + NYSE (942) equities
- Europe: 17 exchanges, 1,214 stocks
- Japan: TSE, 3,709 equities
- Korea: KRX, 2,768 equities

**Government Sources Indexed** (30+ ministries):
- MOSPI: 25 datasets (GDP, CPI, trade, agri, power)
- SEBI: 151,928 XBRL results + IPO pipeline
- PIB: 25+ ministry announcements
- DGFT: India trade (monthly)
- Agmarknet: 300+ mandi prices (daily)

**Storage Backends**:
- Cassandra (herrrickshaw keyspace): Live OHLCV+RSI, <50ms
- Parquet (global-market-data): 10.5y cache, 50ms
- DuckDB (market_data.duckdb): 966 European stocks, 100ms
- SQLite (token_usage.db): Token monitoring, 150ms
- Dropbox: 8.9 GB archives, 500ms-2s

See [**Global Data Library README**](.ruflo/DATA_LIBRARY_README.md) for complete documentation, query examples, and gap analysis.

---

## Platform Architecture

```
Frontend (React :5173)
    ↓ REST API ↓
Backend (FastAPI :8000)
    ├── routers/cassandra_router.py    Daily scans (Darvas/Piotroski)
    ├── routers/live.py                 yfinance fetch + live scan
    ├── routers/portfolio.py            P&L + dividends + RSI
    ├── routers/scan.py                 Screener CSV scan
    └── routers/sectors.py              Damodaran sector benchmarks

Cassandra (herrrickshaw keyspace)       DuckDB (market_data.duckdb)
├── instruments                         ├── europe_all_list (966 stocks)
├── instruments_by_symbol               ├── frankfurt_list (142)
├── stock_quotes                        ├── london_list (436)
├── price_history                       ├── nse_stocks_fundamental
└── seed_status                         └── bse_stocks_fundamental
```

---

## Running the Platform

### Web App

```bash
./run_app.sh
# Starts: Backend (:8000) + Frontend (:5173)
# Refreshes instrument lists from exchanges
```

### CLI: Pegu/Sarvas Scanning

```bash
./run_pegu_sarvas.sh              # NIFTY500 + BSE (default)
./run_pegu_sarvas.sh nifty50      # Quick test (NIFTY50 only)
./run_pegu_sarvas.sh all          # All NSE + BSE equities
```

### CLI: Individual Modules

```bash
python nse_bse_extractor.py --exchange BOTH --index NIFTY500
python portfolio_analysis.py --symbols RELIANCE TCS INFY [--weights 0.4 0.35 0.25]
python stock_metrics_nse.py RELIANCE [--rsi-period 21 --news 5]
python -m put_call_parity.main           # live trading
python -m put_call_parity.main --backtest
```

---

## Daily Scans & Reports

**Darvas + Buffett Screening** (technical + fundamental overlay):
- 0-7 point scoring
- BUY ≥ 5 · WATCH ≥ 3
- Runs daily across all 5 markets

**Piotroski Scoring** (9-point fundamental quality):
- Momentum proxies when fundamentals unavailable
- Dynamic thresholds by data availability
- BUY/WATCH split by quality tier

**Daily Email Brief** (watchlist_mailer):
- Morning summary of signals
- Zone-first ranking (mean-revert vs trend per market)
- >5-session eviction + >15-symbol purge

See [CLAUDE.md](/Users/umashankar/CLAUDE.md) for scanner tuning, signal definitions, and backtest results.

---

## Token Monitoring & Optimization

**Status**: Phase 1 deployed + live
- 3 code optimizations (-9-14k tokens/day)
- Model upgrade to Claude 3.5 Haiku
- Token tracking via RUFLO + SQLite

```bash
# Run monitoring dashboard
bash .ruflo/scripts/token-dashboard.sh

# Query task-specific metrics
sqlite3 .ruflo/data/token_usage.db \
  "SELECT DATE(timestamp), SUM(total_tokens), SUM(cost) \
   FROM token_usage \
   WHERE task_id = 'daily_scan' \
   GROUP BY DATE(timestamp);"
```

See [.ruflo/WEEK1_DEPLOYMENT_SUMMARY.txt](.ruflo/WEEK1_DEPLOYMENT_SUMMARY.txt) for optimization details and validation plan.

---

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/db/daily/scan` | Run Darvas+Piotroski across all markets |
| `POST` | `/api/db/fetch_quotes` | Bulk OHLCV fetch for a market |
| `GET` | `/api/db/fetch_progress` | Poll bulk fetch progress |
| `POST` | `/api/db/seed` | Seed instruments from CSV |
| `GET` | `/api/db/status` | Instrument + quote counts per market |
| `GET` | `/api/db/search` | Search instruments by name/ticker |
| `POST` | `/api/live/fetch` | Fetch live data from yfinance |
| `POST` | `/api/live/scan` | Run scanners on live data |
| `POST` | `/api/portfolio/parse` | Parse Excel/PDF portfolio |
| `POST` | `/api/portfolio/history` | Enrich holdings with P&L |
| `POST` | `/api/db/scheduler/trigger` | Fire immediate prefetch |

See [CLAUDE.md](/Users/umashankar/CLAUDE.md) for request/response schemas.

---

## Key Files

| Path | Purpose |
|------|---------|
| `backend/routers/cassandra_router.py` | Daily scan coordinator (Phase 1 optimized) |
| `backend/db/quote_updater.py` | Cassandra quote persistence (cached) |
| `backend/scanners/daily_scanner.py` | Darvas/Piotroski (lazy-load metrics) |
| `market-pipeline/code/python_files/build_mailer.py` | Watchlist email generation |
| `data/market_data.duckdb` | 966 European stocks + NSE/BSE fundamentals |
| `.ruflo/data-library/data_library.py` | Unified data access interface |
| `.ruflo/DATA_LIBRARY_README.md` | Complete data catalog + examples |
| `.ruflo/graphify-network-diagram.svg` | 5-layer network (sources → storage → analysis) |

---

## Troubleshooting

**No instruments loading?**
- Check `data/nse_equity_list.csv`, `data/us_list.csv`, etc. (refreshed by `run_app.sh`)
- If missing, run: `./run_app.sh` to download fresh lists

**Cassandra connection failed?**
- Ensure Cassandra is running: `docker ps | grep cassandra`
- Start if needed: `docker-compose up -d cassandra`

**Slow OHLCV fetch?**
- Switch to Parquet cache: `lib.get_optimal("us ohlcv", latency="<2000ms")`
- Use DuckDB for Europe: faster for 966 stocks

**Data gaps?**
- Check collector status: `lib.collectors_status()`
- See missing date ranges: `lib.gaps("india", date_from="2026-01-01")`

See [CLAUDE.md](/Users/umashankar/CLAUDE.md) for design decisions and known limitations.

---

## Development

### Adding a New Market

1. Add CSV to `data/` with format: `Symbol,Name,ISIN,Exchange`
2. Update `routers/cassandra_router.py` to detect and seed
3. Test daily scan with new market
4. Register with data library: `lib.add_dataset(...)`

### Adding a New Collector

```python
lib.add_collector(
    collector_id="my_collector",
    name="My Data Pipeline",
    repo="market-pipeline",
    frequency="daily",
    datasets_produced="dataset1,dataset2",
    timeout_seconds=3600
)
```

### Monitoring Your Changes

```bash
# Check token impact
bash .ruflo/scripts/token-dashboard.sh

# Check data quality
lib.gaps("india", date_from="2026-01-01")

# Reindex catalog
python3 .ruflo/data-library/repo_scanner.py
```

---

## Resources

- **[Global Data Library](.ruflo/DATA_LIBRARY_README.md)** — Catalog of 10,528 datasets + query API
- **[Platform Guide](/Users/umashankar/CLAUDE.md)** — Architecture, design decisions, API reference
- **[Token Optimization](.ruflo/WEEK1_DEPLOYMENT_SUMMARY.txt)** — Phase 1 results + validation plan
- **[Network Diagram](.ruflo/graphify-network-diagram.svg)** — Data flow across all 40 repos + 30 gov sources
- **[Government Sources](.ruflo/graphify-all-repos-government-index.md)** — 30+ ministry data sources + freshness

---

**Status**: ✅ Production (Phase 1 optimized, monitoring live)  
**Last Updated**: 2026-07-28  
**Datasets Catalogued**: 10,528 (2.1 GB indexed)  
**Markets**: 5 (India, US, Europe, Japan, Korea)  
**Government Sources**: 30+ (MOSPI, SEBI, PIB, DGFT, Agmarknet, etc.)
