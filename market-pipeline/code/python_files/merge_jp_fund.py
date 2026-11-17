#!/usr/bin/env python3
"""Merge JP fundamentals: J-Quants (authoritative, clean filed/shares) preferred over
yfinance on (ticker, fy_end) collisions; union the rest. -> JP_merged.parquet."""
import pandas as pd
FH="/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
yf=pd.read_parquet(f"{FH}/JP.parquet"); jq=pd.read_parquet(f"{FH}/JP_jquants.parquet")
cols=[c for c in yf.columns if c in jq.columns]          # shared cols BEFORE tagging
a=jq[cols].copy(); a["_pri"]=1                            # prefer jq
b=yf[cols].copy(); b["_pri"]=0
both=pd.concat([a,b], ignore_index=True)
both=both.sort_values("_pri",ascending=False).drop_duplicates(["ticker","fy_end"]).drop(columns=["_pri"])
both.to_parquet(f"{FH}/JP_merged.parquet",index=False)
y=pd.to_datetime(both.fy_end,errors="coerce").dt.year
print(f"JP_merged: {len(both)} rows, {both.ticker.nunique()} tickers, {int(y.min())}-{int(y.max())}")
print(f"  filed non-null: {both.filed.notna().mean():.0%} (was {yf.filed.notna().mean():.0%} yf-only)")
