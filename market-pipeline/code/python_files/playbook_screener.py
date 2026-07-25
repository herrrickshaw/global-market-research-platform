#!/usr/bin/env python3
"""
playbook_screener.py — turn the validated market playbook into LIVE filters that pick stocks,
then feed those picks into watchlist.csv for real performance monitoring.

Each market runs only its backtested edge (from market_playbook / edge_matrix):
  IN — trend (50>200 DMA) + cheap/quality, long-only, liquidity-gated, no mega-cap floor
  US — short-horizon cheap-vs-market (low PE)
  KR — value+quality long/short: long cheap∩hi-ROE, short expensive∩lo-ROE
  JP — value-reversion (cheap-vs-market low PE)
  EU — 12-month momentum
  CN — PASSIVE ONLY (value tested & fails) → no active picks

Signals from: reports/all_ratios.csv (pe/roe/mcap) + reports/valuation_clusters.csv
(valuation_z where available) + warehouse OHLCV (golden cross, 12M momentum, turnover).

Output: reports/playbook_picks.csv  +  appends to watchlist.csv (status='playbook', with
entry_date + entry_price) so the paper-track can score them going forward.
"""
from __future__ import annotations
import glob, datetime
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv"
NORM = {"india": "IN", "us": "US", "korea": "KR", "japan": "JP", "europe": "EU", "china": "CN"}
TODAY = datetime.date.today().isoformat()
TOPN = 12


def price_signals(mkt: str) -> pd.DataFrame:
    """per-ticker: last close, golden-cross (50>200 DMA), 12M momentum, avg turnover."""
    parts = sorted(glob.glob(f"{WH}/{mkt}/year=2025.parquet") + glob.glob(f"{WH}/{mkt}/year=2026.parquet"))
    if not parts:
        return pd.DataFrame()
    px = pd.concat((pd.read_parquet(p, columns=["Date", "Symbol", "Close", "Volume"]) for p in parts), ignore_index=True)
    px["Date"] = pd.to_datetime(px["Date"])
    w = px.pivot_table(index="Date", columns="Symbol", values="Close", aggfunc="last").sort_index()
    v = px.pivot_table(index="Date", columns="Symbol", values="Volume", aggfunc="last").sort_index()
    out = pd.DataFrame(index=w.columns)
    out["close"] = w.iloc[-1]
    out["dma50"] = w.tail(50).mean(); out["dma200"] = w.tail(200).mean()
    out["golden_cross"] = out.dma50 > out.dma200
    out["mom12m"] = w.iloc[-1] / w.iloc[-252] - 1 if len(w) >= 252 else np.nan
    out["turnover"] = (w * v).tail(20).mean()
    out["liquid"] = out.turnover >= out.turnover.quantile(1 / 3)
    out["mega"] = out.turnover >= out.turnover.quantile(0.9)          # mega-cap proxy (exclude for IN)
    out = out.reset_index()
    return out.rename(columns={out.columns[0]: "ticker"})


def fundamentals(mkt: str) -> pd.DataFrame:
    r = pd.read_csv(REP / "all_ratios.csv")
    r["mk"] = r.market.astype(str).str.lower().map(NORM).fillna(r.market.astype(str).str.upper())
    r = r[r.mk == mkt][["ticker", "pe", "roe", "mcap_local"]].copy()
    # value signal: valuation_z from clusters if present, else within-market PE z-score
    c = pd.read_csv(REP / "valuation_clusters.csv")
    c["mk"] = c.market.astype(str).str.lower().map(NORM).fillna(c.market.astype(str).str.upper())
    cc = c[c.mk == mkt]
    if len(cc) and "ticker" in cc.columns:
        r = r.merge(cc[["ticker", "valuation_z", "name"]], on="ticker", how="left")
    if "valuation_z" not in r.columns or r.valuation_z.isna().all():
        pe = r.pe.where((r.pe > 0) & (r.pe < 200))
        r["valuation_z"] = (pe - pe.mean()) / pe.std()               # low PE = negative z = cheap
    if "name" not in r.columns:
        r["name"] = r.ticker
    return r


