# Project retrospective — findings, gaps, and what to publish

A full-arc review from the platform's origin to the live paper-track: what we've established, what's still open, and which insights are novel enough to publish.

## The analysis arc (phases)

1. **Build** — multi-market platform, income/balance statements from the paper-track, 10-stage pipeline, regime survival, Lasso/learning-rate, AWS/Colab sweep, mailer/watchlist.
2. **Validate** — PIT reversion backtests, Deflated Sharpe, value+quality L/S, the suitability matrix; the market-character meta-finding.
3. **Guard** — the anti-false-outcome layer: data_sufficiency, data_ledger, source_registry, the every-3-days check; caught false JP/EU/CN verdicts.
4. **Collect** — deep PIT fundamentals (CN baostock 10y, JP EDINET/J-Quants, EU union, JPX sectors, Damodaran) with anti-throttle (baostock, curl_cffi); the Japan flip.
5. **Explain** — fundamentals-vs-speculation (3 lenses + Damodaran + ROIC/WACC + country-ERP), PEAD routing, the confusion-matrix/information-asymmetry synthesis.
6. **Evaluate** — 70 strategies (durability × access), screener.in popular screens, an audit of the prior working paper.
7. **Operationalise** — the market playbook → live playbook screener → watchlist → daily mailer (sent). Research is now a running system.
8. **Industrialise** (2026-07-27) — official-source fundamentals for JP/KR/CN (EDINET/DART/Eastmoney), one canonical global_fundamentals layer (237k rows, 14 markets), priority-balanced ETL with SQL quality gates + batch lineage, knowledge-graph over the repo, cloud-first raw archives (0 MB local).

## Consolidated findings

| finding | confidence | status |
|---|--:|---|
| Market character decides the playbook (IN mom, KR L/S, JP/US value, EU mom, CN passive) | 9/10 | validated |
| Value-reversion works IN/US/KR/JP (t2.3–4.84), FAILS in China (t0.3, powered null) | 9/10 | validated |
| Momentum/trend survives multiple-testing in IN/KR/EU (Deflated Sharpe >0.95) | 8/10 | validated |
| Fundamentals-vs-speculation is the master dial (explains China null + biotech + PEAD routing) | 8/10 | validated |
| Three regimes not two: current-fundamentals / R&D-growth / speculation (R&D-adj ROIC) | 7/10 | validated |
| PEAD lives in the SPECULATIVE corner (information uncertainty), opposite of value-reversion | 7/10 | validated |
| Edge is MAGNITUDE not hit-rate (~50% accuracy yet profitable); illiquidity-driven, ~$300–500k cap | 8/10 | validated |
| Information-asymmetry tax is horizon-dependent → retail can only harvest SLOW edges | 8/10 | validated |
| Measurement > data quantity (Japan flip: null→+6.6%/6M t4.84 via EDINET depth) | 9/10 | validated |
| Country-ERP: China's cheapness is NOT risk-justified (CRP 0.91%) → speculation confirmed | 7/10 | validated |
| China: NEITHER value (t0.3) NOR 6M momentum (t−0.2) works — passive only (was tentative, now tested) | 8/10 | validated |
| KR value+quality L/S HALVES net of borrow (+4.83%→+2.3%/6M, t4.2→2.0); US L/S turns negative net | 8/10 | validated |
| China is BIMODAL — anchored SOE core (Utilities PB~ROE R²0.90) + speculative retail growth-periphery | 6/10 | validated (small-n caveat) |
| Fundamentals-vs-speculation is MARKET×SECTOR-specific, not poolable across markets | 7/10 | validated |
| EU value effect | 2/10 | underpowered — cannot conclude |
| Official-source fundamentals now span 5 majors (EDGAR US · EDINET JP 99.97% · DART KR · Eastmoney CN · screener.in IN) — 237k-row unified layer | 9/10 | validated 2026-07-27 |
| The right endpoint beats scraping: EDINET's real API host (api.*, not the website) + Eastmoney bulk (all A-shares in 3 calls/yr) replaced weeks of per-stock crawling | 8/10 | validated 2026-07-27 |
| Source precedence belongs in the DBMS, not script order — SQL priority upsert + quality gates auto-rejected the eps-only CN feed on first contact | 8/10 | validated 2026-07-27 |
| External validation gates earn their keep: screener.in check caught a stale INFY close (Friday price on a +3.7% Monday) before the mailer shipped it | 8/10 | validated 2026-07-27 |
| Evictions during market-bull BOOMERANG 45-75% (IN 75/KR 63/US 49/JP 45, 6,151 events) — a bear-state dip in a bull market is usually the bounce | 8/10 | validated 2026-07-27 |
| RSI at eviction has ZERO power to predict which evictions return (median 41 vs 41, all markets) — RSI is a re-entry trigger, not an eviction filter | 8/10 | validated 2026-07-27 |
| Re-entry at the anomaly trigger carries real edge: excess +12.9%/63d IN (t14.2), +24.9% KR (t14.8), +6.1% JP, +5.1% US — survivorship-lite caveat, paper-track settling live | 7/10 | validated 2026-07-27 (live OOS pending) |

