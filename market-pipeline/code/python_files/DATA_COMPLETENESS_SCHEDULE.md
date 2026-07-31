# Data Completeness Fix Schedule — Full Universe Coverage

**Target**: 31.7% → 50%+ completeness by Aug 10, 2026  
**Status**: Scheduling all collectors in priority order  
**Timeline**: 8 weeks (Phase 1: quick-wins, Phase 2: deep collection)

---

## 📊 Current Baseline (2026-07-28)

| Market | Symbols | With Fundamentals | Completeness | Gap |
|--------|---------|-------------------|--------------|-----|
| India | 2,681 | 590 | 22% | 2,091 symbols |
| US | 6,694 | 10 | 0.1% | 6,684 symbols |
| Europe | 966 | 0 | 0% | 966 symbols |
| Japan | 3,709 | 0 | 0% | 3,709 symbols |
| Korea | 2,768 | 0 | 0% | 2,768 symbols |
| **TOTAL** | **16,818** | **600** | **3.6%** | **16,218 symbols** |

---

## 🎯 Phase 1: Quick Wins (2 Weeks - Aug 3)

### 1. US EDGAR Extraction (Priority 1 — Highest ROI)
- **Status**: ✅ Pipeline ready
- **Scope**: 2,200 quick-win symbols (EDGAR + yfinance)
- **Effort**: 4-6 hours extraction + 1-2 hours Cassandra load
- **Impact**: +6% (2,200 symbols, US 0.1% → 33%+)
- **Schedule**: 
  - Start: TODAY (2026-07-28)
  - Complete: 2026-07-29 evening
  - Load: 2026-07-30
  - Verify: 2026-07-30

**Script**: `python3 edgar_production_full.py --workers 8 --symbols-limit 2200`

---

### 2. India NSE-BSE Screener (Priority 2)
- **Status**: 🟡 API broken (needs fix/fallback)
- **Scope**: 5,244 NSE/BSE symbols
- **Effort**: 2-3 days (parallel extraction, 4 workers)
- **Impact**: +5% (5,244 symbols, India 22% → 27%)
- **Schedule**:
  - Start: 2026-07-30 (after US EDGAR loads)
  - Fix screener.in API: 2026-07-30
  - Extract: 2026-07-31 → 2026-08-01
  - Load: 2026-08-01 evening
  - Verify: 2026-08-02

**Scripts**: 
- `fix_india_data_sources.py` (diagnose)
- `run_india_screener_full.py` (extract with fallback)
- `edgar_cassandra_loader.sh` (load)

---

### 3. China A-Shares akshare (Priority 3)
- **Status**: ✅ Ready to schedule
- **Scope**: 5,188 symbols (refresh, 6d stale)
- **Effort**: 1-2 hours (post-12:30 IST)
- **Impact**: +0.4% (data continuity)
- **Schedule**:
  - Start: 2026-08-02 12:30 IST
  - Duration: 1-2 hours
  - Complete: 2026-08-02 evening

**Script**: `python3 china_akshare_collector.py --restart`

---

## 🎯 Phase 2: Deep Collection (Weeks 3-4)

### 4. Japan J-Quants (Priority 4)
- **Status**: 🟡 Validator exists, needs activation
- **Scope**: 1,788 JSE symbols
- **Effort**: 5-7 days (official API, high quality)
- **Impact**: +6% (1,788 symbols, Japan 0% → 75%+)
- **Schedule**:
  - Activate: 2026-08-03
  - Extract: 2026-08-03 → 2026-08-08
  - Load: 2026-08-08 evening
  - Verify: 2026-08-09

**Script**: `jquants_collector.py` (to be created from validator)

---

### 5. Korea KRX (Priority 5)
- **Status**: 🟡 Partial coverage
- **Scope**: 2,768 symbols
- **Effort**: 3-4 days
- **Impact**: +5% (2,768 symbols, Korea 0% → 100%)
- **Schedule**:
  - Start: 2026-08-09
  - Extract: 2026-08-09 → 2026-08-12
  - Load: 2026-08-12
  - Verify: 2026-08-13

**Data source**: FinanceDataReader (already integrated)

---

### 6. Europe (Priority 6)
- **Status**: 🟡 Partial coverage via yfinance
- **Scope**: 966 stocks (17 exchanges)
- **Effort**: 2-3 days
- **Impact**: +5% (966 symbols, Europe 0% → 100%)
- **Schedule**:
  - Start: 2026-08-13
  - Extract: 2026-08-13 → 2026-08-14
  - Load: 2026-08-14
  - Verify: 2026-08-15

**Data source**: yfinance (pre-suffixed tickers `.DE`, `.L`, `.PA`, etc.)

---

## 📋 Execution Schedule (Day by Day)

