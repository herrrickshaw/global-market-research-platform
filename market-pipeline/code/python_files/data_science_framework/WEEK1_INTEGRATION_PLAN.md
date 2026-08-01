# Week 1 Integration Plan: Piotroski + Framework

**Timeline:** 2026-08-05 to 2026-08-09  
**Goal:** Load Piotroski F-Score + ROCE quality metrics into FeatureEngineering layer  
**Owner:** Data Science Team

---

## Day 1 (Monday): Validation & Setup

### Task 1.1: Verify Piotroski Score Scale
**File:** `data_science_framework/core.py`  
**Goal:** Confirm score scale (0-9 standard vs 0-100 database)

```python
# Test script
import duckdb
conn = duckdb.connect('/Users/umashankar/market-pipeline/reports_local/global_fundamentals.duckdb')

# Check score distribution
dist = conn.execute("""
    SELECT MIN(piotroski), MAX(piotroski), COUNT(*), AVG(piotroski)
    FROM fundamentals
    WHERE piotroski IS NOT NULL
""").fetchall()

# Expected output:
# If 0-9 scale: min~0, max~9
# If 0-100 scale: min~8, max~100
# If percentile: min~0.08, max~1.0
```

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-05 EOD

---

### Task 1.2: Query All Markets
**Goal:** Get Piotroski data for IN/US/JP/KR/EU markets

```python
# Query template
SELECT DISTINCT market FROM fundamentals WHERE piotroski IS NOT NULL

# Then for each market:
SELECT ticker, piotroski, roce, roe, quality_score, market_cap_local
FROM fundamentals
WHERE market = 'IN'  -- repeat for US, JP, KR, EU
ORDER BY piotroski DESC
LIMIT 100
```

**Expected Output:**
| Market | Count | Status |
|--------|-------|--------|
| IN | ~2,000 | ⬜ |
| US | ~2,000 | ✓ |
| JP | ~1,000 | ⬜ |
| KR | ~1,000 | ⬜ |
| EU | ~500 | ⬜ |

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-05 EOD

---

### Task 1.3: Document DuckDB Schema
**Goal:** Map DuckDB columns to framework requirements

```
fundamentals table:
├── ticker (STRING) → Used as identifier
├── market (STRING) → Market partition (IN/US/JP/KR/EU)
├── piotroski (DOUBLE) → F-Score value (verify scale)
├── roce (DOUBLE) → ROCE % (capital efficiency)
├── roe (DOUBLE) → ROE % (equity efficiency)
├── quality_score (INTEGER) → Pre-calculated quality rating
├── sector (STRING) → Sector classification
├── industry (STRING) → Industry classification
└── market_cap_local (DOUBLE) → Market cap in local currency

TODO:
- Verify data types
- Check NULL handling
- Document any missing fields
- Note data freshness (update frequency)
```

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-05 EOD

---

## Day 2-3 (Tuesday-Wednesday): Feature Engineering Layer

### Task 2.1: Implement QualityFeaturesLoader
**File:** `data_science_framework/core.py`  
**Add to:** `FeatureEngineering` class

```python
class FeatureEngineering:
    @staticmethod
    def load_quality_scores(ticker: str, market: str) -> dict:
        """
        Load pre-calculated Piotroski + ROCE from DuckDB
        
        Returns:
        {
            'f_score': float (0-9 or 0-100, verify which),
            'roce_pct': float (0-100),
            'roe_pct': float (0-100),
            'quality_score': int (0-10?),
            'sector': str,
            'industry': str,
            'market_cap': float
        }
        """
        import duckdb
        
        conn = duckdb.connect('/path/to/global_fundamentals.duckdb')
        
        result = conn.execute("""
            SELECT piotroski, roce, roe, quality_score, sector, industry, market_cap_local
            FROM fundamentals
            WHERE ticker = ? AND market = ?
        """, [ticker, market]).fetchall()
        
        if result:
            return dict(zip(['f_score', 'roce_pct', 'roe_pct', 'quality_score', 
                            'sector', 'industry', 'market_cap'], result[0]))
        return None
```

**Acceptance Criteria:**
- [ ] Function loads data from DuckDB
- [ ] Returns dict with all required fields
- [ ] Handles missing tickers gracefully
- [ ] Performance: <100ms per ticker

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-06 EOD