def screen(mkt: str) -> pd.DataFrame:
    ps, fu = price_signals(mkt), fundamentals(mkt)
    if ps.empty or fu.empty:
        return pd.DataFrame()
    d = fu.merge(ps, on="ticker", how="inner")
    d = d[d.liquid]
    picks = []
    if mkt == "IN":                                  # trend + cheap/quality, long-only, no mega
        s = d[d.golden_cross & ~d.mega & ((d.valuation_z < -0.3) | (d.roe > 0.15))]
        s = s.sort_values("mom12m", ascending=False)
        picks = _emit(s, mkt, "trend+value/quality", "LONG")
    elif mkt == "US":                                # short-horizon cheap-vs-market
        s = d[d.valuation_z < -0.8].sort_values("valuation_z")
        picks = _emit(s, mkt, "cheap-vs-market", "LONG")
    elif mkt == "JP":                                # value-reversion
        s = d[d.valuation_z < -0.8].sort_values("valuation_z")
        picks = _emit(s, mkt, "value-reversion", "LONG")
    elif mkt == "KR":                                # value+quality long/short
        lo = d[(d.valuation_z < -0.8) & (d.roe > 0.10)].sort_values("valuation_z")
        sh = d[(d.valuation_z > 1.0) & (d.roe < 0.05)].sort_values("valuation_z", ascending=False)
        picks = _emit(lo, mkt, "cheap∩hi-ROE", "LONG") + _emit(sh, mkt, "expensive∩lo-ROE", "SHORT")
    elif mkt == "EU":                                # momentum
        s = d[d.mom12m.notna()].sort_values("mom12m", ascending=False)
        picks = _emit(s, mkt, "12M-momentum", "LONG")
    # CN: no active picks (passive only)
    return pd.DataFrame(picks)


def _emit(s, mkt, filt, direction) -> list:
    out = []
    for _, r in s.head(TOPN).iterrows():
        out.append({"market": mkt, "symbol": str(r.ticker), "name": str(r.get("name", r.ticker))[:30],
                    "filter": filt, "direction": direction, "pe": round(r.pe, 1) if pd.notna(r.pe) else None,
                    "roe": round(r.roe, 3) if pd.notna(r.roe) else None,
                    "valuation_z": round(r.valuation_z, 2) if pd.notna(r.valuation_z) else None,
                    "mom12m": round(r.mom12m, 3) if pd.notna(r.mom12m) else None,
                    "entry_price": round(float(r.close), 2), "entry_date": TODAY})
    return out


def main() -> int:
    allp = pd.concat([screen(m) for m in ["IN", "US", "KR", "JP", "EU"]], ignore_index=True)
    allp.to_csv(REP / "playbook_picks.csv", index=False)

    # ---- feed into the watchlist for performance monitoring ----
    wl = pd.read_csv(HERE / "watchlist.csv")
    have = set(zip(wl.symbol.astype(str), wl.market.astype(str)))
    new = [{"symbol": r.symbol, "market": r.market, "status": "playbook",
            "note": f"{r.filter} ({r.direction})", "entry_date": r.entry_date, "entry_price": r.entry_price}
           for r in allp.itertuples() if (r.symbol, r.market) not in have]
    if new:
        pd.concat([wl, pd.DataFrame(new)], ignore_index=True).to_csv(HERE / "watchlist.csv", index=False)

    print(f"playbook picks: {len(allp)} across markets ({allp.groupby('market').size().to_dict()})")
    print(f"watchlist: +{len(new)} new 'playbook' entries for monitoring (entry {TODAY})")
    print("CN: no active picks — value tested & fails; passive/index only.")
    for m in ["IN", "US", "KR", "JP", "EU"]:
        sub = allp[allp.market == m]
        if len(sub):
            names = ", ".join(f"{r.symbol}{'(S)' if r.direction=='SHORT' else ''}" for r in sub.head(6).itertuples())
            print(f"  {m} [{sub.iloc[0]['filter']}]: {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
