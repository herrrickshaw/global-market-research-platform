# Data pointers — format & location changes (2026-07-27 space reclaim)

Records where data moved and how its format changed during the disk cleanup, so any
reference keeps resolving. Canonical path resolution still lives in
`code/python_files/data_registry.py`; this file records the format/location deltas.

## Correlation matrices — CSV → zstd-compressed CSV
- **Was:** `code/python_files/correlation_scan/<market>_correlation_matrix.csv` (uncompressed, up to 806 MB)
- **Now:** `code/python_files/correlation_scan/<market>_correlation_matrix.csv.zst` (~2.3× smaller, lossless — verified by sha256)
- **Read unchanged:** `pd.read_csv(".../us_correlation_matrix.csv.zst")` — pandas infers zstd from the `.zst` suffix, so DataFrames round-trip identically.
- **Writer updated:** `market_correlation_scan.py` now writes `.csv.zst` directly.
- **Nothing read the big matrix** (only `*_top_correlated_pairs.csv` / `*_clusters.txt` are downstream), so no consumer changes were needed.
- **Backup:** `dropbox:market-pipeline-cache/correlation_scan/<market>_correlation_matrix.csv.zst` (online-only on Dropbox).

## europe_scan matrix — CSV → parquet
- `data/europe_scan/europe_correlation_matrix.csv` (14.9 MB) → `.parquet` (5.8 MB, zstd). Read with `pd.read_parquet(...)`. Row count verified equal.

## market_cache/ — unchanged locally
- `market_cache/{dart,nse_xbrl,ohlc,...}` stays local and is still written/read by the collectors as before. A tar.zst backup can live at `dropbox:market-pipeline-cache/market_cache/` if needed; collectors also rebuild it. No reference change.

## Archived to Dropbox and removed locally (not code-referenced)
- `~/.mempalace/snapshots-archived/*.tar.zst` (3.5 GB) → `dropbox:market-pipeline-cache/mempalace-snapshots/` (all 4 verified byte-identical).
- `~/Desktop/sweep/warehouse.tar` (848 MB) → `dropbox:market-pipeline-cache/misc/` (verified).

## 🔴 Dropbox sync note
A Dropbox **desktop auto-sync** is active. Files under `dropbox:market-pipeline-cache/` appear
in `~/Library/CloudStorage/Dropbox/market-pipeline-cache/` as **online-only placeholders (0 B local)** —
so this backup does NOT re-consume local disk. If that folder ever starts downloading locally,
set it to *Online-only* in the Dropbox app to keep the space freed.

## Rehydrate from Dropbox
```bash
rclone copy dropbox:market-pipeline-cache/correlation_scan/us_correlation_matrix.csv.zst ./
```
