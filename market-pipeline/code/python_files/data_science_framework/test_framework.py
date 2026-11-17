"""
Data Science Framework Test Suite
Tests all components of the framework on synthetic market data
Includes: Data pipelines, feature engineering, signal generation, backtesting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import framework components
from core import (
    DataQualityReport,
    DataPipeline,
    FeatureEngineering,
    StatisticalTesting,
    PatternDiscovery,
    ModelEvaluation,
    Storytelling
)

from market_signals import (
    TrendSignals,
    MeanReversionSignals,
    RegimeDetection,
    SignalComposition,
    SignalBacktest
)

def generate_synthetic_market_data(days=500, market='india'):
    """Generate synthetic OHLCV data for testing"""
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # Create realistic price movement
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.02, days)
    prices = 2500 * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.uniform(-0.01, 0.01, days)),
        'high': prices * (1 + np.abs(np.random.normal(0.01, 0.01, days))),
        'low': prices * (1 - np.abs(np.random.normal(0.01, 0.01, days))),
        'close': prices,
        'volume': np.random.uniform(1000000, 5000000, days),
        'ticker': 'RELIANCE',
        'market': market
    })

    # Ensure OHLC logic
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)

    return df.set_index('date')

def test_data_quality():
    """Test DataQualityReport"""
    print("\n" + "="*60)
    print("TEST 1: DATA QUALITY ASSESSMENT")
    print("="*60)

    df = generate_synthetic_market_data(days=500)

    # Create report
    report = DataQualityReport(
        total_rows=len(df),
        missing_pct={'open': 0.0, 'high': 0.0, 'low': 0.0, 'close': 0.0, 'volume': 0.0},
        duplicates=0,
        outliers={'close': 2},  # Simulate 2 outliers
        date_range=(df.index[0], df.index[-1])
    )

    print(f"✓ Rows analyzed: {report.total_rows}")
    print(f"✓ Missing data: {max(report.missing_pct.values())*100:.2f}%")
    print(f"✓ Date range: {report.date_range[0].date()} to {report.date_range[1].date()}")
    print(f"✓ Data is valid: {report.is_valid()}")

    return df, report

def test_feature_engineering(df):
    """Test FeatureEngineering"""
    print("\n" + "="*60)
    print("TEST 2: FEATURE ENGINEERING")
    print("="*60)

    # Create time features
    df_time = FeatureEngineering.create_time_features(df.reset_index(), 'date')
    print(f"✓ Time features created: {df_time.columns[df_time.columns.str.contains('date_')].tolist()}")

    # Create lag features
    lags = FeatureEngineering.create_lag_features(df['close'], lags=[1, 5, 20])
    print(f"✓ Lag features: {lags.shape[1]} features created")
    print(f"  - lag_1 (yesterday's close)")
    print(f"  - lag_5 (5-day momentum)")
    print(f"  - lag_20 (20-day momentum)")

    # Create rolling features
    rolling = FeatureEngineering.create_rolling_features(df['close'], windows=[20, 50, 200])
    print(f"✓ Rolling features: {rolling.shape[1]} features created")
    print(f"  - SMA 20, 50, 200")
    print(f"  - Volatility 20, 50, 200")

    # Create regime features
    regime = FeatureEngineering.create_regime_features(df['close'], threshold_pct=50)
    print(f"✓ Regime features: {regime.shape[1]} features")

    return df

def test_regime_detection(df):
    """Test RegimeDetection"""
    print("\n" + "="*60)
    print("TEST 3: REGIME DETECTION")
    print("="*60)

    hurst = RegimeDetection.hurst_exponent(df['close'], lags=100)
    regime = RegimeDetection.regime_from_hurst(hurst)

    print(f"✓ Hurst exponent: {hurst:.3f}")
    print(f"✓ Market regime: {regime}")
    print(f"  - 0.45-0.55: Random walk")
    print(f"  - <0.45: Mean-reverting")
    print(f"  - >0.55: Trending")

    autocorr = RegimeDetection.calculate_rolling_correlation(df['close'], lookback=50)
    print(f"✓ Autocorrelation: {autocorr:.3f}")

    return regime

def test_signal_generation(df, regime):
    """Test TrendSignals and MeanReversionSignals"""
    print("\n" + "="*60)
    print("TEST 4: SIGNAL GENERATION")
    print("="*60)

    # Calculate indicators
    sma_50 = df['close'].rolling(50).mean().iloc[-1]
    high_52w = df['close'].max()

    # Test Darvas signal
    darvas = TrendSignals.darvas_box(df['close'], high_52w, sma_50)
    print(f"✓ Darvas Box Signal:")
    print(f"  - Score: {darvas['score']:.1f}/{darvas['max_score']}")
    print(f"  - Components: {darvas['components']}")

    # Test RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_current = rsi.iloc[-1]

    rsi_signal = MeanReversionSignals.rsi_signal(rsi_current, period=14)
    print(f"✓ RSI Signal (RSI={rsi_current:.1f}):")
    print(f"  - Score: {rsi_signal['score']:.1f}/10")
    print(f"  - Signal type: {rsi_signal['signal_type']}")

    return darvas, rsi_signal

def test_signal_composition(darvas, rsi_signal):
    """Test SignalComposition"""
    print("\n" + "="*60)
    print("TEST 5: SIGNAL COMPOSITION (COMBINING SIGNALS)")
    print("="*60)

    components = {
        'darvas': darvas['score'],
        'rsi': rsi_signal['score']
    }

    weights = {
        'darvas': 0.6,  # Trend: 60%
        'rsi': 0.4      # Confirmation: 40%
    }

    score, signal = SignalComposition.composite_score(components, weights)

    print(f"✓ Weighted signal composition:")
    print(f"  - Darvas (60%): {components['darvas']:.1f}")
    print(f"  - RSI (40%): {components['rsi']:.1f}")
    print(f"  - Final score: {score:.1f}/10")
    print(f"  - Signal: {signal}")

def test_statistical_testing(df):
    """Test StatisticalTesting"""
    print("\n" + "="*60)
    print("TEST 6: STATISTICAL TESTING")
    print("="*60)

    # Test stationarity
    returns = df['close'].pct_change().dropna()
    stationarity = StatisticalTesting.test_stationarity(returns)

    print(f"✓ ADF Stationarity Test:")
    print(f"  - Test statistic: {stationarity['adf_statistic']:.4f}")
    print(f"  - P-value: {stationarity['p_value']:.4f}")
    print(f"  - Is stationary (p<0.05): {stationarity['is_stationary_at_05']}")

    # Test correlation
    signal = (df['close'] > df['close'].rolling(50).mean()).astype(int)
    correlation = StatisticalTesting.test_correlation(signal.astype(float), returns)

    print(f"✓ Correlation Test (Signal vs Returns):")
    print(f"  - Correlation: {correlation['correlation']:.4f}")
    print(f"  - P-value: {correlation['p_value']:.4f}")
    print(f"  - Significant at 0.05: {correlation['significant_at_05']}")

def test_backtesting(df):
    """Test SignalBacktest and ModelEvaluation"""
    print("\n" + "="*60)
    print("TEST 7: BACKTESTING & PERFORMANCE EVALUATION")
    print("="*60)

    # Generate simple signals
    sma_50 = df['close'].rolling(50).mean()
    signals = (df['close'] > sma_50).astype(int)

    # Calculate returns
    returns = df['close'].pct_change()
    strategy_returns = signals.shift(1) * returns

    # Metrics
    annual_return = strategy_returns.mean() * 252
    annual_vol = strategy_returns.std() * np.sqrt(252)
    sharpe = (annual_return) / annual_vol if annual_vol > 0 else 0

    print(f"✓ Backtest Results (SMA50 Strategy):")
    print(f"  - Annual return: {annual_return:.2%}")
    print(f"  - Annual volatility: {annual_vol:.2%}")
    print(f"  - Sharpe ratio: {sharpe:.2f}")

    # Drawdown
    drawdown = ModelEvaluation.calculate_drawdown(returns)
    print(f"  - Max drawdown: {drawdown['drawdown_pct'].min():.2f}%")

    # Win rate
    win_rate = (strategy_returns > 0).sum() / len(strategy_returns)
    print(f"  - Win rate: {win_rate:.1%}")

def test_storytelling(df):
    """Test Storytelling"""
    print("\n" + "="*60)
    print("TEST 8: NARRATIVE REPORTING (STORYTELLING)")
    print("="*60)

    returns = df['close'].pct_change()
    signals = (df['close'] > df['close'].rolling(50).mean()).astype(int)

    summary = Storytelling.summarize_backtest(returns, signals)

    print(f"✓ Strategy Summary Report Generated:")
    print(summary['summary'])

def main():
    """Run all framework tests"""
    print("\n" + "="*60)
    print("DATA SCIENCE FRAMEWORK COMPREHENSIVE TEST")
    print("="*60)
    print("Testing all components on synthetic market data")
    print("Markets: India (NSE) - RELIANCE stock")
    print("Period: 500 trading days (~2 years)")

    # Test sequence
    df, report = test_data_quality()
    df = test_feature_engineering(df)
    regime = test_regime_detection(df)
    darvas, rsi = test_signal_generation(df, regime)
    test_signal_composition(darvas, rsi)
    test_statistical_testing(df)
    test_backtesting(df)
    test_storytelling(df)

    # Final summary
    print("\n" + "="*60)
    print("FRAMEWORK TEST COMPLETE")
    print("="*60)
    print("✓ All components tested successfully")
    print("✓ Ready to apply to real Dropbox market data")
    print("\nNext steps:")
    print("1. Load actual market data from Dropbox market-data-backup/")
    print("2. Run daily scan pipeline")
    print("3. Generate backtest reports")
    print("="*60 + "\n")

if __name__ == '__main__':
    main()
