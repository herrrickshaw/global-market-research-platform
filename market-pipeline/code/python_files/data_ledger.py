#!/usr/bin/env python3
"""
data_ledger.py — living data catalog: source × market × type × volume × freshness,
with an update date and the how/when-to-fetch for each asset. Re-run to refresh the
dynamic columns (volume, latest date, updated-at) from the files on disk; the static
columns (source, fetch command, best off-peak window, rate note) come from the registry.

Answers: which market is up to date at what level, and how/when to top it up without
hitting rate throttles.

Output: reports/data_ledger.md + cache_seed/data_ledger.parquet (persistent, versioned).
"""
from __future__ import annotations
import glob, datetime
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv"

# static registry: (asset, market, dtype, path/glob, source, fetch_cmd, off-peak window, rate note)
REG = [
 # ---- OHLCV (prices) ----
 ("ohlcv", "IN", "prices", f"{WH}/IN/year=*.parquet", "NSE/BSE bhavcopy",
  "bhavcopy_history.py", "18:00+ IST (EOD)", "official archive — no throttle"),
 ("ohlcv", "US", "prices", f"{WH}/US/year=*.parquet", "NASDAQ/yfinance",
  "ohlcv_cache.py", "post-US-close / 03:00-07:00 IST", "yfinance throttles in US hours"),
 ("ohlcv", "KR", "prices", f"{WH}/KR/year=*.parquet", "FinanceDataReader/KRX",
  "ohlcv_cache.py", "after 12:30 IST (KRX close)", "FDR gentle; batch"),
 ("ohlcv", "JP", "prices", f"{WH}/JP/year=*.parquet", "JPX/yfinance",
  "ohlcv_cache.py", "after 11:30 IST (TSE close)", "yfinance; J-Quants for validation"),
 ("ohlcv", "EU", "prices", f"{WH}/EU/year=*.parquet", "yfinance (17 exchanges)",
  "ohlcv_cache.py", "after 21:30 IST (EU close)", "yfinance; Volume sparse"),
 ("ohlcv", "CN", "prices", f"{WH}/CN/year=*.parquet", "akshare A-shares",
  "ohlcv_cache.py", "after 12:30 IST (SSE/SZSE close)", "akshare; avoid peak"),
 # ---- fundamentals ----
 ("fundamentals", "IN", "fundamentals", f"{FH}/IN_screener_only_backup.parquet", "screener.in",
  "screener_history_collector.py", "off-hours (run_fundamentals_offhours.sh)", "scrape politely"),
 ("fundamentals", "US", "fundamentals", f"{FH}/US.parquet", "SEC EDGAR",
  "edgar collector", "anytime", "EDGAR fair-use 10 req/s"),
 ("fundamentals", "US", "shares", f"{FH}/US_shares_supplement.parquet", "yfinance .info",
  "us_shares_fetch.py", "off-peak 03:00-07:00 IST", "yfinance ~50% shares coverage"),
 ("fundamentals", "KR", "fundamentals", f"{FH}/KR_deep.parquet", "DART (FSS)",
  "dart_history_collect.py", "off-hours", "DART_KEY; ~20k/day quota; XBRL from ~2019"),
 ("fundamentals", "JP", "fundamentals", f"{FH}/JP.parquet", "yfinance (J-Quants planned)",
  "(J-Quants fins/statements)", "off-hours", "JQUANTS_API_KEY set; tier-limited history"),
 ("fundamentals", "EU", "fundamentals", f"{FH}/EU_union.parquet", "yfinance (DE/DK/CH/FI/SE union)",
  "build EU_union", "after 21:30 IST", "5y only; pre-2021 needs registries"),
 ("fundamentals", "CN", "fundamentals", f"{FH}/CN_deep.parquet", "akshare indicators",
  "cn_akshare_collect.py", "after 15:00 CST / 12:30 IST", "akshare; sleep 0.3s/req"),
 # ---- derived ----
 ("derived", "IN/US/KR", "ratios", "reports/financial_ratios.csv", "financial_ratios.py",
  "financial_ratios.py", "post fundamentals refresh", "rebuilt daily [15b]"),
 ("derived", "6 markets", "ratios", "reports/all_ratios.csv", "build_all_ratios.py",
  "build_all_ratios.py", "post fundamentals refresh", "adds JP/EU/CN"),
]


