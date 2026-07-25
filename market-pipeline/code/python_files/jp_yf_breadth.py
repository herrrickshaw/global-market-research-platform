#!/usr/bin/env python3
"""
jp_yf_breadth.py — raise Japan fundamentals COVERAGE (breadth) via yfinance across the
full liquid .T universe. EDINET-Bench gave depth (13y) but only 1,437 names; yfinance
gives ~5y for essentially every listed name, which fills the coverage gap. Resumable.
Output: JP_yf_breadth.parquet (ticker, fy_end, revenue, net_income, total_assets, equity).
"""
from __future__ import annotations
import sys, glob, time, warnings
from pathlib import Path
import pandas as pd, numpy as np, yfinance as yf
warnings.filterwarnings("ignore")

WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/JP"
OUT = Path("/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/JP_yf_breadth.parquet")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 3200


def pick(df, *names):
    if df is None or df.empty:
        return {}
    for n in names:
        hit = [i for i in df.index if n.lower() in str(i).lower()]
        if hit:
            return {str(c)[:10]: pd.to_numeric(df.loc[hit[0], c], errors="coerce") for c in df.columns}
    return {}


def liquid_jp(limit):
    df = pd.read_parquet(glob.glob(f"{WH}/year=2026.parquet")[0], columns=["Date", "Symbol", "Close", "Volume"])
    last = df[df.Date == df.Date.max()].copy(); last["turn"] = last.Close * last.Volume
    return last[last.turn >= last.turn.quantile(1/3)].nlargest(limit, "turn").Symbol.astype(str).tolist()


def main() -> int:
    tickers = liquid_jp(LIMIT)
    done = set(pd.read_parquet(OUT).ticker) if OUT.exists() else set()
    rows = pd.read_parquet(OUT).to_dict("records") if OUT.exists() else []
    todo = [t for t in tickers if t not in done]
    print(f"JP yfinance breadth: {len(todo)} tickers", flush=True)
    for i, tk in enumerate(todo, 1):
        try:
            t = yf.Ticker(tk)
            inc, bs = t.financials, t.balance_sheet
            rev = pick(inc, "Total Revenue", "Operating Revenue")
            ni = pick(inc, "Net Income Continuous", "Net Income")
            ta = pick(bs, "Total Assets")
            eq = pick(bs, "Stockholders Equity", "Total Equity Gross Minority", "Common Stock Equity")
            for fy in set(rev) | set(ni) | set(ta) | set(eq):
                rows.append({"ticker": tk, "fy_end": fy, "revenue": rev.get(fy),
                             "net_income": ni.get(fy), "total_assets": ta.get(fy), "equity": eq.get(fy)})
        except Exception:
            pass
        if i % 100 == 0:
            pd.DataFrame(rows).drop_duplicates(["ticker", "fy_end"]).to_parquet(OUT, index=False)
            print(f"  {i}/{len(todo)}", flush=True)
        time.sleep(0.3)
    df = pd.DataFrame(rows).drop_duplicates(["ticker", "fy_end"])
    df.to_parquet(OUT, index=False)
    print(f"JP_yf_breadth: {len(df)} rows, {df.ticker.nunique()} tickers", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
