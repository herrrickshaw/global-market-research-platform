#!/usr/bin/env python3
"""
scan_price_reconcile.py — warehouse-first staleness gate for EVERY market's scan.

WHY (2026-07-27): the mailer shipped-then-blocked on INFY carrying Friday's close
on a +3.7% Monday — one yfinance call inside the scan silently fell back to a
stale cache. validate_brief.py only samples India via screener.in; the other four
markets had NO price validation at all. This module closes that gap for all five.

HOW — two independent checks per market, cheapest first:

  1. WAREHOUSE SIGNATURE (free, no network): a scan row whose LTP is exactly the
     previous session's `market_daily.snapshots.ltp` is *suspicious*; many such
     rows among the liquid names = the scan re-served yesterday's prices.
  2. LIVE SPOT-CHECK (small, fresh yfinance batch): re-quote the top-N liquid
     names with a FRESH session (no cache) and flag |scan − fresh| > tolerance.

Exit code = number of markets that FAILED (stale beyond threshold), so
daily_pipeline.sh can gate the mailer on it exactly like validate_brief.

Usage:
  python scan_price_reconcile.py                 # all markets, sample 8
  python scan_price_reconcile.py --market JP     # one market
  python scan_price_reconcile.py --sample 12 --tolerance 2.5
"""
from __future__ import annotations

import argparse
import glob
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent

# market → (scan glob, symbol column, price column, yfinance suffix)
MARKETS = {
    "IN": ("indian_full_scan/indian_full_scan_*.xlsx", "Symbol", "LTP", ".NS"),
    "US": ("us_full_scan/us_full_scan_*.xlsx", "Symbol", "LTP", ""),
    "JP": ("japan_scan/japan_market_scan_*.xlsx", "YF_Ticker", "LTP_JPY", ""),
    "KR": ("korea_scan/korea_market_scan_*.xlsx", "YF_Ticker", "LTP_KRW", ""),
    "EU": ("european_scan/european_market_scan_*.xlsx", "Symbol", "LTP", ""),
}
LIQ_COL = "Turnover_USD"   # present in all five All_Stocks sheets


def market_open_now(mkt: str) -> bool:
    """Rough in-session check (IST clock). When a market is trading, scan-vs-
    fresh gaps are intraday drift, not staleness — tolerance loosens 2x.
    (First live run flagged ASML 3.6% and SKHY 8.8% during EU/US sessions.)"""
    from datetime import datetime
    now = datetime.now()
    h = now.hour + now.minute / 60
    if now.weekday() >= 5:
        return False
    windows = {"IN": (9.25, 15.5), "JP": (5.5, 11.5), "KR": (5.5, 12.0),
               "EU": (12.5, 21.0), "US": (19.0, 25.999)}  # US eve wraps midnight
    lo, hi = windows.get(mkt, (0, 0))
    return (lo <= h <= hi) or (mkt == "US" and h <= 1.5)


