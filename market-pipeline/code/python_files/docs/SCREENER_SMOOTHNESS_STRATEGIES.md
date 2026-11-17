# Daily-screener smoothness strategies — from the 3-repo knowledge graph

Source: `graphify-out/merged-3repo-graph.json` (market-pipeline + global-stock-screener +
global-market-data merged 2026-07-27: **10,754 nodes / 18,777 edges**), cross-checked
against today's live pipeline run and its two failures. Ranked by expected smoothness
gain ÷ effort.

## 1. Kill the 13-way scan-code duplication (highest structural risk)

The graph's clearest finding: **26 functions are duplicated across ≥3 of the market-scan
monoliths** — `compute_darvas_box()` and `fundamental_scan()` exist in **13 copies**,
`main()` ×13, `_first_df()`/`_row()`/`_series()` ×9, `bulk_download_ohlc()` ×7,
cache load/save ×6. Every Darvas or yfinance-quirk fix must currently be applied up to
13 times; the copies WILL drift (the `_first_df` yfinance-DataFrame bug we fixed once
already lives in 9 places).

**Strategy:** extract one `scan_core.py` (box logic, `_first_df`, bulk download, cache,
styling) and make the five `full_*_market_scan.py` thin per-market configs. The graph
already nominates the seam: `strategies/base.py::StockData` is the shared hub (deg 53).
Effort 5, gain: every scan bug becomes a one-place fix.

## 2. Wall off the ~/Downloads wipe-hazard class (recurring outage source)

**28 files** in `code/python_files` still reference `~/Downloads` paths; 8 reference the
exact trees (`Downloads/market_cache`, `Downloads/data`) that a parallel session wipes —
today's sentiment-cache crash was the third incident of this class (SEC + India
collections lost before). `symbol_master.py`, `market_data_cache.py`, `data_registry.py`
are in the list — all upstream of scans.

**Strategy:** repeat today's `sentiment_pipeline.py` fix pattern (repo-relative default +
`mkdir` self-heal + env override) across the 8 direct-path files, then add a step [0]
assertion that every required cache dir exists. Effort 3, gain: deletes an entire
failure class.

## 3. Scan from the warehouse, validate against live (today's INFY lesson)

Today's mailer block: INFY carried Friday's close on a +3.7% Monday because one yfinance
call fell back to stale cache. The graph shows each scan monolith owns its own
`bulk_download_ohlc()` + `_load_cache()` — five independent fetch/fallback stacks, none
warehouse-aware, even though Postgres now holds `bhavcopy.*` (1.8M rows),
`global_fundamentals` (237k, official sources) and `market_daily.snapshots`.

**Strategy:** make scans read prices/fundamentals from the warehouse first (single
consistency point, already freshness-ledgered), with yfinance as *delta* refresh, and
extend the `validate_brief.py` spot-check to every market (it only samples India today).
Effort 5, gain: no more per-scan cache drift; validation catches what remains.

## 4. Put the ETL quality-gate pattern in front of every scan step

The new `etl_fundamentals.py` gates (rows>0, key-null, date-sane, fill-rate) rejected a
bad source on first contact. The scans have no equivalent: an empty/stale parquet flows
straight into signals (the pipeline's own header admits step [0] once flagged deps and
"every scan died").

**Strategy:** 5-line pre-flight per scan step — assert input parquet/table exists, is
non-empty, and its max date ≥ last trading day (use `market_calendar.py`, already a
node in the graph). Fail the step loudly *before* compute, not downstream in the mailer.
Effort 2, gain: failures move to the cheap end of the pipeline.

## 5. Wire the graphs into ops (make this analysis self-refreshing)

The three graphs were built independently (two by a parallel session today) and only
merged manually now. `save_manifest` is recorded for market-pipeline, so `--update` is
incremental (seconds).

**Strategy:** append a weekly `graphify update + merge-graphs` step to
`weekly_maintenance.sh` (NOT the daily pipeline — graph drift is slow), and keep
`merged-3repo-graph.json` queryable so "what breaks if I change X" is a 2k-token query
instead of a grep session. Effort 1.

## Quick-win order

| # | strategy | effort | failure class it removes |
|---|---|--:|---|
| 4 | pre-flight gates on scan inputs | 2 | silent empty/stale inputs |
| 2 | Downloads-path eradication | 3 | parallel-session wipes |
| 5 | weekly graph refresh + merge | 1 | blind cross-repo changes |
| 3 | warehouse-first scans + all-market validation | 5 | per-scan cache drift (INFY class) |
| 1 | scan_core extraction (13× dup) | 5 | divergent copies of core logic |

> Grounded in graph structure + today's observed failures. The duplication counts and
> file lists are reproducible: see the analysis snippets in this doc's commit.
