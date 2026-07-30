# Changelog

All notable changes follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: breaking change or major new capability
- **MINOR**: new feature, backward-compatible
- **PATCH**: bug fix, performance improvement

---

## [3.11.0] — 2026-07-30 — DDD architecture retrofit: stock_ddd + IPO/earnings-call bounded contexts

### Added
- **`code/python_files/stock_ddd/`** — relocated from an untracked
  `~/Downloads/code/stock_ddd/` copy to where `tool_registry.py`'s
  `register_builtin_screeners()` hook already expected it (that hook has
  existed since 3.9.0's Extensibility Registry, silently returning 0 the
  whole time because the folder was never placed where it looked). Bounded
  contexts for `market_data`/`screening`/`backtest`/`intraday`/`reporting`,
  a working 3-tier `CompositeStockRepository` (memory → Parquet → yfinance),
  Evans-literate value objects (`Ticker`, `Exchange`, `MarketRegime`, `Price`,
  `Percentage`) in `domain/shared/value_objects.py`. Verified:
  `register_builtin_screeners()` now returns 6, not 0.
- **`domain/ipo/`** (`entities.py` + `infrastructure/ipo/legacy_adapter.py`)
  — `IpoListing`/`ListingGateStage`/`NewListingEvent` value objects wrapping
  the existing, working `ipo_tracker.py`/`ipo_monitor.py` (739+107 lines)
  behind an adapter — no logic rewritten. Verified behaviour-preserving
  against a synthetic bhavcopy CSV fixture (adapter's symbol set matches
  calling `ipo_tracker.py` directly).
- **`domain/earnings_call/`** (`entities.py` + `ports.py`) — new bounded
  context, design only (no scraper/parser adapter yet): `EarningsCallEvent`,
  `EarningsCallTranscript`, `GuidanceChange`, `EarningsCallSignal` entities
  and the `IEarningsCallScheduleSource`/`IEarningsCallTranscriptSource`/
  `IEarningsCallAnalyzer`/`IEarningsCallSignalRepository` ports. Designed so
  the scheduling side can later wrap the existing `earnings_dates_sec_8k.py`
  (US, SEC EDGAR 8-K Item 2.02) and `earnings_dates_tdnet.py` (Japan, JPX
  TDnet) date collectors instead of duplicating a new date-fetcher — the
  transcript/guidance/sentiment side is genuinely new (confirmed by
  exhaustive grep, nothing existed anywhere).

### Removed
- Two dead DDD scaffolds — `repos/global-market-data/src/` and
  `repos/global-stock-screener/src/` (one incidental commit each, no
  adapters, no tests, nothing imported them) — superseded by
  `stock_ddd/`, deleted rather than left as confusing dead code.
- 3 duplicate `ipo_tracker.py` copies (839/142/738 lines, across
  `repos/global-market-data`, `repos/global-stock-screener`,
  `Downloads/code/python_files`) and 3 duplicate `ipo_monitor.py` copies —
  diffed first, confirmed no unique logic beyond a stale
  `~/Downloads/market_cache`/`~/Downloads/data/bhavcopy_cache` path default
  (the same deprecated location `etl_registry.py`'s weekly audit already
  flags). Canonical copies stay in `code/python_files/`.

### Decisions
- **Wrap, don't rewrite, for anything already working**: `ipo_tracker.py`
  and `ipo_monitor.py` keep their exact tested logic; the DDD layer is an
  adapter around them, not a reimplementation. Same principle applied to
  the `stock_ddd` relocation itself — it moved, it wasn't redesigned.
- **Rejected: a full DDD retrofit across every existing script.** Considered
  and rejected in favour of building new capability (IPO consolidation,
  earnings-call) inside the DDD layer where regression risk is near zero,
  while leaving proven, recently-stabilized code (the mailer/research
  chain, `daily_mailer.sh`/`daily_research.sh`, the `/tmp` pipeline lock,
  `watchlist_markets.py`) completely untouched.
- **Rejected: reworking the bash+`mkdir`-lock orchestration into a formal
  task-graph.** Every orchestration incident this cycle (a 9-hour full
  pipeline run, a launchd chain-fire bug needing `AbandonProcessGroup`, a
  stale-price near-miss) was already fixed with no new incident since —
  reworking orchestration now would be the highest-regret move available,
  not a response to an actual live problem.
