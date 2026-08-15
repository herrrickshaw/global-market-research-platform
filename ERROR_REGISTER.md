# Error register

Defects found across the platform, kept so past failures stay monitorable rather than
being rediscovered. One row per defect, stable ID, never renumbered — a fixed entry
stays in the register with its evidence so a regression is recognisable on sight.

**Scope:** `backend/`, `market-pipeline/code/python_files/`, `scripts/`.
**Last updated:** 2026-08-15.

Severity: **S1** wrong data reaching a decision · **S2** silent failure / data loss ·
**S3** correctness risk not currently firing · **S4** operational noise.

Status: `OPEN` · `FIXED` · `LOST` (unrecoverable) · `WONTFIX`.

---

## Open

| ID | Sev | Component | Defect | Evidence |
|---|---|---|---|---|
| E-001 | S1 | `scanners/daily_scanner.py` | `scan_darvas(lazy_load=True)` nulls `roe`, `pe`, `pb`, `debt_to_equity`, MACD, Bollinger, stochastics and EMA-20/200 **before scoring**. The router passes `lazy_load=True` at both call sites, so 4 of 13 declared criteria are evaluated and `max_score` is 6 against 15. The documented Buffett overlay never fires. | Masking imputed fundamentals changed Darvas BUY counts by exactly 0 across all 5 markets — the fields never reach scoring. Enabling the overlay moves BUY 5,083 → 9,974 (+96%), so the fixed `score >= 5` threshold must be retuned with it, not flipped. |
| E-002 | S1 | `routers/live.py:102-108` | `/api/live/fetch` fire-and-forgets `upsert_quotes` into the same `stock_quotes` row the nightly batch writes, with no ordering guarantee. An ad-hoc fetch on a partial symbol list overwrites the batch values mid-session. | Two writers, last-write-wins. `stock_quotes_history` (E-012) makes it recoverable, not absent. |
| E-003 | S2 | `daily_mailer.sh` | Send phase exits **0** when it loses the shared lock, so launchd records success and no brief goes out. No alert. | 2026-08-15: data phase ran 03:05→07:27, the 06:30 send printed `pipeline already running (pid 48919) — exiting`, `last_brief_sent.json` stayed on 08-14. |
| E-004 | LOST | `global-stock-screener` | `cache_seed/fundamentals_history/IN_screener_only_backup.parquet` — deleted in the 2026-08-14 cleanup, present in git only as a 132-byte LFS pointer (LFS retired), absent from Dropbox *and* gdrive. | Numeric core reconstructed from `public.global_fundamentals` (12,511 rows / 1,459 tickers, EPS verified: RELIANCE 32.40, TCS 135.70, HDFCBANK 48.51). See E-005 for what could not be reconstructed. |
| E-005 | S1 | `backtest_pe_anomalies.py` | `industry` is null in the E-004 reconstruction, and industry drives the sector-relative comparison the screen exists to make. No local source has it. | Cassandra covers 189 of 3,484 India names (5%); `public.stocks` has 0 industry values and no India overlap; `indices.factsheet_sector` is index-level weights. Needs a screener.in re-collection. |
| E-006 | S3 | `playbook_screener.py:125` | `KeyError: 'market'` — groupby on an empty frame, no empty-guard. Was masked by E-014 crashing first. | Reproduced 2026-08-15 after E-014 was fixed. |
| E-007 | S2 | `daily_research.sh` | Lacks the power assertion added to `daily_mailer.sh` (E-010), so R1–R15 is still exposed to suspend-stalling. | Not applied: the script was mid-run, and editing a live bash script shifts its byte-offset read. |
| E-008 | S3 | `db/cassandra_client.py:26` | Cassandra runs `SimpleStrategy` `replication_factor=1` on one node — no replica, so a node loss is data loss. Correct at this scale; becomes S1 the moment it runs on more than one machine. | Verified live: `nodetool status` single `UN`. |
| E-009 | S4 | power management | `pmset` `wakepoweron at 0:10AM` still aims at the `com.umashankar.dailybrief` job retired 2026-07-29. It also failed to power the Mac on at all on 2026-08-04. | Would be useful again if the data phase moves to ~00:30. |

