# Progress report — systematic multi-market strategy platform

**Date:** 2026-07-25 · **Branch:** `claude/strategy-pipeline` · **Scope:** India, US, Korea, Japan, Europe, China
**Status:** research / paper-track only — **no capital deployed**. Every signal below is descriptive
model output, **not investment advice.**

---

## 1. Data status (from `data_ledger.py`, live-inspected)

| market | prices (rows / tickers / latest) | fundamentals (tickers / latest FY / source) | sufficiency verdict |
|---|---|---|---|
| **IN** | 4.46M / 6,731 / 2026-07-22 | 1,487 / 2026-03 / screener.in | ✅ **powered + complete** (60% liq cov, 17 obs) |
| **US** | 16.3M / 9,807 / 2026-07-22 | 4,597 / SEC EDGAR | ✅ **powered** (90% cov) · ⚠️ 12 future-dated FY rows to clean |
| **KR** | 5.29M / 2,597 / 2026-07-23 | 1,564 / 2026-03 / DART | ✅ **powered** (96% cov, borderline window) |
| **JP** | 7.36M / 3,083 / 2026-07-23 | 1,295 / 2026-03 / yfinance | 🔴 **underpowered** (5y, ~9 obs) |
| **EU** | 3.83M / 1,618 / 2026-07-22 | 1,159 / yfinance union | 🔴 **underpowered** (Volume sparse, ~9 obs) |
| **CN** | 10.0M / 5,188 / 2026-07-01 | ⏳ collecting (akshare) | 🔴 **thin** (27%→ improving) |

**In flight:** CN deep fundamentals via akshare (liquid 600, ~2–3h, background). EU breadth already
tripled (449→1,159 tickers via sub-market union).

---

## 2. Run summary — which runs produced usable results

| run | result | usable? |
|---|---|---|
| **Valuation reversion IN** (sector-relative) | +5.3%/6M, **t 2.5** | ✅ **yes — validated** |
| Valuation reversion US | +1.72%/3M **t 2.32**; fades to t1.16 at 6M | ✅ short-horizon only |
| Valuation reversion KR (deep) | +3.85%/6M, t 1.51 | 🟡 borderline |
| Valuation reversion JP / EU / CN | JP t−0.62 · EU +35.9% t1.57 · CN t0.02 | 🔴 **no — underpowered** (data artifacts) |
| **Value+Quality L/S KR** | **+4.83%/6M, t 4.17** | ✅ **yes — strongest** |
| Value+Quality L/S US | +1.66%/6M, t0.98 | 🟡 marginal |
| Value+Quality L/S IN | −1.00%/6M | ❌ fails (momentum runs shorts over) |
| **Deflated Sharpe** (10-trial multiple-testing) | IN-bull-trend .994 · KR-bull-breakout .99 · EU-bull-mom252 .985 **survive**; all bear factors fail | ✅ overfit guard working |
| Learned model (Lasso+SGD) | kept factors: **IN** (trend), **KR** (trend/mom126/golden_cross/lowvol); US/JP/EU → none | ✅ shadow mode |
| Clustering (peer valuation z) | IN/US/KR over/under-priced lists | ✅ descriptive |

**Bottom line:** the money-good results are **IN reversion, KR value+quality L/S, and the three
DSR-surviving momentum factors.** Everything in JP/EU/CN is "insufficient data," not a finding.

---

## 3. Data sources that would speed things up

| gap | source | payoff | effort |
|---|---|---|---|
| CN depth+coverage | **akshare** `stock_financial_analysis_indicator` (→2015) | 27%→80%, 5y→10y → unlocks CN | ⏳ running |
| JP depth | **J-Quants** `fins/statements` (key already set) | 5y→10y → powers JP | 1 collection run |
| EU depth (pre-2021) | national registries / paid vendor | powers EU | 🔴 hard/fragmented |
| US shares (59% null) | yfinance `sharesOutstanding` | tightens US PE | ✅ partial (236 done) |
| IN faster prices | **NSE bhavcopy** already used (2,681 stocks in hrs vs days) | — | done |
| Off-peak windows | ledger cheat-sheet (bhavcopy 18:00 IST no-throttle; yfinance 03:00–07:00 IST) | avoids rate limits | documented |

---

## 4. Insights ledger — key findings across the whole build

1. **Market character IS the playbook.** IN = momentum/trend/long-only; KR = mean-reversion/full
   long-short; US = mixed/light; JP/EU = weak mean-revert. A uniform rule backtested *wrong* (KR t−2.5).
