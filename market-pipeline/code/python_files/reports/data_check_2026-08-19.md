# Data check — 2026-08-19

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
| IN | 1,860 | 3,075 | 48% | 2012-2026 | 102 | 17 | 🔴 THIN | ✅ powered |
| US | 4,597 | 5,700 | 61% | 1987-2029 | 102 | 17 | ✅ complete | ✅ powered |
| EU | 449 | 1,067 | 28% | 2021-2026 | 54 | 9 | 🔴 THIN | 🔴 UNDERPOWERED |


See `reports/data_sufficiency.md`, `reports/data_quality.md`, `reports/data_ledger.md`
for full detail; `cache_seed/data_sufficiency_history.parquet` for the coverage trend.
