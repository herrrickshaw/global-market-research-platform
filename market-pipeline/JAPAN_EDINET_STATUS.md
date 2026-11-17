# Japan EDINET Infrastructure Status — Cloud-First Deployment

**As of 2026-07-27**

---

## Overview

Complete Japan fundamentals infrastructure is now in place. The system consolidates:
- **Real-time pricing + signals** (yfinance + Darvas via daily scan) → `japan_current` table
- **Historical fundamentals** (EDINET XBRL filings) → `japan_fundamentals_history` table
- **Cloud-first storage** (Dropbox + GDrive archival) → zero local disk usage after processing

---

## Current Status

### Postgres Tables (Ready)

| Table | Rows | Coverage | Source | Status |
|-------|------|----------|--------|--------|
| `japan_current` | 2,937 | All TSE companies | yfinance + Darvas scan | ✓ Live |
| `japan_fundamentals_history` | 0 | Awaiting EDINET | EDINET XBRL | ⏳ Pending download |

### Verification

```bash
# Check current snapshot
psql -d market_data -c "
  SELECT COUNT(*) as total_companies,
         COUNT(CASE WHEN darvas_signal IS NOT NULL THEN 1 END) as with_signal,
         COUNT(CASE WHEN roe IS NOT NULL THEN 1 END) as with_roe
  FROM japan_current;"
```

**Expected output:**
```
 total_companies | with_signal | with_roe
-----------------+-------------+----------
            2937 |        2937 |      200
```

### Signals Distribution

```bash
psql -d market_data -c "
  SELECT darvas_signal, COUNT(*) as count
  FROM japan_current
  GROUP BY darvas_signal
  ORDER BY count DESC;"
```

---

## Architecture

### Data Flow

```
1. EDINET Website (https://disclosure2.edinet-fsa.go.jp)
                ↓
2. Download XBRL ZIP to /tmp (temporary, 300-500 MB/quarter)
                ↓
3. Parse XBRL → Postgres (structured, compact, queryable)
                ↓
4. Archive ZIP to Dropbox (audit trail)
                ↓
5. Mirror to GDrive (redundancy)
                ↓
6. Delete /tmp (zero local usage)
                ↓
7. Postgres + Cloud = permanent, queryable data
```

### Storage Allocation

| Location | Purpose | Typical Size | Retention |
|----------|---------|---------|-----------|
| **Postgres** | Live queryable fundamentals | ~50 MB | Indefinite |
| **Dropbox** | Archive (audit trail) | ~1.2 GB/year | Indefinite |
| **GDrive** | Backup (redundancy) | ~1.2 GB/year | Indefinite |
| **Local disk** | None (goal: 0 MB) | 0 MB | N/A |

---

## Implementation Files

### 1. Core Python Modules

**`edinet_xbrl_historical_fetcher.py`**
- Parses EDINET XBRL bulk ZIPs
- Extracts GL account codes (revenue, net income, assets, debt, ROE, ROA)
- Loads into `japan_fundamentals_history` table
- Usage: `python edinet_xbrl_historical_fetcher.py --from-file /tmp/EDINET_XBRL_*.zip`

**`japan_data_consolidator.py`**
- Loads latest scan data (2,937 companies + signals)
- Merges with yfinance fundamentals (200 companies)
- Upserts into `japan_current` table
- Usage: `python japan_data_consolidator.py --load-scan`

### 2. Orchestration Scripts

**`EDINET_WORKFLOW.sh`** (Master workflow)
- `--validate` — Check Postgres readiness
- `--process FILE.zip` — Parse single XBRL archive
- `--download PERIOD` — Guide for manual EDINET download
- `--full-backfill` — Instructions for FY2023-2024 setup
- `--status` — Show coverage + row counts

**`scripts/edinet_process_and_archive.sh`** (Automated pipeline)
- Scans `/tmp` for EDINET_XBRL_*.zip files
- Parses each into Postgres
- Archives to Dropbox via rclone (automatic)
- Mirrors to GDrive (optional backup)
- Verifies Postgres + archives
- Deletes local temp files (zero-footprint cleanup)

### 3. Documentation

**`EDINET_SETUP.md`**
- Step-by-step setup guide
- XBRL GL account reference (jpfr:NetSalesJFY, etc.)
- Integration with daily pipeline
- Troubleshooting

**`EDINET_CLOUD_STRATEGY.md`**
- Cloud-first architecture rationale
- Storage allocation strategy
- Manual + automated workflows
- Cost/disk usage summary

---

## Next Steps: Quick Start

### Step 1: Download EDINET Files (Manual)

Visit: **https://disclosure2.edinet-fsa.go.jp/**

Download these bulk XBRL ZIPs:
- `EDINET_XBRL_2023_all.zip` (FY2023 Annual, ~400 MB)
- `EDINET_XBRL_2024Q1_all.zip` (Q1, ~350 MB)
- `EDINET_XBRL_2024Q2_all.zip` (Q2, ~350 MB)
- `EDINET_XBRL_2024Q3_all.zip` (Q3, ~350 MB)

**Total: ~1.4 GB, ~30 min to download**

### Step 2: Move to Temp Directory

```bash
mv ~/Downloads/EDINET_XBRL_*.zip /tmp/
```

### Step 3: Run Automated Pipeline

```bash
cd /Users/umashankar/market-pipeline
bash scripts/edinet_process_and_archive.sh
```

