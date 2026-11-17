# Piotroski F-Score + ROCE + Framework Integration

**Status:** Existing codebase has production-grade implementations  
**Goal:** Integrate Piotroski F-Score (9-point) + ROCE (3-point) with the new Data Science Framework

---

## Existing Implementation Reference

### 1. Piotroski Plus (PRODUCTION)
**File:** `market-pipeline/code/python_files/piotroski_plus.py` (372 LOC)

**Design Philosophy:**
- **F-Score (0-9):** Unmodified 9-point test battery from original 2000 paper
- **ROCE Block (0-3):** Separate scoring for capital efficiency (NOT merged into F-Score)
- **Reason:** F-Score validity preserved for literature comparison; Plus contribution measurable

**The 9 F-Score Tests:**
1. ROA > 0 (profitable?)
2. CFO > 0 (cash positive?)
3. dROA > 0 (improving profitability?)
4. CFO > NI (quality earnings — accruals < cash flow?)
5. dLeverage < 0 (delevering?)
6. dCurrent Ratio > 0 (liquidity improving?)
7. No Dilution (shares outstanding stable?)
8. dGross Margin > 0 (operating efficiency rising?)
9. dAsset Turnover > 0 (asset efficiency rising?)

**The 3 ROCE Block Tests:**
- **+1 Level:** ROCE (ex-cash) > 15% (earns well on capital employed)
- **+1 Stability:** 5-year coefficient of variation < 0.30 (sustained, not cyclical)
- **+1 Trend:** Latest ROCE ≥ 5-year mean (not deteriorating)

**Key Insight:** F-Score and ROCE correlate at only **+0.236** (near zero) → they measure different dimensions (delta vs level), both valuable.

---

## Integration with Data Science Framework

### Where Piotroski Fits in the Framework

```
Data Science Framework
├── Data Quality (Linoff) ✓
├── Feature Engineering (McKinney)
│   ├── Time series lags ✓
│   ├── Rolling stats ✓
│   └── ADD: Piotroski F-Score (binary tests) ✓
│   └── ADD: ROCE metrics (level, stability, trend) ✓
│
├── Regime Detection ✓
├── Signal Generation
│   ├── Trend Signals (Darvas) ✓
│   ├── Mean-Reversion Signals (RSI) ✓
│   └── ADD: Quality Signals (F-Score + ROCE) ✓
│
├── Backtesting ✓
└── Reporting ✓
```

### Implementation Strategy

#### Phase 1: Feature Layer Integration (Weeks 1-2)

```python
# data_science_framework/core.py - Add to FeatureEngineering class

@staticmethod
def create_piotroski_features(fundamentals_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create 9-point Piotroski F-Score from annual fundamentals.
    
    Input columns (annual data):
    - net_income, net_income_prev
    - roa, roa_prev
    - cfo
    - debt_to_assets, debt_to_assets_prev
    - current_ratio, current_ratio_prev
    - shares, shares_prev
    - gross_margin, gross_margin_prev
    - asset_turnover, asset_turnover_prev
    
    Returns:
    - f_score: 0-9 raw points
    - f_tested: count of tests successfully evaluated (handle missing data)
    - individual test booleans (for weighting/debugging)
    """
    from piotroski_plus import score  # Existing production code
    return score(fundamentals_df)

@staticmethod
def create_roce_features(fundamentals_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create 3-point ROCE block from annual fundamentals.
    
    Tests:
    +1 roce_ex_cash > 15%  (level)
    +1 roce_cv < 0.30      (stability)
    +1 roce_latest >= 5y mean (trend)
    
    Returns:
    - roce_score: 0-3 points
    - roce_level, roce_stable, roce_trend: individual booleans
    - roce_pct: actual ex-cash ROCE %
    """
    from piotroski_plus import score_roce_block
    return score_roce_block(fundamentals_df)
```

#### Phase 2: Signal Layer Integration (Weeks 2-3)