2. **Cheap-vs-peers corrects upward** — but only where powered: **IN (t2.5), US short-horizon (t2.32).**
3. **Cheap-for-quality beats hollow-overpriced in Korea** (+4.83%/6M, t4.17) — the standout L/S.
4. **Shorting fails in India** — momentum runs the short leg over (−1.0%). Long-only there.
5. **Most bear-regime signals fail multiple-testing** (Deflated Sharpe) — only 3 momentum factors survive.
6. **The edge is illiquidity, not size** — capacity ~$300–500k; Piotroski edge dead by $10M.
7. **US Piotroski F-score is inverted** (high-F underperforms) — a real, counterintuitive result.
8. **Data-sufficiency guard caught false outcomes** — JP/EU/CN "findings" were 9-observation artifacts;
   corrected to "insufficient data." (EU's headline +35.9% is the clearest trap.)
9. **India fundamentals hazard:** yfinance mixes quarterly-as-annual (4× EPS error) → use
   `IN_screener_only_backup`. India prices need `ohlcv_adj`.

---

## 5. Replicability of findings

| finding | replicability | why |
|---|---|---|
| IN valuation reversion | **HIGH** | two independent methods agree (sector- & market-relative) + 17 non-overlap obs + PIT-lagged |
| KR value+quality L/S | **MED-HIGH** | t4.17, DART 96% coverage; recent-window caveat |
| DSR-surviving momentum (IN/KR/EU bull) | **MED-HIGH** | passes multiple-testing correction, the anti-overfit gate |
| US reversion | **MEDIUM** | t2.32 at 3M but fades by 6M; coverage-thin on shares |
| Learned Lasso model | **MEDIUM** | null-tested for leakage; kept factors only where economically sensible; shadow mode |
| JP / EU / CN anything | **NOT YET** | underpowered — cannot replicate until deeper data lands |

**Guards in place:** point-in-time `filed`-date lags, winsorised ratios, non-overlapping t-stats,
Deflated Sharpe, null/leakage test, survivorship read-spreads-not-levels, and the sufficiency gate.

---

## 6. Choices incorporated into the watchlist (796 names)

- **Zone-first, per-market:** momentum zones for IN; mean-revert zones for US/KR/JP/EU (Buy/Hold/Sell).
- **Value-hold overlay:** cheap-for-quality names get a *hold* even when momentum is quiet (visible as
  `value-hold` status — IN 5, US 5, KR 5, EU-side).
- **Eviction/purge:** >5-session no-signal → evict; >15-session → purge. Trend-based, split semantics.
- **Learned model shadow-mode:** `rec_learned` recorded and compared, does **not** drive eviction/mailer
  until it beats the regime rule on forward paper-track data.
- **Pre-send validation:** ISIN prefix check (INE=equity) so no ETF ships as a stock pick.
- Current book: US 112 held + 102 signal; KR 110 signal; IN 135 watch + 59 signal; JP 52; EU 23.

---

## 7. Daily mailer (for the user)

- **ONE morning email** (brief + digest) via `send_mailer`, zone-first (Buy/Hold/Sell), smart-investing.in
  palette. `build_mailer.py` (brief) + `strategy_mailer.py` (strategy view) + `send_mailer.py` (transport).
- Sends **to the user only** (`umashankartd1991@gmail.com`).
- 🔴 **Open item:** the n8n 07:00 workflow is **deactivated** — reactivating it double-sends. Keep the
  local cron/launchd as the single sender until n8n is reconciled.

---

## 8. Call to action — the system's current signals (research, NOT advice)

> These are the pipeline's zone assignments on **validated markets only**. The user has stated no capital
> is deployed; this is watchlist validation against the live market. **Not investment advice — verify each
> name against screener.in / primary filings before any decision.**

| market | conviction | what the system says |
|---|---|---|
| **India** | ✅ highest | **BUY:** breakout + sector-relative-cheap names (reversion validated t2.5). Long-only. Learned model: 537 buy / 665 sell of 1,438. Top model picks: ASTRAZEN, KOTAKBANK, INDIAMART, HDFCLIFE. |
| **Korea** | ✅ high | **BUY** cheap∩high-ROE, **SELL/short** expensive∩low-ROE (L/S t4.17). 655 buy / 541 sell of 1,725. |
| **US** | 🟡 selective | **BUY** short-horizon cheap-vs-market (t2.32, ≤3M holds). Top model picks: PEG, AOS, RPM, HSY, PEP. Light sizing. |
| **Japan / Europe / China** | 🔴 no signal | **HOLD / no action** — data insufficient to issue a defensible buy or sell. Await deeper history. |

**Sizing discipline (from the risk overlay):** inverse-vol + vol-target + kill-switch; capacity ~$300–500k
before the illiquid edge decays; costs (Almgren-Chriss impact + borrow on shorts) must clear before acting.

---

## What's next (gated on data)

1. CN akshare collection completes → re-run `data_sufficiency.py`; if CN clears the bar, re-run reversion/clustering.
2. JP J-Quants deep pull → same gate.
3. Clean the 12 US future-dated FY rows (surfaced by the ledger).
4. `strategy_matrix.py` flip-detects any verdict that changes as data deepens — the keep-testing loop.

*Descriptive research pipeline. Not investment advice.*
