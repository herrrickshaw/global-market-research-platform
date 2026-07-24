# Data sufficiency & completion — guarding against false outcomes

Cross-market conclusions are only as good as the data behind them. Before trusting any
verdict, `data_sufficiency.py` quantifies **completeness** (fundamentals coverage of the
*liquid* universe) and **statistical power** (non-overlapping observations behind each
t-stat). A 5-year window de-overlapped by 6 gives only ~9 observations — a t-stat there
is meaningless, so "not significant" means **underpowered**, not "no effect."

## Sufficiency verdict (per `data_sufficiency.py`)

| market | fund tickers | liquid universe | coverage | history | non-overlap 6M | verdict |
|--------|--:|--:|--:|--:|--:|---|
| **IN** | 1,870 | 3,103 | 60% | 2012–26 | 17 | ✅ **trust it** — powered + complete |
| **US** | 4,597 | 5,086 | 90% | 1987–26 | 17 | ✅ **trust it** |
| **KR** | 1,564 | 1,622 | 96% | 2016–26 (DART) | 17 | ✅ **trust it** |
| JP | 1,295 | 1,609 | 80% | 2021–26 | 9 | 🔴 **can't conclude** — underpowered |
| EU | 449→1,159 | (Volume sparse) | — | 2021–26 | 9 | 🔴 **can't conclude** |
| CN | 932 | 3,454 | 27% | 2021–25 | 9 | 🔴 **thin + underpowered** |

**Correction this forced:** the earlier "JP not significant / EU +36% / CN value absent"
were **data-sufficiency artifacts, not findings**. Only India, US, Korea have enough data
to support the value-reversion conclusion; JP/EU/CN must read as *"insufficient data"*
until deepened. (An earlier hand-written "IN 78% coverage" claim was itself a false
assumption — the audit computes it, never assumes it.)

## Completion plan (source · effort · status)

| market | gap | source | status |
|--------|-----|--------|--------|
| **CN** | 27% cov + 5y | **akshare** `stock_financial_analysis_indicator` (EPS+ROE to 2015) | ⏳ `cn_akshare_collect.py` running (liquid 600) |
| **EU** | breadth | union DE/DK/CH/FI/SE sub-markets | ✅ done — 449→**1,159** tickers (`EU_union.parquet`); depth (pre-2021) still open |
| **JP** | 5y depth | **J-Quants** (`JQUANTS_API_KEY` set) `fins/statements` | 📋 planned — J-Quants historical pull |
| **US** | shares 59% null | yfinance `sharesOutstanding` | ✅ partial (`us_shares_fetch.py`, 236 filled) |
| **KR** | — | DART (done, 2016→) | ✅ complete |
| EU pre-2021 | depth | national registries / a paid vendor | 🔴 hard — fragmented, low priority |

## Re-run gating

The analysis re-runs **per market as its data clears the sufficiency bar** (≥15 non-overlap
obs AND ≥60% liquid coverage):
1. Collect (CN akshare ⏳, JP J-Quants 📋, EU union ✅-breadth).
2. Merge into `*_deep.parquet`, rebuild `all_ratios` (`build_all_ratios.py`).
3. Re-run `data_sufficiency.py` → only then re-run `valuation_reversion_backtest.py` /
   `value_quality_ls_backtest.py` for the newly-sufficient market.
4. `strategy_matrix.py` flip-detects any verdict that changes.

Until a market clears the bar, its cell reads **"insufficient data"** — never a verdict.
This is the anti-false-outcome contract. Research only, not investment advice.
