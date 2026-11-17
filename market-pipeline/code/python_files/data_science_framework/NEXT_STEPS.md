# Next Steps: Week 1 Integration Roadmap

**Current Status:** Framework + Piotroski docs committed, Task 1.1 verification script ready  
**Start Date:** Monday 2026-08-05  
**Timeline:** 5 business days  
**Owner:** Data Science Team

---

## 🎯 Critical Path (Must Complete by Friday)

### BLOCKERS (Do First)
These must be done before any backtesting:

#### 1. **Task 1.1: Verify Score Scale** ⏰ Due Monday EOD
**Script:** `task_1_1_verification.py`

```bash
cd market-pipeline/code/python_files/data_science_framework
python3 task_1_1_verification.py
```

**Decision Points:**
- [ ] Is ROCE max < 100%? YES → Proceed | NO → Flag for correction
- [ ] Is F-Score in 0-9 or 0-12 range? YES → Proceed | NO → Plan normalization
- [ ] Is India coverage > 80%? YES → Ready for backtest
- [ ] Is US coverage > 80%? YES → Ready for backtest

**Blockers on this:**
- ✅ Script exists
- ✅ Database path known
- ⏳ Requires: duckdb + pandas (one-time install)

**Unblocks:**
→ Task 1.2 (Query all markets)  
→ Task 2.1 (Load into FeatureEngineering)

---

#### 2. **Task 1.2: Query All Markets** ⏰ Due Monday EOD
**Goal:** Confirm Piotroski data exists for IN/US/JP/KR/EU

**Create script:** `task_1_2_market_query.py`

```python
# Pseudo-code
import duckdb

markets = ['IN', 'US', 'JP', 'KR', 'EU']

for market in markets:
    query = f"""
        SELECT COUNT(*), 
               COUNT(CASE WHEN piotroski IS NOT NULL THEN 1 END) as f_score_count,
               COUNT(CASE WHEN roce IS NOT NULL THEN 1 END) as roce_count
        FROM fundamentals
        WHERE market = '{market}'
    """
    result = conn.execute(query).fetchall()
    
    # Output: Market | Total | F-Score | ROCE | Coverage %
    print(f"{market}: {result[0][0]} total, {result[0][1]} F-Score, {result[0][2]} ROCE")
```

**Success Criteria:**
- [ ] All 5 markets queryable
- [ ] IN/US coverage > 80%
- [ ] JP/KR/EU coverage > 50% (minimum for Phase 2)

**Known Risks:**
- JP/KR/EU may have < 50% coverage (yfinance limitations)
- If JP/KR/EU sparse: Fall back to IN/US for Week 1, expand Week 2

**Unblocks:**
→ Task 3.3 (Multi-market backtest scope)

---

### IMPLEMENTATION (Tue-Wed)

#### 3. **Task 2.1: Load Quality Features** ⏰ Due Wednesday EOD
**File:** `core.py` → Add to `FeatureEngineering` class

**Implement:**
```python
@staticmethod
def load_quality_scores(ticker: str, market: str) -> dict:
    """Load pre-calculated F-Score + ROCE from DuckDB"""
    import duckdb
    conn = duckdb.connect(DB_PATH)
    result = conn.execute("""
        SELECT piotroski, roce, roe, quality_score, sector, industry
        FROM fundamentals
        WHERE ticker = ? AND market = ?
    """, [ticker, market]).fetchall()
    
    if result:
        return {
            'f_score': result[0][0],
            'roce_pct': result[0][1],
            'roe_pct': result[0][2],
            'quality_score': result[0][3],
            'sector': result[0][4],
            'industry': result[0][5]
        }
    return None

@staticmethod
def normalize_piotroski_score(raw_score: float, detected_scale: str) -> float:
    """Normalize to 0-9 standard (from Task 1.1 findings)"""
    if detected_scale == 'standard':
        return raw_score  # Already 0-9
    elif detected_scale == 'percentile':
        return raw_score / 100 * 9  # Convert 0-100 to 0-9
    else:
        raise ValueError(f"Unknown scale: {detected_scale}")
```

**Test:** Can load NVDA, MSFT from US? Can load RELIANCE, TCS from IN?

**Acceptance Criteria:**
- [ ] Connects to DuckDB
- [ ] Loads F-Score for sample stocks
- [ ] Normalizes score to 0-9 range
- [ ] Returns all required fields
- [ ] Performance <100ms per ticker

**Unblocks:**
→ Task 2.3 (Quality type classification)

