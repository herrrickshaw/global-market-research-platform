#!/usr/bin/env python3
"""
price_band_migration.py — do cheap stocks stay cheap, and does it pay?

THE QUESTION, from the masaladeutsch series ("Do Cheap Stocks Stay Cheap?",
"Below Rs 250 Is Where the Real Risk Lives", "Rs 0-50 Is Its Own Category"):
Indian retail sorts stocks by SHARE PRICE, treating a Rs 30 stock as cheap. Price
level is not valuation — it is an artefact of how many shares were issued — but
it demonstrably drives behaviour, so the empirical question stands on its own:
where does a stock in each price band end up a year later, and what did holding
it return?

🔴 TWO PRICES ARE NEEDED AND USING ONE FOR BOTH JOBS WRECKS THE STUDY.
  * BAND MEMBERSHIP uses the RAW traded price, because that is the number the
    investor sees and sorts on. Assigning bands on split-adjusted history would
    place a stock in a band it never actually traded in.
  * RETURNS use the SPLIT-ADJUSTED series. A 10:1 split drops the raw price 90%
    overnight; measured raw, every split reads as a catastrophic loss AND as a
    migration three bands down. Both effects point the same way, so the naive
    version would "discover" that expensive stocks crash and become cheap — an
    artefact of corporate actions, not a finding.

🔴 SURVIVORSHIP IS REPORTED, NOT SILENTLY DROPPED. A stock present at t and
absent at t+12M is usually a delisting or suspension, and those are concentrated
in the cheapest band — exactly where the study is most interesting. Dropping them
quietly would make the microcap band look far safer than it was, so attrition is
printed per band and the returns are labelled as survivor-conditional.

    python3 price_band_migration.py
    python3 price_band_migration.py --horizon 24
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

RAW = os.path.expanduser("~/.cache/market-warehouse/ohlcv/IN")
ADJ = os.path.expanduser("~/.cache/market-warehouse/ohlcv_adj/IN")

# Bands follow the series' own cuts rather than equal quantiles: the argument
# there is that Rs 0-50 behaves as its own category and that Rs 250 is where the
# character changes, which quantiles would blur away.
EDGES = [0, 50, 250, 1000, np.inf]
LABELS = ["Rs 0-50", "Rs 50-250", "Rs 250-1000", "Rs 1000+"]


def load(path: str, col: str = "Close") -> pd.DataFrame:
    fs = sorted(glob.glob(f"{path}/*.parquet"))
    if not fs:
        raise SystemExit(f"no partitions under {path}")
    d = pd.concat((pd.read_parquet(f, columns=["Date", "Symbol", col]) for f in fs),
                  ignore_index=True)
    d["Date"] = pd.to_datetime(d["Date"])
    d["Symbol"] = d["Symbol"].astype(str).str.upper()
    return d


def month_end(d: pd.DataFrame, col: str) -> pd.DataFrame:
    """Last observation per symbol per month."""
    d = d.sort_values("Date")
    d["ym"] = d["Date"].values.astype("datetime64[M]")
    return d.groupby(["Symbol", "ym"], as_index=False).last()[["Symbol", "ym", col]]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--horizon", type=int, default=12, help="months forward")
    p.add_argument("--min-price", type=float, default=1.0,
                   help="drop sub-rupee names: their returns are quantisation noise")
    a = p.parse_args()

    raw = month_end(load(RAW), "Close").rename(columns={"Close": "raw"})
    adj = month_end(load(ADJ), "Close").rename(columns={"Close": "adj"})
    m = raw.merge(adj, on=["Symbol", "ym"], how="inner")
    m = m[m.raw >= a.min_price]
    print(f"# Price-band migration — {a.horizon}-month horizon\n")
    print(f"{len(m):,} symbol-months, {m.Symbol.nunique():,} symbols, "
          f"{m.ym.min():%Y-%m} to {m.ym.max():%Y-%m}")

    m["band"] = pd.cut(m.raw, EDGES, labels=LABELS, right=False)

    # Forward join: same symbol, `horizon` months later.
    fwd = m[["Symbol", "ym", "raw", "adj", "band"]].copy()
    fwd["ym"] = fwd["ym"] - pd.DateOffset(months=a.horizon)
    fwd = fwd.rename(columns={"raw": "raw_f", "adj": "adj_f", "band": "band_f"})
    j = m.merge(fwd, on=["Symbol", "ym"], how="left")

    print("\n## Attrition — how many simply are not there a year later\n")
    att = j.groupby("band", observed=True).apply(
        lambda g: pd.Series({"observed": len(g),
                             "survived": int(g.adj_f.notna().sum()),
                             "gone_%": 100 * (1 - g.adj_f.notna().mean())}),
        include_groups=False)
    print(att.to_string(float_format=lambda x: f"{x:10,.1f}"))
    print("\n🔴 Everything below is SURVIVOR-CONDITIONAL: the missing names are")
    print("   disproportionately in the cheap bands and their outcomes are unknown,")
    print("   so cheap-band returns are an upper bound, not an estimate.")

    s = j.dropna(subset=["adj_f"]).copy()
    s["ret_%"] = (s.adj_f / s.adj - 1) * 100

    print(f"\n## Where does each band end up after {a.horizon}M? (row %)\n")
    tm = pd.crosstab(s.band, s.band_f, normalize="index") * 100
    print(tm.to_string(float_format=lambda x: f"{x:8.1f}"))

    print(f"\n## Forward {a.horizon}M return by starting band (split-adjusted)\n")
    r = s.groupby("band", observed=True)["ret_%"].agg(
        n="size", mean="mean", median="median",
        p25=lambda x: x.quantile(.25), p75=lambda x: x.quantile(.75),
        loss_rate=lambda x: (x < 0).mean() * 100)
    print(r.to_string(float_format=lambda x: f"{x:10.1f}"))

    print("\n## Does MIGRATING pay more than the band you started in?\n")
    up = s[s.band.astype(str) != s.band_f.astype(str)]
    stay = s[s.band.astype(str) == s.band_f.astype(str)]
    print(f"   stayed in band : n={len(stay):>7,}  mean {stay['ret_%'].mean():>7.1f}%  "
          f"median {stay['ret_%'].median():>6.1f}%")
    print(f"   changed band   : n={len(up):>7,}  mean {up['ret_%'].mean():>7.1f}%  "
          f"median {up['ret_%'].median():>6.1f}%")
    print("\n   (Tautological by construction — a band change IS a large price move —")
    print("    so this is a decomposition of where the return came from, not a signal.")
    print("    The tradeable question is the transition matrix above: what fraction of")
    print("    each band moves UP, knowable only ex ante from the band itself.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
