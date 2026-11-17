#!/usr/bin/env python3
"""
correlation_regime_spectrum.py — executes BACKTEST_QUEUE.md #3/#9: does the
spectral shape of the market's own correlation matrix carry regime
information the existing gate (an EMA-vs-index trend + a volatility
percentile, market_regime.py:70-81) does not have?

METHOD (Halperin 2607.19005 + the m- participation-ratio companion the daily
literature task found, 2608.09641): rolling 60-trading-day correlation matrix
over a liquid universe, same spectral_stats() used in factor_redundancy.py
but applied to STOCK RETURNS instead of factor exposures. Two numbers per
window: participation ratio (effective independent stocks -- low means the
market is moving as one correlated block) and absorption ratio of PC1 (share
of variance in the single largest mode -- classic "everyone selling
together" signature).

DATA: nse_deep.parquet (10.5y official bhavcopy, same panel used for the
2026-08-22 entry-bar A/B) -- no network, no yfinance.

This is a MEASUREMENT script, not a new gate. It answers "does this carry
information" before anyone wires it into market_regime.py -- exactly the
"log first, gate later" instruction in BACKTEST_QUEUE.md #9.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from factor_redundancy import spectral_stats  # noqa: E402

PANEL = "/Users/umashankar/market-pipeline/data/bhavcopy_cache/nse_deep.parquet"
N_SYMBOLS = 150
WINDOW = 60
OUT = Path(__file__).resolve().parent / "correlation_regime_spectrum.csv"


def load_wide():
    d = pd.read_parquet(PANEL, columns=["Date", "Symbol", "Close", "Volume"])
    d = d.dropna(subset=["Close"])
    d["turn"] = d["Close"] * d["Volume"]
    liq = d.groupby("Symbol")["turn"].median().sort_values(ascending=False)
    counts = d.groupby("Symbol").size()
    ok = [s for s in liq.index if counts.get(s, 0) >= 1500][:N_SYMBOLS]
    d = d[d["Symbol"].isin(ok)]
    wide = d.pivot_table(index="Date", columns="Symbol", values="Close", aggfunc="last").sort_index()
    return wide


def main():
    wide = load_wide()
    rets = wide.pct_change()
    print(f"  universe: {wide.shape[1]} symbols, {wide.shape[0]} trading days "
          f"({wide.index.min().date()} -> {wide.index.max().date()})")

    dates, prs, ar1s, n_used = [], [], [], []
    idx = rets.index
    for i in range(WINDOW, len(idx), 5):  # step 5 trading days, ~weekly, for tractability
        win = rets.iloc[i - WINDOW:i]
        col_ok = win.notna().sum() >= WINDOW * 0.9  # need most of the window populated
        w = win.loc[:, col_ok]
        if w.shape[1] < 30:
            continue
        corr = w.corr().values
        if not np.isfinite(corr).all():
            continue
        s = spectral_stats(corr)
        dates.append(idx[i]); prs.append(s["participation_ratio"])
        ar1s.append(s["eigenvalues"][0] / s["eigenvalues"].sum())
        n_used.append(w.shape[1])

    out = pd.DataFrame({"date": dates, "participation_ratio": prs,
                        "pc1_absorption": ar1s, "n_symbols": n_used})
    out.to_csv(OUT, index=False)
    print(f"  {len(out)} windows scored, -> {OUT}")

    print(f"\n  PARTICIPATION RATIO (effective independent stocks, of ~{N_SYMBOLS}):")
    print(f"    overall:  mean={out.participation_ratio.mean():.1f}  "
          f"min={out.participation_ratio.min():.1f}  max={out.participation_ratio.max():.1f}")
    print(f"\n  lowest-PR (most correlated / one-block) windows:")
    for _, r in out.nsmallest(5, "participation_ratio").iterrows():
        print(f"    {r.date.date()}  PR={r.participation_ratio:.1f}  "
              f"PC1={r.pc1_absorption:.1%}  n={r.n_symbols:.0f}")
    print(f"\n  highest-PR (most dispersed) windows:")
    for _, r in out.nlargest(5, "participation_ratio").iterrows():
        print(f"    {r.date.date()}  PR={r.participation_ratio:.1f}  "
              f"PC1={r.pc1_absorption:.1%}  n={r.n_symbols:.0f}")

    # sanity check: does PR actually DROP around known stress -- 2020 COVID
    # crash is in-sample (panel starts 2016) and is the one universally-known
    # stress event to eyeball against, independent of anything this repo claims.
    covid = out[(out.date >= "2020-02-15") & (out.date <= "2020-05-01")]
    normal = out[(out.date >= "2019-06-01") & (out.date <= "2019-12-01")]
    if len(covid) and len(normal):
        print(f"\n  SANITY CHECK — Feb-May 2020 (COVID crash) vs Jun-Dec 2019 (calm):")
        print(f"    COVID window PR:  mean={covid.participation_ratio.mean():.1f}  "
              f"min={covid.participation_ratio.min():.1f}")
        print(f"    calm window PR:   mean={normal.participation_ratio.mean():.1f}  "
              f"min={normal.participation_ratio.min():.1f}")
        print(f"    {'PASSES' if covid.participation_ratio.mean() < normal.participation_ratio.mean() else 'FAILS'} "
              f"the sanity check (PR should be LOWER during the crash — a correlated selloff "
              f"has fewer independent directions of movement, not more).")


if __name__ == "__main__":
    main()