- Full options survey and staged plan (Phase 0-3) recorded in
  `~/.claude/plans/swift-nibbling-shore.md`.

## [3.10.0] — 2026-07-29 — Unlimited-OCR integration (scanned-PDF fallback)

### Added
- **`ocr/`** — shared client for a remote **baidu/Unlimited-OCR** endpoint
  (arXiv:2606.23050, "Unlimited OCR Works": R-SWA attention transcribes dozens
  of pages in a single forward pass with constant KV cache, 32K context, MIT
  license). The model needs an NVIDIA GPU, so it is NOT run locally — it is
  served on Colab/EC2 GPU behind vLLM's OpenAI-compatible API and reached over
  HTTP. Config: `UNLIMITED_OCR_URL` (env or `~/.config/market-secrets/
  credentials.env`). CLI: `python3 -m ocr file.pdf` / `--ping`. Pages are
  batched 8-per-request by default to exploit the single-pass design.
- **`ocr/serve/`** — Colab notebook (free T4 + cloudflared quick tunnel) and
  docker one-liner (`vllm/vllm-openai:unlimited-ocr`) to bring the endpoint up.
- **`backend/parsers/pdf_parser.py`** — OCR fallback: when pdfplumber extracts
  zero symbols (scanned/image-only portfolio PDFs), the transcript is fetched
  and re-fed through the same table/text symbol matching, with an explicit
  review warning. Strictly opt-in: with `UNLIMITED_OCR_URL` unset, behavior is
  byte-identical to before.
- **`requirements-ocr.txt`** added to every repo that parses documents/PDFs
  (BazaarTalks, india-trade-sector-policy-recommendations,
  ppac-ready-reckoner-data, repos/cng-cgd-retail-outlet-mapping,
  repos/global-market-{data,scanners}, repos/global-stock-screener,
  vehicle_fuel_mileage, market-pipeline); appended to the two existing
  requirements.txt in this repo (root + backend).

### Decisions
- **Remote-serve over local**: no CUDA on macOS; alternatives rejected —
  CPU/MPS transformers (unsupported/slow), tesseract (poor on tabular Indian
  filings, no layout), paid OCR APIs (cost + the repo is public).
- **Opt-in, never required**: OCR deps are lazy imports; pipelines must not
  gain a hard GPU-service dependency.

## [3.9.0] — 2026-06-26 — Extensibility Registry + Approach Docs

### Added
- **`tool_registry.py`** — decorator-based registry to add screeners, news
  sources, and analyses with ONE function each (minimises code as the system
  grows). `@screener / @news_source / @analysis` auto-register; pipelines can
  iterate `run_all_screeners()` instead of hard-coding rules. The 6 built-in
  screeners fold in via `register_builtin_screeners()` so old + new share one
  source of truth. Verified: a new screener = ~5 lines.
- **`APPROACHES.md`** — full write-up of the two analytical approaches
  (fundamental/historical vs news/sentiment), their data, strengths, limits,
  the convergence cross-check, and how to extend either with minimal code.
- Two-approach comment header added to daily_combined_report.py.

### Note
- Gmail MCP in this environment exposes only `create_draft` (no send tool), so
  the daily report is left as a Gmail draft for one-click manual send.

---

## [3.8.0] — 2026-06-26 — US News Sources (CNBC + MarketWatch)

### Added
- `USRSSProvider` in sentiment_pipeline.py — free RSS, no API key:
  CNBC (top news, markets, finance) + MarketWatch (top stories, market pulse,
  bulletins). Same company-name matching as the Indian provider (name looked up
  from the symbol master). `get_market_mood('US')` gives a US regime gauge.

### Fixed
- symbol_master `_ensure_lookup` crashed on tickers listed on >1 exchange
  (`DataFrame index must be unique`) — now dedups by symbol. This silently broke
  US name lookups; now NVDA→NVIDIA, AAPL→Apple, TSLA→Tesla, MU→Micron all match
  CNBC/MarketWatch headlines.

### Changed
- daily_combined_report passes market to get_market_mood (IN→Moneycontrol/ET,
  US→CNBC/MarketWatch).

