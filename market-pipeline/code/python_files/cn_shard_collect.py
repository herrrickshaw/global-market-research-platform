#!/usr/bin/env python3
"""
cn_shard_collect.py NUM_SHARDS SHARD_ID [LIMIT] — one parallel worker of the CN
fundamentals collection. Processes the liquid-CN tickers whose index %% NUM_SHARDS ==
SHARD_ID, writing its own CN_deep_shard_{SHARD_ID}.parquet (no cross-worker write race).
Run N of these concurrently, then merge_cn_shards.py unions them into CN_deep.parquet.
Resumable per shard; per-ticker try/except so one bad code never kills the worker.
"""
import sys, glob, time
from pathlib import Path
import pandas as pd, numpy as np, akshare as ak

NSH = int(sys.argv[1]); SID = int(sys.argv[2])
LIMIT = int(sys.argv[3]) if len(sys.argv) > 3 else 600
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/CN"
FHDIR = Path("/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history")
OUT = FHDIR / f"CN_deep_shard_{SID}.parquet"

df = pd.read_parquet(glob.glob(f"{WH}/year=2026.parquet")[0], columns=["Date", "Symbol", "Close", "Volume"])
last = df[df.Date == df.Date.max()].copy(); last["turn"] = last.Close * last.Volume
liq = last[last.turn >= last.turn.quantile(0.5)].nlargest(LIMIT, "turn").Symbol.astype(str)
codes = [(s.split(".")[0], s) for s in liq if s.split(".")[0].isdigit()]
mine = [(c, s) for i, (c, s) in enumerate(codes) if i % NSH == SID]           # this worker's slice

done = set(pd.read_parquet(OUT).ticker) if OUT.exists() else set()
rows = pd.read_parquet(OUT).to_dict("records") if OUT.exists() else []
todo = [(c, s) for c, s in mine if s not in done]
print(f"[shard {SID}/{NSH}] {len(todo)} tickers", flush=True)
for i, (code, sym) in enumerate(todo, 1):
    try:
        d = ak.stock_financial_analysis_indicator(symbol=code, start_year="2015")
        dc = [c for c in d.columns if "每股收益" in c and "摊薄" in c] or [c for c in d.columns if "每股收益" in c]
        rc = [c for c in d.columns if "净资产收益率" in c and "加权" in c] or [c for c in d.columns if "净资产收益率" in c]
        datecol = [c for c in d.columns if c in ("日期", "报告期")][0]
        ann = d[pd.to_datetime(d[datecol], errors="coerce").dt.month == 12]
        for _, r in ann.iterrows():
            yr = pd.to_datetime(r[datecol], errors="coerce").year
            rows.append({"ticker": sym, "fy_end": f"{int(yr)}-12-31",
                         "eps": pd.to_numeric(r[dc[0]], errors="coerce") if dc else np.nan,
                         "roe": pd.to_numeric(r[rc[0]], errors="coerce") / 100 if rc else np.nan})
    except Exception:
        pass
    if i % 20 == 0:
        pd.DataFrame(rows).to_parquet(OUT, index=False)
        print(f"[shard {SID}] {i}/{len(todo)}", flush=True)
    time.sleep(0.25)
pd.DataFrame(rows).to_parquet(OUT, index=False)
print(f"[shard {SID}] done: {len(rows)} rows, {pd.DataFrame(rows).ticker.nunique() if rows else 0} tickers", flush=True)
