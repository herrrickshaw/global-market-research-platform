# Data Science Module: Integration Guide

A production-ready framework synthesizing:
- **Linoff (SQL/Excel)**: Structured data ingestion & quality checks
- **McKinney (Python)**: Pandas wrangling, time series, feature engineering
- **Han/Kamber/Pei (Mining)**: Pattern discovery, clustering, classification
- **Business Books**: Storytelling, decision frameworks, regime detection

## Architecture Overview

```
Raw Data (SQL, CSV, API)
        ↓
DataPipeline (extract → validate → transform → store)
        ↓
FeatureEngineering (lags, rolling stats, regimes)
        ↓
SignalGeneration (Darvas, RSI, mean-reversion, regimes)
        ↓
Backtesting (walk-forward, Sharpe ratio, drawdown)
        ↓
Reports (Storytelling: narrative + metrics)
```

## Quick Start: Apply to Your Markets

### 1. NSE/BSE Daily Scan (Existing Use Case)

**Before** (current `daily_scanner.py`):
- Hardcoded thresholds
- Single scoring logic
- No regime awareness

**After** (with framework):

```python
from data_science_framework import (
    DataPipeline, FeatureEngineering, TrendSignals,
    RegimeDetection, SignalComposition, Storytelling
)
import pandas as pd

# Step 1: Load Cassandra data (use existing bulk_fetcher.py)
df = cassandra_client.fetch_market_data('india', 'NIFTY500')

# Step 2: Detect regime (McKinney + Han/Kamber)
hurst = RegimeDetection.hurst_exponent(df['close'])
regime = RegimeDetection.regime_from_hurst(hurst)

# Step 3: Generate signals per regime
signals = []
for ticker in df['ticker'].unique():
    ticker_data = df[df['ticker'] == ticker]
    
    # Feature engineering (McKinney: rolling stats)
    features = FeatureEngineering.create_rolling_features(
        ticker_data['close'], 
        windows=[20, 50, 200]
    )
    
    # Signal generation (regime-aware)
    if regime == 'TRENDING':
        # Use Darvas box
        score, components = TrendSignals.darvas_box(
            ticker_data['close'],
            ticker_data['high'].max(),  # 52W high
            features['sma_50'].iloc[-1]
        )
    else:
        # Use RSI for mean-reverting
        rsi = calculate_rsi(ticker_data['close'])
        score, components = MeanReversionSignals.rsi_signal(rsi)
    
    # Composite score
    final_score, signal = SignalComposition.composite_score(components)
    signals.append({
        'ticker': ticker,
        'signal': signal,
        'score': final_score,
        'regime': regime
    })

# Step 4: Storytelling (actionable narrative)
summary = Storytelling.summarize_signals(pd.DataFrame(signals), regime)
print(summary)
```

### 2. US Portfolio P&L (Existing Use Case)

**Integration with `portfolio_analysis.py`**:

```python
from data_science_framework import (
    FeatureEngineering, ModelEvaluation, Storytelling
)

# Load portfolio holdings
portfolio = load_portfolio()

for holding in portfolio:
    # Fetch price history (yfinance)
    prices = yf.download(holding['symbol'], period='2y')
    
    # Calculate returns
    returns = prices['Adj Close'].pct_change()
    
    # Risk metrics (Storytelling)
    sharpe = ModelEvaluation.calculate_sharpe_ratio(returns)
    drawdown_df = ModelEvaluation.calculate_drawdown(returns)
    
    # Store in summary
    holding['metrics'] = {
        'sharpe_ratio': sharpe,
        'max_drawdown': drawdown_df['drawdown_pct'].min(),
        'volatility': returns.std() * np.sqrt(252)
    }

# Generate narrative P&L report
summary = Storytelling.summarize_portfolio(portfolio)
```

### 3. Put-Call Parity (Existing Use Case)

**Integration with `parity_engine.py`**:

```python
from data_science_framework import (
    PatternDiscovery, StatisticalTesting, ModelEvaluation
)

# Detect outlier parity deviations (actual mispricings)
parity_series = calculate_parity_deviation(option_chain)

# Find outliers (Han/Kamber: outlier detection)
outliers = PatternDiscovery.detect_outliers_iqr(parity_series)

# Test if deviations are statistically significant
for idx, row in outliers.iterrows():
    test_result = StatisticalTesting.test_stationarity(
        parity_series.iloc[max(0, idx-20):idx+1]
    )
    
    if test_result['is_stationary_at_05']:
        # Mean-reverting mispricing → tradeable
        print(f"Tradeable deviation at {row['date']}: {row['value']:.2%}")
    else:
        # Regime shift → not tradeable
        print(f"Regime shift detected, skip trade")
```

## Tips & Tricks from GitHub Repos

### Tip 1: Data Quality First (80% of work)
From `data_validation.py` + `bulk_fetcher.py`:
```python
# Always check quality BEFORE modeling
pipeline = YourDataPipeline(...)
if not pipeline.load_transform_store():
    logger.error("Data quality failed, abort pipeline")
    exit(1)

# Inspect the quality report
for report in pipeline.quality_log:
    print(report)
```

### Tip 2: Time Zone Handling (Critical for International)
From `market_daily.py`:
```python
# Always store dates in UTC, convert to local in reports
df['date_utc'] = pd.to_datetime(df['date']).dt.tz_localize('UTC')

# Convert to market timezone when reporting
df['date_ist'] = df['date_utc'].dt.tz_convert('Asia/Kolkata')
df['date_est'] = df['date_utc'].dt.tz_convert('America/New_York')
```