def inspect(path: str):
    """(rows, tickers, latest_date, updated_at) from the file(s)."""
    files = sorted(glob.glob(path)) if "*" in path else ([path] if Path(path).exists() else [])
    files = [f for f in files if Path(f).exists()]
    if not files:
        return 0, 0, "—", "—"
    mt = max(Path(f).stat().st_mtime for f in files)
    updated = datetime.datetime.utcfromtimestamp(mt).strftime("%Y-%m-%d")
    try:
        if path.endswith(".csv"):
            d = pd.read_csv(files[0])
        else:
            cols = None
            samp = pd.read_parquet(files[0])
            keep = [c for c in ["Symbol", "ticker", "Date", "fy_end"] if c in samp.columns]
            d = pd.concat([pd.read_parquet(f, columns=keep) if keep else pd.read_parquet(f)
                           for f in files], ignore_index=True)
        rows = len(d)
        tkcol = next((c for c in ["ticker", "Symbol", "market"] if c in d.columns), None)
        tickers = d[tkcol].nunique() if tkcol else 0
        datecol = next((c for c in ["Date", "fy_end", "close_date"] if c in d.columns), None)
        latest = str(pd.to_datetime(d[datecol], errors="coerce").max().date()) if datecol else "—"
    except Exception:
        rows, tickers, latest = 0, 0, "?"
    return rows, tickers, latest, updated


def main() -> int:
    today = None  # avoid Date.now dependence for reproducibility; freshness uses file dates
    rows = []
    for asset, mkt, dtype, path, src, cmd, window, rate in REG:
        n, tk, latest, updated = inspect(path)
        rows.append({"asset": asset, "market": mkt, "type": dtype, "rows": n, "tickers": tk,
                     "latest_data": latest, "updated": updated, "source": src,
                     "fetch": cmd, "off_peak_window": window, "rate_note": rate})
    d = pd.DataFrame(rows)
    d.to_parquet(HERE / "cache_seed" / "data_ledger.parquet", index=False)

    L = ["# Data ledger — source · type · volume · freshness · how/when to fetch", "",
         "Living catalog; re-run `data_ledger.py` to refresh volume/latest/updated from disk. "
         "`updated` = the data file's last write (= last fetch). `off_peak_window` = when to "
         "fetch without rate throttling.", "",
         "## Prices (OHLCV)", "",
         "| market | rows | tickers | latest | updated | source | off-peak window | rate note |",
         "|---|--:|--:|--:|--:|---|---|---|"]
    for _, r in d[d.asset == "ohlcv"].iterrows():
        L.append(f"| {r.market} | {r.rows:,} | {r.tickers:,} | {r.latest_data} | {r.updated} | "
                 f"{r.source} | {r.off_peak_window} | {r.rate_note} |")
    L += ["", "## Fundamentals", "",
          "| market | type | rows | tickers | latest FY | updated | source | fetch | off-peak | rate note |",
          "|---|---|--:|--:|--:|--:|---|---|---|---|"]
    for _, r in d[d.asset == "fundamentals"].iterrows():
        L.append(f"| {r.market} | {r.type} | {r.rows:,} | {r.tickers:,} | {r.latest_data} | {r.updated} | "
                 f"{r.source} | `{r.fetch}` | {r.off_peak_window} | {r.rate_note} |")
    L += ["", "## Derived", "",
          "| scope | rows | updated | builder | note |", "|---|--:|--:|---|---|"]
    for _, r in d[d.asset == "derived"].iterrows():
        L.append(f"| {r.market} | {r.rows:,} | {r.updated} | `{r.fetch}` | {r.rate_note} |")
    L += ["", "## Fetch-window cheat-sheet (post-market, un-throttled)", "",
          "- **India prices** — NSE/BSE bhavcopy after **18:00 IST**; official archive, no throttle.",
          "- **yfinance** (US/EU/CN/JP prices + JP/EU fundamentals) — **03:00–07:00 IST** (post-US-close, "
          "pre-Asia-open); throttles hard during US market hours.",
          "- **DART** (KR fund) — anytime with `DART_KEY`; run off-hours to preserve the ~20k/day quota.",
          "- **J-Quants** (JP fund) — off-hours; free tier is history-limited.",
          "- **akshare** (CN fund) — after **12:30 IST** (China close); `sleep 0.3s`/request.",
          "- **SEC EDGAR** (US fund) — anytime, 10 req/s fair-use.",
          "- **screener.in** (IN fund) — the off-hours job; scrape politely.",
          "", "> Re-run after each collection to keep the ledger current; `cache_seed/data_ledger.parquet` "
          "is the machine-readable version. Research pipeline, not investment advice."]
    (HERE / "reports" / "data_ledger.md").write_text("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote reports/data_ledger.md + cache_seed/data_ledger.parquet ({len(d)} assets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