## Fixed

| ID | Sev | Component | Defect | Evidence / fix |
|---|---|---|---|---|
| E-010 | S1 | `daily_mailer.sh` | **The pipeline was sleeping, not slow.** 262-min data phase vs 11 min on adjacent days. | `pmset` logged **37** `Entering Sleep state` events inside 03:05→07:27 and **0** inside the two 11-min runs; step [4/13]'s marker is `04:33:55`, a sleep event to the second. Profiled the rebuild everyone assumed was the cost: clean 17.1s + LMDB 5.8s + regroup 2.2s + parquet 0.2s ≈ **29s** of a 3,670s step. Fixed with `caffeinate -i -m -w "$$"`. An incremental rebuild was **not** written — it would have recovered 0.8%. |
| E-011 | S2 | `daily_mailer.sh` `cap()` | Watchdog accumulated `CAP_POLL` per iteration; `sleep 5` does not advance while suspended, so a 61-min step never tripped `CAP_BHAVCOPY=2400` and no TIMEOUT was logged. | Now compares `date +%s` against a start stamp. Tested: 3s job / 10s cap → rc 0; 8s job / 2s cap → rc 124, killed. |
| E-012 | S2 | `db/schema.cql` | `stock_quotes` overwritten in place — every RSI/MACD/PE the pipeline ever computed was lost on the next fetch; no signal could be backtested against its own inputs. | Added append-only `stock_quotes_history`, PK `((market, yf_ticker), snapshot_date)` DESC. Measured 385 B/row, 1.90 GiB/yr, ~250 rows/partition/yr. Re-keying `stock_quotes` was rejected: three readers depend on `market` being the whole partition key. |
| E-013 | S2 | `db/schema.cql` | Drifted from `cassandra_client._SCHEMA`: missing `price_history` entirely and all 25 migration columns. `cqlsh -f schema.cql` produced a keyspace that failed on the first portfolio lookup. | Synced and verified column-for-column; applied cleanly to a live node. |
| E-014 | S2 | `strategy_regime_survival.py`, `backtest_pe_anomalies.py` | The 2026-08-14 warehouse migration broke both silently behind `|| continuing` — `max()` on an empty glob, and `pd.concat` "No objects to concatenate" which took the value-rerating, playbook and small-cap screens with it. | Repointed at `~/.cache/market-warehouse` (237 MB, only the years actually read). Both now raise on missing years instead of truncating; negative-tested. `MARKET_WH` scoped to `--refresh-regime` so the monthly full backtests can't silently shorten. |
| E-015 | S1 | `db/cassandra_client.py` | The live `stock_quotes` had **49** columns while the backend declared **41**. `bridge_ratios_to_cassandra.py` had `ALTER`ed the table directly; `fundamentals_source` — the column that distinguishes imputed from measured — was invisible to every backend query. | All 8 declared and applied. Kept as `_BRIDGE_COLS`, separate from `_VALUE_COLS`, because `upsert_quotes` binds positionally and the fetch path produces none of them. |
| E-016 | S1 | `bridge_ratios_to_cassandra.py` | ROE written as a **fraction** into a column the app documents as a **percent** (`base.py:56 # %`, `yahoo.py:127 _pct`), read by `daily_scanner.py:191` as `roe > 12`. | 0% of bridge-written rows could pass, against 4–24% for the placeholders they replaced — the "fix" made the column strictly worse for its only consumer. Now ×100; pass rate 26% (JP) / 14% (KR). |
| E-017 | S1 | `bridge_ratios_to_cassandra.py` | `fundamentals_source` stamped `derived_price_join` unconditionally, so roe-only rows kept the median placeholder underneath while claiming to be derived. | 348 japan / 1,005 korea rows. Now labelled per row (`derived_roe_only`). Post-fix rows-on-sentinel-while-labelled-derived = **0**. |
| E-018 | S1 | `bridge_ratios_to_cassandra.py` | Ticker resolution created duplicates: `load_fundamentals` dedupes on the raw ticker, then bare `003547` maps onto an existing `003547.KS`. Last write won arbitrarily. | KOREA 4,749 rows for 2,667 tickers (4,164 dupes); JAPAN 0. Cost 1,227 tickers a valid `pe`. Dedupe moved after resolution, keeping the most complete row. |
| E-019 | S1 | `bridge_ratios_to_cassandra.py` | Loss-makers (`eps <= 0`) kept an imputed **positive** P/E while being stamped derived — a positive earnings multiple asserted for a company that lost money. | 830 korea rows. Now written as an explicit NULL. |
| E-020 | S2 | `bridge_ratios_to_cassandra.py` | ROE had no plausibility ceiling while `pe`/`pb` did, despite sharing the near-zero-equity failure mode. | KOREA produced `roe = -1312` (−131,200%) from 8 symbols with equity ≤ 0. Bounded at ±200%. |
| E-021 | S2 | `db/quote_updater.py` | `snapshot_market()` recorded a 17-day-stale serving table as a fresh observation — 21,198 rows under `snapshot_date = 2026-08-15` carrying `fetched_at = 2026-07-29`. No backtest could tell it from real. | Skips rows older than `max_age_days` (default 2). Boundary-tested at 1/2/3 days. A gap in history is honest; a duplicated stale row is not. |
| E-022 | S3 | `db/quote_updater.py` | `cassandra.util.Date` has no `.isoformat()`; `get_quote_history()` raised on the first real read. Invisible to a stubbed session. | `str()` yields ISO for both that type and `datetime.date`. |

