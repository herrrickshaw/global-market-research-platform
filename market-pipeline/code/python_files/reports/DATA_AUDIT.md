# Data audit — 2026-08-24 19:53

Warehouse-readiness of every price store, checked on five axes that fail independently: **integrity**, **adjustment**, **corruption**, **completeness**, **freshness**. A store can pass one and be unusable on another.

## Verdict per panel

| tree | mkt | rows | syms | span | lag | integrity | adjustment | corruption | verdict |
|---|---|---:|---:|---|---:|---|---|---|---|
| ohlcv (raw) | IN | 4,560,409 | 7,507 | 2016-01-01 → 2026-08-21 | 3d | clean | **0.03%** unadj | 115 (25.2/M) | 🟡 cleanable — needs an outlier rule |
| ohlcv (raw) | US | 16,446,833 | 9,938 | 2016-06-27 → 2026-08-21 | 3d | clean | **0.20%** unadj | 2,173 (132.1/M) | 🔴 unusable for returns |
| ohlcv (raw) | JP | 7,412,057 | 3,572 | 2016-06-27 → 2026-08-24 | 0d | clean | clean | 3 (0.4/M) | 🟢 warehouse-ready |
| ohlcv (raw) | KR | 5,349,826 | 2,776 | 2016-06-27 → 2026-08-24 | 0d | clean | clean | 35 (6.5/M) | 🟡 cleanable — needs an outlier rule |
| ohlcv (raw) | EU | 3,818,743 | 1,666 | 2016-06-27 → 2026-08-21 | 3d | clean | clean | 22 (5.8/M) | 🟡 cleanable — needs an outlier rule |
| ohlcv (raw) | CN | 10,010,203 | 5,188 | 2016-06-27 → 2026-07-01 | 54d | clean | clean | 10 (1.0/M) | 🟠 stale |
| ohlcv_adj | IN | 4,555,615 | 7,494 | 2016-01-01 → 2026-08-20 | 4d | clean | clean | 64 (14.0/M) | 🟡 cleanable — needs an outlier rule |
| ohlcv_adj | US | — | — | — | — | — | — | — | **NO PARTITIONS** dir exists, contents: ['corrected_symbols.parquet'] |
| ohlcv_adj | JP | — | — | — | — | — | — | — | **NO PARTITIONS** dir exists, contents: ['corrected_symbols.parquet'] |
| ohlcv_adj | KR | — | — | — | — | — | — | — | **NO PARTITIONS** dir exists, contents: ['corrected_symbols.parquet'] |

## Integrity detail

| tree | mkt | dup (Date,Symbol) | High<Low | Close outside bar | Close<=0 | Vol<0 | null Close |
|---|---|---:|---:|---:|---:|---:|---:|
| ohlcv (raw) | IN | 0 | 0 | 0 | 0 | 0 | 0 |
| ohlcv (raw) | US | 0 | 0 | 0 | 0 | 0 | 0 |
| ohlcv (raw) | JP | 0 | 0 | 0 | 0 | 0 | 0 |
| ohlcv (raw) | KR | 0 | 0 | 0 | 0 | 0 | 0 |
| ohlcv (raw) | EU | 0 | 0 | 0 | 0 | 0 | 0 |
| ohlcv (raw) | CN | 0 | 0 | 0 | 0 | 0 | 0 |
| ohlcv_adj | IN | 0 | 0 | 0 | 0 | 0 | 0 |

## Adjustment and corruption

`split-like` = daily close ratio outside [0.55, 1.82] — a corporate action, not a price move. `corrupt` = ratio beyond 10x in one session, which no split explains either.

| tree | mkt | split-like | as % of bars | corrupt (>=10x) | per million bars | max daily ratio |
|---|---|---:|---:|---:|---:|---:|
| ohlcv (raw) | IN | 1,398 | 0.031% | 115 | 25.2 | 426.0 |
| ohlcv (raw) | US | 33,245 | 0.202% | 2,173 | 132.1 | 7,801,928.0 |
| ohlcv (raw) | JP | 53 | 0.001% | 3 | 0.4 | 19,771,264.6 |
| ohlcv (raw) | KR | 266 | 0.005% | 35 | 6.5 | 191.2 |
| ohlcv (raw) | EU | 332 | 0.009% | 22 | 5.8 | 100.1 |
| ohlcv (raw) | CN | 67 | 0.001% | 10 | 1.0 | 98.8 |
| ohlcv_adj | IN | 867 | 0.019% | 64 | 14.0 | 426.0 |

## Completeness

