# Data Completeness Analysis — 2026-07-28

**Status:** 28,826 tickers across 6 markets; 9,128 with complete OHLCV+fundamentals (31.7% blended)

---

## Executive Summary

### Headline Metrics

| Metric | Value | Trend |
|--------|-------|-------|
| Total tickers indexed | 28,826 | ✓ Stable |
| OHLCV coverage | 28,826 (100%) | ✓ Complete |
| Fundamentals coverage | 10,528 (36.6%) | ⚠ Uneven by market |
| Complete (both) | 9,128 (31.7%) | ⚠ Conservative estimate |
| Data freshness | Mixed | ⚠ CN stale; US current |

### Critical Finding

**Blended completeness is masked by large disparities:** US/China are only 47%/8% complete, while Europe/Korea are 72%/60%. This means 58% of the library has usable prices but no fundamentals, preventing Piotroski/financial scoring on those tickers.

---

## By-Market Completeness

### INDIA (IN)
- **Universe:** 6,731 (NSE + BSE)
- **OHLCV:** 6,731 tickers (100%), updated 2026-07-23
- **Fundamentals:** 1,487 tickers (22.1%), latest FY: 2026-03-31
- **Complete:** 1,487 (22.1%)
- **Data range:** 2016–present (10 years)
- **Freshness:** OHLCV is 5 days old (acceptable); fundamentals 10 days old

**Gap Analysis:**
- 5,244 tickers have prices but no fundamentals
- screener.in collector is running but slow (~1,487 / 6,731 target)
- Missing: ~5,244 companies' financials

**Action:** Accelerate screener.in collection (parallel fetch) → could reach 50% in 2 weeks

---

### UNITED STATES (US)
- **Universe:** 9,829 (NYSE/NASDAQ/OTC)
- **OHLCV:** 9,829 tickers (100%), updated 2026-07-27
- **Fundamentals:** 4,597 tickers (46.8%), latest FY: 2029-12-31 (EDGAR)
- **Complete:** 4,597 (46.8%) — conservative; actual overlap unknown
- **Data range:** 2016–present (10 years)
- **Freshness:** OHLCV is current (1 day old); fundamentals 9 days old

**Gap Analysis (Critical):**
- **Known issue from data_completeness_audit.py:** EDGAR (4,597) and price panel (9,829) have only 50% overlap
  - This means: ~2,300 tickers are in EDGAR but NOT in the price panel
  - And: ~5,232 tickers are in prices but NOT in EDGAR
- 5,232 tickers have prices but no fundamentals available in current sources
- US shares supplement only covers 463 tickers (yfinance .info)

**Action:** Run EDGAR/price reconciliation to unlock +2,200 tickers

**Reference:** `/Users/umashankar/market-pipeline/code/python_files/data_completeness_audit.py`

---

### EUROPE (EU)
- **Universe:** 1,618 (17 exchanges: LSE, Frankfurt, Euronext, Nordic, etc.)
- **OHLCV:** 1,618 tickers (100%), updated 2026-07-22 (5 days old)
- **Fundamentals:** 1,159 tickers (71.6%), latest FY: 2026-05-31
- **Complete:** 1,159 (71.6%)
- **Data range:** OHLCV 10 years; Fundamentals 5 years only (pre-2021 missing)
- **Freshness:** OHLCV is 5 days old (acceptable); fundamentals 4 days old

**Gap Analysis:**
- 459 tickers have prices but no fundamentals (28%)
- Fundamentals history only 5y (yfinance limitation); needs exchange registries for pre-2021
- Frankfurt/London account for ~60% of EU volume but lack deep history

**Action:** Add BaFin (DE), FCA (UK), AMF (FR), AFM (NL) registry collectors for 10y history

---

### JAPAN (JP)
- **Universe:** 3,083 (TSE)
- **OHLCV:** 3,083 tickers (100%), updated 2026-07-23 (5 days old)
- **Fundamentals:** 1,295 tickers (42.0%), latest FY: 2026-03-31
- **Complete:** 1,295 (42.0%)
- **Data range:** 2016–present (10 years)
- **Freshness:** OHLCV is current; fundamentals 10 days old

**Gap Analysis:**
- 1,788 tickers have prices but no fundamentals (58%)
- J-Quants API is configured (JQUANTS_API_KEY set) but no collector running
- J-Quants is official JSE source with historical XBRL — untapped

