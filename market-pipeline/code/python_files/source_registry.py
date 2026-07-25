#!/usr/bin/env python3
"""
source_registry.py — the master DATA-SOURCES registry: every upstream provider the
platform pulls from, what it gives, how to access it, auth, rate limits, the best
off-peak window, and a live reachability probe with a last-checked date. Distinct from
`data_ledger.py` (data ASSETS on disk — volume/freshness); this tracks the SOURCES, for
constant reference & update. (Not to be confused with `data_sources.py`, the runtime
OHLC-fetch fallback module.)

Re-run to refresh reachability; the static metadata is the registry. Wired into the
every-3-days `data_check.sh`.

Output: docs/DATA_SOURCES.md (human) + cache_seed/data_sources.parquet (machine).
"""
from __future__ import annotations
import datetime
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent

# id, markets, data_type, provider, url, official, access, auth, rate/window, notes
REG = [
 # ---- PRICES (OHLCV) ----
 ("in-bhavcopy", "IN", "prices", "NSE/BSE Bhavcopy", "https://www.nseindia.com/", True,
  "daily EOD CSV archive", "none", "after 18:00 IST · no throttle",
  "official archive; 2,681 stocks in hrs vs days of yfinance"),
 ("us-yf", "US", "prices", "NASDAQ trader + yfinance", "https://finance.yahoo.com/", False,
  "yf.download batches (+ Stooq fallback)", "none", "03:00-07:00 IST · throttles in US hours",
  "~9,800 tickers; data_sources.py has the Stooq fallback"),
 ("kr-fdr", "KR", "prices", "FinanceDataReader/KRX", "https://finance.naver.com/", False,
  "FDR API", "none", "after 12:30 IST (KRX close)", "KOSPI+KOSDAQ"),
 ("jp-yf", "JP", "prices", "JPX + yfinance", "https://www.jpx.co.jp/", True,
  "yf.download; JPX for validation", "none", "after 11:30 IST (TSE close)", "3,083 tickers"),
 ("eu-yf", "EU", "prices", "yfinance (17 exchanges)", "https://finance.yahoo.com/", False,
  "yf.download", "none", "after 21:30 IST (EU close)", "Volume sparse in warehouse"),
 ("cn-akshare-px", "CN", "prices", "akshare (wraps SSE/SZSE)", "https://akshare.akfamily.xyz/", False,
  "ak.stock_zh_a_hist", "none", "after 12:30 IST (China close)", "A-shares"),
 # ---- FUNDAMENTALS ----
 ("in-screener", "IN", "fundamentals", "screener.in", "https://www.screener.in/", False,
  "login + HTML/export", "creds (.env)", "off-hours · scrape politely",
  "10y India vs yf's 5; 'Operating Profit' is QUARTERLY — derive ebit; use IN_screener_only_backup"),
 ("us-edgar", "US", "fundamentals", "SEC EDGAR", "https://www.sec.gov/edgar", True,
  "companyfacts JSON API", "UA header", "anytime · 10 req/s fair-use",
  "authoritative dated filings; F-score inverted in US backtest"),
 ("kr-dart", "KR", "fundamentals", "DART / FSS (OpenDART)", "https://opendart.fss.or.kr/", True,
  "REST API", "DART_KEY", "off-hours · ~20k/day quota", "XBRL from ~2019; 96% raw coverage"),
 ("jp-jquants", "JP", "fundamentals", "J-Quants V2", "https://api.jquants.com/v2", True,
  "REST /fins/summary", "x-api-key", "off-hours · rate-limited (429 backoff)",
  "V1 dead (410→V2); free/std ~2y (quality not depth); Premium 20y = paid"),
 ("cn-akshare-fun", "CN", "fundamentals", "akshare indicators", "https://akshare.akfamily.xyz/", False,
  "ak.stock_financial_analysis_indicator", "none", "after 12:30 IST · sleep 0.3s/req",
  "wraps SSE/SZSE/Eastmoney; EPS+ROE to 2015 (10y); the free deep-history path for CN"),
 # ---- OFFICIAL CN EXCHANGES (provenance + validation) ----
 ("cn-sse", "CN", "official-exchange", "Shanghai SE (SSE)", "https://english.sse.com.cn/", True,
  "query.sse.com.cn JSON API (+Referer)", "none", "anytime (validation)",
  "English portal live; query API returns JSON for 60x/68x; financials mostly PDF"),
 ("cn-szse", "CN", "official-exchange", "Shenzhen SE (SZSE)", "http://www.szse.cn/English/", True,
  "disclosure/report APIs (session-gated)", "none", "anytime (validation)",
  "portal reachable; direct API finicky (50x on guess) — akshare is the practical wrap"),
 ("cn-bse", "CN", "official-exchange", "Beijing SE (BSE)", "https://www.bse.cn/", True,
  "listings/disclosures", "none", "anytime", "NEEQ-graduated small caps; niche coverage"),
 ("cn-csrc", "CN", "regulator", "CSRC", "http://www.csrc.gov.cn/csrc_en/", True,
  "regulatory filings (PDF)", "none", "anytime", "regulator; rules + enforcement, not bulk financials"),
 # ---- REFERENCE / UNIVERSE ----
 ("jp-jpx-master", "JP", "reference", "JPX listed-issues master",
  "https://www.jpx.co.jp/english/markets/statistics-equities/misc/", True,
  "data_e.xls download", "none", "anytime · FREE",
  "TSE 33/17-sector + TOPIX size + ETF flag; 3,904 equities; NOT fundamentals (paid)"),
 ("in-nse-list", "IN", "reference", "NSE EQUITY_L", "https://www.nseindia.com/", True,
  "EQUITY_L.csv", "none", "anytime", "daily-refreshed universe"),
]
COLS = ["id", "markets", "data_type", "provider", "url", "official",
        "access", "auth", "rate_window", "notes"]


