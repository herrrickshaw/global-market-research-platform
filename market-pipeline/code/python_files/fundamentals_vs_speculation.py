#!/usr/bin/env python3
"""
fundamentals_vs_speculation.py — which sectors are priced on FUNDAMENTALS and which on
SPECULATION?

Theory (residual-income / Gordon model): a firm's price-to-book should rise with its
return-on-equity — PB ≈ (ROE − g)/(r − g). So *within a peer group*, if PB is well explained
by ROE, the market is pricing on fundamentals; if PB is disconnected from ROE, price is
driven by sentiment/speculation. We measure that link with the **R² of PB ~ ROE** per sector:

  high R²  → FUNDAMENTALS RULE (good performance ⇒ higher valuation, rationally)
  low  R²  → SPECULATION RULES (valuation detached from performance)

The regression RESIDUAL per company = how over/under-valued it is versus what its own
performance justifies (only meaningful in a fundamentals-ruled sector).

Sources: reports/all_ratios.csv (pe/pb/roe) + market_cache/sector_map.json (GICS-like sector).
Output: reports/fundamentals_vs_speculation.{csv,md,png}
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
NORM = {"india": "IN", "us": "US", "korea": "KR", "japan": "JP", "europe": "EU", "china": "CN"}
MIN_N = 12                                    # min names per (market, sector) to regress


def load() -> pd.DataFrame:
    d = pd.read_csv(REP / "all_ratios.csv")
    d["mk"] = d.market.astype(str).str.lower().map(NORM).fillna(d.market.astype(str).str.upper())
    smap = json.loads((HERE.parent.parent / "market_cache" / "sector_map.json").read_text()) \
        if (HERE.parent.parent / "market_cache" / "sector_map.json").exists() \
        else json.loads(Path("/Users/umashankar/market-pipeline/market_cache/sector_map.json").read_text())
    # sector_map keys look like "EU:BBOX.L" / "US:AAPL"
    sec = {}
    for k, v in smap.items():
        if ":" in k:
            mk, tk = k.split(":", 1); sec[(mk.upper(), tk)] = v
    d["sector"] = [sec.get((m, str(t))) for m, t in zip(d.mk, d.ticker)]
    d = d[d.sector.notna() & (d.pb > 0) & np.isfinite(d.roe) & (d.roe.abs() < 3)].copy()
    return d


def r2(x, y) -> float:
    if len(x) < MIN_N or x.std() == 0:
        return np.nan
    b = np.polyfit(x, y, 1)
    yhat = np.polyval(b, x)
    ss_res = ((y - yhat) ** 2).sum(); ss_tot = ((y - y.mean()) ** 2).sum()
    return 1 - ss_res / ss_tot if ss_tot else np.nan


def main() -> int:
    d = load()
    rows = []
    for (mk, sec), g in d.groupby(["mk", "sector"]):
        if len(g) < MIN_N:
            continue
        rows.append({"market": mk, "sector": sec, "n": len(g),
                     "R2_pb_roe": round(r2(g.roe.values, g.pb.values), 2),
                     "spearman": round(g[["roe", "pb"]].corr("spearman").iloc[0, 1], 2),
                     "median_pe": round(g.pe.median(), 1), "median_roe": round(g.roe.median() * 100, 1)})
    res = pd.DataFrame(rows).dropna(subset=["R2_pb_roe"])
    res["regime"] = np.where(res.R2_pb_roe >= 0.30, "🟢 FUNDAMENTALS",
                     np.where(res.R2_pb_roe >= 0.10, "🟡 mixed", "🔴 SPECULATION"))
    res = res.sort_values("R2_pb_roe", ascending=False)

    # global sector view (pool markets; how fundamentally-priced is each sector overall)
    glob = (d.groupby("sector").apply(lambda g: pd.Series(
        {"n": len(g), "R2_pb_roe": r2(g.roe.values, g.pb.values),
         "median_pe": g.pe.median(), "median_roe": g.roe.median() * 100}), include_groups=False)
        .dropna(subset=["R2_pb_roe"]).sort_values("R2_pb_roe", ascending=False).reset_index())
    glob = glob[glob.n >= MIN_N]

    res.to_csv(REP / "fundamentals_vs_speculation.csv", index=False)

    # ---- markdown ----
    L = ["# Fundamentals vs speculation — which sectors price on performance?", "",
         "R² of **PB ~ ROE** within each sector: high = the market pays up for real "
         "performance (fundamentals rule); low = valuation detached from performance "
         "(speculation rules). Residual-income theory: PB should rise with ROE.", "",
         "## Global sector ranking (all markets pooled)", "",
         "| sector | n | R²(PB~ROE) | med PE | med ROE% | regime |", "|---|--:|--:|--:|--:|---|"]
    for _, r in glob.iterrows():
        reg = "🟢 FUNDAMENTALS" if r.R2_pb_roe >= 0.30 else "🟡 mixed" if r.R2_pb_roe >= 0.10 else "🔴 SPECULATION"
        L.append(f"| {r.sector} | {int(r.n)} | {r.R2_pb_roe:.2f} | {r.median_pe:.1f} | {r.median_roe:.1f} | {reg} |")
    L += ["", "## By market × sector", "",
          "| market | sector | n | R²(PB~ROE) | Spearman | med PE | med ROE% | regime |",
          "|---|---|--:|--:|--:|--:|--:|---|"]
    for _, r in res.iterrows():
        L.append(f"| {r.market} | {r.sector} | {r.n} | {r.R2_pb_roe:.2f} | {r.spearman:.2f} | "
                 f"{r.median_pe} | {r.median_roe} | {r.regime} |")
    L += ["", "> **Company-level inference:** in a 🟢 fundamentals-ruled sector, a stock's "
          "residual from the PB~ROE line is genuine over/under-valuation vs what its performance "
          "justifies (a real signal). In a 🔴 speculation-ruled sector, valuation says little "
          "about performance — cheapness/richness there is sentiment, and the value-reversion "
          "edge is weakest.", "",
          "**Caveats:** single-period cross-section (not time-series); survivorship-biased; "
          "sector labels cover ~830 names; PB~ROE is a linear proxy for a convex relation; "
          "financials/REITs have book-heavy PB that flatters the fit. Research, not advice."]
    (REP / "fundamentals_vs_speculation.md").write_text("\n".join(L))

    # ---- viz: global sector R² bar ----
    fig, ax = plt.subplots(figsize=(10, max(4, len(glob) * 0.35)))
    colors = ["#1a9850" if v >= 0.30 else "#fee08b" if v >= 0.10 else "#d73027" for v in glob.R2_pb_roe]
    ax.barh(glob.sector, glob.R2_pb_roe, color=colors)
    ax.axvline(0.30, ls="--", c="green", lw=1, alpha=.6); ax.axvline(0.10, ls="--", c="red", lw=1, alpha=.6)
    ax.set_xlabel("R²  of  PB ~ ROE   (fundamental linkage)"); ax.invert_yaxis()
    ax.set_title("Fundamentals vs speculation by sector\n"
                 "green = performance drives valuation · red = speculation drives valuation", fontsize=11)
    plt.tight_layout(); plt.savefig(REP / "fundamentals_vs_speculation.png", dpi=150, bbox_inches="tight")
    print("\n".join(L[:40]))
    print(f"\nwrote reports/fundamentals_vs_speculation.{{csv,md,png}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
