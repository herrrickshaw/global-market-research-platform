# RLOO peer-group re-score — 2026-08-24 16:49

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
| `darvas_breakout` | IN | 938,156 | 2,399 | 3 | +1.00% | -0.33% | -3.58 | -0.37% | -4.34 |
| `darvas_breakout` | JP | 2,181,020 | 2,278 | 3 | +0.74% | -0.20% | -3.39 | -0.20% | -3.40 |
| `darvas_breakout` | KR | 1,197,582 | 2,260 | 3 | +0.35% | -0.25% | -2.23 | -0.26% | -2.33 |
| `darvas_breakout` | US | 3,848,231 | 2,327 | 3 | +0.25% | -0.28% | -2.97 | -0.29% | -3.24 |
| `darvas_fresh` | IN | 41,943 | 2,305 | 2 | +1.64% | +0.35% | +1.88 | +0.33% | +2.01 |
| `darvas_fresh` | JP | 96,373 | 2,193 | 3 | +0.77% | -0.08% | -0.89 | -0.05% | -0.58 |
| `darvas_fresh` | KR | 38,464 | 2,003 | 3 | +0.23% | -0.45% | -2.42 | -0.35% | -2.09 |
| `darvas_fresh` | US | 178,959 | 2,276 | 3 | +0.62% | +0.11% | +0.67 | +0.09% | +0.58 |
| `golden_cross` | IN | 9,405 | 2,012 | 3 | +0.95% | +0.02% | +0.08 | -0.04% | -0.18 |
| `golden_cross` | JP | 19,686 | 2,224 | 3 | +0.79% | -0.09% | -0.76 | -0.09% | -0.72 |
| `golden_cross` | KR | 13,667 | 1,966 | 3 | +0.14% | -0.40% | -1.62 | -0.45% | -1.87 |
| `golden_cross` | US | 36,342 | 2,313 | 3 | +0.12% | -0.38% | -1.88 | -0.34% | -1.73 |

## Horizon: 63 trading days

| screen | mkt | picks | dates | med tier | raw | adv vs mkt | t | adv vs tier | t |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `darvas_breakout` | IN | 897,382 | 2,357 | 3 | +3.53% | -0.15% | -0.76 | -0.26% | -1.46 |
| `darvas_breakout` | JP | 2,142,351 | 2,236 | 3 | +2.59% | -0.19% | -1.88 | -0.18% | -1.87 |
| `darvas_breakout` | KR | 1,181,911 | 2,219 | 3 | +1.30% | -0.46% | -2.30 | -0.47% | -2.72 |
| `darvas_breakout` | US | 3,712,599 | 2,286 | 3 | +1.73% | -0.27% | -1.35 | -0.30% | -1.61 |
| `darvas_fresh` | IN | 40,224 | 2,261 | 2 | +4.69% | +1.28% | +2.72 | +1.16% | +2.99 |
| `darvas_fresh` | JP | 94,662 | 2,152 | 3 | +2.70% | +0.11% | +0.63 | +0.16% | +0.93 |
| `darvas_fresh` | KR | 38,418 | 2,001 | 3 | +1.60% | -0.27% | -0.75 | -0.10% | -0.30 |
| `darvas_fresh` | US | 173,907 | 2,238 | 3 | +2.50% | +0.53% | +1.29 | +0.50% | +1.27 |
| `golden_cross` | IN | 8,728 | 1,962 | 3 | +2.55% | -0.43% | -0.98 | -0.59% | -1.44 |
| `golden_cross` | JP | 19,483 | 2,183 | 3 | +2.36% | -0.26% | -1.07 | -0.18% | -0.76 |
| `golden_cross` | KR | 13,637 | 1,966 | 3 | +0.56% | -1.16% | -2.15 | -1.34% | -2.80 |
| `golden_cross` | US | 35,030 | 2,276 | 3 | +1.24% | -0.69% | -1.88 | -0.63% | -1.69 |

## Panel diagnostics

| market | panel | symbols | dates | span | eligible cells |
|---|---|---:|---:|---|---:|
| IN | adjusted | 7,494 | 2,624 | 2016-01-01 → 2026-08-20 | 3,713,808 |
| US | RAW + split guard | 9,938 | 2,553 | 2016-06-27 → 2026-08-21 | 12,790,200 |
| JP | RAW + split guard | 3,572 | 2,503 | 2016-06-27 → 2026-08-24 | 6,739,639 |
| KR | RAW + split guard | 2,776 | 2,488 | 2016-06-27 → 2026-08-24 | 4,717,986 |

## Reading this

A screen whose `raw` is strongly positive but whose `adv_tier` is flat did not pick well — it was carried by the market, or it is a liquidity proxy. The gap between `adv_mkt` and `adv_tier` is exactly the size of the factor tilt.

`|t| >= 2` on `adv_tier` is the bar for a claim of selection skill, and even that is a single-hypothesis bar — this table tests 24 combinations, so a Bonferroni-adjusted threshold is nearer |t| >= 2.8.
