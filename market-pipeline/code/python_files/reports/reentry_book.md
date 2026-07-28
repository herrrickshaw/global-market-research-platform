# Re-entry book — IN, buy at anomaly trigger, hold 63d

- events        : **508** (of 541 anomalies · 2 right-censored · 31 overlapping dropped)
- window        : 2020-12-02 → 2026-02-24

## 1. Is there an edge? (excess vs equal-weight index, same window)

| | median | mean |
|---|--:|--:|
| re-entry raw | +3.83% | +5.31% |
| benchmark | +5.99% | +5.13% |
| **excess** | **-1.88%** | **+0.18%** |

- win rate (excess > 0): **45%**
- paired t on excess   : **t = 0.27** (n=508)
- verdict              : **NO EDGE**

## 2. By year (a single-regime edge is not an edge)

| Year | n | excess median | excess mean | win% |
|---|--:|--:|--:|--:|
| 2020 | 7 | -7.19% | -8.74% | 14% |
| 2021 | 206 | -2.51% | +0.52% | 42% |
| 2023 | 121 | -0.63% | +0.88% | 48% |
| 2024 | 144 | -2.17% | -0.56% | 45% |
| 2025 | 15 | -3.06% | -4.27% | 40% |
| 2026 | 15 | +5.55% | +5.34% | 80% |

> wrote 508 trades → `/private/tmp/claude-501/-Users-umashankar/9d96e160-2af9-44bf-8d9a-94b70f61240b/scratchpad/reentry_events.csv` (feed to `fund_scorecard.py --events /private/tmp/claude-501/-Users-umashankar/9d96e160-2af9-44bf-8d9a-94b70f61240b/scratchpad/reentry_events.csv`)
