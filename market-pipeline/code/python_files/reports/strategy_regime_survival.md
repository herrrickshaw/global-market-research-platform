# Strategy survival across bull & bear markets (2016→2026)

Each price-based filter run PIT on each market's own 10y weekly panel; returns split by regime (BEAR = breadth <45% of liquid names above their 40-week trend; BULL otherwise). Universe = HIGH+MEDIUM turnover tier only. `spread` = BUY−SELL fwd-10d; `book` = long-only BUY names; `index` = equal-weight all names (the benchmark); `excess` = book − index. **Survives = excess > 0 in BOTH regimes.** No costs, weekly rebalance.

## IN  (346 bull / 214 bear weeks) — zone-winner **trend**, survives both: **YES**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.66 (t+7.2) | +1.08 | +0.77 | **+0.31** |
|  | bear | +0.05 (t+0.1) | +0.06 | -0.00 | **+0.06** |
| revert | bull | -0.10 (t-1.0) | +0.73 | +0.77 | **-0.04** |
|  | bear | +0.35 (t+1.9) | +0.16 | +0.04 | **+0.12** |
| mom126 | bull | +0.65 (t+4.6) | +1.05 | +0.77 | **+0.29** |
|  | bear | +0.13 (t+0.3) | +0.13 | +0.04 | **+0.09** |
| mom_st | bull | +0.42 (t+3.2) | +0.98 | +0.77 | **+0.21** |
|  | bear | -0.40 (t-1.4) | -0.16 | +0.04 | **-0.20** |
| golden_cross | bull | +0.63 (t+5.6) | +0.96 | +0.77 | **+0.19** |
|  | bear | +0.41 (t+1.5) | +0.26 | +0.04 | **+0.22** |
| breakout | bull | +0.90 (t+6.1) | +1.21 | +0.77 | **+0.45** |
|  | bear | +0.56 (t+1.5) | +0.29 | -0.10 | **+0.39** |
| hi52 | bull | +0.75 (t+4.9) | +1.11 | +0.77 | **+0.34** |
|  | bear | +0.15 (t+0.4) | +0.12 | +0.04 | **+0.08** |
| lowvol | bull | +0.02 (t+0.2) | +0.70 | +0.77 | **-0.07** |
|  | bear | +0.32 (t+1.1) | +0.09 | +0.04 | **+0.05** |

## US  (400 bull / 134 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.28 (t+2.6) | +0.25 | +0.14 | **+0.11** |
|  | bear | -0.56 (t-1.5) | -0.03 | +0.39 | **-0.41** |
| revert | bull | +0.02 (t-0.0) | +0.07 | +0.14 | **-0.07** |
|  | bear | +0.28 (t+2.0) | +0.48 | +0.39 | **+0.09** |
| mom126 | bull | +0.51 (t+3.0) | +0.29 | +0.14 | **+0.15** |
|  | bear | +0.21 (t+0.6) | +0.37 | +0.32 | **+0.05** |
| mom_st | bull | +0.09 (t+1.0) | +0.09 | +0.14 | **-0.05** |
|  | bear | -0.31 (t-1.1) | +0.16 | +0.39 | **-0.22** |
| golden_cross | bull | +0.52 (t+3.3) | +0.33 | +0.14 | **+0.19** |
|  | bear | +0.31 (t+0.8) | +0.49 | +0.39 | **+0.10** |
| breakout | bull | +0.63 (t+2.6) | +0.34 | +0.14 | **+0.20** |
|  | bear | -0.28 (t-0.3) | -0.11 | +0.29 | **-0.39** |
| hi52 | bull | +0.86 (t+3.3) | +0.37 | +0.14 | **+0.23** |
|  | bear | +0.29 (t+0.5) | +0.32 | +0.32 | **-0.00** |
| lowvol | bull | +0.91 (t+2.9) | +0.37 | +0.15 | **+0.22** |
|  | bear | +0.50 (t+0.6) | +0.41 | +0.39 | **+0.02** |

## JP  (418 bull / 117 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.14 (t+1.5) | +0.46 | +0.42 | **+0.04** |
|  | bear | -0.75 (t-2.5) | +0.43 | +0.97 | **-0.54** |
| revert | bull | +0.01 (t+0.4) | +0.40 | +0.42 | **-0.01** |
|  | bear | +0.43 (t+1.8) | +1.05 | +0.87 | **+0.18** |
| mom126 | bull | +0.33 (t+2.9) | +0.47 | +0.34 | **+0.13** |
|  | bear | -0.56 (t-2.5) | +0.54 | +0.83 | **-0.29** |
| mom_st | bull | +0.06 (t+0.6) | +0.44 | +0.42 | **+0.03** |
|  | bear | -0.59 (t-2.4) | +0.48 | +0.83 | **-0.34** |
| golden_cross | bull | +0.28 (t+3.2) | +0.49 | +0.42 | **+0.07** |
|  | bear | -0.31 (t-2.0) | +0.60 | +0.83 | **-0.22** |
| breakout | bull | +0.41 (t+3.1) | +0.46 | +0.34 | **+0.12** |
|  | bear | -0.58 (t-1.7) | +0.58 | +1.00 | **-0.42** |
| hi52 | bull | +0.30 (t+2.6) | +0.47 | +0.34 | **+0.12** |
|  | bear | -0.61 (t-2.0) | +0.51 | +0.83 | **-0.31** |
| lowvol | bull | +0.02 (t+0.6) | +0.40 | +0.41 | **-0.01** |
|  | bear | -0.07 (t-0.5) | +0.78 | +0.83 | **-0.05** |

