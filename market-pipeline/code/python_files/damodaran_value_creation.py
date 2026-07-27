#!/usr/bin/env python3
"""
damodaran_value_creation.py — two Damodaran-powered analyses:

1. VALUE CREATION (ROIC − WACC by industry). The proper economic-value test (better than
   ROE−cost-of-equity): a sector creates value only if its return on capital exceeds its
   cost of capital. Uses the R&D-adjusted ROIC so research-heavy sectors are judged fairly.

2. COUNTRY-ERP REFRAME of the China null. Is China "cheap / value-reversion-failing" because
   it is RISKY (high country risk premium) or because it is SPECULATIVE (inefficient pricing)?
   Damodaran's country equity-risk-premium data separates the two.

Inputs: data/reference_data/dam_roc.xls, dam_wacc.xls, dam_ctryprem.xlsx.
Output: reports/damodaran_value_creation.{csv,md,png} + reports/country_erp.csv
"""
from __future__ import annotations
from pathlib import Path
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
RD = Path("/Users/umashankar/market-pipeline/data/reference_data")


def _sheet(f):
    raw = pd.read_excel(f, sheet_name="Industry Averages", header=None, nrows=24)
    hdr = next(i for i in range(24) if any(str(x).strip().lower() == "industry name"
                                           for x in raw.iloc[i].values))
    return pd.read_excel(f, sheet_name="Industry Averages", header=hdr)


def main() -> int:
    # ---- 1. ROIC - WACC ----
    roc = _sheet(RD / "dam_roc.xls")
    wac = _sheet(RD / "dam_wacc.xls")
    icol = [c for c in roc.columns if "Industry" in str(c)][0]
    roic_c = [c for c in roc.columns if "R&D adjusted after-tax ROIC" in str(c)] or \
             [c for c in roc.columns if "Unadjusted after-tax ROIC" in str(c)]
    wcol = [c for c in wac.columns if "Cost of Capital" in str(c)] or \
           [c for c in wac.columns if "WACC" in str(c)]
    wic = [c for c in wac.columns if "Industry" in str(c)][0]
    r = roc[[icol, roic_c[0]]].rename(columns={icol: "Industry", roic_c[0]: "ROIC"})
    w = wac[[wic, wcol[0]]].rename(columns={wic: "Industry", wcol[0]: "WACC"})
    m = r.merge(w, on="Industry")
    for c in ("ROIC", "WACC"):
        m[c] = pd.to_numeric(m[c], errors="coerce")
    m["value_spread"] = m.ROIC - m.WACC
    m = m.dropna(subset=["value_spread"]).sort_values("value_spread", ascending=False)
    m.to_csv(REP / "damodaran_value_creation.csv", index=False)

    # ---- 2. country ERP ----
    ct = pd.read_excel(RD / "dam_ctryprem.xlsx", sheet_name="ERPs by country", header=7)
    cc = ct.columns[0]
    ct = ct.rename(columns={cc: "Country", ct.columns[2]: "rating",
                            ct.columns[3]: "default_spread", ct.columns[4]: "total_ERP",
                            ct.columns[5]: "country_risk_premium"})
    mk = ct[ct.Country.astype(str).isin(["China", "India", "United States", "Japan",
                                         "South Korea", "Korea", "Germany", "United Kingdom"])]
    mk = mk[["Country", "rating", "total_ERP", "country_risk_premium"]].copy()
    for c in ("total_ERP", "country_risk_premium"):
        mk[c] = pd.to_numeric(mk[c], errors="coerce")
    mk.to_csv(REP / "country_erp.csv", index=False)

    def pct(x):
        x = x.copy(); x.ROIC = (x.ROIC * 100).round(1); x.WACC = (x.WACC * 100).round(1)
        x.value_spread = (x.value_spread * 100).round(1); return x[["Industry", "ROIC", "WACC", "value_spread"]]

    L = ["# Damodaran value-creation (ROIC−WACC) + the China country-risk reframe", "",
         "## 1. Which industries create economic value? (ROIC − WACC, R&D-adjusted)", "",
         "A sector creates value only when return on capital beats its cost of capital. Using the "
         "**R&D-adjusted ROIC** so research-heavy sectors are judged fairly.", "",
         "**Value CREATORS (ROIC ≫ WACC):**", "", pct(m.head(10)).to_markdown(index=False), "",
         "**Value DESTROYERS (ROIC < WACC):**", "", pct(m.tail(10)).to_markdown(index=False), "",
         "## 2. Country-ERP reframe — is China cheap from RISK or from SPECULATION?", "",
         "| country | Moody's | total equity risk premium | country risk premium |",
         "|---|---|--:|--:|"]
    for _, r in mk.sort_values("total_ERP").iterrows():
        L.append(f"| {r.Country} | {r.rating} | {r.total_ERP*100:.2f}% | {r.country_risk_premium*100:.2f}% |")
    ch = mk[mk.Country == "China"]; ind = mk[mk.Country == "India"]
    L += ["", "### The reframe", "",
          f"- **China is A-rated with a country risk premium of only "
          f"{ch.country_risk_premium.iloc[0]*100:.2f}%** (total ERP {ch.total_ERP.iloc[0]*100:.2f}%) — "
          f"barely above the US. **India's is higher** (CRP {ind.country_risk_premium.iloc[0]*100:.2f}%, "
          f"ERP {ind.total_ERP.iloc[0]*100:.2f}%).",
          "- So China's cheap multiples and **failed value-reversion are NOT risk-justified** — a "
          "low-risk-premium market isn't 'cheap because dangerous.' That **strengthens the "
          "speculation/inefficiency reading**: China's mispricings persist because the retail-"
          "driven marginal trader doesn't arbitrage them, not because value there is riskier.",
          "- Corollary: **India carries a genuinely higher risk premium yet value-reversion "
          "WORKS there** — so India's value edge is a real, risk-priced anomaly being corrected, "
          "not a risk illusion. The country-ERP control makes the IN-vs-CN contrast sharper.", "",
          "> Damodaran Jan-2026 data. ROIC/WACC are US-industry aggregates; country ERP is "
          "rating-based. Research, not investment advice."]
    (REP / "damodaran_value_creation.md").write_text("\n".join(L))

    # viz: value creators/destroyers
    top = pd.concat([m.head(10), m.tail(10)])
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ["#1a9850" if v > 0 else "#d73027" for v in top.value_spread]
    ax.barh(top.Industry, top.value_spread * 100, color=colors)
    ax.axvline(0, c="k", lw=.8); ax.invert_yaxis()
    ax.set_xlabel("ROIC − WACC  (%)   ·   >0 creates economic value, <0 destroys it")
    ax.set_title("Value creation by industry (Damodaran ROIC vs cost of capital, R&D-adjusted)\n"
                 "consumer staples/tobacco compound value · biotech/real-estate-dev destroy it", fontsize=11)
    plt.tight_layout(); plt.savefig(REP / "damodaran_value_creation.png", dpi=150, bbox_inches="tight")

    # persist datasets to reference_seed as parquet
    rs = HERE / "reference_seed"
    m.to_parquet(rs / "damodaran_roic_wacc.parquet", index=False)
    mk.to_parquet(rs / "damodaran_country_erp.parquet", index=False)   # clean subset only
    print("\n".join(L))
    print("\nwrote reports/damodaran_value_creation.{csv,md,png} + country_erp.csv + reference_seed parquets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
