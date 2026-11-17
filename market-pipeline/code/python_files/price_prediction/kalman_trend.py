"""Local-linear-trend Kalman filter on log price (pure numpy).

State x = [level, slope]; observation y = log(Close).
    level_t = level_{t-1} + slope_{t-1} + w1
    slope_t = slope_{t-1}            + w2
    y_t     = level_t                + v

The filter separates the persistent trend from observation noise; the
prediction read-out is the filtered slope (expected next-day log return).
Process/observation variances are set from the series' own variance with a
signal-to-noise ratio q — no look-ahead beyond each point's own past.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class KalmanTrendModel:
    def __init__(self, q_level: float = 1e-5, q_slope: float = 1e-7, r_obs: float = 1e-3):
        self.Q = np.diag([q_level, q_slope])
        self.R = r_obs
        self.F = np.array([[1.0, 1.0], [0.0, 1.0]])
        self.H = np.array([[1.0, 0.0]])

    def filter(self, log_price: pd.Series) -> pd.DataFrame:
        """Run the filter forward; returns level, slope, innovation per day."""
        y = log_price.values
        n = len(y)
        x = np.array([y[0], 0.0])
        P = np.eye(2)
        out = np.zeros((n, 3))
        for t in range(n):
            # predict
            x = self.F @ x
            P = self.F @ P @ self.F.T + self.Q
            # update
            innov = (y[t] - self.H @ x).item()
            S = (self.H @ P @ self.H.T + self.R).item()
            K = (P @ self.H.T) / S
            x = x + (K * innov).ravel()
            P = (np.eye(2) - K @ self.H) @ P
            out[t] = [x[0], x[1], innov]
        return pd.DataFrame(out, index=log_price.index,
                            columns=["level", "slope", "innovation"])

    def predict_return(self, log_price: pd.Series) -> pd.Series:
        """E[next-day log return] at each t, using data up to t only."""
        return self.filter(log_price)["slope"]
