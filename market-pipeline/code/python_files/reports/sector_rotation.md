# Sector rotation — 12 NIFTY sectoral indices, 63-bar hold, top 3

- 91 monthly formations, 2018-08-08 → 2026-04-15
- returns are EXCESS over Nifty 500 total return · 20bp charged
- `eq` = hold all 12 sectors equally (the null: rotation adds nothing)

| signal | mean excess | median | win% | t | vs equal-weight |
|---|--:|--:|--:|--:|--:|
| eq | +0.12% | -0.12% | 48% | 0.65 |  |
| **mom** | -0.12% | -0.50% | 42% | -0.21 | -0.24pp |
| **value** | -0.03% | -0.21% | 49% | -0.06 | -0.15pp |
| **trend** | -0.61% | -0.13% | 47% | -1.67 | -0.72pp |
| **mom+value** | -0.02% | -1.03% | 41% | -0.03 | -0.13pp |

## by sub-period

| period | eq | mom | value | trend | mom+value |
|---|---|---|---|---|---|
| 2018-2020 (n=27) | -0.60% | -1.24% | -0.93% | -2.43% | -2.17% |
| 2020-2023 (n=37) | +0.97% | +1.09% | +1.04% | +0.21% | +1.45% |
| 2024-2026 (n=27) | -0.33% | -0.65% | -0.59% | +0.10% | +0.14% |

> A signal must beat `eq` — holding every sector equally — not merely be positive. Beating zero only says sectors outran the benchmark on average, which is a property of the universe, not of the rotation.
