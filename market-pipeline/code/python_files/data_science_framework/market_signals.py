"""
Market Signal Generation: Practical trading signal framework.
Synthesizes pattern mining (Han/Kamber) with time series analysis (McKinney).

Key patterns:
- Darvas Box: trend following (prices near 52W high + above EMA50)
- Mean Reversion: oversold/overbought (RSI, Bollinger Bands)
- Volume Breakout: confirmation (volume spike + price move)
- Regime Detection: adapt strategy per market character
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class Signal:
    """Standardized signal representation."""
    date: pd.Timestamp
    ticker: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD', 'WATCH'
    score: float  # 0-10
    components: Dict[str, float]  # individual signal contributions
    confidence: float  # 0-1
    reasons: List[str]


class TrendSignals:
    """Trend-following signals (Darvas-style)."""

    @staticmethod
    def darvas_box(close: pd.Series, high_52w: float, ema_50: float) -> Dict[str, float]:
        """
        Darvas Box: Price within 2% of 52W high + above EMA50.
        Scoring: each condition adds points.
        """
        score = 0
        components = {}

        current_price = close.iloc[-1]

        # Component 1: Near 52W high (0-2 points)
        distance_from_high = (high_52w - current_price) / high_52w
        if distance_from_high < 0.02:
            score += 2
            components['near_52w_high'] = 2
        elif distance_from_high < 0.05:
            score += 1
            components['near_52w_high'] = 1
        else:
            components['near_52w_high'] = 0

        # Component 2: Above EMA50 (0-2 points)
        if current_price > ema_50:
            distance_above_ema = (current_price - ema_50) / ema_50
            if distance_above_ema > 0.05:
                score += 2
                components['above_ema50'] = 2
            else:
                score += 1
                components['above_ema50'] = 1
        else:
            components['above_ema50'] = 0

        # Component 3: Range strength (0-1 point)
        # Last 50 days price range
        recent_high = close.tail(50).max()
        recent_low = close.tail(50).min()
        range_strength = (current_price - recent_low) / (recent_high - recent_low)
        if range_strength > 0.7:
            score += 1
            components['range_strength'] = 1
        else:
            components['range_strength'] = 0

        return {'score': score, 'components': components, 'max_score': 5}

    @staticmethod
    def momentum_breakout(close: pd.Series, volume: pd.Series, lookback: int = 20) -> Dict[str, float]:
        """
        Price breakout above previous N-day high with volume surge.
        Confirms breakouts are real (not false spikes).
        """
        current_price = close.iloc[-1]
        current_volume = volume.iloc[-1]
        avg_volume = volume.tail(lookback).mean()
        prev_high = close.tail(lookback + 1).iloc[:-1].max()

        score = 0
        components = {}

        # Breakout above previous high
        if current_price > prev_high * 1.01:  # 1% above
            score += 2
            components['price_breakout'] = 2
        else:
            components['price_breakout'] = 0

        # Volume confirmation
        if current_volume > avg_volume * 1.5:
            score += 2
            components['volume_surge'] = 2
        else:
            components['volume_surge'] = 0

        return {'score': score, 'components': components, 'max_score': 4}


class MeanReversionSignals:
    """Mean-reversion signals (oversold/overbought)."""

    @staticmethod
    def rsi_signal(rsi: float, period: int = 14) -> Dict[str, float]:
        """
        RSI-based signals: oversold (<30), overbought (>70).
        For mean-reverting markets.
        """
        score = 0
        signal_type = 'HOLD'
        components = {}

        # Oversold signal (buy)
        if rsi < 30:
            score = 10 - (rsi / 3)  # Stronger below 20
            signal_type = 'BUY'
            components['oversold'] = score
        # Overbought signal (sell)
        elif rsi > 70:
            score = (rsi - 70) * 0.6 + 2
            signal_type = 'SELL'
            components['overbought'] = score
        else:
            components['neutral'] = 0

        return {'score': min(score, 10), 'signal_type': signal_type, 'components': components}

    @staticmethod
    def bollinger_band_signal(close: float, sma: float, std: float, period: int = 20) -> Dict[str, float]:
        """
        Bollinger Band mean reversion.
        Buy at lower band, sell at upper band.
        """
        upper_band = sma + (2 * std)
        lower_band = sma - (2 * std)

        score = 0
        signal_type = 'HOLD'
        components = {}

        # Below lower band (buy)
        if close < lower_band:
            band_percentile = (close - lower_band) / (sma - lower_band)
            score = max(10 - abs(band_percentile) * 10, 3)
            signal_type = 'BUY'
            components['below_lower_band'] = score
        # Above upper band (sell)
        elif close > upper_band:
            band_percentile = (close - upper_band) / (upper_band - sma)
            score = max(10 - abs(band_percentile) * 10, 3)
            signal_type = 'SELL'
            components['above_upper_band'] = score
        else:
            components['neutral'] = 0

        return {'score': min(score, 10), 'signal_type': signal_type, 'components': components}


class RegimeDetection:
    """
    Detect market regime: trending vs mean-reverting.
    Adapt strategy per regime (critical for robustness).
    """

    @staticmethod
    def hurst_exponent(series: pd.Series, lags: int = 100) -> float:
        """
        Hurst Exponent: 0.5 = random, <0.5 = mean-reverting, >0.5 = trending.
        Guides strategy selection.
        """
        tau = []
        for lag in range(1, lags):
            # Log returns
            returns = np.log(series / series.shift(lag))
            # Variance
            tau.append(np.sqrt(np.var(returns)))

        # Fit line to log-log plot
        from scipy.stats import linregress
        x = np.log(range(1, len(tau) + 1))
        y = np.log(tau)
        slope, _, _, _, _ = linregress(x, y)

        hurst = slope * 2

        return hurst

    @staticmethod
    def regime_from_hurst(hurst: float) -> str:
        """Convert Hurst to regime."""
        if hurst < 0.45:
            return 'MEAN_REVERTING'
        elif hurst > 0.55:
            return 'TRENDING'
        else:
            return 'RANDOM'

    @staticmethod
    def calculate_rolling_correlation(price: pd.Series, lookback: int = 50) -> float:
        """
        Autocorrelation of returns.
        Positive = trending, Negative = mean-reverting.
        """
        returns = price.pct_change().dropna()
        return returns.autocorr(lag=1)


class SignalComposition:
    """Combine multiple signals into unified recommendation."""

    @staticmethod
    def composite_score(
        components: Dict[str, float],
        weights: Dict[str, float] = None
    ) -> Tuple[float, str]:
        """
        Weighted combination of signals.
        Example weights: {'darvas': 0.4, 'rsi': 0.3, 'volume': 0.3}
        """
        if weights is None:
            weights = {k: 1 / len(components) for k in components.keys()}

        score = sum(components.get(k, 0) * weights.get(k, 0) for k in components.keys())
        score = min(max(score, 0), 10)  # Clamp to 0-10

        # Convert score to signal
        if score >= 7:
            signal = 'BUY'
        elif score >= 5:
            signal = 'WATCH'
        elif score >= 3:
            signal = 'HOLD'
        else:
            signal = 'SELL'

        return score, signal

    @staticmethod
    def generate_report(signal: Signal) -> str:
        """Narrative explanation of signal (storytelling)."""
        report = f"""
        === SIGNAL REPORT ===
        Ticker: {signal.ticker}
        Date: {signal.date.strftime('%Y-%m-%d')}

        Signal: {signal.signal_type} (Score: {signal.score:.1f}/10)
        Confidence: {signal.confidence:.1%}

        Components:
        {chr(10).join([f'  - {k}: {v:.1f}' for k, v in signal.components.items()])}

        Reasons:
        {chr(10).join([f'  • {reason}' for reason in signal.reasons])}
        """
        return report


class SignalBacktest:
    """Backtest signals: from generation to P&L."""

    @staticmethod
    def apply_signals(prices: pd.Series, signals: pd.Series) -> pd.Series:
        """
        Convert signals to returns.
        Assumes: BUY=long, SELL=short/flat, HOLD=do nothing.
        """
        # Signal to position: 1=long, 0=flat, -1=short
        position = signals.map({'BUY': 1, 'HOLD': 0, 'SELL': -1}).fillna(0)

        # Daily returns
        returns = prices.pct_change()

        # Strategy returns = position * returns
        strategy_returns = position.shift(1) * returns  # Shift: signal today, trade tomorrow

        return strategy_returns

    @staticmethod
    def metric_summary(returns: pd.Series, risk_free_rate: float = 0.05) -> Dict[str, float]:
        """Full backtest metrics."""
        annual_return = (1 + returns.mean()) ** 252 - 1
        annual_vol = returns.std() * np.sqrt(252)
        sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0

        cumulative_return = (1 + returns).cumprod()
        peak = cumulative_return.expanding().max()
        drawdown = (cumulative_return - peak) / peak
        max_drawdown = drawdown.min()

        win_rate = (returns > 0).sum() / len(returns)
        profit_factor = returns[returns > 0].sum() / abs(returns[returns < 0].sum())

        return {
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_return': (1 + returns).prod() - 1
        }