---

#### 4. **Task 2.3: Quality Classification** ⏰ Due Wednesday EOD
**File:** `market_signals.py` → Add `QualitySignals` class

**Implement:**
```python
class QualitySignals:
    @staticmethod
    def classify_quality(f_score: float, roce_pct: float) -> dict:
        """Classify into STRONG/GOOD/TURNAROUND/QUALITY_TRAP/POOR"""
        
        # Convert to 0-9 scale if needed (from Task 2.1)
        f_normalized = f_score if f_score <= 9 else f_score / 100 * 9
        
        if f_normalized >= 7 and roce_pct >= 15:
            quality_type = 'STRONG'  # Improving + good business
        elif f_normalized >= 5 and roce_pct >= 5:
            quality_type = 'GOOD'  # Improving + OK business
        elif f_normalized >= 5 and roce_pct < 5:
            quality_type = 'TURNAROUND'  # Improving + bad business
        elif f_normalized < 5 and roce_pct >= 15:
            quality_type = 'QUALITY_TRAP'  # Bad year + good business
        else:
            quality_type = 'POOR'  # Bad year + bad business
        
        return {
            'type': quality_type,
            'confidence': 'HIGH' if abs(f_normalized - 4.5) > 2 else 'MEDIUM',
            'f_score_normalized': f_normalized,
            'roce_pct': roce_pct,
            'trade_signal': {
                'STRONG': 'BUY',
                'GOOD': 'WATCH',
                'TURNAROUND': 'WATCH',
                'QUALITY_TRAP': 'HOLD',
                'POOR': 'AVOID'
            }[quality_type]
        }
```

**Test:** Classify NVDA (F≥7, ROCE 22%), TATASTEEL (F≥7, ROCE 12%)

**Acceptance Criteria:**
- [ ] Classifies all 5 types correctly
- [ ] Returns confidence level
- [ ] Generates appropriate trade signal
- [ ] Handles both 0-9 and 0-100 scales

**Unblocks:**
→ Task 3.2 (Liquidity tier segmentation)

---

### TESTING & VALIDATION (Thu-Fri)

#### 5. **Task 3.2: Liquidity Tier Segmentation** ⏰ Due Thursday EOD
**File:** `market_signals.py` → Add to `SignalComposition` class

**🔴 CRITICAL:** This determines success (+33.7% edge) or failure (-1.7%)

**Implement:**
```python
@staticmethod
def calculate_percent_adv(prices_series: pd.Series, volume_series: pd.Series) -> float:
    """% ADV = (median daily volume $) / (market cap $)"""
    median_volume_dollars = (prices_series * volume_series).median()
    market_cap = prices_series.iloc[-1] * volume_series.sum()  # Approximate
    return (median_volume_dollars / market_cap) * 100

@staticmethod
def segment_by_liquidity(stocks_df: pd.DataFrame) -> pd.DataFrame:
    """Create liquidity_tier column: ILLIQUID / MID / LIQUID"""
    stocks_df['liquidity_pct'] = stocks_df.apply(
        lambda row: calculate_percent_adv(row['prices'], row['volume']),
        axis=1
    )
    
    tercile_33 = stocks_df['liquidity_pct'].quantile(0.33)
    tercile_67 = stocks_df['liquidity_pct'].quantile(0.67)
    
    stocks_df['liquidity_tier'] = pd.cut(
        stocks_df['liquidity_pct'],
        bins=[-np.inf, tercile_33, tercile_67, np.inf],
        labels=['ILLIQUID', 'MID', 'LIQUID']
    )
    
    # CRITICAL: Rank WITHIN tier only
    stocks_df['rank_within_tier'] = stocks_df.groupby('liquidity_tier')[
        'quality_score'
    ].rank(ascending=False)
    
    return stocks_df
```

**Test on 10 NSE stocks:**
- [ ] Calculates % ADV correctly
- [ ] Segments into 3 tiers
- [ ] Ranking is WITHIN tier, not across
- [ ] Validates production gradient (ILLIQUID >> LIQUID)

**Acceptance Criteria:**
- [ ] % ADV calculation correct
- [ ] Tercile segmentation works
- [ ] Ranking enforced within tier
- [ ] Performance <100ms for 2000 stocks
- [ ] Can reproduce production edge pattern

**Unblocks:**
→ Task 3.3 (5-year backtest)

---

#### 6. **Task 3.3: 5-Year NSE Backtest** ⏰ Due Friday EOD
**File:** `test_quality_backtest.py`

