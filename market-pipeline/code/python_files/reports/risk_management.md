# Risk overlay: inverse-vol sizing · vol-target · drawdown kill-switch

Target vol 10%; kill-switch halves exposure when drawdown >15%, restores under 7%. Sharpe/maxDD per desk on the regime-conditional book (optimised map).

| desk | Sharpe EW | Sharpe invvol | **Sharpe vt+KS** | maxDD EW | **maxDD vt+KS** | KS fired |
|---|--:|--:|--:|--:|--:|--:|
| IN | 0.94 | 0.55 | **1.17** | -77% | **-31%** | 4× |
| US | 0.65 | 0.80 | **0.98** | -52% | **-20%** | 4× |
| JP | 0.89 | 0.94 | **1.42** | -61% | **-26%** | 3× |
| KR | 0.64 | 0.72 | **0.97** | -69% | **-25%** | 3× |
| EU | 0.88 | 0.90 | **1.34** | -59% | **-20%** | 4× |

> Inverse-vol sizing raises Sharpe by down-weighting the noisiest names; vol-targeting standardises risk across desks (so leverage/carry can be sized to a known vol budget); the kill-switch caps tail drawdowns — the balance-sheet protection the equal-weight book lacked. Gross of costs. Not investment advice.