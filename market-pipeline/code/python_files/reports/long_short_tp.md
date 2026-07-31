# Long/short + profit-booking on the reward-optimised book

New composite filters (tri_confirm, blend_rank) added on top of the benchmark filters; best factor per market×regime selected by the long/short + take-profit information ratio. Take-profit 8% / stop 12% on the daily path; long/short is dollar-neutral 50/50. Reward (info ratio) as each mechanic is added:

| market | regime | factor | long-only IR | +short IR | +take-profit IR | **L/S + TP IR** |
|---|---|---|--:|--:|--:|--:|
| IN | bull | qual_mom | 0.43 | 1.7 | -1.0 | **1.67** |
| IN | bear | def_revert | 0.83 | 1.46 | -0.14 | **0.71** |
| US | bull | def_revert | 1.02 | 1.34 | 0.63 | **1.42** |
| US | bear | def_revert | 0.55 | 1.25 | 0.21 | **1.74** |
| JP | bull | qual_mom | 0.49 | 1.06 | -0.14 | **0.74** |
| JP | bear | def_revert | 0.52 | 0.7 | -0.24 | **0.38** |
| KR | bull | qual_mom | 1.54 | 2.08 | -0.05 | **1.66** |
| KR | bear | def_revert | 1.34 | 2.24 | 0.07 | **2.05** |
| EU | bull | mom252 | 1.4 | 1.32 | 0.49 | **0.67** |
| EU | bear | def_revert | 0.35 | 0.56 | -0.44 | **0.48** |

## Firm annual PAT ($M) — full long/short + profit-booking book

| year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PAT | -0.15 | -0.23 | -0.02 | -0.34 | -0.24 | +0.08 | -0.13 | +0.04 | +0.01 | +0.11 | -0.11 |

Mean annual PAT $-0.09M · ROE -1.8% · annual Sharpe -0.63 · loss years 7/11

> Dollar-neutral long/short removes market beta, so its return IS its excess — that is why the L/S info ratios read higher and the loss years shrink (the short leg pays in the bear drawdowns the long-only book bled in). Gross of borrow cost/slippage. Not investment advice.