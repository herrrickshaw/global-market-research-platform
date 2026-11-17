"""Panel loading + universe selection for prediction models."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

LTM_DIR = os.environ.get(
    "LTM_DIR", os.path.expanduser("~/repos/global-stock-screener/cache_seed/ltm")
)


def load_panel(market: str) -> pd.DataFrame:
    """Long panel [Date, Symbol, Open, High, Low, Close, Volume] for a market."""
    path = os.path.join(LTM_DIR, f"{market.upper()}.parquet")
    df = pd.read_parquet(path)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["Symbol", "Date"]).reset_index(drop=True)
    return df


def top_liquid_symbols(panel: pd.DataFrame, n: int = 20, min_years: float = 8.0) -> list[str]:
    """Most-liquid symbols (median daily dollar volume) with a long history."""
    g = panel.groupby("Symbol")
    span_days = (g["Date"].max() - g["Date"].min()).dt.days
    long_enough = span_days[span_days >= min_years * 365].index
    sub = panel[panel["Symbol"].isin(long_enough)]
    dollar_vol = (sub["Close"] * sub["Volume"]).groupby(sub["Symbol"]).median()
    # Guard against data glitches: require a sane, mostly-continuous series
    counts = sub.groupby("Symbol")["Date"].count()
    ok = counts[counts >= min_years * 200].index
    return dollar_vol.loc[dollar_vol.index.isin(ok)].nlargest(n).index.tolist()


def symbol_series(panel: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Clean single-symbol frame indexed by Date with log returns."""
    df = panel[panel["Symbol"] == symbol].set_index("Date").sort_index()
    df = df[df["Close"] > 0]
    df = df[~df.index.duplicated(keep="last")]
    df["log_ret"] = np.log(df["Close"]).diff()
    # Drop absurd jumps (bad ticks / unflagged splits) rather than model them
    df = df[df["log_ret"].abs().fillna(0) < 0.5]
    df["log_ret"] = np.log(df["Close"]).diff()
    return df.dropna(subset=["log_ret"])