---

## [3.7.0] — 2026-06-26 — Company-Name Sentiment + Symbol Master Parquet

Switches news matching from tickers to COMPANY NAMES and persists a full
ticker↔name master as Parquet.

### Added
- **`symbol_master.py`** — builds/maintains `market_cache/symbol_master.parquet`:
  every NSE+BSE+US stock with `symbol, name, name_clean, exchange, suffix,
  yf_symbol` (11,707 stocks). Company names come free from NSE/BSE bhavcopy
  `FinInstrmNm` and SEC EDGAR. Auto-refreshes when >24h stale.
  - `clean_name()` strips only legal-form suffixes (LTD/LIMITED/PVT…), KEEPS
    descriptive tokens so group companies stay distinct
    ("ADANI ENTERPRISES" vs "ADANI PORTS" vs "ADANI POWER").
  - `name_for()` / `clean_name_for()` lookups.
- `symbol_master.parquet` shipped in nse_screener_reference/ and the Docker image.

### Changed
- `IndianRSSProvider.fetch_news` now matches the multi-word COMPANY NAME phrase
  (auto-looked-up from the master) instead of the ticker — fixes both recall
  (headlines say "Reliance Industries", not "RELIANCE") and precision
  (no more DOLLAR↔"dollar", DEN↔"dent", or one headline hitting many tickers).
  Falls back to ticker word-boundary only when no name is available.

### Verified
- Name-based matches: MANAPPURAM→"Manappuram Finance", DELHIVERY→"Delhivery",
  RELIANCE→"Reliance Industries"; DOLLAR/DEN/STAR → 0 false matches.

---

## [3.6.0] — 2026-06-26 — Two-Component Daily Report + Docker

Surfaces the two pipelines as two labelled components in the daily mailer and
packages everything into the Docker image.

### Added
- **`daily_combined_report.py`** — merges both pipelines into one report with:
  - **"Stock Picks Based on Fundamentals"** (Component 1 — screener pipeline)
  - **"Talk on the Street"** (Component 2 — live news sentiment + market mood)
  - **Convergence** section: highlights stocks where BOTH agree
    (✅ strong fundamentals AND positive news = high-conviction;
     ⚠️ strong fundamentals BUT negative news = caution).
  - Efficient: fundamentals run full-universe (offline); news runs only on the
    fundamental shortlist + market-mood gauge (conserves news quota).
  - Emits HTML fragment (`--html`) + JSON for the mailer.
- Docker: 10 new modules copied into the image (stock_utils, pattern_discovery,
  sector_analysis, dl_strategy_eval, sentiment_pipeline, sentiment_price_link,
  pipeline_historical, pipeline_news, daily_combined_report, r_analysis).
- entrypoint.sh commands: `report`, `historical`, `news`, `patterns`.
- docker-compose services: `report`, `historical`, `news`.

### Changed
- Daily mailer (8:30 AM cron) restructured around the two named components,
  leading with the Convergence highlight. Subject line shows fundamentals
  count, street mood, and convergence count.

### Verified
- Combined report runs: 8 fundamental triple-hits + market mood +0.44 POSITIVE.

---

## [3.5.0] — 2026-06-26 — Two Separate Pipelines (Historical vs News)

Splits all analysis into two clean, independent orchestrators with distinct
entry points, data sources, and online/offline characteristics.

### Added
- **`pipeline_historical.py`** — PIPELINE 1: historical data analysis (OFFLINE).
  Orchestrates price/fundamental stages over the 5-year Parquet cache:
  scan → backtest → walk-forward → pattern discovery → sector clustering →
  DL strategy → implied sentiment↔price proxy. `--stages` selects a subset;
  `full` / `analytics` presets. No live network beyond cache warming.
- **`pipeline_news.py`** — PIPELINE 2: news-based analysis (ONLINE/live text).
  4 stages: market mood (regime gauge) → per-ticker sentiment → forward
  monitor (logs at 1d/1wk/1mo/3mo cadence) → sentiment↔price join (builds the
  true news-vs-price correlation dataset as the log matures).
  Sources: RSS (Moneycontrol/ET/BusinessLine/LiveMint, no key) + 4 APIs.

