# Strategy survival across bull & bear markets (2016→2026)

Each price-based filter run PIT on each market's own 10y weekly panel; returns split by regime (BEAR = breadth <45% of liquid names above their 40-week trend; BULL otherwise). Universe = HIGH+MEDIUM turnover tier only. `spread` = BUY−SELL fwd-10d; `book` = long-only BUY names; `index` = equal-weight all names (the benchmark); `excess` = book − index. **Survives = excess > 0 in BOTH regimes.** No costs, weekly rebalance.

## IN  (346 bull / 211 bear weeks) — zone-winner **trend**, survives both: **YES**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.66 (t+7.1) | +1.09 | +0.78 | **+0.31** |
|  | bear | +0.06 (t+0.1) | +0.09 | +0.03 | **+0.06** |
| revert | bull | -0.10 (t-1.0) | +0.74 | +0.78 | **-0.04** |
|  | bear | +0.34 (t+1.9) | +0.19 | +0.07 | **+0.12** |
| mom126 | bull | +0.65 (t+4.6) | +1.07 | +0.78 | **+0.29** |
|  | bear | +0.15 (t+0.3) | +0.17 | +0.07 | **+0.11** |
| mom_st | bull | +0.42 (t+3.2) | +0.99 | +0.78 | **+0.21** |
|  | bear | -0.40 (t-1.4) | -0.13 | +0.07 | **-0.20** |
| golden_cross | bull | +0.63 (t+5.6) | +0.97 | +0.78 | **+0.19** |
|  | bear | +0.41 (t+1.5) | +0.29 | +0.07 | **+0.23** |
| breakout | bull | +0.90 (t+6.1) | +1.23 | +0.78 | **+0.45** |
|  | bear | +0.58 (t+1.5) | +0.34 | -0.07 | **+0.41** |

## US  (400 bull / 131 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.28 (t+2.6) | +0.25 | +0.14 | **+0.11** |
|  | bear | -0.57 (t-1.5) | +0.04 | +0.46 | **-0.42** |
| revert | bull | +0.02 (t-0.1) | +0.07 | +0.14 | **-0.07** |
|  | bear | +0.34 (t+2.1) | +0.60 | +0.46 | **+0.14** |
| mom126 | bull | +0.51 (t+3.0) | +0.29 | +0.14 | **+0.15** |
|  | bear | +0.14 (t+0.4) | +0.43 | +0.40 | **+0.03** |
| mom_st | bull | +0.09 (t+1.0) | +0.09 | +0.14 | **-0.05** |
|  | bear | -0.35 (t-1.1) | +0.24 | +0.46 | **-0.22** |
| golden_cross | bull | +0.52 (t+3.3) | +0.33 | +0.14 | **+0.19** |
|  | bear | +0.27 (t+0.7) | +0.54 | +0.46 | **+0.08** |
| breakout | bull | +0.63 (t+2.6) | +0.34 | +0.14 | **+0.20** |
|  | bear | -0.38 (t-0.4) | -0.09 | +0.36 | **-0.45** |

## JP  (414 bull / 117 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.15 (t+1.7) | +0.49 | +0.44 | **+0.05** |
|  | bear | -0.75 (t-2.5) | +0.43 | +0.97 | **-0.54** |
| revert | bull | +0.03 (t+0.6) | +0.44 | +0.44 | **-0.00** |
|  | bear | +0.43 (t+1.8) | +1.05 | +0.87 | **+0.18** |
| mom126 | bull | +0.33 (t+2.9) | +0.50 | +0.37 | **+0.13** |
|  | bear | -0.56 (t-2.5) | +0.54 | +0.83 | **-0.29** |
| mom_st | bull | +0.08 (t+0.8) | +0.48 | +0.44 | **+0.04** |
|  | bear | -0.59 (t-2.4) | +0.48 | +0.83 | **-0.34** |
| golden_cross | bull | +0.28 (t+3.2) | +0.52 | +0.44 | **+0.07** |
|  | bear | -0.31 (t-2.0) | +0.60 | +0.83 | **-0.22** |
| breakout | bull | +0.41 (t+3.1) | +0.49 | +0.37 | **+0.12** |
|  | bear | -0.58 (t-1.7) | +0.58 | +1.00 | **-0.42** |