## Historical — fixed before this register, kept for regression watch

| ID | Sev | Component | Defect | Watch for |
|---|---|---|---|---|
| E-023 | S1 | mailer send gate | 2026-07-15: every internal check passed while the pipeline shipped a GOLDEN_CROSS pick quoting a **seven-week-old** price. | The gate added in response has since fired for real (2026-08-01, and 2026-08-15 on a lagging yfinance validator). Do not weaken it. |
| E-024 | S1 | `db/quote_updater.py` | 2026-07-29: binding `None` wrote tombstones, so the Phase-1 price loader and the Phase-2 fundamentals loader silently deleted each other's columns. ~25,500 rows carrying `cmp` at 08:27 were down to 3 by 09:40; `eps > 0` in zero rows across every market. | Fixed with `UNSET_VALUE`. Any future all-columns INSERT must use it. Note the trade-off: a value that legitimately becomes null now retains its last figure. |
| E-025 | S1 | `bhavcopy_history.py` | 2026-07-15: NSE precedence resolved per *symbol* instead of per (symbol, date), freezing 270 of 7,833 symbols at their last NSE bar — up to 313 days stale — while BSE traded on. MODISONLTD was emitted as a GOLDEN_CROSS pick at a stale price. | Resolved per (Symbol, Date). Watch any change to the dedup keys. |
| E-026 | S2 | `bhavcopy_history.py` | 2026-07-15: if a run persisted `assembled` then died before writing `cleaned`, `new_rows` was empty on every later run and the fast path short-circuited the rebuild **forever**. | Guarded by `_cleaned_behind_assembled`. |
| E-027 | S2 | `bhavcopy_history.py` | The fast path returned before the LMDB sync, pinning the store at 2026-07-15 while `cleaned` advanced to 07-20 — stale prices returned plausibly rather than failing. | Guarded by `_lmdb_behind_cleaned`, and the failure is loud. |

---

## Standing hazards (not defects, but they cause them)

- **`|| continuing` hides everything.** E-003, E-010 and E-014 were all invisible for days because a step that fails is indistinguishable from a step that succeeds quietly. Any new guarded step needs its failure surfaced in the alert, not just the log.
- **Imputed values are indistinguishable from measured ones without `fundamentals_source`.** India/US/Europe remain 62–77% `median_imputed`; only JP/KR have been rebuilt. Anything ranking on `pe`/`roe` is ranking partly on placeholders.
- **The Dropbox mirror is online-only placeholders** — 886 MB logical, 0 resident. A restore is a download, not a copy, and has never been drilled. gdrive holds only DART + EDINET, so the two providers are complementary, not redundant.
