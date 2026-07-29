"""First-order Markov chain over discrete market regimes.

States are formed from rolling return + volatility so the chain sees
"bull / bear / choppy" rather than raw daily noise. The model estimates the
transition matrix on training data only and predicts P(next state) from the
current state; the trading read-out is the expected next-day return of the
predicted state distribution.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STATE_NAMES = ["bear", "chop", "bull"]


def label_states(log_ret: pd.Series, trend_win: int = 21, vol_win: int = 21,
                 trend_band: float = 0.25) -> pd.Series:
    """3 regimes from rolling annualised trend, banded by rolling vol.

    bull  = rolling mean return >  +trend_band * rolling std / sqrt(win)
    bear  = rolling mean return <  -trend_band * rolling std / sqrt(win)
    chop  = otherwise
    """
    mu = log_ret.rolling(trend_win).mean()
    se = log_ret.rolling(vol_win).std() / np.sqrt(trend_win)
    state = pd.Series(1, index=log_ret.index)  # chop
    state[mu > trend_band * se] = 2            # bull
    state[mu < -trend_band * se] = 0           # bear
    state[mu.isna() | se.isna()] = -1          # warm-up
    return state.astype(int)


class MarkovRegimeModel:
    def __init__(self, n_states: int = 3, laplace: float = 1.0):
        self.n = n_states
        self.laplace = laplace
        self.T = np.full((n_states, n_states), 1.0 / n_states)
        self.state_ret = np.zeros(n_states)

    def fit(self, states: pd.Series, log_ret: pd.Series) -> "MarkovRegimeModel":
        s = states[states >= 0]
        counts = np.full((self.n, self.n), self.laplace)
        prev, nxt = s.values[:-1], s.values[1:]
        for a, b in zip(prev, nxt):
            counts[a, b] += 1
        self.T = counts / counts.sum(axis=1, keepdims=True)
        # expected next-day return conditional on today's state
        aligned = log_ret.shift(-1).reindex(states.index)
        for k in range(self.n):
            vals = aligned[states == k].dropna()
            self.state_ret[k] = vals.mean() if len(vals) else 0.0
        return self

    def predict_return(self, current_state: int) -> float:
        """E[next-day return] = sum_k P(next=k | now) * E[ret | state k]."""
        if current_state < 0:
            return 0.0
        return float(self.T[current_state] @ self.state_ret)

    def predict_proba(self, current_state: int) -> np.ndarray:
        if current_state < 0:
            return np.full(self.n, 1.0 / self.n)
        return self.T[current_state]