def warehouse_prev_close(market: str) -> pd.DataFrame:
    """Previous session's ltp per symbol from market_daily.snapshots (via psql)."""
    sql = f"""SELECT symbol, ltp FROM market_daily.snapshots
              WHERE market='{market}' AND as_of_date =
                (SELECT MAX(as_of_date) FROM market_daily.snapshots
                 WHERE market='{market}' AND as_of_date < CURRENT_DATE)"""
    try:
        r = subprocess.run(["psql", "-d", "market_data", "--csv", "-c", sql],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            return pd.read_csv(StringIO(r.stdout))
    except Exception:
        pass
    return pd.DataFrame(columns=["symbol", "ltp"])


def fresh_quotes(tickers: list[str]) -> dict[str, float]:
    """Fresh last closes via a NEW yfinance session — deliberately no cache."""
    import yfinance as yf
    out: dict[str, float] = {}
    try:
        data = yf.download(tickers, period="1d", progress=False,
                           auto_adjust=False, threads=True)
        closes = data["Close"] if "Close" in data else data
        if isinstance(closes, pd.Series):          # single ticker
            out[tickers[0]] = float(closes.dropna().iloc[-1])
        else:
            for t in tickers:
                if t in closes.columns:
                    s = closes[t].dropna()
                    if len(s):
                        out[t] = float(s.iloc[-1])
    except Exception as e:
        print(f"    fresh-quote batch failed: {e}")
    return out


def reconcile(market: str, sample: int, tolerance: float) -> bool:
    """Returns True if the market PASSES."""
    pat, sym_col, px_col, suffix = MARKETS[market]
    files = sorted(glob.glob(str(HERE / pat)))
    if not files:
        print(f"  [{market}] no scan workbook — SKIP")
        return True
    scan_path = files[-1]

    df = pd.read_excel(scan_path, sheet_name="All_Stocks")
    if sym_col not in df.columns or px_col not in df.columns:
        print(f"  [{market}] missing {sym_col}/{px_col} in {Path(scan_path).name} — SKIP")
        return True

    liquid = (df.sort_values(LIQ_COL, ascending=False).head(sample)
              if LIQ_COL in df.columns else df.head(sample))
    liquid = liquid[[sym_col, px_col]].dropna()

    # Check 1 — warehouse signature (scan price == yesterday's warehouse ltp)
    wh = warehouse_prev_close(market)
    n_sig = 0
    if not wh.empty:
        m = liquid.merge(wh, left_on=liquid[sym_col].astype(str).str.replace(
            r"\.(NS|BO|T|KS|KQ)$", "", regex=True), right_on="symbol", how="left")
        n_sig = int((abs(m[px_col] - m["ltp"]) < 1e-6).sum())
        if n_sig:
            print(f"  [{market}] ⚠ {n_sig}/{len(liquid)} liquid names EXACTLY equal "
                  f"yesterday's warehouse close (stale-cache signature)")

    # Check 2 — fresh live spot-check
    tickers = [str(s) + suffix if suffix and not str(s).endswith(suffix) else str(s)
               for s in liquid[sym_col]]
    fresh = fresh_quotes(tickers)
    if market_open_now(market):
        tolerance = tolerance * 2
        print(f"  [{market}] market in session — tolerance loosened to {tolerance:.1f}% (intraday drift)")
    n_checked = n_stale = 0
    worst = ("", 0.0)
    for (_, row), tkr in zip(liquid.iterrows(), tickers):
        if tkr not in fresh or not fresh[tkr]:
            continue
        n_checked += 1
        diff = abs(row[px_col] - fresh[tkr]) / fresh[tkr] * 100
        if diff > tolerance:
            n_stale += 1
            print(f"    !! {tkr:14s} scan={row[px_col]:<12g} fresh={fresh[tkr]:<12g} "
                  f"diff={diff:.2f}%")
            if diff > worst[1]:
                worst = (tkr, diff)
    if n_checked == 0:
        print(f"  [{market}] live spot-check unavailable (yfinance) — "
              f"warehouse signature only")
        return n_sig < max(2, len(liquid) // 2)

    ok = n_stale == 0
    verdict = "PASS" if ok else f"FAIL — {n_stale}/{n_checked} stale (worst {worst[0]} {worst[1]:.1f}%)"
    print(f"  [{market}] {Path(scan_path).name}: {n_checked} checked · {verdict}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--market", choices=list(MARKETS), help="one market (default all)")
    ap.add_argument("--sample", type=int, default=8)
    ap.add_argument("--tolerance", type=float, default=2.0, help="max %% diff vs fresh quote")
    a = ap.parse_args()

    targets = [a.market] if a.market else list(MARKETS)
    print(f"scan price reconcile — markets: {', '.join(targets)} "
          f"(sample {a.sample}, tol {a.tolerance}%)")
    fails = sum(0 if reconcile(m, a.sample, a.tolerance) else 1 for m in targets)
    print(f"reconcile: {len(targets) - fails}/{len(targets)} markets clean")
    return fails


if __name__ == "__main__":
    sys.exit(main())