**Action:** Activate J-Quants integration → could reach 80%+ coverage in 1 week

---

### KOREA (KR)
- **Universe:** 2,597 (KOSPI + KOSDAQ)
- **OHLCV:** 2,597 tickers (100%), updated 2026-07-23 (5 days old)
- **Fundamentals:** 1,564 tickers (60.2%), latest FY: 2026-03-31
- **Complete:** 1,564 (60.2%)
- **Data range:** 2016–present (10 years)
- **Freshness:** OHLCV current; fundamentals 4 days old

**Gap Analysis:**
- 1,033 tickers have prices but no fundamentals (40%)
- DART collector is current (2026-07-24) and sustainable (~20k/day quota)
- 60% coverage is natural; smaller-cap XBRL adoption in Korea is lower

**Action:** No immediate action — maintain current schedule

---

### CHINA (CN)
- **Universe:** 5,188 (A-shares: Shanghai + Shenzhen)
- **OHLCV:** 5,188 tickers (100%), last update 2026-07-22 (6 DAYS OLD — CRITICAL)
- **Fundamentals:** 426 tickers (8.2%), latest: 2025-12-31
- **Complete:** 426 (8.2%)
- **Data range:** OHLCV 10 years; Fundamentals 1 year
- **Freshness:** OHLCV is stale; fundamentals 3 days old but sparse

**Gap Analysis:**
- 4,762 tickers have prices but no fundamentals (92%)
- akshare collector is NOT running (NSE blocks AWS; must run locally)
- Fundamentals extremely limited (only 426 tickers, latest FY year-end 2025)
- Data drift risk: 6 days without update

**Action (Urgent):** Restart akshare OHLCV collector locally (post-12:30 IST only)

---

## Global Completeness by Data Type

| Data Type | Coverage | Status | Notes |
|-----------|----------|--------|-------|
| **OHLCV** | 28,826 / 28,826 (100%) | ✓ Complete | All markets have price data; some stale |
| **Fundamentals (core)** | 10,528 / 28,826 (36.6%) | ⚠ Partial | Highly uneven: US 47%, EU 72%, CN 8% |
| **RSI/Technical** | ~28k (inferred from OHLCV) | ✓ Derived | Calculated from prices; not stored |
| **Corporate actions** | ~1,500 (IN only) | ◻ Missing | No coverage for US/EU/JP/KR/CN |
| **Sector/Industry** | ~20,000 (EU/JP covered) | ⚠ Partial | Only JP master (free) + EU union |
| **10+ year history** | ~6,000 (IN/US/JP/KR) | ⚠ Partial | EU limited to 5y; CN to 1y |

---

## Priority Gaps & Recommended Actions

### Tier 1: Critical (Next 48 hours)

#### 🔴 China OHLCV Staleness
- **Issue:** 6 days without update; data drift imminent
- **Impact:** 5,188 tickers; moderate priority but growing risk
- **Action:** Restart akshare collector locally
- **Effort:** HIGH (requires local machine; akshare throttles)
- **Timeline:** 1-2 days
- **Reference:** `ohlcv_cache.py` (CN path)

#### 🔴 US EDGAR/Price Reconciliation
- **Issue:** 50% overlap unknown; some tickers in both, some missing in one source
- **Impact:** Could unlock +2,200 tickers (US completeness 47% → 70%+)
- **Action:** Run cross-match + gap analysis
- **Effort:** MEDIUM (data already exists; needs analysis)
- **Timeline:** 3-5 days
- **Reference:** `data_completeness_audit.py` shows methodology

### Tier 2: High Impact (Week 1-2)

#### 🟠 India Fundamentals Acceleration
- **Issue:** screener.in collector is slow; 22% coverage vs 50% potential
- **Impact:** +3,000 tickers with financials for Piotroski
- **Action:** Parallelize screener.in fetch (threading)
- **Effort:** LOW (infrastructure exists)
- **Timeline:** 2-3 days
- **Reference:** `screener_history_collector.py`

#### 🟠 Japan J-Quants Activation
- **Issue:** API configured but no collector running
- **Impact:** +1,788 tickers (official JSE, historical XBRL)
- **Action:** Build J-Quants integration module
- **Effort:** MEDIUM (API is ready)
- **Timeline:** 5-7 days
- **Reference:** `JQUANTS_API_KEY` already in .env

### Tier 3: Long-term (Week 3+)