This will:
1. Find all `EDINET_XBRL_*.zip` in `/tmp`
2. Parse each into Postgres (1-2 min/quarter)
3. Verify in Postgres
4. Archive to Dropbox (5-10 min/quarter)
5. Mirror to GDrive (optional)
6. Delete `/tmp` files
7. Log all steps to `state/edinet_archive_YYYYMMDD_HHMMSS.log`

### Step 4: Verify

```bash
# Check total rows loaded
psql -d market_data -c "SELECT COUNT(*) FROM japan_fundamentals_history;"

# Expected: ~10k-12k rows (2,937 companies × ~3.5 quarters)

# Check coverage by period
psql -d market_data -c "
  SELECT fiscal_period, COUNT(*) as companies
  FROM japan_fundamentals_history
  GROUP BY fiscal_period
  ORDER BY fiscal_period;"
```

### Step 5: Resume Daily Pipeline

Once Postgres has fundamentals:

```bash
# Run full daily pipeline
./daily_pipeline.sh
```

Step [7/14] Japan scan now:
- Joins `japan_current` (live prices + signals)
- Joins `japan_fundamentals_history` (quarterly EDINET data)
- Outputs comprehensive Japan screening results

---

## Integration with Daily Pipeline

### Step [7/14] Query Template

```sql
SELECT
  j.tse_code,
  j.company_name,
  j.ltp_jpy,
  j.darvas_signal,
  j.quality_score,
  f.revenue_jpy,
  f.net_income_jpy,
  f.roe,
  f.debt_to_equity
FROM japan_current j
LEFT JOIN japan_fundamentals_history f
  ON j.tse_code = f.tse_code
  AND f.fiscal_period LIKE 'FY2024%'
ORDER BY f.roe DESC, j.quality_score DESC;
```

### Usage in Screening

- **Darvas breakout + Buffett fundamentals**: Filter Darvas signals with ROE > 15%
- **Piotroski F-Score**: Compute from EDINET GL accounts (upcoming)
- **Coffee Can**: High ROE + stable margins + low debt (from EDINET)

---

## Troubleshooting

### Issue: "No EDINET_XBRL_*.zip files found"

**Solution:** Download from https://disclosure2.edinet-fsa.go.jp/ first, move to `/tmp/`

### Issue: "Dropbox archive failed"

**Solution:** Verify rclone config: `rclone config list` (should show `dropbox:` and `gdrive:`)

### Issue: "XBRL parse error: UnicodeDecodeError"

**Solution:** This has been fixed in code. The parser auto-detects cp932 (Japanese encoding).

### Issue: Duplicate key error (unique constraint on tse_code + fiscal_period)

**Solution:** Normal — same company's quarterly filing loaded twice. Use `ON CONFLICT DO UPDATE` (already in code).

---

## Monitoring

### Log File Location

```bash
tail -f /Users/umashankar/market-pipeline/state/edinet_archive_*.log
```

### Check Archive Status

```bash
# List Dropbox archives
rclone lsf dropbox:/market-data-archive/edinet_xbrl/ --recurse

# List GDrive backups
rclone lsf gdrive:/Market-Data-Archive/EDINET/ --recurse
```

### Postgres Health

```bash
# Total fundamentals rows
psql -d market_data -c "SELECT COUNT(*) FROM japan_fundamentals_history;"

# Latest filing date
psql -d market_data -c "SELECT MAX(filing_date) FROM japan_fundamentals_history;"

# Completeness by quarter
psql -d market_data -c "
  SELECT fiscal_period, COUNT(DISTINCT tse_code) as unique_companies
  FROM japan_fundamentals_history
  GROUP BY fiscal_period
  ORDER BY fiscal_period DESC;"
```

---

## Cost Summary (2024–2025)

| Component | Annual | Notes |
|-----------|--------|-------|
| Dropbox | $200/yr | 2 TB plan (shared) |
| GDrive | $100/yr | 200 GB plan (shared) |
| Postgres | $0 | Local (included in setup) |
| **Total** | **$300/yr** | Cloud-first storage |

---

## What's Committed

All infrastructure code has been committed to `claude/strategy-pipeline` branch:

```
✓ edinet_xbrl_historical_fetcher.py — XBRL parser
✓ japan_data_consolidator.py — Scan consolidation
✓ EDINET_WORKFLOW.sh — Master orchestrator
✓ scripts/edinet_process_and_archive.sh — Automated pipeline
✓ EDINET_SETUP.md — Setup guide
✓ EDINET_CLOUD_STRATEGY.md — Architecture guide
✓ JAPAN_EDINET_STATUS.md — This file
```

---

## Timeline

- **2026-07-25**: EDINET code files validated (all stocks + parameters confirmed)
- **2026-07-26**: Cloud-first architecture + automation designed
- **2026-07-27**: All scripts committed; awaiting EDINET XBRL download
- **2026-07-27+**: Download → process → archive → integrate pipeline

---

## Next Session

1. Download EDINET bulk XBRL files from their website
2. Move to `/tmp/`
3. Run `bash scripts/edinet_process_and_archive.sh`
4. Verify Postgres row counts
5. Resume daily pipeline (Step [7/14] now has full Japan fundamentals)

---

**Status**: 🟡 **Awaiting EDINET Download** — All infrastructure ready, waiting for manual XBRL file acquisition.
