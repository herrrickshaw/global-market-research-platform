#!/usr/bin/env python3
"""Fetch US sharesOutstanding + bookValue (equity) for US fundamentals tickers that
have net_income but null shares — the pending data the DQ gate flags. Writes a
supplement parquet build_all_ratios can merge. Bounded to tickers that also have
warehouse prices (the ones that matter). yfinance, cached, resumable."""
import glob, time
from pathlib import Path
import pandas as pd, numpy as np, yfinance as yf
from obs import get_logger
LOG = get_logger("us_shares_fetch")
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/US"
OUT = Path(f"{FH}/US_shares_supplement.parquet")
us = pd.read_parquet(f"{FH}/US.parquet").sort_values("fy_end").groupby("ticker",as_index=False).last()
need = us[us.net_income.notna() & us.shares.isna()].ticker.astype(str)
have_px = set(pd.concat([pd.read_parquet(p,columns=["Symbol"]) for p in glob.glob(f"{WH}/year=2026.parquet")]).Symbol.astype(str))
tk = [t for t in need if t in have_px]
done = set(pd.read_parquet(OUT).ticker) if OUT.exists() else set()
tk = [t for t in tk if t not in done]
LOG.info(f"fetching shares+equity for {len(tk)} US tickers (pending)")
rows = list(pd.read_parquet(OUT).to_dict("records")) if OUT.exists() else []
for i,t in enumerate(tk,1):
    try:
        info = yf.Ticker(t).info
        rows.append({"ticker":t,"shares":info.get("sharesOutstanding"),
                     "equity":info.get("bookValue",np.nan)*(info.get("sharesOutstanding") or np.nan)})
    except Exception: pass
    if i%200==0:
        pd.DataFrame(rows).to_parquet(OUT,index=False); LOG.info(f"  {i}/{len(tk)}")
pd.DataFrame(rows).to_parquet(OUT,index=False)
LOG.info(f"wrote {OUT}: {len(rows)} tickers")
print(f"US shares supplement: {len(rows)} tickers")
