# Week 1 Integration Plan: Piotroski + Framework

**Timeline:** 2026-08-05 to 2026-08-09  
**Goal:** Load Piotroski F-Score + ROCE quality metrics into FeatureEngineering layer  
**Owner:** Data Science Team

---

## Day 1 (Monday): Validation & Setup

### Task 1.1: Verify Piotroski Score Scale & Production Findings
**File:** `data_science_framework/core.py`  
**Goal:** Confirm score scale (0-9 standard vs 0-100 database) AND apply production learnings

**🔴 CRITICAL PRODUCTION FINDINGS (from prior backtests):**
- **US Piotroski is INVERTED in large-cap liquid stocks** (−1.7% edge)
- **Illiquid stocks show strongest edge** (+33.7% in LARGE+ILLIQUID, +13.8% in SMALL+ILLIQUID)
- **Liquidity tier segmentation is MANDATORY** — rank within tier, never across entire sample
- **%ADV (not market cap) determines liquidity** — use daily volume ÷ shares outstanding
- **ROCE ex-cash only** — cash inflates ROCE by +10% in large-caps vs small-caps (India data)
- **F-Score + ROCE correlation = +0.236** (near-zero) → keep them separate blocks

```python
# Task 1.1a: Verify score scale
import duckdb
conn = duckdb.connect('/Users/umashankar/market-pipeline/reports_local/global_fundamentals.duckdb')

# Check score distribution
dist = conn.execute("""
    SELECT MIN(piotroski), MAX(piotroski), COUNT(*), AVG(piotroski)
    FROM fundamentals
    WHERE piotroski IS NOT NULL
""").fetchall()

# Task 1.1b: Check ROCE calculation (must be ex-cash)
roce = conn.execute("""
    SELECT ticker, market, roce, market_cap_local, volume
    FROM fundamentals
    WHERE market = 'IN' AND piotroski >= 7
    ORDER BY roce DESC
    LIMIT 20
""").fetchall()

# VALIDATE: Highest ROCE should be moderate (15-40%), not extreme (>80%)
# If extreme, check if cash is excluded from denominator
```

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-05 EOD
**Critical:** This task unblocks liquidity tier architecture

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

### Task 3.2: Add Liquidity Tier Segmentation (🔴 CRITICAL)
**File:** `data_science_framework/market_signals.py`  
**Goal:** Segment stocks by liquidity BEFORE ranking — this determines profitability

🔴 **THIS DETERMINES SUCCESS OR FAILURE.** Production data shows:
- Rank across entire sample → Piotroski works in large-cap liquid only (−1.7% edge, NEGATIVE)
- Rank within illiquid tier → +33.7% edge (LARGE+ILLIQUID) or +13.8% (SMALL+ILLIQUID)

