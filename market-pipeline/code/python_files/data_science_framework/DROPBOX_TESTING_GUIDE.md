# Dropbox Data Testing Guide

## Framework Testing on Real Market Data

This guide walks you through testing the complete data science framework on your actual Dropbox market data.

---

## What's Available in Dropbox

### Market Data Structure

```
/market-data-backup/
├── current/
│   ├── fundamentals_history/     ← Historical fundamentals (PE, ROE, etc.)
│   ├── reference/                ← Reference data (symbols, exchanges)
│   ├── pipeline-market_cache/    ← Market cache for NSE/US/Europe
│   ├── gmd-cache_seed/           ← Global Market Data seed files
│   ├── pipeline-reports/         ← Generated reports
│   ├── gmd-warehouse/            ← Data warehouse tables
│   ├── correlation-scan/         ← Signal correlation analysis
│   └── fundamentals/             ← Current fundamentals
│
├── history/                      ← Historical backtest data
│   ├── 2024/
│   ├── 2025/
│   ├── 2026/
│   └── cache_seed/               ← Long-term market data
│
└── market_cache/                 ← Fast-access price cache
```

---

## Framework Components to Test

### 1. **Data Quality Assessment**
Test: DataQualityReport
- Load OHLCV data from `pipeline-market_cache`
- Check: missing percentages, duplicates, date ranges
- Expected: 95%+ data completeness for active securities

### 2. **Feature Engineering**
Test: FeatureEngineering
- Create lag features (1, 5, 20 days)
- Rolling statistics (SMA 20, 50, 200)
- Regime features (trending vs mean-reverting)
- Expected: 20+ engineered features per stock

### 3. **Regime Detection**
Test: RegimeDetection
- Calculate Hurst exponent on price series
- Classify regime: trending (>0.55), random (0.45-0.55), mean-reverting (<0.45)
- Measure regime accuracy against known market phases
- Expected: 65%+ regime classification accuracy

### 4. **Signal Generation**
Test: TrendSignals + MeanReversionSignals
- Darvas Box: detect 52W high + above EMA50
- RSI: identify oversold (<30) and overbought (>70)
- Signal composition: weighted combination
- Expected: 30-40% signal hit rate

### 5. **Backtesting & Validation**
Test: SignalBacktest + ModelEvaluation
- Walk-forward validation on 5-year history
- Calculate: Sharpe ratio, win rate, max drawdown
- Compare: regime-aware vs hardcoded strategies
- Expected: Regime-aware +4% annual return improvement

### 6. **Narrative Reporting**
Test: Storytelling
- Summarize backtest results in natural language
- Generate: performance context + metrics + interpretation
- Expected: Readable weekly/monthly reports

---

## Testing Roadmap (3 Weeks)

### **Week 1: Setup & Validation**

#### Day 1-2: Data Exploration
```bash
# Download sample data from Dropbox market-data-backup/
# - NSE stocks: pipeline-market_cache/
# - US stocks: gmd-cache_seed/
# - Europe: fundamentals_history/

# Check data schema
python3 -c "
import pandas as pd
nse_data = pd.read_parquet('~/Dropbox/market-data-backup/current/pipeline-market_cache/NSE_RELIANCE.parquet')
print(nse_data.head())
print(f'Shape: {nse_data.shape}')
print(f'Date range: {nse_data.index.min()} to {nse_data.index.max()}')
"
```

#### Day 3-4: Run Data Quality Tests
```python
from data_science_framework import DataQualityReport

# Load data
data = load_from_dropbox('NSE_RELIANCE')

# Assess quality
report = DataQualityReport(
    total_rows=len(data),
    missing_pct=data.isnull().sum() / len(data),
    duplicates=data.duplicated().sum(),
    outliers=identify_outliers(data),
    date_range=(data.index.min(), data.index.max())
)

print(f"Data is valid: {report.is_valid()}")
```

#### Day 5-7: Test Feature Engineering
```python
from data_science_framework import FeatureEngineering

# Create features
lags = FeatureEngineering.create_lag_features(data['close'], lags=[1, 5, 20])
rolling = FeatureEngineering.create_rolling_features(data['close'], windows=[20, 50, 200])
regimes = FeatureEngineering.create_regime_features(data['close'])

# Validate
print(f"Features created: {lags.shape[1] + rolling.shape[1] + regimes.shape[1]}")
```

