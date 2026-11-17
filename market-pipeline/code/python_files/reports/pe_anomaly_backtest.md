# PE anomaly backtests — India

Universe: 1458 NSE names, monthly 2017-01-31 → 2026-06-30. Annual PIT EPS (filed date, else fy_end+90d); adjusted closes; PE winsorized to [1.0, 200.0]. Survivorship-biased universe — read SPREADS, not levels.

## A. Sector-relative PE — do anomalies correct?

109 monthly formations; quintile 1 = CHEAPEST vs own industry.

| horizon | Q1 cheap | Q2 | Q3 | Q4 | Q5 rich | Q1−Q5 | t (de-overlapped) |
|---|---|---|---|---|---|---|---|
| 1M | +2.26% | +2.06% | +1.59% | +1.62% | +1.31% | **+0.95%** | 3.16 |
| 3M | +5.75% | +5.33% | +4.14% | +4.14% | +3.37% | **+2.39%** | 2.80 |
| 6M | +11.26% | +9.93% | +8.30% | +7.70% | +6.18% | **+5.07%** | 2.88 |

**Sector-level stretch (median PE z vs own 36M history) → forward 3M sector return:**

- stretched rich (z > +1.5): +6.39% (n=368 sector-months)
- neutral (|z| ≤ 0.5): +5.76% (n=659)
- stretched cheap (z < −1.5): +9.32% (n=168)

## B. PE trends vs company performance

12M multiple change × 12M EPS delivery → forward returns (equal-weight, monthly formations):

| bucket | n/mo | fwd 3M | fwd 6M |
|---|---|---|---|
| PE↑ EPS↑ (earned re-rating) | 105 | +5.56% | +11.55% |
| PE↑ EPS↓ (hope rally) | 192 | +5.15% | +10.83% |
| PE↓ EPS↑ (cheapening on delivery) | 256 | +3.52% | +7.47% |
| PE↓ EPS↓ (deserved de-rating) | 76 | +2.67% | +7.71% |

**Do high-PE names deliver faster subsequent EPS growth (next 12M, log growth)?**

| PE quintile (1=cheap) | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| subsequent EPS growth | -37.2% | -11.6% | -0.2% | +9.7% | +33.7% |
