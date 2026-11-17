# ETF builder — JP top-200, walk-forward, monthly rebalance

- periods      : 110 (2017-06-30 → 2026-07-31)
- lookback     : 252d trailing, strictly before each rebalance
- constraints  : long-only, 10% cap, 10bp turnover cost

| Scheme | CAGR | Vol | Sharpe | MaxDD | Turnover/mo | vs 1/N | vs SPY | Breakeven cost |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1/N equal | **12.63%** | 15.5% | 0.81 | -25.7% | 65% | +0.00% | -2.36% | — |
| inverse-vol | **11.93%** | 14.3% | 0.83 | -24.7% | 75% | -0.70% | -3.06% | — |
| min-variance | **6.18%** | 9.7% | 0.64 | -22.5% | 121% | -6.44% | -8.81% | — |
| max-Sharpe | **11.68%** | 18.0% | 0.65 | -27.4% | 127% | -0.95% | -3.31% | — |
| momentum 12-1 | **13.50%** | 19.4% | 0.69 | -26.4% | 114% | +0.88% | -1.49% | — |
| **SPY (the ETF you'd just buy)** | **14.99%** | 16.0% | 0.94 | -23.9% | ~0% | +2.36% | — | — |