### Tip 3: Walk-Forward Validation (Prevent Overfitting)
From `backtester.py`:
```python
# Don't test on all data at once (overfitting!)
metrics = ModelEvaluation.walk_forward_validate(
    df=prices,
    model_fn=lambda train_data: YourModel().fit(train_data),
    train_window=252,  # 1 year
    test_window=63,    # 3 months
    step=21            # Rebalance monthly
)

print(f"Out-of-sample Sharpe: {metrics['sharpe_ratio']:.2f}")
```

### Tip 4: Regime Detection (Market Character Matters)
From `pe_anomaly_backtest.md`:
```python
# India: mean-reverting (seasonal, flows-driven)
# US: trending (momentum-driven)
# Europe: mixed (policy-driven)

regime = RegimeDetection.regime_from_hurst(
    RegimeDetection.hurst_exponent(df['close'])
)

if regime == 'MEAN_REVERTING':
    # Buy dips, sell rallies
    use_rsi_strategy()
else:
    # Follow trend
    use_darvas_strategy()
```

### Tip 5: Signal Composition (Prevent False Signals)
From `daily_scanner.py`:
```python
# Single signals = noise. Combine signals.
components = {
    'darvas_box': darvas_score,
    'rsi_oversold': rsi_score,
    'volume_surge': volume_score
}

# Weight by strength
weights = {
    'darvas_box': 0.5,      # Primary signal
    'rsi_oversold': 0.3,    # Confirmation
    'volume_surge': 0.2     # Strength check
}

final_score, signal = SignalComposition.composite_score(components, weights)
```

## Market-Specific Configurations

### India (NSE/BSE): Mean-Reverting
```python
INDIA_CONFIG = {
    'regime': 'MEAN_REVERTING',
    'signals': ['RSI', 'Bollinger Bands', 'Volume'],
    'lookback': 50,
    'win_rate_target': 0.55,
    'sharpe_target': 0.8,
}

# Apply: Use RSI and Bollinger Bands
# Avoid: Darvas box (too many false breakouts)
```

### US (NYSE/NASDAQ): Trending
```python
US_CONFIG = {
    'regime': 'TRENDING',
    'signals': ['Darvas Box', 'Moving Average Crossovers', 'Momentum'],
    'lookback': 100,
    'win_rate_target': 0.52,
    'sharpe_target': 1.2,
}

# Apply: Darvas + momentum
# Avoid: Mean-reversion (ignores mega-cap flows)
```

### Europe: Mixed (Policy-Sensitive)
```python
EUROPE_CONFIG = {
    'regime': 'MIXED',
    'signals': ['Zone-based', 'Calendar Effects', 'Regime Detector'],
    'lookback': 252,
    'win_rate_target': 0.50,
    'sharpe_target': 0.6,
}

# Apply: Adaptive regime switching
# Trigger: ECB announcements, Brexit-like events
```

## Backtest → Production Checklist

✅ **Before you trade any signal:**

- [ ] Walk-forward validation shows positive Sharpe (out-of-sample)
- [ ] Win rate > market neutral (depends on regime)
- [ ] Max drawdown < 15% annually
- [ ] Signal not over-fitted (test on 2+ years of data)
- [ ] Regime detection active (don't apply India strategy to US)
- [ ] Data quality checks pass every run
- [ ] Narrative report generated (storytelling)

✅ **Deployment:**

- [ ] Signal sent to watchlist/mailer, NOT auto-traded initially
- [ ] Monitor actual fills vs backtest assumptions
- [ ] Re-optimize every quarter (markets change)
- [ ] Document assumptions (why this signal works now)

## Files Structure

```
data_science_framework/
├── core.py                 # DataPipeline, FeatureEngineering, Testing
├── market_signals.py       # Signal generation + backtesting
├── INTEGRATION_GUIDE.md    # This file
└── examples/
    ├── nse_daily_scan.py   # India equities daily scan
    ├── us_portfolio_pl.py   # US portfolio analysis
    └── parity_trading.py    # Put-call parity signals
```

## FAQ

**Q: What if I add a new market (Japan, Korea)?**
A: Copy `INDIA_CONFIG`, adjust `regime` based on market character, test walk-forward validation.

**Q: My signals have low win rate (40%?)**
A: Regime mismatch. Run `RegimeDetection.hurst_exponent()` — if your market is trending, don't use RSI-only.

**Q: Can I combine signals from multiple books/methods?**
A: Yes! Use `SignalComposition.composite_score()` with custom weights. Example: 50% Darvas (momentum), 30% RSI (confirmation), 20% Volume (strength).

**Q: How often should I retrain/rebalance?**
A: Monthly (walk-forward step=21). Quarterly if market regime stable. Re-run regime detection weekly.

## References

- McKinney, Wes. *Python for Data Analysis*, 3rd Ed. (pandas, time series, groupby)
- Han, Jiawei et al. *Data Mining: Concepts and Techniques*, 3rd Ed. (clustering, pattern mining, outliers)
- Linoff, Gordon S. *Data Analysis Using SQL and Excel* (data quality, SQL best practices)
- Knaflic, Cole Nussbaumer. *Storytelling with Data* (narrative, visualization)

---

**Last Updated:** 2026-08-01  
**Status:** Ready for integration into all repos
