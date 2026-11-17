# Unified Fundamentals Schema
## Same Columns for All Markets, Flexible Calculation Methods

**Principle:** Every symbol in Cassandra has the SAME set of fundamental columns, regardless of market or API source. The VALUE and CALCULATION METHOD can vary, but the COLUMN STRUCTURE is canonical.

---

## Canonical Fundamental Columns

All 25,335 symbols will have these 12 columns populated (or NULL):

```sql
-- Cassandra table schema (must have these columns for all markets)
stock_quotes (
  -- Primary key (market, yf_ticker)
  -- ... existing OHLCV columns ...
  
  -- VALUATION MULTIPLES (standardized)
  pe DOUBLE,           -- Price-to-Earnings ratio
  pb DOUBLE,           -- Price-to-Book ratio
  ps DOUBLE,           -- Price-to-Sales ratio (optional, for depth)
  
  -- PROFITABILITY METRICS (standardized)
  roe DOUBLE,          -- Return on Equity (%)
  roa DOUBLE,          -- Return on Assets (%)
  opm DOUBLE,          -- Operating Profit Margin (%)
  npm DOUBLE,          -- Net Profit Margin (%)
  
  -- EFFICIENCY METRICS (standardized)
  roce DOUBLE,         -- Return on Capital Employed (%)
  roc DOUBLE,          -- Return on Capital (%)
  
  -- QUALITY SCORES (0-100, unified tier)
  quality_score INT,   -- Liquidity/quality proxy (0-100)
  
  -- COMPOSITE SIGNALS
  piotroski INT,       -- Piotroski F-Score (0-9 or 0-100)
  
  -- METADATA
  fundamentals_source TEXT,  -- 'alphavantage', 'eodhd', 'screener', 'jquants', 'dart'
  fundamentals_date TIMESTAMP -- when fundamentals were last updated
);
```

---

## Market-Specific Implementation

### US Market
**Primary Source:** AlphaVantage  
**Fallback:** EODHD

| Column | Source | Calculation | Method |
|--------|--------|------------|--------|
| pe | AlphaVantage OVERVIEW | Direct | `PE` field from API |
| pb | AlphaVantage OVERVIEW | Direct | `PriceToBookRatio` field |
| ps | EODHD Fundamentals | Direct | `PS` / `PriceToSalesRatio` |
| roe | AlphaVantage OVERVIEW | TTM (Trailing Twelve Months) | `ReturnOnEquityTTM` |
| roa | EODHD Fundamentals | Annual | Balance sheet ROA |
| opm | EODHD Fundamentals | Annual | Operating Income / Revenue |
| npm | EODHD Fundamentals | Annual | Net Income / Revenue |
| roce | EODHD Fundamentals | Annual | EBIT / (Debt + Equity) |
| roc | AlphaVantage OVERVIEW | Calculated | (Operating Income - Taxes) / Capital |
| quality_score | Volume-based | 0-100 scale | Volume rank + liquidity tier |
| piotroski | sweep_piotroski_plus_us.csv | 0-100 normalized | F-Score from `sweep_piotroski` |
| fundamentals_source | Mixed | — | 'alphavantage' or 'eodhd' |

**Fallback Strategy:**
- If AlphaVantage fails → EODHD
- If both fail → Use quality_score (volume proxy)
- Never leave column NULL if there's ANY data source available

---

### India Market
**Primary Source:** screener.in, IN_screener_only_backup.parquet  
**Calculation Basis:** ANNUAL (most recent FY end)

| Column | Source | Calculation | Method |
|--------|--------|------------|--------|
| pe | screener.in | Annual | Price / EPS (annual) |
| pb | screener.in | Annual | Market Cap / Book Value |
| ps | screener.in | Annual | Market Cap / Revenue |
| roe | IN_screener_only_backup | Annual | Net Income / Equity |
| roa | Derived | Annual | Net Income / Total Assets |
| opm | Derived | Annual | Operating Income / Revenue |
| npm | screener.in | Annual | Net Profit / Revenue |
| roce | india_factor_panel.parquet | Annual | EBIT / Capital Employed |
| roc | Derived | Annual | Operating profit / Invested capital |
| quality_score | nse_deep.parquet | 0-100 scale | Volume magnitude (0-100) |
| piotroski | piotroski_plus_india.csv | 0-9 → 0-100 | F-Score (normalized to 0-100) |
| fundamentals_source | Mixed | — | 'screener', 'parquet', 'roace' |

**Specificity:** India uses ANNUAL fundamentals (full fiscal year), not quarterly or TTM. All metrics are standardized to this basis.

---

### Europe Market
**Primary Source:** EODHD (17 exchanges, 1,709 symbols)

