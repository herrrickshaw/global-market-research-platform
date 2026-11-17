# Data-collection history — Japan & all other sources

An audit of what has already been collected (so we don't re-collect), where it lives, and
from which source. Compiled 2026-07-25.

## Japan — every source tried (rich history)

| layer | source | file / script | status |
|---|---|---|---|
| **Prices** | JPX / yfinance | `warehouse/ohlcv/JP/year=2016…2025`, `ltm/JP`, `compact/JP_2025plus` | ✅ deep (~10y, 2,467 tickers) |
| Prices gapfill | EC2 run | `dropbox:market-data-ec2/exports/gapfill_japan.parquet` (15.6MB) | ✅ 2026-07-23 |
| **Fundamentals** | yfinance | `JP.parquet` (`bulk_fetcher`) | ✅ 2021–2026 (~5y) |
| Fundamentals | **J-Quants V2** | `JP_jquants.parquet` (`jq_jp_collect.py`) | ✅ 2020–2026, authoritative, ~2y/ticker |
| Fundamentals | **kabupy** (kabuyoho scrape) | `jp_dual_validator.py` | ✅ used for cross-validation |
| Fundamentals | merged (J-Quants⊕yfinance) | `JP_merged.parquet` (`merge_jp_fund.py`) | ✅ 2,006 tickers |
| Fundamentals | **EDINET / Sakana EDINET-Bench** | HF parquets (no API key) | 🆕 1,478 tickers × 5y — not yet merged |
| Fundamentals | EDINET API (own collector) | `aws_collector/edinet_collect.py` | ⏸ needs Subscription-Key |
| **Earnings dates** | **TDnet** (JPX Timely Disclosure) | `earnings_dates_tdnet.py`, `earnings_dates_tdnet/JP.parquet` | ✅ real announcement dates |
| **Sectors / universe** | JPX listed-issues master | `jp_sectors.parquet` (data_e.xls) | ✅ 3,904 eq, 33/17-sector + ETF flag |
| Code map | EDINETCODE list | `edinet_code_map.parquet` | ✅ 3,828 listed cos, EDINET↔ticker |
| **Validation** | J-Quants vs panel | `jquants_validator.py` (daily-returns, not levels) | ✅ |
| Validation | kabupy × J-Quants dual | `jp_dual.log` (120 tickers, ~37 flagged) | ✅ EC2 2026-07-23 |

**Takeaway:** Japan has been collected from **six** fundamentals angles (yfinance, J-Quants,
kabupy, EDINET-Bench, EDINET-API-pending, merged) plus TDnet earnings dates and JPX sectors —
the *depth* gap (for the value backtest) is what remained, and the **Sakana EDINET-Bench panel
(1,478×5y, no key) is the piece that closes it.** J-Quants/kabupy are best kept as validators.

## Prior EC2 collection (Dropbox `market-data-ec2`, 2026-07-23)

`status.json`: **state=done, 2,307 tickers, 3.52M rows added, 1 error.** Exports:
`gapfill_{china,europe,hongkong(48MB),japan(15.6MB),korea,us}.parquet` + `jp_dual_validation`,
`jq_flags_gapfill`, `validation_flags`. → an EC2 machine has already done a full multi-market
price gapfill + JP dual-validation. The `market-data-ec2/{compact,exports,status}` tree is the
canonical EC2 output.

## Other markets — fundamentals already collected (~20 markets)

| market | file(s) | source |
|---|---|---|
| **India** | `IN`, `IN_screener_only_backup` (use this — merged has 4× EPS bug), `IN_nse_results` (XBRL), `IN_yfinance` | screener.in, NSE XBRL, yfinance |
| **US** | `US`, `US_shares_supplement` | SEC EDGAR + yfinance shares |
| **Korea** | `KR`, `KR_deep`, `KR_dart_history`, `KR_dart_joined` | DART/FSS |
| **China** | `CN`, `CN_deep` (+6 shards) | akshare 10y |
| **Europe** | `EU`, `EU_union`, `DE`, `DK`, `FI`, `SE`, `CH` | yfinance (sub-market union) |
| **Asia-Pacific** | `HK`, `SG`, `TW`, `AU` | yfinance |
| **Americas / other** | `CA`, `BR`, `SA` | yfinance |

So the platform already has **fundamentals for ~20 markets** (not just the 6 in the strategy
matrix) — the extras (HK/SG/TW/AU/CA/BR/SA/DE/DK/FI/SE/CH) are collected but not yet run through
the sufficiency + backtest pipeline.

## Storage map

| store | contents |
|---|---|
| `repos/global-market-data/warehouse/ohlcv/<MKT>` | prices, year-partitioned (all markets, ~10y) |
| `repos/global-stock-screener/cache_seed/fundamentals_history/` | fundamentals per market (the table above) |
| `dropbox:market-data-backup/current/` | fundamentals + gmd-cache + correlation scans (this session's pushes) |
| `dropbox:market-data-ec2/` | prior EC2 gapfill exports + status/logs |
| `dropbox:market-data-archive/`, `market-data-coldstore/` | older snapshots |

## What NOT to re-collect

- JP prices, JP J-Quants, JP kabupy, TDnet dates, JPX sectors — **done**.
- Multi-market price gapfill — **done on EC2** (2026-07-23, on Dropbox).
- 20-market fundamentals — **done** (just not all analysed).
- **Only genuinely new work:** merge the Sakana EDINET-Bench JP panel (closes JP depth), and
  run the sufficiency + backtest pipeline on the already-collected extra markets (HK/SG/TW/…).

> Research pipeline. Not investment advice.