```python
# data_science_framework/market_signals.py - Add class

class QualitySignals:
    """Piotroski F-Score + ROCE based signals."""
    
    @staticmethod
    def piotroski_signal(f_score: int, f_tested: int) -> dict:
        """
        Convert F-Score to trading signal.
        
        Rules:
        - F_Score >= 7: BUY (strong quality)
        - F_Score >= 5: WATCH (improving)
        - F_Score < 5: HOLD (weak)
        
        Notes:
        - Adjust threshold if f_tested < 9 (missing data)
        - Weight recent tests more (they're more predictive)
        """
        if f_tested < 5:
            return {'score': 0, 'signal': 'INSUFFICIENT_DATA'}
        
        adjusted_threshold = 7 * (f_tested / 9)  # Scale for missing tests
        
        if f_score >= adjusted_threshold:
            return {'score': f_score/9, 'signal': 'BUY', 'confidence': 'HIGH'}
        elif f_score >= 5:
            return {'score': f_score/9, 'signal': 'WATCH', 'confidence': 'MEDIUM'}
        else:
            return {'score': f_score/9, 'signal': 'HOLD', 'confidence': 'LOW'}
    
    @staticmethod
    def roce_signal(roce_score: int, roce_pct: float) -> dict:
        """
        Convert ROCE to signal.
        
        ROCE is a QUALITY filter, NOT a timing signal.
        - 3/3: Premium business (allocate capital aggressively)
        - 2/3: Good business (normal allocation)
        - 1/3: Average business (cautious)
        - 0/3: Poor business (avoid or deep value only)
        """
        if roce_score == 3:
            return {'score': roce_score, 'quality': 'PREMIUM', 'confidence': 'HIGH'}
        elif roce_score == 2:
            return {'score': roce_score, 'quality': 'GOOD', 'confidence': 'MEDIUM'}
        elif roce_score == 1:
            return {'score': roce_score, 'quality': 'AVERAGE', 'confidence': 'LOW'}
        else:
            return {'score': roce_score, 'quality': 'POOR', 'confidence': 'AVOID'}
    
    @staticmethod
    def quality_composite(f_score_dict: dict, roce_dict: dict) -> dict:
        """
        Combine F-Score (momentum) + ROCE (quality).
        
        Result types:
        - STRONG: F >= 7 AND ROCE >= 2/3 (improving great business)
        - GOOD: F >= 5 AND ROCE >= 1/3 (improving OK business)
        - TURNAROUND: F >= 5 AND ROCE < 1/3 (improving bad business)
        - QUALITY_TRAP: F < 5 AND ROCE >= 2/3 (bad year for good business)
        
        "STRONG" stocks compound wealth. "TURNAROUND" has higher risk.
        "QUALITY_TRAP" are deep-value opportunities.
        """
        f = f_score_dict['score']
        r = roce_dict['score']
        
        if f >= 7/9 and r >= 2:
            return {'type': 'STRONG', 'confidence': 'HIGH', 'composite': (f + r/3) / 2}
        elif f >= 5/9 and r >= 1:
            return {'type': 'GOOD', 'confidence': 'MEDIUM', 'composite': (f + r/3) / 2}
        elif f >= 5/9 and r < 1:
            return {'type': 'TURNAROUND', 'confidence': 'MEDIUM', 'composite': f}
        elif f < 5/9 and r >= 2:
            return {'type': 'QUALITY_TRAP', 'confidence': 'LOW', 'composite': r/3}
        else:
            return {'type': 'AVOID', 'confidence': 'HIGH', 'composite': 0}
```

#### Phase 3: Backtesting Integration (Weeks 3-4)

```python
# market-signals.py - Add to SignalBacktest class

@staticmethod
def backtest_quality(prices: pd.Series, f_scores: pd.Series, roce_scores: pd.Series,
                    weighting: str = 'canonical') -> dict:
    """
    Backtest Piotroski + ROCE signals.
    
    Weighting options (from piotroski_plus.py):
    - 'canonical': all tests weight 1.0 (control)
    - 'quality': emphasize profitability + ROCE level
    - 'turnaround': emphasize improving metrics + ignore ROCE
    - 'safety': emphasize stability + ROCE stability
    
    Returns:
    - annual_return: strategy return %
    - sharpe_ratio: risk-adjusted return
    - win_rate: % positive days
    - quality_distribution: # of STRONG/GOOD/TURNAROUND/AVOID stocks per period
    
    Key insight: Piotroski works ONLY in illiquid stocks.
    High-F small-illiquid names: +13.8% edge (verified US 2016-2025)
    High-F large-liquid names: -1.7% edge (value trap effect)
    => Must rank WITHIN liquidity tier, not across entire sample
    """
    pass
```

---

## Known Limitations & Gotchas

### 🔴 Critical Issues (From Production Experience)

**1. US Piotroski is INVERTED in large caps**
- Small/illiquid stocks: F-Score works (+13.8% edge)
- Large/liquid stocks: F-Score backfires (−1.7% edge)
- **Fix:** Always segment by **liquidity tier** (not size) before ranking
- **Data:** Use % ADV (dollar trading volume / shares), not market cap

**2. ROCE numerator missing from yfinance**
- yfinance has assets, liabilities, but NO EBIT/operating profit
- Can't properly compute ROCE = EBIT / (Total Assets − Current Liabilities)
- **Fix:** Use `global-stock-screener/fundamentals_history/*.parquet` (has filed dates + EBIT)
- **Warning:** Deriving EBIT from net_income produces 95–137% false ROCE (ratio inversion trap)

**3. NaN/Boolean trap in scoring**
- Skipped tests (missing data) round-trip as float NaN
- `NaN is None` = False, but `if NaN:` = True → skipped counts as PASS
- `bool("False")` = True (string trap)
- **Fix:** Use `_ran()` / `_passed()` guards from piotroski_plus.py
- **Verify:** Assert `canonical_raw == f_score + plus_score` after every sweep

