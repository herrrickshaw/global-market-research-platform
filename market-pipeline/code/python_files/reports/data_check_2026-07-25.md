# Data check — 2026-07-25

Every-3-days sufficiency + quality sweep. Sources: `data_check.sh`.

```
  ✅ ratios rebuilt (6 markets)
  ✅ quality gate (GE/dbt expectations)
  ✅ sufficiency guard (+ trend history + flips)
  ✅ freshness ledger
```

## Current sufficiency verdict

| market | fund tickers | liquid universe | coverage | years | formations | nonov-6M | completeness | power |
|---|--:|--:|--:|--:|--:|--:|:--:|:--:|
| IN | 1,870 | 3,103 | 60% | 2012-2026 | 102 | 17 | ✅ complete | ✅ powered |
| US | 4,597 | 5,086 | 90% | 1987-2029 | 102 | 17 | ✅ complete | ✅ powered |
| KR | 1,564 | 1,622 | 96% | 2016-2026 | 102 | 17 | ✅ complete | ✅ powered |
| JP | 1,295 | 1,609 | 80% | 2021-2026 | 54 | 9 | ✅ complete | 🔴 UNDERPOWERED |
| EU | 449 | 15 | 2993% | 2021-2026 | 54 | 9 | ✅ complete | 🔴 UNDERPOWERED |
| CN | 932 | 3,454 | 27% | 2021-2025 | 54 | 9 | 🔴 THIN | 🔴 UNDERPOWERED |


See `reports/data_sufficiency.md`, `reports/data_quality.md`, `reports/data_ledger.md`
for full detail; `cache_seed/data_sufficiency_history.parquet` for the coverage trend.