### Separation of concerns
  Historical = offline, price/fundamentals, backtested patterns, 5-yr cache.
  News       = online, live headlines, VADER/provider sentiment, forward-looking.
  They share only stock_utils helpers; otherwise fully decoupled.

---

## [3.4.0] — 2026-06-26 — Indian News Sources (Moneycontrol/ET/BusinessLine)

### Added
- `IndianRSSProvider` in sentiment_pipeline.py — free RSS, no API key:
  Moneycontrol, Economic Times, BusinessLine, LiveMint. Per-ticker matching +
  market-mood regime gauge. Verified live (ADANIENT +0.64, market mood +0.43).

---

## [3.3.0] — 2026-06-26 — News Sentiment Ingestion Pipeline

Adds the textual-sentiment stream that turns the price-only screeners/ML into
hybrid market+sentiment models — the configuration Sharma et al. (IJIRTM 2025)
and the DL survey found consistently outperforms single-source models.

### Added
- **`sentiment_pipeline.py`** — multi-source news sentiment ingestion:
  - 4 provider adapters (free tiers): **Marketaux** (100/day, global),
    **Alpha Vantage** (25/day, native sentiment), **Finnhub** (60/min),
    **NewsData.io** (1,000/month, multi-language)
  - Provider abstraction with per-source rate-limit throttling
  - Sentiment scoring: provider-native score when available, else VADER with a
    finance-tuned lexicon (beat/upgrade/surge positive; plunge/fraud/downgrade negative)
  - Quota-weighted aggregation → per-ticker score [-1,+1] + POSITIVE/NEUTRAL/NEGATIVE
  - 6-hour result cache to conserve API quota; graceful degradation if a key is missing
  - Demo mode (VADER on sample headlines) when no API keys are set
- `vaderSentiment` added to requirements.txt

### Setup
  export MARKETAUX_KEY / ALPHAVANTAGE_KEY / FINNHUB_KEY / NEWSDATA_KEY
- `warm_india_cache.py` — warms 5-yr Parquet cache for full NSE+BSE
  (2,372 NSE + 2,133 BSE-only = 4,505 tickers)

### Research papers added (1)
- Sharma et al. (IJIRTM 2025) — hybrid market+sentiment beats price-only. (16 total)

---

## [3.2.0] — 2026-06-26 — AI Pattern Discovery & Sector Analytics

Adds an analytics suite that mines the 5-year Parquet cache (6,280 stocks across
NSE + NASDAQ + NYSE) for structure, plus a literature-grounded strategy evaluator
and a full glossary. Reuses the shared `stock_utils` helpers throughout.

### Added
- **`stock_utils.py`** — shared helpers eliminating duplication across 14 scripts
  (`first_df`, `row`, `series`, `extract_ticker_df`, `bulk_download`,
  `parallel_map`, `cagr`, `pct_change`, `normalise_debt_to_equity`).
- **`pattern_discovery.py`** — 4-step unsupervised + supervised discovery:
  cleansing → 24-feature extraction → KMeans/DBSCAN/PCA + GradientBoosting →
  insight extraction (behavioural archetypes, anomalies, co-moving pairs).
  Honest finding: out-of-sample forward-return R² ≈ 0 (semi-efficient markets);
  value is structural (clusters, pairs), not predictive.
- **`dl_strategy_eval.py`** — directional classification → mechanical long/flat
  strategy → economic backtest vs buy-and-hold, grounded in 5 DL papers
  (Fister 2019, Olorunnimbe 2022, Toichatturat 2024, Sharma 2025, Miao CS230).
  Finding: ML earns no return alpha in efficient US, modest edge in India, but
  consistently cuts drawdown 12–15pp in both — Fister's risk-adjusted thesis.
- **`sector_analysis.py`** — sector classification (cached) → equal-weighted
  sector return indices → KMeans on 10-feature fingerprints → rankings,
  co-movement (diversification pairs), rotation. Rediscovered defensive vs
  cyclical split; Utilities as best diversifier (US); Tech defensive in India.
- **`GLOSSARY.md`** — ~180 terms across 12 sections (screeners, indicators,
  fundamentals, regime, backtesting, ML, intraday, IPO, architecture, papers).