```python
@staticmethod
def calculate_percent_adv(prices_df: pd.DataFrame, volume_col: str, 
                         shares_outstanding: float) -> pd.Series:
    """
    % ADV = (median daily volume in dollars) / (shares outstanding × share price)
    
    This is the TRUE liquidity measure, independent of market cap.
    Use it, not market_cap, to segment the universe.
    """
    median_volume_dollars = (prices_df[volume_col] * prices_df['close']).median()
    market_cap_dollars = shares_outstanding * prices_df['close'].iloc[-1]
    return (median_volume_dollars / market_cap_dollars) * 100

@staticmethod
def segment_by_liquidity_adv(stocks: pd.DataFrame, shares_outstanding_col: str, 
                             prices_dict: dict) -> pd.DataFrame:
    """
    Segment stocks into liquidity tiers using % ADV (not size)
    
    Returns DataFrame with 'liquidity_tier' column:
    - 'ILLIQUID': bottom tercile (< 33rd percentile %ADV)
    - 'MID': middle tercile
    - 'LIQUID': top tercile (> 66th percentile %ADV)
    
    🔴 CRITICAL RULE: Rank within tier, NEVER across entire sample!
    
    Production backtest results (US, 2016-2025, 8 rebalances):
    | size | liquidity | edge |
    |------|-----------|------|
    | LARGE | ILLIQUID | +33.7% ← STRONGEST |
    | SMALL | ILLIQUID | +13.8% |
    | SMALL | LIQUID | +7.7% |
    | LARGE | LIQUID | -1.7% ← ONLY NEGATIVE |
    
    The edge lives in ILLIQUID names. Efficient pricing (LARGE+LIQUID)
    neutralizes Piotroski advantage — this is the market working correctly.
    """
    # Calculate % ADV for all stocks
    stocks['adv_pct'] = stocks.apply(
        lambda row: calculate_percent_adv(
            prices_dict[row['ticker']], 
            'volume',
            row[shares_outstanding_col]
        ), 
        axis=1
    )
    
    # Tercile segmentation
    terciles = stocks['adv_pct'].quantile([0.33, 0.67])
    
    stocks['liquidity_tier'] = pd.cut(
        stocks['adv_pct'],
        bins=[-np.inf, terciles[0.33], terciles[0.67], np.inf],
        labels=['ILLIQUID', 'MID', 'LIQUID']
    )
    
    return stocks

@staticmethod
def rank_within_tier(stocks: pd.DataFrame, score_col: str) -> pd.DataFrame:
    """
    RANK WITHIN liquidity tier only, never across.
    
    This is the load-bearing operation. Get this wrong and you flip from
    +33% edge to -1.7% edge (and don't know which).
    """
    stocks['rank_within_tier'] = stocks.groupby('liquidity_tier')[score_col].rank(ascending=False)
    return stocks
```

**Acceptance Criteria:**
- [ ] % ADV calculated correctly (dollar volume ÷ market cap)
- [ ] Segments into 3 tiers
- [ ] Ranking is WITHIN tier, not across
- [ ] Production backtest gradient confirmed (see table above)
- [ ] Performance: <100ms for 2000 stocks

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-07 EOD
**Critical blocking:** This step determines if strategy is profitable or negative

---

### Task 3.3: Backtest Quality Signals on NSE (5-Year)
**File:** Create new: `data_science_framework/test_quality_backtest.py`  
**Goal:** Validate quality signals on historical data WITH production safeguards

🔑 **PRODUCTION SAFEGUARDS (learned from prior backtests):**
1. **Report MEDIAN + MEAN** — mean is distorted by lottery winners
2. **Rank within liquidity tier** — don't rank across entire sample
3. **Market-specific rules work best:**
   - India: TREND following (+0.44 excess, Darvas/breakout works)
   - US: Mean-reversion (+0.41 excess, RSI oversold works)
   - Japan/Korea: Mean-reversion works
4. **Cost model:** Reality > simulated costs (assume 1-2% round-trip)
5. **Survivorship bias:** Delisted stocks have prices but no fundamentals
6. **Winsorize extremes:** 1st/99th percentile to avoid lottery tail

