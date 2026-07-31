# Data-quality report (expectations · dedup · ratio derivation)

GE/dbt-style validation of the warehouse ratios + fundamentals. Educational research pipeline. 

## 1. Expectations (sufficiency gate)

| expectation | result | detail |
|---|:--:|---|
| ratios.market_ticker unique | ✅ pass | 0 dupes |
| ratios.ticker not-null | ❌ FAIL | 1 nulls |
| ratios.close not-null | ❌ FAIL | 1.1% null |
| ratios.pe in (0,1000] | ✅ pass | 0 out-of-range |
| ratios.roe in [-3,3] | ✅ pass | 0 out-of-range |
| ratios.pe coverage ≥ 70% | ❌ FAIL | 57% present |
| ratios.roe coverage ≥ 90% | ✅ pass | 91% present |

## 2. Deduplication

| table | key | dupes |
|---|---|--:|
| financial_ratios | market×ticker | 0 ✅ |
| fundamentals/IN_screener_only_backup | ticker×fy_end | 0 ✅ |
| fundamentals/US | ticker×fy_end | 0 ✅ |
| fundamentals/KR | ticker×fy_end | 0 ✅ |
| fundamentals/JP | ticker×fy_end | 0 ✅ |

## 3. Missing ratios derived (from raw fundamentals, no fetch)

| ratio | coverage before | after | filled |
|---|--:|--:|--:|
| pe | 55% | **57%** | +310 |
| pb | 81% | **82%** | +112 |
| roe | 93% | **91%** | +256 |
| roce | 56% | **56%** | +0 |

## 4. Freshness (warehouse latest date)

| market | IN | US | KR | JP | EU |
|---|---|---|---|---|---|
| last date | 2026-07-30 | 2026-07-27 | 2026-07-23 | 2026-07-23 | 2026-07-22 |

## 5. Pending (fetch-only — cannot be derived)

- **US shares/equity** 53–59% null in fundamentals_history → PE/PB still gappy for US; needs an EDGAR/yfinance shares+equity fetch.
- **EU/JP** absent from `financial_ratios.csv` — no fundamentals snapshot built; EU has `fundamentals_history/EU.parquet`, JP via EDINET (collector not built).
- **ROCE** needs EBIT + capital_employed — only India's screener carries them; US/KR ROCE stays null without those raw fields.

> Derived ratios use latest-FY fundamentals + current price (a PIT approximation for the snapshot). Enriched file: `reports/financial_ratios_enriched.csv`. Not advice.