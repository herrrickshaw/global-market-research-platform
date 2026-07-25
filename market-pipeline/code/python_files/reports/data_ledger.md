# Data ledger — source · type · volume · freshness · how/when to fetch

Living catalog; re-run `data_ledger.py` to refresh volume/latest/updated from disk. `updated` = the data file's last write (= last fetch). `off_peak_window` = when to fetch without rate throttling.

## Prices (OHLCV)

| market | rows | tickers | latest | updated | source | off-peak window | rate note |
|---|--:|--:|--:|--:|---|---|---|
| IN | 4,456,125 | 6,731 | 2026-07-22 | 2026-07-23 | NSE/BSE bhavcopy | 18:00+ IST (EOD) | official archive — no throttle |
| US | 16,290,431 | 9,807 | 2026-07-22 | 2026-07-23 | NASDAQ/yfinance | post-US-close / 03:00-07:00 IST | yfinance throttles in US hours |
| KR | 5,292,842 | 2,597 | 2026-07-23 | 2026-07-23 | FinanceDataReader/KRX | after 12:30 IST (KRX close) | FDR gentle; batch |
| JP | 7,359,698 | 3,083 | 2026-07-23 | 2026-07-23 | JPX/yfinance | after 11:30 IST (TSE close) | yfinance; J-Quants for validation |
| EU | 3,828,110 | 1,618 | 2026-07-22 | 2026-07-23 | yfinance (17 exchanges) | after 21:30 IST (EU close) | yfinance; Volume sparse |
| CN | 10,010,203 | 5,188 | 2026-07-01 | 2026-07-22 | akshare A-shares | after 12:30 IST (SSE/SZSE close) | akshare; avoid peak |

## Fundamentals

| market | type | rows | tickers | latest FY | updated | source | fetch | off-peak | rate note |
|---|---|--:|--:|--:|--:|---|---|---|---|
| IN | fundamentals | 14,162 | 1,487 | 2026-03-31 | 2026-07-18 | screener.in | `screener_history_collector.py` | off-hours (run_fundamentals_offhours.sh) | scrape politely |
| US | fundamentals | 111,949 | 4,597 | 2029-12-31 | 2026-07-19 | SEC EDGAR | `edgar collector` | anytime | EDGAR fair-use 10 req/s |
| US | shares | 463 | 463 | — | 2026-07-24 | yfinance .info | `us_shares_fetch.py` | off-peak 03:00-07:00 IST | yfinance ~50% shares coverage |
| KR | fundamentals | 6,825 | 1,564 | 2026-03-31 | 2026-07-24 | DART (FSS) | `dart_history_collect.py` | off-hours | DART_KEY; ~20k/day quota; XBRL from ~2019 |
| JP | fundamentals | 5,263 | 1,295 | 2026-03-31 | 2026-07-18 | yfinance (J-Quants planned) | `(J-Quants fins/statements)` | off-hours | JQUANTS_API_KEY set; tier-limited history |
| EU | fundamentals | 4,666 | 1,159 | 2026-05-31 | 2026-07-24 | yfinance (DE/DK/CH/FI/SE union) | `build EU_union` | after 21:30 IST | 5y only; pre-2021 needs registries |
| CN | fundamentals | 0 | 0 | — | — | akshare indicators | `cn_akshare_collect.py` | after 15:00 CST / 12:30 IST | akshare; sleep 0.3s/req |

## Derived

| scope | rows | updated | builder | note |
|---|--:|--:|---|---|
| IN/US/KR | 7,590 | 2026-07-24 | `financial_ratios.py` | rebuilt daily [15b] |
| 6 markets | 10,202 | 2026-07-24 | `build_all_ratios.py` | adds JP/EU/CN |

## Fetch-window cheat-sheet (post-market, un-throttled)

- **India prices** — NSE/BSE bhavcopy after **18:00 IST**; official archive, no throttle.
- **yfinance** (US/EU/CN/JP prices + JP/EU fundamentals) — **03:00–07:00 IST** (post-US-close, pre-Asia-open); throttles hard during US market hours.
- **DART** (KR fund) — anytime with `DART_KEY`; run off-hours to preserve the ~20k/day quota.
- **J-Quants** (JP fund) — off-hours; free tier is history-limited.
- **akshare** (CN fund) — after **12:30 IST** (China close); `sleep 0.3s`/request.
- **SEC EDGAR** (US fund) — anytime, 10 req/s fair-use.
- **screener.in** (IN fund) — the off-hours job; scrape politely.

> Re-run after each collection to keep the ledger current; `cache_seed/data_ledger.parquet` is the machine-readable version. Research pipeline, not investment advice.