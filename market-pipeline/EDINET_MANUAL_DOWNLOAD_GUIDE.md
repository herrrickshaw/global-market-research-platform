# EDINET Manual Download — Step-by-Step Guide

Complete walkthrough for downloading Japan XBRL files and loading into Postgres.

---

## Step 1: Open EDINET Website

**Action:** Open your browser and navigate to:
```
https://disclosure2.edinet-fsa.go.jp/
```

**You should see:**
- Japanese website with navigation menu
- "Download" or "ダウンロード" link at the top

---

## Step 2: Find the Download Section

**Action:** Look for and click the download option. The exact path may vary, but typically:
- Click "Download" (top menu)
- OR Look for "XBRL Bulk Data" / "XBRLデータ"
- OR Search for "FY2024" or "2024年度"

**Expected:** You should see a page with options to select:
- Fiscal year/period dropdown
- File format (XBRL should be available)
- Download button

---

## Step 3: Download FY2023 Annual (First Period)

**Action:**
1. Select period: **FY2023 Annual** (2023年度通年 or 2023-04-01 to 2024-03-31)
2. Select format: **XBRL** (if options appear)
3. Click **Download**

**What to expect:**
- Browser downloads `EDINET_XBRL_2023_all.zip` or similar (~500 MB)
- File goes to `~/Downloads/` by default
- Wait for download to complete (10-30 min depending on speed)

**Verify:** Open Terminal and check:
```bash
ls -lh ~/Downloads/EDINET_XBRL_*.zip
```

Should see: `-rw-r--r-- ... EDINET_XBRL_2023_all.zip (500 MB)`

---

## Step 4: Download FY2024 Q1

**Action:** Repeat Step 3 for the next period:
1. Select period: **FY2024 Q1** (2024年度第1四半期 or 2024-04-01 to 2024-06-30)
2. Select format: **XBRL**
3. Click **Download**

**Wait for completion** (10-30 min)

**Verify:**
```bash
ls -lh ~/Downloads/EDINET_XBRL_2024Q1*.zip
```

---

## Step 5: Download FY2024 Q2

**Action:** Repeat Step 3 for Q2:
1. Select period: **FY2024 Q2** (2024年度第2四半期 or 2024-07-01 to 2024-09-30)
2. Select format: **XBRL**
3. Click **Download**

**Wait for completion** (10-30 min)

**Verify:**
```bash
ls -lh ~/Downloads/EDINET_XBRL_2024Q2*.zip
```

---

## Step 6: Download FY2024 Q3 (Latest)

**Action:** Repeat Step 3 for Q3:
1. Select period: **FY2024 Q3** (2024年度第3四半期 or 2024-10-01 to 2024-12-31)
2. Select format: **XBRL**
3. Click **Download**

**Wait for completion** (10-30 min)

**Verify:**
```bash
ls -lh ~/Downloads/EDINET_XBRL_2024Q3*.zip
```

---

## Step 7: Verify All 4 Files Downloaded

**Action:** Check that all files are in Downloads:

```bash
ls -lh ~/Downloads/EDINET_XBRL_*.zip
```

**Expected output:**
```
-rw-r--r-- ... 500M ... EDINET_XBRL_2023_all.zip
-rw-r--r-- ... 500M ... EDINET_XBRL_2024Q1_all.zip
-rw-r--r-- ... 500M ... EDINET_XBRL_2024Q2_all.zip
-rw-r--r-- ... 500M ... EDINET_XBRL_2024Q3_all.zip
```

**Total size:** ~2 GB

If any file is missing or small (<100 MB), re-download it (Step 3-6).

---

## Step 8: Move Files to Processing Directory

**Action:** Move all ZIPs to `/tmp/` for processing:

```bash
mv ~/Downloads/EDINET_XBRL_*.zip /tmp/
```

**Verify:**
```bash
ls -lh /tmp/EDINET_XBRL_*.zip
```

Should show all 4 files in `/tmp/`.

---

## Step 9: Process Files into Postgres

**Action:** Run the batch processor:

```bash
cd /Users/umashankar/market-pipeline
python3 scripts/edinet_batch_process.py --src /tmp
```

**What happens:**
1. Scanner finds all `.zip` files in `/tmp/`
2. For each ZIP:
   - Extracts XBRL files
   - Parses financial metrics (revenue, net income, assets, etc.)
   - Loads into Postgres table `japan_fundamentals_history`
3. Progress bar shows: `[1/4]`, `[2/4]`, etc.