### Fixed
- Look-ahead leakage in `pattern_discovery` supervised model (as-of feature
  cutoff): spurious R²=0.926 → honest R²=−0.063.

### Research papers added (5)
- Fister et al. (NNW 2019), Olorunnimbe & Viktor (AI Review 2022),
  Toichatturat (SET 2024), Sharma et al. (IJIRTM 2025), Miao (Stanford CS230).
  Total papers incorporated: 15.

---

## [3.1.0] — 2026-06-26 — Domain-Driven Architecture

Refactored the monolithic scan scripts into a clean 3-layer DDD architecture
under `Downloads/stock_ddd/`. Existing v1.0 infrastructure (Parquet cache,
nsepython fetcher) is wrapped as repository adapters — proven code reused, not
rewritten.

### Added
- **Domain Layer** (`domain/`) — pure business logic, zero outer-layer imports
  - `shared/value_objects.py` — `Ticker`, `Price`, `Percentage`, `DateRange`,
    `ReturnHorizon`, `VIXLevel`, `Exchange`/`MarketRegime`/`PEZone` enums
  - `shared/events.py` — domain events + `DomainEventBus` (pub/sub)
  - `market_data/entities.py` — `Stock` aggregate root, `MarketIndex`,
    `PriceBar`, `Sector`; `classify_regime()` as pure domain logic
  - `market_data/repositories.py` — `IStockRepository`, `IMarketIndexRepository`,
    `ILiveMarketDataService`, `IFundamentalsRepository` interfaces
  - `screening/specifications.py` — Specification pattern: 6 screeners +
    `TripleHitSpec` + `MultiScreenSpec`, composable via `.and_()`/`.or_()`/`.not_()`
- **Application Layer** (`application/`) — orchestration, no business rules
  - `commands/run_daily_scan.py` — `RunDailyScanCommand` + handler (CQRS)
  - `ports/report_writer.py` — `IReportWriter`, `INotificationService` output ports
- **Infrastructure Layer** (`infrastructure/`) — the only layer touching yfinance/Parquet/nsepython
  - `market_data/composite_repository.py` — `CompositeStockRepository` (3-tier cache),
    `ParquetIndexRepository`, `NSEPythonLiveService`, `YFinanceFundamentalsRepository`,
    `create_stock_analysis_container()` DI factory
- `stock_ddd/README.md` — architecture guide with layer diagram

### Changed
- Business rules (screener thresholds, regime classification, PE zones) moved
  out of scripts into testable Domain objects
- Dependency rule enforced: Domain ← Application ← Infrastructure (inward only)

### Benefits
- Screeners testable without network (in-memory `Stock` + `Specification`)
- New data source = one new `IStockRepository` impl, zero Domain/App changes
- Single source of truth for each rule (was duplicated across 3–4 scripts)

---

## [2.0.0] — Planned

### Added
- `intraday_monitor.py` — real-time 15-min / 30-min OHLC monitoring daemon
  - Opening Range Breakout (ORB) detection
  - VWAP deviation alerts
  - Volume surge detection (> 3× 15-min average)
  - Momentum burst pattern (3+ consecutive candles in same direction)
  - Darvas Box applied to intraday (15-min bars)
  - Bollinger Band squeeze breakout
  - Runs only during NSE market hours (09:15–15:30 IST, Mon–Fri)
- Intraday strategy section in daily email
- New fundamental strategies based on company regulatory filings

### Changed
- Docker image: added monitoring daemon as background service
- Cron schedule: added 09:15, 09:30, 10:00 IST monitoring triggers

---

## [1.1.0] — Planned

### Changed
- Async data fetching using `asyncio` + `aiohttp` (target: 50% runtime reduction)
- Shared base module extracted from Indian/US scan scripts (remove redundancy)
- Incremental backtest: only re-compute signals for new bars since last run
- Memory optimisation: process stocks in streaming chunks (not all at once)
- Parquet columnar filtering: read only required columns per screener

### Fixed
- US backtest: SEC EDGAR fallback when NASDAQ FTP times out (v1.0.1 backport)
- yfinance crumb expiry: auto-refresh session every 30 minutes in long runs

---

## [1.0.0] — 2026-06-26

### Initial Release — First Docker image

