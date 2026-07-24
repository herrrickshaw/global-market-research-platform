#!/usr/bin/env python3
"""
build_all_ratios.py — derive valuation ratios for EVERY market that already has
fundamentals + warehouse prices on disk (no fetch): IN, US, KR, JP, EU, CN.

Uses already-collected data (LFS-backed global-stock-screener fundamentals_history +
global-market-data warehouse). Derives EPS, PE, ROE, PB, earnings-yield per ticker
from latest-FY fundamentals × latest adjusted price; deduplicates; unions.

Extends the ratio universe beyond the old IN/US/KR (financial_ratios.csv) to add
JP + EU + CN, so valuation clustering / reversion can cover all 5-6 markets.

Output: reports/all_ratios.csv + coverage summary (stdout / data_quality integration).
"""
from __future__ import annotations
import glob
from pathlib import Path
import numpy as np, pandas as pd
from obs import get_logger

HERE = Path(__file__).resolve().parent
LOG = get_logger("build_all_ratios")
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv"
# market: (fundamentals file, warehouse dir, local currency)
MK = {"IN": ("IN", "IN", "INR"), "US": ("US", "US", "USD"), "KR": ("KR_deep", "KR", "KRW"),
      "JP": ("JP", "JP", "JPY"), "EU": ("EU", "EU", "EUR"), "CN": ("CN", "CN", "CNY")}


def latest_price(mkt: str) -> pd.Series:
    parts = sorted(glob.glob(f"{WH}/{mkt}/year=2025.parquet") + glob.glob(f"{WH}/{mkt}/year=2026.parquet"))
    px = pd.concat((pd.read_parquet(p, columns=["Date", "Symbol", "Close"]) for p in parts),
                   ignore_index=True)
    px = px.sort_values("Date").groupby("Symbol").Close.last()
    return px


def norm(s: pd.Index) -> pd.Index:
    """strip exchange suffix for cross-source ticker matching (7203.T -> 7203)."""
    return s.astype(str).str.upper().str.split(".").str[0]


def latest_fund(mkt: str) -> pd.DataFrame:
    fund, _, _ = MK[mkt]
    f = pd.read_parquet(f"{FH}/{fund}.parquet")
    f = f.sort_values("fy_end").groupby("ticker", as_index=False).last()
    ni = pd.to_numeric(f.net_income, errors="coerce"); sh = pd.to_numeric(f.shares, errors="coerce")
    eq = (pd.to_numeric(f.get("equity_capital"), errors="coerce") + pd.to_numeric(f.get("reserves"), errors="coerce")
          if "equity_capital" in f.columns else pd.to_numeric(f.get("equity"), errors="coerce"))
    # merge the fetched US shares/equity supplement (us_shares_fetch.py) where null
    sup_path = Path(f"{FH}/{fund}_shares_supplement.parquet")
    if sup_path.exists():
        sup = pd.read_parquet(sup_path).drop_duplicates("ticker").set_index("ticker")
        tkey = f.ticker.astype(str)
        sh = sh.where(sh.notna(), tkey.map(sup["shares"]).values)
        if "equity" in sup.columns:
            eq = eq.where(eq.notna(), tkey.map(sup["equity"]).values)
    return pd.DataFrame({"ticker": f.ticker.astype(str), "ni": ni, "shares": sh, "equity": eq,
                         "fy_end": f.fy_end})


def main() -> int:
    frames, cov = [], []
    for mkt in MK:
        try:
            fu = latest_fund(mkt); px = latest_price(mkt)
        except Exception as e:
            LOG.error(f"{mkt}: {e}"); continue
        # join: exact ticker first, then suffix-normalised
        pxn = pd.Series(px.values, index=norm(px.index)); pxn = pxn[~pxn.index.duplicated()]
        fu["close"] = fu.ticker.map(px)
        miss = fu.close.isna()
        fu.loc[miss, "close"] = norm(pd.Index(fu.loc[miss, "ticker"])).map(pxn).values
        fu = fu.dropna(subset=["close"])
        fu["eps"] = fu.ni / fu.shares
        fu["pe"] = (fu.close / fu.eps).where(fu.eps > 0)
        fu["roe"] = (fu.ni / fu.equity).where(fu.equity > 0)
        fu["mcap_local"] = fu.close * fu.shares
        fu["pb"] = (fu.mcap_local / fu.equity).where(fu.equity > 0)
        fu["earnings_yield"] = 1.0 / fu.pe
        fu["market"] = mkt
        fu = fu.drop_duplicates("ticker")
        frames.append(fu[["market", "ticker", "fy_end", "close", "eps", "pe", "pb", "roe",
                          "mcap_local", "earnings_yield"]])
        cov.append({"market": mkt, "n": len(fu), "pe%": round(fu.pe.notna().mean()*100),
                    "roe%": round(fu.roe.notna().mean()*100), "pb%": round(fu.pb.notna().mean()*100)})
    allr = pd.concat(frames, ignore_index=True)
    # sanity clip
    allr.loc[(allr.pe <= 0) | (allr.pe > 1000), "pe"] = np.nan
    allr.loc[(allr.pb <= 0) | (allr.pb > 200), "pb"] = np.nan
    allr.loc[allr.roe.abs() > 3, "roe"] = np.nan            # |ROE|>300% = data error
    allr = allr.drop_duplicates(["market", "ticker"])
    allr.to_csv(HERE / "reports" / "all_ratios.csv", index=False)
    c = pd.DataFrame(cov)
    print("=== ratios derived across all warehouse markets (already-collected data) ===")
    print(c.to_string(index=False))
    print(f"\ntotal {len(allr)} rows, {allr.market.nunique()} markets "
          f"(added JP/EU/CN beyond the old IN/US/KR)")
    LOG.info(f"all_ratios: {len(allr)} rows across {allr.market.nunique()} markets")
    print("wrote reports/all_ratios.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