---

### Task 2.2: Normalize Score Scale
**File:** `data_science_framework/core.py`  
**Goal:** Convert to standard 0-9 scale if database uses 0-100

```python
@staticmethod
def normalize_piotroski_score(raw_score: float, detected_scale: str) -> float:
    """
    Normalize Piotroski score to standard 0-9 scale
    
    Args:
        raw_score: Score from database
        detected_scale: 'standard' (0-9), 'percentile' (0-100), 'percentile_decimal' (0-1.0)
    
    Returns:
        Normalized score 0-9
    """
    if detected_scale == 'standard':
        return raw_score  # Already 0-9
    elif detected_scale == 'percentile':
        return raw_score / 100 * 9  # Convert 0-100 to 0-9
    elif detected_scale == 'percentile_decimal':
        return raw_score * 9  # Convert 0-1.0 to 0-9
    else:
        raise ValueError(f"Unknown scale: {detected_scale}")
```

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-06 EOD

---

### Task 2.3: Create Quality Type Classification
**File:** `data_science_framework/market_signals.py`  
**Add to:** `QualitySignals` class

```python
class QualitySignals:
    @staticmethod
    def classify_quality(f_score: float, roce_pct: float) -> dict:
        """
        Classify stock into quality type based on F-Score + ROCE
        
        Returns:
        {
            'type': 'STRONG' | 'GOOD' | 'TURNAROUND' | 'QUALITY_TRAP' | 'POOR',
            'confidence': 'HIGH' | 'MEDIUM' | 'LOW',
            'f_score_pct': float (0-100 for display),
            'roce_pct': float,
            'trade_signal': 'BUY' | 'WATCH' | 'HOLD' | 'AVOID'
        }
        """
        # Rules (f_score 0-9 scale):
        # STRONG: F >= 7 AND ROCE >= 2/3 (15% baseline)
        # GOOD: F >= 5 AND ROCE >= 1/3 (5% baseline)
        # TURNAROUND: F >= 5 AND ROCE < 1/3
        # QUALITY_TRAP: F < 5 AND ROCE >= 2/3 (good business, bad year)
        # POOR: F < 5 AND ROCE < 1/3
        
        pass
```

**Acceptance Criteria:**
- [ ] Classifies all 4 categories correctly
- [ ] Returns confidence level
- [ ] Generates appropriate trade signal
- [ ] Works with 0-9 and 0-100 score scales

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-06 EOD

---

## Day 4 (Thursday): Integration & Testing

### Task 3.1: Integrate with Daily Scanner
**File:** `market-pipeline/code/python_files/daily_scanner.py`  
**Goal:** Add quality signal to daily_darvas_scan()

```python
def enhanced_darvas_scan_with_quality(prices_dict, fundamentals_db_path):
    """
    Darvas scan enhanced with quality filtering
    
    Process:
    1. For each stock in prices_dict:
    2.   Load quality scores (F-Score, ROCE)
    3.   Classify quality type
    4.   Run Darvas signal
    5.   Combine: Darvas signal + Quality type
    6. Return BUY signals with HIGH quality only
    """
    pass
```

**Testing:**
- [ ] Load sample of 10 NSE stocks
- [ ] Verify quality scores load correctly
- [ ] Check Darvas + Quality composite works
- [ ] Performance: <1s for 100 stocks

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-07 EOD

---

### Task 3.2: Add Liquidity Tier Segmentation
**File:** `data_science_framework/market_signals.py`  
**Goal:** Segment stocks by liquidity before ranking

```python
@staticmethod
def segment_by_liquidity(stocks: pd.DataFrame, market_cap_col: str, 
                        volume_col: str) -> pd.DataFrame:
    """
    Segment stocks into liquidity tiers using % ADV (not size)
    
    % ADV = daily_volume_rupees / shares_outstanding
    
    Returns DataFrame with 'liquidity_tier' column:
    - 'ILLIQUID': bottom tercile (< 33rd percentile %ADV)
    - 'MID': middle tercile
    - 'LIQUID': top tercile (> 66th percentile %ADV)
    
    CRITICAL: Rank within tier, never across entire sample!
    Piotroski edge only exists in ILLIQUID stocks.
    """
    pass
```

