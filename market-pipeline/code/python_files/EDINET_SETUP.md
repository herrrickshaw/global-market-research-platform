# EDINET Japan Historical Fundamentals — Setup & Usage

## Overview

This pipeline fetches **historical financial data for all Japan (TSE) companies** from EDINET (Electronic Disclosure for Investors' Network), Japan's official corporate disclosure system. Stores in Postgres for use in screening and analysis.

---

## Step 1: Obtain EDINET Bulk XBRL Files

EDINET publishes filings in **XBRL format** (eXtensible Business Reporting Language), a standardized financial reporting format. Bulk files are available as ZIP archives.

### Option A: Download from EDINET Official Site

1. Visit: **https://disclosure2.edinet-fsa.go.jp/**
2. Navigate to **Download** → **XBRL Bulk Data**
3. Select fiscal year and quarter (e.g., FY2024 Q3, FY2023 Annual)
4. Download ZIP file (typically 100–500 MB per quarter)

Example filenames:
```
edinet_xbrl_2024q3_tse.zip
edinet_xbrl_2023_annual.zip
```

### Option B: Use EDINET API with Session Handling

EDINET has an API, but it requires session cookies. For production use, consider:
- **Web scraping** with Selenium (headless browser)
- **Direct file download** from EDINET's archive
- **Historical archive** (if available on data.go.jp or academic sources)

### Option C: Test with Sample Data

For now, test the parser with a sample XBRL file:
```bash
# Create a mock XBRL for testing (see SAMPLE_XBRL below)
cat > sample_8001_q3.xbrl << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<xbrl xmlns:jppfs="http://disclosure.edinet-fsa.go.jp/jppfs/...">
  <jppfs:RevenueJFY>1234567890</jppfs:RevenueJFY>
  <jppfs:NetIncomeJFY>123456789</jppfs:NetIncomeJFY>
  <!-- ... more GL accounts ... -->
</xbrl>
EOF
```

---

## Step 2: Prepare EDINET Data for Processing

### Create test XBRL ZIP archive:

```bash
cd /tmp
mkdir edinet_test
cd edinet_test

# Add sample XBRL files (one per company-quarter)
# Naming convention: XXXXXXXX_jp_FY2024Q3_tse-xxx_DATE_01.xbrl
cp sample_8001_q3.xbrl 8001_jp_FY2024Q3_tse-acedjpfr_2024-09-30_01.xbrl

# Create ZIP
zip -r edinet_xbrl_2024q3.zip *.xbrl
mv edinet_xbrl_2024q3.zip /Users/umashankar/market-pipeline/data/

cd /Users/umashankar/market-pipeline
```

---

## Step 3: Run the EDINET Fetcher

### Validate Postgres schema:
```bash
python3 code/python_files/edinet_xbrl_historical_fetcher.py --validate
```

Expected output:
```
Japan fundamentals tables in Postgres:
  (none yet — will be created on first insert)
```

### Process a bulk XBRL ZIP file:

```bash
python3 code/python_files/edinet_xbrl_historical_fetcher.py \
  --from-file data/edinet_xbrl_2024q3.zip
```

Output:
```
======================================================================
EDINET XBRL Historical Fundamentals Fetcher
======================================================================

Processing XBRL archive: data/edinet_xbrl_2024q3.zip
  Found 2368 XBRL files
  [100/2368] [200/2368] ... [2368/2368]
  Processed 2368 companies

✓ Stored 2368 rows in japan_fundamentals_history
```

### Export to CSV:

```bash
python3 code/python_files/edinet_xbrl_historical_fetcher.py \
  --from-file data/edinet_xbrl_2024q3.zip \
  --output /tmp/japan_fund_2024q3.csv
```

### Backfill historical data (multiple years):

```bash
# Download FY2023 Annual
python3 code/python_files/edinet_xbrl_historical_fetcher.py \
  --from-file data/edinet_xbrl_2023_annual.zip

# Download FY2024 Q1, Q2, Q3
python3 code/python_files/edinet_xbrl_historical_fetcher.py \
  --from-file data/edinet_xbrl_2024q1.zip

# ... repeat for Q2, Q3, etc.
```

---

## Step 4: Verify Data in Postgres

```bash
psql -d market_data -c "
SELECT tse_code, fiscal_period, revenue, net_income, total_assets
FROM japan_fundamentals_history
ORDER BY tse_code, fiscal_period DESC
LIMIT 20;
"
```

---

## Integration with Pipeline

Once historical data is loaded, it's automatically used by:

### 1. **Japan Scanner** (`full_japan_market_scan.py`)
   - Joins XBRL fundamentals with yfinance prices
   - Computes Piotroski F-Score, Coffee Can, ROE/ROA screens

### 2. **Daily Pipeline** (`daily_pipeline.sh` Step [7/14])
   - Step [7] runs full Japan scan + fundamentals
   - Uses `japan_fundamentals_history` for latest quarterly data

### 3. **Screening Logic**
   ```python
   # Example: Nifty Japan candidates (Piotroski 8+, ROE 15%+)
   SELECT j.tse_code, j.fiscal_period, j.net_income, j.total_equity,
          (j.net_income::FLOAT / j.total_equity::FLOAT) as roe
   FROM japan_fundamentals_history j
   WHERE j.fiscal_period LIKE 'FY2024%'
   AND j.net_income > 0
   AND (j.net_income::FLOAT / j.total_equity::FLOAT) > 0.15
   ORDER BY roe DESC;
   ```

---

## Postgres Schema

```sql
CREATE TABLE japan_fundamentals_history (
  id SERIAL PRIMARY KEY,
  tse_code VARCHAR(6),
  fiscal_period VARCHAR(20),  -- 'FY2024Q3', 'FY2023', etc.
  filing_date DATE,
  revenue BIGINT,             -- JPY
  operating_income BIGINT,
  net_income BIGINT,
  total_assets BIGINT,
  total_liabilities BIGINT,
  shareholders_equity BIGINT,
  operating_cash_flow BIGINT,
  free_cash_flow BIGINT,
  roe NUMERIC,                -- Return on Equity (%)
  roa NUMERIC,                -- Return on Assets (%)
  created_at TIMESTAMP,
  UNIQUE(tse_code, fiscal_period),
  INDEX idx_japan_hist_code (tse_code),
  INDEX idx_japan_hist_period (fiscal_period)
);
```

---

## XBRL GL Account Reference

### Income Statement
| Metric | Japanese GL Account |
|--------|-------------------|
| Revenue | `jpfr:NetSalesJFY` or `jpfr-asr:OperatingRevenueJFY` |
| Operating Income | `jpfr:OperatingIncomeJFY` |
| Net Income | `jpfr:NetIncomeJFY` or `jppfs:NetIncomeJFY` |

### Balance Sheet
| Metric | Japanese GL Account |
|--------|-------------------|
| Total Assets | `jppfs:TotalAssetsJFY` |
| Total Liabilities | `jppfs:TotalLiabilitiesJFY` |
| Shareholders' Equity | `jppfs:ShareholdersEquityJFY` |

### Cash Flow
| Metric | Japanese GL Account |
|--------|-------------------|
| Operating CF | `jpfr:OperatingCashFlowJFY` |
| Free CF | `jpfr:FreeCashFlowJFY` |

---

## Troubleshooting

### Issue: "No filings fetched from API"
**Solution**: Download bulk XBRL ZIP from EDINET directly (Step 1), then use `--from-file`.

### Issue: "XBRL parse error"
**Solution**: Verify ZIP contains valid `.xbrl` files. Check file encoding (should be UTF-8).

### Issue: Duplicate key error in Postgres
**Solution**: XBRL files with same `(tse_code, fiscal_period)` are merged. This is expected.

### Issue: Missing GL accounts in XBRL
**Solution**: Not all companies report all metrics (e.g., some don't report FCF). Nulls are expected.

---

## Next Steps

1. **Download EDINET bulk XBRL for 2023–2024** (all quarters)
2. **Process into Postgres** using this fetcher
3. **Backfill 3–5 years** for historical analysis
4. **Integrate into Japan screening logic** (Piotroski, Coffee Can, ROE filters)
5. **Run daily pipeline** Step [7/14] to refresh with latest EDINET filings

---

## Resources

- **EDINET Official**: https://disclosure2.edinet-fsa.go.jp/
- **XBRL Taxonomy (Japan)**: https://xbrl.fsa.go.jp/ (Japanese only)
- **XBRL Standard**: http://www.xbrl.org/
- **Credentials**: `EDINET_API_KEY` in `~/.config/market-secrets/credentials.env`

