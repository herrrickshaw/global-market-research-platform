# Global Market Research Platform

Multi-market (India/US/Europe/Japan/Korea) fundamentals collection and the
nightly research pipeline that turns it into a daily brief: bhavcopy/OHLC
ingest → five-market scan + mailer → correlation/factor modelling → factor
grid backtests.

## Layout

| Path | Contents |
|---|---|
| `code/python_files/` | The actual pipeline: `ingest.sh`/`mailer.sh`/`modelling.sh`/`factor_tests.sh` (see `PIPELINE.md`), `data_registry.py`/`data_index.py` (freshness gating), `run_monitor.py`, `repo_tracker.py`, plus scanners/backtests (`darvas_breakouts.py`, `pead_analysis.py`, `sip_xirr_backtest.py`, `train_ppo_factor_weights.py`, `sentiment_pipeline.py`, `ohlcv_cache.py`, `full_us_market_scan.py`, ...) |
| `data/` | Pipeline outputs and caches per market/scan type, plus `market_data.duckdb` |
| `market_cache/` | Local `dart`/`nse_xbrl`/`ohlc`/... cache read and written by the collectors |
| Top-level `*.py` | Fundamentals collectors and the Postgres→Cassandra bridge (see below) |
| `colibri.yaml` | Memory-optimized streaming extraction config (batch sizes, rate limits, checkpointing) for NSE/BSE/US/EU/JP/KR |
| `daily_collection.sh` | launchd-scheduled daily fundamentals refresh (Japan J-Quants, Korea KRX, Europe; India/US run on separate schedules — see the script) |

## Nightly pipeline

`code/python_files/PIPELINE.md` is the authoritative doc. Summary: what was
one 14-step, 3-5h, all-or-nothing `daily_pipeline.sh` run is now four sections
on three schedules, linked by a freshness gate in `data_registry.py`:

```
ingest.sh (weekdays 00:15) → mailer.sh (weekdays 00:30, HARD-gated on ingest)
                            → modelling.sh (Sat 02:00, advisory-gated)
                            → factor_tests.sh (Sat, after modelling, advisory-gated)
```

```bash
./ingest.sh && ./mailer.sh      # the weekday chain
./mailer.sh --draft             # build the brief without sending
./modelling.sh --skip-ppo       # weekly research, minus the long pole
./factor_tests.sh --market IN   # one market's grid

data_index.py                   # what is stale, and who was supposed to write it
data_index.py --require ingest  # the gate itself; exit 1 = not usable
run_monitor.py                  # per-step durations, per-section trend
repo_tracker.py --paths         # path-drift guard (scripts disagreeing on cache paths)
```

`daily_pipeline.sh` still exists and still works — the four sections are
additive, not a replacement, until the staged `launchd/` plists are installed.

## Fundamentals collection

Per-market collectors and a Postgres→Cassandra bridge, documented in
`FUNDAMENTALS_COLLECTION_STRATEGY.md`, `UNIFIED_FUNDAMENTALS_SCHEMA.md`, and
the market-specific status docs (`JAPAN_EDINET_STATUS.md`, `EDINET_README.md`,
`ALTERNATIVE_FUNDAMENTALS_SOURCES.md`):

- `dart_fundamentals_collector.py`, `build_korea_dart_mapping.py`, `dart_fetch_company_list.py` — Korea DART
- `complete_india_us_fundamentals.py`, `fundamentals_collector_production_FULL.py`, `fundamentals_collector_production_v2_20col.py` — India/US
- `bridge_pg_fundamentals_to_cassandra.py` — pushes the Postgres fundamentals warehouse into the Cassandra keyspace the live app reads from
- `export_fundamentals_duckdb.py`, `impute_and_flag_nulls.py` — export + null-handling

## Known hazards

- **TCC**: macOS denies launchd all access to `~/Downloads` — every collector path must resolve through the `$MARKET_CACHE`/`$BHAV_CACHE` env vars (`data_registry.py`), not a hardcoded path. `repo_tracker.py --paths` guards against drift.
- **The Mac must be awake** for `StartCalendarInterval` launchd jobs to fire — check `pmset -g sched` is non-empty. A job listed by `launchctl list` is not evidence it ran; check `runs =` in `launchctl print gui/$(id -u)/<label>`.
- See `DATA_POINTERS.md` for where data moved during the 2026-07-27 disk-space reclaim (correlation matrices → `.zst`, europe_scan → parquet) and how to rehydrate anything archived to Dropbox.