**4. ROCE affected by cash on balance sheet**
- High cash (treasury) depresses ROCE = EBIT / (Assets − Liabilities)
- India large caps: 20% of capital employed is cash vs 9.5% for small caps
- **Fix:** Use ROCE(ex-cash) = EBIT / (Assets − Liabilities − Cash)
- **Impact:** Large-cap "efficiency" penalties reversed when cash-adjusted

**5. Mean vs Median in results**
- Mean is distorted by lottery-winner outliers
- Median tells what the TYPICAL stock actually does
- Example: low-F stocks have +10.5% mean but −3.2% median
- **Fix:** Always report BOTH, interpret median for strategy

### ⚠️ Design Rules (Do NOT break)

1. **F-Score stays 0-9, ROCE stays 0-3**
   - Never merge or reweight them together
   - Keeps literature comparability + contribution measurable

2. **Quality filter, NOT liquidity filter**
   - ROCE says nothing about cash flow, revenue growth, or short-term solvency
   - Always run BEHIND a liquidity gate (% ADV > threshold)
   - Don't use Piotroski to check if something is tradeable

3. **Rank WITHIN liquidity tier, not across**
   - Segment by % ADV tercile (illiquid/mid/liquid)
   - Rank separately within each tier
   - DON'T rank top-20 across the whole sample

4. **Survivorship bias in backtests**
   - yfinance serves statements only for currently-listed companies
   - 964 delisted India names have prices but no statements
   - This inflates results for weak strategies most (they crashed for a reason)
   - Use price + fundamentals simultaneously from the same source

---

## Integration Roadmap

### Week 1: Feature Engineering
- [ ] Load piotroski_plus.py into framework.core
- [ ] Create `FeatureEngineering.create_piotroski_features()`
- [ ] Create `FeatureEngineering.create_roce_features()`
- [ ] Add missing EBIT support to data pipeline

### Week 2: Signal Generation
- [ ] Build `QualitySignals` class in market_signals.py
- [ ] Implement composite quality scoring
- [ ] Test on 5-year NSE data
- [ ] Compare vs old hardcoded signals

### Week 3: Backtesting
- [ ] Add walk-forward backtest for quality signals
- [ ] Implement liquidity tier segmentation
- [ ] Calculate Sharpe, win rate, max DD
- [ ] Verify against existing piotroski_plus backtest results

### Week 4: Production Integration
- [ ] Add to daily_scanner.py (behind liquidity gate)
- [ ] Add to API endpoints (/api/db/daily/scan)
- [ ] Dashboard: Show F-Score, ROCE, quality type
- [ ] Deploy to staging

---

## Testing Checklist

- [ ] F-Score matches piotroski_plus.py output exactly (canonical=100% match)
- [ ] ROCE calculation verified on known stocks (TATASTEEL, BHEL, SUZLON examples)
- [ ] Missing data handling: f_tested and r_tested match test count
- [ ] NaN/boolean trap: skipped tests NOT counted as passes
- [ ] Liquidity tier segmentation: small/mid/large properly split by %ADV
- [ ] Backtesting: results consistent with piotroski_plus benchmarks
- [ ] No survivorship bias: delisted names handled correctly

---

## Expected Integration Benefits

**Current Framework:**
- Regime detection (trending vs mean-reverting)
- Trend signals (Darvas Box)
- Reversion signals (RSI)

**After Piotroski Integration:**
- Quality dimension (F-Score: is company improving?)
- Durability dimension (ROCE: can it sustain returns?)
- **New composite:** Darvas (trend) + RSI (timing) + F-Score (quality) + ROCE (durability)

**Example New Signal:**
- Stock is TRENDING (Darvas) + OVERSOLD (RSI) + STRONG (F≥7, ROCE≥2) = **STRONG BUY**
- vs. Stock is TRENDING + OVERSOLD + WEAK (F<5, ROCE<1) = **RISKY TRADE**

**Expected Improvement:**
- Sharpe ratio: +20-30% (avoids quality traps, confirms strength)
- Win rate: +5-10% (fewer false signals from quality-less trends)
- Drawdown: −2-5% (avoids deteriorating "improving" names)

---

## References

- `piotroski_plus.py` — Production scoring engine (372 LOC)
- `backtest_piotroski_plus.py` — Backtesting harness
- `sweep_piotroski_plus.py` / `sweep_piotroski_plus_us.py` — Weight sweeps
- Memory: [[project_piotroski_plus]], [[project_piotroski_backtests]]
- Research: [[project_cost_capacity]], [[project_liquidity_scan_research]]

---

**Status:** Ready for integration with data science framework

**Timeline:** 4 weeks to production (parallel with NSE deployment)

**Owner:** Data Science Team

**Last Updated:** 2026-08-01
