# Tier-2/3 eviction backtest — anomalies under the preset criteria

Criteria: evict on market-bull + Markov bear-state + negative Kalman drift; anomaly at +10.0% (or +5.0% in RSI BUY band); validated at -15.0% or 90d. Top 200 liquid names/market, monthly evals 2018-01-01→.

## IN — 721 evictions
- ANOMALY 75.0% (median +6.3% in 18d) · validated-decline 10.8% · age-out 14.1%
- RSI at eviction: anomalies median 41 vs validated 41
- anomaly rate by year: 2020:100% · 2021:87% · 2023:83% · 2024:65% · 2025:45%
- re-entry 21d: n=540 (censored 1) · raw +1.67% med / +2.69% mean · **excess -0.52% med / +0.73% mean** · win 47% · t=1.95
- re-entry 63d: n=539 (censored 2) · raw +3.85% med / +5.26% mean · **excess -2.01% med / +0.04% mean** · win 44% · t=0.06
- re-entry 126d: n=537 (censored 4) · raw +7.53% med / +9.45% mean · **excess -2.96% med / -0.31% mean** · win 42% · t=-0.33

## JP — 2407 evictions
- ANOMALY 45.3% (median +11.1% in 34d) · validated-decline 20.2% · age-out 34.4%
- RSI at eviction: anomalies median 43 vs validated 42
- anomaly rate by year: 2018:29% · 2019:28% · 2020:39% · 2021:54% · 2022:35% · 2023:57% · 2024:34% · 2025:52% · 2026:54%
- re-entry 21d: n=1065 (censored 26) · raw +0.15% med / +0.77% mean · **excess -0.33% med / +0.45% mean** · win 48% · t=1.78
- re-entry 63d: n=1051 (censored 40) · raw +1.58% med / +2.71% mean · **excess -0.56% med / +0.70% mean** · win 47% · t=1.38
- re-entry 126d: n=956 (censored 135) · raw +2.32% med / +4.63% mean · **excess -1.35% med / +0.13% mean** · win 46% · t=0.18

## KR — 828 evictions
- ANOMALY 62.9% (median +11.8% in 21d) · validated-decline 23.9% · age-out 13.2%
- RSI at eviction: anomalies median 41 vs validated 41
- anomaly rate by year: 2020:55% · 2021:58% · 2023:51% · 2025:77% · 2026:52%
- re-entry 21d: n=519 (censored 2) · raw +0.70% med / +3.65% mean · **excess -2.37% med / -0.42% mean** · win 40% · t=-0.67
- re-entry 63d: n=504 (censored 17) · raw +1.67% med / +6.20% mean · **excess -5.36% med / -1.18% mean** · win 36% · t=-1.00
- re-entry 126d: n=414 (censored 107) · raw +8.48% med / +22.17% mean · **excess -9.39% med / +2.89% mean** · win 37% · t=1.20

## US — 2177 evictions
- ANOMALY 49.2% (median +11.1% in 28d) · validated-decline 25.1% · age-out 25.7%
- RSI at eviction: anomalies median 40 vs validated 41
- anomaly rate by year: 2018:21% · 2019:48% · 2020:65% · 2021:55% · 2022:39% · 2023:41% · 2024:57% · 2025:45% · 2026:38%
- re-entry 21d: n=1064 (censored 6) · raw +0.84% med / +0.68% mean · **excess -0.59% med / -0.36% mean** · win 47% · t=-1.11
- re-entry 63d: n=1050 (censored 20) · raw +2.59% med / +3.35% mean · **excess -1.19% med / +0.18% mean** · win 47% · t=0.30
- re-entry 126d: n=1029 (censored 41) · raw +4.11% med / +7.45% mean · **excess -2.60% med / +0.75% mean** · win 45% · t=0.74
