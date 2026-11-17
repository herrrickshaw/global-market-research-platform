# RLOO peer-group re-score — 2026-08-24 16:50

Every screen scored three ways on the same picks:

| column | meaning |
|---|---|
| `raw` | forward return of the picks. Confounds market, factor tilt and skill. |
| `adv_mkt` | RLOO advantage vs **all** eligible names that market-day. Removes the market. |
| `adv_tier` | RLOO advantage vs eligible names **in the same liquidity quintile**. Removes the market *and* the liquidity tilt. This is the selection-skill number. |

t-stats are Newey-West HAC on the per-date cohort series (lag = horizon), not on individual picks — overlapping forward windows make a naive per-pick t meaningless.

Source panel: `~/.cache/market-warehouse/ohlcv_adj` (split/bonus back-adjusted). Darvas boxes exclude the signal bar.

## Horizon: 21 trading days

| screen | mkt | picks | dates | med tier | raw | adv vs mkt | t | adv vs tier | t |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `darvas_breakout` | IN | 473,384 | 1,065 | 3 | +1.05% | -0.19% | -1.71 | -0.25% | -2.44 |
| `darvas_fresh` | IN | 22,148 | 1,009 | 2 | +1.60% | +0.11% | +0.44 | +0.03% | +0.13 |
| `golden_cross` | IN | 5,067 | 952 | 3 | +1.38% | +0.25% | +0.94 | +0.15% | +0.60 |

## Horizon: 63 trading days

| screen | mkt | picks | dates | med tier | raw | adv vs mkt | t | adv vs tier | t |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `darvas_breakout` | IN | 437,971 | 1,023 | 3 | +3.92% | -0.07% | -0.26 | -0.28% | -1.18 |
| `darvas_fresh` | IN | 20,681 | 966 | 2 | +4.92% | +0.76% | +1.42 | +0.55% | +1.11 |
| `golden_cross` | IN | 4,461 | 905 | 3 | +3.55% | +0.01% | +0.02 | -0.21% | -0.50 |

## Panel diagnostics

| market | panel | symbols | dates | span | eligible cells |
|---|---|---:|---:|---|---:|
| IN | adjusted | 7,116 | 1,290 | 2021-06-01 → 2026-08-20 | 1,846,917 |

## Reading this

A screen whose `raw` is strongly positive but whose `adv_tier` is flat did not pick well — it was carried by the market, or it is a liquidity proxy. The gap between `adv_mkt` and `adv_tier` is exactly the size of the factor tilt.

`|t| >= 2` on `adv_tier` is the bar for a claim of selection skill, and even that is a single-hypothesis bar — this table tests 6 combinations, so a Bonferroni-adjusted threshold is nearer |t| >= 2.8.
