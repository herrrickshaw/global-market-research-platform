# Expanded Fundamentals Schema - 20 Columns (All Markets)

## New Coverage Target: 100% of all 25,335 tickers

**Principle:** Every symbol receives ALL 20 canonical columns. Missing data → fallback chain → quality_score proxy (never NULL).

---

## Canonical 20-Column Structure

### CORE VALUATION (4)
```
pe              DOUBLE    -- Price-to-Earnings ratio
pb              DOUBLE    -- Price-to-Book ratio
ps              DOUBLE    -- Price-to-Sales ratio
dividend_yield  DOUBLE    -- Annual dividend as % of price
```

### CORE PROFITABILITY (4)
```
roe             DOUBLE    -- Return on Equity (%)
roa             DOUBLE    -- Return on Assets (%)
opm             DOUBLE    -- Operating Profit Margin (%)
npm             DOUBLE    -- Net Profit Margin (%)
```

### CORE EFFICIENCY (3)
```
roce            DOUBLE    -- Return on Capital Employed (%)
roc             DOUBLE    -- Return on Capital (%)
asset_turnover  DOUBLE    -- Revenue / Total Assets
```

### GROWTH METRICS (2)
```
revenue_growth  DOUBLE    -- YoY Revenue Growth (%)
eps_growth      DOUBLE    -- YoY EPS Growth (%)
```

### FINANCIAL HEALTH (3)
```
debt_to_equity  DOUBLE    -- Total Debt / Equity
current_ratio   DOUBLE    -- Current Assets / Current Liabilities
interest_cov    DOUBLE    -- EBIT / Interest Expense
```

### CAPITAL STRUCTURE (2)
```
market_cap      BIGINT    -- Market Capitalization (USD millions)
enterprise_val  BIGINT    -- Market Cap + Debt - Cash (USD millions)
```

### COMPOSITE QUALITY (2)
```
quality_score   INT       -- Liquidity/Exchange quality (0-100, NEVER NULL)
piotroski       DOUBLE    -- F-Score (0-100, normalized)
```

### METADATA (1)
```
fundamentals_source TEXT  -- 'alphavantage|eodhd|screener|jquants|dart|eastmoney'
```

---

## Collection Strategy by Market

### US (9,278 symbols)
**Primary:** AlphaVantage (5 calls/min)  
**Fallback:** EODHD (2 calls/sec)

| Column | Source | Method |
|--------|--------|--------|
| pe, pb | AlphaVantage OVERVIEW | Direct |
| ps, dividend_yield | EODHD Fundamentals | Direct |
| roe, roa, opm, npm | EODHD Income Statement + Balance Sheet | Direct |
| roce, roc, asset_turnover | EODHD (calculated) | Derived |
| revenue_growth, eps_growth | EODHD (historical YoY) | Calculated |
| debt_to_equity, current_ratio, interest_cov | EODHD Balance Sheet | Direct |
| market_cap, enterprise_val | EODHD Valuation | Direct |
| quality_score | Volume-based proxy | (0-100, NO NULL) |
| piotroski | sweep_piotroski_plus_us.csv | Normalized |
| fundamentals_source | Mixed | 'alphavantage' or 'eodhd' |

**Fallback Chain:**
1. AlphaVantage for (PE, PB) + EODHD for rest
2. If AlphaVantage fails → EODHD only (covers all except Piotroski)
3. If both fail → quality_score only (liquidity proxy)
4. Target: 90%+ PE/PB, 85%+ complete rows, 100% quality_score

---

### India (3,480 symbols)
**Primary:** screener.in, IN_screener_only_backup.parquet  
**Status:** 100% ROE already loaded

