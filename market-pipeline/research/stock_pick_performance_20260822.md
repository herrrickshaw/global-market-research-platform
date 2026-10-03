# Stock Pick Performance — 2026-08-22

Merged from every dated/priced source available on this machine — not a true archive of what was emailed (none exists before this data), see coverage below.

## Coverage

| source | rows | date range |
|---|---:|---|
| backfill_ledger | 18,957 | 2026-06-12 → 2026-06-26 |
| live_ledger | 4,852 | 2026-07-13 → 2026-07-22 |
| watchlist_zone | 251 | 2026-07-13 → 2026-08-20 |
| gmail_brief | 158 | 2026-07-09 → 2026-07-17 |

Merged/deduped/priced: **23,900** entries, 2026-06-12 → 2026-08-20.

**Known gaps:**
- 2026-06-27 → 2026-07-12 (16d): no source has anything.
- `signal_tracker.py --record` has not run since 2026-07-22 (31d and counting) — wired into no cron/launchd job.
- EU/JP/KR: no local price panel, scored 0 unless `--fetch-missing`.

## Scored (min 5d held)

21,577 of 23,900 entries scored. Skipped: no_panel_file=2170, not_in_panel=58, no_bar_at_entry=56

| tier | n | median ret% | median vs bench% | win% | median days held |
|---|---:|---:|---:|---:|---:|
| buy | 21504 | 0.36 | -2.75 | 53% | 56 |
| hold | 41 | 5.56 | 2.29 | 80% | 24 |
| sell | 32 | -5.18 | -6.91 | 34% | 32 |

**Overall**: median return 0.37%, median vs benchmark -2.74%, win rate 53%.

'vs benchmark' is the number that matters — beating the index, not the sign of the raw return. n is still small; treat as a diary, not a result, until each tier has hundreds of entries across many dates.