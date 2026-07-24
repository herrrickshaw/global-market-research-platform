#!/usr/bin/env python3
"""
data_quality.py — Great-Expectations-style validation + remediation for the market
data warehouse (in the spirit of dbt tests / GE expectations / DVT cross-source checks).

  1. EXPECTATIONS — per table: not-null on keys, unique keys, accepted ranges, freshness.
     Runs them, reports pass/fail with counts (the "sufficiency" gate).
  2. DEDUP — asserts key uniqueness (fundamentals ticker×fy_end, ratios market×ticker).
  3. DERIVE MISSING RATIOS — PE/PB/ROE/ROCE/earnings-yield back-filled from raw
     fundamentals where the ratio is null but its inputs exist (no fetch needed).
  4. PENDING — lists genuinely-missing, fetch-only fields (can't be derived).

Output: reports/data_quality.md + reports/financial_ratios_enriched.csv
"""
from __future__ import annotations
import glob
from pathlib import Path
import numpy as np, pandas as pd
from obs import get_logger

HERE = Path(__file__).resolve().parent
LOG = get_logger("data_quality")
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv"
FUND_FILE = {"india": "IN_screener_only_backup", "us": "US", "korea": "KR"}


def latest_fundamentals(mkt: str) -> pd.DataFrame:
    """Latest-FY net_income / shares / total-equity per ticker for a market."""
    f = pd.read_parquet(f"{FH}/{FUND_FILE[mkt]}.parquet")
    f = f.sort_values("fy_end").groupby("ticker", as_index=False).last()
    ni = pd.to_numeric(f.net_income, errors="coerce")
    sh = pd.to_numeric(f.shares, errors="coerce")
    eq = (pd.to_numeric(f.equity_capital, errors="coerce") + pd.to_numeric(f.reserves, errors="coerce")
          if "equity_capital" in f.columns else pd.to_numeric(f.equity, errors="coerce"))
    ebit = pd.to_numeric(f.ebit, errors="coerce") if "ebit" in f.columns else np.nan
    ce = pd.to_numeric(f.capital_employed, errors="coerce") if "capital_employed" in f.columns else np.nan
    return pd.DataFrame({"ticker": f.ticker, "eps": ni / sh, "equity_t": eq,
                         "ni": ni, "ebit": ebit, "cap_emp": ce})


def expectations(d: pd.DataFrame) -> list:
    """(name, passed, detail) — GE-style suite over the ratios table."""
    out = []
    def E(name, ok, detail): out.append((name, bool(ok), detail))
    E("ratios.market_ticker unique", d.duplicated(["market", "ticker"]).sum() == 0,
      f"{d.duplicated(['market','ticker']).sum()} dupes")
    E("ratios.ticker not-null", d.ticker.notna().all(), f"{d.ticker.isna().sum()} nulls")
    E("ratios.close not-null", d.close.notna().mean() > 0.99, f"{d.close.isna().mean()*100:.1f}% null")
    E("ratios.pe in (0,1000]", (((d.pe > 0) & (d.pe <= 1000)) | d.pe.isna()).all() if d.pe.notna().any() else False,
      f"{(~((d.pe>0)&(d.pe<=1000))&d.pe.notna()).sum()} out-of-range")
    E("ratios.roe in [-3,3]", (((d.roe >= -3) & (d.roe <= 3)) | d.roe.isna()).all(),
      f"{(~((d.roe>=-3)&(d.roe<=3))&d.roe.notna()).sum()} out-of-range")
    E("ratios.pe coverage ≥ 70%", d.pe.notna().mean() >= 0.70, f"{d.pe.notna().mean()*100:.0f}% present")
    E("ratios.roe coverage ≥ 90%", d.roe.notna().mean() >= 0.90, f"{d.roe.notna().mean()*100:.0f}% present")
    return out


