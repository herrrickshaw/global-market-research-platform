#!/usr/bin/env python3
"""
fundamentals_vs_speculation_ts.py — the TIME dimension: does a sector drift between being
priced on fundamentals and being priced on speculation?

For each fiscal year × sector we recompute the R² of PB ~ ROE across that sector's names
(residual-income link). A sector-by-year heatmap then shows *when* a sector decouples from
fundamentals (R² collapses → speculation/bubble) and when it re-anchors (R² rises).

PB = year-end price / (equity/shares); ROE = net_income/equity. Sectors from
sector_universe.parquet (yfinance GICS, whole universe) with sector_map.json as fallback.
Default market US (deepest history). Output: reports/spec_timeseries_<mkt>.{csv,png}
"""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv"
MKT = sys.argv[1] if len(sys.argv) > 1 else "US"
FUND = {"US": "US", "KR": "KR_deep", "IN": "IN_screener_only_backup"}.get(MKT, MKT)
MIN_N = 15


def sectors() -> dict:
    m = {}
    su = REP / "sector_universe.parquet"
    if su.exists():
        s = pd.read_parquet(su)
        for _, r in s[s.market == MKT].iterrows():
            if r.sector:
                m[str(r.ticker)] = r.sector
    sm = Path("/Users/umashankar/market-pipeline/market_cache/sector_map.json")
    if sm.exists():
        for k, v in json.loads(sm.read_text()).items():
            if k.startswith(f"{MKT}:"):
                m.setdefault(k.split(":", 1)[1], v)
    return m


def year_end_price() -> pd.DataFrame:
    parts = sorted(glob.glob(f"{WH}/{MKT}/year=*.parquet"))
    px = pd.concat((pd.read_parquet(p, columns=["Date", "Symbol", "Close"]) for p in parts), ignore_index=True)
    px["Date"] = pd.to_datetime(px["Date"]); px["yr"] = px.Date.dt.year
    ye = px.sort_values("Date").groupby(["Symbol", "yr"], as_index=False).last()
    return ye.rename(columns={"Symbol": "ticker", "Close": "price"})[["ticker", "yr", "price"]]


def r2(x, y) -> float:
    if len(x) < MIN_N or np.std(x) == 0:
        return np.nan
    b = np.polyfit(x, y, 1); yh = np.polyval(b, x)
    ss = ((y - yh) ** 2).sum(); tot = ((y - y.mean()) ** 2).sum()
    return 1 - ss / tot if tot else np.nan


def main() -> int:
    f = pd.read_parquet(f"{FH}/{FUND}.parquet")
    f["yr"] = pd.to_datetime(f.fy_end, errors="coerce").dt.year
    for c in ("net_income", "equity", "shares"):
        if c not in f.columns:
            print(f"{MKT}: missing {c} — cannot build PB/ROE time-series for this market"); return 1
    f = f[(f.equity > 0) & (f.shares > 0) & f.net_income.notna()].copy()
    f["roe"] = f.net_income / f.equity
    f["bps"] = f.equity / f.shares
    px = year_end_price()
    d = f.merge(px, on=["ticker", "yr"], how="inner")
    d["pb"] = d.price / d.bps
    d = d[(d.pb > 0) & (d.pb < 50) & (d.roe.abs() < 2)]
    sec = sectors(); d["sector"] = d.ticker.astype(str).map(sec)
    d = d[d.sector.notna()]
    if not len(d):
        print(f"{MKT}: no sector-labelled rows yet (sector collection still running)."); return 1

    rows = []
    for (yr, s), g in d.groupby(["yr", "sector"]):
        v = r2(g.roe.values, g.pb.values)
        if v == v:
            rows.append({"year": int(yr), "sector": s, "n": len(g), "R2": round(v, 2)})
    ts = pd.DataFrame(rows)
    ts.to_csv(REP / f"spec_timeseries_{MKT.lower()}.csv", index=False)
    if not len(ts):
        print(f"{MKT}: not enough names/sector/year yet."); return 1

    # heatmap sector × year
    piv = ts.pivot_table(index="sector", columns="year", values="R2")
    piv = piv.loc[piv.notna().sum(axis=1).sort_values(ascending=False).index]     # densest sectors on top
    yrs = [y for y in piv.columns if y >= 2005]
    piv = piv[yrs]
    fig, ax = plt.subplots(figsize=(min(20, 2 + len(yrs) * 0.45), 1 + len(piv) * 0.5))
    im = ax.imshow(piv.values, cmap="RdYlGn", vmin=0, vmax=0.6, aspect="auto")
    ax.set_xticks(range(len(piv.columns))); ax.set_xticklabels(piv.columns, rotation=90, fontsize=8)
    ax.set_yticks(range(len(piv.index))); ax.set_yticklabels(piv.index, fontsize=9)
    for i in range(len(piv.index)):
        for j in range(len(piv.columns)):
            v = piv.values[i, j]
            if v == v:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5)
    fig.colorbar(im, ax=ax, label="R²(PB~ROE): green=fundamentals, red=speculation", shrink=.6)
    ax.set_title(f"{MKT}: does each sector price on fundamentals or speculation, over time?\n"
                 "green year = valuation tracks ROE · red year = decoupled (bubble/speculation)", fontsize=11)
    plt.tight_layout(); plt.savefig(REP / f"spec_timeseries_{MKT.lower()}.png", dpi=140, bbox_inches="tight")
    print(f"wrote reports/spec_timeseries_{MKT.lower()}.{{csv,png}} — {len(ts)} sector-years, "
          f"{ts.sector.nunique()} sectors, {ts.year.min()}-{ts.year.max()}")
    # flag the most speculative sector-years
    print("\nMost SPECULATIVE sector-years (R²<0.05, n>=20):")
    for _, r in ts[(ts.R2 < 0.05) & (ts.n >= 20)].sort_values("year").iterrows():
        print(f"  {r.year} {r.sector} (R²{r.R2}, n{r.n})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