**Implement:**
```python
def backtest_quality_signals():
    """Walk-forward backtest with mean/median split reporting"""
    
    prices = load_nse_prices('2021-01-01', '2026-08-01')
    quality = load_quality_scores(market='IN')
    
    # Liquidity gate: Rs 1 crore/day
    data = merge_and_gate(prices, quality, min_adv_rupees=1e7)
    
    results = []
    for rebalance_date in monthly_dates('2021-01-01', '2026-08-01'):
        # Segment by liquidity
        tiered = segment_by_liquidity(data.loc[:rebalance_date])
        
        # Signal: Darvas + Quality overlay
        darvas_score = TrendSignals.darvas_box(tiered)
        quality_filter = tiered['f_score'] >= 7
        
        # Calculate forward returns (winsorized)
        fwd_returns = calculate_forward_returns(data, rebalance_date, 252)
        fwd_returns_ws = fwd_returns.clip(
            lower=fwd_returns.quantile(0.01),
            upper=fwd_returns.quantile(0.99)
        )
        
        results.append({
            'date': rebalance_date,
            'baseline_mean': fwd_returns_ws.mean(),
            'baseline_median': fwd_returns_ws.median(),
            'combined_mean': fwd_returns_ws[quality_filter].mean(),
            'combined_median': fwd_returns_ws[quality_filter].median(),
            'win_rate': (fwd_returns[quality_filter] > 0).sum() / quality_filter.sum(),
            'mean_median_spread': fwd_returns_ws.mean() - fwd_returns_ws.median(),
            'n_signals': quality_filter.sum()
        })
    
    # Report with emphasis on MEDIAN
    df = pd.DataFrame(results)
    print("BASELINE (Darvas only):")
    print(f"  Mean:   {df['baseline_mean'].mean():+.2f}%")
    print(f"  Median: {df['baseline_median'].mean():+.2f}%")
    print(f"  Sharpe (median): {df['baseline_median'].mean() / df['baseline_median'].std():.2f}")
    print()
    print("COMBINED (Darvas + Quality):")
    print(f"  Mean:   {df['combined_mean'].mean():+.2f}%")
    print(f"  Median: {df['combined_median'].mean():+.2f}%")
    print(f"  Sharpe (median): {df['combined_median'].mean() / df['combined_median'].std():.2f}")
    print()
    print("IMPROVEMENT:")
    print(f"  Median edge: {(df['combined_median'] - df['baseline_median']).mean():+.2f}pp")
    print(f"  Mean-median split: {df['mean_median_spread'].mean():+.2f}pp (watch for lottery tail)")
    
    return df
```

**Success Targets:**
- [ ] combined_median > baseline_median by ≥50bps
- [ ] Sharpe > 0.6 (baseline), > 0.85 (combined)
- [ ] Win rate > 50%
- [ ] % ADV < 20% (tradeable)
- [ ] Mean-median spread < 5pp (no lottery tail)

**Expected Result (from production):**
```
Baseline:  +8.2% annual, 0.6 Sharpe
Combined: +12-14% annual, 0.85+ Sharpe
Improvement: +400-600 bps
```

**Unblocks:**
→ Daily scanner integration (Week 2)

---

## 🚨 Risk Mitigation

### If Task 1.1 Fails

| Finding | Action |
|---------|--------|
| ROCE max > 100% | Add ex-cash correction; test on known stocks (RELIANCE) |
| F-Score scale unknown | Implement all 3 normalizations (0-9, 0-12, 0-100) and test |
| India coverage < 50% | Fall back to US only for Week 1; defer India to Week 2 |
| US coverage < 50% | Use cached fundamentals_history/US.parquet instead |

### If Task 3.3 Shows Negative Edge

| Symptom | Debug Step |
|---------|-----------|
| combined_median < baseline | Check if liquidity tier segmentation is working (rank_within_tier) |
| combined_median = baseline | Quality filter may be too weak; lower F-threshold to ≥5 |
| High mean but low median | Lottery tail detected; check for lookahea bias or survivorship |
| Sharpe < 0.6 even baseline | NSE fundamentals data may be stale; verify data freshness |

---

## 📅 Weekly Schedule

### Monday (Aug 5)
- [ ] Task 1.1: Verify score scale
- [ ] Task 1.2: Query all markets
- [ ] Decision: Proceed or revise

