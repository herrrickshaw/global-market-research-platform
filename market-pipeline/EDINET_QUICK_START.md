# Japan EDINET Infrastructure — Quick Start

**Status**: ✓ Infrastructure complete | ⏳ Awaiting EDINET files

---

## What's Ready

All Japan fundamentals infrastructure has been built and committed:

✓ **Postgres tables** → `japan_current` (2,937 TSE stocks) + `japan_fundamentals_history`  
✓ **XBRL parser** → `edinet_xbrl_historical_fetcher.py` (GL account extraction)  
✓ **Processing pipeline** → `scripts/edinet_process_and_archive.sh` (parse + archive)  
✓ **Cloud-first strategy** → Dropbox + GDrive archival + zero local disk  
✓ **Test data generator** → `create_test_edinet_xbrl.py` (validate pipeline)  
✓ **Documentation** → Setup guide, architecture, troubleshooting  

---

## Challenge Encountered

**Automated EDINET download doesn't work:**
- EDINET API returns 403 Forbidden (not public)
- Direct download URLs redirect to login pages
- Bulk files require session/browser authentication
- Website uses JavaScript rendering (not API-accessible)

**Solution**: Manual download + automated processing

---

## Path Forward

### Option A: Test Pipeline First (5 min)

Validate the full workflow with mock data:

```bash
cd /Users/umashankar/market-pipeline

# 1. Create sample XBRL ZIP (3 companies)
python3 scripts/create_test_edinet_xbrl.py --dest /tmp

# 2. Run the fetcher to parse into Postgres
python3 code/python_files/edinet_xbrl_historical_fetcher.py --from-file /tmp/EDINET_XBRL_2024Q3_TEST.zip

# 3. Verify in Postgres
psql -d market_data -c "SELECT COUNT(*) FROM japan_fundamentals_history;"
```

This validates the entire pipeline end-to-end without waiting for real files.

---

### Option B: Get Real EDINET Files (Manual)

1. **Visit EDINET website:**
   ```
   https://disclosure2.edinet-fsa.go.jp/
   ```

2. **Navigate to bulk download:**
   - Click "Download" / "XBRL Bulk Data"
   - Select period (FY2024 Q3, Q2, Q1 or FY2023 Annual)
   - Download ZIP (~300-500 MB each)

3. **Move to temp directory:**
   ```bash
   mv ~/Downloads/EDINET_XBRL_*.zip /tmp/
   ```

4. **Run automated processing:**
   ```bash
   bash /Users/umashankar/market-pipeline/scripts/edinet_process_and_archive.sh
   ```

   This will:
   - Parse each ZIP into Postgres
   - Archive to Dropbox + GDrive
   - Delete /tmp files (zero local disk)
   - Verify row counts

5. **Verify coverage:**
   ```bash
   psql -d market_data -c "
     SELECT fiscal_period, COUNT(*) as companies
     FROM japan_fundamentals_history
     GROUP BY fiscal_period;"
   ```

---

## File Inventory

| File | Purpose |
|------|---------|
| `EDINET_SETUP.md` | Step-by-step setup guide |
| `EDINET_CLOUD_STRATEGY.md` | Cloud-first architecture rationale |
| `JAPAN_EDINET_STATUS.md` | Current status + monitoring |
| `EDINET_WORKFLOW.sh` | Master orchestration script |
| `scripts/edinet_process_and_archive.sh` | Automated pipeline (parse + archive) |
| `scripts/create_test_edinet_xbrl.py` | Mock data generator |
| `code/python_files/edinet_xbrl_historical_fetcher.py` | XBRL → Postgres parser |
| `code/python_files/japan_data_consolidator.py` | Scan data consolidation |

---

## Integration with Daily Pipeline

Once EDINET data is loaded in Postgres, Step [7/14] Japan scan automatically uses it:

```bash
./daily_pipeline.sh
# Step [7/14] joins japan_current (live prices + signals)
#           with japan_fundamentals_history (quarterly EDINET)
#           outputs: Japan screening + fundamentals
```

---

## Disk Usage

| Component | After Processing |
|-----------|------------------|
| Local disk | 0 MB ✓ |
| Postgres | ~50 MB |
| Dropbox | ~1.2 GB/year |
| GDrive | ~1.2 GB/year |

---

## Next Steps

**Immediate (Test):**
```bash
python3 scripts/create_test_edinet_xbrl.py --dest /tmp
python3 code/python_files/edinet_xbrl_historical_fetcher.py --from-file /tmp/EDINET_XBRL_2024Q3_TEST.zip
```

**Real Data (After download):**
```bash
mv ~/Downloads/EDINET_XBRL_*.zip /tmp/
bash scripts/edinet_process_and_archive.sh
```

**Then resume:**
```bash
./daily_pipeline.sh  # Step [7/14] Japan now has full fundamentals
```

---

## Support Resources

- **EDINET Official**: https://disclosure2.edinet-fsa.go.jp/
- **EDINET Bulk Data**: https://disclosure2.edinet-fsa.go.jp/
- **XBRL Taxonomy**: https://xbrl.fsa.go.jp/ (Japanese)
- **Troubleshooting**: See `EDINET_SETUP.md`

---

**Last Updated**: 2026-07-27 | **Branch**: claude/strategy-pipeline
