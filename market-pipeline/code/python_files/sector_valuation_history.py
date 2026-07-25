#!/usr/bin/env python3
"""
sector_valuation_history.py — how has the market priced each segment over time, and how does
it price them now? For each year × sector we take the median P/E and median ROE, so you can
see valuations inflate and deflate (dot-com, GFC, 2021, AI) and whether fundamentals kept up.

The gap between the P/E trend and the ROE trend IS the speculation premium: when P/E climbs
while ROE is flat, the market is paying more for the same performance.

US (deepest fundamentals + prices). Sectors from Damodaran's 48k-company map.
Output: reports/sector_valuation_history.{csv,png}
"""
from __future__ import annotations
import glob
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/US"


def sector_map() -> dict:
    dm = pd.read_parquet(REP / "damodaran_sector_map.parquet")
    dm = dm[dm.Country == "United States"]
    return dict(zip(dm.Ticker.astype(str), dm["Primary Sector"]))


def year_end_price() -> pd.DataFrame:
    px = pd.concat((pd.read_parquet(p, columns=["Date", "Symbol", "Close"])
                    for p in sorted(glob.glob(f"{WH}/year=*.parquet"))), ignore_index=True)
    px["Date"] = pd.to_datetime(px["Date"]); px["yr"] = px.Date.dt.year
    ye = px.sort_values("Date").groupby(["Symbol", "yr"], as_index=False).last()
    return ye.rename(columns={"Symbol": "ticker", "Close": "price"})[["ticker", "yr", "price"]]


def main() -> int:
    f = pd.read_parquet(f"{FH}/US.parquet")
    f["yr"] = pd.to_datetime(f.fy_end, errors="coerce").dt.year
    f = f[(f.equity > 0) & (f.shares > 0) & f.net_income.notna()].copy()
    f["eps"] = f.net_income / f.shares; f["roe"] = f.net_income / f.equity
    d = f.merge(year_end_price(), on=["ticker", "yr"], how="inner")
    d["pe"] = (d.price / d.eps).where(d.eps > 0)
    d = d[(d.pe > 0) & (d.pe < 200) & (d.roe.abs() < 2)]
    sec = sector_map(); d["sector"] = d.ticker.astype(str).map(sec)
    d = d[d.sector.notna() & (d.yr >= 2004) & (d.yr <= 2025)]

    agg = (d.groupby(["yr", "sector"])
           .agg(pe=("pe", "median"), roe=("roe", "median"), n=("pe", "size"))
           .reset_index())
    agg = agg[agg.n >= 8]
    agg.to_csv(REP / "sector_valuation_history.csv", index=False)

    # keep the best-covered sectors
    keep = agg.groupby("sector").n.sum().sort_values(ascending=False).head(7).index.tolist()
    a = agg[agg.sector.isin(keep)]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    cmap = plt.cm.tab10
    for i, s in enumerate(keep):
        g = a[a.sector == s].sort_values("yr")
        ax1.plot(g.yr, g.pe, marker="o", ms=3, lw=1.8, color=cmap(i), label=s)
        ax2.plot(g.yr, g.roe * 100, marker="o", ms=3, lw=1.8, color=cmap(i), label=s)
    for ax, yr, lab in [(ax1, 2000, ""), (ax1, 2009, "GFC"), (ax1, 2021, "2021"), (ax1, 2000, "dot-com")]:
        pass
    for x, lab in [(2009, "GFC"), (2021, "2021 peak"), (2023, "AI run")]:
        ax1.axvline(x, ls=":", c="grey", alpha=.5); ax1.text(x, ax1.get_ylim()[1]*0.95, lab, fontsize=7, rotation=90, va="top")
    ax1.set_ylabel("median P/E"); ax1.set_title("How the market prices each US segment over time — P/E (valuation)", fontsize=12)
    ax1.legend(fontsize=8, ncol=2, loc="upper left"); ax1.grid(alpha=.3)
    ax2.set_ylabel("median ROE %"); ax2.set_xlabel("year")
    ax2.set_title("...and the fundamentals underneath — ROE. P/E climbing while ROE is flat = speculation premium", fontsize=11)
    ax2.grid(alpha=.3)
    plt.tight_layout(); plt.savefig(REP / "sector_valuation_history.png", dpi=140, bbox_inches="tight")

    # current snapshot: where each segment is priced NOW vs its 20y median
    now = a[a.yr == a.yr.max()].set_index("sector")["pe"]
    hist = a.groupby("sector").pe.median()
    print("How each segment is priced NOW vs its own history (US):")
    for s in keep:
        if s in now.index:
            rich = (now[s] / hist[s] - 1) * 100
            print(f"  {s:26s} PE now {now[s]:5.1f}  vs 20y-median {hist[s]:5.1f}  ({rich:+.0f}%)")
    print(f"\nwrote reports/sector_valuation_history.{{csv,png}} ({a.yr.min()}-{a.yr.max()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