#### Data
- NSE EQ universe: 2,406 stocks (via bhavcopy)
- BSE: 317 BSE-only stocks
- NASDAQ: 4,320 stocks (SEC EDGAR)
- NYSE: 2,831 stocks (SEC EDGAR)
- 5-year OHLC Parquet cache: 340 MB (Nifty 500 baked into image)
- Nifty 50 + S&P 500 index data: 10-year window

#### Screeners (6 total)
- Darvas Box Breakout (walk-forward, volume-confirmed)
- Golden Crossover (50 DMA × 200 DMA)
- Magic Formula (Greenblatt 2005)
- Piotroski F-Score ≥7 (2000)
- Coffee Can Portfolio (Mukherjea / Marcellus)
- Bull Cartel (quarterly earnings momentum)

#### Analysis
- Backtest: 1-year walk-forward (5 horizons: T+1d → T+3mo)
- Walk-forward: 3y/5y/10y train/test/val framework (8 horizons: T+1d → T+252d)
- ML signal: Ridge regression (AlQahtani et al. IJACSA 2025)
- IPO tracker: bhavcopy diff discovery of new listings
- PE zone classification: sector-aware (8 sectors)
- Market regime: Nifty 50 vs 200 DMA + India VIX

#### Infrastructure
- `market_data_cache.py`: 3-tier Parquet cache (memory → disk → network)
  - Cold start: ~12 min for full NSE; warm reads: 0.7 s from memory
  - 334× speedup vs re-downloading every run
- `nse_data_fetcher.py`: live nsepython integration (VIX, FII/DII, bulk deals)
- `stock_enricher.py`: company names, PE zones, exchange grouping
- `ipo_tracker.py`: new listing discovery and graduated screener gates
- `ml_signal_engine.py`: Ridge/LR signal with compare_models() evaluation

#### Daily Automation
- Cron: 8:30 AM weekdays (morning-stock-analysis-report)
- Email: HTML report with exchange-split tables, PE zones, IPO section
- Sequence: IPO tracker → screener_analysis → full Indian scan → full US scan

#### Research Papers Incorporated (10 total)
1. Greenblatt (2005) — Magic Formula
2. Piotroski (2000) — F-Score
3. Darvas (1960) — Box method
4. Mukherjea (2018) — Coffee Can
5. Bailey et al. (2014) — Backtest overfitting
6. Preet et al. (2021) — Magic Formula India
7. Bhute et al. (2024) — Backtesting Brilliance
8. Liu & Zhu (2024) — Kalman Filter market efficiency
9. Dhanus & Amutha (2025) — Super Trend NSE
10. AlQahtani et al. (2025) — ML/DL models

---

## [3.0.0] — Planned (C + R + Async)

### Added
- `c_extensions/darvas_fast.c` — C implementation of Darvas Box (313× faster)
  - `darvas_classify()` — single-bar classification (O(n × lookback))
  - `darvas_walk_forward()` — full walk-forward signal detection
  - `zscore_normalize_window()` — ML feature normalisation (vectorised SIMD)
  - Compiled: `gcc -O3 -march=native -shared -fPIC -o darvas_fast.so`
- `c_extensions/darvas_wrapper.py` — ctypes Python bridge
  - Falls back to pure Python if .so not available
  - `benchmark()` function for A/B timing comparison
- `r_analysis.py` — R statistical analysis via subprocess
  - `compute_r_stats()` — PerformanceAnalytics: Sharpe, Sortino, Calmar, VaR, CVaR
  - `detect_regimes_r()` — HMM regime detection using depmixS4 (3 states)
  - `sharpe_significance_test()` — Lo (2002) bootstrap significance test
  - `compute_technical_indicators_r()` — TTR: RSI, MACD, ATR, Bollinger Bands

### Performance (profiling results)
- Bottleneck identified: **network I/O = 84%** of total time (not processing)
- Darvas Python: 7.8ms/call → C: 0.025ms/call (**313× speedup**)
- Full NSE 2,400 stocks: Python ~138s → C ~1.4s for Darvas
- R PerformanceAnalytics: 0.4s for Sharpe/Sortino/Calmar/VaR
- Conclusion: Parquet cache solves the real bottleneck; C is a bonus for scale