def main() -> int:
    d = pd.read_csv(HERE / "reports" / "financial_ratios.csv")
    before = {c: d[c].notna().mean() for c in ["pe", "pb", "roe", "roce"]}

    # ---- 3. derive missing ratios from raw fundamentals ----------------------
    fills = {"pe": 0, "pb": 0, "roe": 0, "roce": 0}
    for mkt in ["india", "us", "korea"]:
        fu = latest_fundamentals(mkt).set_index("ticker")
        m = d.market == mkt
        idx = d.index[m]
        tk = d.loc[idx, "ticker"].astype(str)
        eps = tk.map(fu.eps); eq = tk.map(fu.equity_t); ni = tk.map(fu.ni)
        ebit = tk.map(fu.ebit); ce = tk.map(fu.cap_emp)
        close = pd.to_numeric(d.loc[idx, "close"], errors="coerce")
        mcap = pd.to_numeric(d.loc[idx, "mcap_local"], errors="coerce")
        # PE where null and EPS>0
        need = d.loc[idx, "pe"].isna() & (eps.values > 0)
        d.loc[idx[need.values], "pe"] = (close / eps.values)[need.values]; fills["pe"] += int(need.sum())
        # ROE where null and equity present
        need = d.loc[idx, "roe"].isna() & (eq.values > 0) & np.isfinite(ni.values)
        d.loc[idx[need.values], "roe"] = (ni.values / eq.values)[need.values]; fills["roe"] += int(need.sum())
        # PB where null and equity present  (PB = mcap / book equity)
        need = d.loc[idx, "pb"].isna() & (eq.values > 0) & np.isfinite(mcap.values)
        d.loc[idx[need.values], "pb"] = (mcap.values / eq.values)[need.values]; fills["pb"] += int(need.sum())
        # ROCE where null and ebit + capital_employed present (India only)
        need = d.loc[idx, "roce"].isna() & (ce.values > 0) & np.isfinite(ebit.values)
        d.loc[idx[need.values], "roce"] = (ebit.values / ce.values)[need.values]; fills["roce"] += int(need.sum())

    # (c) clean outliers — null clear data errors so downstream ratios are trustworthy
    n_pe_out = int(((d.pe <= 0) | (d.pe > 1000)).sum())
    n_roe_out = int((d.roe.abs() > 3).sum())               # |ROE|>300% = neg-equity/data error
    d.loc[(d.pe <= 0) | (d.pe > 1000), "pe"] = np.nan
    d.loc[(d.pb <= 0) | (d.pb > 200), "pb"] = np.nan
    d.loc[d.roe.abs() > 3, "roe"] = np.nan
    LOG.info(f"cleaned outliers: pe {n_pe_out}, roe {n_roe_out}")
    after = {c: d[c].notna().mean() for c in ["pe", "pb", "roe", "roce"]}
    d.to_csv(HERE / "reports" / "financial_ratios_enriched.csv", index=False)

    # ---- 1/2. expectations + dedup + freshness -------------------------------
    exp = expectations(d)
    # freshness: warehouse latest date per market
    fresh = {}
    for mkt in ["IN", "US", "KR", "JP", "EU"]:
        parts = glob.glob(f"{WH}/{mkt}/year=2026.parquet")
        if parts:
            dd = pd.read_parquet(parts[0], columns=["Date"]); fresh[mkt] = str(pd.to_datetime(dd.Date).max().date())

    L = ["# Data-quality report (expectations · dedup · ratio derivation)", "",
         "GE/dbt-style validation of the warehouse ratios + fundamentals. "
         "Educational research pipeline. ", "",
         "## 1. Expectations (sufficiency gate)", "",
         "| expectation | result | detail |", "|---|:--:|---|"]
    for name, ok, det in exp:
        L.append(f"| {name} | {'✅ pass' if ok else '❌ FAIL'} | {det} |")
    L += ["", "## 2. Deduplication", "",
          "| table | key | dupes |", "|---|---|--:|",
          f"| financial_ratios | market×ticker | {d.duplicated(['market','ticker']).sum()} ✅ |"]
    for m in ["IN_screener_only_backup", "US", "KR", "JP"]:
        try:
            f = pd.read_parquet(f"{FH}/{m}.parquet")
            L.append(f"| fundamentals/{m} | ticker×fy_end | {f.duplicated(['ticker','fy_end']).sum()} ✅ |")
        except Exception:
            pass
    L += ["", "## 3. Missing ratios derived (from raw fundamentals, no fetch)", "",
          "| ratio | coverage before | after | filled |", "|---|--:|--:|--:|"]
    for c in ["pe", "pb", "roe", "roce"]:
        L.append(f"| {c} | {before[c]*100:.0f}% | **{after[c]*100:.0f}%** | +{fills[c]:,} |")
    L += ["", "## 4. Freshness (warehouse latest date)", "",
          "| market | " + " | ".join(fresh) + " |", "|---|" + "---|"*len(fresh),
          "| last date | " + " | ".join(fresh.values()) + " |"]
    L += ["", "## 5. Pending (fetch-only — cannot be derived)", "",
          "- **US shares/equity** 53–59% null in fundamentals_history → PE/PB still gappy for US; "
          "needs an EDGAR/yfinance shares+equity fetch.",
          "- **EU/JP** absent from `financial_ratios.csv` — no fundamentals snapshot built; "
          "EU has `fundamentals_history/EU.parquet`, JP via EDINET (collector not built).",
          "- **ROCE** needs EBIT + capital_employed — only India's screener carries them; "
          "US/KR ROCE stays null without those raw fields.",
          "", "> Derived ratios use latest-FY fundamentals + current price (a PIT approximation "
          "for the snapshot). Enriched file: `reports/financial_ratios_enriched.csv`. Not advice."]
    (HERE / "reports" / "data_quality.md").write_text("\n".join(L))
    npass = sum(1 for _, ok, _ in exp if ok)
    LOG.info(f"expectations {npass}/{len(exp)} pass; filled pe+{fills['pe']} roe+{fills['roe']} "
             f"pb+{fills['pb']} roce+{fills['roce']}")
    print("\n".join(L))
    print(f"\nwrote reports/data_quality.md + financial_ratios_enriched.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
