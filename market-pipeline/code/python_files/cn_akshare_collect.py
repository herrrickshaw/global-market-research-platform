#!/usr/bin/env python3
"""Deep CN fundamentals via akshare (fixes CN's 27% coverage + underpowered 5y window).
Pulls annual EPS + ROE per A-share from stock_financial_analysis_indicator, back to
2015, for the liquid CN warehouse universe. Cached/resumable. Bounded by LIMIT."""
import sys, glob, time
from pathlib import Path
import pandas as pd, numpy as np, akshare as ak
from obs import get_logger
LOG = get_logger("cn_akshare")
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/CN"
OUT = Path("/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/CN_deep.parquet")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 600
# liquid CN universe (top turnover), bare 6-digit codes
df = pd.concat([pd.read_parquet(p, columns=["Date","Symbol","Close","Volume"]) for p in glob.glob(f"{WH}/year=2026.parquet")])
last = df[df.Date == df.Date.max()].copy(); last["turn"] = last.Close*last.Volume
liq = last[last.turn >= last.turn.quantile(0.5)].nlargest(LIMIT, "turn").Symbol.astype(str)
codes = [(s.split(".")[0], s) for s in liq if s.split(".")[0].isdigit()]
done = set(pd.read_parquet(OUT).ticker) if OUT.exists() else set()
rows = list(pd.read_parquet(OUT).to_dict("records")) if OUT.exists() else []
todo = [(c, sym) for c, sym in codes if sym not in done]
LOG.info(f"CN deep: {len(todo)} stocks via akshare")
for i, (code, sym) in enumerate(todo, 1):
    try:
        d = ak.stock_financial_analysis_indicator(symbol=code, start_year="2015")
        dc = [c for c in d.columns if "每股收益" in c and "摊薄" in c] or [c for c in d.columns if "每股收益" in c]
        rc = [c for c in d.columns if "净资产收益率" in c and "加权" in c] or [c for c in d.columns if "净资产收益率" in c]
        datecol = [c for c in d.columns if c in ("日期","报告期")][0]
        d["yr"] = pd.to_datetime(d[datecol], errors="coerce").dt.year
        ann = d[pd.to_datetime(d[datecol], errors="coerce").dt.month == 12]
        for _, r in ann.iterrows():
            rows.append({"ticker": sym, "fy_end": f"{int(r.yr)}-12-31",
                         "eps": pd.to_numeric(r[dc[0]], errors="coerce") if dc else np.nan,
                         "roe": pd.to_numeric(r[rc[0]], errors="coerce")/100 if rc else np.nan})
    except Exception:
        pass
    if i % 25 == 0:
        pd.DataFrame(rows).to_parquet(OUT, index=False); LOG.info(f"  {i}/{len(todo)}")
    time.sleep(0.3)
pd.DataFrame(rows).to_parquet(OUT, index=False)
LOG.info(f"wrote {OUT}: {len(rows)} statement-years, {pd.DataFrame(rows).ticker.nunique() if rows else 0} tickers")
print(f"CN deep: {len(rows)} rows")