| Column | Source | Calculation | Method |
|--------|--------|------------|--------|
| pe | EODHD | Annual | Trailing PE (12-month) |
| pb | EODHD | Annual | Price / Book Value per share |
| ps | EODHD | Annual | Price / Sales per share |
| roe | EODHD Balance Sheet | Annual | Net Income / Shareholders' Equity |
| roa | EODHD Balance Sheet | Annual | Net Income / Total Assets |
| opm | EODHD Income Statement | Annual | Operating Income / Revenue |
| npm | EODHD Income Statement | Annual | Net Income / Revenue |
| roce | EODHD Financials | Annual | EBIT / (Debt + Equity) |
| roc | Calculated | Annual | Operating Income / Capital |
| quality_score | Exchange tier | 0-100 scale | LSE=80, Frankfurt=75, Others=60-70 |
| piotroski | Derived | 0-100 | Quality score mapped to F-Score equivalent |
| fundamentals_source | eodhd | — | 'eodhd' |

**Exchange Tiers (Quality Score):**
- LSE (436): 80
- Frankfurt (142): 75
- Euronext (208): 75
- Nasdaq Nordic (80): 70
- Others (857): 65

---

### Japan Market
**Primary Source:** EODHD + J-Quants + EDINET

| Column | Source | Calculation | Method |
|--------|--------|------------|--------|
| pe | EODHD | Annual | Price / EPS (annual) |
| pb | EODHD | Annual | Price / Book Value |
| ps | EODHD | Annual | Price / Sales |
| roe | EDINET Filings | Fiscal Year | Net Income / Shareholders' Equity |
| roa | J-Quants | Fiscal Year | Operating Income / Total Assets |
| opm | EODHD Income Statement | Annual | Operating Income / Revenue |
| npm | EODHD Income Statement | Annual | Net Income / Revenue |
| roce | Derived from filings | Fiscal Year | EBIT / (Debt + Equity) |
| roc | Calculated | Fiscal Year | Operating profit / Invested capital |
| quality_score | Volume-based | 0-100 scale | TSE volume rank (0-100) |
| piotroski | Derived | 0-100 | Quality score → F-Score equivalent |
| fundamentals_source | Mixed | — | 'eodhd', 'jquants', 'edinet' |

**Japan Note:** Fiscal year end (March 31), use latest annual results, not TTM.

---

### Korea Market
**Primary Source:** EODHD + DART

| Column | Source | Calculation | Method |
|--------|--------|------------|--------|
| pe | EODHD | Annual | Price / EPS (annual) |
| pb | DART Korean Exchange | Annual | Price / Book Value |
| ps | EODHD | Annual | Price / Sales |
| roe | DART Filings | Annual | Net Income / Equity |
| roa | EODHD Balance Sheet | Annual | Operating Income / Assets |
| opm | EODHD Income Statement | Annual | Operating Income / Revenue |
| npm | EODHD Income Statement | Annual | Net Income / Revenue |
| roce | Derived | Annual | EBIT / Capital Employed |
| roc | DART Corporate Data | Annual | Operating profit / Invested capital |
| quality_score | Volume-based | 0-100 scale | KRX volume rank (0-100) |
| piotroski | Derived | 0-100 | Quality score + momentum |
| fundamentals_source | Mixed | — | 'eodhd', 'dart' |

---

### China Market
**Primary Source:** EODHD + Eastmoney (fallback)

| Column | Source | Calculation | Method |
|--------|--------|------------|--------|
| pe | EODHD | Annual | Price / EPS (annual) |
| pb | EODHD | Annual | Price / Book Value |
| ps | EODHD | Annual | Price / Sales |
| roe | Eastmoney | Annual | Net Income / Equity |
| roa | EODHD Balance Sheet | Annual | Operating Income / Total Assets |
| opm | EODHD Income Statement | Annual | Operating Income / Revenue |
| npm | EODHD Income Statement | Annual | Net Income / Revenue |
| roce | Derived | Annual | EBIT / Capital Employed |
| roc | Calculated | Annual | Operating profit / Invested capital |
| quality_score | Volume-based | 0-100 scale | SSE/SZSE volume rank (0-100) |
| piotroski | Derived | 0-100 | Quality score based on scale |
| fundamentals_source | Mixed | — | 'eodhd', 'eastmoney' |

**China Note:** Use RMB-denominated data, standardize to USD using period-average FX rates for comparability.

---

## Unified Output: The Canonical Update Statement

**All markets, regardless of source, produce CQL in THIS format:**

```sql
UPDATE herrrickshaw.stock_quotes SET 
  pe = 25.5,
  pb = 3.2,
  ps = 8.5,
  roe = 18.5,
  roa = 8.2,
  opm = 22.3,
  npm = 14.5,
  roce = 16.8,
  roc = 15.2,
  quality_score = 75,
  piotroski = 72,
  fundamentals_source = 'eodhd',
  fundamentals_date = toTimestamp(now())
WHERE market = 'europe' AND yf_ticker = 'SAP.DE';
```

**Key point:** EVERY symbol gets ALL 12 columns, with NULL permitted only if the source cannot provide any data.

---

## Null Handling Policy

| Scenario | Action | Column Value |
|----------|--------|--------------|
| API provides data | Use it directly | Actual value |
| API doesn't provide, fallback does | Use fallback | Fallback value |
| No data from any source | Use proxy | quality_score only |
| Completely unavailable | Allow NULL | NULL (rare) |

**Example:**
- US symbol: AlphaVantage provides PE → use PE value
- If AV down: EODHD provides PE → use EODHD PE
- If both down: Use volume-based quality_score
- All sources down: Accept NULL (historical data still queryable)

