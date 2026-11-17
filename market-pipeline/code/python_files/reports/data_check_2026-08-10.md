# Data check — 2026-08-10

Every-3-days sufficiency + quality sweep. Sources: `data_check.sh`.

```
  ✅ ratios rebuilt (6 markets)
  ✅ quality gate (GE/dbt expectations)
  ✅ sufficiency guard (+ trend history + flips)
  ✅ freshness ledger
  ✅ source registry (+ reachability)
```

## Current sufficiency verdict

| market | fund tickers | liquid universe | coverage | years | formations | nonov-6M | completeness | power |
|---|--:|--:|--:|--:|--:|--:|:--:|:--:|
| IN | 1,880 | 3,147 | 49% | 2006-2026 | 102 | 17 | 🔴 THIN | ✅ powered |
| US | 4,597 | 4,045 | 67% | 1987-2029 | 102 | 17 | ✅ complete | ✅ powered |
| KR | 1,564 | 1,645 | 58% | 2016-2026 | 102 | 17 | 🔴 THIN | ✅ powered |
| JP | 1,437 | 2,345 | 34% | 2011-2024 | 102 | 17 | 🔴 THIN | ✅ powered |
| EU | 449 | 448 | 52% | 2021-2026 | 54 | 9 | 🔴 THIN | 🔴 UNDERPOWERED |
| CN | 1,993 | 3,454 | 58% | 2015-2025 | 102 | 17 | 🔴 THIN | ✅ powered |


See `reports/data_sufficiency.md`, `reports/data_quality.md`, `reports/data_ledger.md`
for full detail; `cache_seed/data_sufficiency_history.parquet` for the coverage trend.