**Expected output:**
```
======================================================================
EDINET Batch XBRL Processor
======================================================================

[INFO] Scanning /tmp for *.zip...
✓ Found 4 files

[INFO] Processing 4 XBRL files...

  [1/4] EDINET_XBRL_2023_all.zip
    ✓ Extracted 2937 company-quarters
    
  [2/4] EDINET_XBRL_2024Q1_all.zip
    ✓ Extracted 2937 company-quarters
    
  [3/4] EDINET_XBRL_2024Q2_all.zip
    ✓ Extracted 2937 company-quarters
    
  [4/4] EDINET_XBRL_2024Q3_all.zip
    ✓ Extracted 2937 company-quarters

======================================================================
Processing complete: 11748 rows loaded to Postgres
======================================================================
```

**Time:** ~5-10 minutes total

---

## Step 10: Verify Data in Postgres

**Action:** Query Postgres to confirm all data loaded:

```bash
psql -d market_data -c "
  SELECT fiscal_period, COUNT(*) as companies
  FROM japan_fundamentals_history
  GROUP BY fiscal_period
  ORDER BY fiscal_period;"
```

**Expected output:**
```
 fiscal_period | companies
---------------+-----------
 FY2023        |      2937
 FY2024Q1      |      2937
 FY2024Q2      |      2937
 FY2024Q3      |      2937
(4 rows)
```

**If rows are 0:** Something went wrong in Step 9. Check error messages.

**If rows differ from 2937:** Some companies may not have filed for that period (expected).

---

## Step 11: Archive to Cloud (Optional)

**Action:** Move processed ZIPs to Dropbox for backup:

```bash
rclone move /tmp/EDINET_XBRL_*.zip dropbox:/market-data-archive/edinet_xbrl/
```

**Verify:**
```bash
rclone lsf dropbox:/market-data-archive/edinet_xbrl/ --recurse
```

Should show all 4 files in Dropbox.

---

## Step 12: Clean Up Local Disk

**Action:** Remove any remaining temp files:

```bash
rm -f /tmp/EDINET_XBRL_*.zip
ls -lh /tmp/EDINET_XBRL_* 2>&1 | head -3
```

**Expected:** No files found (or just unrelated files)

---

## Step 13: Resume Daily Pipeline

**Action:** Now that Japan fundamentals are loaded, run the full daily pipeline:

```bash
cd /Users/umashankar/market-pipeline
./daily_pipeline.sh
```

**What happens:**
- Step [1/14] to Step [6/14]: India, US, Europe, Korea data
- **Step [7/14]: Japan scan now includes fundamentals** (from EDINET)
- Step [8/14] to Step [14/14]: Reports and cleanup

**Time:** ~30-60 minutes (depends on network)

---

## Troubleshooting

### Issue: Downloads fail or files are small (<100 MB)

**Solution:**
1. Check your internet connection
2. Manually visit https://disclosure2.edinet-fsa.go.jp/ in browser
3. Try downloading one file via browser (to confirm site is working)
4. Re-run Step 3-6

### Issue: Postgres shows 0 rows after processing

**Solution:**
1. Check for errors in Step 9 output
2. Verify files are valid ZIPs:
   ```bash
   unzip -l /tmp/EDINET_XBRL_2023_all.zip | head -5
   ```
   Should show XBRL filenames (not errors)
3. Check Postgres connection:
   ```bash
   psql -d market_data -c "SELECT count(*) FROM japan_current;"
   ```

### Issue: Processing takes too long

**Normal:** Each period (~2,937 files) takes 2-3 minutes.
- Total 4 periods = ~10 minutes expected
- If taking >30 minutes, something may be stuck

**Restart:** Press `Ctrl+C` to stop, then re-run Step 9

### Issue: "rclone: command not found"

**Solution:** Skip Step 11 (cloud archival) — it's optional
- OR Install rclone: `brew install rclone` (macOS)

---

## Success Indicators

✓ All 4 periods downloaded (~2 GB total)
✓ All files moved to `/tmp/`
✓ Batch processor completed without errors
✓ Postgres shows ~11,748 rows (2,937 × 4 periods)
✓ Daily pipeline Step [7/14] includes Japan fundamentals

---

## Next Steps

1. **Daily reports:** View Japan results in daily pipeline output
2. **Queries:** See `JAPAN_DATA_STATUS.md` for SQL examples
3. **Monitoring:** Check `state/edinet_archive_*.log` for processing history

---

**Questions?** Refer to:
- `EDINET_SETUP.md` — Technical details
- `EDINET_CLOUD_STRATEGY.md` — Cloud storage architecture
- `JAPAN_EDINET_STATUS.md` — Current system status
