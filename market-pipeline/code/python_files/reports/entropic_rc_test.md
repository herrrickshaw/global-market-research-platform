# Entropic yield curve — does Var(R/C) predict bear markets?

Sample 1990-01-02 .. 2026-07-30 (9,136 trading days). Bear = 20% drawdown off the running peak; a signal is a HIT if a bear starts within 252 trading days.

Thresholds are EXPANDING-window percentiles, so no signal uses information from its own future.


## Bear onsets found (4)

- 2001-03-12
- 2008-07-09
- 2020-03-12
- 2022-06-13

## Signal scorecard

| signal | fires | hits | false pos | precision | bears caught | recall |
|---|---|---|---|---|---|---|
| Var(R/C), 60d | 11 | 1 | 10 | 0.09 | 1/4 | 0.25 |
| Var(a), 60d | 13 | 2 | 11 | 0.15 | 2/4 | 0.50 |
| |a| level | 4 | 0 | 4 | 0.00 | 0/4 | 0.00 |
| fit RMSE | 4 | 0 | 4 | 0.00 | 0/4 | 0.00 |
| **10Y-3M inversion (baseline)** | 11 | 3 | 8 | 0.27 | 2/4 | 0.50 |

## Is R/C independent of the term spread?

- corr(a, 10Y-3M spread)   = -0.952
- corr(R/C, 10Y-3M spread) = +0.821
- corr(R/C, a)             = -0.859
- days with a >= 1 (R/C undefined): 794 of 9,136 (8.7%)
- R/C range: -5.3 .. 4.5  (a negative information-processing rate is meaningless in the model)

## Parker's Table 2, recomputed on the same zones

| zone | mean R/C | var R/C | mean a | var a | days a>=1 |
|---|---|---|---|---|---|
| I 1990-1998 | 3.47 | 0.40 | -13.256 | 66.7313 | 0 |
| II 1999-2002 | 3.38 | 1.06 | -11.002 | 107.6619 | 172 |
| III 2003-2006 | 3.33 | 1.85 | -14.685 | 131.0556 | 70 |
| IV 2007-2009 | 3.52 | 1.62 | -15.779 | 111.7561 | 56 |
| V 2010-2016 | 4.11 | 0.05 | -22.051 | 24.2846 | 0 |

## Verdict

**The claim does not survive.** Var(R/C) fires 11 times and catches 1 of 4 bear markets at 0.09 precision. Plain 10Y-3M inversion fires the same 11 times, catches 2, at 0.27. The entropic signal is strictly dominated by the oldest and simplest yield-curve indicator there is.

**And it is not an independent quantity.** corr(R/C, 10Y-3M) = +0.821. R/C is a monotone reparameterisation of the term spread, so it cannot carry information the spread does not already have — it can only add noise, which is what 10 false positives versus 8 looks like.

**Parker's Table 2 does not replicate — selectively.** This reconstruction matches his published numbers closely in the BULL zones (I: 3.47/0.40 vs his 3.41/0.41; V: 4.11/0.05 vs 4.07/0.10), which is the evidence that the estimator is faithful. It does not reproduce them in the two CRISIS zones his entire thesis rests on: he reports mean R/C of -56.78 and -24.35 with variances of 1097 and 1302; the same calculation on the same dates and the same Treasury series gives means of 3.38 and 3.52 with variances of 1.06 and 1.62. Mean R/C is flat (3.33 to 4.11) across all five zones. Zone III — a bull period — has HIGHER variance (1.85) than either crisis zone, so the variance ordering does not separate bulls from bears at all.

**Where his numbers likely come from.** R/C = 1 + ln(1 - a) has a logarithmic singularity at a = 1. Any fit that wanders near it prints arbitrarily large negative values — exactly the -56.78 shape. Here a >= 1 on 794 days (8.7%), where R/C is undefined rather than extreme. A "phase transition" that is a coordinate singularity in the author's own reparameterisation is not evidence about the economy.

**Fit quality, for context.** The one-parameter fixed-shape curve misses the actual Treasury curve by a median 67 bp (p95 210 bp). It is not tracking the yield curve closely enough for a derived quantity to mean much.

**Recommendation: do not wire this into the brief.** Not as a signal, and not as a regime input. If the entropy/bond-equity direction is worth pursuing, the credible route is transfer entropy on returns (Jizba et al., Renyi TE) rather than a yield-curve reparameterisation — with the caveat that TE cannot identify direction near synchronisation, which is precisely the crisis regime of interest.