| Column | Source | Method |
|--------|--------|--------|
| pe, pb, ps | screener.in API | Direct (annual basis) |
| dividend_yield | screener.in | Annual dividend / Price |
| roe, npm | IN_screener_only_backup.parquet | Direct |
| roa, opm, roce, roc | india_factor_panel.parquet | Derived |
| asset_turnover | Calculated from revenue/assets | Derived |
| revenue_growth, eps_growth | screener.in (10-year history) | YoY calculation |
| debt_to_equity | screener.in balance sheet | Direct |
| current_ratio, interest_cov | screener.in financials | Derived |
| market_cap, enterprise_val | screener.in (nse_deep volume data) | Direct |
| quality_score | nse_deep.parquet volume | (0-100) |
| piotroski | piotroski_plus_india.csv | Normalized to 0-100 |
| fundamentals_source | Mixed | 'screener' or 'parquet' |

**Fallback Chain:**
1. screener.in for all metrics
2. If screener down → India parquet files (ROACE, factor panel)
3. If both fail → quality_score (volume-based, 0-100)
4. Target: 100% coverage (already 3,480/3,480 ROE; extend to all 20 cols)

---

### Europe (1,709 symbols)
**Primary:** EODHD (all 17 exchanges)  
**Quality Tiers:** LSE=80, Frankfurt=75, Euronext=75, Others=65

| Column | Source | Method |
|--------|--------|--------|
| pe, pb, ps | EODHD Fundamentals | Direct (12-month trailing) |
| dividend_yield | EODHD Valuation | Direct |
| roe, roa, opm, npm | EODHD Income Statement + Balance Sheet | Direct |
| roce, roc, asset_turnover | EODHD (calculated) | Derived from financials |
| revenue_growth, eps_growth | EODHD (YoY from historical) | 5-year trend |
| debt_to_equity, current_ratio | EODHD Balance Sheet | Direct |
| interest_cov | EBIT / Interest Expense | Calculated |
| market_cap, enterprise_val | EODHD Valuation | Direct |
| quality_score | Exchange tier + volume | LSE=80, Frankfurt=75, etc. |
| piotroski | Quality score mapped to F-Score | Composite |
| fundamentals_source | eodhd | 'eodhd' |

**Fallback Chain:**
1. EODHD for all 20 columns
2. If EODHD fails → quality_score (exchange-tier based, never NULL)
3. Target: 90%+ PE, 85%+ complete rows, 100% quality_score

---

### Japan (3,083 symbols)
**Primary:** EODHD  
**Secondary:** J-Quants, EDINET (fiscal year end = March 31)

| Column | Source | Method |
|--------|--------|--------|
| pe, pb, ps | EODHD Fundamentals | Direct (annual, not TTM) |
| dividend_yield | EODHD Valuation | Direct |
| roe | EDINET Filings (fiscal year basis) | Direct or EODHD fallback |
| roa, opm, npm | EODHD Income Statement | Direct |
| roce, roc | EDINET or derived from financials | Calculated |
| asset_turnover | EODHD (Revenue / Assets) | Direct |
| revenue_growth, eps_growth | EODHD (YoY historical) | 5-year trend |
| debt_to_equity, current_ratio, interest_cov | EODHD Balance Sheet | Direct |
| market_cap, enterprise_val | EODHD Valuation | Direct |
| quality_score | TSE volume rank | (0-100) |
| piotroski | Quality score mapped | Composite |
| fundamentals_source | Mixed | 'eodhd' or 'jquants' |

**Fallback Chain:**
1. EODHD for all metrics
2. J-Quants for enhanced ROA/ROCE (optional depth)
3. EDINET for ROE (if EODHD fails; 100/day rate limit)
4. If all fail → quality_score (TSE volume tier, never NULL)
5. Target: 85%+ PE, 75%+ complete rows, 100% quality_score

---

### Korea (2,597 symbols)
**Primary:** EODHD  
**Secondary:** DART (Korean exchange filings)

| Column | Source | Method |
|--------|--------|--------|
| pe, pb, ps | EODHD Fundamentals | Direct (annual) |
| dividend_yield | EODHD Valuation | Direct |
| roe | DART or EODHD | Corporate filing basis |
| roa, opm, npm | EODHD Income Statement | Direct |
| roce, roc | EODHD or derived | Calculated |
| asset_turnover | EODHD (Revenue / Assets) | Direct |
| revenue_growth, eps_growth | EODHD (YoY historical) | 5-year trend |
| debt_to_equity, current_ratio, interest_cov | EODHD Balance Sheet | Direct |
| market_cap, enterprise_val | EODHD Valuation | Direct |
| quality_score | KRX volume rank | (0-100) |
| piotroski | Quality score mapped | Composite |
| fundamentals_source | Mixed | 'eodhd' or 'dart' |

