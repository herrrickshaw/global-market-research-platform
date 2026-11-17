# Spectrum noise null — BACKTEST_QUEUE #37(a)

Generated 2026-09-18 by `research/spectrum_noise_null.py` (200 replicates/window/null, seed 20260918, 299 windows).

Panel: `nse_deep.parquet`, 150 symbols -> 126-150 used per window, T=60, n/T=2.35 on average (target N_SYMBOLS=150).


## The measured series

- Participation ratio: mean **12.26**, range 3.47-24.10.
- PC1 absorption: mean **27.5%**, range 14.3%-52.8%.
- Mean pairwise correlation: mean **0.237**, range 0.102-0.499.


## Null A — independence (item 37(a) as written)

Each column shuffled in time; marginals kept, cross-correlation destroyed.

- Null PR band: **41.0 - 42.6** (median 41.8); analytic MP floor n/(1+n/T) = 42.1.
- Null PC1 absorption reaches only 4.7% at the 97.5th pct; measured mean is 27.5%.
- Measured PR falls **below** the null band in **100.0%** of windows; inside it in 0.0%.

**Verdict:** the measured level is not a dimension artefact. A window of this shape filled with pure noise does not collapse — it sits at PR 42 with PC1 absorbing under 5%, because rank deficiency alone cannot manufacture a dominant common mode. The measured mean of 12.3 (min 3.5) is far below that in every one of the 299 windows. The gap is market structure, not n/T.


## Null B — equicorrelated at each window's own rho-bar (addition)

One common factor, same n, same T, same mean pairwise correlation.

- Null PR band: **10.7 - 20.8** (median 15.0).
- Null PC1 band: 19.1% - 31.1% (median 24.9%).
- Measured PR is inside the band in **97.0%** of windows, below it in 3.0%, above it in 0.0%.


## The five lowest-PR windows

| date | PR | PC1 | rho-bar | Null-B PR band | outside? |
|---|---|---|---|---|---|
| 2020-03-30 | 3.47 | 52.8% | 0.499 | 2.90-5.54 | no — rho-bar explains it |
| 2020-04-08 | 3.52 | 52.4% | 0.495 | 2.83-5.40 | no — rho-bar explains it |
| 2020-04-17 | 3.73 | 50.9% | 0.482 | 3.07-5.66 | no — rho-bar explains it |
| 2020-05-11 | 3.85 | 50.1% | 0.474 | 3.30-6.73 | no — rho-bar explains it |
| 2020-04-24 | 3.86 | 49.9% | 0.473 | 3.22-6.04 | no — rho-bar explains it |

Correlation between measured PR and mean pairwise correlation across all 299 windows: **-0.931**.


## Caveats

- Null B is Gaussian and homogeneous: it gives every name the same loading and no fat tails. Null A keeps the real marginals. Neither reproduces the market's heterogeneous betas, so 'outside Null B' means 'not explained by rho-bar alone', not 'not explained by any one-factor model'.
- The independence null shuffles within the 60-day window, so it also destroys each series' own autocorrelation. For PR this is second-order; a phase-randomised variant would preserve it.
- Items 37(b) (n/T sweep) and 37(c) (2609.20550's estimable out-of-subspace floor) are NOT executed here.

Runtime 111s.
