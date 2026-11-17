# Data-sufficiency audit — is each conclusion actually supported?

Guards against false outcomes from thin data. **completeness** = fundamentals cover ≥60% of the tradeable universe. **power** = ≥15 non-overlapping obs behind a 6M t-stat (below this, a t-stat is meaningless — 'not significant' means UNDERPOWERED, not 'no effect').

| market | fund tickers | liquid universe | coverage | years | formations | nonov-6M | completeness | power |
|---|--:|--:|--:|--:|--:|--:|:--:|:--:|
| IN | 1,860 | 3,300 | 47% | 2012-2026 | 102 | 17 | 🔴 THIN | ✅ powered |
| US | 4,597 | 4,623 | 63% | 1987-2029 | 102 | 17 | ✅ complete | ✅ powered |
| EU | 449 | 1,005 | 32% | 2021-2026 | 54 | 9 | 🔴 THIN | 🔴 UNDERPOWERED |

## What each verdict means for the analysis (DERIVED from the numbers above)

| market | trust the value-reversion result? | why |
|---|---|---|
| IN | 🟡 RETURNS ONLY | 17 obs (powered) BUT 47% liquid cov — a coverage bias risk; fetch more fundamentals |
| US | ✅ YES | 1987-2029, 63% liquid cov, 17 non-overlap obs — powered & complete |
| EU | 🔴 CAN'T CONCLUDE | only 9 non-overlap obs (2021-2026) — any t-stat is UNDERPOWERED; the verdict is a data artifact, not an effect |

> 🔴 The honest correction: only **India** is fully powered + reasonably complete. US is powered but coverage-thin (fetch shares). KR is borderline. **JP/EU/CN cannot be concluded either way on current data** — their verdicts were data-sufficiency artifacts. To fix: (1) fetch full-universe fundamentals (raise coverage), (2) collect deep history via official filings (EDINET-JP, EU registries, akshare-CN) to raise obs count, THEN re-run. Until then, report JP/EU/CN as 'insufficient data', not a verdict.