---

### **Week 2: Regime Detection & Signals**

#### Day 1-2: Regime Detection
```python
from data_science_framework import RegimeDetection

# Detect regime
hurst = RegimeDetection.hurst_exponent(data['close'], lags=100)
regime = RegimeDetection.regime_from_hurst(hurst)
autocorr = RegimeDetection.calculate_rolling_correlation(data['close'], lookback=50)

print(f"Hurst: {hurst:.3f} → Regime: {regime}")
print(f"Autocorrelation: {autocorr:.3f}")
```

#### Day 3-4: Signal Generation
```python
from data_science_framework import TrendSignals, MeanReversionSignals

# Darvas Box
darvas_signal = TrendSignals.darvas_box(
    data['close'], 
    high_52w=data['close'].max(),
    sma_50=data['close'].rolling(50).mean().iloc[-1]
)

# RSI
rsi_signal = MeanReversionSignals.rsi_signal(
    rsi_current=calculate_rsi(data['close']).iloc[-1],
    period=14
)

print(f"Darvas: {darvas_signal}")
print(f"RSI: {rsi_signal}")
```

#### Day 5-7: Signal Composition
```python
from data_science_framework import SignalComposition

# Combine signals
components = {
    'darvas': darvas_signal['score'],
    'rsi': rsi_signal['score']
}

weights = {
    'darvas': 0.6,  # Trend signal
    'rsi': 0.4      # Confirmation signal
}

final_score, final_signal = SignalComposition.composite_score(components, weights)

print(f"Composite Score: {final_score:.1f}/10 → {final_signal}")
```

---

### **Week 3: Backtesting & Reporting**

#### Day 1-3: Backtesting
```python
from data_science_framework import SignalBacktest, ModelEvaluation

# Historical backtest
returns = data['close'].pct_change()
signals = generate_signals_walk_forward(data)

# Metrics
sharpe = calculate_sharpe(returns[signals > 0])
max_dd = ModelEvaluation.calculate_drawdown(returns)['drawdown_pct'].min()
win_rate = (returns[signals > 0] > 0).mean()

print(f"Sharpe: {sharpe:.2f}")
print(f"Max DD: {max_dd:.2f}%")
print(f"Win Rate: {win_rate:.1%}")
```

#### Day 4-5: Statistical Validation
```python
from data_science_framework import StatisticalTesting

# Test significance
stationarity = StatisticalTesting.test_stationarity(returns)
correlation = StatisticalTesting.test_correlation(signals, returns)

print(f"Stationarity p-value: {stationarity['p_value']:.4f}")
print(f"Signal correlation p-value: {correlation['p_value']:.4f}")
```

#### Day 6-7: Narrative Reporting
```python
from data_science_framework import Storytelling

# Generate narrative
summary = Storytelling.summarize_backtest(returns, signals)

print(summary['summary'])
# Output:
# "Strategy generated signals on 150/500 days. Win rate: 55.3%. 
#  Sharpe ratio: 0.82, exceeding S&P benchmark 0.45. Maximum drawdown 
#  was -12% in January 2024, recovered in March."
```

---

## File Structure After Testing

```
data_science_framework/
├── core.py                           (1,200 LOC)
├── market_signals.py                 (800 LOC)
├── test_framework.py                 (Testing script)
├── test_results/                     (Testing outputs)
│   ├── data_quality_report.txt
│   ├── nse_darvas_backtest.md
│   ├── us_rsi_backtest.md
│   ├── europe_mixed_backtest.md
│   ├── regime_analysis.csv
│   └── signal_composition_report.md
│
├── README.md                         (50+ pages)
├── INTEGRATION_GUIDE.md              (30+ pages)
├── TOOLS_TECHNIQUES_ANALYSIS.md      (100+ pages)
├── MIT_COURSES_ALIGNMENT.md          (20+ pages)
├── DROPBOX_TESTING_GUIDE.md          (this file)
│
└── examples/
    ├── nse_daily_scan.py             (NSE implementation)
    ├── us_portfolio_pl.py            (US portfolio analysis)
    └── parity_trading.py             (Put-call parity validation)
```

