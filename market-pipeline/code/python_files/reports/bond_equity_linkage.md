# Bond yields and equities — what actually links them

S&P 500 and the US Treasury curve, 1990-01-03 .. 2026-07-30 (9,135 trading days).


Every entropy figure is bias-corrected against shuffled surrogates and significance-tested, and every result is shown next to the plain correlation it has to beat. Method notes and limits are in the module docstring.


## 1. Does equity entropy fall in crises?

Sample entropy (m=2, r=0.2σ) of S&P 500 log returns, 252-day window stepped 21 days. **Lower = more regular = more predictable.** This is sequential regularity, not distribution width — the two move in opposite directions in a crash, and conflating them is the usual error.


Calm-period baseline: **SampEn 1.945** (n=354 windows), annualised vol 15.4%


| period | SampEn | vs calm | ann. vol | entropy direction |
|---|---|---|---|---|
| GFC 2007-09 to 2009-06 | 1.912 | -0.033 | 27.1% | DOWN (more regular) |
| COVID 2020-02 to 2020-06 | 1.311 | -0.634 | 24.9% | DOWN (more regular) |
| 2022 bear | 1.881 | -0.064 | 18.7% | DOWN (more regular) |
| dot-com 2000-03 to 2002-10 | 2.084 | +0.140 | 21.3% | UP |

- corr(SampEn, realised vol) = **-0.352** — entropy is NOT just inverted volatility

## 2. Transfer entropy — who leads whom?

Shannon TE, tercile bins, lag 1 day, 300 shuffled surrogates. **Effective TE** subtracts the surrogate mean because finite-sample TE is biased upward; the raw column shows how large that bias is. p is a permutation test.


🔴 TE is directional, NOT causal. Both series reacting to a common driver (a Fed decision, a CPI print) produces flow in both directions and is indistinguishable from causation with this method.


| period | n | TE bond→eq (eff) | p | TE eq→bond (eff) | p | net |
|---|---|---|---|---|---|---|
| full sample 1990-2026 | 9,135 | 0.00036 | 0.116 | 0.00022 | 0.189 | bond leads |
| 1990-1999 | 2,500 | -0.00082 | 0.811 | -0.00096 | 0.884 | bond leads |
| 2000-2009 | 2,497 | -0.00065 | 0.741 | 0.00250 | 0.020 | equity leads |
| 2010-2019 | 2,497 | 0.00049 | 0.256 | -0.00011 | 0.478 | bond leads |
| 2020-2026 | 1,641 | -0.00142 | 0.847 | 0.00158 | 0.166 | equity leads |

### State dependence

| state | n | TE bond→eq (eff) | p | TE eq→bond (eff) | p |
|---|---|---|---|---|---|
| calm (bottom 80% vol) | 7,320 | 0.00059 | 0.073 | -0.00034 | 0.841 |
| turbulent (top 20% vol) | 1,815 | -0.00003 | 0.445 | 0.00113 | 0.199 |

### Baseline it has to beat

- contemporaneous corr(bond return, equity return) = **-0.165**
- lagged corr(bond ret t-1, equity ret t) = +0.035
- lagged corr(equity ret t-1, bond ret t) = +0.041

## 3. What happens to equities during a bond selloff?

Selloff = 20-session rise in the 10-year yield above its 95th percentile (**+43 bp**). De-clustered at 60 days → **49 episodes**.


| horizon | mean fwd equity | median | hit rate >0 | unconditional mean | edge |
|---|---|---|---|---|---|
| 21d | +0.95% | +1.07% | 63% | +0.71% | +0.24pp |
| 63d | +1.99% | +2.44% | 69% | +2.15% | -0.16pp |
| 126d | +3.25% | +4.29% | 73% | +4.24% | -1.00pp |
| 252d | +8.22% | +11.13% | 79% | +8.59% | -0.38pp |

### The correlation is not stable — this is the main finding

| era | corr(bond ret, equity ret) | bonds hedge equities? |
|---|---|---|
| 1990-1999 | +0.338 | NO — positive corr, they fall together |
| 2000-2009 | -0.231 | YES — negative corr |
| 2010-2019 | -0.410 | YES — negative corr |
| 2020-2021 | -0.322 | YES — negative corr |
| 2022-2026 | +0.048 | neither, ~zero |

