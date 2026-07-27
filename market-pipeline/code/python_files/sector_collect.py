#!/usr/bin/env python3
"""
sector_collect.py — GICS sector/industry for the WHOLE universe via yfinance .info, so the
fundamentals-vs-speculation analysis has a consistent cross-market sector taxonomy. Uses
curl_cffi (browser impersonation) to dodge Yahoo rate-limits; checkpointed + resumable.
Output: reports/sector_universe.parquet (market, ticker, yf_ticker, sector, industry).
"""
from __future__ import annotations
import sys, time, warnings
from pathlib import Path
import pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")
try:
    from curl_cffi import requests as cffi
    SESS = cffi.Session(impersonate="chrome")
except Exception:
    SESS = None

REP = Path(__file__).resolve().parent / "reports"
OUT = REP / "sector_universe.parquet"
NORM = {"india": "IN", "us": "US", "korea": "KR", "japan": "JP", "europe": "EU", "china": "CN"}


def yf_ticker(mk: str, tk: str) -> str:
    tk = str(tk)
    return tk + ".NS" if mk == "IN" and "." not in tk else tk   # India stored bare


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
    d = pd.read_csv(REP / "all_ratios.csv")
    d["mk"] = d.market.astype(str).str.lower().map(NORM).fillna(d.market.astype(str).str.upper())
    uni = d[["mk", "ticker"]].drop_duplicates().head(limit)
    done = set(pd.read_parquet(OUT).ticker) if OUT.exists() else set()
    rows = pd.read_parquet(OUT).to_dict("records") if OUT.exists() else []
    todo = [(r.mk, str(r.ticker)) for r in uni.itertuples() if str(r.ticker) not in done]
    print(f"sector collect: {len(todo)} tickers", flush=True)
    for i, (mk, tk) in enumerate(todo, 1):
        yt = yf_ticker(mk, tk)
        try:
            info = (yf.Ticker(yt, session=SESS) if SESS is not None else yf.Ticker(yt)).info
            rows.append({"market": mk, "ticker": tk, "yf_ticker": yt,
                         "sector": info.get("sector"), "industry": info.get("industry")})
        except Exception:
            rows.append({"market": mk, "ticker": tk, "yf_ticker": yt, "sector": None, "industry": None})
        if i % 200 == 0:
            pd.DataFrame(rows).drop_duplicates("ticker").to_parquet(OUT, index=False)
            got = pd.DataFrame(rows).sector.notna().mean()
            print(f"  {i}/{len(todo)}  ({got:.0%} have sector)", flush=True)
        time.sleep(0.25)
    df = pd.DataFrame(rows).drop_duplicates("ticker")
    df.to_parquet(OUT, index=False)
    print(f"sector_universe: {len(df)} tickers, {df.sector.notna().mean():.0%} have sector, "
          f"{df.sector.nunique()} sectors", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