**Fallback Chain:**
1. EODHD for all metrics
2. DART for corporate filings (ROE, debt ratios)
3. If both fail → quality_score (KRX volume tier, never NULL)
4. Target: 85%+ PE, 80%+ complete rows, 100% quality_score

---

### China (5,188 symbols)
**Primary:** EODHD  
**Secondary:** Eastmoney (for A-shares standardization)  
**Note:** Use RMB → USD conversion (period-average FX rates)

| Column | Source | Method |
|--------|--------|--------|
| pe, pb, ps | EODHD Fundamentals | Direct (annual, CNY) |
| dividend_yield | EODHD Valuation | Direct |
| roe, roa, opm, npm | Eastmoney or EODHD | Annual basis |
| roce, roc, asset_turnover | EODHD (calculated) | Derived |
| revenue_growth, eps_growth | EODHD (YoY historical) | 5-year trend |
| debt_to_equity, current_ratio, interest_cov | EODHD Balance Sheet | Direct |
| market_cap, enterprise_val | EODHD Valuation (CNY→USD) | Direct |
| quality_score | SSE/SZSE volume rank | (0-100) |
| piotroski | Quality score mapped | Composite |
| fundamentals_source | Mixed | 'eodhd' or 'eastmoney' |

**Fallback Chain:**
1. EODHD for all metrics (most standardized)
2. Eastmoney for A-shares supplementation
3. If both fail → quality_score (SSE/SZSE volume tier, never NULL)
4. Target: 80%+ PE, 75%+ complete rows, 100% quality_score

---

## 100% Coverage Guarantee

### Quality Score Fallback (Never NULL)

**Volume-Based Proxy (0-100):**
```
quality_score = (volume_percentile × 0.6) + (exchange_tier × 0.4)

Exchange Tiers:
  LSE (UK):           80
  Frankfurt (DE):     75
  Euronext (EU):      75
  Nasdaq Nordic:      70
  US/India/JP/KR:     65
  China SSE/SZSE:     60
  Others:             50
```

**Calculation per market:**
- Rank all symbols in market by 20-day avg volume
- Assign 0-100 based on percentile (top 10% = 100, bottom 10% = 10)
- Apply exchange tier weighting (if applicable)
- Result: NEVER NULL; all 25,335 tickers receive 1-100 score

---

## CQL Schema Update

```sql
ALTER TABLE herrrickshaw.stock_quotes ADD dividend_yield DOUBLE;
ALTER TABLE herrrickshaw.stock_quotes ADD asset_turnover DOUBLE;
ALTER TABLE herrrickshaw.stock_quotes ADD revenue_growth DOUBLE;
ALTER TABLE herrrickshaw.stock_quotes ADD eps_growth DOUBLE;
ALTER TABLE herrrickshaw.stock_quotes ADD debt_to_equity DOUBLE;
ALTER TABLE herrrickshaw.stock_quotes ADD current_ratio DOUBLE;
ALTER TABLE herrrickshaw.stock_quotes ADD interest_cov DOUBLE;
ALTER TABLE herrrickshaw.stock_quotes ADD market_cap BIGINT;
ALTER TABLE herrrickshaw.stock_quotes ADD enterprise_val BIGINT;
```

---

## Collection Timeline (EC2 t3.micro, Parallel)

| Phase | Market | Symbols | Duration | Workers | Rate Limit |
|-------|--------|---------|----------|---------|-----------|
| 1 | US | 9,278 | 4-6h | 3 | 5/min (AV) |
| 2 | Europe | 1,709 | 2h | 4 | 2/sec (EODHD) |
| 3 | Japan | 3,083 | 3h | 4 | 2/sec (EODHD) |
| 4 | Korea | 2,597 | 2h | 4 | 2/sec (EODHD) |
| 5 | China | 5,188 | 3h | 4 | 2/sec (EODHD) |
| 6 | India | 3,480 | 0.5h | 1 | 3/sec (screener) |
| **TOTAL** | **25,335** | **6-8h parallel** | **14 total** | — |