| tree | mkt | sessions | expected | missing | median sessions/symbol | symbols < 200 bars |
|---|---|---:|---:|---:|---:|---:|
| ohlcv (raw) | IN | 2,625 | 2,616 | -0.3% | 29 | 4,464 |
| ohlcv (raw) | US | 2,553 | 2,557 | 0.2% | 2,096 | 1,322 |
| ohlcv (raw) | JP | 2,503 | 2,488 | -0.6% | 2,498 | 489 |
| ohlcv (raw) | KR | 2,488 | 2,478 | -0.4% | 2,486 | 202 |
| ohlcv (raw) | EU | 2,646 | 2,588 | -2.2% | 2,560 | 59 |
| ohlcv (raw) | CN | 2,429 | 2,432 | 0.1% | 2,429 | 49 |
| ohlcv_adj | IN | 2,624 | 2,615 | -0.3% | 28 | 4,452 |

`symbols < 200 bars` matters because a 200-day moving average — which the Darvas, golden-cross and regime screens all depend on — is undefined for those names. They are silently dropped by every screen, so a large count here is unmeasured universe shrinkage.

## Postgres `market_data`

| schema | table | rows |
|---|---|---:|
| public | `ohlcv_history` | 38,235,027 |
| public | `ohlcv_history_current` | 32,896,842 |
| funds | `nav` | 22,345,052 |
| public | `fact_screener_signal` | 4,980,728 |
| bhavcopy | `nse_deep_ohlcv` | 4,423,382 |
| public | `fact_screener_signal_current` | 3,874,417 |
| fundamentals | `india_pe_daily` | 1,979,108 |
| bhavcopy | `bhavcopy_ohlcv` | 1,925,343 |
| bhavcopy | `bse_raw` | 1,418,977 |
| bhavcopy | `cleaned_ohlcv` | 1,243,238 |
| bhavcopy | `nse_raw` | 677,544 |
| market_daily | `snapshots` | 495,161 |
| public | `global_fundamentals` | 245,116 |
| indices | `nse_daily` | 240,622 |
| public | `fact_insider_transaction` | 204,977 |
| public | `fact_short_interest` | 97,555 |
| public | `fact_short_interest_current` | 97,555 |
| indices | `custom_daily` | 62,535 |
| fundamentals | `india_quarterly` | 55,002 |
| market_daily | `ticker_reference` | 37,537 |
| market_daily | `ticker_freshness` | 37,473 |
| public | `stocks` | 35,243 |
| fundamentals | `intl_pit_quarterly` | 33,334 |
| market_daily | `symbol_names` | 27,107 |
| funds | `scheme_status` | 22,677 |

## DuckDB `data/market_data.duckdb`

| table | rows |
|---|---:|

## Gaps — collect better

1. **Corporate actions are applied for India only.** `ohlcv_adj` has no partitions for US, JP, KR, EU, CN; those directories hold a `corrected_symbols.parquet` and nothing else. `adjustment_factors.parquet` is likewise India-only (NSE corporate-action text). Every non-India backtest is therefore run on raw Close, and every split in it is a fabricated return. This is the single highest-value collection gap.

2. **US is not fit for return calculations.** 2,173 bars move more than 10x in a single session (132 per million), topping out at 7,801,928x. That is not a split and not a price — it is a broken collector. Re-collect rather than clean.

3. **CN is 54 days stale** (last session 2026-07-01). It is being stored but no longer collected.

4. **IN's universe is not filtered to equities.** The median symbol has 29 sessions out of 2,625, and 4,464 of 7,507 symbols never reach 200 bars — because the panel ingests every bhavcopy series, not just EQ. The short-history names are debt instruments (`0ANSPL28`, `1003IIFL29`, `1003NHF30` — numeric prefix = coupon, suffix = maturity). Screens hide this because a 200-DMA filter drops them silently, but any statement about universe size is wrong by ~3x, and liquidity tiers are computed across a population that includes bonds. Filter on series at ingest.

5. **No adjustment factors are stored for non-India markets.** `adjustment_factors.parquet` (795 rows, 2015-2026) is the only corporate-action record on the machine. Without an equivalent for US/JP/KR/EU there is no way to build an adjusted panel for them even retrospectively — the raw history alone cannot distinguish a split from a crash. Collecting actions is a prerequisite, not a nice-to-have.

6. **Point-in-time is absent from the price layer.** Panels are keyed `(Date, Symbol)` with no ingest timestamp and no revision history, so a restated bar overwrites the original and no backtest can reconstruct what was knowable on the day. A warehouse wanting honest PIT needs either an `ingested_at` column or an append-only revision table.

## Storage — what a warehouse still needs

| gap | why it matters |
|---|---|
| no `(Date, Symbol)` uniqueness constraint | the panels happen to be clean today (0 duplicates everywhere), but nothing enforces it — a double-ingest would silently double-count |
| no schema contract across year partitions | `ohlcv_adj/IN` carries an `adj_factor` column the raw tree lacks; readers must special-case |
| ticker conventions differ by market | India bare, everything else pre-suffixed. Every consumer re-implements the mapping |
| no data-quality gate at ingest | the checks in this file run after the fact; none of them block a bad batch from landing |
| freshness is not asserted per market calendar | a stale market (CN, 54 days) looks identical to a market that is simply closed |

