# Completeness audit — data, claims, and gates

Generated 2026-07-30 by `completeness_graph.py` (LangGraph, 4 nodes, deterministic — no LLM).

**15 sources inventoried, 0 missing/erroring, 0 source(s) past their expected refresh cadence · 8 scheduled scripts checked, 1 quoting numbers their own cited report no longer contains · 8 analyses checked for the contamination gate, 0 ungated · 30 conclusions have a declared universe, 8 rest on a top-N liquid SAMPLE rather than the full market · 7 Cassandra market(s) audited, 1 present but hollow (rows and prices, no fundamentals)**

## 1. Data completeness

| source | rows | symbols | span | stale (d) | cadence | crit |
|---|--:|--:|---|--:|---|:--:|
| `bhavcopy.cleaned_ohlcv` | 1,241,642 | 7,838 | 2025-06-25 -> 2026-07-29 | 1 | daily | ✅ |
| `bhavcopy.nse_deep_ohlcv` | 4,423,382 | 3,476 | 2016-01-01 -> 2026-07-13 | 17 | static |  |
| `fundamentals.india_pe_daily` | 1,962,914 | 1,744 | 2019-01-17 -> 2026-07-28 | 2 | daily | ✅ |
| `fundamentals.india_quarterly` | 53,794 | 2,575 | 2018-05-21 -> 2026-07-27 | 3 | quarterly | ✅ |
| `fundamentals.ratios` | 9,478 | 9,456 | — | — | weekly |  |
| `funds.nav` | 22,327,834 | 22,668 | 2016-07-28 -> 2026-07-27 | 3 | daily |  |
| `indices.nse_daily` | 240,314 | 173 | 2016-07-28 -> 2026-07-27 | 3 | daily |  |
| `indices.nse_tri` | 22,266 | 17 | 2016-08-01 -> 2026-07-27 | 3 | daily |  |
| `indices.custom_daily` | 61,963 | 31 | — | — | weekly |  |
| `market_daily.snapshots` | 180,816 | 17,398 | — | — | daily | ✅ |
| `market_daily.ticker_freshness` | 21,290 | 21,209 | — | — | daily | ✅ |
| `public.ohlcv_history` | 38,235,027 | — | 2011-01-04 -> 2026-07-17 | 13 | external |  |
| `public.global_fundamentals` | 245,116 | 25,430 | — | — | external |  |
| `india split factors` | 688 | 468 | — | — | — | ✅ |
| `india unverifiable` | 29 | 29 | — | — | — | ✅ |

## 2. Claim consistency — does the quoted number still exist upstream?

| script | cites | quoted | verdict |
|---|---|---|---|
| `reentry_engine.py` | tier_anomaly_backtest.md | — | consistent |
| `prediction_filter.py` | mailer_prediction_audit.md | — | consistent |
| `smallcap_screener.py` | — | — | no numeric claim cited |
| `playbook_screener.py` | market_playbook.md | — | consistent |
| `watchlist_tiers.py` | — | — | no numeric claim cited |
| `custom_indices.py` | smallcap_validation_hold126.md | +3.07%, t 8.75 | consistent |
| `cluster_indices.py` | cluster_indices.md | t  13.27, t  17.62 | consistent |
| `scan_price_reconcile.py` | — | +3.7% | 🔴 UNSOURCED |

## 3. Contamination gate coverage

| analysis | drops contaminated symbols | verdict |
|---|:--:|---|
| `pead_liquidity_study.py` | yes | gated |
| `pead_portfolio.py` | yes | gated |
| `cluster_indices.py` | yes | gated |
| `smallcap_screener.py` | yes | gated |
| `custom_indices.py` | yes | gated |
| `peer_warranted.py` | — | n/a — no raw price panel loaded |
| `etf_builder.py` | NO | guarded by refusal — rejects the unadjusted panel rather than filtering it |
| `reentry_book.py` | — | n/a — no raw price panel loaded |

## 4. Breadth and power — full universe, or a top-N sample?