---

## Success Criteria

### Data Quality ✓
- [ ] 95%+ data completeness
- [ ] No more than 2% duplicates
- [ ] Date range covers 5+ years

### Feature Engineering ✓
- [ ] 20+ features generated per stock
- [ ] No NaN values in lag/rolling features after warmup
- [ ] Regime classification consistent with market history

### Signal Generation ✓
- [ ] Darvas box identifies 40-60% of rallies
- [ ] RSI correctly identifies reversals 50%+ of time
- [ ] Composite signal improves over individual signals

### Backtesting ✓
- [ ] Sharpe ratio > 0.7 (good strategy)
- [ ] Win rate > 50% (profitable on average)
- [ ] Max drawdown < 20% (acceptable risk)
- [ ] Out-of-sample results match in-sample (no overfitting)

### Validation ✓
- [ ] Regime detection p-value < 0.05 (significant)
- [ ] Signal correlation p-value < 0.05 (meaningful edge)
- [ ] Walk-forward validation confirms stability

### Reporting ✓
- [ ] Narrative summaries are readable and accurate
- [ ] Reports include context + metrics + interpretation
- [ ] Charts show signal timing + performance together

---

## Troubleshooting

### Problem: Data Loading Fails
**Solution:**
```python
# Check Dropbox connection
from data_science_framework import DataPipeline
dp = DataPipeline(db_type='dropbox')
dp.test_connection()

# List available files
files = dp.list_remote_files('NSE')
print(f"Found {len(files)} NSE stocks")
```

### Problem: Missing Values in Features
**Solution:**
```python
# Fill NA values before backtesting
features = features.fillna(method='forward')  # Forward fill
features = features.bfill()                    # Backward fill
# Drop first 50 rows (warmup period for rolling windows)
features = features.iloc[50:]
```

### Problem: Regime Detection Unstable
**Solution:**
```python
# Increase lookback window
hurst = RegimeDetection.hurst_exponent(
    data['close'], 
    lags=200  # Increase from 100 to 200
)

# Use 50-day rolling window
autocorr = RegimeDetection.calculate_rolling_correlation(
    data['close'],
    lookback=50
)
```

### Problem: Backtest Results Unrealistic
**Solution:**
```python
# Check for look-ahead bias
assert signals.index == returns.index, "Misaligned dates"

# Shift signals by 1 day (trade tomorrow based on today's signal)
signals = signals.shift(1)

# Use walk-forward validation, not in-sample
backtest = SignalBacktest.walk_forward(
    data, 
    signal_func=your_signal_generator,
    train_period=252*2,  # 2 years
    test_period=252      # 1 year
)
```

---

## Next Steps After Testing

1. **Compare Against Existing System**
   - Old hardcoded daily_scanner.py: baseline
   - New framework signals: improvement measurement
   - Expected: +3-5% annual return, higher Sharpe

2. **Deploy to Watchlist**
   - Start with NSE only (most understood)
   - Generate daily signals via scheduled job
   - Monitor for 2-4 weeks before expanding

3. **Expand to Other Markets**
   - US: Focus on trending strategies (Darvas)
   - Europe: Mixed adaptive (both signals)
   - Japan/Korea: Adjust regime thresholds

4. **Continuous Learning**
   - Start MIT 18.050 (Statistics) for deeper validation
   - Implement bootstrap CI for Sharpe ratios
   - Add causal analysis (what REALLY drives returns)

---

## Reference

- **framework module:** `data_science_framework/`
- **sample data:** `/market-data-backup/current/`
- **backtest results:** `test_results/`
- **implementation examples:** `examples/`

---

**Ready to test?** Run:

```bash
cd ~/market-pipeline/code/python_files/data_science_framework
python test_framework.py
```

**Expected output:** 8 test sections, all passing, total time ~5-10 minutes.

---

**Status:** ✅ Framework ready | 🔄 Testing in progress | ⏳ Deployment pending

---

**Last Updated:** 2026-08-01  
**Framework Version:** 1.0 Production-Ready  
**Expected Dropbox Integration:** Week of 2026-08-07
