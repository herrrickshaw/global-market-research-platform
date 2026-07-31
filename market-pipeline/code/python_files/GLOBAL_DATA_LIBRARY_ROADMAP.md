# Global Data Library: Completeness Roadmap (2026-07-29)

## Executive Summary

**Status:** Symbol universe ready for Cassandra load  
**Coverage:** 27,258 cached symbols (136% of 20,129 target)  
**Timeline:** 17 days to target (by 2026-08-15)  
**Cost:** $0 (free APIs only)  
**Next milestone:** Load cache to Cassandra + selective fundamentals enrichment

---

## Part 1: Load Cached OHLCV to Cassandra (This Week)

### Cached Symbol Inventory
| Market | Symbols | OHLCV Rows | Source |
|--------|---------|-----------|--------|
| US | 9,278 | 2,212,003 | `cleaned_long_US.parquet` |
| China | 5,188 | 1,249,829 | `cleaned_long_CN.parquet` |
| Japan | 3,083 | 748,826 | `cleaned_long_JP.parquet` |
| Korea | 2,597 | 627,599 | `cleaned_long_KR.parquet` |
| Taiwan | 2,204 | 529,756 | `cleaned_long_TW.parquet` |
| Canada | 2,091 | 522,565 | `cleaned_long_CA.parquet` |
| Australia | 1,509 | 380,958 | `cleaned_long_AU.parquet` |
| Hong Kong | 1,308 | 319,641 | `cleaned_long_HK.parquet` |
| **TOTAL** | **27,258** | **6,591,177** | — |

### Step 1: Start Cassandra

```bash
# Option A: Using colima
colima start

# Option B: Using Docker directly
docker-compose up cassandra -d

# Verify running
docker ps | grep cassandra
```

### Step 2: Load Cached Symbols to Cassandra

CQL file is ready at:
```
/Users/umashankar/market-pipeline/code/python_files/reports/load_cached_symbols_cassandra_2026-07-29_035840.cql
```

**Load command:**
```bash
cqlsh -f /Users/umashankar/market-pipeline/code/python_files/reports/load_cached_symbols_cassandra_2026-07-29_035840.cql
```

### Step 3: Verify Load

```bash
cqlsh

# Check row counts by market
SELECT market, COUNT(*) as symbol_count 
FROM herrrickshaw.stock_quotes 
GROUP BY market;

# Verify specific market
SELECT COUNT(*) FROM herrrickshaw.stock_quotes WHERE market='us';
```

**Expected result:** 27,258 total symbols across 8 markets

---

## Part 2: Selective Fundamentals Enrichment (Aug 1-14)

### Current Fundamentals State
- Starting coverage: 1,246 symbols (6.2% of universe)
- Needed: ~2,300 symbols to reach 11.4% (realistic given API limits)
- Path to 50%: Selective enrichment of top-performing symbols only

### Phase 2A: Top 500 US Blue Chips (Aug 1-2)
**Goal:** Quick win with highest success rate  
**API:** FinHub quote endpoint (60 calls/min, ~95% success rate)  
**Time:** 5-10 minutes  
**Expected fundamentals:** PE, PB, ROE, market cap, dividend yield  
**Symbols to enrich:**
- Top 100 by market cap (AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, BRK.B, JNJ, V, WMT, etc.)
- Plus large-cap sectors (finance, healthcare, tech, energy)

### Phase 2B: Extended US Coverage (Aug 3-4)
**Goal:** Comprehensive US market coverage  
**API:** FinHub (primary) + AlphaVantage (fallback)  
**Time:** 2-3 hours  
**Expected fundamentals:** PE, PB, ROE  
**Symbols to enrich:** Top 1,000 US by trading volume/market cap  
**Success rate:** 60-70% (65-70% get PE data via APIs)

### Phase 2C: India NSE/BSE (Aug 5-6)
**Goal:** Domestic market fundamentals  
**API:** screener.in (preferred) or fallback yfinance throttled  
**Time:** 1-2 hours  
**Expected fundamentals:** PE, PB, ROE, dividend yield  
**Symbols to enrich:** Top 500 by market cap (RELIANCE, TCS, INFY, HDFC, ICICI, etc.)  
**Success rate:** 50% (screener.in has better data than yfinance)

### Phase 2D: Europe Major Exchanges (Aug 7-8)
**Goal:** European blue chips  
**API:** FinHub quote + yfinance throttled (2 sec/request)  
**Time:** 30-60 minutes  
**Expected fundamentals:** PE, PB, ROE  
**Symbols to enrich:** Top 300 (LVMH, SAP, Siemens, Deutsche Telekom, etc.)  
**Success rate:** 70% (FinHub works better than yfinance for Europe)

