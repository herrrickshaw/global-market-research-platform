# Japan Market Data — Consolidation Status

**Date**: 2026-07-27 · **Last Updated**: 09:30 JST

---

## Current Snapshot (Postgres: `japan_current`)

✓ **2,937 TSE Companies loaded**

| Metric | Count | Details |
|--------|-------|---------|
| Total Companies | 2,937 | All TSE Prime + Standard |
| With Current Prices | 2,937 | From yfinance, 27 Jul 2026 |
| Darvas Breakouts | 1,023 | Ready to break up (+34.8%) |
| In-Box Consolidation | 1,842 | Mid-formation (62.7%) |
| Breakdowns | 71 | Below box bottom (2.4%) |
| Insufficient Data | 1 | Will populate on next scan |

**Data Source**: yfinance real-time + Darvas Box + Quality Scores
**Scan Date**: 2026-07-27 09:30
**Coverage**: Prices, Darvas signals, EMA/DMA, turnover, liquidity tier

---

## Historical Fundamentals (Postgres: `japan_fundamentals_history`)

**Status**: Schema ready, awaiting EDINET bulk download

| Metric | Status | Plan |
|--------|--------|------|
| Revenue | 0 rows | EDINET FY2023–2024 |
| Net Income | 0 rows | EDINET quarterly filings |
| Assets / Debt | 0 rows | EDINET Q1–Q3 2024 |
| ROE / ROA | Computed | Derived from EDINET data |
| Historical Depth | 0 years | Target: 3–5 years (EDINET backfill) |

**Next Step**: Download EDINET bulk XBRL → Process with `edinet_xbrl_historical_fetcher.py` → Populate table

---

## Data Sources & Integration

### 1. Current Snapshot (Live)
- **Source**: yfinance (daily update)
- **Frequency**: On-demand via pipeline Step [7/14]
- **Coverage**: All 2,937 tickers
- **Latency**: ~15 min after market close
- **Table**: `japan_current`

### 2. EDINET Fundamentals (Quarterly)
- **Source**: EDINET bulk XBRL downloads
- **Frequency**: After EDINET filing (45–60 days post quarter-end)
- **Coverage**: 2,000–2,900 companies (most file quarterly)
- **Latency**: 1–2 quarters
- **Table**: `japan_fundamentals_history`

### 3. Correlation Matrix
- **Location**: `/correlation_scan/japan_correlation_matrix.parquet`
- **Updated**: 2026-07-24
- **Use**: Sector rotation, pair trading

---

## Usage Examples

### Get top Darvas breakouts by quality:
```sql
SELECT tse_code, company_name, ltp_jpy, upside_to_top_pct, quality_score
FROM japan_current
WHERE darvas_signal = 'BREAKOUT_BUY'
AND quality_score > 70
ORDER BY upside_to_top_pct DESC
LIMIT 20;
```

### Join with fundamentals once EDINET is loaded:
```sql
SELECT 
  j.tse_code, j.company_name,
  j.ltp_jpy, j.quality_score,
  f.revenue_jpy, f.net_income_jpy, f.roe, f.fiscal_period
FROM japan_current j
LEFT JOIN japan_fundamentals_history f 
  ON j.tse_code = f.tse_code 
  AND f.fiscal_period LIKE 'FY2024%'
WHERE j.darvas_signal = 'BREAKOUT_BUY'
AND f.roe > 0.10
ORDER BY f.roe DESC;
```

---

## Next Steps

1. **Download EDINET bulk XBRL** (FY2023 Annual, FY2024 Q1–Q3)
   - Source: https://disclosure2.edinet-fsa.go.jp/
   - Expected size: ~400 MB total

2. **Process XBRL into Postgres**
   ```bash
   python edinet_xbrl_historical_fetcher.py --from-file data/edinet_xbrl_2024q3.zip
   ```

3. **Backfill 3–5 years** (repeat for each quarter/year)

4. **Integrate into daily pipeline** Step [7/14] 
   - Merge `japan_current` + `japan_fundamentals_history`
   - Compute Piotroski F-Score, Coffee Can, liquidity gates
   - Output: Screened Japan picks for daily brief

---

## Postgres Schema

### japan_current
- **Columns**: 24
- **Rows**: 2,937
- **Primary Key**: `tse_code` (UNIQUE)
- **Indexes**: code, signal, updated_at
- **Freshness**: Updated on each scan (Step [7/14])

### japan_fundamentals_history
- **Columns**: 31
- **Rows**: 0 (awaiting EDINET)
- **Primary Key**: `(tse_code, fiscal_period)` (UNIQUE)
- **Indexes**: code, period
- **Freshness**: Quarterly (45–60d lag from quarter-end)

---

## Credentials & Access

- **EDINET API Key**: `~/.config/market-secrets/credentials.env` → `EDINET_API_KEY`
- **Postgres**: `psql -d market_data`
- **Scripts**: `/market-pipeline/code/python_files/`
  - `japan_data_consolidator.py` — Load scans into `japan_current`
  - `edinet_xbrl_historical_fetcher.py` — Parse XBRL into `japan_fundamentals_history`
  - `full_japan_market_scan.py` — Daily scanner (Step [7/14])

---

## Troubleshooting

**Q: Why no fundamentals for 200+ companies in latest scan?**
A: yfinance returns limited fundamentals. EDINET will provide comprehensive quarterly statements for all 2,937 tickers.

**Q: When is EDINET data available?**
A: ~45–60 days after quarter-end. Q3 (Sep 30) filings typically arrive by Nov 15.

**Q: Can I use older EDINET data?**
A: Yes — download FY2023 Annual + FY2024 Q1–Q3 at once to backfill 18 months of history.

**Q: How do I refresh `japan_current`?**
A: Run pipeline Step [7/14] or manually: `python full_japan_market_scan.py && python japan_data_consolidator.py --load-scan`

