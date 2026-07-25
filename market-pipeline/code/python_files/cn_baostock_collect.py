#!/usr/bin/env python3
"""
cn_baostock_collect.py — deep + broad CN fundamentals via BAOSTOCK, the anti-throttle
route for China. Eastmoney's bulk snapshot is geo-blocked from non-China IPs; baostock.com
is a *different* provider that is NOT blocked, free, and needs no key. Gives per-year
epsTTM / roeAvg / netProfit with pubDate (the real filing date → point-in-time) for the
whole A-share universe. Maps baostock code (sh.600519) → warehouse ticker (600519.SS).

Anti-throttle design: single persistent baostock socket (no per-request HTTP handshake),
serial but fast (~0.1s/query, no rate limit), checkpoint every 50 tickers, resumable.

Output: CN_baostock.parquet (ticker, fy_end, eps, roe, net_income, filed).
"""
from __future__ import annotations
import sys, glob
from pathlib import Path
import pandas as pd, numpy as np, baostock as bs

WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/CN"
OUT = Path("/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/CN_baostock.parquet")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
YEARS = list(range(2015, 2025))


def bao_code(sym: str) -> str | None:
    base = sym.split(".")[0]
    if not base.isdigit():
        return None
    if sym.endswith(".SS") or sym.endswith(".SH"):
        return f"sh.{base}"
    if sym.endswith(".SZ"):
        return f"sz.{base}"
    return None


def liquid_cn(limit):
    df = pd.read_parquet(glob.glob(f"{WH}/year=2026.parquet")[0], columns=["Date", "Symbol", "Close", "Volume"])
    last = df[df.Date == df.Date.max()].copy(); last["turn"] = last.Close * last.Volume
    return last[last.turn >= last.turn.quantile(1/3)].nlargest(limit, "turn").Symbol.astype(str).tolist()


def main() -> int:
    bs.login()
    syms = liquid_cn(LIMIT)
    pairs = [(bao_code(s), s) for s in syms if bao_code(s)]
    done = set(pd.read_parquet(OUT).ticker) if OUT.exists() else set()
    rows = pd.read_parquet(OUT).to_dict("records") if OUT.exists() else []
    todo = [(c, s) for c, s in pairs if s not in done]
    print(f"CN baostock: {len(todo)} tickers × {len(YEARS)}y", flush=True)
    for i, (code, sym) in enumerate(todo, 1):
        for yr in YEARS:
            try:
                rs = bs.query_profit_data(code=code, year=yr, quarter=4)   # Q4 = full-year cumulative
                while rs.error_code == "0" and rs.next():
                    d = dict(zip(rs.fields, rs.get_row_data()))
                    if not d.get("statDate"):
                        continue
                    rows.append({"ticker": sym, "fy_end": d["statDate"],
                                 "eps": pd.to_numeric(d.get("epsTTM"), errors="coerce"),
                                 "roe": pd.to_numeric(d.get("roeAvg"), errors="coerce"),
                                 "net_income": pd.to_numeric(d.get("netProfit"), errors="coerce"),
                                 "filed": d.get("pubDate")})
            except Exception:
                pass
        if i % 50 == 0:
            pd.DataFrame(rows).drop_duplicates(["ticker", "fy_end"]).to_parquet(OUT, index=False)
            print(f"  {i}/{len(todo)}", flush=True)
    bs.logout()
    df = pd.DataFrame(rows).drop_duplicates(["ticker", "fy_end"])
    df.to_parquet(OUT, index=False)
    y = pd.to_datetime(df.fy_end, errors="coerce").dt.year
    print(f"CN_baostock: {len(df)} rows, {df.ticker.nunique()} tickers, "
          f"{int(y.min())}-{int(y.max())}, eps nn {df.eps.notna().mean():.0%}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