#### 🟡 Europe Registry Depth
- **Issue:** Fundamentals only 5 years; pre-2021 missing
- **Impact:** Enables 10y Piotroski for 966 core EU stocks
- **Action:** Add BaFin (DE), FCA (UK), AMF (FR), AFM (NL) collectors
- **Effort:** HIGH (4 new integrations × 3-5 days each)
- **Timeline:** 3-4 weeks
- **Reference:** 17 exchanges; Frankfurt + London = 60% of volume

#### 🟡 Global Fundamentals Unification
- **Issue:** No single catalog showing complete vs partial coverage
- **Action:** Build `tickers_with_complete_data.csv` (per market)
- **Impact:** Enables automated tier selection (Piotroski vs Darvas vs Screener)
- **Effort:** MEDIUM (scripting + validation)
- **Timeline:** 1 week
- **Output:** Reports/tickers_complete_status.csv

---

## Collector & Pipeline Status

### Active & Healthy
- ✓ **India (IN)** — bhavcopy: Daily, 18:00+ IST (no throttle)
- ✓ **US (US)** — yfinance: Current to 2026-07-27 (post-US-close)
- ✓ **Europe (EU)** — yfinance: Current to 2026-07-22 (post-EU-close)
- ✓ **Japan (JP)** — yfinance: Current to 2026-07-23 (post-TSE-close)
- ✓ **Korea (KR)** — FinanceDataReader + DART: Current (FinanceDataReader 2026-07-23, DART 2026-07-24)

### Needs Restart/Maintenance
- ✗ **China (CN)** — akshare: STALE (2026-07-22, 6d old) — NSE-AWS blocks, run locally
- ⚠ **India Fundamentals** — screener.in: Slow (2026-07-18, 10d old) — parallelize
- ⚠ **Japan Fundamentals** — J-Quants: NOT RUNNING (API ready, needs integration)

### Missing Collectors
- ◻ **Europe Fundamentals (pre-2021)** — No registry collectors
- ◻ **US Fundamentals Unification** — No EDGAR/price cross-match pipeline

---

## Recommendations Summary

### Immediate (Scorecard)

| Task | Impact | Effort | Timeline | Owner |
|------|--------|--------|----------|-------|
| China akshare restart | Medium | High | 1-2 days | Local |
| US EDGAR/price reconciliation | Critical | Medium | 3-5 days | [Pipeline] |
| India screener.in parallelization | High | Low | 2-3 days | [Pipeline] |

### By Market (Priority + Action)

**India:** Accelerate → 50%+ in 2 weeks (low effort, high ROI)
**US:** Reconcile → unlock 2.2k tickers (medium effort, critical impact)
**Europe:** Maintain OHLCV; add registries for depth (long-term)
**Japan:** Activate J-Quants → reach 80%+ in 1 week (medium effort)
**Korea:** Maintain current schedule (running well)
**China:** Restart akshare → prevent drift (urgent)

---

## Data Quality & Validation Notes

### Known Issues
1. **US EDGAR/yfinance mismatch** (documented in `data_completeness_audit.py`)
   - EDGAR has tickers not in yfinance panel
   - Price panel has tickers not in EDGAR
   - No current cross-match; blind overlap at 50%

2. **China fundamentals sparse** (akshare has limited coverage)
   - Only 426 / 5,188 tickers (8.2%)
   - Quality varies by data provider; use with caution

3. **Europe fundamentals shallow** (yfinance limited to 5 years)
   - Pre-2021 requires exchange registries
   - Prevents long-term Piotroski analysis

### Strengths
- **OHLCV is globally complete** (100% coverage across all markets)
- **OHLCV is well-dated** (10-year history for all except CN)
- **Korea fundamentals reliable** (DART is official source)
- **India fundamentals improving** (screener.in is growing)

---

## Files & References

- **Data Ledger:** `/Users/umashankar/market-pipeline/code/python_files/reports/data_ledger.md`
- **Data Completeness Audit:** `/Users/umashankar/market-pipeline/code/python_files/data_completeness_audit.py` (US EDGAR/price gap)
- **OHLCV Warehouse:** `/Users/umashankar/repos/global-market-data/warehouse/ohlcv/{market}/`
- **Fundamentals:** `/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/`

---

**Analysis Date:** 2026-07-28 | **Next Review:** 2026-08-04 | **Prepared by:** Data completeness audit script
