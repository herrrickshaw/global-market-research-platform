# Multi-market systematic strategy platform

A research platform that finds, validates, and monitors **per-market equity strategies**
across India, US, Korea, Japan, Europe and China — with statistical guards against false
discovery, an end-to-end data pipeline, and a credit-free RAG for querying the results.

> ⚠️ Descriptive research and education only — **not investment advice.** Every earnings
> figure is gross of costs on survivorship-biased data; read spreads, not levels.

## The approach

There is no universal strategy. Each market has a **character**, and the pipeline matches a
factor family to it, then proves the edge is real before acting:

```
data (prices + fundamentals, point-in-time)
  → factor / value / quality backtest (spreads, non-overlapping t-stats)
  → multiple-testing correction (Deflated Sharpe)
  → sufficiency gate (≥15 non-overlap obs AND ≥60% liquid coverage)
  → verdict per market  → screener + watchlist + mailer
```

## The winning strategy per market (backtested, point-in-time)

| market | character | book | edge | evidence |
|---|---|---|---|---|
| **India** | momentum/trend | long-only | trend + sector-relative value | +5.3%/6M, t 2.5 · DSR 0.994 |
| **Korea** | mean-reversion | full long/short | cheap∩hi-ROE − expensive∩lo-ROE | +4.83%/6M, t 4.17 |
| **Japan** | value-reversion | long cheap-vs-market | low PE vs market (deep EDINET) | **+6.6%/6M, t 4.84** |
| **US** | mixed/light | long-tilt | short-horizon cheap-vs-market | +1.72%/3M, t 2.32 |
| **Europe** | momentum (bull) | directional | 12-month momentum | DSR 0.985 |
| **China** | momentum/retail | — | value **tested & fails** | t 0.04 (powered null) |

**Meta-finding:** momentum/trend survives multiple-testing almost everywhere; value works
only where the data is deep enough to prove it (India, US, Korea, and — once EDINET depth was
added — Japan). China's multiples converge but don't pay a return premium.

## How to read the results

- **Quantitative bar:** `|t|≳2` on non-overlapping obs, **Deflated Sharpe > 0.95** for
  technical factors, **≥15 non-overlap obs** (powered), **≥60% liquid coverage** (complete).
- **Qualitative:** judge by market character; confirm value with multiple-convergence; treat
  nulls and flips as real verdicts; discount magnitude on thin/selected samples.
- Full treatment, assumptions, and citations: **[docs/METHODOLOGY.md](docs/METHODOLOGY.md)**.

## How metrics are computed

Every screened number, with its exact definition **as implemented**, its inputs, and the
source it is taken from: **[docs/METRICS.md](docs/METRICS.md)**.

| metric | definition | source |
|---|---|---|
| **EPS** | `(net income − preferred dividends) / weighted-average common shares` — the share basis (`diluted`/`basic`/`period_end`) is recorded per row, since they are different statistics | standard accounting definition, validated against filers' own `us-gaap:EarningsPerShareDiluted` to **<0.7%** across 7 mega-caps |
| **PE · PB · earnings yield** | `close/EPS`, `mcap/book equity`, `1/PE`; priced off the live per-ticker tree, outliers nulled not carried | — |
| **ROCE** | `EBIT / capital employed` — **India only**; left `NULL` elsewhere rather than approximated | — |
| **Piotroski F-Score** | 9 binary signals; signal 4 is the accrual test in level form (`CFO > net income`) | Piotroski (2000), *J. Accounting Research* 38:1–41 |
| **Darvas Box** | `box_top` = unbeaten high; `box_bottom` = lowest low *after* it; breakout = close above `box_top`. Current bar excluded from formation | Darvas (1960), *How I Made $2,000,000 in the Stock Market* |
| **Liquidity** | floors are **absolute** ($10k structural, ₹1cr India policy); tiers are **percentile within market** — one USD constant is four different filters across five markets | Amihud (2002), *J. Financial Markets* 5:31–56 |
| **CCC** | `DSO + DIO − DPO` from filings — EDGAR (US) / yfinance store (India); screener.in is a **fallback only**, and the source is rendered per row | validated: AAPL −71.1d, WMT +2.8d |
| **Freshness** | graded by the trading **session the data contains**, never mtime/filename/row-count; median symbol, not maximum | see METRICS.md §5 |

Deviations from a canonical definition are stated rather than glossed — e.g. Piotroski
signal 7 defaults to *true* on missing share history, awarding a free point to **12%** of
US tickers. An undocumented deviation is how a screen silently stops measuring what its
name claims.

## Documentation

| doc | what |
|---|---|
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | assumptions · how to read results · literature |
| [docs/METRICS.md](docs/METRICS.md) | **how every metric is computed** — exact formulas, inputs, sources |
| [docs/EDGE_MATRIX.md](docs/EDGE_MATRIX.md) | **the fat-pitch grid** — where the edge is (filter × market) |
| [docs/WHY_THESE_WIN.md](docs/WHY_THESE_WIN.md) | **why** each filter wins — economics + literature + caveats |
| [docs/FUNDAMENTALS_VS_SPECULATION.md](docs/FUNDAMENTALS_VS_SPECULATION.md) | **fundamentals vs speculation** by sector/time + Damodaran + R&D/asset nuance |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | **every term in plain English** (no finance background needed) |
| [docs/PIPELINE_STAGES.md](docs/PIPELINE_STAGES.md) | the 10-stage pipeline |
| [docs/SYSTEM_REFERENCE.md](docs/SYSTEM_REFERENCE.md) | module map · findings · data map |
| [docs/DATA_SUFFICIENCY.md](docs/DATA_SUFFICIENCY.md) | the anti-false-outcome power/coverage gate |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | upstream sources · access · reachability |
| [docs/DATA_COLLECTION_HISTORY.md](docs/DATA_COLLECTION_HISTORY.md) | what's already collected (all markets) |
| [docs/SAKANA_COMPARISON.md](docs/SAKANA_COMPARISON.md) | Sakana EDINET-Bench vs this research |
| [docs/LOCAL_RAG.md](docs/LOCAL_RAG.md) | credit-free Q&A over the outputs |

## Key modules

`valuation_reversion_backtest.py` · `value_quality_ls_backtest.py` · `deflated_sharpe.py` ·
`data_sufficiency.py` (power/coverage guard) · `data_ledger.py` + `source_registry.py`
(catalogs, refreshed every 3 days by `data_check.sh`) · `strategy_matrix.py` (self-testing
suitability matrix) · `execution_cost_model.py` · `risk_management.py` · `local_rag.py`.

The standalone **winning-strategies RAG** lives in the `market_screener_rag` repo.

---

*Legacy:* the original Phase-1 NSE-only screener (`run_pipeline.py`, `screening_engine.py`,
`report_generator.py`) still runs — `python run_pipeline.py [--symbols-file f.xlsx]` — and was
the seed this platform grew from.

> Not investment advice. No warranty.