## Gaps to fix (prioritised by impact ÷ effort)

| gap | impact | effort | fix |
|---|--:|--:|---|
| valuation_clusters only IN/US/KR — JP/EU/CN have no peer clusters (screener falls back) | 8 | 3 | re-run valuation_clustering.py on JP_full/CN_full/EU_union (data now exists) → fills JP/EU picks |
| EV/EBITDA sector map not run (dam_vebitda downloaded) | 5 | 2 | capital-structure-neutral re-do of the sector map — de-distorts financials/asset-heavy |
| EU has no official-source fundamentals (no EDGAR-equivalent wired; EODHD key dormant on an env-var rename) | 5 | 2 | alias EODHD_KEY→EODHD_API_KEY to wake the wired 20-exchange fallback; longer term: per-country registries |
| Short-borrow cost not modelled in KR/JP long/short returns | 6 | 3 | haircut the short leg by a locate+borrow estimate — the L/S t-stats are gross |
| Full-universe fundamentals-vs-speculation incomplete (US-only preview) | 6 | 4 | join Damodaran sector map (48k, instant) to all markets → the cross-market speculation map |
| Confusion matrix on SHORT-horizon signals (PEAD/momentum) not done | 6 | 4 | where the info-asymmetry tax actually bites — run the net-of-cost classifier on fast signals |
| fx_usd in global_fundamentals is a static 2026-07 snapshot | 3 | 2 | wire FRED (key exists, unused) for live FX + macro regime in one step |
| H2 Accumulation (prior paper) never re-tested this session | 5 | 4 | OBV/Chaikin accumulation backtest — auditable open item from the paper |
| Time-series speculation only US 2017–2025, shallow | 5 | 4 | CN_em now holds 10y of full statements — extend the TS speculation study to CN (and JP via EDINET) next |
| Regime (bull/bear) not wired into the LIVE screener (static filters) | 5 | 4 | condition the playbook screener on the breadth-regime proxy already built |
| Live forward performance = zero (paper-track just started) | 7 | 9 | TIME — the picks were only just watchlisted; needs weeks/months to validate out-of-sample |
| Re-entry engine edge is backtest-only (survivorship-lite top-200 panel) | 6 | 8 | TIME — status=reentry rows now feed the paper-track; judge after 1-2 months of live triggers |
| EU depth pre-2021 paywalled → EU value stays underpowered | 4 | 7 | national registries / paid vendor — low priority, hard |

### ✅ Cleared this pass (2026-07-27)

1. JP fundamentals gap CLOSED — EDINET official API, 3,933 filings, 99.97% of the live universe FY2024+. 2. KR fundamentals gap CLOSED — DART official API, 6,352 filings FY2023-25. 3. CN statements gap CLOSED — Eastmoney bulk, 50k rows / 10y / 100% revenue fill (was eps-only). 4. Unified global_fundamentals (237k rows, 14 markets) + DBMS ETL (priority upsert, quality gates, lineage, watermarks). 5. Consistency hygiene: EU per-suffix currency + fx_usd, fy_end sanity filter, placeholder markets purged. Prior pass: valuation clustering JP/EU/CN, CN momentum null, borrow-haircut L/S, full-universe fund-vs-spec, EV/EBITDA.

### Residual backlog (bigger / time-gated)

1. **Extend valuation clustering to JP/EU/CN** — the data now exists; instantly fills the thin JP/EU picks and gives peer-relative value everywhere (impact 8, effort 3).
2. **Backtest CN momentum** — resolve the one asserted-but-untested claim (impact 6, effort 3).
3. **Haircut the KR/JP L/S returns for borrow cost** — the strongest edge (KR t4.2) is gross of the short-leg cost; net it before trusting the magnitude (impact 6, effort 3).
4. **Join the Damodaran 48k sector map to all markets** — completes the cross-market speculation map without waiting on the yfinance crawl (impact 6, effort 3).

## What to publish

| insight | novelty | vehicle |
|---|--:|---|
| Measurement over quantity: the Japan value flip (null→edge via deep PIT data) | 9/10 | note/blog + v3 paper |
| Fundamentals-vs-speculation as a master dial (sector+market, PEAD routing) | 8/10 | working paper section |
| Cross-market factor character map (which factor fits which market, 6 markets deep-data) | 8/10 | v3 of the platform paper |
| Information-asymmetry tax × horizon: why retail can only harvest slow edges | 7/10 | blog/note |
| Three regimes: separating R&D-growth from speculation (R&D-adjusted ROIC) | 6/10 | note |

**The headline publishable contribution:** *measurement quality dominates data quantity* — demonstrated live by the Japan flip (an underpowered null became a t 4.84 edge when deep PIT history replaced a snapshot) **and** its mirror, China (a null that *survived* the same deepening). This is the inverse of the replication crisis and extends the prior working paper to a v3 with genuine cross-market deep data. The fundamentals-vs-speculation dial and the retail-harvestability framing are the two other sections worth writing up.

> Descriptive research retrospective. Not investment advice.