**Acceptance Criteria:**
- [ ] Correctly calculates % ADV
- [ ] Segments into 3 tiers
- [ ] Handles missing volume data
- [ ] Performance: <100ms for 2000 stocks

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-07 EOD

---

### Task 3.3: Backtest Quality Signals on NSE (5-Year)
**File:** Create new: `data_science_framework/test_quality_backtest.py`  
**Goal:** Validate quality signals on historical data

```python
def backtest_quality_signals():
    """
    Walk-forward backtest of quality signals on NSE
    
    Period: 2021-01-01 to 2026-08-01 (5 years)
    Universe: NSE stocks with quality scores
    
    Signals:
    1. Darvas only (baseline)
    2. Darvas + Quality (new)
    
    Metrics:
    - Annual return
    - Sharpe ratio
    - Win rate
    - Max drawdown
    
    Expected result: +20-30% Sharpe improvement
    """
    pass
```

**Acceptance Criteria:**
- [ ] Loads 5-year NSE price data
- [ ] Gets quality scores for period
- [ ] Backtests both signals
- [ ] Produces Sharpe comparison
- [ ] Win rate > 50%

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-08 EOD

---

## Day 5 (Friday): Validation & Documentation

### Task 4.1: Validation Checklist
**Goal:** Verify everything works before staging deployment

- [ ] Quality scores load from DuckDB
- [ ] Score scale normalized correctly
- [ ] Quality types classified correctly
- [ ] Liquidity tier segmentation works
- [ ] Daily scanner runs without errors
- [ ] 5-year backtest shows improvement
- [ ] Performance targets met (<1s for 100 stocks)
- [ ] Code reviewed and documented

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-09 EOD

---

### Task 4.2: Generate Week 1 Summary Report
**File:** Create new: `data_science_framework/WEEK1_INTEGRATION_SUMMARY.md`  
**Contents:**
- What was integrated (F-Score + ROCE loading)
- Test results (5-year backtest Sharpe improvement)
- Production readiness assessment
- Known limitations (score scale, liquidity tier requirement)
- Week 2 roadmap

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-09 EOD

---

## Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Quality scores loaded | 100% | ⬜ |
| Score scale verified | ✓ | ⬜ |
| All 4 markets queryable | ✓ | ⬜ |
| Backtest Sharpe +20% | ✓ | ⬜ |
| Performance <1s/100 stocks | ✓ | ⬜ |
| Daily scanner integration | ✓ | ⬜ |
| Documentation complete | ✓ | ⬜ |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Score scale unknown | High | Task 1.1 - verify immediately |
| DuckDB query slow | Medium | Index tickers, cache results |
| Liquidity data missing | High | Use price volume as fallback |
| Backtest shows no improvement | High | Debug signal logic, verify data |
| Performance >1s | Medium | Use connection pooling, async |

---

## Daily Standup Template

**Date:** 2026-08-0X  
**Owner:** [Name]  

**Yesterday:**
- [ ] Task completed
- [ ] Status: ⬜ / 🟨 / ✅

**Today:**
- [ ] Task planned
- [ ] Blockers: None / [list]

**Blockers:**
- None / [describe]

---

## Week 1 Acceptance Criteria

✅ **All of the following must be true:**

1. Piotroski F-Score + ROCE successfully load from DuckDB
2. Score scale is verified and normalized to 0-9 standard
3. Quality type classification works (STRONG/GOOD/TURNAROUND/QUALITY_TRAP)
4. Liquidity tier segmentation implemented
5. 5-year NSE backtest shows ≥20% Sharpe improvement
6. Daily scanner integration complete
7. Performance: <1s for 100 stocks
8. All code documented with docstrings
9. No regressions in existing Darvas/RSI signals
10. Ready to deploy to staging

---

## Status Summary

**Created:** 2026-08-01  
**Start Date:** 2026-08-05  
**End Date:** 2026-08-09  
**Owner:** Data Science Team  
**Next Phase:** Week 2 - US Market Integration + Production Deployment

---

## Owner Sign-Off

- [ ] Reviewed by: ________________
- [ ] Approved by: ________________
- [ ] Date: ____________________