### Same event, opposite outcome depending on regime

| prevailing stock-bond corr at selloff | episodes | mean fwd 63d equity |
|---|---|---|
| negative (bonds hedging) | 27 | +0.98% |
| positive (bonds NOT hedging) | 19 | +3.09% |

## 4. Is there a borrow-and-trade (carry) channel?

Read as: does cheap short-term funding coincide with equity gains, and does the relationship reverse when funding costs spike? The 3-month bill is the funding-cost proxy; the term spread is the classic carry proxy.


| conditioning variable | corr with forward 1y equity return |
|---|---|
| 3m bill LEVEL (funding cost) | +0.040 |
| 3m bill 63d CHANGE (funding shock) | +0.213 |
| term spread 10y-3m (carry) | -0.088 |
| 10y yield level | -0.011 |

### Forward equity return by funding-cost quintile

| funding cost (3m bill) | mean fwd 1y | median | n days |
|---|---|---|---|
| Q1 cheapest | +10.42% | +11.88% | 1,808 |
| Q2 | +10.77% | +12.56% | 1,749 |
| Q3 | -2.20% | +4.28% | 1,773 |
| Q4 | +11.47% | +13.67% | 1,791 |
| Q5 dearest | +12.47% | +16.37% | 1,759 |

### Funding SHOCKS, not levels

- days after a top-decile 3m-rate rise (>45bp/63d): mean fwd 1y equity **+10.62%** (n=881)
- unconditional: +8.59%
- while the curve is INVERTED (negative carry): mean fwd 1y equity **+9.03%** (n=1,093)

## 5. Interpretation and limits

### 🔴 Effective sample size, not row count

The tables above quote n in the thousands, but forward returns are measured over OVERLAPPING windows. With 9,135 daily rows spanning 37 years, a 252-day forward return has roughly **37 independent observations**, not 9,135. Every correlation and quintile mean in section 4 therefore has far wider error bars than its row count suggests. A quintile holding ~1,800 days holds about 7 independent years. Treat differences of a few percentage points as noise.

### What each section actually established

1. **Entropy in crises — weakly supported, one event doing the work.** SampEn fell in the GFC (−0.03), COVID (−0.63) and 2022 (−0.06) but ROSE in dot-com (+0.14). Only COVID is a large move; the GFC and 2022 effects are negligible against a calm baseline of 1.945. So the published claim is not contradicted, but on this data it rests almost entirely on one crisis.
2. **Transfer entropy found essentially nothing.** Of ten direction/period cells, one reached p<0.05 (equity→bond, 2000-2009, p=0.020) — about what ten tests produce by chance. Several effective values are NEGATIVE, i.e. below the shuffled surrogate mean. At a one-day lag there is no reliable directional flow in either direction. The plain contemporaneous correlation (−0.165) carries more than any lead-lag relationship measured here.
3. **A bond selloff does not, on average, predict equity weakness.** Across 49 episodes the edge over the unconditional mean is +0.24pp at 21d and NEGATIVE at 63/126/252d — indistinguishable from zero. Forward hit rates (63–79% positive) match the unconditional drift of a rising market.
4. **No borrow-and-trade carry channel is visible.** If cheap funding drove equities, the cheapest-funding quintile would lead. It does not: dearest funding shows the HIGHEST forward return (+12.47% vs +10.42%), and a funding SHOCK correlates POSITIVELY with forward equity returns (+0.213). That is the procyclical reading — short rates rise because the economy is strong — not a carry unwind. The Q3 outlier (−2.20%) is period clustering, not a rate effect: that bucket is dominated by 2000-02 and 2007-08.

### The one durable finding

**The stock–bond correlation is not a constant, and it has flipped twice.** Positive in the 1990s (+0.34, they fell together), decisively negative through 2000–2021 (−0.23 to −0.41, bonds hedged equities), and back to roughly zero in 2022–2026 (+0.05). This is the fact that matters for the original question: 'what happens to equities in a bond selloff' has no era-independent answer, because whether bonds hedge equities is itself regime-dependent. Any allocation rule assuming the 2010s negative correlation is assuming a regime that ended.

*Descriptive analysis of historical relationships. Not investment advice.*
