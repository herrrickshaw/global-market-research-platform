# Strategy survival across bull & bear markets (2016→2026)

Each price-based filter run PIT on each market's own 10y weekly panel; returns split by regime (BEAR = breadth <45% of liquid names above their 40-week trend; BULL otherwise). Universe = HIGH+MEDIUM turnover tier only. `spread` = BUY−SELL fwd-10d; `book` = long-only BUY names; `index` = equal-weight all names (the benchmark); `excess` = book − index. **Survives = excess > 0 in BOTH regimes.** No costs, weekly rebalance.

## IN  (338 bull / 209 bear weeks) — zone-winner **trend**, survives both: **YES**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.65 (t+6.9) | +1.10 | +0.79 | **+0.30** |
|  | bear | +0.06 (t+0.1) | +0.09 | +0.03 | **+0.06** |
| revert | bull | -0.09 (t-0.7) | +0.76 | +0.79 | **-0.04** |
|  | bear | +0.35 (t+1.9) | +0.19 | +0.07 | **+0.12** |
| mom126 | bull | +0.63 (t+4.4) | +1.07 | +0.79 | **+0.28** |
|  | bear | +0.15 (t+0.3) | +0.17 | +0.07 | **+0.11** |
| mom_st | bull | +0.41 (t+3.1) | +0.99 | +0.79 | **+0.20** |
|  | bear | -0.40 (t-1.4) | -0.14 | +0.07 | **-0.20** |
| golden_cross | bull | +0.61 (t+5.3) | +0.97 | +0.79 | **+0.18** |
|  | bear | +0.41 (t+1.5) | +0.29 | +0.07 | **+0.23** |
| breakout | bull | +0.88 (t+5.8) | +1.24 | +0.79 | **+0.44** |
|  | bear | +0.58 (t+1.5) | +0.34 | -0.07 | **+0.41** |

## US  (393 bull / 128 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.29 (t+2.7) | +0.27 | +0.16 | **+0.11** |
|  | bear | -0.58 (t-1.5) | +0.05 | +0.48 | **-0.43** |
| revert | bull | +0.01 (t-0.1) | +0.09 | +0.16 | **-0.07** |
|  | bear | +0.35 (t+2.2) | +0.63 | +0.48 | **+0.15** |
| mom126 | bull | +0.51 (t+3.0) | +0.31 | +0.15 | **+0.15** |
|  | bear | +0.13 (t+0.4) | +0.44 | +0.42 | **+0.02** |
| mom_st | bull | +0.10 (t+0.9) | +0.11 | +0.16 | **-0.05** |
|  | bear | -0.36 (t-1.1) | +0.26 | +0.48 | **-0.22** |
| golden_cross | bull | +0.53 (t+3.3) | +0.35 | +0.16 | **+0.19** |
|  | bear | +0.26 (t+0.7) | +0.56 | +0.48 | **+0.08** |
| breakout | bull | +0.66 (t+2.7) | +0.37 | +0.15 | **+0.21** |
|  | bear | -0.39 (t-0.4) | -0.07 | +0.38 | **-0.46** |

## JP  (404 bull / 117 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.16 (t+1.9) | +0.48 | +0.42 | **+0.06** |
|  | bear | -0.75 (t-2.5) | +0.43 | +0.97 | **-0.54** |
| revert | bull | +0.01 (t+0.3) | +0.42 | +0.42 | **-0.01** |
|  | bear | +0.43 (t+1.8) | +1.05 | +0.87 | **+0.18** |
| mom126 | bull | +0.34 (t+2.9) | +0.48 | +0.35 | **+0.13** |
|  | bear | -0.56 (t-2.5) | +0.54 | +0.83 | **-0.29** |
| mom_st | bull | +0.09 (t+1.2) | +0.47 | +0.42 | **+0.04** |
|  | bear | -0.59 (t-2.4) | +0.48 | +0.83 | **-0.34** |
| golden_cross | bull | +0.29 (t+3.2) | +0.50 | +0.42 | **+0.08** |
|  | bear | -0.31 (t-2.0) | +0.60 | +0.83 | **-0.22** |
| breakout | bull | +0.43 (t+3.2) | +0.47 | +0.35 | **+0.12** |
|  | bear | -0.57 (t-1.7) | +0.58 | +1.00 | **-0.42** |