## KR  (235 bull / 300 bear weeks) — zone-winner **revert**, survives both: **NO**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.53 (t+3.2) | +0.15 | -0.12 | **+0.27** |
|  | bear | -1.01 (t-4.4) | -0.81 | +0.00 | **-0.81** |
| revert | bull | -0.17 (t-1.8) | -0.24 | -0.12 | **-0.12** |
|  | bear | +0.51 (t+2.0) | +0.23 | +0.07 | **+0.16** |
| mom126 | bull | +0.37 (t+1.2) | +0.05 | -0.04 | **+0.09** |
|  | bear | -0.58 (t-2.8) | -0.24 | +0.07 | **-0.31** |
| mom_st | bull | +0.39 (t+2.1) | -0.00 | -0.12 | **+0.12** |
|  | bear | -0.68 (t-3.2) | -0.36 | +0.07 | **-0.44** |
| golden_cross | bull | +0.41 (t+1.8) | +0.03 | -0.12 | **+0.15** |
|  | bear | -0.38 (t-2.4) | -0.21 | +0.07 | **-0.29** |
| breakout | bull | +1.00 (t+4.2) | +0.62 | -0.04 | **+0.66** |
|  | bear | -0.44 (t-1.4) | -0.54 | -0.14 | **-0.40** |
| hi52 | bull | +0.90 (t+4.2) | +0.42 | -0.04 | **+0.46** |
|  | bear | -0.48 (t-1.9) | -0.19 | +0.07 | **-0.26** |
| lowvol | bull | +0.54 (t+2.9) | +0.15 | -0.09 | **+0.24** |
|  | bear | +0.52 (t+2.7) | +0.27 | +0.08 | **+0.19** |

## EU  (434 bull / 100 bear weeks) — zone-winner **revert**, survives both: **YES**

| strategy | regime | spread% (t) | book% | index% | excess% |
|---|---|---|---|---|---|
| trend | bull | +0.05 (t+1.1) | +0.23 | +0.21 | **+0.02** |
|  | bear | -0.57 (t-1.1) | +0.78 | +1.18 | **-0.40** |
| revert | bull | +0.05 (t-1.0) | +0.23 | +0.21 | **+0.02** |
|  | bear | +0.65 (t+2.1) | +1.44 | +1.14 | **+0.31** |
| mom126 | bull | +0.32 (t+3.0) | +0.32 | +0.18 | **+0.14** |
|  | bear | -0.26 (t-1.1) | +1.05 | +1.14 | **-0.09** |
| mom_st | bull | -0.07 (t-0.1) | +0.18 | +0.21 | **-0.04** |
|  | bear | -0.85 (t-2.8) | +0.69 | +1.14 | **-0.44** |
| golden_cross | bull | +0.36 (t+4.1) | +0.33 | +0.21 | **+0.12** |
|  | bear | -0.06 (t-0.6) | +1.06 | +1.14 | **-0.08** |
| breakout | bull | +0.43 (t+3.0) | +0.32 | +0.18 | **+0.14** |
|  | bear | -0.43 (t-0.5) | +0.86 | +1.18 | **-0.32** |
| hi52 | bull | +0.32 (t+2.6) | +0.30 | +0.18 | **+0.12** |
|  | bear | -0.54 (t-1.4) | +0.83 | +1.14 | **-0.30** |
| lowvol | bull | +0.10 (t+0.9) | +0.24 | +0.21 | **+0.03** |
|  | bear | -0.26 (t-1.0) | +0.96 | +1.14 | **-0.18** |

## Book economics — zone-winner, annualized (×26), $10k/position
| market | regime | book ret/2w | annualized | vs index (excess ann.) | $ excess p.a. / $1M book |
|---|---|---|---|---|---|
| IN | bull | +1.08% | +28.1% | +8.1% | +81,006 |
|  | bear | +0.06% | +1.4% | +1.4% | +14,392 |
| US | bull | +0.07% | +1.9% | -1.8% | -18,281 |
|  | bear | +0.48% | +12.4% | +2.4% | +23,550 |
| JP | bull | +0.40% | +10.5% | -0.3% | -2,907 |
|  | bear | +1.05% | +27.2% | +4.6% | +45,871 |
| KR | bull | -0.24% | -6.3% | -3.2% | -31,900 |
|  | bear | +0.23% | +6.1% | +4.2% | +41,804 |
| EU | bull | +0.23% | +6.0% | +0.4% | +4,404 |
|  | bear | +1.44% | +37.5% | +8.0% | +79,834 |

> ⚠️ Long-only book returns are gross, no costs, no slippage, weekly rebalance on a $1-floor universe; annualization assumes the per-regime mean repeats — a ceiling, not a forecast. Excess vs the equal-weight index is the survival read; the raw book return just inherits beta.