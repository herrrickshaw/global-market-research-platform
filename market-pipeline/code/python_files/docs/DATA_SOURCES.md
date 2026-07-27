# Data sources registry — provenance, access, auth, reachability

Master list of every upstream the platform pulls from. Re-run `source_registry.py` to refresh reachability (last checked **2026-07-25**). Distinct from `data_ledger.md` (on-disk assets); this is the SOURCES catalog — constantly referenced & updated. 🟢 official exchange/regulator · ⚪ third-party aggregator.

> `reach` is a **bare-URL liveness** ping. A `403/401` on a keyed/cookie'd source (EDGAR needs a UA, NSE needs a cookie, J-Quants needs the `x-api-key`) is **expected** — use the method in the `access` column, not a plain GET. Only a connection error means the host is actually unreachable.

## Prices (OHLCV)

| market | provider | reach | access | auth | off-peak / rate | notes |
|---|---|:--:|---|---|---|---|
| IN | 🟢 [NSE/BSE Bhavcopy](https://www.nseindia.com/) | HTTP 403 | daily EOD CSV archive | none | after 18:00 IST · no throttle | official archive; 2,681 stocks in hrs vs days of yfinance |
| US | ⚪ [NASDAQ trader + yfinance](https://finance.yahoo.com/) | HTTP 200 | yf.download batches (+ Stooq fallback) | none | 03:00-07:00 IST · throttles in US hours | ~9,800 tickers; data_sources.py has the Stooq fallback |
| KR | ⚪ [FinanceDataReader/KRX](https://finance.naver.com/) | HTTP 200 | FDR API | none | after 12:30 IST (KRX close) | KOSPI+KOSDAQ |
| JP | 🟢 [JPX + yfinance](https://www.jpx.co.jp/) | HTTP 200 | yf.download; JPX for validation | none | after 11:30 IST (TSE close) | 3,083 tickers |
| EU | ⚪ [yfinance (17 exchanges)](https://finance.yahoo.com/) | HTTP 200 | yf.download | none | after 21:30 IST (EU close) | Volume sparse in warehouse |
| CN | ⚪ [akshare (wraps SSE/SZSE)](https://akshare.akfamily.xyz/) | HTTP 200 | ak.stock_zh_a_hist | none | after 12:30 IST (China close) | A-shares |

## Fundamentals

| market | provider | reach | access | auth | off-peak / rate | notes |
|---|---|:--:|---|---|---|---|
| IN | ⚪ [screener.in](https://www.screener.in/) | HTTP 200 | login + HTML/export | creds (.env) | off-hours · scrape politely | 10y India vs yf's 5; 'Operating Profit' is QUARTERLY — derive ebit; use IN_screener_only_backup |
| US | 🟢 [SEC EDGAR](https://www.sec.gov/edgar) | HTTP 403 | companyfacts JSON API | UA header | anytime · 10 req/s fair-use | authoritative dated filings; F-score inverted in US backtest |
| KR | 🟢 [DART / FSS (OpenDART)](https://opendart.fss.or.kr/) | HTTP 200 | REST API | DART_KEY | off-hours · ~20k/day quota | XBRL from ~2019; 96% raw coverage |
| JP | 🟢 [J-Quants V2](https://api.jquants.com/v2) | HTTP 403 | REST /fins/summary | x-api-key | off-hours · rate-limited (429 backoff) | V1 dead (410→V2); free/std ~2y (quality not depth); Premium 20y = paid |
| CN | ⚪ [akshare indicators](https://akshare.akfamily.xyz/) | HTTP 200 | ak.stock_financial_analysis_indicator | none | after 12:30 IST · sleep 0.3s/req | wraps SSE/SZSE/Eastmoney; EPS+ROE to 2015 (10y); the free deep-history path for CN |

## Official CN exchanges & regulator

| market | provider | reach | access | auth | off-peak / rate | notes |
|---|---|:--:|---|---|---|---|
| CN | 🟢 [Shanghai SE (SSE)](https://english.sse.com.cn/) | ReadTimeout | query.sse.com.cn JSON API (+Referer) | none | anytime (validation) | English portal live; query API returns JSON for 60x/68x; financials mostly PDF |
| CN | 🟢 [Shenzhen SE (SZSE)](http://www.szse.cn/English/) | HTTP 200 | disclosure/report APIs (session-gated) | none | anytime (validation) | portal reachable; direct API finicky (50x on guess) — akshare is the practical wrap |
| CN | 🟢 [Beijing SE (BSE)](https://www.bse.cn/) | HTTP 200 | listings/disclosures | none | anytime | NEEQ-graduated small caps; niche coverage |
| CN | 🟢 [CSRC](http://www.csrc.gov.cn/csrc_en/) | HTTP 200 | regulatory filings (PDF) | none | anytime | regulator; rules + enforcement, not bulk financials |

## Reference / universe

| market | provider | reach | access | auth | off-peak / rate | notes |
|---|---|:--:|---|---|---|---|
| JP | 🟢 [JPX listed-issues master](https://www.jpx.co.jp/english/markets/statistics-equities/misc/) | HTTP 200 | data_e.xls download | none | anytime · FREE | TSE 33/17-sector + TOPIX size + ETF flag; 3,904 equities; NOT fundamentals (paid) |
| IN | 🟢 [NSE EQUITY_L](https://www.nseindia.com/) | HTTP 403 | EQUITY_L.csv | none | anytime | daily-refreshed universe |

## CN sourcing decision

akshare is the **practical collection engine** for China — it aggregates SSE + SZSE + BSE + Eastmoney/Sina, which mirror the official filings, and exposes 10y EPS/ROE programmatically (`stock_financial_analysis_indicator`). The official **SSE query API** (JSON, works with a `Referer`) is the **authoritative validation** layer for 600/601/603/688xxx names; **SZSE**'s direct API is session-gated/unreliable; **CSRC/BSE** are provenance, not bulk feeds. Direct exchange scrapers would duplicate akshare for no depth gain.

> Re-run in the every-3-days `data_check.sh`. Research pipeline, not investment advice.