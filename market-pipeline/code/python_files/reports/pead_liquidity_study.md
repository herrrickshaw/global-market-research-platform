# PEAD x illiquidity — India, 63-bar forward, FULL panel

- events        : **42,369** across 2,031 symbols, 2016–2025
- signal        : announcement abnormal return [0,+1], index-relative
- forward       : 63 bars from day +2, index-relative (no overlap with the signal window)
- excluded      : 287 symbols with unexplained discontinuities

## 1. PEAD — forward excess by announcement-reaction quantile

| quantile | n | mean CAR | mean fwd excess | median | win% |
|---|--:|--:|--:|--:|--:|
| Q1 (worst reaction) | 8,474 | -7.66% | **+0.55%** | -2.95% | 44% |
| Q2 | 8,474 | -3.06% | **+0.59%** | -2.74% | 43% |
| Q3 | 8,473 | -0.99% | **+0.54%** | -2.45% | 44% |
| Q4 | 8,474 | +1.05% | **+0.88%** | -1.90% | 45% |
| Q5 (best reaction) | 8,474 | +7.32% | **+2.43%** | -1.23% | 47% |

- **top-minus-bottom spread: +1.88%  (t = 4.93)**
- rank IC (Spearman): **+0.0302**  (t = 6.22)
- verdict: **PEAD PRESENT**

## 2. PEAD conditional on Amihud illiquidity

| liquidity tier | n | top-minus-bottom | t | rank IC |
|---|--:|--:|--:|--:|
| liquid | 13,150 | +2.24% | 3.94 | +0.0481 |
| mid | 13,150 | +2.68% | 3.81 | +0.0444 |
| illiquid | 13,151 | +1.40% | 1.92 | +0.0095 |

## 3. By year (regime robustness)

| year | n | top-minus-bottom | rank IC |
|---|--:|--:|--:|
| 2016 | 3,668 | -0.26% | -0.0075 |
| 2017 | 4,409 | +0.22% | +0.0081 |
| 2018 | 4,486 | +0.27% | +0.0175 |
| 2019 | 4,186 | +1.14% | +0.0080 |
| 2020 | 4,229 | +2.25% | +0.0228 |
| 2021 | 4,418 | +4.75% | +0.0670 |
| 2022 | 4,904 | +3.68% | +0.0762 |
| 2023 | 5,100 | +2.53% | +0.0587 |
| 2024 | 5,459 | +1.58% | +0.0493 |
| 2025 | 1,510 | -4.82% | -0.0609 |

> Every return is index-relative (Nifty-50 total return), so a rising market cannot make a quantile look profitable. Signal and forward windows never overlap. Prices are split-adjusted; symbols with unexplained residual discontinuities are excluded.
