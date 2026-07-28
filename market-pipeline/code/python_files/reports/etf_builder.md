# ETF builder — US top-200, walk-forward, monthly rebalance

- periods      : 110 (2017-06-30 → 2026-07-31)
- lookback     : 252d trailing, strictly before each rebalance
- constraints  : long-only, 10% cap, 10bp turnover cost

| Scheme | CAGR | Vol | Sharpe | MaxDD | Turnover/mo | vs 1/N | vs SPY | Breakeven cost |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1/N equal | **12.26%** | 18.7% | 0.66 | -33.9% | 57% | +0.00% | -2.58% | — |
| inverse-vol | **12.20%** | 16.1% | 0.76 | -25.3% | 73% | -0.07% | -2.65% | — |
| min-variance | **5.81%** | 9.8% | 0.59 | -28.6% | 120% | -6.46% | -9.04% | — |
| max-Sharpe | **13.52%** | 17.4% | 0.78 | -36.9% | 129% | +1.26% | -1.32% | — |
| momentum 12-1 | **18.95%** | 28.3% | 0.67 | -35.3% | 118% | +6.68% | +4.10% | 39bp |
| **SPY (the ETF you'd just buy)** | **14.85%** | 16.0% | 0.93 | -23.9% | +2.58% | — |

