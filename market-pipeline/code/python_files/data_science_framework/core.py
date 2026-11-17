"""
Data Science Framework: Unified pipeline for market analysis.
Synthesizes SQL/Excel (Linoff), Python data wrangling (McKinney),
data mining patterns (Han/Kamber/Pei), and big data techniques.

Core principles:
- Data quality > model complexity
- Temporal validity (market regimes change)
- Interpretability > black boxes
- Reproducibility > one-off scripts
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, List, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class DataQualityReport:
    """Track data quality metrics across pipeline."""
    total_rows: int
    missing_pct: Dict[str, float]
    duplicates: int
    outliers: Dict[str, int]
    date_range: Tuple[datetime, datetime]
    timestamp: datetime = None

    def __post_init__(self):
        self.timestamp = datetime.now()

    def is_valid(self, min_complete_pct: float = 0.95) -> bool:
        """Check if data meets minimum quality thresholds."""
        avg_completeness = 1 - np.mean(list(self.missing_pct.values()))
        return avg_completeness >= min_complete_pct and self.duplicates == 0


class DataPipeline(ABC):
    """
    Base class for all data pipelines.
    Each market/dataset gets its own pipeline following: Extract→Load→Transform→Validate→Store
    """

    def __init__(self, name: str, source: str, target: str):
        self.name = name
        self.source = source
        self.target = target
        self.quality_log: List[DataQualityReport] = []

    @abstractmethod
    def extract(self) -> pd.DataFrame:
        """Source-specific extraction logic."""
        pass

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Source-specific validation rules."""
        pass

    def load_transform_store(self) -> bool:
        """Template method: orchestrates the pipeline."""
        try:
            # EXTRACT
            logger.info(f"[{self.name}] Extracting from {self.source}")
            df = self.extract()

            # VALIDATE INPUT
            is_valid, msg = self.validate(df)
            if not is_valid:
                logger.error(f"[{self.name}] Validation failed: {msg}")
                return False

            # TRANSFORM (standardized steps)
            df = self._deduplicate(df)
            df = self._handle_missing(df)
            df = self._normalize_types(df)

            # QUALITY REPORT
            report = self._generate_quality_report(df)
            if not report.is_valid():
                logger.warning(f"[{self.name}] Quality threshold not met: {report}")
            self.quality_log.append(report)

            # STORE
            self._store(df)
            logger.info(f"[{self.name}] Pipeline completed. Rows: {len(df)}")
            return True

        except Exception as e:
            logger.error(f"[{self.name}] Pipeline failed: {str(e)}")
            return False

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove exact row duplicates."""
        before = len(df)
        df = df.drop_duplicates()
        after = len(df)
        if before > after:
            logger.info(f"[{self.name}] Removed {before - after} exact duplicates")
        return df

    def _handle_missing(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle missing values with strategy-per-column."""
        for col in df.columns:
            missing_pct = df[col].isna().sum() / len(df)
            if missing_pct > 0.5:
                logger.warning(f"[{self.name}] {col} is {missing_pct*100:.1f}% missing - dropping")
                df = df.drop(col, axis=1)
            elif missing_pct > 0:
                if df[col].dtype in ['float64', 'int64']:
                    df[col] = df[col].fillna(df[col].median())
                else:
                    df[col] = df[col].fillna(df[col].mode()[0] if len(df[col].mode()) > 0 else 'Unknown')
        return df

    def _normalize_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize data types."""
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                df[col] = pd.to_datetime(df[col], errors='coerce')
        return df

    def _generate_quality_report(self, df: pd.DataFrame) -> DataQualityReport:
        """Quantify data quality."""
        missing_pct = (df.isna().sum() / len(df)).to_dict()
        duplicates = df.duplicated().sum()
        date_cols = df.select_dtypes(include=['datetime64']).columns
        date_range = (df[date_cols[0]].min(), df[date_cols[0]].max()) if len(date_cols) > 0 else (None, None)

        return DataQualityReport(
            total_rows=len(df),
            missing_pct=missing_pct,
            duplicates=duplicates,
            outliers={},
            date_range=date_range
        )

    @abstractmethod
    def _store(self, df: pd.DataFrame):
        """Target-specific storage logic."""
        pass


class FeatureEngineering:
    """
    Feature engineering following: Domain Knowledge → Statistical Tests → Automated Generation
    Inspired by: McKinney (feature transforms) + Han/Kamber (attribute transforms)
    """

    @staticmethod
    def create_time_features(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
        """Extract temporal features from datetime column."""
        df[f'{date_col}_year'] = df[date_col].dt.year
        df[f'{date_col}_month'] = df[date_col].dt.month
        df[f'{date_col}_dow'] = df[date_col].dt.dayofweek  # 0=Mon, 6=Sun
        df[f'{date_col}_qtr'] = df[date_col].dt.quarter
        df[f'{date_col}_is_quarter_end'] = df[date_col].dt.is_quarter_end.astype(int)
        return df

    @staticmethod
    def create_lag_features(series: pd.Series, lags: List[int]) -> pd.DataFrame:
        """Create lagged features for time series (momentum, mean reversion)."""
        result = pd.DataFrame(index=series.index)
        for lag in lags:
            result[f'lag_{lag}'] = series.shift(lag)
        return result

    @staticmethod
    def create_rolling_features(series: pd.Series, windows: List[int]) -> pd.DataFrame:
        """Create rolling statistics (moving averages, volatility)."""
        result = pd.DataFrame(index=series.index)
        for window in windows:
            result[f'sma_{window}'] = series.rolling(window).mean()
            result[f'std_{window}'] = series.rolling(window).std()
        return result

    @staticmethod
    def create_regime_features(series: pd.Series, threshold_pct: float = 50) -> pd.DataFrame:
        """Detect regimes (trending vs mean-reverting) using percentile bands."""
        q_high = series.rolling(252).quantile(threshold_pct / 100)
        q_low = series.rolling(252).quantile((100 - threshold_pct) / 100)

        result = pd.DataFrame(index=series.index)
        result['is_high_regime'] = (series > q_high).astype(int)
        result['is_low_regime'] = (series < q_low).astype(int)
        return result


class StatisticalTesting:
    """
    Hypothesis testing for feature significance.
    Prevents overfitting via statistical validation before modeling.
    """

    @staticmethod
    def test_correlation(x: pd.Series, y: pd.Series, method: str = 'pearson') -> Dict[str, float]:
        """Test if x and y are significantly correlated."""
        from scipy.stats import pearsonr, spearmanr

        # Align series on common index
        common_idx = x.index.intersection(y.index)
        x_aligned = x.loc[common_idx].dropna()
        y_aligned = y.loc[common_idx].dropna()

        # Align on common non-null indices
        common_valid = x_aligned.index.intersection(y_aligned.index)
        x_valid = x_aligned.loc[common_valid]
        y_valid = y_aligned.loc[common_valid]

        if len(x_valid) < 2:
            return {
                'correlation': 0.0,
                'p_value': 1.0,
                'significant_at_05': False,
                'significant_at_01': False
            }

        if method == 'pearson':
            corr, pval = pearsonr(x_valid, y_valid)
        else:
            corr, pval = spearmanr(x_valid, y_valid)

        return {
            'correlation': corr,
            'p_value': pval,
            'significant_at_05': pval < 0.05,
            'significant_at_01': pval < 0.01
        }

    @staticmethod
    def test_stationarity(series: pd.Series) -> Dict[str, Any]:
        """ADF test: is series stationary (mean-reverting)?"""
        from scipy.stats import shapiro
        from statsmodels.tsa.stattools import adfuller

        adf_result = adfuller(series.dropna(), autolag='AIC')

        return {
            'adf_statistic': adf_result[0],
            'p_value': adf_result[1],
            'is_stationary_at_05': adf_result[1] < 0.05,
            'critical_values': adf_result[4]
        }


class PatternDiscovery:
    """
    Pattern mining following Han/Kamber/Pei methodologies.
    Applies to market signals: frequent itemsets, association rules, outliers.
    """

    @staticmethod
    def find_frequent_patterns(df: pd.DataFrame, support_pct: float = 5) -> Dict[str, int]:
        """
        Find frequently co-occurring signal combinations.
        Example: How often do (RSI>70 AND Price>MA50 AND Volume>Avg) occur?
        """
        # Discretize each column to binary signals
        binary_df = pd.DataFrame()
        for col in df.columns:
            if df[col].dtype in ['float64', 'int64']:
                median = df[col].median()
                binary_df[f'{col}_high'] = (df[col] > median).astype(int)

        # Find frequent itemsets (simplified: count co-occurrences)
        patterns = {}
        for combo_size in [2, 3]:
            from itertools import combinations
            for cols in combinations(binary_df.columns, combo_size):
                subset = binary_df[list(cols)].sum(axis=1) == combo_size
                support = subset.sum() / len(df) * 100
                if support >= support_pct:
                    pattern_name = ' AND '.join(cols)
                    patterns[pattern_name] = int(support)

        return dict(sorted(patterns.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def detect_outliers_zscore(series: pd.Series, threshold: float = 3.0) -> pd.DataFrame:
        """Outlier detection via Z-score (univariate)."""
        z_scores = np.abs((series - series.mean()) / series.std())
        outliers = series[z_scores > threshold]

        result = pd.DataFrame({
            'date': outliers.index,
            'value': outliers.values,
            'z_score': z_scores[z_scores > threshold].values
        })
        return result

    @staticmethod
    def detect_outliers_iqr(series: pd.Series) -> pd.DataFrame:
        """Outlier detection via IQR (robust to extreme values)."""
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        outliers = series[(series < lower_bound) | (series > upper_bound)]

        result = pd.DataFrame({
            'date': outliers.index,
            'value': outliers.values,
            'type': ['below_lower' if v < lower_bound else 'above_upper' for v in outliers.values]
        })
        return result


class ModelEvaluation:
    """
    Evaluation framework: walk-forward validation, Sharpe ratio, drawdown analysis.
    Prevents overfitting to historical noise (critical for trading).
    """

    @staticmethod
    def walk_forward_validate(
        df: pd.DataFrame,
        model_fn,
        train_window: int = 252,
        test_window: int = 63,
        step: int = 21
    ) -> Dict[str, float]:
        """
        Walk-forward validation: train on past 252 days, test on next 63 days, roll forward 21 days.
        Returns out-of-sample performance metrics.
        """
        predictions = []
        actuals = []

        for i in range(0, len(df) - train_window - test_window, step):
            train_data = df.iloc[i:i + train_window]
            test_data = df.iloc[i + train_window:i + train_window + test_window]

            # Train and predict
            model = model_fn(train_data)
            pred = model.predict(test_data)

            predictions.extend(pred)
            actuals.extend(test_data['target'].values)

        predictions = np.array(predictions)
        actuals = np.array(actuals)

        # Metrics
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        mae = mean_absolute_error(actuals, predictions)
        rmse = np.sqrt(mean_squared_error(actuals, predictions))

        return {'mae': mae, 'rmse': rmse, 'predictions': predictions, 'actuals': actuals}

    @staticmethod
    def calculate_drawdown(returns: pd.Series) -> pd.DataFrame:
        """Calculate maximum drawdown from peak."""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max

        return pd.DataFrame({
            'drawdown': drawdown,
            'drawdown_pct': drawdown * 100
        })

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
        """Sharpe ratio = (mean_return - risk_free_rate) / std_return."""
        excess_returns = returns - risk_free_rate / 252  # annualize
        return excess_returns.mean() / excess_returns.std() * np.sqrt(252)


class Storytelling:
    """
    Data storytelling: turn findings into actionable narratives.
    Inspired by Cole Nussbaumer Knaflic's "Storytelling with Data".
    """

    @staticmethod
    def summarize_backtest(returns: pd.Series, signals: pd.Series) -> Dict[str, Any]:
        """Generate narrative summary of backtest results."""
        from scipy.stats import linregress

        cumulative_return = (1 + returns).prod() - 1
        annual_return = (1 + returns.mean()) ** 252 - 1
        annual_vol = returns.std() * np.sqrt(252)

        # Win rate
        win_rate = (returns > 0).sum() / len(returns)

        # Largest wins/losses
        largest_win = returns.max()
        largest_loss = returns.min()

        # Signal effectiveness
        signal_active = (signals == 1).sum()
        win_when_signal = returns[signals == 1].mean() if signal_active > 0 else 0

        summary = f"""
        === BACKTEST SUMMARY ===
        Total Return: {cumulative_return:.2%}
        Annual Return: {annual_return:.2%}
        Annual Volatility: {annual_vol:.2%}
        Sharpe Ratio: {ModelEvaluation.calculate_sharpe_ratio(returns):.2f}
        Win Rate: {win_rate:.1%}

        Largest Win: {largest_win:.2%}
        Largest Loss: {largest_loss:.2%}

        Signal Effectiveness:
        - Active {signal_active} days ({signal_active/len(signals):.1%})
        - Avg return when signaled: {win_when_signal:.2%}
        """

        return {
            'cumulative_return': cumulative_return,
            'annual_return': annual_return,
            'sharpe_ratio': ModelEvaluation.calculate_sharpe_ratio(returns),
            'win_rate': win_rate,
            'summary': summary
        }


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Data Science Framework loaded. Use from your pipelines.")
