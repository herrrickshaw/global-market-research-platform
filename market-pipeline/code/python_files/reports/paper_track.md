# Paper watchlist — mailer picks 13→22 Jul, marked to today

2500 unique picks priced (first-appearance entry, equal-weight, held to latest close). Return vs each market's median tracked name = excess. Short window, no costs — read direction.

## Overall

| book | n | mean return | hit rate | excess vs market |
|---|---|---|---|---|
| ALL picks (raw) | 2500 | -0.75% | 43% | -0.45% |
| CURATED (graded-A + fundamentals) | 811 | -0.65% | 44% | -0.28% |
| REC-BUY at entry (per-market rule) | 877 | -1.31% | 35% | -0.94% |
| REC-SELL at entry (rule said avoid) | 813 | -0.68% | 47% | -0.42% |
| CURATED ∩ REC-BUY | 278 | -1.36% | 35% | -0.78% |

## By market

| market | n | mean | hit | excess | curated mean | rec-BUY mean |
|---|---|---|---|---|---|---|
| EU | 185 | +0.25% | 61% | -0.01% | +0.05% (32) | -0.26% (61) |
| IN | 70 | -0.72% | 31% | +0.81% | -0.72% (70) | -0.72% (70) |
| JP | 765 | -0.28% | 45% | -0.17% | -0.08% (340) | -0.05% (255) |
| KR | 177 | -1.51% | 38% | -0.73% | +0.60% (60) | -5.92% (58) |
| US | 1303 | -1.06% | 41% | -0.70% | -1.56% (309) | -1.68% (433) |

## By filter (curated only)

| filter | n | mean | hit | excess |
|---|---|---|---|---|
| debt_reduction | 50 | -1.72% | 28% | -0.19% |
| piotroski+debt | 10 | +6.40% | 80% | +7.93% |
| roce_plus | 6 | -4.12% | 0% | -2.59% |
| technical | 741 | -0.64% | 45% | -0.38% |

## Entry-day cohorts (mean return to today)

| entry date | n | mean return |
|---|---|---|
| 2026-07-21 | 2172 | -0.74% |
| 2026-07-22 | 328 | -0.79% |

## Read

⚠️ WINDOW: 87% of picks entered on 2026-07-21 (the breakout firehose day) — only a few trading sessions of forward data, inside the KOSDAQ-crash / soft-US drawdown, so EVERY book is negative in absolute terms. Excess vs market is the fair read; the per-market REC rule is a 2-WEEK reversion signal and CANNOT be judged on 2-3 sessions — its forward validation is backtest_zone_rules.py (8y, mean-revert wins US/JP/KR/EU). This paper-track is a curation test, not a rule test.

- CURATION IS THE VALUE-ADD: raw picks lag their market by -0.45%; graded-A + fundamentals lifts that to -0.28% excess (≈market-neutral in a down tape).
- Curation dodged the KOSDAQ crash: KR raw -1.51% → KR curated +0.60% (60 names).
- Best curated filter by excess: piotroski+debt (+7.93%); EU picks +0.25% at 61% hit.
- Per-market rule applied AT ENTRY (point-in-time): REC-BUY -1.31% vs REC-SELL -0.68% — a -0.63% spread (no edge this window).