```
2026-07-28 (TODAY)
  09:00 - Launch US EDGAR extraction (2,200 symbols)
  [RUNNING: 4-6 hours]

2026-07-28 Evening
  16:00 - US EDGAR extraction complete
  17:00 - Load to Cassandra (1-2 hours)
  19:00 - US EDGAR load complete ✅

2026-07-29
  09:00 - Verify US completeness (+6%)
  10:00 - Fix/diagnose India screener.in
  14:00 - Start India NSE-BSE extraction

2026-07-30
  [RUNNING: India extraction continues]

2026-07-31
  [India extraction continues]
  
2026-08-01 Morning
  09:00 - India extraction complete
  10:00 - Load to Cassandra
  12:00 - India load complete ✅

2026-08-02 12:30
  12:30 - Launch China akshare collector (post-NSE firewall)
  14:00 - China update complete ✅

2026-08-03
  09:00 - Activate Japan J-Quants
  [RUNNING: 5-7 days]

2026-08-08
  [Japan extraction complete]
  09:00 - Load Japan to Cassandra
  11:00 - Japan load complete ✅

2026-08-09
  10:00 - Start Korea extraction
  
2026-08-12
  [Korea extraction complete]
  09:00 - Load Korea to Cassandra
  11:00 - Korea load complete ✅

2026-08-13
  10:00 - Start Europe extraction

2026-08-14
  [Europe extraction complete]
  09:00 - Load Europe to Cassandra
  11:00 - Europe load complete ✅

2026-08-15
  15:00 - FINAL COMPLETENESS AUDIT
```

---

## 🎯 Expected Outcomes

| Phase | Date | Market | Gain | Target Completeness |
|-------|------|--------|------|---------------------|
| Quick-win 1 | 2026-07-30 | US | +6% | 9.6% |
| Quick-win 2 | 2026-08-01 | India | +5% | 14.6% |
| Quick-win 3 | 2026-08-02 | China | +0.4% | 15% |
| Deep 1 | 2026-08-08 | Japan | +6% | 21% |
| Deep 2 | 2026-08-12 | Korea | +5% | 26% |
| Deep 3 | 2026-08-14 | Europe | +5% | 31% |
| **FINAL** | **2026-08-15** | **ALL** | **+27.3%** | **~50%+** |

---

## 🚀 Start Command (Immediate)

```bash
# Step 1: Launch US EDGAR extraction (NOW)
cd /Users/umashankar/market-pipeline/code/python_files
source ~/.venvs/edgar/bin/activate
python3 edgar_production_full.py --workers 8 --symbols-limit 2200 &

# Step 2: Monitor progress
tail -f reports/edgar_full_*.log

# Step 3: When done, load to Cassandra
bash edgar_cassandra_loader.sh

# Step 4: Verify
python3 data_completeness_audit.py
```

---

## 📊 Resource Requirements

| Phase | CPU | Memory | Disk | Duration |
|-------|-----|--------|------|----------|
| US EDGAR | 30% | 200 MB | 50 MB | 4-6 hrs |
| India screener | 25% | 300 MB | 100 MB | 2-3 days |
| China akshare | 10% | 100 MB | 50 MB | 1-2 hrs |
| Japan J-Quants | 20% | 200 MB | 150 MB | 5-7 days |
| Korea | 15% | 150 MB | 80 MB | 3-4 days |
| Europe yfinance | 25% | 200 MB | 70 MB | 2-3 days |
| **TOTAL** | - | - | **~500 MB** | **~18 days** |

---

## ✅ Quality Gates

Each phase must verify:

```bash
# After each collection:
1. Row count check
   cqlsh -e "SELECT COUNT(*) FROM herrrickshaw.stock_quotes WHERE market='$MARKET';"

2. Fundamentals coverage
   cqlsh -e "SELECT market, COUNT(pe), COUNT(pb), COUNT(roe) FROM herrrickshaw.stock_quotes WHERE market='$MARKET' GROUP BY market;"

3. Completeness audit
   python3 data_completeness_audit.py

# Success criteria: No errors, +X% gain verified
```

---

## 🔄 Fallback Plans

| Collector | If Fails | Fallback |
|-----------|----------|----------|
| screener.in API | ❌ Broken | Use yfinance for India fundamentals |
| J-Quants | ❌ Unavailable | Use yfinance for Japan |
| akshare | ❌ NSE firewall | Run post-12:30 IST from India IP |
| yfinance | ❌ Rate limited | Reduce workers, increase sleep |

---

## 📞 Contacts & Resources

- **EDGAR**: SEC EDGAR API (free, no auth)
- **screener.in**: Web scraper (API currently broken)
- **yfinance**: Yahoo Finance API (free, no auth)
- **akshare**: Chinese finance data (free)
- **J-Quants**: Japan Stock Exchange (free tier)
- **FinanceDataReader**: Korea data (free)

---

**Status**: ✅ Schedule ready  
**Start time**: 2026-07-28 (NOW)  
**Target completion**: 2026-08-15  
**Expected result**: 31.7% → ~50%+ completeness (full universe covered)

