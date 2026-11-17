# Entropic yield curve — the 2020 (Entropy 20:662) variant

Sample 1990-01-02 .. 2026-07-30 (9,136 days), 4 bear onsets, expanding-window thresholds (no lookahead).


Spec: `r(t) = B0 + ln(t)/t*(1-p) - ln(sigma)/t*p`, maturities 1M..20Y, sigma FREE. With `A = 1-p` and `B = -p*ln(sigma)` this is ordinary OLS in `{ln(t)/t, 1/t}`. Median fit RMSE **34.0 bp**, against 67.1 bp for the 2017 spec — the extra parameter genuinely helps.


**C1 is unknown and does not matter.** `R/C = 1 + ln(p)/C1` is strictly monotone in `p` for any `C1 > 0`, and `Var(R/C) = Var(ln p)/C1^2` is that series times a positive constant. Every signal below is a percentile breach of one of the two, so the scorecard is invariant to C1 — only printed levels move. The unknown parameter cannot rescue the result.


| signal | fires | hits | false pos | precision | caught | recall |
|---|---|---|---|---|---|---|
| Var(R/C) 60d, 2020 spec | 6 | 1 | 5 | 0.17 | 1/4 | 0.25 |
| R/C LOW level (his trigger shape) | 8 | 1 | 7 | 0.12 | 1/4 | 0.25 |
| sigma HIGH level | 12 | 2 | 10 | 0.17 | 2/4 | 0.50 |
| 10Y-3M inversion (baseline) | 11 | 3 | 8 | 0.27 | 2/4 | 0.50 |

- corr(R/C, 10Y-3M spread) = **+0.811** — still essentially the term spread, even with sigma freed.
- corr(sigma, 10Y-3M spread) = -0.014 — sigma IS a genuinely new quantity, uncorrelated with the curve. It is still the weaker signal.

## Verdict

**The 2020 variant fails too, and for the same reason.** Parker's own trigger is a LOW-LEVEL one (R/C < 1.02), so that shape is tested directly rather than only the variance: it fires 8 times, catches 1 of 4 bears at 0.12 precision. Plain 10Y-3M inversion catches 2 of 4 at 0.27. Freeing sigma improves the CURVE FIT (67 -> 34 bp) without improving the SIGNAL — which is what you expect when the derived quantity is a reparameterisation of the term structure rather than new information.

The one honest positive: sigma is uncorrelated with the term spread, so it is not just the curve in disguise. It still scores below the baseline (0.17 vs 0.27 precision), so it is new but not useful — and n=4 bear onsets cannot separate 0.17 from 0.27 with any confidence. Neither variant is worth wiring in.

