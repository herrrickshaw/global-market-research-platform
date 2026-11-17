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
    # full-universe GICS sectors: yfinance crawl (95%, all markets) ∪ Damodaran 48k map
    sec = {}
    su = REP / "sector_universe.parquet"
    if su.exists():
        s = pd.read_parquet(su)
        for _, r in s[s.sector.notna()].iterrows():
            sec[(str(r.market), str(r.ticker))] = r.sector
    dm = REP / "damodaran_sector_map.parquet"
    if dm.exists():
        for _, r in pd.read_parquet(dm)[["wh_ticker", "Primary Sector"]].dropna().iterrows():
            sec.setdefault((None, str(r.wh_ticker)), r["Primary Sector"])
    d["sector"] = [sec.get((m, str(t))) or sec.get((None, str(t))) for m, t in zip(d.mk, d.ticker)]
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

    # global sector view — WITHIN-MARKET standardised (you cannot pool raw PB/ROE across
    # markets: a US PB isn't comparable to a China PB, so cross-market level noise washes out
    # the relationship). z-score pb & roe inside each market, then pool per sector.
    dz = d.copy()
    for col in ("pb", "roe"):
        dz[col + "_z"] = dz.groupby("mk")[col].transform(lambda s: (s - s.mean()) / (s.std(ddof=0) or 1))
    glob = (dz.groupby("sector").apply(lambda g: pd.Series(
        {"n": len(g), "R2_pb_roe": r2(g.roe_z.values, g.pb_z.values),
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
    L += ["", "## Full-universe findings (all 6 markets, 95% sector coverage)", "",
          "- **The regime is MARKET×SECTOR-specific, not a universal sector property.** Pooling "
          "PB~ROE across markets washes the signal out (US Tech prices on ROE at R² 0.41, but "
          "'Tech' across all 6 markets ≈ 0) — because Chinese, Japanese and US tech each price "
          "differently. Read the *by market × sector* table, never the pooled global.",
          "- **Surprise: China's SOE core is the MOST fundamentally-priced** — CN Utilities "
          "(R² 0.90), Communication/telecom (0.84), Energy (0.81) track ROE tightly. The state "
          "prices these like regulated bonds (stable ROE → stable PB). This **refines** (not "
          "contradicts) the China value-reversion null: China's *cross-sectional cheapness* doesn't "
          "reward because the liquid, retail-driven **growth periphery** is speculative — even "
          "though the SOE **core** is anchored. China is bimodal.",
          "- EU/KR/JP carry the most speculation cells; developed-market sector valuations float "
          "further from current ROE (growth/future-priced).", "",
          "> **Company-level inference:** in a 🟢 fundamentals-ruled market×sector, a stock's "
          "residual from the PB~ROE line is genuine over/under-valuation (a real signal). In a 🔴 "
          "speculation-ruled one, valuation is sentiment and value-reversion is weakest. NB: this "
          "level-tracking metric (does PB track ROE?) is *related to but distinct from* "
          "value-reversion (does cheapness correct?) — a homogeneous SOE group can track tightly "
          "yet re-rate together without cross-sectional reversion.", "",
          "**Caveats:** single-period cross-section; survivorship-biased; small-n sectors (esp. the "
          "high-R² China SOE cells, n15–27); PB~ROE is linear for a convex relation; book-heavy "
          "financials/REITs/utilities flatter the fit. Research, not advice."]
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
