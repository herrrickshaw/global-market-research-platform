# Graph Report - .  (2026-07-27)

## Corpus Check
- Large corpus: 414 files · ~546,721 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 3223 nodes · 5558 edges · 286 communities (219 shown, 67 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 134 edges (avg confidence: 0.66)
- Token cost: 367,156 input · 8,961 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165
- Community 166
- Community 167
- Community 168
- Community 169
- Community 170
- Community 171
- Community 172
- Community 173
- Community 174
- Community 175
- Community 176
- Community 177
- Community 178
- Community 179
- Community 180
- Community 181
- Community 182
- Community 183
- Community 184
- Community 185
- Community 186
- Community 187
- Community 188
- Community 189
- Community 190
- Community 191
- Community 192
- Community 193
- Community 194
- Community 195
- Community 196
- Community 197
- Community 198
- Community 199
- Community 200
- Community 201
- Community 202
- Community 203
- Community 204
- Community 205
- Community 207
- Community 208
- Community 209
- Community 210
- Community 211
- Community 212
- Community 213
- Community 214
- Community 215
- Community 216
- Community 221
- Community 222
- Community 223
- Community 224
- Community 226
- Community 229
- Community 231
- Community 234
- Community 235
- Community 236
- Community 237
- Community 238
- Community 239
- Community 240
- Community 241
- Community 242
- Community 243
- Community 244
- Community 245
- Community 246
- Community 256
- Community 257
- Community 259
- Community 260
- Community 261
- Community 262
- Community 263
- Community 264
- Community 265
- Community 266
- Community 267
- Community 268
- Community 269
- Community 270
- Community 271
- Community 272
- Community 273
- Community 274
- Community 275
- Community 276
- Community 277
- Community 278
- Community 279
- Community 280
- Community 281
- Community 282
- Community 283
- Community 284
- Community 285

## God Nodes (most connected - your core abstractions)
1. `StockData` - 37 edges
2. `run()` - 28 edges
3. `Result` - 26 edges
4. `NSEDataFetcher` - 25 edges
5. `SentimentPipeline` - 24 edges
6. `run()` - 24 edges
7. `run()` - 24 edges
8. `MarketCache` - 23 edges
9. `get_logger()` - 23 edges
10. `DecisionLog` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Sakana AI Comparison` --semantically_similar_to--> `Piotroski Liquidity Paper`  [INFERRED] [semantically similar]
  docs/SAKANA_COMPARISON.md → reports/PIOTROSKI_LIQUIDITY_PAPER.md
- `process_batch()` --calls--> `process_xbrl_zip()`  [INFERRED]
  scripts/edinet_batch_process.py → code/python_files/edinet_xbrl_historical_fetcher.py
- `Full European Market Scan` --implements--> `Piotroski F-Score`  [EXTRACTED]
  python_files/full_european_market_scan.py → python_files/SCREENER_LITERATURE_LOG.md
- `Full Indian Market Scan` --implements--> `Piotroski F-Score`  [EXTRACTED]
  python_files/full_indian_market_scan.py → python_files/SCREENER_LITERATURE_LOG.md
- `Full US Market Scan` --implements--> `Piotroski F-Score`  [EXTRACTED]
  python_files/full_us_market_scan.py → python_files/SCREENER_LITERATURE_LOG.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Market Pipeline Execution Flow** — python_files_ingest, python_files_mailer, python_files_modelling, python_files_factor_tests [EXTRACTED 1.00]
- **Core Screener Methodologies** — python_files_piotroski_f_score, python_files_darvas_box, python_files_magic_formula, python_files_coffee_can_portfolio [EXTRACTED 1.00]
- **Statistical Validation Guards** — python_files_data_sufficiency, python_files_deflated_sharpe, python_files_valuation_reversion_backtest [EXTRACTED 0.90]
- **Market Character Strategy Mapping** — docs_why_these_win, reports_market_playbook, reports_playbook_digest_preview [EXTRACTED 0.95]
- **Piotroski Liquidity vs Size Thesis** — reports_piotroski_liquidity_paper, reports_caveman_summary, reports_execution_capacity [EXTRACTED 1.00]
- **Corporate Action Intimation Drift Validation** — reports_cost_intimation_drift, reports_intimation_validation, reports_pit_event_studies, reports_recommendation_roi [EXTRACTED 0.90]
- **Market Character Meta-Finding** — reports_project_retrospective, reports_strategy_matrix, reports_zone_rules_by_market [EXTRACTED 0.95]
- **Cross-Market Valuation Reversion Analysis** — reports_valuation_reversion_jp, reports_valuation_clusters, reports_value_quality_ls [EXTRACTED 0.90]
- **Underpriced Indian Assets** — analysis_dashboard_9758d6c0_rajeshexpo, analysis_dashboard_9758d6c0_insecticid, analysis_dashboard_9758d6c0_smcglobal [EXTRACTED 0.90]
- **Underpriced US Assets** — analysis_dashboard_9758d6c0_chtr, analysis_dashboard_9758d6c0_nxtt, analysis_dashboard_9758d6c0_pdynw [EXTRACTED 0.90]
- **Underpriced Korean Assets** — analysis_dashboard_9758d6c0_kr_290560_kq, analysis_dashboard_9758d6c0_kr_058430_ks, analysis_dashboard_9758d6c0_kr_151860_kq [EXTRACTED 0.90]

## Communities (286 total, 67 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (72): _already_done(), _compile_screener_outputs(), compute_coffee_can(), compute_darvas_box(), compute_piotroski_score(), convert_all_documents(), convert_to_markdown(), _darvas_core() (+64 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (68): BSE, compute_coffee_can(), compute_darvas_box(), compute_piotroski_score(), display_board_meetings(), display_bse_price(), display_bulk_deals(), display_coffee_can() (+60 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (63): compute_coffee_can(), compute_darvas_box(), compute_piotroski_score(), display_coffee_can(), display_corporate_actions(), display_darvas_box(), display_historical_summary(), display_insider_trades() (+55 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (58): _as_of_html(), build(), _ccc_rows(), _convergence_html(), _corr_section(), _darvas_section(), _eu_picks_rows(), _fund_coverage_note() (+50 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (40): load_panel(), DataFrame, Panel loading + universe selection for prediction models., Long panel [Date, Symbol, Open, High, Low, Close, Volume] for a market., Most-liquid symbols (median daily dollar volume) with a long history., Clean single-symbol frame indexed by Date with log returns., symbol_series(), top_liquid_symbols() (+32 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (50): build_mst(), compute_correlation_clusters(), fetch_universe_prices(), load_universe(), mst_clusters(), DataFrame, Batched yf.download across the whole *symbols* list (same "batches of 50"     st, Returns (correlation_matrix, clusters) where clusters is a list of sets     of s (+42 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (49): _day_table(), Path, Bring CACHE/<exch>.parquet current from CACHE/<exch>/ day-CSVs., One day-CSV -> arrow table with the pinned schema., refresh(), backfill_corp_actions(), collect(), consolidate() (+41 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (49): _bse_day(), _cleaned_behind_assembled(), _equity_only(), fetch_history(), get_symbol(), _lmdb_behind_cleaned(), _lmdb_max_date(), _nse_day() (+41 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (30): get_fetcher(), get_institutional_confirmation(), get_live_regime(), get_nse_symbols(), _get_strategy_recommendation(), get_upcoming_results(), NSEDataFetcher, DataFrame (+22 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (45): compute_darvas_box(), compute_pegy_and_breakout(), compute_piotroski_score(), display_corporate_actions(), display_darvas_box(), display_pegy_and_breakout(), display_piotroski_score(), display_price_summary() (+37 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (19): audit_market(), _floors(), _latest(), main(), Bar, median_age_days(), Money, PriceSeries (+11 more)

### Community 11 - "Community 11"
Cohesion: 0.16
Nodes (23): cagr(), Everything a strategy might inspect for one ticker., Return float or None (filters NaN)., Result, safe(), sma(), StockData, screen() (+15 more)

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (35): build(), _market_of(), Path, fetch(), DataFrame, Map a yfinance ticker to a Stooq symbol (covers the markets Stooq carries)., Fetch OHLC with fallback. Tries sources in `order`; each source only     handles, stooq_fetch() (+27 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (37): analyze_signals(), build_heatmap(), classify_regime(), compute_forward_returns(), compute_index_returns(), detect_darvas_signals(), detect_golden_cross_signals(), download_index() (+29 more)

### Community 14 - "Community 14"
Cohesion: 0.15
Nodes (33): backfill_gaps(), check_coverage(), detect_bear_window(), fetch_benchmark(), _korea_suffix_map(), load_backfill_to_warehouse(), main(), DataFrame (+25 more)

### Community 15 - "Community 15"
Cohesion: 0.09
Nodes (36): amihud_illiq(), annotate(), build_index(), currency_for(), _fred_key(), _fx_from_erapi(), _fx_from_frankfurter(), _fx_from_fred() (+28 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (29): _AsOf, forward_returns(), liquid_universe(), main(), DataFrame, A Ticker-shaped view of statements truncated to what was public at `asof`., PIT forward returns with the corporate-action filter and delisting exits., Fetch once; every rebalance and every vector reuses this. (+21 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (35): attach_forward_returns(), attach_market_cap(), below_200dma_signals(), benchmark_lookup(), build_fundamental_signal_dates(), compute_fundamental_screens(), darvas_signals(), _flag_split_days() (+27 more)

### Community 18 - "Community 18"
Cohesion: 0.10
Nodes (35): bulk_download_ohlc(), compute_bull_cartel(), compute_coffee_can(), compute_darvas_box(), compute_golden_crossover(), compute_magic_formula(), compute_piotroski(), enrich_symbol() (+27 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (18): MarketCache, DataFrame, date, Path, Persistent cache for market data using Parquet files.      Parquet was chosen ov, Record cache entry metadata after writing a file., Return True if the cache entry is older than stale_hours., Return the last date in the cache for incremental updates. (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.13
Nodes (27): compute_reward(), DataFrame, ndarray, Exposed separately from step() so train_ppo_factor_weights.py can         run th, Non-negative, sums to 1 -- makes weights directly comparable across     factors, Same formula as reward_screener_opt.py's reward(): n, median excess     (primary, One episode = one regime draw -> one weight-vector action -> reward     from tha, RegimeWeightedScoreEnv (+19 more)

### Community 21 - "Community 21"
Cohesion: 0.12
Nodes (32): _cap_technical(), harvest_fundamental(), harvest_technical(), _latest(), main(), DataFrame, Path, Most recent rebalance's factor passes from the India panel. (+24 more)

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (32): analyze_all(), assign_split(), classify_regime(), compute_stats(), darvas_signals(), fetch_index(), fetch_ohlc_bulk(), forward_returns() (+24 more)

### Community 23 - "Community 23"
Cohesion: 0.11
Nodes (30): _bq_fields(), bulk_download_ohlc(), compute_darvas_box(), compute_golden_crossover(), fetch_all_us_symbols_from_sec(), _fetch_nasdaq_file(), fetch_nasdaq_symbols(), fetch_nyse_symbols() (+22 more)

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (31): compute_vwap(), detect_bb_squeeze(), detect_intraday_darvas(), detect_momentum_burst(), detect_orb(), detect_volume_surge(), detect_vwap_deviation(), fetch_intraday() (+23 more)

### Community 25 - "Community 25"
Cohesion: 0.10
Nodes (31): already_done(), compile_outputs(), _darvas_from_df(), fetch_stock_universe(), _first_df(), init_db(), main(), mark_done() (+23 more)

### Community 26 - "Community 26"
Cohesion: 0.13
Nodes (28): has(), _load(), mcap_and_info(), DataFrame, quarterly_statements(), (mcap, info) for a store ticker, from stored latest-year values + price.      Co, Bull Cartel's quarterly income statement, yfinance-shaped, or None.      Rows "T, True if the store can serve annual statements for this symbol. (+20 more)

### Community 27 - "Community 27"
Cohesion: 0.12
Nodes (27): answer(), balance_sheet(), build_corpus(), edge_map(), etl_status(), global_fund(), income_statement(), local_llm() (+19 more)

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (25): _age_days(), assess(), _coverage(), main(), _mtimes(), _newest_mtime(), _ohlc_data_coverage(), _pg_freshness() (+17 more)

### Community 29 - "Community 29"
Cohesion: 0.13
Nodes (25): _bq_fields(), _bse_session(), bulk_download_ohlc(), bulk_ohlc(), compute_darvas_box(), compute_golden_crossover(), fetch_bse_only_symbols(), fetch_nse_symbols() (+17 more)

### Community 30 - "Community 30"
Cohesion: 0.13
Nodes (22): _bq_fields(), build_ticker_universe(), bulk_download_ohlc(), compute_darvas_box(), fetch_tse_universe_jpx(), fetch_tse_universe_kabupy(), _first_df(), fundamental_scan() (+14 more)

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (22): _bq_fields(), build_krx_universe(), compute_darvas_box(), _fetch_kind_list(), fetch_krx_ohlc(), _first_df(), fundamental_scan(), _gc_fields() (+14 more)

### Community 32 - "Community 32"
Cohesion: 0.13
Nodes (25): liquid_symbols(), Symbols trading at least `min_usd`/day, optionally limited to a market and     t, _add_liquidity(), bootstrap(), custom_screen(), get(), _india_ccc(), _live_path() (+17 more)

### Community 33 - "Community 33"
Cohesion: 0.13
Nodes (21): consolidate(), preferred_exchange_rank(), Collapse *candidates* referring to the same entity (same key_fn(c)) down to, Convenience rank_fn helper for the common "prefer one exchange, then break     t, _distinctive_phrase(), _load_english_words(), news_picks(), Common English words — a single-token company match on one of these     (ENERGY, (+13 more)

### Community 34 - "Community 34"
Cohesion: 0.13
Nodes (23): compare_ticker(), _dividend_yield_pct(), fetch_screener_ratios(), fetch_yfinance_ratios(), _first_df(), _first_row(), _get_yf_session(), _pct() (+15 more)

### Community 35 - "Community 35"
Cohesion: 0.13
Nodes (20): Breakout-quality columns for a scanner row, mirroring golden_cross.row_fields., row_fields(), _bq_fields(), bulk_download(), compute_darvas_box(), _first_df(), fundamental_scan(), _gc_fields() (+12 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (17): compare_models(), compute_features(), MLSignalEngine, DataFrame, ndarray, Series, Compute technical indicator features from OHLC.      AlQahtani et al. (2025) met, Z-score normalisation: Z = (X - μ) / σ     Applied per feature column as specifi (+9 more)

### Community 37 - "Community 37"
Cohesion: 0.11
Nodes (17): analysis(), count_bars(), get_news_source(), near_high(), news_source(), Register a news source. Provide RSS `feeds` for the default fetcher, or     deco, Register an analysis tool that the historical pipeline can run as a stage., Return the keys of every registered screener the candidate passes.     Lets the (+9 more)

### Community 38 - "Community 38"
Cohesion: 0.15
Nodes (13): ABC, AlphaVantageProvider, Article, FinnhubProvider, MarketauxProvider, NewsDataProvider, NewsProvider, One news item with a sentiment score in [-1, +1]. (+5 more)

### Community 39 - "Community 39"
Cohesion: 0.14
Nodes (15): liquid_universe(), main(), (set of liquid tickers, #all tickers) — liquid = top-2 turnover terciles on the, get_logger(), Configured logger: UTC timestamps, stdout + a per-day file. Idempotent., _utcstamp(), html(), main() (+7 more)

### Community 40 - "Community 40"
Cohesion: 0.16
Nodes (19): Nifty 50 P/E and P/B ratios — macro valuation context.         Nifty P/E > 25 =, _bootstrap_fallback(), check_r_packages(), compute_r_stats(), compute_technical_indicators_r(), detect_regimes_r(), install_r_packages(), DataFrame (+11 more)

### Community 41 - "Community 41"
Cohesion: 0.16
Nodes (21): build_feature_matrix(), discover_clusters(), extract_features(), extract_insights(), find_comoving_pairs(), load_and_clean(), main(), name_archetype() (+13 more)

### Community 42 - "Community 42"
Cohesion: 0.16
Nodes (21): build_sector_indices(), classify_sectors(), cluster_sectors(), extract_patterns(), fetch_sector(), load_returns(), _load_sector_cache(), load_universe() (+13 more)

### Community 43 - "Community 43"
Cohesion: 0.13
Nodes (17): capacity(), classify(), describe(), Gate, market_floor(), DataFrame, Floor a SCAN should apply: structural, plus policy where one was chosen.      De, Policy floor for one market in USD/day, or 0 where no policy was chosen.      Re (+9 more)

### Community 44 - "Community 44"
Cohesion: 0.17
Nodes (16): data(), eval_cell(), main(), build_xy(), ls_book_ir(), main(), Long top-tercile / short bottom-tercile of the PREDICTED return each week;     r, latest_features() (+8 more)

### Community 45 - "Community 45"
Cohesion: 0.16
Nodes (18): _amount(), corp_map(), f_score(), _fresh(), _get(), _key(), piotroski_inputs(), Path (+10 more)

### Community 46 - "Community 46"
Cohesion: 0.15
Nodes (19): _bare_krx(), _check(), collect(), fetch_corp_code_map(), fetch_filings(), _load_dotenv(), main(), DataFrame (+11 more)

### Community 47 - "Community 47"
Cohesion: 0.18
Nodes (19): _annual_series(), coverage(), fetch_companyfacts(), _hash_order(), load_cik_map(), load_store(), main(), parse_companyfacts() (+11 more)

### Community 48 - "Community 48"
Cohesion: 0.16
Nodes (18): assign_sectors(), data_gaps(), _dist_bar(), _jp_sectors_from_workbook(), _load_sector_cache(), _median(), _pctfmt(), pick_category() (+10 more)

### Community 49 - "Community 49"
Cohesion: 0.15
Nodes (20): build_rows(), classify(), _close_series(), _fx_map(), maintain(), _pct_change(), DataFrame, Series (+12 more)

### Community 50 - "Community 50"
Cohesion: 0.20
Nodes (18): build(), fundamentals_overlay(), _india_equity_names(), india_momentum_picks(), main(), oversold_picks(), DataFrame, Series (+10 more)

### Community 51 - "Community 51"
Cohesion: 0.20
Nodes (13): _load_prices(), main(), DataFrame, stage_join(), stage_monitor(), stage_mood(), stage_score(), main() (+5 more)

### Community 52 - "Community 52"
Cohesion: 0.22
Nodes (16): load_eps(), load_prices(), main(), month_ends(), nonoverlap_t(), pit_eps_panel(), DataFrame, Series (+8 more)

### Community 53 - "Community 53"
Cohesion: 0.19
Nodes (17): _clean_equities(), coverage(), _fresh_set(), _hash_order(), load_store(), main(), Deterministic, alphabet-independent ordering.      The whole point: a run that t, Drop non-equity instruments the ltm parquet is polluted with.      ltm/IN.parque (+9 more)

### Community 54 - "Community 54"
Cohesion: 0.17
Nodes (16): aqr_links(), _cached_get(), company_industry(), damodaran(), damodaran_companies(), french_factors(), industry_metric(), DataFrame (+8 more)

### Community 55 - "Community 55"
Cohesion: 0.23
Nodes (16): _assert_input_coverage(), build(), _debt(), _equity(), main(), piotroski(), DataFrame, Series (+8 more)

### Community 56 - "Community 56"
Cohesion: 0.17
Nodes (11): dsr(), expected_max_sr(), main(), López de Prado E[max SR] from N independent trials given their dispersion., Deflated Sharpe: P(true SR > E[max SR]) for the selected strategy., main(), DecisionLog, Path (+3 more)

### Community 57 - "Community 57"
Cohesion: 0.21
Nodes (16): Time a phase; logs START then DONE with elapsed seconds (even on error)., timed(), liquidity_mask(), load_panel(), main(), DataFrame, Series, Per regime: (BUY-SELL spread%, t), (BUY-book ret%, t), index ret%, excess%, n_we (+8 more)

### Community 58 - "Community 58"
Cohesion: 0.24
Nodes (16): build(), _expected_returns(), load_index_returns(), _load_ohlc(), load_picks(), load_returns(), _norm_index(), optimise() (+8 more)

### Community 59 - "Community 59"
Cohesion: 0.26
Nodes (15): _body(), _compression(), darvas_box(), _num(), DataFrame, Series, EMA-50: price above it, and the EMA itself rising., Did the range tighten into the breakout?      Compares the box's own width to th (+7 more)

### Community 60 - "Community 60"
Cohesion: 0.16
Nodes (7): build_symbol_year_table(), fit_factorial(), main(), DataFrame, Series, Cap extreme returns at the 1st/99th percentile. The raw Close-price     panel he, winsorize()

### Community 61 - "Community 61"
Cohesion: 0.20
Nodes (15): append_ipo_to_scan_excel(), discover_new_listings(), download_ipo_ohlc(), enrich_ipo(), main(), DataFrame, Path, Download maximum available OHLC history for new listings.     Uses period='max' (+7 more)

### Community 62 - "Community 62"
Cohesion: 0.15
Nodes (7): IndianRSSProvider, Indian financial-news via free RSS feeds — NO API key required.     Sources: Mon, Fetch + cache all feed entries once per run (market-wide pool)., Match feed entries by COMPANY NAME (preferred) rather than ticker.          If a, US financial-news via free RSS feeds — NO API key required.     Sources: CNBC (t, Overall market news sentiment (regime gauge) for the given market., USRSSProvider

### Community 63 - "Community 63"
Cohesion: 0.14
Nodes (15): cn_eastmoney(), eu(), eu_curated(), euronext_equities(), from_damodaran(), investpy_universe(), Full Euronext equity list from live.euronext.com (official CSV export),     mapp, European stock LISTINGS via investpy (Investing.com bundled lists): returns (+7 more)

### Community 64 - "Community 64"
Cohesion: 0.23
Nodes (15): append_manifest(), daterange(), download_document(), filter_filings(), get_api_key(), list_documents(), load_manifest(), main() (+7 more)

### Community 65 - "Community 65"
Cohesion: 0.23
Nodes (14): build(), convergence_block(), darvas_section(), latest_json(), latest_scan_xlsx(), main(), market_snapshot(), news_picks_block() (+6 more)

### Community 66 - "Community 66"
Cohesion: 0.27
Nodes (14): fetch_actual_eps(), fetch_and_cache(), fetch_board_meetings(), fetch_financial_results(), _get_json(), _load_cached(), main(), _new_session() (+6 more)

### Community 67 - "Community 67"
Cohesion: 0.19
Nodes (13): _classified_symbols(), load_events(), main(), DataFrame, Series, For each sector, the equal-weighted daily return of ITS MEMBERS,     precomputed, events_loader(market, symbols_set) -> DataFrame with columns     [ticker, event_, Symbols already sector-classified for cross_sectional_momentum.py,     read stra (+5 more)

### Community 68 - "Community 68"
Cohesion: 0.27
Nodes (14): anchor_events(), ann_ca_events(), ca_events(), car(), load_prices(), main(), pead_events(), DataFrame (+6 more)

### Community 69 - "Community 69"
Cohesion: 0.23
Nodes (14): breadth_png(), build_all(), _close_matrix(), DataFrame, _ramp(), Wide date × symbol close matrix for one market's priced rows., {'treemap'|'rrg'|'breadth': png_bytes} — only the ones that rendered., 1d% → colour: RED (≤-4) → neutral grey (0) → TEAL (≥+4). (+6 more)

### Community 70 - "Community 70"
Cohesion: 0.30
Nodes (13): detect_patterns(), Extremum, _match_cup_and_handle(), _match_double_top_bottom(), _match_head_and_shoulders(), PatternHit, Series, _rasterize_and_find_extrema() (+5 more)

### Community 71 - "Community 71"
Cohesion: 0.22
Nodes (13): _ccc(), compute_metrics(), evaluate(), DataFrame, Series, Return (passed, metrics). criteria is either a callable(metrics)->bool, or     a, Evaluate every stock; return a DataFrame of the ones that pass.      rank_by — m, Cash Conversion Cycle (days) = DIO + DSO - DPO, if inputs present. (+5 more)

### Community 72 - "Community 72"
Cohesion: 0.23
Nodes (13): build_report(), find_convergence(), get_fundamental_picks(), get_street_talk(), main(), print_report(), DataFrame, Market-mood gauge + per-ticker sentiment for the given symbols.     Returns (mar (+5 more)

### Community 73 - "Community 73"
Cohesion: 0.26
Nodes (13): data_state(), git_changes(), main(), pipeline_runs(), Path, Commits authored on `day`, with the files they touched., Which sections ran, how long, and what failed., Freshness of every registered dataset — the evidence a run was built on.      Ca (+5 more)

### Community 74 - "Community 74"
Cohesion: 0.30
Nodes (13): compute_price_changes(), load_all_events(), _load_bse_date_only(), _load_date_only(), _load_nse_eps_yoy_surprise(), _load_yahooquery_full(), _load_yfinance_cache(), main() (+5 more)

### Community 75 - "Community 75"
Cohesion: 0.23
Nodes (13): _annual(), companyfacts(), _first(), fundamentals(), _margin(), _pct(), _ratio(), Gross margin %, nulled if implausible (concept mismatch). (+5 more)

### Community 76 - "Community 76"
Cohesion: 0.24
Nodes (12): api_key(), extract(), list_annual(), load_code_map(), main(), parse_csv(), DataFrame, pull the 5-year summary: one row per (relative-year) with the mapped metrics. (+4 more)

### Community 77 - "Community 77"
Cohesion: 0.23
Nodes (12): fetch_filings_list(), main(), parse_xbrl_document(), process_xbrl_zip(), DataFrame, Fetch list of EDINET filings within date range.      Args:       start_date: YYY, Parse XBRL XML document and extract financial metrics.      Args:       xbrl_con, Process a ZIP archive containing XBRL files (bulk download format).      Args: (+4 more)

### Community 78 - "Community 78"
Cohesion: 0.28
Nodes (12): add_zscores(), attach_industry(), build_india_panel(), build_us_panel(), main(), DataFrame, Series, Join Damodaran Industry Group by bare ticker, market-specific     exchange filte (+4 more)

### Community 79 - "Community 79"
Cohesion: 0.33
Nodes (12): build(), build_market(), _latest_closes(), main(), _names(), DataFrame, Path, (symbol, close, close_date) at each symbol's own last bar. (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.24
Nodes (12): _bench_since(), build(), _bundle_name(), _closes(), load(), maybe_build(), Series, Monthly rebalance rhythm: rebuild on the first run of a new month (or     when n (+4 more)

### Community 81 - "Community 81"
Cohesion: 0.26
Nodes (12): _code_lines(), git_state(), main(), orphans(), path_audit(), _py_files(), Path, Files with a hardcoded home path and no env-var escape hatch. (+4 more)

### Community 82 - "Community 82"
Cohesion: 0.27
Nodes (11): audit(), _classify(), _handler_is_fatal(), _imported(), _local_modules(), main(), Path, {module: required} for one file.      module-level import            -> required (+3 more)

### Community 83 - "Community 83"
Cohesion: 0.32
Nodes (11): collect_ticker_8ks(), _fetch_submissions(), main(), DataFrame, Session, TICKER -> zero-padded 10-digit CIK, from SEC's own ticker map.     Identical sou, All 8-K filings from the 'recent' window of the submissions JSON,     with the I, run() (+3 more)

### Community 84 - "Community 84"
Cohesion: 0.29
Nodes (11): book_series(), daily_close(), leg_pnl(), main(), new_filters(), path_returns(), DataFrame, At each weekly formation date, per name: raw 2wk return, and the favourable/ (+3 more)

### Community 85 - "Community 85"
Cohesion: 0.24
Nodes (11): _articles_for(), classify(), _clean_name(), main(), Company-specific headlines only: named in the title, not a market wrap., (verdict, score, n, why) for one stock's headlines., Company name for `sym`, for title matching. Falls back to the symbol., Distinctive tokens that must appear in a TITLE to count as a match.      Drops c (+3 more)

### Community 86 - "Community 86"
Cohesion: 0.33
Nodes (11): _download(), get(), get_closes(), _path(), DataFrame, {symbol: DataFrame(Open..Volume, DatetimeIndex)} — refreshed incrementally., Aligned close-price matrix — drop-in for fetch_universe_prices()., Bring the market's cache up to date, fetching ONLY missing dates. (+3 more)

### Community 87 - "Community 87"
Cohesion: 0.30
Nodes (11): build_adjusted(), _candidates(), confirm(), detect(), main(), DataFrame, Cross-check every detected event against yfinance's split calendar.     Only cal, SPARSE overlay (unlike India's full copy): the non-IN panels are already     yfi (+3 more)

### Community 88 - "Community 88"
Cohesion: 0.21
Nodes (11): build_exchange_groups(), enrich_stocks(), _fetch_one(), format_stock_display(), generate_stock_table_html(), DataFrame, Fetch company name, PE, sector, exchange for one stock., Enrich a screener results DataFrame with company name, PE, exchange.      df: (+3 more)

### Community 89 - "Community 89"
Cohesion: 0.38
Nodes (10): build(), convert(), _fx(), load(), main(), matrix(), DataFrame, USD value of 1 unit of `ccy` on `date` (latest if None). (+2 more)

### Community 90 - "Community 90"
Cohesion: 0.42
Nodes (10): fetch_and_cache(), fetch_financial_results(), fetch_scrip_list(), _get_json(), _load_cached(), main(), _new_session(), DataFrame (+2 more)

### Community 91 - "Community 91"
Cohesion: 0.31
Nodes (10): collect_disclosures(), fetch_available_dates(), _fetch_page(), _jp_tickers_from_sector_cache(), main(), _max_page(), _parse_rows(), DataFrame (+2 more)

### Community 92 - "Community 92"
Cohesion: 0.29
Nodes (10): _chunks(), _classified_symbols(), fetch_batch(), _full_universe_symbols(), main(), DataFrame, resume=True (default): skip tickers that already have a row with     real histor, The complete OHLCV-panel universe (thousands/market), not just the     ~700/mark (+2 more)

### Community 93 - "Community 93"
Cohesion: 0.25
Nodes (10): fetch_companies(), fetch_filings(), main(), parse_xbrl_financials(), Fetch and parse XBRL filing (financial statements).      XBRL is XML-based finan, # TODO: Parse XBRL XML using arelle or pd.read_xml, Store fundamentals DataFrame into Postgres market_data.japan_fundamentals., Fetch all listed companies from EDINET.     Returns: DataFrame with columns [cod (+2 more)

### Community 94 - "Community 94"
Cohesion: 0.25
Nodes (8): _files(), get(), _parse(), present(), Path, Resolve one secret. os.environ wins, then .env, then ~/.env.local., Resolve several, reporting which are MISSING by name.      Names only — never va, require()

### Community 95 - "Community 95"
Cohesion: 0.31
Nodes (10): build_symbol_year_table(), fit_factorial(), main(), DataFrame, Series, Same logic as year_by_year_consistency.py: per screener, per     calendar year,, Same construction as factorial_screener_analysis.py's own function:     one row, Same light secondary guard as factorial_screener_analysis.py --     the primary (+2 more)

### Community 96 - "Community 96"
Cohesion: 0.31
Nodes (10): build_symbol_year_table(), fit_factorial(), main(), DataFrame, Series, Exact port of year_by_year_consistency.py's logic: per screener, per     calenda, Identical approach to factorial_screener_analysis.build_symbol_year_table:     o, Same secondary guard as factorial_screener_analysis.py: the underlying     panel (+2 more)

### Community 97 - "Community 97"
Cohesion: 0.35
Nodes (10): fetch_kospi_benchmark(), _flag_stale_halted_days(), load_ohlcv_kr(), main(), DataFrame, Korea-specific data-quality addition -- NOT part of the reused     factorial_scr, Sanity check before trusting the run: any xret in the millions-of-     percent r, Fetch ^KS11 (KOSPI Composite) daily OHLCV via yfinance and reshape it     to mat (+2 more)

### Community 98 - "Community 98"
Cohesion: 0.27
Nodes (10): create_schema(), insert_snapshot(), load_latest_scan(), main(), DataFrame, Insert/update current snapshot from latest scan., Check Postgres tables., Load latest Japan market scan workbook. (+2 more)

### Community 99 - "Community 99"
Cohesion: 0.33
Nodes (10): _get(), _latest_scan(), main(), mc_code(), mc_price(), Path, Price + close date from screener.in's company header., NSE symbol -> moneycontrol's internal code (RELIANCE -> RI). (+2 more)

### Community 100 - "Community 100"
Cohesion: 0.36
Nodes (9): _fetch(), hhi(), main(), nse_members(), DataFrame, Path, spdr_holdings(), validate() (+1 more)

### Community 101 - "Community 101"
Cohesion: 0.31
Nodes (9): build_panel(), evaluate_stock(), load_stocks(), main(), DataFrame, Train classifier walk-forward, build long/flat strategy, compare vs buy-hold., Build a per-bar feature panel with a forward-direction label.      Label = 1 if, parallel_map() (+1 more)

### Community 102 - "Community 102"
Cohesion: 0.31
Nodes (9): main(), DataFrame, Path, Series, How much of the cell's total excess return comes from its single best name., Mean excess return with the YEAR as the unit of observation.      Pooling stock-, run(), _top1_share() (+1 more)

### Community 103 - "Community 103"
Cohesion: 0.38
Nodes (8): build_symbol_year_table(), fit_factorial(), main(), DataFrame, Series, Light secondary guard against genuine fat-tailed (non-split, non-     stale-data, winsorize(), main()

### Community 104 - "Community 104"
Cohesion: 0.36
Nodes (9): add_working_capital_ratios(), fix_currency_scaled_thresholds(), main(), merge_backup_fields(), DataFrame, Quick ratio, inventory turnover (+ N-years-back), debtor days (+     N-years-bac, Recompute the three USD-literal-dependent pass columns using INR-scaled     thre, Merge in receivables/inventory/industry/cogs from IN_screener_only_     backup.p (+1 more)

### Community 105 - "Community 105"
Cohesion: 0.29
Nodes (9): fetch_fundamentals(), load_tse_stocks(), main(), Store fundamentals DataFrame into Postgres.      Creates table if not exists., Check Postgres schema for Japan fundamentals., Load TSE stock codes.      Returns: List of codes (e.g., ["8001", "8002", ...]), Fetch fundamentals for a single stock via yfinance.      Args:       code: TSE c, store_postgres() (+1 more)

### Community 106 - "Community 106"
Cohesion: 0.36
Nodes (9): build(), current_prices(), main(), _norm(), DataFrame, Add the TOP qualifiers as `signal` tier. Existing rows are NEVER touched     — a, Ledger vs workbook symbol normalisation. KR codes lose leading zeros in     the, (symbol_norm, price, tier) from the newest scan workbook's All_Stocks. (+1 more)

### Community 107 - "Community 107"
Cohesion: 0.33
Nodes (9): main(), _piotroski(), DataFrame, Piotroski F-score from the SAME statements — 7 of the 9 tests.      Computed her, All available years for the first matching statement line, newest first., ROCE for one symbol: latest, cash-adjusted, and its 5-year stability.      THREE, roace_one(), _series() (+1 more)

### Community 108 - "Community 108"
Cohesion: 0.29
Nodes (9): _liquidity(), main(), # WHY: without a liquidity floor the screener recommends stocks you cannot buy., (median daily turnover in Rs, tier) — tier is None when below the floor., Run the price screeners on one symbol's bhavcopy OHLCV frame., _retier(), _screen_one(), pct_change() (+1 more)

### Community 109 - "Community 109"
Cohesion: 0.31
Nodes (7): backfill(), collect(), measured(), _parse_banner(), Path, Steps with real [STEP] markers: duration = next marker - this one., Reconstruct pre-marker runs from artifact mtimes. Inferred, not measured.

### Community 110 - "Community 110"
Cohesion: 0.29
Nodes (9): ccc_map(), ccc_screen(), fetch_screen(), _header(), DataFrame, {NSE symbol: cash conversion cycle (days)} from the screen., Column names from the first table's <th> cells (handles nested markup)., Paginate a screener.in screen → DataFrame with a Symbol column.      Parsed row- (+1 more)

### Community 111 - "Community 111"
Cohesion: 0.33
Nodes (9): analyse_linkage(), detect_shocks_and_returns(), main(), DataFrame, Aggregate forward returns by implied-sentiment direction × horizon., Poll live news sentiment and append to the forward log with a timestamp.      Ru, Detect implied-news shocks and record forward returns at each horizon.      A 's, run_historical() (+1 more)

### Community 112 - "Community 112"
Cohesion: 0.20
Nodes (10): annotate_learned(), assign_recommendations(), _learned_recs(), main(), Regime-conditional map from strategy_regime_survival.py:     {mkt: {bull_rule, b, Set r['rec'] (BUY/HOLD/SELL) and r['rec_rule'] per each market's winning     rul, (market, symbol) -> rec_learned from the offline learned model     (learned_reco, SHADOW mode: attach the learned-model recommendation (r['rec_learned']) and (+2 more)

### Community 113 - "Community 113"
Cohesion: 0.36
Nodes (9): build(), _fmt(), _load(), main(), DataFrame, Series, Percent return over `bars` sessions, or None if history is too short.      None, report() (+1 more)

### Community 114 - "Community 114"
Cohesion: 0.20
Nodes (10): Market Playbook Visualization, Project Retrospective, Project Retrospective Visualization, Screener Evaluation (India), Screener Evaluation Visualization, Strategy Suitability Matrix, Strategy Regime Survival, Valuation Clustering Report (+2 more)

### Community 115 - "Community 115"
Cohesion: 0.39
Nodes (8): latest_fund(), latest_price(), main(), norm(), DataFrame, Series, strip exchange suffix for cross-source ticker matching (7203.T -> 7203)., Index

### Community 116 - "Community 116"
Cohesion: 0.39
Nodes (8): compute_pair_correlations(), fetch_pair_prices(), find_preferred_pairs(), DataFrame, For each pair, fetches BOTH {common_code}{suffix} and     {preferred_code}{suffi, For each pair with usable data on both sides, computes the correlation     of da, Scans KOSPI + KOSDAQ for preferred-share names, strips the suffix, and     keeps, run()

### Community 117 - "Community 117"
Cohesion: 0.33
Nodes (7): compute(), main(), DataFrame, screener.in's quarterly table: (quarter_label, sales_cr, pat_cr, eps).      Pars, _screener_quarters(), validate(), Series

### Community 118 - "Community 118"
Cohesion: 0.42
Nodes (7): require_fresh(), run(), run_critical(), section_end(), pipeline_lib.sh script, step(), warn_stale()

### Community 119 - "Community 119"
Cohesion: 0.44
Nodes (8): _fmt(), _logs(), main(), parse(), Path, One log -> {section, date, steps[{label, start, dur}], total}.      Duration is, _section_of(), show_run()

### Community 120 - "Community 120"
Cohesion: 0.22
Nodes (9): Darvas Box Scan, Full European Market Scan, Full Indian Market Scan, Full US Market Scan, PEGY Ratio, Piotroski F-Score, Singapore Stock Daily Report, Darvas Strategy Module (+1 more)

### Community 121 - "Community 121"
Cohesion: 0.43
Nodes (7): load_closes(), main(), DataFrame, Per-rule DataFrame of +1 (BUY) / −1 (SELL) / 0 (HOLD) aligned to w., (mean BUY−SELL fwd spread, de-overlapped t) for one rule.      Forward returns w, score(), zone_signals()

### Community 122 - "Community 122"
Cohesion: 0.43
Nodes (7): _diagnose_limit_move_clustering(), fetch_benchmark(), main(), DataFrame, Fallback chain: 000300.SS (CSI 300) -> ^SSEC (Shanghai Composite,     literal ti, Reports (does not exclude/fix) clustering of daily %% changes at     China's exc, _reshape_yf_index()

### Community 123 - "Community 123"
Cohesion: 0.50
Nodes (7): attach_returns(), fetch_nikkei_benchmark(), load_jp_ohlcv(), main(), DataFrame, Fetch ^N225 via yfinance and reshape to the OHLCV schema every     screener/forw, run_screeners()

### Community 124 - "Community 124"
Cohesion: 0.46
Nodes (7): annual_firm_pnl(), fetch_comparables(), main(), DataFrame, Series, Annual per-desk + firm PAT under a given {mkt:{bull_rule,bear_rule}} map., stats()

### Community 125 - "Community 125"
Cohesion: 0.43
Nodes (7): fetch_jq_returns(), get_api_key(), jq_code(), load_env_file(), main(), our_returns(), 7203.T -> 7203 (V2 accepts 4- or 5-char codes).

### Community 126 - "Community 126"
Cohesion: 0.50
Nodes (7): _dart_date_override(), _from_yahooquery(), _from_yfinance_cache(), load_combined_events(), main(), DataFrame, Korea only: DART periodic-report filing_date is a real regulatory     timestamp,

### Community 127 - "Community 127"
Cohesion: 0.50
Nodes (7): _emit(), fundamentals(), main(), price_signals(), DataFrame, per-ticker: last close, golden-cross (50>200 DMA), 12M momentum, avg turnover., screen()

### Community 128 - "Community 128"
Cohesion: 0.39
Nodes (7): build_adjusted(), build_factors(), main(), DataFrame, Adjusted partitions. Only symbols WITH events differ from raw; the rest     are, Cross-check vs yfinance's independent adjustment, ACROSS each event.      For a, validate()

### Community 129 - "Community 129"
Cohesion: 0.32
Nodes (7): desk_quarterly(), main(), DataFrame, Series, Per-week forward-2wk return of the regime-conditional, liquidity-gated     long-, Quarterly P&L for one desk from bi-weekly (non-overlapping) holds., weekly_book_returns()

### Community 130 - "Community 130"
Cohesion: 0.43
Nodes (7): apply_overlay(), desk_book(), main(), Series, Weekly (date-indexed) book return under equal-weight / inverse-vol sizing,     p, Vol-target the inverse-vol book and apply the drawdown kill-switch., stats()

### Community 131 - "Community 131"
Cohesion: 0.50
Nodes (4): Entry, main(), render(), _wrap()

### Community 132 - "Community 132"
Cohesion: 0.32
Nodes (7): _fresh_in(), _fresh_us(), main(), DataFrame, Per-ticker parquets from market_cache -> long frame., bhavcopy LMDB -> long frame., update()

### Community 133 - "Community 133"
Cohesion: 0.39
Nodes (7): edgar_current(), _fetch(), main(), nse_current(), Path, old NSE symbol -> CURRENT symbol, chains resolved., rename_map()

### Community 135 - "Community 135"
Cohesion: 0.39
Nodes (7): fetch_corp_codes(), get_key(), main(), parse_accounts(), Path, Download corp_code map; return {stock_code: (corp_code, corp_name)}., Map DART account rows → canonical fields.      fs_div (CFS/OFS) is a request par

### Community 136 - "Community 136"
Cohesion: 0.46
Nodes (7): extract_for(), main(), psql(), DataFrame, One canonical frame for (source, market), reusing merge-script loaders., run_batch(), show_status()

### Community 137 - "Community 137"
Cohesion: 0.52
Nodes (6): build(), main(), Quarterly rebalance dates, stopping HOLD_BARS before data end., report(), sample(), DuckDBPyConnection

### Community 138 - "Community 138"
Cohesion: 0.43
Nodes (6): _load_seed(), main(), DataFrame, Path, Return the subset of tickers that return data from a 5-day yfinance pull., _validate()

### Community 139 - "Community 139"
Cohesion: 0.43
Nodes (6): amihud(), corwin_schultz(), main(), DataFrame, Amihud ILLIQ: price impact per $1M traded (scaled), per symbol., Corwin-Schultz (2012) two-day high-low spread estimator, per symbol.      beta

### Community 140 - "Community 140"
Cohesion: 0.43
Nodes (6): expectations(), latest_fundamentals(), main(), DataFrame, Latest-FY net_income / shares / total-equity per ticker for a market., (name, passed, detail) — GE-style suite over the ratios table.

### Community 141 - "Community 141"
Cohesion: 0.52
Nodes (6): _cache_path(), fetch_and_cache(), _load_cached(), main(), DataFrame, Path

### Community 142 - "Community 142"
Cohesion: 0.52
Nodes (6): jq_fins(), kb_top(), latest_close(), load_env_file(), main(), names_from_master()

### Community 143 - "Community 143"
Cohesion: 0.43
Nodes (4): _first_df(), get_cache(), One-shot cache warm-up for a symbol list.     Call this once (takes ~45 min for, warm_cache()

### Community 144 - "Community 144"
Cohesion: 0.43
Nodes (6): bh_fdr(), main(), DataFrame, Series, quarter_t(), One-sample t across calendar-quarter means.

### Community 145 - "Community 145"
Cohesion: 0.57
Nodes (6): load_prices(), main(), nonoverlap_t(), pit_eps(), DataFrame, Series

### Community 146 - "Community 146"
Cohesion: 0.52
Nodes (6): fund_records(), load_px(), main(), nonoverlap_t(), pit_panel(), run()

### Community 147 - "Community 147"
Cohesion: 0.43
Nodes (6): create_sample_xbrl(), create_test_zip(), main(), Path, Create a sample XBRL document for a TSE company., Create test XBRL ZIP with a few sample companies.

### Community 148 - "Community 148"
Cohesion: 0.48
Nodes (6): find_xbrl_files(), main(), process_batch(), Path, Find all XBRL ZIP files matching pattern., Process all files, consolidate results into Postgres.      Returns: Total rows i

### Community 149 - "Community 149"
Cohesion: 0.48
Nodes (6): canonize(), eu_currency(), load_market(), main(), DataFrame, Load + map one market. Returns canonical frame (may concat sources).

### Community 150 - "Community 150"
Cohesion: 0.48
Nodes (6): load_dart_fresh(), load_parquet(), main(), norm_ticker(), DataFrame, Strip .KS/.KQ suffixes → bare 6-digit code.

### Community 151 - "Community 151"
Cohesion: 0.53
Nodes (5): _fetch(), main(), _pit_tercile(), Series, Trailing-window tercile label per day, no lookahead.

### Community 152 - "Community 152"
Cohesion: 0.47
Nodes (5): desk_liquidity(), impact_bps(), main(), Median ADV ($) and daily vol of the liquid (HIGH+MEDIUM) universe., Round-trip cost in bps for trading q_usd in a name of adv_usd, sigma.

### Community 153 - "Community 153"
Cohesion: 0.53
Nodes (5): load_ohlcv_in(), main(), DataFrame, Same >=5yr-history filter and _flag_split_days pass as fst.load_ohlcv(),     poi, run_technical_screeners()

### Community 154 - "Community 154"
Cohesion: 0.40
Nodes (6): from_yfinance(), _pick(), _quarterly_rows(), Row for the first matching label, EXACT match preferred.      🔴 Substring matchi, Per-QUARTER (ticker, quarter_end, revenue, net_income) rows for Bull Cartel., Per-fiscal-year rows for one NSE symbol, or [] on any failure.      Never raises

### Community 155 - "Community 155"
Cohesion: 0.60
Nodes (5): main(), DataFrame, r2(), sectors(), year_end_price()

### Community 156 - "Community 156"
Cohesion: 0.47
Nodes (5): compute(), DataFrame, 50/200-DMA state for one symbol. Never raises — returns a null result., Scan-row fields, named consistently across every market., row_fields()

### Community 157 - "Community 157"
Cohesion: 0.60
Nodes (5): _append_log(), check(), _load_snapshot(), _save_snapshot(), get_universe()

### Community 158 - "Community 158"
Cohesion: 0.53
Nodes (5): api_key(), liquid_jp(), main(), (jquants_code, warehouse_symbol) for the liquid JP universe (top turnover)., to_num()

### Community 159 - "Community 159"
Cohesion: 0.47
Nodes (5): analyse(), load(), _metrics(), DataFrame, Series

### Community 160 - "Community 160"
Cohesion: 0.40
Nodes (5): bh_fdr(), deflated_sharpe(), main(), Benjamini-Hochberg: returns boolean survivors for FDR level q., Probability the observed Sharpe exceeds the max expected from     n_trials of no

### Community 161 - "Community 161"
Cohesion: 0.60
Nodes (5): latest_close(), main(), 5-session return AS OF `date` — the mean-revert signal a pick would have     sho, _series(), trailing_5d_at()

### Community 162 - "Community 162"
Cohesion: 0.47
Nodes (5): main(), DataFrame, Median within year, then across years — the year is the observation.      Announ, run(), year_clustered()

### Community 163 - "Community 163"
Cohesion: 0.53
Nodes (5): build_index_df(), main(), DataFrame, Same dma200/dma200_sl construction as walk_forward_backtest.py's     fetch_index, tag_regimes()

### Community 164 - "Community 164"
Cohesion: 0.40
Nodes (5): analyse(), load_highlights(), DataFrame, min_turnover_usd>0 pre-filters to liquid names — far faster and surfaces     onl, Load the most recent global highlights as a DataFrame (for later reference).

### Community 165 - "Community 165"
Cohesion: 0.53
Nodes (5): _fetch(), _latest_scan(), main(), Parse screener.in's header: '<Name> Rs 1,099 -1.72% 14 Jul - close price'., validate()

### Community 166 - "Community 166"
Cohesion: 0.47
Nodes (5): build_duckdb(), build_market(), main(), Path, A small .duckdb of VIEWS over the parquet — no data copied into it.      Views k

### Community 167 - "Community 167"
Cohesion: 0.33
Nodes (6): _load_ohlc(), Cache-key spellings for a watchlist symbol in the warehouse.      The watchlist, Recent OHLC for one symbol from the local cache. None if not cached., symbol -> OHLC frame for one market from the warehouse. Last TWO year     partit, _warehouse_frames(), _wh_candidates()

### Community 168 - "Community 168"
Cohesion: 0.60
Nodes (5): log_error(), log_info(), log_step(), log_warn(), edinet_process_and_archive.sh script

### Community 169 - "Community 169"
Cohesion: 0.53
Nodes (5): load_parquet(), main(), parse_edinet_zip(), DataFrame, Extract canonical metrics from one EDINET CSV ZIP (type=5 download).

### Community 170 - "Community 170"
Cohesion: 0.50
Nodes (4): features(), main(), DataFrame, per-ticker business-economics profile from the deep fundamentals + all_ratios.

### Community 171 - "Community 171"
Cohesion: 0.60
Nodes (4): collect(), main(), DataFrame, universe()

### Community 172 - "Community 172"
Cohesion: 0.70
Nodes (4): evaluate(), main(), metrics(), pe_panel()

### Community 173 - "Community 173"
Cohesion: 0.60
Nodes (4): kr_universe(), main(), (net_income, equity) for a company-year via cached DART statements., year_amounts()

### Community 174 - "Community 174"
Cohesion: 0.50
Nodes (4): build_debt_cycle(), main(), DataFrame, Consecutive-years-of-declining-debt streak, per (ticker, fy_end).     A break (d

### Community 175 - "Community 175"
Cohesion: 0.40
Nodes (4): load(), merge(), ({symbol: fundamentals_row}, source_filename) from the newest usable workbook., Rows for symbols served from cache, with price fields refreshed from today.

### Community 176 - "Community 176"
Cohesion: 0.70
Nodes (4): load(), main(), DataFrame, r2()

### Community 177 - "Community 177"
Cohesion: 0.70
Nodes (4): liquid_jp(), main(), pick(), ticker()

### Community 178 - "Community 178"
Cohesion: 0.60
Nodes (4): main(), n8n_runs(), pipeline_runs(), Every completed run section in the last few days of pipeline logs.

### Community 180 - "Community 180"
Cohesion: 0.60
Nodes (4): main(), DataFrame, sector_map(), year_end_price()

### Community 181 - "Community 181"
Cohesion: 0.40
Nodes (5): Sakana AI Comparison, Why These Filters Win, Caveman Summary, Paper Claim Audit, Piotroski Liquidity Paper

### Community 182 - "Community 182"
Cohesion: 0.40
Nodes (5): Daily Pipeline, Data Index Utility, Data Registry, Ingest Script, Mailer Script

### Community 183 - "Community 183"
Cohesion: 0.83
Nodes (3): main(), norm_symbol(), parse_one()

### Community 184 - "Community 184"
Cohesion: 0.83
Nodes (3): bao_code(), liquid_cn(), main()

### Community 185 - "Community 185"
Cohesion: 0.67
Nodes (3): inspect(), main(), (rows, tickers, latest_date, updated_at) from the file(s).

### Community 186 - "Community 186"
Cohesion: 0.67
Nodes (3): load_consolidated_events(), main(), DataFrame

### Community 187 - "Community 187"
Cohesion: 0.67
Nodes (3): main(), Run one historical-analysis stage as a subprocess; capture summary., run_stage()

### Community 188 - "Community 188"
Cohesion: 0.67
Nodes (3): book(), main(), DataFrame

### Community 189 - "Community 189"
Cohesion: 0.50
Nodes (3): BHAV_CACHE, MARKET_CACHE, run_fundamentals_offhours.sh script

### Community 190 - "Community 190"
Cohesion: 0.67
Nodes (3): main(), px_source_sql(), OVERLAY-FIRST price source: non-IN panels are yfinance-adjusted at     collectio

### Community 191 - "Community 191"
Cohesion: 0.67
Nodes (3): main(), probe(), live reachability — HTTP status or error class (best-effort, short timeout).

### Community 192 - "Community 192"
Cohesion: 0.67
Nodes (3): main(), Live-fetch the screener.in CCC screen and sanity-check the result.     Returns (, run()

### Community 193 - "Community 193"
Cohesion: 0.67
Nodes (3): main(), yfinance's REAL current assets / current liabilities, per fiscal year., truth()

### Community 195 - "Community 195"
Cohesion: 0.50
Nodes (4): Cost Intimation Drift, PIT Event Studies, Recommendation ROI, Strategy Report Template

### Community 196 - "Community 196"
Cohesion: 0.50
Nodes (4): Data Check 2026-07-25, Data Ledger, Data Quality Report, Data Sufficiency Audit

### Community 197 - "Community 197"
Cohesion: 0.67
Nodes (3): fetch_year(), main(), DataFrame

### Community 209 - "Community 209"
Cohesion: 0.67
Nodes (3): Data Sufficiency Guard, CFA Ratio Definitions, Valuation Reversion Backtest

### Community 210 - "Community 210"
Cohesion: 0.67
Nodes (3): Confusion Matrix Visualization, 70 Trading Strategies Evaluation, Strategy Evaluation Visualization

### Community 211 - "Community 211"
Cohesion: 0.67
Nodes (3): Profitability Optimizer Report, Quarterly Earnings Report, Zone Rules by Market

## Knowledge Gaps
- **93 isolated node(s):** `cn_collect_loop.sh script`, `cn_shards_run.sh script`, `factor_tests.sh script`, `ingest.sh script`, `lint.sh script` (+88 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **67 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `series()` connect `Community 12` to `Community 0`, `Community 1`, `Community 2`, `Community 13`, `Community 18`, `Community 23`, `Community 25`, `Community 29`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `StockData` connect `Community 11` to `Community 32`, `Community 164`, `Community 71`, `Community 40`, `Community 117`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `NSEDataFetcher` connect `Community 8` to `Community 40`, `Community 18`, `Community 22`, `Community 23`, `Community 29`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **What connects `cn_collect_loop.sh script`, `cn_shards_run.sh script`, `factor_tests.sh script` to the rest of the system?**
  _93 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.0654490106544901 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.060528559249786874 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.0689484126984127 - nodes in this community are weakly interconnected._