```python
def backtest_quality_signals():
    """
    Walk-forward backtest of quality signals on NSE
    
    Period: 2021-01-01 to 2026-08-01 (5 years)
    Universe: NSE stocks with quality scores
    
    Signals:
    1. Darvas only (baseline) ← India-specific trend signal
    2. Darvas + Quality (new overlay)
    
    Constraints:
    - Liquidity gate: Rs 1 crore/day minimum ADV
    - Rank within liquidity tier only
    - Report BOTH mean AND median returns
    - Winsorize 1/99 percentile per rebalance
    
    Metrics:
    - Annual return (mean + median)
    - Sharpe ratio (based on MEDIAN)
    - Win rate
    - Max drawdown
    - % ADV consumption (validate tradeable)
    
    Expected result (from production):
    - Baseline Darvas: ~8% annual, 0.6 Sharpe
    - Darvas + F≥7 overlay: ~12-14% annual, 0.85+ Sharpe
    - Key: overlay works as FILTER, not standalone signal
    - ⚠️ Piotroski alone is NEGATIVE in US large-cap (−4pp)
         but POSITIVE in India trending (+2.8pp at 252d)
    """
    import pandas as pd
    import numpy as np
    
    # Load NSE price data
    prices = load_nse_prices('2021-01-01', '2026-08-01')
    
    # Load quality scores (pre-calculated from DuckDB)
    quality = load_quality_scores_from_duckdb(market='IN')
    
    # Merge prices + quality
    data = prices.join(quality, how='inner')
    
    # Apply liquidity gate
    data = data[data['adv_rupees'] >= 1e7]  # Rs 1 crore/day
    
    # Backtest loop
    results = []
    for rebalance_date in monthly_rebalance_dates:
        # Segment by liquidity tier
        data_tier = segment_by_liquidity_adv(
            data.loc[:rebalance_date],
            shares_col='shares',
            prices_dict=prices
        )
        
        # Signal 1: Darvas only (trend signal for India)
        darvas_scores = TrendSignals.darvas_box(data_tier)
        
        # Signal 2: Darvas + Quality overlay
        quality_filter = data_tier['f_score'] >= 7
        signal_combined = (darvas_scores > threshold) & quality_filter
        
        # Winsorize to avoid lottery tail
        fwd_returns = calculate_forward_returns(data, rebalance_date, horizon=252)
        fwd_returns_winsorized = fwd_returns.clip(
            lower=fwd_returns.quantile(0.01),
            upper=fwd_returns.quantile(0.99)
        )
        
        # Metrics (REPORT BOTH MEAN AND MEDIAN)
        baseline_edge = fwd_returns_winsorized.median()
        combined_edge = fwd_returns_winsorized[signal_combined].median()
        
        results.append({
            'date': rebalance_date,
            'baseline_mean': fwd_returns_winsorized.mean(),
            'baseline_median': baseline_edge,
            'combined_mean': fwd_returns_winsorized[signal_combined].mean(),
            'combined_median': combined_edge,
            'win_rate': (fwd_returns[signal_combined] > 0).sum() / len(signal_combined),
            'n_signals': signal_combined.sum(),
            'pct_adv': (position_size / data_tier['adv_rupees']).max()
        })
    
    # Summary (emphasize median, highlight mean vs median split)
    df = pd.DataFrame(results)
    print(f"Baseline Sharpe (median): {df['baseline_median'].mean() / df['baseline_median'].std():.2f}")
    print(f"Combined Sharpe (median): {df['combined_median'].mean() / df['combined_median'].std():.2f}")
    print(f"Improvement: {(df['combined_median'] - df['baseline_median']).mean():.2f}pp")
    print()
    print("⚠️ Mean vs Median Split (lottery tail detection):")
    print(f"Baseline: mean {df['baseline_mean'].mean():.2f}% vs median {df['baseline_median'].mean():.2f}%")
    print(f"Combined: mean {df['combined_mean'].mean():.2f}% vs median {df['combined_median'].mean():.2f}%")
    
    return df
```

**Acceptance Criteria:**
- [ ] Loads 5-year NSE price data
- [ ] Gets quality scores from DuckDB (pre-calculated)
- [ ] Applies liquidity gate (Rs 1cr/day minimum)
- [ ] Ranks within liquidity tier only
- [ ] Reports MEDIAN + MEAN (separately)
- [ ] Winsorizes extremes (1/99 percentile)
- [ ] Win rate > 50%
- [ ] Median Sharpe > 0.6 (baseline), > 0.85 (combined)
- [ ] Validates % ADV consumption (should be <20%)
- [ ] Mean/median split analysis shows no lottery tail distortion

**Owner:** [Name]  
**Status:** ⬜ Not Started  
**Due:** 2026-08-08 EOD

**Key metric to watch:** If combined_median > baseline_median by >50bps, the overlay works

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

