"""Full historical replay: screener recommends, regime gates, outcomes judge.

Replays Darvas-style breakout/breakdown signals over the full OHLCV panel,
labels each signal date with the market's point-in-time trend regime (Markov
state of the equal-weight market index) and volatility regime (expanding
percentile of rolling vol), then scores forward 5d/21d excess returns.

Statistics are clustered by signal date: per-date mean excess first, then a
t-stat across dates — signals sharing a date share market moves, so
per-signal t-stats would be badly overstated (the defect in the small-sample
live tracking this replay extends).

Signal definitions (documented proxies for the live daily_scanner):
  BREAKOUT_BUY   close crosses above the prior 55-day box high (current bar
                 excluded from the box), close > EMA50, RSI14 in [50, 80]
  BREAKDOWN_SELL close crosses below the prior 55-day box low, close < EMA50

Run:  python -m price_prediction.replay --market US IN JP KR EU UK CN HK
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from .data import load_panel
# regime labels are computed inline on the market index

TREND_NAMES = {0: "bear", 1: "chop", 2: "bull", -1: "warmup"}
MIN_OBS = 300          # symbol must have this many days to participate
MIN_NAMES = 50         # market index needs this many names per day
UNIVERSE_N = 1000      # top names by median dollar volume
BOX_WIN = 55
HORIZONS = (5, 21)


def _rsi14(close: pd.DataFrame) -> pd.DataFrame:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, min_periods=14).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14).mean()
    return 100 - 100 / (1 + up / (dn + 1e-12))


def _wide(panel: pd.DataFrame, col: str) -> pd.DataFrame:
    return panel.pivot_table(index="Date", columns="Symbol", values=col,
                             aggfunc="last").sort_index()


def build_signals(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (signals long-frame, per-date market/regime frame)."""
    close = _wide(panel, "Close")
    high = _wide(panel, "High")
    low = _wide(panel, "Low")
    vol = _wide(panel, "Volume")
    # Liquid universe: top names by median dollar volume among long-history
    # symbols. Kills penny-stock artifacts in the breadth index and benchmark,
    # and trims (not eliminates) delisting-survivorship in the sell leg.
    # Full-sample liquidity ranking is mild lookahead — documented tradeoff.
    hist_ok = close.columns[close.notna().sum() >= MIN_OBS]
    if len(hist_ok) < MIN_NAMES:
        raise ValueError(
            f"only {len(hist_ok)} symbols with >= {MIN_OBS} obs — panel too shallow")
    dv = (close[hist_ok] * vol[hist_ok]).median()
    keep = dv.nlargest(UNIVERSE_N).index
    close, high, low = close[keep], high[keep], low[keep]

    ret = close.pct_change()
    # kill bad ticks / unflagged splits: mask absurd single-day moves
    bad = ret.abs() > 0.6
    close = close.mask(bad)
    ret = close.pct_change()

    ema50 = close.ewm(span=50, min_periods=50).mean()
    rsi = _rsi14(close)
    box_hi = high.rolling(BOX_WIN).max().shift(1)   # current bar excluded
    box_lo = low.rolling(BOX_WIN).min().shift(1)

    buy = (close > box_hi) & (close.shift(1) <= box_hi.shift(1)) \
        & (close > ema50) & (rsi >= 50) & (rsi <= 80)
    sell = (close < box_lo) & (close.shift(1) >= box_lo.shift(1)) \
        & (close < ema50)

    # forward returns and per-date cross-sectional market median
    fwd = {h: close.shift(-h) / close - 1 for h in HORIZONS}
    mkt_med = {h: fwd[h].median(axis=1) for h in HORIZONS}

    # Market index for regimes: trimmed mean of the top-20 turnover names with
    # near-complete coverage (blue-chip basket). The full-universe breadth
    # median compounds hugely negative in IN/KR/CN (sporadic microcaps +
    # decliner-heavy turnover tail) and mislabels the whole decade "bear";
    # the basket tracks each market's real index to within reason.
    cov_full = close.columns[close.notna().mean() >= 0.95]
    basket = (dv.reindex(cov_full)).nlargest(20).index
    bret = ret[basket]
    n_b = bret.notna().sum(axis=1)
    trimmed = (bret.sum(axis=1) - bret.max(axis=1) - bret.min(axis=1)) / (n_b - 2)
    idx_ret = trimmed.where(n_b > 4).dropna()
    # market trend: index vs its EMA100 and the EMA's slope (balanced, PIT)
    idx = (1 + idx_ret).cumprod()
    ema = idx.ewm(span=100, min_periods=100).mean()
    slope = ema.diff(5)
    trend = pd.Series(1, index=idx.index)               # chop
    trend[(idx > ema) & (slope > 0)] = 2                # bull
    trend[(idx < ema) & (slope < 0)] = 0                # bear
    trend[ema.isna()] = -1
    vol21 = idx_ret.rolling(21).std()
    vol_pct = vol21.expanding(252).apply(
        lambda w: (w[:-1] <= w[-1]).mean() if len(w) > 1 else np.nan, raw=True)
    vol_reg = pd.cut(vol_pct, [0, 1 / 3, 2 / 3, 1.0001],
                     labels=["LOW", "MID", "HIGH"])
    dates = pd.DataFrame({
        "trend": trend.map(TREND_NAMES).reindex(idx_ret.index),
        "vol_regime": vol_reg,
    })

    frames = []
    for name, mask in [("BREAKOUT_BUY", buy), ("BREAKDOWN_SELL", sell)]:
        s = mask.stack()
        s = s[s]
        f = pd.DataFrame(index=s.index)
        f["signal"] = name
        for h in HORIZONS:
            f[f"fwd{h}"] = fwd[h].stack().reindex(s.index)
            f[f"ex{h}"] = f[f"fwd{h}"] - mkt_med[h].reindex(
                s.index.get_level_values(0)).values
        frames.append(f)
    sig = pd.concat(frames).reset_index().rename(
        columns={"level_0": "Date", "level_1": "Symbol"})
    sig = sig.merge(dates, left_on="Date", right_index=True, how="left")
    return sig, dates