---

## Collection Checklist: Ensure Coverage

Before final Cassandra load, validate:

```sql
-- Check all markets have pe column populated
SELECT market, COUNT(*) as symbols, COUNT(pe) as with_pe 
FROM stock_quotes GROUP BY market;

-- Expected output:
-- market    | symbols | with_pe
-- us        |    9278 |    6555  (90%+ of attempted)
-- europe    |    1709 |    1452  (85%+)
-- japan     |    3083 |    2312  (75%+)
-- korea     |    2597 |    2078  (80%+)
-- china     |    5188 |    3632  (70%+)
-- india     |    3480 |    3480  (100%)

-- Check roe coverage across markets
SELECT market, COUNT(roe) as with_roe FROM stock_quotes 
WHERE roe IS NOT NULL GROUP BY market;

-- Check piotroski coverage (US focus)
SELECT market, COUNT(piotroski) as with_piotroski 
FROM stock_quotes WHERE piotroski > 0 ALLOW FILTERING GROUP BY market;
```

---

## Quality Assurance

**Before marking collection complete:**

1. ✅ **Completeness:** All 12 columns defined for every market
2. ✅ **Consistency:** Same column names, same data types
3. ✅ **Fallback chain:** Each market has 2+ sources (primary + fallback)
4. ✅ **Documentation:** Source and calculation method recorded in `fundamentals_source` + comments
5. ✅ **Nullability:** <10% NULL rate for PE, <20% for ROE
6. ✅ **Verification:** Sample queries on each market return non-NULL results

---

## Post-Collection: Unified Analysis

**With canonical columns, these queries work identically across all markets:**

```sql
-- Filter by valuation (PE < 20) across all geographies
SELECT market, yf_ticker, pe, roe FROM stock_quotes 
WHERE pe > 0 AND pe < 20 ALLOW FILTERING;

-- Screen for quality (ROE > 15%, PE < 25) universally
SELECT market, yf_ticker, roe, pe FROM stock_quotes 
WHERE roe > 15.0 AND pe < 25 ALLOW FILTERING;

-- Composite score: Piotroski + Quality
SELECT market, yf_ticker, piotroski, quality_score FROM stock_quotes 
WHERE (piotroski + quality_score) > 150 ALLOW FILTERING;
```

**No market-specific translation layer needed** because columns are canonical.

---

## Implementation: Modify Collector

The production collector must enforce this schema:

```python
# Unified output function
def generate_canonical_update(symbol, market, fundamentals_dict):
    """
    Ensure ALL 12 columns are in the UPDATE statement.
    
    Args:
        fundamentals_dict: {
            'pe': float,
            'pb': float,
            'roe': float,
            'roce': float,
            ...
        }
    
    Returns:
        CQL UPDATE with all 12 columns (NULLs if not available)
    """
    
    # Define canonical columns
    CANONICAL_COLUMNS = [
        'pe', 'pb', 'ps', 'roe', 'roa', 'opm', 
        'npm', 'roce', 'roc', 'quality_score', 'piotroski'
    ]
    
    # Build SET clause
    set_clauses = []
    for col in CANONICAL_COLUMNS:
        value = fundamentals_dict.get(col)
        if value is not None:
            set_clauses.append(f"{col} = {value}")
        # If NULL, omit from SET (Cassandra won't overwrite non-NULL with NULL)
    
    # Add metadata
    set_clauses.append(f"fundamentals_source = '{fundamentals_dict.get('source', 'unknown')}'")
    set_clauses.append("fundamentals_date = toTimestamp(now())")
    
    # Generate CQL
    cql = f"""UPDATE herrrickshaw.stock_quotes SET {', '.join(set_clauses)} 
    WHERE market = '{market}' AND yf_ticker = '{symbol}';"""
    
    return cql
```

---

## Expected Final State

All 25,335 symbols will have:

```
┌─────────────────────────────────────────────────┐
│ Canonical Fundamentals Schema (12 Columns)      │
├─────────────────────────────────────────────────┤
│ ✓ pe (P/E Ratio)                                │
│ ✓ pb (P/B Ratio)                                │
│ ✓ ps (P/S Ratio)                                │
│ ✓ roe (Return on Equity, %)                     │
│ ✓ roa (Return on Assets, %)                     │
│ ✓ opm (Operating Profit Margin, %)              │
│ ✓ npm (Net Profit Margin, %)                    │
│ ✓ roce (Return on Capital Employed, %)          │
│ ✓ roc (Return on Capital, %)                    │
│ ✓ quality_score (0-100 universal tier)          │
│ ✓ piotroski (0-100 F-Score normalized)          │
│ ✓ fundamentals_source (data lineage)            │
└─────────────────────────────────────────────────┘

Applied to:
  • 9,278 US symbols
  • 3,480 India symbols
  • 1,709 Europe symbols
  • 3,083 Japan symbols
  • 2,597 Korea symbols
  • 5,188 China symbols
  ────────────────────
  25,335 TOTAL
```

**All markets, same columns. Different calculation methods, unified output.**
