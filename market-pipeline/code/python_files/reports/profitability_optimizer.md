# Reward-optimised factor selection (max information ratio)

Decision variable = each desk's screener per regime; reward = annualised information ratio of the liquidity-gated long-only book's EXCESS over its index (risk-adjusted, so it lifts income *and* cuts loss-year drawdowns → stronger balance sheet). Factor library expanded to low-vol, 12m-momentum and multi-factor blends.

| market | regime | current rule | current IR | **optimised rule** | **opt IR** | Δ excess%/2w |
|---|---|---|--:|---|--:|--:|
| IN | bull | trend | +2.34 | **trend** | +2.34 | +0.00 |
| IN | bear | revert | +0.51 | **def_revert** ⬆️ | +0.86 | +0.11 |
| US | bull | mom126 | +0.74 | **mom252** ⬆️ | +1.19 | +0.12 |
| US | bear | revert | +0.48 | **def_revert** ⬆️ | +0.55 | +0.07 |
| JP | bull | mom126 | +0.83 | **golden_cross** ⬆️ | +0.84 | -0.06 |
| JP | bear | revert | +0.84 | **revert** | +0.84 | +0.00 |
| KR | bull | trend | +1.52 | **breakout** ⬆️ | +2.04 | +0.39 |
| KR | bear | revert | +0.79 | **def_revert** ⬆️ | +1.32 | +0.24 |
| EU | bull | mom126 | +0.96 | **mom252** ⬆️ | +1.39 | +0.12 |
| EU | bear | revert | +1.18 | **revert** | +1.18 | +0.00 |

## Best factor per market×regime (reward = info ratio)

| market | regime | factor | info ratio | mean excess%/2w | hit |
|---|---|---|--:|--:|--:|
| IN | bull | **trend** | +2.34 | +0.30 | 72% |
| IN | bear | **def_revert** | +0.86 | +0.23 | 57% |
| US | bull | **mom252** | +1.19 | +0.27 | 65% |
| US | bear | **def_revert** | +0.55 | +0.21 | 57% |
| JP | bull | **golden_cross** | +0.84 | +0.08 | 62% |
| JP | bear | **revert** | +0.84 | +0.18 | 59% |
| KR | bull | **breakout** | +2.04 | +0.66 | 64% |
| KR | bear | **def_revert** | +1.32 | +0.39 | 62% |
| EU | bull | **mom252** | +1.39 | +0.27 | 67% |
| EU | bear | **revert** | +1.18 | +0.30 | 60% |

> Reward = info ratio (risk-adjusted); `zone_regime_optimized.json` is a drop-in replacement for `zone_regime.json` once validated. Gross of costs; the profitability lift flows into the quarterly-earnings model on re-run.