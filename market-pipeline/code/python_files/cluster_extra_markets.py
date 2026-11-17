#!/usr/bin/env python3
"""
cluster_extra_markets.py — extend valuation clustering to JP/EU/CN (the data now exists),
so the playbook screener gets proper peer-relative value there instead of a crude within-
market PE z-score. Business-economics features are derived from the fundamentals collected
this session (JP_full, EU_union, CN_full) joined to all_ratios (pe/pb/roe). Appends rows to
reports/valuation_clusters.csv in the same schema as IN/US/KR.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
FUND = {"JP": "JP_full", "EU": "EU_union", "CN": "CN_full"}
NAMES = {"JP": "japan", "EU": "europe", "CN": "china"}


def features(mkt: str) -> pd.DataFrame:
    """per-ticker business-economics profile from the deep fundamentals + all_ratios."""
    r = pd.read_csv(REP / "all_ratios.csv")
    r["mk"] = r.market.astype(str).str.upper().replace({"INDIA": "IN", "US": "US", "KOREA": "KR",
                                                        "JAPAN": "JP", "EUROPE": "EU", "CHINA": "CN"})
    r = r[r.mk == mkt][["ticker", "pe", "pb", "roe"]].copy()
    try:
        f = pd.read_parquet(f"{FH}/{FUND[mkt]}.parquet")
        f["yr"] = pd.to_datetime(f.fy_end, errors="coerce").dt.year
        f = f.sort_values("yr").groupby("ticker").last().reset_index()          # latest FY
        prof = f[["ticker"]].copy()
        if {"revenue", "net_income"}.issubset(f.columns):
            prof["net_margin"] = pd.to_numeric(f.net_income, errors="coerce") / pd.to_numeric(f.revenue, errors="coerce")
        if {"revenue", "total_assets"}.issubset(f.columns):
            prof["asset_turnover"] = pd.to_numeric(f.revenue, errors="coerce") / pd.to_numeric(f.total_assets, errors="coerce")
        if "roe" in f.columns:
            prof["roe_f"] = pd.to_numeric(f.roe, errors="coerce")
        r = r.merge(prof, on="ticker", how="left")
    except Exception:
        pass
    if "roe" not in r.columns or r.roe.isna().all():
        r["roe"] = r.get("roe_f")
    r["name"] = r.ticker
    return r


def main() -> int:
    existing = pd.read_csv(REP / "valuation_clusters.csv")
    keep_cols = list(existing.columns)
    added = []
    for mkt in ["JP", "EU", "CN"]:
        d = features(mkt)
        d = d[(d.pe.between(1, 200)) & np.isfinite(d.roe)].copy()
        if len(d) < 30:
            print(f"{mkt}: only {len(d)} names — skipped"); continue
        feats = [c for c in ["roe", "net_margin", "asset_turnover"] if c in d.columns and d[c].notna().mean() > 0.5]
        if not feats:
            feats = ["roe"]
        X = d[feats].fillna(d[feats].median())
        X = StandardScaler().fit_transform(np.clip(X, X.quantile(0.02), X.quantile(0.98), axis=1) if hasattr(X, "quantile") else X)
        k = min(8, max(3, len(d) // 25))
        d["cluster"] = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
        for col, z in [("pe", "pe_z"), ("pb", "pb_z")]:
            g = d.groupby("cluster")[col]
            d[z] = (d[col] - g.transform("median")) / g.transform(lambda s: s.std(ddof=0) or 1)
        d["valuation_z"] = d[["pe_z", "pb_z"]].mean(axis=1)
        d["val_pct"] = d.groupby("cluster")["valuation_z"].rank(pct=True)
        d["roe_rank"] = d.groupby("cluster")["roe"].rank(pct=True)
        d["verdict"] = np.where(d.valuation_z > 1.5, "OVERPRICED",
                        np.where(d.valuation_z < -1.5, "UNDERPRICED", "fair"))
        d["market"] = NAMES[mkt]
        for c in keep_cols:
            if c not in d.columns:
                d[c] = np.nan
        added.append(d[keep_cols])
        print(f"{mkt}: {len(d)} stocks, {k} clusters on {feats}; "
              f"{(d.verdict=='UNDERPRICED').sum()} underpriced, {(d.verdict=='OVERPRICED').sum()} overpriced")
    if added:
        out = pd.concat([existing[~existing.market.isin(NAMES.values())]] + added, ignore_index=True)
        out.to_csv(REP / "valuation_clusters.csv", index=False)
        print(f"valuation_clusters.csv: now covers {out.market.nunique()} markets, {len(out)} stocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