---

## Success Criteria: 100% Coverage

| Metric | Target | Why |
|--------|--------|-----|
| quality_score populated | 25,335 / 25,335 (100%) | Volume proxy always available |
| PE ratio | 23,000+ / 25,335 (90%+) | Most symbols have market prices |
| Complete rows (all 20 cols) | 22,000+ / 25,335 (87%+) | API coverage + fallbacks |
| Major metrics (PE, ROE, margins) | 24,000+ / 25,335 (95%+) | Core fundamentals across all APIs |

---

## CQL Generation Strategy

**Update statement format (20 columns):**
```sql
UPDATE herrrickshaw.stock_quotes SET 
  pe = 25.5,
  pb = 3.2,
  ps = 8.5,
  dividend_yield = 2.1,
  roe = 18.5,
  roa = 8.2,
  opm = 22.3,
  npm = 14.5,
  roce = 16.8,
  roc = 15.2,
  asset_turnover = 1.8,
  revenue_growth = 12.3,
  eps_growth = 8.5,
  debt_to_equity = 0.45,
  current_ratio = 2.1,
  interest_cov = 5.2,
  market_cap = 450000,
  enterprise_val = 425000,
  quality_score = 75,
  piotroski = 72,
  fundamentals_source = 'eodhd',
  fundamentals_date = toTimestamp(now())
WHERE market = 'europe' AND yf_ticker = 'SAP.DE';
```

**Output files:**
- `FUNDAMENTALS_EXPANDED_US_*.cql` (9,278 updates)
- `FUNDAMENTALS_EXPANDED_EUROPE_*.cql` (1,709 updates)
- `FUNDAMENTALS_EXPANDED_JAPAN_*.cql` (3,083 updates)
- `FUNDAMENTALS_EXPANDED_KOREA_*.cql` (2,597 updates)
- `FUNDAMENTALS_EXPANDED_CHINA_*.cql` (5,188 updates)
- `FUNDAMENTALS_EXPANDED_INDIA_*.cql` (3,480 updates)

---

## Validation Queries (Post-Load)

```sql
-- Check 100% quality_score coverage
SELECT market, COUNT(*) as total, COUNT(quality_score) as with_quality
FROM herrrickshaw.stock_quotes
GROUP BY market;
-- Expected: all counts match total

-- Check core fundamentals coverage per market
SELECT market, COUNT(pe) as with_pe, COUNT(roe) as with_roe, COUNT(revenue_growth) as with_growth
FROM herrrickshaw.stock_quotes
GROUP BY market;

-- Check for any NULL quality_score (should be 0)
SELECT COUNT(*) as nulls FROM herrrickshaw.stock_quotes 
WHERE quality_score IS NULL;
-- Expected: 0

-- Sample data from each market
SELECT market, yf_ticker, pe, roe, revenue_growth, quality_score 
FROM herrrickshaw.stock_quotes 
WHERE market IN ('us', 'india', 'europe', 'japan', 'korea', 'china')
LIMIT 6;
```

---

## Expected Final State

**All 25,335 symbols with:**
- ✓ quality_score: 100% (0-100, never NULL)
- ✓ PE/PB/PS: 90%+ populated
- ✓ ROE/ROA/Margins: 85%+ populated
- ✓ Growth metrics: 85%+ populated
- ✓ Financial health: 85%+ populated
- ✓ Complete rows (all 20): 87%+ of universe

**Market Breakdown:**
- US: 9,278 (22% → 90%+ coverage)
- India: 3,480 (100% → 100% with 20 cols)
- Europe: 1,709 (0% → 90%+ coverage)
- Japan: 3,083 (0% → 85%+ coverage)
- Korea: 2,597 (0% → 85%+ coverage)
- China: 5,188 (0% → 80%+ coverage)

**Improvement:** 26% → 90% average coverage across all metrics and all markets.