| conclusion | declared universe | sample kind | n | formations |
|---|---|---|--:|--:|
| `pead_liquidity_study.md` | — | — | 42369 | — |
| `pead_fund_vs_spec.md` | — | — | 9658 | — |
| `PIOTROSKI_LIQUIDITY_PAPER.md` | definition (measured: $300k with junk, $896k without). The | declared | 2703 | 9 |
| `tier_anomaly_backtest.md` | top 200 | 🔶 SAMPLE (top-N liquid) | 1065 | — |
| `pe_anomaly_backtest.md` | 1458 NSE names, monthly 2017-01-31 → 2026-06-30. Annual PI | declared | 601 | 109 |
| `reentry_book.md` | — | — | 508 | — |
| `smallcap_validation_hold63.md` | — | — | 108 | 108 |
| `smallcap_validation_hold126.md` | — | — | 105 | 105 |
| `mailer_effectiveness.md` | — | — | 80 | — |
| `completeness_analysis_2026-07-28.md` | ** 6,731 (NSE + BSE) | declared | 60 | — |
| `sector_rotation.md` | — | — | 37 | 91 |
| `PIT_EVENT_STUDIES.md` | 78,799; the rest fall outside the 2016+ adjusted panel | declared | — | — |
| `STRATEGY_REPORT_TEMPLATE.md` | gate**: position ≤ 10% of the name's trailing-120d median  | declared | — | — |
| `bundle_validation.md` | top 14 | 🔶 SAMPLE (top-N liquid) | — | — |
| `cluster_indices.md` | top 300 by trailing turnover with an NSE Industry label (~ | 🔶 SAMPLE (top-N liquid) | — | 35 |
| `completeness_graph.md` | of 6 stocks and a span ending 2029, both impossible, while | 🔶 SAMPLE (top-N liquid) | — | — |
| `data_sufficiency.md` | fundamentals (raise coverage), (2) collect deep history vi | declared | — | — |
| `etf_builder.md` | top 200 | 🔶 SAMPLE (top-N liquid) | — | — |
| `fundamentals_vs_speculation.md` | findings (all 6 markets, 95% sector coverage) | declared | — | — |
| `long_short_tp.md` | top 12 | 🔶 SAMPLE (top-N liquid) | — | — |
| `peer_warranted.md` | — | — | — | 8 |
| `project_retrospective.md` | fundamentals-vs-speculation incomplete (US-only preview) | 🔶 SAMPLE (top-N liquid) | — | — |
| `reentry_markers.md` | top 200 | 🔶 SAMPLE (top-N liquid) | — | — |
| `strategy_regime_survival.md` | = HIGH+MEDIUM turnover tier only. `spread` = BUY−SELL fwd- | declared | — | — |
| `valuation_reversion_cn.md` | — | — | — | 109 |
| `valuation_reversion_eu.md` | — | — | — | 35 |
| `valuation_reversion_jp.md` | — | — | — | 116 |
| `valuation_reversion_kr.md` | — | — | — | 35 |
| `valuation_reversion_kr_deep.md` | — | — | — | 68 |
| `valuation_reversion_us.md` | — | — | — | 109 |

> 🔶 marks a conclusion measured on the most liquid slice of the market. That is not a defect — liquidity gating is deliberate and keeps the result tradeable — but it narrows what the number is ABOUT, and the narrowing disappears by the time the figure is quoted downstream.

## 5. Cassandra — rows present vs fields POPULATED vs MEASURED

| market | rows | price fields | fundamentals | measured | verdict |
|---|--:|--:|--:|--:|---|
| us | 9,458 | 6,435 | 9,451 (99.9%) | 3,137 (33.2%) | fundamentals present |
| china | 5,207 | 5,196 | 5,188 (99.6%) | 19 (0.4%) | 🔴 ALMOST ALL IMPUTED — populated, not measured |
| japan | 3,664 | 3,643 | 3,664 (100.0%) | 0 (0.0%) | 🔴 ALMOST ALL IMPUTED — populated, not measured |
| india | 3,484 | 2,367 | 3,484 (100.0%) | 1,328 (38.1%) | fundamentals present |
| korea | 2,766 | 2,757 | 2,766 (100.0%) | 0 (0.0%) | 🔴 ALMOST ALL IMPUTED — populated, not measured |
| hong_kong | 2,765 | 2,765 | 0 (0.0%) | n/a | 🔴 HOLLOW — counts as coverage, is not coverage |
| europe | 1,826 | 990 | 1,826 (100.0%) | 416 (22.8%) | fundamentals present |

> `fundamentals` is COUNTED as the BEST-populated column in each group, so it is an upper bound — the true per-field coverage is lower. `measured` is rows whose `fundamentals_source` is NOT `median_imputed` — found 2026-07-30 while investigating a repeated-decimal (pe,pb,roe) triple across unrelated symbols (a contamination shape the whole-number score check above does not catch). Every market sampled at 99-100% imputed; a median-imputed ROE ranks identically to a measured one in anything that sorts on the column, so `fundamentals present` alone was reporting placeholder coverage as if it were per-symbol data. A row that exists with null fundamentals is still worse than a missing table — the missing table raises an error where it is used, the null column silently narrows every downstream sample and still reports full coverage to a `COUNT(*)`.

## Notes

- 🔴 cassandra[japan]: fund_pct reports 100% populated, but only 0.0% of that is measured — the rest is fundamentals_source='median_imputed' reporting as if it were real per-symbol data
- 🔴 cassandra[korea]: fund_pct reports 100% populated, but only 0.0% of that is measured — the rest is fundamentals_source='median_imputed' reporting as if it were real per-symbol data
- 🔴 cassandra[china]: fund_pct reports 100% populated, but only 0.4% of that is measured — the rest is fundamentals_source='median_imputed' reporting as if it were real per-symbol data
- 🔴 cassandra[hong_kong]: 2,765 rows, prices populated (2,765) but fundamentals effectively EMPTY (0 = 0.0%) — counts as coverage in a row count, is not coverage in an analysis

> Completeness is not correctness. This audit proves a source is present, fresh, internally consistent with what quotes it, and gated — not that the numbers in it are right. `reports/data_sufficiency.md` is the cautionary case: it reports a US liquid universe of 6 stocks and a span ending 2029, both impossible, while looking like a clean pass.