### Tuesday-Wednesday (Aug 6-7)
- [ ] Task 2.1: Load quality features into core.py
- [ ] Task 2.3: Create QualitySignals class
- [ ] Unit tests for both

### Thursday (Aug 8)
- [ ] Task 3.2: Implement liquidity tier segmentation
- [ ] Test on 10-stock sample
- [ ] Validate production gradient

### Friday (Aug 9)
- [ ] Task 3.3: Run 5-year backtest
- [ ] Generate summary report
- [ ] Create Week 1 summary document

---

## ✅ Week 1 Completion Criteria

**All of these must be true:**

1. ✅ Piotroski score scale verified + normalized to 0-9
2. ✅ ROCE ex-cash validated (max < 100%)
3. ✅ Quality scores load from DuckDB for IN/US
4. ✅ Quality type classification works (STRONG/GOOD/TURNAROUND/QUALITY_TRAP/POOR)
5. ✅ Liquidity tier segmentation implemented + tested
6. ✅ 5-year NSE backtest complete
7. ✅ Median edge ≥ 50bps improvement
8. ✅ Sharpe ratio improved to >0.85
9. ✅ No regressions in Darvas/RSI signals
10. ✅ Ready for daily_scanner.py integration (Week 2)

---

## 🔗 Dependencies & Blockers

```
Task 1.1 ──┬─→ Task 1.2 ──┐
           │              ├─→ Task 3.3 (backtest)
Task 2.1 ──┤              │
           ├─→ Task 2.3 ──┤
Task 3.2 ──┴──────────────┘
```

**Cannot start:** 2.1, 2.3 until 1.1 complete  
**Cannot start:** 3.2 until 2.3 complete  
**Cannot start:** 3.3 until all prior tasks complete

---

## 📊 Success Metrics Dashboard

Track daily:

| Task | Target | Mon | Tue | Wed | Thu | Fri |
|------|--------|-----|-----|-----|-----|-----|
| 1.1 Validation | ✅ | [ ] | | | | |
| 1.2 Markets | ✅ | [ ] | | | | |
| 2.1 Load Features | ✅ | | [ ] | [ ] | | |
| 2.3 Classification | ✅ | | [ ] | [ ] | | |
| 3.2 Liquidity Tier | ✅ | | | [ ] | [ ] | |
| 3.3 Backtest | ≥50bps | | | | [ ] | [ ] |
| Final Report | ✅ | | | | | [ ] |

---

## 🎯 Go/No-Go Decision Points

### Monday EOD (after Task 1.1 + 1.2)
**Question:** Do we have clean Piotroski data for IN/US?
- **YES** → Proceed to Day 2
- **NO** → Spend Tuesday fixing data, push backtest to Wed

### Wednesday EOD (after Task 2.1 + 2.3)
**Question:** Do quality scores load and classify correctly?
- **YES** → Proceed to liquidity tier work
- **NO** → Debug DuckDB connection, push to Thursday

### Thursday EOD (after Task 3.2)
**Question:** Does liquidity tier segmentation validate production edge?
- **YES** → Run full backtest Friday
- **NO** → Debug rank_within_tier logic, trim scope (IN only)

### Friday EOD (after Task 3.3)
**Question:** Does backtest show ≥50bps improvement?
- **YES** → ✅ Week 1 SUCCESS, prepare for Week 2
- **NO** → Document findings, iterate on quality thresholds next week

---

## 📝 Deliverables

**By Friday EOD, commit to repo:**

```
data_science_framework/
├── core.py                      # Updated FeatureEngineering
├── market_signals.py            # New QualitySignals class
├── test_quality_backtest.py     # 5-year backtest script
├── WEEK1_INTEGRATION_SUMMARY.md # Results + metrics
└── reports/
    └── backtest_quality_report_2026-08-01.csv
```

**Report should contain:**
- Score scale finding (0-9 confirmed)
- ROCE ex-cash validation (max value)
- Quality type distribution (STRONG/GOOD/TURNAROUND/TRAP/POOR %)
- Backtest results (mean + median, both)
- Sharpe improvement vs baseline
- Liquidity tier edge pattern
- Mean-median spread analysis
- Ready-for-production checklist

---

## 🚀 Ready to Start?

**Monday checklist:**
- [ ] Install duckdb: `pip install --user duckdb pandas`
- [ ] Download `task_1_1_verification.py`
- [ ] Run: `python3 task_1_1_verification.py`
- [ ] Record findings in team tracker
- [ ] Slack results to team

**GO!**
