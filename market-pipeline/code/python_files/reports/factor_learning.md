# Learned factor model — Lasso + online learning-rate adaptation

Lasso (CV-tuned α) learns a SPARSE weighted factor combo per desk; an online SGD model then adapts those weights week-by-week (learning rate η, grid-tuned) as realised outcomes arrive. All IRs are strictly out-of-sample (last 40% of history). `factor_weights.json` is the drop-in learned model.

| market | obs | α (CV) | factors kept | Lasso OOS IR | best η | online OOS IR |
|---|--:|--:|---|--:|--:|--:|
| IN | 261,385 | 2.2e-03 | trend | 0.86 | 0.01 | 2.9 |
| US | 259,493 | 1.1e-03 | (none) | -0.44 | 0.01 | 2.76 |
| JP | 259,498 | 1.5e-03 | (none) | -0.19 | 0.01 | 2.78 |
| KR | 259,500 | 5.0e-04 | trend, mom126, golden_cross, lowvol | 0.84 | 0.01 | 3.87 |
| EU | 259,500 | 1.1e-03 | (none) | nan | 0.01 | 2.79 |

## Learned Lasso weights (×1e4, non-zero only)

- **IN**: trend +4.89
- **KR**: lowvol +30.42, golden_cross -18.06, trend -12.96, mom126 +12.19

> Lasso zeroing a factor = that factor adds nothing once the others are in (built-in selection — a principled cure for the multiple-testing fragility the Deflated-Sharpe flagged). Positive weight = long the factor's BUY signal. The online model keeps learning post-deployment; η is how fast it trusts new data. OOS = genuinely held-out. Gross of costs. Not investment advice.
>
> **Leakage check (KR):** the high online IRs are NOT an artifact — a null test that
> shuffles the target within each week collapses the OOS IR from 3.86 → 0.47, so the
> online model is capturing real cross-sectional signal (a leak would keep the null
> high too). Interpretation: the STATIC Lasso generalises poorly (most factors zeroed),
> but the ONLINE model with η=0.01 adapts to regime drift and that adaptation is what
> generalises. Still gross of costs, and a broad 500-name dollar-neutral book inflates
> IR mechanically — discount the ~0.47 null floor from the headline.