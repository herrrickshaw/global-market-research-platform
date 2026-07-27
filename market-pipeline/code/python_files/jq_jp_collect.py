#!/usr/bin/env python3
"""
jq_jp_collect.py — Japan fundamentals via J-Quants V2 (`x-api-key`, /fins/summary).
NOTE ON DEPTH: the free/standard plan returns only ~2 recent years — SHALLOWER than the
5y yfinance JP history already on disk. So this does NOT fix JP's statistical underpower
(that needs ~8y → the paid Premium 20y plan, which is out of scope). What it DOES buy is
QUALITY for the recent window: authoritative IFRS filings, a real disclosure date
(`DiscDate` → correct point-in-time lag), clean shares (`ShOutFY`) and direct EPS.

Merges (does not overwrite) into JP.parquet: J-Quants rows are authoritative for the
years they cover; yfinance fills the older tail. Liquid universe, resumable, rate-limited.
Run: python jq_jp_collect.py [LIMIT]
"""
from __future__ import annotations
import sys, glob, time
from pathlib import Path
import pandas as pd, numpy as np, requests
from obs import get_logger

LOG = get_logger("jq_jp")
BASE = "https://api.jquants.com/v2"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/JP"
OUT = Path("/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/JP_jquants.parquet")
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 1500


def api_key() -> str:
    for l in open("/Users/umashankar/.config/market-secrets/credentials.env"):
        if l.startswith("JQUANTS_API_KEY="):
            return l.split("=", 1)[1].strip().strip('"')
    raise SystemExit("no JQUANTS_API_KEY")


def liquid_jp(limit: int) -> list:
    """(jquants_code, warehouse_symbol) for the liquid JP universe (top turnover)."""
    df = pd.read_parquet(f"{WH}/year=2026.parquet", columns=["Date", "Symbol", "Close", "Volume"])
    last = df[df.Date == df.Date.max()].copy()
    last["turn"] = last.Close * last.Volume
    liq = last[last.turn >= last.turn.quantile(0.5)].nlargest(limit, "turn")
    out = []
    for sym in liq.Symbol.astype(str):          # warehouse "7203.T"
        base = sym.split(".")[0]
        if base.isdigit() and len(base) == 4:
            out.append((base + "0", sym))        # J-Quants "72030"
    return out


def to_num(x):
    try:
        return float(x)
    except Exception:
        return np.nan


def main() -> int:
    h = {"x-api-key": api_key()}
    codes = liquid_jp(LIMIT)
    done = set(pd.read_parquet(OUT).ticker) if OUT.exists() else set()
    rows = pd.read_parquet(OUT).to_dict("records") if OUT.exists() else []
    todo = [(c, s) for c, s in codes if s not in done]
    LOG.info(f"JP J-Quants: {len(todo)} tickers (quality upgrade, ~2y depth)")
    t0 = time.time()
    for i, (code, sym) in enumerate(todo, 1):
        try:
            r = requests.get(f"{BASE}/fins/summary?code={code}", headers=h, timeout=30)
            if r.status_code == 429:              # rate limited — back off
                LOG.warning("429 rate-limit; sleeping 60s"); time.sleep(60)
                r = requests.get(f"{BASE}/fins/summary?code={code}", headers=h, timeout=30)
            if r.status_code != 200:
                continue
            for x in r.json().get("data", []):
                if "FYFinancial" not in x.get("DocType", ""):
                    continue                       # annual only
                rows.append({
                    "ticker": sym, "fy_end": x.get("CurFYEn"),
                    "net_income": to_num(x.get("NP")), "revenue": to_num(x.get("Sales")),
                    "gross_profit": np.nan, "total_assets": to_num(x.get("TA")),
                    "current_assets": np.nan, "current_liabilities": np.nan,
                    "long_term_debt": np.nan, "shares": to_num(x.get("ShOutFY")),
                    "equity": to_num(x.get("Eq")), "cfo": to_num(x.get("CFO")),
                    "eps": to_num(x.get("EPS")), "filed": x.get("DiscDate")})
        except Exception:
            pass
        if i % 100 == 0:
            pd.DataFrame(rows).drop_duplicates(["ticker", "fy_end"]).to_parquet(OUT, index=False)
            LOG.info(f"  {i}/{len(todo)}  ({i/(time.time()-t0)*60:.0f} req/min)")
        time.sleep(0.2)
    df = pd.DataFrame(rows).drop_duplicates(["ticker", "fy_end"])
    df.to_parquet(OUT, index=False)
    LOG.info(f"wrote {OUT}: {len(df)} rows, {df.ticker.nunique()} tickers")
    print(f"JP J-Quants: {len(df)} rows, {df.ticker.nunique()} tickers -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