## KR  (235 bull / 286 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.53 (t+3.2) | +0.15 | -0.12 | **+0.27** |
|  | bear | -0.94 (t-4.1) | -0.76 | +0.01 | **-0.77** |
| revert | bull | -0.17 (t-1.8) | -0.24 | -0.12 | **-0.12** |
|  | bear | +0.50 (t+1.9) | +0.24 | +0.08 | **+0.16** |
| mom126 | bull | +0.37 (t+1.2) | +0.05 | -0.04 | **+0.09** |
|  | bear | -0.52 (t-2.5) | -0.21 | +0.08 | **-0.29** |
| mom_st | bull | +0.39 (t+2.1) | -0.00 | -0.12 | **+0.12** |
|  | bear | -0.63 (t-3.0) | -0.33 | +0.08 | **-0.41** |
| golden_cross | bull | +0.40 (t+1.8) | +0.03 | -0.12 | **+0.15** |
|  | bear | -0.33 (t-2.0) | -0.17 | +0.08 | **-0.25** |
| breakout | bull | +1.00 (t+4.2) | +0.62 | -0.04 | **+0.66** |
|  | bear | -0.36 (t-1.0) | -0.41 | -0.08 | **-0.33** |

## EU  (422 bull / 99 bear weeks) — zone-winner **revert**, survives both: **YES**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.06 (t+1.6) | +0.24 | +0.22 | **+0.02** |
|  | bear | -0.56 (t-1.1) | +0.77 | +1.16 | **-0.39** |
| revert | bull | +0.04 (t-0.6) | +0.23 | +0.22 | **+0.01** |
|  | bear | +0.64 (t+2.0) | +1.42 | +1.12 | **+0.30** |
| mom126 | bull | +0.34 (t+3.3) | +0.34 | +0.19 | **+0.14** |
|  | bear | -0.26 (t-1.1) | +1.03 | +1.12 | **-0.09** |
| mom_st | bull | -0.07 (t+0.3) | +0.19 | +0.22 | **-0.03** |
|  | bear | -0.83 (t-2.8) | +0.69 | +1.12 | **-0.43** |
| golden_cross | bull | +0.37 (t+4.3) | +0.35 | +0.22 | **+0.13** |
|  | bear | -0.06 (t-0.6) | +1.04 | +1.12 | **-0.08** |
| breakout | bull | +0.46 (t+3.5) | +0.34 | +0.19 | **+0.15** |
|  | bear | -0.43 (t-0.6) | +0.83 | +1.16 | **-0.33** |

## Book economics — zone-winner, annualized (×26), $10k/position
| market | regime | book ret/2w | annualized | vs index (excess ann.) | $ excess p.a. / $1M book |
|---|---|---|---|---|---|
| IN | bull | +1.10% | +28.5% | +7.9% | +78,618 |
|  | bear | +0.09% | +2.3% | +1.5% | +15,370 |
| US | bull | +0.09% | +2.3% | -1.8% | -18,477 |
|  | bear | +0.63% | +16.3% | +3.8% | +38,211 |
| JP | bull | +0.42% | +10.8% | -0.2% | -2,139 |
|  | bear | +1.05% | +27.2% | +4.6% | +45,936 |
| KR | bull | -0.24% | -6.3% | -3.2% | -31,892 |
|  | bear | +0.24% | +6.2% | +4.0% | +40,305 |
| EU | bull | +0.23% | +6.0% | +0.3% | +2,822 |
|  | bear | +1.42% | +36.9% | +7.9% | +78,756 |

> ⚠️ Long-only book returns are gross, no costs, no slippage, weekly rebalance on a $1-floor universe; annualization assumes the per-regime mean repeats — a ceiling, not a forecast. Excess vs the equal-weight index is the survival read; the raw book return just inherits beta.