# Firm profitability: current vs reward-optimised, benchmarked to real firms

Firm equity $5M (5 desks × $1M), 10y backtest, liquidity-gated, regime-conditional. Reward-optimised map = `zone_regime_optimized.json` (max information ratio).

## Profitability & balance-sheet lift

| metric | current | **optimised** |
|---|--:|--:|
| mean annual PAT ($M) | 0.19 | **0.34** |
| return on equity (ROE) | 3.9% | **6.8%** |
| annual Sharpe (PAT) | 0.29 | **0.54** |
| worst year ($M) | -1.12 | **-0.96** |
| loss years (of 11) | 2 | **2** |

## Annual PAT ($M) — current vs optimised

| year | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| current | +0.11 | +0.78 | -1.12 | +0.01 | +1.29 | +0.61 | -0.69 | +0.57 | +0.16 | +0.41 | +0.00 |
| optimised | +0.23 | +0.81 | -0.96 | +0.33 | +1.37 | +0.70 | -0.48 | +0.70 | +0.29 | +0.57 | +0.18 |

## Benchmark — real listed trading/brokerage firms (live yfinance)

| geography | firm | ROE | net margin | rev growth | mkt cap ($B) |
|---|---|--:|--:|--:|--:|
| India | Motilal Oswal | 15.6% | 23.2% | 159.8% | 521.5 |
| India | Angel One | — | 20.7% | 23.0% | 279.4 |
| India | ICICI Securities | — | — | — | — |
| India | 360 ONE | — | 26.5% | 29.9% | 442.0 |
| US | Interactive Brokers | 24.0% | 16.5% | 22.3% | 155.6 |
| US | Charles Schwab | 20.3% | 38.8% | 20.9% | 176.7 |
| US | Robinhood | 21.5% | 41.1% | 15.1% | 91.5 |
| US | LPL Financial | 20.5% | 5.1% | 35.0% | 25.9 |
| Japan | Nomura | 10.1% | 16.7% | 27.5% | 4662.1 |
| Japan | Daiwa Securities | 9.6% | 11.9% | 4.7% | 2564.0 |
| Japan | Matsui | — | 30.5% | 60.4% | 285.9 |
| Korea | Mirae Asset Sec | 17.4% | 8.0% | 185.4% | 21293.7 |
| Korea | Samsung Securities | 15.7% | 7.7% | 129.2% | 8885.3 |
| Europe | Flow Traders | 18.1% | 18.0% | 16.7% | 1.1 |
| Europe | IG Group | — | 46.3% | 8.1% | 5.6 |
| Europe | Plus500 | 46.4% | 36.0% | 1.6% | 2.8 |
| **—** | **Our firm (optimised)** | **6.8%** | — | — | 0.005 |

> Our ROE is on a $5M paper-AUM prop book, gross of slippage; real firms carry fee/interest/AMC income, leverage and franchise value a pure prop desk lacks — read the comparison as a return-quality sanity check, not a valuation. Not investment advice.