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

## Documentation

| doc | what |
|---|---|
| [docs/METHODOLOGY.md](docs/METHODOLOGY.md) | assumptions · how to read results · literature |
| [docs/EDGE_MATRIX.md](docs/EDGE_MATRIX.md) | **the fat-pitch grid** — where the edge is (filter × market) |
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
