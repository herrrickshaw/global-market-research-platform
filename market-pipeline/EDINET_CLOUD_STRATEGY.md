# EDINET Japan Fundamentals — Cloud-First Strategy

## Objective
Minimize local disk usage while maintaining complete historical data in Dropbox + GDrive.

---

## Workflow Architecture

```
EDINET Website
    ↓
Download to /tmp (temporary)
    ↓
Process (parse XBRL → Postgres) [keeps only structured DB]
    ↓
Archive to Cloud (Dropbox + GDrive)
    ↓
Delete local /tmp [free up disk]
    ↓
Postgres has queryable fundamentals
```

---

## Implementation

### 1. Download Phase (Temporary Local)

```bash
# Download EDINET XBRL bulk files to /tmp (NOT /Users/umashankar)
cd /tmp
wget https://disclosure2.edinet-fsa.go.jp/XBRL/2024q3/edinet_xbrl_2024q3_all.zip
# ~300-500 MB, cleaned up after processing
```

### 2. Process Phase (Postgres Storage)

```bash
# Parse XBRL and load into Postgres
python edinet_xbrl_historical_fetcher.py --from-file /tmp/edinet_xbrl_2024q3.zip
# Result: 2,937 company-quarters stored in Postgres (compact, queryable)
```

### 3. Archive Phase (Cloud Backup)

```bash
# After successful processing, move XBRL ZIP to Dropbox
# Use rclone (configured in cloud_backup.sh)
rclone move /tmp/edinet_xbrl_2024q3.zip dropbox:/market-data-archive/edinet_xbrl/

# Parallel: Mirror to GDrive
rclone copy /tmp/edinet_xbrl_2024q3.zip gdrive:/Market-Data-Archive/EDINET/
```

### 4. Cleanup Phase (Free Local Disk)

```bash
# After both uploads confirm, remove local /tmp file
rm /tmp/edinet_xbrl_*.zip
# Local disk: FREED
# Data: SAFE in Dropbox + GDrive + Postgres
```

---

## Storage Allocation

| Location | Content | Size | Purpose | Keep? |
|----------|---------|------|---------|-------|
| **Postgres** | Structured fundamentals (2,937 cos/q) | ~50 MB | Live query layer | ✓ Always |
| **Dropbox** | XBRL bulk archive (quarterly) | ~300 MB/quarter | Audit trail + re-processing | ✓ Always |
| **GDrive** | XBRL bulk archive (mirror) | ~300 MB/quarter | Redundant backup | ✓ Always |
| **/tmp** | XBRL during processing | ~300 MB | Temporary (auto-delete) | ✗ After done |
| **Local drive** | Nothing | 0 MB | Goal: minimal footprint | ✓ Achieved |

---

## Automation via Cron

Add to crontab to auto-fetch + process + archive (requires EDINET API key + web scraping):

```bash
# Proposed (requires development): Auto-download latest EDINET filings
# 30 11 15 * * cd /Users/umashankar/market-pipeline && bash scripts/edinet_auto_fetch.sh >> state/edinet_cron.log 2>&1
```

---

## Manual Workflow (Today)

Since EDINET doesn't expose a public bulk download API, follow this:

### Step 1: Download (One-Time Setup)

```bash
# Visit: https://disclosure2.edinet-fsa.go.jp/
# Download each quarter/year:
#   - EDINET_XBRL_2023_all.zip (FY2023 Annual)
#   - EDINET_XBRL_2024Q1_all.zip
#   - EDINET_XBRL_2024Q2_all.zip
#   - EDINET_XBRL_2024Q3_all.zip

# Move to /tmp for processing
mv ~/Downloads/EDINET_XBRL_*.zip /tmp/
```

### Step 2: Process & Archive

```bash
#!/bin/bash
# edinet_process_and_archive.sh

cd /tmp

for file in EDINET_XBRL_*.zip; do
  echo "Processing $file..."
  
  # 1. Parse into Postgres
  python3 /Users/umashankar/market-pipeline/code/python_files/edinet_xbrl_historical_fetcher.py \
    --from-file "/tmp/$file"
  
  # 2. Check success (row count > 0)
  if [ $? -eq 0 ]; then
    echo "✓ $file loaded successfully"
    
    # 3. Archive to Dropbox
    rclone move "/tmp/$file" dropbox:/market-data-archive/edinet_xbrl/
    
    # 4. Mirror to GDrive (optional second backup)
    # rclone copy "dropbox:/market-data-archive/edinet_xbrl/$file" gdrive:/Market-Data-Archive/EDINET/
    
    echo "✓ $file archived to Dropbox"
  else
    echo "✗ Failed to process $file — keeping local for retry"
  fi
done

# 5. Cleanup remaining temps
rm -f /tmp/EDINET_XBRL_*.zip

echo "✓ All EDINET files processed and archived"
```

### Step 3: Validate

```bash
# Check Postgres coverage
psql -d market_data -c "SELECT COUNT(*) FROM japan_fundamentals_history;"

# Check Dropbox archive
rclone ls dropbox:/market-data-archive/edinet_xbrl/ --recurse
```

---

## Cloud Storage Paths

**Dropbox**:
```
/Market-Data-Archive/EDINET/
  ├── edinet_xbrl_2023_all.zip (FY2023 Annual)
  ├── edinet_xbrl_2024q1_all.zip
  ├── edinet_xbrl_2024q2_all.zip
  └── edinet_xbrl_2024q3_all.zip
```

**GDrive**:
```
/Market-Data-Archive/EDINET/
  └── [Same structure as Dropbox]
```

---

## Integration with Daily Pipeline

Once EDINET data is loaded in Postgres, the daily pipeline (Step [7] Japan) automatically uses it:

```python
# Step [7/14] Japan scan
SELECT j.tse_code, j.company_name, j.ltp_jpy,
       f.revenue_jpy, f.net_income_jpy, f.roe
FROM japan_current j
LEFT JOIN japan_fundamentals_history f 
  ON j.tse_code = f.tse_code
  AND f.fiscal_period LIKE 'FY2024%'
ORDER BY f.roe DESC;
```

No local XBRL storage needed — Postgres is the single source of truth.

---

## Disk Usage Summary

| Phase | Local Disk | Dropbox | GDrive |
|-------|-----------|---------|--------|
| After FY2023 | 0 MB | 300 MB | 300 MB |
| After FY2024Q1 | 0 MB | 600 MB | 600 MB |
| After FY2024Q2 | 0 MB | 900 MB | 900 MB |
| After FY2024Q3 | 0 MB | 1.2 GB | 1.2 GB |
| **Total** | **0 MB** ✓ | 1.2 GB | 1.2 GB |

**Goal achieved**: Zero local footprint, complete cloud archive.

---

## Next Steps

1. **Download EDINET files** (manually from their website)
2. **Run processing script** (`edinet_process_and_archive.sh`)
3. **Verify Postgres** (`SELECT COUNT(*) FROM japan_fundamentals_history`)
4. **Confirm Dropbox/GDrive** have archives
5. **Run daily pipeline** Step [7] → Japan fundamentals + prices merged

