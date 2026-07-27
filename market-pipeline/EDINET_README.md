# Japan EDINET Fundamentals — Single Source of Truth

**Status (2026-07-27): OPERATIONAL.** API download works; data aggregated into Postgres + master parquet.

---

## Current State

| Store | Contents |
|---|---|
| Postgres `japan_fundamentals_history` | 18,398 rows, 3,500+ tickers, FY2011→FY2026 |
| Postgres `japan_current` | 2,937 TSE companies (prices + Darvas signals, refreshed by daily pipeline) |
| `global-stock-screener/cache_seed/fundamentals_history/JP_master.parquet` | Deduped master (all sources merged) |
| Dropbox + GDrive `/market-data-archive/edinet_xbrl/` | Raw EDINET ZIPs (cold archive) |

Coverage: **94%+ of the live 2,937-company universe has FY2024+ fundamentals.**

---

## The Working Pipeline (3 commands)

EDINET has no bulk endpoint but the **official API** (`api.edinet-fsa.go.jp/api/v2`) serves
individual filings. Key in `~/.config/market-secrets/credentials.env` (`EDINET_API_KEY`).

```bash
# 1. Download filings (individual files, resumable via manifest.csv)
python3 scripts/edinet_api_downloader.py \
    --start 2025-07-01 --end 2026-06-30 --doc-types 120 --format csv --dest /tmp/edinet_annual

# 2. Aggregate everything (fresh EDINET + all prior parquets) → Postgres + JP_master.parquet
/usr/bin/python3 scripts/japan_aggregate_all.py

# 3. Archive raw ZIPs to cloud, free local disk
tar cf /tmp/edinet_annual_$(date +%Y%m%d).tar -C /tmp edinet_annual
rclone move /tmp/edinet_annual_*.tar dropbox:/market-data-archive/edinet_xbrl/
rclone copy dropbox:/market-data-archive/edinet_xbrl/ gdrive:/Market-Data-Archive/EDINET/
rm -rf /tmp/edinet_annual
```

Notes:
- `--format csv` (API type=5) = EDINET's pre-extracted CSV (UTF-16 TSV) — far easier than raw iXBRL.
- Doc types: `120` annual, `140` quarterly (abolished Apr 2024), `160` semi-annual.
- Both scripts are idempotent: downloader skips manifest entries, aggregator upserts on conflict.
- Aggregator source priority: `edinet_fresh > edinet_prior > jquants > merged_prior > full_prior > yf_breadth > yf_core`.

## Annual refresh

Most March-FYE companies file in late June. Run the 3 commands above each July with the
date range advanced one year.

## Querying

```sql
-- Join live signals with fundamentals
SELECT c.tse_code, c.company_name, c.darvas_signal, h.roe, h.revenue_jpy
FROM japan_current c
JOIN japan_fundamentals_history h ON h.tse_code = c.tse_code
WHERE h.fiscal_period >= 'FY2024' AND h.roe > 0.15
ORDER BY h.roe DESC;
```

Or via the knowledge graph: `graphify query "how does EDINET data flow into Postgres"`.

## History / superseded approaches

Bulk-download, web-scraping, and manual-download approaches were dead ends (EDINET's
disclosure website is JS-rendered and has no bulk files; the *website* API returns HTML).
The fix was using the documented API host. Removed scripts/docs live in git history
(commits `8557cc44` and earlier: `edinet_auto_download.py`, `edinet_web_scraper.py`,
`edinet_individual_downloader.py`, `EDINET_MANUAL_DOWNLOAD_GUIDE.md`, `EDINET_QUICK_START.md`,
`EDINET_WORKFLOW_VISUAL.txt`, `EDINET_FILES_INDEX.md`, `EDINET_CLOUD_STRATEGY.md`, `EDINET_WORKFLOW.sh`).