def clustered_stats(sig: pd.DataFrame, h: int, by: list[str],
                    min_dates: int = 100) -> pd.DataFrame:
    """Per-date means first, then t across dates. Cells under min_dates dropped."""
    col = f"ex{h}"
    d = sig.dropna(subset=[col])
    day = d.groupby(["Date"] + by, observed=True)[col].mean().reset_index()
    g = day.groupby(by, observed=True)[col]
    out = pd.DataFrame({
        "n_signals": d.groupby(by, observed=True)[col].size(),
        "n_dates": g.size(),
        "mean_excess_%": g.mean() * 100,
        "t_clustered": g.mean() / (g.std() / np.sqrt(g.size().clip(lower=2))),
        "hit_%": d.groupby(by, observed=True)[col].apply(lambda x: (x > 0).mean() * 100),
    })
    return out[out.n_dates >= min_dates].round(2)


def run_market(market: str, out_dir: str) -> None:
    print(f"\n================ {market} ================")
    sig, _ = build_signals(load_panel(market))
    sig.to_parquet(os.path.join(out_dir, f"replay_signals_{market.lower()}.parquet"))
    for h in HORIZONS:
        print(f"\n--- {market} h={h}d: signal alone ---")
        print(clustered_stats(sig, h, ["signal"]).to_string())
        print(f"\n--- {market} h={h}d: signal x trend regime ---")
        print(clustered_stats(sig, h, ["signal", "trend"]).to_string())
        print(f"\n--- {market} h={h}d: signal x vol regime ---")
        print(clustered_stats(sig, h, ["signal", "vol_regime"]).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", nargs="+", default=["US", "IN", "JP", "KR", "CN"])
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for m in args.market:
        try:
            run_market(m, args.out)
        except Exception as e:
            print(f"{m}: FAILED — {e}")


if __name__ == "__main__":
    main()
