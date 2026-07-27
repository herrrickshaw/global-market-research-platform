#!/usr/bin/env python3
"""
damodaran_speculation.py — use Aswath Damodaran's industry datasets as an authoritative,
global cross-check on "where speculation rules vs fundamentals rule".

His per-industry data carries a cleaner speculation signal than any single ratio: the
**% of money-losing firms** together with the **trailing PE** and **PEG**. An industry
where most firms lose money yet trade at a high multiple is, by definition, priced on hope
(future growth / sentiment), not current performance. Where ROE justifies a modest PE and
few firms lose money, price tracks fundamentals.

Also emits a whole-universe sector map from `damodaran_companies` (48k global names) — an
instant, authoritative alternative to scraping yfinance per-ticker.

Output: reports/damodaran_speculation.{csv,md,png} + reports/damodaran_sector_map.parquet
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
RS = HERE / "reference_seed"


def main() -> int:
    pe = pd.read_parquet(RS / "damodaran_pe.parquet")
    roe = pd.read_parquet(RS / "damodaran_roe.parquet")[["Industry", "ROE (unadjusted)"]]
    m = pe.merge(roe, on="Industry")
    m["pct_losing"] = m["% of Money Losing firms (Trailing)"]
    m["roe"] = m["ROE (unadjusted)"]
    m["pe"] = pd.to_numeric(m["Trailing PE"], errors="coerce")
    m["peg"] = pd.to_numeric(m["PEG Ratio"], errors="coerce")
    m["nfirms"] = m["Number of firms"]
    d = m[(m.nfirms >= 30) & m.pe.notna() & m.pct_losing.notna()].copy()

    # speculation score: money-losing (½) + rich multiple (³⁄₁₀) + weak ROE (⅕)
    d["spec_score"] = (d.pct_losing.rank(pct=True) * 0.5
                       + d.pe.clip(upper=200).rank(pct=True) * 0.3
                       + (1 - d.roe.rank(pct=True)) * 0.2)
    d = d.sort_values("spec_score", ascending=False)
    d[["Industry", "nfirms", "pct_losing", "pe", "roe", "peg", "spec_score"]] \
        .to_csv(REP / "damodaran_speculation.csv", index=False)

    def fmt(x):
        x = x.copy()
        x["% losing"] = (x.pct_losing * 100).round(0); x["ROE%"] = (x.roe * 100).round(1)
        x["PE"] = x.pe.round(0); x["PEG"] = x.peg.round(1)
        return x[["Industry", "nfirms", "% losing", "PE", "ROE%", "PEG"]]

    L = ["# Damodaran cross-check — where speculation rules vs fundamentals (global industries)", "",
         "Authoritative global industry data (Aswath Damodaran, NYU Stern). The **% of money-"
         "losing firms** × **PE** × **PEG** is the sharpest speculation signal: a sector where "
         "most firms lose money yet trade at a high multiple is priced on hope, not performance.", "",
         "## 🔴 Speculation rules (money-losing yet richly priced)", "",
         fmt(d.head(12)).to_markdown(index=False), "",
         "## 🟢 Fundamentals rule (ROE justifies a modest PE, few money-losers)", "",
         fmt(d[d.pct_losing < 0.35].nsmallest(10, "spec_score")).to_markdown(index=False), "",
         "## What this confirms", "",
         "- Our PB~ROE R² test flagged **Healthcare and Technology as speculation-ruled** — "
         "Damodaran shows exactly why: **Biotech is 90% money-losing at PE 64 (ROE −2%)**, "
         "**Software 70% money-losing**, **Healthcare-IT at PE 507**. The multiple prices a "
         "pipeline/growth story, not earnings.",
         "- Our **fundamental** sectors (financials/utilities-like) match his low-speculation set: "
         "**Insurance ROE 15% at PE 18**, Banks, Power, Homebuilding — ROE justifies the price.",
         "- **The value-reversion edge should be harvested in the 🟢 rows and avoided in the 🔴 "
         "rows** — cheapness only mean-reverts where price tracks fundamentals. Same mechanism as "
         "China (a speculation-ruled market) being the one place value-reversion failed.", "",
         "> Damodaran data is a global snapshot (mostly US-weighted); % money-losing is trailing. "
         "Research, not investment advice."]
    (REP / "damodaran_speculation.md").write_text("\n".join(L))

    # ---- speculation map (scatter) ----
    fig, ax = plt.subplots(figsize=(11, 7))
    sc = ax.scatter(d.pct_losing * 100, d.pe.clip(upper=150), c=d.roe * 100, s=d.nfirms.clip(upper=400),
                    cmap="RdYlGn", vmin=-10, vmax=25, alpha=.8, edgecolor="k", linewidth=.4)
    for _, r in pd.concat([d.head(8), d[d.pct_losing < 0.3].nsmallest(6, "spec_score")]).iterrows():
        ax.annotate(r.Industry[:26], (r.pct_losing * 100, min(r.pe, 150)), fontsize=7,
                    xytext=(3, 3), textcoords="offset points")
    ax.axvspan(55, 100, alpha=.05, color="red"); ax.axhspan(40, 160, alpha=.05, color="red")
    ax.set_xlabel("% of firms losing money (trailing)"); ax.set_ylabel("Trailing PE (capped 150)")
    fig.colorbar(sc, label="industry ROE %", shrink=.7)
    ax.set_title("Damodaran speculation map — top-right = priced on hope, not earnings\n"
                 "(bubble size = # firms · colour = ROE)", fontsize=11)
    plt.tight_layout(); plt.savefig(REP / "damodaran_speculation.png", dpi=150, bbox_inches="tight")

    # ---- whole-universe sector map from Damodaran's 48k companies ----
    try:
        c = pd.read_parquet(RS / "damodaran_companies.parquet")
        EXSUF = {"NSE": ".NS", "BSE": ".BO", "TSE": ".T", "KRX": ".KS", "KOSDAQ": ".KQ",
                 "SHSE": ".SS", "SZSE": ".SZ", "LSE": ".L", "XETRA": ".DE"}
        c["wh_ticker"] = c.apply(lambda r: str(r.Ticker) + EXSUF.get(str(r.Exchange), ""), axis=1)
        c[["Company Name", "Country", "Primary Sector", "Industry Group", "Exchange", "Ticker", "wh_ticker"]] \
            .to_parquet(REP / "damodaran_sector_map.parquet", index=False)
        print(f"damodaran_sector_map: {len(c)} companies, {c['Primary Sector'].nunique()} sectors, "
              f"{c.Country.nunique()} countries")
    except Exception as e:
        print("company map skipped:", e)

    print("\n".join(L[:26]))
    print("\nwrote reports/damodaran_speculation.{csv,md,png} + damodaran_sector_map.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
