#!/usr/bin/env python3
"""Union all CN_deep_shard_*.parquet + the existing CN_deep base -> CN_deep.parquet
(dedup on ticker+fy_end). Idempotent; safe to run repeatedly during collection."""
import glob
from pathlib import Path
import pandas as pd
FHDIR = Path("/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history")
OUT = FHDIR / "CN_deep.parquet"
parts = []
if OUT.exists():
    parts.append(pd.read_parquet(OUT))                       # preserve existing base
for p in glob.glob(str(FHDIR / "CN_deep_shard_*.parquet")):
    try:
        parts.append(pd.read_parquet(p))
    except Exception:
        pass
if parts:
    d = pd.concat(parts, ignore_index=True).drop_duplicates(["ticker", "fy_end"], keep="last")
    d.to_parquet(OUT, index=False)
    print(f"CN_deep merged: {len(d)} rows, {d.ticker.nunique()} tickers")