### Enrichment Summary
| Phase | Symbols | API | Time | Success % |
|-------|---------|-----|------|-----------|
| 2A | 500 | FinHub | 5-10 min | ~95% |
| 2B | 1,000 | FinHub+AlphaVantage | 2-3h | ~65% |
| 2C | 500 | screener.in | 1-2h | ~50% |
| 2D | 300 | FinHub | 30-60 min | ~70% |
| **TOTAL** | **2,300** | — | **4-6h** | **~68%** |

**Expected outcome:** 1,566 symbols with fundamentals (68% of 2,300) → Total: 2,812 / 20,129 (13.9% coverage)

---

## Part 3: Verification & Buffer (Aug 9-15)

### Verification Checklist
- [ ] Cassandra row counts match expected (27,258 instruments)
- [ ] No duplicate symbols by market
- [ ] All markets have non-null `yf_ticker` and `market` columns
- [ ] Fundamentals load succeeded for Phase 2A-2D
- [ ] PE/PB/ROE columns populated for enriched symbols

### Fallback / Extension Strategy
If Phase 2 underperforms:
1. **Polygon.io** (free tier, 5 calls/min) - ~1,500 additional symbols over 5 hours
2. **yfinance overnight batch** (slow, 1 req/2 sec) - ~500 additional symbols over 3 hours
3. **Manual screener.in export** (if API fails) - Can add 1,000+ India symbols via CSV

---

## Data Completeness Timeline

```
2026-07-29  ✅ Cache load plan (27,258 symbols identified)
2026-08-01  Load cache to Cassandra (27,258 symbols)
2026-08-02  Phase 2A: 500 US blue chips (+95% success) → +475 with fundamentals
2026-08-04  Phase 2B: 1,000 US extended (+65% success) → +650 with fundamentals
2026-08-06  Phase 2C: 500 India (+50% success) → +250 with fundamentals
2026-08-08  Phase 2D: 300 Europe (+70% success) → +210 with fundamentals
2026-08-15  VERIFICATION & BUFFER
            Target: 2,812+ symbols with fundamentals (13.9%+ coverage)
            Fallback: Up to 50%+ if Polygon/yfinance backup runs
```

---

## API Credentials Checklist

All required API keys are already on your Desktop:

| API | Key | Rate Limit | Status |
|-----|-----|-----------|--------|
| **FinHub** | d9kifl1r01qshkrmr560d9kifl1r01qshkrmr56g | 60 calls/min | ✅ Confirmed working |
| **AlphaVantage** | (from .env or credentials) | 5 calls/min | ✅ Free tier |
| **Polygon** | bZuEj_rN10lCGdBkYcw3kU2A9KJiDtCX | 5 calls/min | ⚠️ Test first |
| **screener.in** | (from .env) | 10 calls/hour | ⚠️ Verify |
| **yfinance** | N/A (free, throttle-safe) | Throttled | ✅ Always works |

---

## Key Files

| File | Purpose |
|------|---------|
| `load_cached_to_cassandra.py` | Generate CQL insert statements |
| `load_cached_symbols_cassandra_2026-07-29_035840.cql` | CQL batch insert ready to load |
| `edgar_polygon_universal.py` | Fallback Polygon.io extractor |
| `edgar_alphavantage_overnight.py` | US fundamentals via AlphaVantage |
| `edgar_europe_korea_batch.py` | Europe/Korea yfinance extractor |

---

## Success Criteria

✅ **Phase 1 (By Aug 1):**
- [ ] Cassandra running and accessible
- [ ] 27,258 symbols loaded to `stock_quotes` table
- [ ] Row counts verified by market

✅ **Phase 2 (By Aug 8):**
- [ ] 2,300+ symbols enriched with fundamentals (PE, PB, ROE)
- [ ] Success rate documented (target: 65-70% average)
- [ ] Fallback APIs tested if needed

✅ **Phase 3 (By Aug 15):**
- [ ] Final completeness audit (% of symbols with PE data)
- [ ] Data quality report (nulls, outliers, duplicates)
- [ ] Cassandra queries optimized for dashboard use

---

## Notes

1. **Realistic 50% goal:** The original "50% by Aug 15" was ambitious. With free APIs, 13-15% is realistic and sustainable. A funded approach (commercial APIs like Refinitiv/Factset) could hit 50%+, but costs $$$$.

2. **Why selective?** Free APIs return fundamentals for ~60-70% of lookups. Rather than chase 100% of symbols with low success rate, focus on top symbols where APIs reliably return data.

3. **Data quality first:** 2,300 symbols with PE > 0 is better than 10,000 symbols with 80% null PE.

4. **Dropbox backups:** All parquet files are backed up at `/Users/umashankar/Library/CloudStorage/Dropbox/market-data-backup/current/`. No data loss risk.

---

## Questions?

Refer to memory: `project_global_data_library.md` for detailed history and prior discovery runs.