def probe(url: str) -> str:
    """live reachability — HTTP status or error class (best-effort, short timeout)."""
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 Chrome/120"},
                         timeout=10, stream=True, allow_redirects=True)
        r.close()
        return f"HTTP {r.status_code}"
    except Exception as e:
        return type(e).__name__


def main(do_probe: bool = True) -> int:
    today = datetime.date.today().isoformat()
    rows = []
    for r in REG:
        d = dict(zip(COLS, r))
        d["reachable"] = probe(d["url"]) if do_probe else "—"
        d["checked"] = today
        rows.append(d)
    df = pd.DataFrame(rows)
    df.to_parquet(HERE / "cache_seed" / "data_sources.parquet", index=False)

    L = ["# Data sources registry — provenance, access, auth, reachability", "",
         f"Master list of every upstream the platform pulls from. Re-run `source_registry.py` "
         f"to refresh reachability (last checked **{today}**). Distinct from `data_ledger.md` "
         "(on-disk assets); this is the SOURCES catalog — constantly referenced & updated. "
         "🟢 official exchange/regulator · ⚪ third-party aggregator.", "",
         "> `reach` is a **bare-URL liveness** ping. A `403/401` on a keyed/cookie'd source "
         "(EDGAR needs a UA, NSE needs a cookie, J-Quants needs the `x-api-key`) is **expected** "
         "— use the method in the `access` column, not a plain GET. Only a connection error "
         "means the host is actually unreachable.", ""]
    for section, dt in [("Prices (OHLCV)", "prices"), ("Fundamentals", "fundamentals"),
                        ("Official CN exchanges & regulator", ("official-exchange", "regulator")),
                        ("Reference / universe", "reference")]:
        sub = df[df.data_type.isin(dt if isinstance(dt, tuple) else [dt])]
        if not len(sub):
            continue
        L += [f"## {section}", "",
              "| market | provider | reach | access | auth | off-peak / rate | notes |",
              "|---|---|:--:|---|---|---|---|"]
        for _, r in sub.iterrows():
            flag = "🟢" if r.official else "⚪"
            L.append(f"| {r.markets} | {flag} [{r.provider}]({r.url}) | {r.reachable} | {r.access} | "
                     f"{r.auth} | {r.rate_window} | {r.notes} |")
        L.append("")
    L += ["## CN sourcing decision", "",
          "akshare is the **practical collection engine** for China — it aggregates SSE + SZSE + "
          "BSE + Eastmoney/Sina, which mirror the official filings, and exposes 10y EPS/ROE "
          "programmatically (`stock_financial_analysis_indicator`). The official **SSE query API** "
          "(JSON, works with a `Referer`) is the **authoritative validation** layer for "
          "600/601/603/688xxx names; **SZSE**'s direct API is session-gated/unreliable; **CSRC/BSE** "
          "are provenance, not bulk feeds. Direct exchange scrapers would duplicate akshare for no "
          "depth gain.", "",
          "> Re-run in the every-3-days `data_check.sh`. Research pipeline, not investment advice."]
    (HERE / "docs" / "DATA_SOURCES.md").write_text("\n".join(L))
    print("\n".join(L))
    print(f"\nwrote docs/DATA_SOURCES.md + cache_seed/data_sources.parquet ({len(df)} sources)")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(do_probe="--no-probe" not in sys.argv))