## KR  (235 bull / 296 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.53 (t+3.2) | +0.15 | -0.12 | **+0.27** |
|  | bear | -0.99 (t-4.3) | -0.74 | +0.07 | **-0.81** |
| revert | bull | -0.17 (t-1.8) | -0.24 | -0.12 | **-0.12** |
|  | bear | +0.53 (t+2.1) | +0.31 | +0.14 | **+0.17** |
| mom126 | bull | +0.37 (t+1.2) | +0.05 | -0.04 | **+0.09** |
|  | bear | -0.57 (t-2.7) | -0.17 | +0.13 | **-0.31** |
| mom_st | bull | +0.39 (t+2.1) | -0.00 | -0.12 | **+0.12** |
|  | bear | -0.67 (t-3.2) | -0.29 | +0.14 | **-0.42** |
| golden_cross | bull | +0.41 (t+1.8) | +0.03 | -0.12 | **+0.15** |
|  | bear | -0.35 (t-2.2) | -0.13 | +0.14 | **-0.27** |
| breakout | bull | +1.00 (t+4.2) | +0.62 | -0.04 | **+0.66** |
|  | bear | -0.44 (t-1.4) | -0.47 | -0.07 | **-0.40** |

## EU  (430 bull / 100 bear weeks) — zone-winner **revert**, survives both: **YES**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.05 (t+1.2) | +0.24 | +0.22 | **+0.02** |
|  | bear | -0.57 (t-1.1) | +0.78 | +1.18 | **-0.40** |
| revert | bull | +0.05 (t-1.0) | +0.24 | +0.22 | **+0.02** |
|  | bear | +0.65 (t+2.1) | +1.44 | +1.14 | **+0.31** |
| mom126 | bull | +0.33 (t+3.1) | +0.33 | +0.19 | **+0.14** |
|  | bear | -0.26 (t-1.1) | +1.05 | +1.14 | **-0.09** |
| mom_st | bull | -0.07 (t-0.0) | +0.18 | +0.22 | **-0.03** |
|  | bear | -0.85 (t-2.8) | +0.69 | +1.14 | **-0.44** |
| golden_cross | bull | +0.37 (t+4.1) | +0.34 | +0.22 | **+0.12** |
|  | bear | -0.06 (t-0.6) | +1.06 | +1.14 | **-0.08** |
| breakout | bull | +0.44 (t+3.0) | +0.33 | +0.19 | **+0.14** |
|  | bear | -0.43 (t-0.5) | +0.86 | +1.18 | **-0.32** |

## Book economics — zone-winner, annualized (×26), $10k/position
| market | regime | book ret/2w | annualized | vs index (excess ann.) | $ excess p.a. / $1M book |
|---|---|---|---|---|---|
| IN | bull | +1.09% | +28.5% | +8.1% | +80,747 |
|  | bear | +0.09% | +2.3% | +1.5% | +15,459 |
| US | bull | +0.07% | +1.9% | -1.8% | -18,256 |
|  | bear | +0.60% | +15.5% | +3.6% | +36,190 |
| JP | bull | +0.44% | +11.5% | -0.0% | -253 |
|  | bear | +1.05% | +27.2% | +4.6% | +45,871 |
| KR | bull | -0.24% | -6.3% | -3.2% | -31,900 |
|  | bear | +0.31% | +8.1% | +4.5% | +44,822 |
| EU | bull | +0.24% | +6.1% | +0.5% | +4,559 |
|  | bear | +1.44% | +37.5% | +8.0% | +79,834 |

> ⚠️ Long-only book returns are gross, no costs, no slippage, weekly rebalance on a $1-floor universe; annualization assumes the per-regime mean repeats — a ceiling, not a forecast. Excess vs the equal-weight index is the survival read; the raw book return just inherits beta.