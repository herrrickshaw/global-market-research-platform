# Strategy suitability matrix — what works where (evidence-backed)

Assembled from this repo's backtests; each row's verdict traces to a stat. Legend: ✅ robust · 🟡 conditional/earned · ⚠️ fragile (fails multiple-testing) · ❌ fails · — untested. Cells re-derive when the backtests re-run.

## Technical factors — best per market × regime (Deflated-Sharpe checked)

| market | BULL factor | BULL | BEAR factor | BEAR |
|---|---|:--:|---|:--:|
| IN | trend | ✅ | def_revert | ⚠️ |
| US | mom252 | ⚠️ | def_revert | ⚠️ |
| KR | breakout | ✅ | def_revert | ⚠️ |
| JP | golden_cross | ⚠️ | revert | ⚠️ |
| EU | mom252 | ✅ | revert | ⚠️ |

## Valuation ratios & reversion

| strategy \ market | IN | US | KR | JP | EU |
|---|:--:|:--:|:--:|:--:|:--:|
| Value — cheap vs peers (low PE) | ✅ | ✅ | 🟡 | ⚠️ | ⚠️ |
| Value+Quality long/short (cheap∩hiROE − rich∩loROE) | ❌ | 🟡 | ✅ | — | — |
| Quality (high ROE) as premium filter | 🟡 | 🟡 | ✅ | — | — |

## Screeners / filters

| strategy \ market | IN | US | KR | JP | EU |
|---|:--:|:--:|:--:|:--:|:--:|
| Darvas / breakout (near-52w-high) | ✅ | 🟡 | ✅ | 🟡 | 🟡 |
| Golden cross (50>200DMA) | ✅ | ✅ | 🟡 | 🟡 | 🟡 |
| Mean-reversion (buy oversold) | ⚠️ | ✅ | ✅ | ✅ | ✅ |
| Piotroski / fundamental quality | 🟡 | ⚠️ | 🟡 | — | — |

## Deployment rules (market character — the meta-finding)

| market | character | long book | short book |
|---|---|---|---|
| IN | momentum/trend | breakout + sector-relative value | ❌ don't short (bull runs them over) |
| US | mixed | golden-cross / value, light | marginal |
| KR | mean-reversion | cheap∩hi-ROE (Korea discount) | ✅ hollow-overpriced (validated) |
| JP | mean-revert (weak) | mom in bull, revert in bear | — (value not significant) |
| EU | mean-revert | momentum bull, revert bear | — (no fundamentals) |

## Freshness / keep-testing

| block | source backtest | last tested |
|---|---|---|
| technical factors | deflated_sharpe + regime_survival | 2026-07-24 |
| tuned hyperparams | aws_sweep | 2026-07-24 |
| value / reversion | pe_anomaly + valuation_reversion | 2026-07-23 |
| value+quality L/S | value_quality_ls | 2026-07-24 |

> Re-run the backtests then `strategy_matrix.py`; it re-stamps every cell and alerts on any verdict FLIP. Wire into monthly [16d] after the backtests. Deepening data (DART/EDINET for KR/JP) will refresh those cells automatically. Descriptive research, not investment advice.