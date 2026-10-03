# Paper watchlist — mailer picks 13→22 Jul, marked to today

7309 unique picks priced (first-appearance entry, equal-weight, held to latest close). Return vs each market's median tracked name = excess. Short window, no costs — read direction.

## Overall

| book | n | mean return | hit rate | excess vs market |
|---|---|---|---|---|
| ALL picks (raw) | 7309 | -1.40% | 40% | +0.14% |
| CURATED (graded-A + fundamentals) | 2574 | -0.80% | 41% | +0.78% |
| REC-BUY at entry (per-market rule) | 2456 | -1.92% | 36% | -0.32% |
| REC-SELL at entry (rule said avoid) | 2439 | -1.11% | 43% | +0.39% |
| CURATED ∩ REC-BUY | 763 | -1.20% | 37% | +0.62% |

## By market

| market | n | mean | hit | excess | curated mean | rec-BUY mean |
|---|---|---|---|---|---|---|
| EU | 393 | -0.64% | 44% | -0.00% | -0.73% (110) | -1.65% (126) |
| IN | 68 | +0.76% | 40% | +5.69% | +0.76% (68) | +0.76% (68) |
| JP | 2122 | +2.03% | 54% | +1.67% | +2.87% (768) | +1.89% (701) |
| KR | 1292 | -1.47% | 34% | +0.21% | -0.95% (452) | -3.09% (425) |
| US | 3434 | -3.61% | 32% | -0.93% | -3.23% (1176) | -4.03% (1136) |

## By filter (curated only)

| filter | n | mean | hit | excess |
|---|---|---|---|---|
| debt_reduction | 49 | -2.90% | 33% | +2.04% |
| piotroski+debt | 9 | +22.27% | 78% | +27.21% |
| roce_plus | 6 | -8.49% | 17% | -3.55% |
| technical | 2506 | -0.84% | 41% | +0.64% |

## Entry-day cohorts (mean return to today)

| entry date | n | mean return |
|---|---|---|
| 2026-07-21 | 2162 | +0.41% |
| 2026-07-22 | 321 | -3.94% |
| 2026-08-29 | 1257 | -1.32% |
| 2026-08-31 | 845 | -4.24% |
| 2026-09-01 | 434 | -3.30% |
| 2026-09-03 | 73 | -6.32% |
| 2026-09-04 | 275 | -3.99% |
| 2026-09-07 | 427 | -1.67% |
| 2026-09-09 | 195 | -2.43% |
| 2026-09-10 | 63 | -3.19% |
| 2026-09-11 | 56 | -3.36% |
| 2026-09-12 | 59 | -0.77% |
| 2026-09-14 | 95 | +0.31% |
| 2026-09-16 | 188 | -0.00% |
| 2026-09-17 | 175 | -0.85% |
| 2026-09-19 | 58 | -0.73% |
| 2026-09-21 | 172 | +0.69% |
| 2026-09-22 | 111 | +1.49% |
| 2026-09-23 | 59 | -1.87% |
| 2026-09-24 | 139 | +0.16% |
| 2026-09-25 | 39 | -0.37% |
| 2026-09-26 | 106 | -0.05% |

## Read

⚠️ WINDOW: 30% of picks entered on 2026-07-21 (the breakout firehose day) — only a few trading sessions of forward data, inside the KOSDAQ-crash / soft-US drawdown, so EVERY book is negative in absolute terms. Excess vs market is the fair read; the per-market REC rule is a 2-WEEK reversion signal and CANNOT be judged on 2-3 sessions — its forward validation is backtest_zone_rules.py (8y, mean-revert wins US/JP/KR/EU). This paper-track is a curation test, not a rule test.

- CURATION IS THE VALUE-ADD: raw picks lag their market by +0.14%; graded-A + fundamentals lifts that to +0.78% excess (≈market-neutral in a down tape).
- Curation dodged the KOSDAQ crash: KR raw -1.47% → KR curated -0.95% (452 names).
- Best curated filter by excess: piotroski (+36.63%); EU picks -0.64% at 44% hit.
- Per-market rule applied AT ENTRY (point-in-time): REC-BUY -1.92% vs REC-SELL -1.11% — a -0.81% spread (no edge this window).