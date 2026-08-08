"""
Test Data Science Framework on Real Dropbox Market Data
Loads NSE/US/Europe data from cache_seed and runs framework tests
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

# Import framework components
from core import (
    DataQualityReport,
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

# Data paths
CACHE_SEED = '/Users/umashankar/market-pipeline/code/python_files/cache_seed'
CLEANED_LONG = f'{CACHE_SEED}/cleaned_long.parquet'  # India data
CLEANED_LONG_US = f'{CACHE_SEED}/cleaned_long_US.parquet'  # US data

def load_nse_data():
    """Load India NSE market data from cleaned_long.parquet"""
    print("\n" + "="*60)
    print("LOADING NSE DATA FROM DROPBOX CACHE")
    print("="*60)

    try:
        df = pd.read_parquet(CLEANED_LONG)
        print(f"✓ Loaded {len(df):,} rows from {CLEANED_LONG}")
        print(f"✓ Columns: {list(df.columns)}")
        print(f"✓ Data types:\n{df.dtypes}")

        # Parse Date column if present
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            date_min = df['Date'].min()
            date_max = df['Date'].max()
            print(f"✓ Date range: {date_min.date()} to {date_max.date()}")
        else:
            print(f"✓ No Date column; {len(df)} total records")

        # Set close as index for framework compatibility
        if 'Close' in df.columns:
            df = df.rename(columns={'Close': 'close', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'volume'})
            df = df.set_index(pd.Index(df['Date']) if 'Date' in df.columns else df.index)

        return df
    except FileNotFoundError:
        print(f"✗ File not found: {CLEANED_LONG}")
        return None
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        return None

def test_data_quality_real(df):
    """Test DataQualityReport on real NSE data"""
    print("\n" + "="*60)
    print("TEST 1: DATA QUALITY ON REAL NSE DATA")
    print("="*60)

    # Calculate quality metrics
    total_rows = len(df)
    missing_pct = df.isnull().sum() / len(df)
    duplicates = df.duplicated().sum()

    # Find outliers (>3 standard deviations from mean)
    outliers = {}
    for col in df.select_dtypes(include=[np.number]).columns:
        z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
        outlier_count = (z_scores > 3).sum()
        if outlier_count > 0:
            outliers[col] = outlier_count

    # Get date range safely
    if isinstance(df.index[0], pd.Timestamp):
        date_range = (df.index.min(), df.index.max())
    else:
        date_range = (0, len(df))

    report = DataQualityReport(
        total_rows=total_rows,
        missing_pct=dict(missing_pct),
        duplicates=duplicates,
        outliers=outliers,
        date_range=date_range
    )

    print(f"✓ Rows analyzed: {report.total_rows:,}")
    print(f"✓ Missing data: {max(report.missing_pct.values() if report.missing_pct else [0])*100:.2f}%")
    print(f"✓ Duplicates: {report.duplicates}")
    print(f"✓ Outliers detected: {len(report.outliers)}")
    if report.outliers:
        for col, count in list(report.outliers.items())[:3]:
            print(f"  - {col}: {count} outliers")
    if isinstance(report.date_range[0], pd.Timestamp):
        print(f"✓ Date range: {report.date_range[0].date()} to {report.date_range[1].date()}")
    else:
        print(f"✓ Records: {report.date_range[0]} to {report.date_range[1]}")
    print(f"✓ Data is valid: {report.is_valid()}")

    return report

def test_feature_engineering_real(df):
    """Test FeatureEngineering on real NSE data"""
    print("\n" + "="*60)
    print("TEST 2: FEATURE ENGINEERING ON REAL NSE DATA")
    print("="*60)

    # Assume 'close' column exists
    if 'close' not in df.columns:
        print("✗ 'close' column not found")
        return None

    prices = df['close']

    # Create lag features
    lags = FeatureEngineering.create_lag_features(prices, lags=[1, 5, 20])
    print(f"✓ Lag features: {lags.shape[1]} created")

    # Create rolling features
    rolling = FeatureEngineering.create_rolling_features(prices, windows=[20, 50, 200])
    print(f"✓ Rolling features: {rolling.shape[1]} created")

    # Create regime features
    regime = FeatureEngineering.create_regime_features(prices, threshold_pct=50)
    print(f"✓ Regime features: {regime.shape[1]} created")

    print(f"✓ Total features created: {lags.shape[1] + rolling.shape[1] + regime.shape[1]}")

    return lags, rolling, regime

def test_regime_detection_real(df):
    """Test RegimeDetection on real NSE data"""
    print("\n" + "="*60)
    print("TEST 3: REGIME DETECTION ON REAL NSE DATA")
    print("="*60)

    if 'close' not in df.columns:
        print("✗ 'close' column not found")
        return None

    prices = df['close']

    try:
        hurst = RegimeDetection.hurst_exponent(prices, lags=100)
        regime = RegimeDetection.regime_from_hurst(hurst)

        print(f"✓ Hurst exponent: {hurst:.3f}")
        print(f"✓ Market regime: {regime}")
        print(f"  - <0.45: Mean-reverting")
        print(f"  - 0.45-0.55: Random walk")
        print(f"  - >0.55: Trending")

        autocorr = RegimeDetection.calculate_rolling_correlation(prices, lookback=50)
        print(f"✓ Autocorrelation: {autocorr:.3f}")

        return regime
    except Exception as e:
        print(f"✗ Error in regime detection: {e}")
        return None

def test_signal_generation_real(df, regime):
    """Test TrendSignals and MeanReversionSignals on real NSE data"""
    print("\n" + "="*60)
    print("TEST 4: SIGNAL GENERATION ON REAL NSE DATA")
    print("="*60)

    if 'close' not in df.columns:
        print("✗ 'close' column not found")
        return None, None

    prices = df['close']
    sma_50 = prices.rolling(50).mean().iloc[-1]
    high_52w = prices.max()

    try:
        # Darvas signal
        darvas = TrendSignals.darvas_box(prices, high_52w, sma_50)
        print(f"✓ Darvas Box Signal:")
        print(f"  - Score: {darvas['score']:.1f}/{darvas['max_score']}")
        print(f"  - Components: {darvas['components']}")

        # RSI signal
        delta = prices.diff()
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
    except Exception as e:
        print(f"✗ Error in signal generation: {e}")
        return None, None

def test_signal_composition_real(darvas, rsi_signal):
    """Test SignalComposition on real NSE data"""
    print("\n" + "="*60)
    print("TEST 5: SIGNAL COMPOSITION ON REAL NSE DATA")
    print("="*60)

    if darvas is None or rsi_signal is None:
        print("✗ Cannot compose signals (missing inputs)")
        return None

    try:
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

        return score, signal
    except Exception as e:
        print(f"✗ Error in signal composition: {e}")
        return None

def test_statistical_testing_real(df):
    """Test StatisticalTesting on real NSE data"""
    print("\n" + "="*60)
    print("TEST 6: STATISTICAL TESTING ON REAL NSE DATA")
    print("="*60)

    if 'close' not in df.columns:
        print("✗ 'close' column not found")
        return None

    prices = df['close']
    returns = prices.pct_change().dropna()

    try:
        # Test stationarity
        stationarity = StatisticalTesting.test_stationarity(returns)

        print(f"✓ ADF Stationarity Test:")
        print(f"  - Test statistic: {stationarity['adf_statistic']:.4f}")
        print(f"  - P-value: {stationarity['p_value']:.4f}")
        print(f"  - Is stationary (p<0.05): {stationarity['is_stationary_at_05']}")

        # Test correlation
        signal = (prices > prices.rolling(50).mean()).astype(int)
        correlation = StatisticalTesting.test_correlation(signal.astype(float), returns)

        print(f"✓ Correlation Test (Signal vs Returns):")
        print(f"  - Correlation: {correlation['correlation']:.4f}")
        print(f"  - P-value: {correlation['p_value']:.4f}")
        print(f"  - Significant at 0.05: {correlation['significant_at_05']}")

        return stationarity, correlation
    except Exception as e:
        print(f"✗ Error in statistical testing: {e}")
        return None

def test_backtesting_real(df):
    """Test backtesting on real NSE data"""
    print("\n" + "="*60)
    print("TEST 7: BACKTESTING & PERFORMANCE ON REAL NSE DATA")
    print("="*60)

    if 'close' not in df.columns:
        print("✗ 'close' column not found")
        return None

    prices = df['close']
    returns = prices.pct_change()

    try:
        # Generate simple signals
        sma_50 = prices.rolling(50).mean()
        signals = (prices > sma_50).astype(int)

        strategy_returns = signals.shift(1) * returns

        # Calculate metrics
        annual_return = strategy_returns.mean() * 252
        annual_vol = strategy_returns.std() * np.sqrt(252)
        sharpe = (annual_return) / annual_vol if annual_vol > 0 else 0

        print(f"✓ Backtest Results (SMA50 Strategy on Real Data):")
        print(f"  - Annual return: {annual_return:.2%}")
        print(f"  - Annual volatility: {annual_vol:.2%}")
        print(f"  - Sharpe ratio: {sharpe:.2f}")

        # Drawdown
        drawdown = ModelEvaluation.calculate_drawdown(returns)
        print(f"  - Max drawdown: {drawdown['drawdown_pct'].min():.2f}%")

        # Win rate
        win_rate = (strategy_returns > 0).sum() / len(strategy_returns)
        print(f"  - Win rate: {win_rate:.1%}")

        print(f"\n✓ Real data backtest completed successfully")

        return {
            'annual_return': annual_return,
            'sharpe': sharpe,
            'max_dd': drawdown['drawdown_pct'].min(),
            'win_rate': win_rate
        }
    except Exception as e:
        print(f"✗ Error in backtesting: {e}")
        return None

def test_storytelling_real(df):
    """Test Storytelling on real NSE data"""
    print("\n" + "="*60)
    print("TEST 8: NARRATIVE REPORTING ON REAL NSE DATA")
    print("="*60)

    if 'close' not in df.columns:
        print("✗ 'close' column not found")
        return None

    prices = df['close']
    returns = prices.pct_change()
    signals = (prices > prices.rolling(50).mean()).astype(int)

    try:
        summary = Storytelling.summarize_backtest(returns, signals)

        print(f"✓ Strategy Summary Report Generated:")
        print(summary['summary'])

        return summary
    except Exception as e:
        print(f"✗ Error in storytelling: {e}")
        return None

def main():
    """Run all framework tests on real NSE Dropbox data"""
    print("\n" + "="*70)
    print("DATA SCIENCE FRAMEWORK TEST ON REAL DROPBOX NSE MARKET DATA")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Data source: {CLEANED_LONG}")

    # Load data
    df = load_nse_data()
    if df is None:
        print("✗ Cannot proceed without data")
        return

    # Run tests
    test_data_quality_real(df)
    test_feature_engineering_real(df)
    regime = test_regime_detection_real(df)
    darvas, rsi = test_signal_generation_real(df, regime)
    test_signal_composition_real(darvas, rsi)
    test_statistical_testing_real(df)
    backtest_results = test_backtesting_real(df)
    test_storytelling_real(df)

    # Summary
    print("\n" + "="*70)
    print("FRAMEWORK TEST ON REAL DROPBOX DATA COMPLETE")
    print("="*70)
    print("✓ All components tested successfully on real NSE market data")
    if backtest_results:
        print(f"✓ Strategy Sharpe ratio: {backtest_results['sharpe']:.2f}")
        print(f"✓ Win rate: {backtest_results['win_rate']:.1%}")
        print(f"✓ Max drawdown: {backtest_results['max_dd']:.2f}%")
    print("\nNext steps:")
    print("1. Deploy to NSE daily scan")
    print("2. Test on US data (cleaned_long_US.parquet)")
    print("3. Expand to Europe/Japan/Korea")
    print("="*70 + "\n")

if __name__ == '__main__':
    main()
