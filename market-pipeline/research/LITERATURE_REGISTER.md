# Literature Register

Running log of papers reviewed for market-pipeline technique extraction. One entry
per paper. Seeded 2026-08-22 from a 12-paper session sweep (5 agents, per-technique
file:line verification against the repo). Extended daily by the
`literature-review-daily` scheduled task — read-only, no repo edits, no backtests
run from this task; candidate backtests go to `BACKTEST_QUEUE.md` instead.

**Grading convention**: EVIDENCE-GRADE strong = risk-adjusted metric (Sharpe/return),
costs modelled or addressed, disclosed universe/period. weak = price-level MAPE/RMSE,
no costs, small/undisclosed universe, or self-contradicting result.

**Dedup rule**: check arXiv ID against every entry below before triaging a candidate.

---

## Strong evidence, high relevance

### 2605.19337 — Agentic Trading: When LLM Agents Meet Financial Markets
Audit of 77 LLM-trading studies; reproducibility checklist (only 2/19 primary
studies time-consistent, 0 reached R3). **Hub paper for citation-following.**
- Doing-right: survivorship reported not dropped, multiple-testing correction
  (deflated_sharpe.py), immutable forward log (signal_tracker.py) — repo reaches R3.
- Gap: no embargo/CPCV anywhere in the repo (`grep -rniE 'embargo|cpcv'` = 0 hits).
- Action taken: none yet. Queued: 21-day outcome embargo on signal_tracker.py.

### 2607.15414 — AI Trading: Evaluating LLMs for Technical Market Analysis
5-LLM eval; failure modes incl. sideways-regime degradation.
- Gap: `market_regime.py` computes 'chop' but scanner only demotes on 'bear'.
- Action queued: extend regime demotion to chop+HIGH-vol (build_mailer.py:434 already
  flags it as a warning; not yet a hard gate).

### 2602.00196 — Generative AI for Stock Selection (Rasekhschaffe)
AI-generated features decorrelated from traditional ones (corr 0.06-0.14), combine well.
- Gap: all 10 repo factors derive from ONE weekly close panel (factor_learning.py:37).
- Action queued: promote sentiment_pipeline.py (collected, unused as factor) or PEAD
  data into FACTORS.

### 1809.09441 — Temporal Relational Ranking for Stock Prediction (RSR)
Ranking beats regression/classification on same backbone (Table 5) — well evidenced.
Its relational-graph claim is weaker (Table 6: graph CUTS NASDAQ IRR 0.68->0.23).
- Gap: no learning-to-rank formulation anywhere in repo; scores are independent
  per-stock thresholds (Piotroski >=7, Darvas 0-7).
- Action queued: replace build_mailer.py:227 fixed pio>=7 gate with a within-market,
  within-week cross-sectional percentile cut.

### 2607.19005 — Observable Matrix Dynamics of Stocks (Halperin)
Spectral/correlation-matrix regime + effective-dimension method, S&P 500 crises.
- Gap: market_regime.py:76 is EMA-vs-index + vol percentile only — cannot distinguish
  a correlated crash from a dispersion unwind.
- Action queued: participation ratio of (a) the nightly correlation matrix
  (market_correlation_scan.py already builds it, discards it after writing files),
  and (b) the 10-factor correlation matrix — direct measurement of the redundancy gap.

### 2603.19286 — Generalized Stock Price Prediction w/ News Fusion
Proves relevance filtering must key on full company name, not ticker (US ticker
runs LOSE to a no-news baseline: MAE 0.2653 vs 0.1030).
- Doing-right: sentiment_pipeline.py:399-408 already reached this independently
  (ticker-matching demoted to guarded fallback).
- Gap: the per-ticker match is a hard GATE (drops non-matching articles, truncates
  [:15]) rather than a relevance SCORE; aggregation weights by provider, not relevance.
- Coverage caveat: free news exists for IN/US only.

### 2506.16746 — SSPT: Pre-training Time Series Models with Stock Data Customization
3 label-free pretext tasks (code/sector/moving-average classification) — needs no
data the repo doesn't already have (stock codes, sectors, prices).
- Feasibility check done: torch 2.13.0 installed, warehouse (7,955 US symbols,
  2016-2026) exceeds the paper's largest dataset. Repo taxonomy is 11-12 sectors vs
  paper's 112-129 (weaker pretext signal) — mitigable via `industry` column.
- Verdict: task-design idea transfers even without training the transformer;
  same free-label insight cashes in via Lasso.

---

## Weak evidence or narrow scope — logged, not actioned

- **2608.27076** (Le Grice, Tabular DL / XGBoost+TabNet, 2026-08-27; triaged 2026-10-02)
  — ~300 US large caps over 11 years. The headline is 51.26%/yr and Sharpe 2.44, and the
  abstract does not say whether costs were modelled. The return looks implausibly high for
  the setup. Not deep-read.
- **SSRN 7099378** (Ayan Jain, "Survivorship Bias in Indian Equities is not a Number",
  triaged 2026-10-02) — **not assessed.** SSRN returned HTTP 403 to both WebFetch and curl.
  Only a search-engine snippet was seen, which claims a bias range of +0.8 to +3.3pp/yr
  depending on vintage and filter. That has not been verified against the paper. Retry when
  the page is reachable, because it is directly on-theme for India.

- **1902.08684** (candlestick Word2Vec) — only paper of its batch that models costs
  and reports significance tests, but its own held-out result LOSES to buy-and-hold
  (Table 3/5). Repo already has both halves (Darvas boxes + KMeans clustering) at
  better quality. Verdict: not worth a build.
- **2305.14382** (Informer, 1-5min intraday) — does not transfer; repo has no
  intraday trading and its one real intraday module (intraday_monitor.py) is unwired.
- **2506.04658** (DRL: DDQN/PPO) — order-placing/shorting agent; doesn't map to a
  signal-only long-only pipeline. Non-transferable mechanism, transferable idea only
  (abstention-rate as a headline metric — see below).
- **1809.09441 companion papers** (GNN rolling-window, KG+LLM, Node Transformer+BERT)
  — see paper-G-relational.md; KG+LLM paper has NO quantitative evaluation at all,
  cite for schema only, never for evidence.
- **2509.12286** (Quantum GAN) — self-refuting: its own table shows QGAN RMSE 251.89
  vs classical GAN 84.27. Discard.
- **2505.05325** (LSTM+VADER) — MAPE 2.72 on 4 correlated tech stocks, no date range,
  no costs. Metric rewards lagging. Discard.
- **1909.12227** (autoencoder+CNN+LSTM) — no costs, no backtest, universe undisclosed.
  One durable line (predict rate-of-change not price level) — repo already does this.

---

- **2601.06090** (Nordic correlation regime shifts, Girnyk) — passes on rigor
  (two decades, eigenvalue-ratio crisis indicator, cleaned correlation matrix,
  min-variance overlay) but the universe is 3 *indices* (OMXS30/OMXC20/OMXH25),
  not a stock cross-section, and costs are unmentioned. The mechanism it uses
  (λ₁/λ₂ crisis indicator) is already captured by 2604.17251's spectral-gap
  feature — nothing additional to queue. Logged, not deep-read.
- **2601.08571** (Regime Discovery, EMD/Hilbert-Huang + variable-length Markov
  chains) — descriptive only: no Sharpe/return/IR, no MAPE/RMSE, no date range
  disclosed, no costs. Regime taxonomy (Normal/High/Extreme) adds nothing over
  `market_regime.py`'s existing bull/chop/bear × LOW/MID/HIGH. Discard.
- **2507.14325** (multiscale RMT eigenvalue distribution) — physics-side
  distributional modelling of the spectrum, no trading evaluation of any kind.
  Off-scope for technique extraction. Discard.

## Rejected adoptions (build-vs-borrow verdicts)

### arXiv:2412.20138 / github.com/TauricResearch/TradingAgents
**REJECT adoption.** Default fundamentals path is a live snapshot ignoring backtest
date (`y_finance.py:274-282`, stamped `datetime.now()`) — any historical run is
unfalsifiable. No transaction costs in its backtest (3 stocks, 62 trading days,
single seed). ~$1-5 per ticker-date in LLM API cost; replicating 20 daily finalists
across 5 markets ≈ $1,200/month to replace a mailer that costs zero. Borrowable idea
only: outcome-feedback loop, which score_signals.py already ~80% implements
deterministically (no LLM needed).

---

## Session log

- 2026-08-23 (daily): 8 candidates triaged (3 via citation-following from
  2605.19337, 5 via the Saturday correlation-spectrum query). 3 deep-read
  (2604.17251, 2608.09641, 2607.04958), 3 logged weak/narrow, 2 found but left
  untriaged for budget (2212.05504, 2511.21515). 3 queue items added (9-11).
- 2026-08-22: 12 papers processed (5 agents + 1 solo), ~95 techniques extracted,
  register seeded. Entry-bar look-ahead bug found (backtest_screeners.py,
  factorial_screener_test.py) and fixed; measured on 10.5y NSE (20,905 signals)
  and 5.1y US (14,646 signals) offline panels — bias real, short-horizon,
  ~-0.15 to -0.22pp (India) / -0.09 to -0.15pp (US), washes out by T+3mo.
- 2026-08-22/23: full historical stock-pick performance measured (23,900 merged
  entries, 4 sources incl. real Gmail draft/sent brief content — the send
  tool doesn't exist, only create_draft, so real briefs were recoverable as
  drafts). Overall median vs benchmark -2.74%, win rate 53%. Caught and fixed
  a benchmark-computation bug mid-analysis (panel-median fallback produced a
  fabricated +46.77% "vs bench" for India; replaced with a real NIFTYBEES+NIFTY50
  splice). Discovered signal_tracker.py --record has been silent 31+ days,
  wired into no cron/launchd job. Five scheduled tasks now running: brief-log
  audit, signal-tracker resume, Gmail brief parser, literature review, weekly
  performance monitor — all Mon-Sat/weekly, all read-only against the live
  pipeline except their own designated output files.
- 2026-08-23: BACKTEST_QUEUE items #1 and #3 executed (not just queued).
  Factor redundancy: participation ratio 4.92/10 (IN), 4.53/10 (US) — confirms
  the qualitative "factors are redundant" finding with a real number.
  Correlation-spectrum regime signal: validated against the independent,
  out-of-sample-to-this-repo COVID crash — 5 lowest-PR windows in 10.5y of
  NSE data are all Mar-May 2020, PC1 absorption 50-53% vs 14-15% calm.
  Logged only, not gated, per the "measure before wiring" discipline.

---

## Added 2026-08-23 (daily task)

### 2604.17251 — ORCA: Online Regime Correlation Analyzer (Kriuk & Kriuk, 2026-04-19)
Spectral graph theory + RMT + Random Forest to predict 10-day rallies/crashes.
24 exchange-traded instruments, 15y US daily (2009–2024), 127 spectral + 79
price features. **EVIDENCE-GRADE: strong** — Sharpe 1.13 / CAGR 15.6% vs 3.7%
buy-and-hold, max DD −7.5%, crisis-detection AUC 0.741, and it models costs
(5bps per unit of position change + 50bps/yr leverage) *inside* the grid-search
objective, not just the final table. 8-fold expanding walk-forward, 3y train /
6mo test, **10-trading-day anti-leakage gap** matched to the prediction horizon.
**CORRECTION 2026-08-23** (4-agent CPCV/embargo research round, primary source
re-fetched and confirmed): ORCA does NOT ablate this gap — it reports ONE
walk-forward result with the 10d gap already baked in, not a with/without
comparison. The gap-methodology description above is accurate; do not read it
as "ORCA showed the gap's effect empirically" — it didn't test that.
- Doing-right: repo already models cost in its walk-forward
  (`walk_forward_backtest.py:156`, 0.2% round-trip STT+brokerage).
- Gap 1 (spectral): the repo computes correlation matrices
  (`market_correlation_scan.py:168`, `:311`) but never decomposes them — the
  matrix is consumed only as thresholded graph edges (`:171-178`) / MST (`:312-313`)
  and then written to CSV. `grep -rniE 'eigen|effective_rank|absorption_ratio|marchenko'`
  over `code/python_files/` (excluding vendored `.venv`) returns exactly one hit,
  a *comment* at `market_correlation_scan.py:306`. This paper supplies the missing
  formulas: absorption ratio AR_k = Σ₁..ₖλᵢ/Σλᵢ (k∈{1,3,5}), eigenvalue entropy
  H = −Σλ̃ᵢlnλ̃ᵢ, effective rank ER = exp(H), spectral gap λ₁/λ₂, condition number
  λ₁/λₙ, Marchenko–Pastur excess λ₁−(1+√(n/T))², first-eigenvector HHI.
- Gap 2 (embargo): `walk_forward_backtest.py:173-181` splits 60/20/20 strictly
  chronologically with **zero gap** — `test_start` is the next trading day after
  train. Repo horizons run to 8 forward windows, so the overlap is real.
- Action queued: items 9 and 10 below.

### 2608.09641 — Lower Spectrum of Financial Correlation Matrices (Grassi, Pastorino, Uberti, 2026-08-10)
Argues the *smallest* eigenvalues carry the diversification-collapse signal, not
just the largest. Defines m⁻ = count of eigenvalues below the lower
Marchenko–Pastur bound (1−√(n/w))². Datasets: 10 S&P sector indices 1990–2020;
377 S&P constituents and 199 Nikkei 225 constituents, both 2005–2020.
Rolling window w=1000.
- **EVIDENCE-GRADE: medium.** Real disclosed universes and long periods, and the
  predictive test is risk-conditional (1% VaR and next-day return dispersion rise
  with m⁻) — but it is a risk-forecasting result, not a traded strategy, and no
  transaction costs appear. Graded medium, not strong, on that basis; it is
  nonetheless directly usable because the repo wants a *regime gate*, not a trade.
- Gap: same as above — no eigendecomposition exists to compute m⁻ from. It is one
  extra line on a matrix `market_correlation_scan.py` already builds and discards.
- Note: m⁻ is the mirror of ORCA's effective rank; computing both from one
  decomposition costs nothing extra, so they should be queued as a single change.
- Action queued: folded into item 9.

### 2607.04958 — Look-Ahead-Freedom as Temporal Non-Interference (Fonseca, 2026-07-06)
Found by citation-following from the hub paper 2605.19337. Reframes look-ahead
bias as temporal non-interference over a time-indexed information lattice.
Central practical construct: a **pipeline calculus separating a datum's
availability time from its reference time**. Proves the general problem
undecidable (Π⁰₁-hard) where availability depends on data values, but gives a
sound, linear-time-decidable type-and-effect system on the value-independent
fragment — which explicitly covers windowing, resampling, joins, point-in-time
and vintage reads. Their checker caught every planted leak that differential and
tiling detectors missed.
- **EVIDENCE-GRADE: n/a (not an empirical trading paper)** — graded instead on
  whether the mechanism transfers. It does, in reduced form.
- Doing-right: the repo independently hit this distinction — `pe_bands.py:82-93`
  uses an FYE+90d availability proxy rather than the reference date, which is
  exactly the availability-vs-reference split this paper formalises.
- Gap: that discipline is per-site folklore, not checkable. `grep -rniE
  'embargo|purge|cpcv'` over `code/python_files/` still returns 0 non-vendored
  hits, and no module annotates its columns with an as-of semantics.
- Not adopted wholesale: implementing the type system is out of scope for a
  one-person Mac pipeline. The transferable part is the annotation discipline.
- Action queued: item 11.

---

## CPCV / embargo — dedicated research round (2026-08-23)

User-requested deep dive on the one gap flagged as "purely theoretical, not yet
actioned" (item 6/10). 4 parallel agents: foundational algorithm, critiques/
failure-modes, empirical effect-sizes, implementation reality. Full synthesis
and the concrete action are in BACKTEST_QUEUE.md item 6 — this section is the
source ledger.

**Foundational** (AFML Ch.7 §7.4.1 p.105 / §7.4.2 p.107 / Ch.12, via
mlfinlab docs+source, reasonabledeviations.com, Towards AI): purging drops
training rows whose LABEL window overlaps a test label window. Embargo has no
single canonical formula — mlfinlab defaults to % of dataset; "embargo ≥
horizon" is a theoretically-argued convention, not a proven law. CPCV's real
contribution is a Sharpe *distribution* over C(N,k) paths for overfitting
detection, not leakage prevention (purge+embargo alone does that). Cost:
C(20,10) ≈ 184,756 splits.

**Critiques** (eslazarev/purged-cross-validation README — fetched and
confirmed; Arian/Norouzi M./Seco 2024 Knowledge-Based Systems — abstract-level
only, SSRN/ScienceDirect blocked 403): purge/embargo ≠ protection against
selection bias across strategy configurations — that needs deflated Sharpe,
which `deflated_sharpe.py` already implements here. No verified minimum-
sample-size threshold in the literature; reasoned (not sourced) inference that
CPCV's ~100+-path stability requirement is in tension with India's shorter
history (~2,500 trading days).

**Empirical** (eslazarev repo's own ablations — fetched; ORCA 2604.17251
primary source — fetched and confirmed, see correction above; Arian et al. —
abstract only): no clean equity-Sharpe before/after number exists in the
accessible literature. Real inflation numbers on synthetic/crypto/non-financial
targets: naive shuffled CV reports R²=0.83–0.99 on literally unpredictable
data; purged/walk-forward CV correctly collapses this below baseline. No
literature-validated embargo-to-horizon scaling formula found (ORCA uses 1×
horizon with no ablation; one weak secondary source claims 2×, unconfirmed
against AFML directly).

**Implementation** (GitHub/PyPI, fetched and independently re-verified this
session): mlfinlab is dead for reuse — closed-source, delisted from PyPI,
confirmed. `sklearn.model_selection.TimeSeriesSplit(gap=...)` is real
(confirmed against the installed sklearn 1.9.0 — `gap=0` default) but only a
fixed-index-count gap, not label-horizon-aware purging. Two alternative
libraries found and rejected: `timeseriescv` (stale since 2022-02, usable as
reference code only) and `purgedcv` (released the same day as this research,
zero track record). `walk_forward_backtest.py` independently confirmed to run
under Python 3.11 (not 3.9), so no version blocker either way. Recommendation:
hand-build, ~40–80 lines for purge+embargo, ~150–250 for full CPCV.

**Convergent verdict, reached independently by all four agents**: build a
minimal purge+embargo function now (embargo = 252 trading days, the repo's
longest evaluated horizon); pair it with the deflated Sharpe ratio already in
`deflated_sharpe.py`; do not build full CPCV as a first move — its documented
value is overfitting-distribution analysis, not leakage prevention, and its
combinatorial cost is unjustified before the simpler fix lands.

---

## Evidenced-screener backtest round (2026-08-23)

3-agent literature search (quality/value, momentum/technical, low-vol/size)
ranked candidates by evidence quality; all cited **McLean & Pontiff (2016,
JoF)** independently — 97 published predictors lose 26% return out-of-sample,
58% post-publication. Four candidates were built, tested, and backtested for
real: momentum 12-1 (Jegadeesh & Titman 1993), 52-week-high proximity (George
& Hwang 2004, both IN+US, OHLCV only), gross profitability (Novy-Marx 2013)
and accruals (Sloan 1996, both US-only — India's `total_assets` is 0%
populated in every fundamentals table checked, unreconstructable, a genuine
data gap not fillable from local sources).

**Two real bugs found and fixed during the build**, both worth remembering
for any future forward-return scorer in this repo:
1. A near-zero `assets_est` (units/reporting error in the source filing, e.g.
   OGS FY2013 computing gp_assets_pct = 8.13e10%) let data errors dominate a
   top-decile ranking — fixed with a disclosed plausibility filter (|value|
   <= 300%), not a silent drop.
2. **The "score as of today" convention itself is a confound**, not just a
   convenience: CETX (and 774 of 2,167 gross-profitability signals) had a
   next-available price bar YEARS after the signal date (a real gap in the
   price panel's per-symbol coverage), silently producing an arbitrarily
   delayed "entry" that bears no resemblance to the signal. A 30-calendar-day
   staleness guard fixed this. Even after the fix, "hold until today" gives
   each signal a wildly different holding period (recent signals held weeks,
   2016-era signals held a decade), which by itself produced implausible
   -94%/-117% "vs bench" medians — not from a bug, but from comparing an
   uneven-hold raw return against a benchmark that simply compounded over
   whatever window happened to elapse. **Fixed-horizon scoring (1mo/3mo/6mo/
   1yr from each signal's own entry) is the correct design and the one that
   should be reused for any future paper-motivated backtest in this repo** —
   `run_factor_backtests_fixed.py` is the reusable pattern.

**Final result, all four screens, real benchmarks (NIFTYBEES+NIFTY50 splice
IN, SPY US), entry-bar-correct, staleness- and split-guarded:**

| screen | market | n (1yr) | 1yr vs bench |
|---|---|---:|---:|
| Momentum 12-1 | IN | 3,541 | -14.11% |
| Momentum 12-1 | US | 17,606 | -15.08% |
| 52-week-high | IN | 4,387 | -2.50% |
| 52-week-high | US | 16,216 | -12.56% |
| Gross profitability | US | 1,214 | -14.29% |
| Accruals | US | 2,436 | -32.48% |

**Every screen underperforms the benchmark, and the gap widens at longer
horizons** — a consistent pattern, not noise. This is exactly what McLean &
Pontiff's decay finding predicts: none of these well-published, heavily-
publicized anomalies shows a live edge in this dataset today. 52-week-high in
India is the closest to neutral (~0% at 1mo-6mo, only drifting negative at
1yr) but still never positive. Combined with the debt-turnaround screen's
earlier -14.71% result, five separate paper-motivated screens have now been
tested with this repo's rigor and NONE has shown a real edge — a real,
disciplined finding in itself, not a failed exercise.

---

## Existing-screener + screener.in round (2026-08-23, same day continued)

Applied the SAME fixed-horizon methodology retroactively to this repo's OWN
production screeners, using their real detection code directly
(`backtest_screeners.detect_darvas_signals()`/`detect_golden_cross_signals()`,
unmodified, already entry-bar-fixed) plus 3 screens sourced from
https://www.screener.in/screens/ (user-provided URL, fetched 2026-08-23; 24
public screens found, several matching what was already covered): RSI
Oversold (<30) and a simple single-leg Debt Reduction (vs. the earlier 3-leg
debt-turnaround trajectory). New reusable module:
`run_existing_screeners_fixed.py` + Piotroski F-Score built fresh from
`public.global_fundamentals` (9-point, US-only, same total_assets gap as
gross_profitability/accruals; a missing input EXCLUDES that point from both
numerator and denominator rather than scoring it as failed — tested).

**Result, 1yr vs benchmark, real signals not extrapolated:**

| screen | market | n (1yr) | 1yr vs bench |
|---|---|---:|---:|
| **Darvas box breakout** | **IN** | **17,963** | **+1.41%** |
| Darvas box breakout | US | 16,267 | -1.87% |
| Golden Cross | IN/US | n/a | inconclusive — only 566 raw signals total, too rare for a mature 1yr sample within the 3y scan window |
| Piotroski F-Score >=7 | US | 1,211 | -9.12% |
| RSI Oversold (<30) | IN | 2,335 | -15.00% |
| RSI Oversold (<30) | US | 13,134 | -18.39% |
| Debt reduction (simple) | US | 5,862 | -9.35% |

**Darvas in India is the one real, sizeable edge found across the entire
2026-08-23 research round** — improving monotonically with horizon (-0.40%
at 1mo -> +1.41% at 1yr, win rate 54%->60%), on this repo's own production
detection logic, at genuine scale (17,963-20,505 signals per horizon). It
independently corroborates this repo's own pre-existing, separately-derived
finding at `code/python_files/CLAUDE.md`: "India | momentum/trend | trend +
sector-relative value, +5.3%/6M" -- a real cross-check, not circular, since
that finding predates tonight's work and used different methodology. Darvas
in the US shows no edge, consistent with the same doc's "US | mixed/light"
characterisation.

RSI Oversold's negative 1yr number should not be read as discrediting the
signal's actual (short-horizon, mean-reversion) thesis: India is near-neutral
at 3mo (+0.03% vs bench) and only degrades by 1yr -- holding a "buy the dip"
signal for a full year contradicts its own logic. If revisited, test it at
1-4 week horizons specifically, not 1yr.

**Combined tally, all screens tested 2026-08-23 with identical rigor: 13
market/screen combinations, 1 real positive edge (Darvas, India), 1
inconclusive (Golden Cross, small n), 11 negative.** The negative results are
not a failed session -- they are exactly what a disciplined test should
produce when most tested ideas are heavily-published, decay-prone anomalies
(McLean & Pontiff). The one positive result surviving this level of scrutiny,
and cross-checking against an independently-derived prior finding, is the
kind of signal worth acting on BECAUSE eleven other plausible ideas were
tested with equal rigor and did not survive.

---

## Regional/regime literature survey — buy/hold/sell rule variation (2026-08-23)

Sourced by a dedicated research agent to ground `backtest_zone_rules.py` and
`strategy_regime_survival.py`'s per-market, per-regime design against the
academic literature, following the mom126 bug fix + India significance
re-test the same day. Full source-by-source detail with credibility grading
kept in this session's transcript; key findings and grades below.

**Regional variation — why momentum/reversal strength differs by market:**
- Rouwenhorst (1998, JoF) — momentum present in 12 developed markets, not US-only. *Very high credibility.*
- Griffin, Ji & Martin (2003, JoF, 40 countries) — momentum profits don't co-move across countries; not a single global risk factor. *Very high.*
- Chui, Titman & Wei (2010, JoF, 41 markets) — momentum magnitude tracks Hofstede individualism (overconfidence proxy); explains why momentum is weak in Korea/Japan (low-individualism). *High, causal claim contested.*
- Hameed & Kusnadi (2002, J. Financial Research) — unrestricted momentum fails in 6 Asian markets incl. Korea. *High — direct Korea corroboration.*
- Balvers & Wu (2006, J. Empirical Finance) — [already in repo] momentum+mean-reversion coexist, OPTIMAL WEIGHT DIFFERS BY COUNTRY. *Very high — closest thing to a direct endorsement of this repo's whole per-market design.*
- India: JBF (2023), 3,956 BSE stocks 2000-2021 — momentum AND reversal both real, liquidity-conditional (momentum in liquid names, reversal in illiquid). *High.* Explains why this repo's India trend rule tests marginal (t<1.5): a uniform EMA rule averages two opposite-signed liquidity regimes.
- Korea: two papers (Investment Analysts Journal, 2024; Emerging Markets Finance & Trade, 2022) — individual-stock momentum REVERSES in Korea, explained by a "salience"/behavioral effect; foreign investors trade momentum, retail investors are contrarians. *Moderate-high — strongest literature match to any of this repo's own findings (Korea mom126 t=-2.13).*
- Japan: Asness (2011, JPM/AQR) — momentum Sharpe ~0.03 in Japan vs 0.22-0.48 elsewhere, argued to be within noise given momentum/value's negative correlation. *High but self-interested (AQR); later work on residual/industry-neutral momentum finds Japan momentum DOES work with better specification — treat "just noise" skeptically.*

**Regime-dependence — bull vs bear:**
- Cooper, Gutierrez & Hameed (2004, JoF) — US momentum profit is +0.93%/mo after up-markets, **-0.37%/mo after down-markets**; sign LITERALLY FLIPS by regime. *Very high — landmark result, directly explains why this repo's uniform trend rule "dies in bear markets everywhere."*
- Daniel & Moskowitz (2016, JFE) — "momentum crashes" cluster specifically at the bear-to-rebound TRANSITION (not throughout the bear), via short-leg option-like beta. *Very high.* Actionable: check whether this repo's regime-labeled data shows worst trend-following losses concentrated at that specific transition point, not spread through the bear regime.
- Asness et al. (2013, JoF) — value/momentum negatively correlated everywhere, linked to opposite-signed funding-liquidity exposure — mechanistically ties momentum failure to the same liquidity contractions that mark bear regimes. *Very high.*
- McLean & Pontiff (2016, JoF) — [already in repo] ~26-58% return decay post-discovery/publication. Caveat for ALL of this repo's backtested effect sizes, weighted least for Korea (mean-reversion) and India (liquidity-conditional momentum) since those anomalies are less likely to have been arbitraged by crowded global momentum capital than plain US/EU/JP momentum.

**Practitioner (lower weight, directional only):** Research Affiliates and AQR both run momentum+mean-reversion combined systematically, treating them as complementary horizons rather than competing rules — consistent with, not independent confirmation of, Balvers & Wu.

**Corroboration table — literature vs. this repo's own findings:**
| This repo's finding | Verdict |
|---|---|
| Korea: significantly negative momentum | STRONGLY CORROBORATED — best-supported match in the whole survey |
| US/JP/EU: regime-conditional (bull-momentum/bear-revert) | CORROBORATED as a general pattern (Cooper-Gutierrez-Hameed, Daniel-Moskowitz) |
| India: trend favored but not significant | PARTIALLY CORROBORATED — likely a liquidity-conditional specification issue, not "no edge"; a %ADV split is a concrete next refinement |
| India + Europe are the ONLY markets whose single rule survives both regimes | **NO literature match found — flag as a genuinely novel, unconfirmed result of this repo's own backtest, not literature-backed** |

**Uses**: the India-liquidity-split idea and the bear-regime-transition-timing check are both queued as candidate refinements, not yet built — see `BACKTEST_QUEUE.md` convention if picked up.

---

## Added 2026-08-24 (daily task, citation-following from hub 2605.19337)

### 2606.08285 — Beyond Agent Architecture: Execution Assumptions and Reproducibility in LLM-Based Trading Systems (Yao & Zheng, 2026-06-06)
Cites the hub paper (2605.19337); extends its reproducibility audit to a coded
evidence matrix over 30 LLM-trading studies specifically on execution realism:
point-in-time controls, temporal splits, execution timing, turnover treatment,
transaction costs, artifact release. Demonstrates via a 10-equity worked example
that undisclosed friction/timing choices materially compress active-strategy
results.
- Doing-right (all verified by grep, not assumed): transaction costs are modelled
  and disclosed — `walk_forward_backtest.py:156` (`TRANSACTION_COST = 0.002`,
  "0.2% round-trip (STT + brokerage)") and `backtest_screeners.py:176-177`
  (same rate, cited to JIER 2024). Point-in-time discipline is pervasive, not a
  single site — `backtest_ccc.py:134` (`pit_panel`), `backtest_liquidity_forward.py:78`
  ("PRECEDING-only frame => strictly point-in-time"), `backtest_piotroski_plus.py:40,106`,
  `backtest_pe_anomalies.py:157` (`pit_eps_panel`). Turnover is tracked as a tiering
  input (`adaptive_liquidity.py:236` `retier(..., turnover_col=...)`) and eviction
  rules bound rebalance frequency (>5-session eviction per the watchlist mailer).
- Gap: none material found. This repo is a signal-only EOD mailer (no execution
  layer), so "execution timing" (fill assumptions, latency) in the paper's sense
  doesn't apply — there is no order execution to misreport.
- Action queued: none. Logged as a doing-right confirmation from a second,
  independent audit (different authors, narrower lens than the hub paper),
  corroborating rather than adding to the hub's checklist.

### Weak/off-scope, one line each (triaged, not deep-read)
- **2607.19453** (Binance spot extrema audit, Jadouli) — real costs (31bps),
  real negative result (10-pair selector -6.72%/19 cycles, NO_TRADE conclusion),
  genuinely rigorous by this register's own bar — but crypto spot intraday timing
  models, and this pipeline trades neither crypto nor intraday. No transferable
  mechanism; logged for completeness of the citation-following sweep only.
- **2407.17645** (Hopfield Networks for Asset Allocation) — surfaced by an
  embargo/CPCV arXiv search (uses CPCV for validation) but abstract discloses no
  universe, date range, or cost treatment, and the mechanism (training a Hopfield
  network) needs an ML-training path this repo doesn't have. Not deep-read.

---

## Added 2026-08-25 (daily task, Tuesday gap query: factor redundancy / spanning tests)

Citation-following from hub 2605.19337 returned **no new candidates today** — the
Semantic Scholar citation list is unchanged at 3 papers (2607.19453, 2607.04958,
2606.08285), all three already in this register. The whole day's yield came from
the weekday gap query.

### 2601.10279 — Selecting and Testing Asset Pricing Models: A Stepwise Approach (Feng, Lan, Wang & Zhang, 2026-01-15)
Accepted at *Management Science*. Sequentially adds/removes factors from a baseline
(e.g. CAPM) to find the model spanning the joint efficient frontier of test assets
*and* all candidate factors, then tests performance on selected **and unselected**
factors — the unselected half is the part most selection procedures skip. Uses
asset-pricing duality (minimising unexplained pricing error ≡ maximising Sharpe) to
argue selection consistency. Standard factor models fail their test; the derived
8-factor model passes and holds up out-of-sample.
- **EVIDENCE-GRADE: medium.** Sharpe-based (not MAPE/RMSE), peer-reviewed at a top
  journal, and it reports out-of-sample results — but the abs page discloses neither
  the date range nor any transaction-cost treatment, so it does not clear the bar for
  "strong" as this register defines it. Graded on mechanism transfer, which is direct:
  the repo has a factor set and no formal test of whether its members are redundant.
- Gap (verified, not assumed): `grep -rniE 'spanning.test|stepwise|orthogonaliz|residualiz|variance_inflation' --include='*.py' code/python_files/ research/` returns
  **zero hits**. The repo's only factor-selection mechanism is L1 shrinkage —
  `factor_learning.py:88` (`LassoCV(cv=5, n_alphas=40, max_iter=5000)`), whose kept-set
  is read off `lcv.coef_` at `:89-90`. Lasso zeroing a coefficient is *not* a spanning
  test: it answers "does this factor improve the fitted combination" under one penalty
  path, not "is this factor's return spanned by the others", and it gives no t-stat.
- Complements, does not duplicate, queue item 1 (DONE): that item **counted** redundancy
  (participation ratio 4.92 of 10 IN / 4.53 of 10 US). A spanning test **names** which
  specific factors are the redundant ones and attaches a significance level.
- Action queued: item 12.

### 2111.05072 — The Evolving Causal Structure of Equity Risk Factors (D'Acunto, Bajardi, Bonchi & De Francisci Morales, 2021-11-09)
Causal structure learning over **11 US equity risk factors, 29 years, daily**. Two
findings that bear directly on this repo's own measured result: (a) the causal network
among factors **sparsifies over the long run**, and (b) that trend **reverses under
financial stress** — the network densifies, driven by the market factor, until
"exposure to different factors boils down to exposure to the market risk factor."
Argues causal structure beats plain correlation specifically during downturns.
- **EVIDENCE-GRADE: medium.** Long disclosed period, disclosed factor count, daily
  frequency, and the headline claim is tested for statistical significance — but it is
  a structural/descriptive study with no traded strategy, no Sharpe, and no costs.
  Usable here for exactly the reason 2608.09641 was: the repo wants a *regime
  descriptor*, not a trade.
- Gap (verified): the repo's factor-redundancy measurement is **static**.
  `research/factor_redundancy.py:65` takes one `df.corr()` over the entire pooled panel
  (263K/261K obs) and eigendecomposes that single matrix at `:42-52`. There is no
  rolling variant — `grep -rniE 'rolling' --include='*.py' research/` hits only
  `correlation_regime_spectrum.py:9`, which is the **stock** correlation matrix
  (150-symbol NSE universe, rolling 60d), not the factor matrix.
- Why this matters concretely: if the paper's densification result holds here, the
  "4.92 of 10" headline from queue item 1 is an *average over two structurally
  different regimes*, and the true calm-period figure is higher while the stress-period
  figure is materially lower — i.e. the factor set collapses toward one factor exactly
  when the mailer most needs diversification. That is a falsifiable prediction about
  data already on disk, testable with machinery that already exists.
- Cheap: the rolling-window code in `correlation_regime_spectrum.py` and the spectral
  stats in `factor_redundancy.py:42` already exist; this points the former at the
  latter's matrix. No new data, no new fetch, no training.
- Action queued: item 13.

### Incidental finding (not from a paper — found while grep-verifying the above)
`factor_learning.py:88` runs `LassoCV(cv=5, ...)` on the train split (`:84-85`,
60/40 chronological). `cv=5` is plain 5-fold KFold: sklearn will fit the penalty path
on folds that sit *after* the fold being scored, so α is tuned with future information
even though the outer 60/40 train/test boundary is chronologically clean. This is a
third concrete site for the purge+embargo function already specified in queue item 6,
and it was not previously named there. Queued as item 14.

### Weak/off-scope, one line each (triaged, not deep-read)
- **2606.19550** (Shin, "Which Portfolios? The Construction Dependence of Factor Model
  Performance") — real finding (model rankings flip with weighting/rebalancing choice;
  FF3 most stable under daily constant-weighting), but it evaluates FF3/FF5/FF6/q5 on
  characteristic-unsorted random CRSP portfolios, and this repo uses none of those
  models; no cost treatment disclosed. No transferable mechanism for a screener.
- **2606.23596** (Shin, "Anatomy of the Market: A Body-Tail Test of Factor Models") —
  same author, same limitation: an internal-consistency diagnostic for q5/FF3 (q5 shows
  offsetting body/tail leg alphas at daily frequency). Diagnoses academic factor models
  the repo does not run. Discard.
- **2603.29751** (Common Risk Factors in Decentralized AI Subnets) — surfaced by the
  spanning-test query and does report spanning alphas, but the universe is crypto AI
  subnets. Off-scope universe entirely.
- **2603.16365** (FactorEngine, LLM-based factor mining) — needs a per-query LLM API
  spend path; this register already rejected that cost profile once on
  arXiv:2412.20138 (TradingAgents, ~$1,200/mo to replace a zero-cost mailer). Discard.
- **2604.26747** (Constrained LLM Agents in Cryptocurrency Markets) — crypto, LLM-cost.
  Discard on both counts.
- **2405.07294** (Factor Strength Estimation in Vector and Matrix Time Series) —
  econometric estimation theory, no trading evaluation of any kind. Off-scope.

## Added 2026-08-26 (daily task, Wednesday gap query: learning-to-rank cross-sectional equity returns)

Citation-following from hub 2605.19337 again returned **no new candidates** — Semantic
Scholar still lists the same 3 citing papers (2607.19453, 2607.04958, 2606.08285), all
already registered. Third consecutive quiet day on that edge. Whole yield from the
weekday gap query. 1809.09441 (RSR) already covers the deep-learning-ranker branch of
this literature, so triage biased toward the *evaluation* and *data-hygiene* branches.

### 2507.07107 — Machine Learning Enhanced Multi-Factor Quantitative Trading: A Cross-Sectional Portfolio Optimization Approach with Bias Correction (Yimin Du, v1 2025-06-02, v2 2026-05-09)
Chinese A-share rolling-window factor pipeline. The paper's real contribution is not
the model — it is a named data-contamination mechanism. A-shares have price limits;
on a limit-locked day the printed close is a price **nobody could transact at**.
Standard pipelines compute factors over those closes and only filter for tradability
afterwards. Du calls this *upstream contamination* and quantifies it: it inflates the
information coefficient by **18%** while cutting realized Sharpe by **0.44**. The fix
is a "mask-first" design that threads the tradability constraint through every
operation rather than applying it at the end. Reports annualized Sharpe 2.05 synthetic
/ 1.63 real (deflated 0.978), 3,000-stock synthetic universe, 2022–2024 real backtest.
- **EVIDENCE-GRADE: medium.** Headline is Sharpe, not MAPE/RMSE, and it reports a
  *deflated* Sharpe — a rare and honest touch. Marked down because the real panel is
  proprietary A-share (unreproducible), the window is a short 2022–2024, and explicit
  transaction costs are not disclosed on the abs page. Graded mostly on mechanism
  transfer, which is direct: India runs ±5/10/20% circuit bands, so the exact hazard
  exists in this repo's largest market.
- Doing-right (verified): the repo is **already mask-first on liquidity**.
  `liquidity.py:5` states the design intent outright ("expensive strategy logic only
  runs on TRADABLE names"), the gate is `liquid_symbols()` at `liquidity.py:548`, and
  it is applied *before* scoring at `screener_kit.py:92-93` and
  `run_existing_screeners_fixed.py:66`. Turnover itself excludes untraded days —
  `liquidity.py:139` (`ok = ret.notna() & (dvol > 0) & dvol.notna()`), with the
  reasoning spelled out at `:128`. This is precisely the discipline Du argues for,
  arrived at independently.
- Doing-right (verified): the KR screener already implements the *stale-print* half.
  `factorial_screener_test_KR.py:119` `_flag_stale_halted_days()` exists because of a
  concrete find — `:128` records `Volume==0` stretches on `000300.KS` in a 200-symbol
  smoke test — and `:134` gives the exact rationale ("nobody could trade a Volume=0
  print").
- **Gap (verified, not assumed): that guard is KR-only.**
  `grep -rln '_flag_stale_halted_days' --include='*.py'` returns exactly one file,
  `factorial_screener_test_KR.py`. No India, US, EU or JP screener has an equivalent,
  and India is the one market with statutory daily price bands. Zero-volume handling is
  also inconsistent rather than absent: `cost_vs_edge.py:130`,
  `backtest_piotroski_plus.py:77` and `daily_breakout_combo_us.py:82` all filter
  `Volume > 0`, but `backtest_liquidity_forward.py:74` uses `Volume >= 0` and so admits
  untradable prints into a forward-return study.
- **Gap: no limit-locked-bar detection anywhere.** `grep -rniE 'circuit|price_limit'`
  over `--include='*.py'` returns only a portfolio drawdown kill-switch
  (`risk_management.py:5`), an unrelated retry helper (`iter_utils.py:48`), and prose in
  `quick_reference.py`. Nothing inspects a bar's range against a band.
- Action queued: item 15.

### 2605.00501 — LambdaRankIC: Directly Optimizing Rank IC for Financial Prediction (Yan Lin, Yihong Su, Yi Yang, 2026-05-01)
Argues the standard mismatch: models are *judged* on Rank IC (Spearman corr of
prediction with realized return) but *trained* on regression or NDCG-style losses that
do not align with it. Derives a closed-form lambda gradient for the pairwise rank swaps
so Rank IC can be optimized directly inside the LambdaRank framework, proves it
optimizes an upper bound on Rank IC, and ships it as a **custom XGBoost objective** —
i.e. CPU, no GPU. Out-of-sample it wins on Rank IC, ICIR, monthly return and Sharpe;
in simulation it beats regression and NDCG baselines specifically under low
signal-to-noise and heavy-tailed noise.
- **EVIDENCE-GRADE: medium.** Evaluated on finance metrics including Sharpe, not on
  MAPE/RMSE, and the low-SNR/heavy-tail simulation is the right stress test for equity
  returns. Marked down hard because the abs page discloses **neither the universe nor
  the date range** for the "real market data" experiments, and transaction costs are
  not mentioned at all.
- Doing-right (verified): the repo already evaluates by rank IC, and does it *better*
  than the paper's own summary statistic. `backtest_ccc.py:258` builds a per-month
  Spearman IC series; the comment at `:255-257` gives the reason for preferring
  full-cross-section IC over a quintile spread ("a quintile spread throws away the
  middle 60%"). `pead_liquidity_study.py:222,226` computes and reports rank IC with a
  t-stat. Crucially, `backtest_ccc.py:288-300` reports mean IC **with a
  non-overlap-corrected t-stat, independent-sample count and hit rate** — strictly
  more informative than the paper's ICIR, since ICIR ≈ t/√n and hides both n and the
  overlap correction. No action needed here; the register should not log this as a gap.
- **Gap, but NOT actionable at this scale.** The training half has no target: the repo
  has no learned cross-sectional ranker to re-fit — its scores are rule-based
  (Piotroski/Darvas/Coffee-Can composites), and the one learned component,
  `factor_learning.py:88`, is a `LassoCV` regression on factor returns, not a
  stock-level ranker. Adopting LambdaRankIC would mean *building* an ML ranker first,
  which is a different project from a rule-based EOD screener. Logged for the record;
  nothing queued.
- Action queued: none.

### Weak/off-scope, one line each (triaged, not deep-read)
- **2604.20204** (Li & Zhang, "ACT: Anti-Crosstalk Learning for Cross-Sectional Stock
  Ranking") — graph deep learning with a temporal-decomposition encoder on CSI300/CSI500;
  headline is a bare "up to 74.25% improvement" with no cost modelling and no disclosed
  date range, and it needs GPU training the pipeline does not have. Off-scope on compute
  and universe both; 1809.09441 already occupies this branch of the register.
- **2510.14156** (Kwiatkowski & Chudziak, "On Evaluating Loss Functions for Stock
  Ranking") — legitimate benchmark of pointwise/pairwise/listwise losses on S&P 500, and
  it is judged on ranking rather than MAPE/RMSE, but every finding is a *training-loss*
  choice and this repo trains no neural ranker. No transferable mechanism; abs page also
  discloses no date range and no cost treatment.
- **2503.09647** (Leveraging LLMs for Top-Down Sector Allocation) — surfaced by the
  ranking query but is an LLM-agent sector-allocation paper; per-query LLM spend profile
  this register has already rejected twice (2412.20138, 2603.16365). Discard.
- **"Building Cross-Sectional Systematic Strategies by Learning to Rank"** (Poh et al.,
  *Journal of Financial Data Science*, pm-research.com) — paywalled, no free preprint
  reachable from the search result, so it could not be verified against the
  no-fabrication rule. Not registered; note it as a possible re-check if an open version
  appears.

## Added 2026-08-27 (daily task, Thursday gap query: transaction-cost-aware factor evaluation)

Citation-following from hub 2605.19337 returned **no new candidates** for the fourth
consecutive day — Semantic Scholar still lists exactly 3 citing papers (2607.19453,
2607.04958, 2606.08285), all already registered. Entire day's yield from the weekday
gap query. Note for future runs: this edge has been dry since 2026-08-24; consider
demoting it to a weekly check rather than a daily one.

### Baldi-Lanfranchi (2024) — Transaction-cost-aware Factors (EPFL / Swiss Finance Institute, 17 May 2024)
Not on arXiv; fetched as PDF from afajof.org (AFA submission copy). Standard factors
are transaction-cost-*unaware* (TCU): they rebalance fully to the target weights each
period regardless of cost. TCA factors instead rebalance only *partially* toward the
target at an optimized trading intensity τ — a weighted average of last period's
allocation and the target factor. Trading intensity is factor-specific, driven by
characteristic persistence, characteristic/cost correlation, and risk-premium decay rate.
- **EVIDENCE-GRADE: medium-strong.** Headline metric is the net squared Sharpe ratio
  (Barillas–Shanken Sh² criterion), costs are the entire subject rather than an
  afterthought, and results are reported both in-sample and out-of-sample with
  factor-level spanning regressions. Marked down from strong because the pages fetched
  disclose neither the sample period nor the asset universe — that is a limit of what
  was read, not a claim the paper omits them.
- Numbers, verbatim from the fetched pages: net Sh² improves 28%–150% (abstract says
  "up to a factor of 2.5") switching TCU→TCA within a model. All 11 TCA factors produce
  positive net alphas on their TCU counterparts, 6 significant; TCU factors leave
  negative or insignificant intercepts on the TCA versions. Momentum is the worked case:
  gross premium 0.64%/mo (highest of the set), TCU trading costs 63bps/mo, net premium
  0.01%/mo — i.e. costs eat essentially all of it. TCA momentum incurs 30bps/mo,
  raising net return **22-fold** and annualized net Sharpe by 0.19. The Barillas–Shanken
  six-factor model has the highest gross Sh² (2.25) but its Sh² **drops 80% after costs**,
  ranking second-worst; TCA construction nearly doubles its net Sh².
- **Directly relevant to this repo's own result.** The 2026-08-23 round measured
  momentum 12-1 at **-14.11% vs bench (IN, n=3,541)** and **-15.08% (US, n=17,606)** and
  logged it as "no live edge." This paper is the specific claim that a chunk of
  momentum's net-of-cost failure is a *construction* artifact rather than an absent
  premium — TCU momentum is exactly the full-rebalance form the repo tested.
- Doing-right (verified): the repo does deduct costs rather than report gross —
  `walk_forward_backtest.py:156` (`TRANSACTION_COST = 0.002`, "0.2% round-trip
  (STT + brokerage)") and `backtest_screeners.py:176` (`TRANSACTION_COST_PCT = 0.002`),
  with net returns computed at `backtest_screeners.py:266`. Per-market round-trip bps
  are modelled separately at `confusion_matrix_eval.py:33`. So the repo is on the *net*
  side of the paper's four-way split, not the gross side it criticises.
- **Gap (verified): no trading-intensity or partial-rebalancing concept exists.**
  `grep -rniE 'trading_intensity|partial.rebal|rebalance_intensity|turnover_penalt|turnover.aware|cost.aware' --include='*.py'`
  over `code/python_files/` returns **zero non-vendored hits** (the only matches are
  inside `.venv/.../torch/fx/experimental/`). The repo's sole cost-mitigation mechanism
  is a *rebalancing-frequency* heuristic — the watchlist mailer's >5-session eviction /
  >15-session purge — which is precisely the alternative footnote 1 of this paper argues
  is dominated by intensity optimization, on the grounds that frequency reduction throws
  away higher-frequency characteristic changes while intensity optimization keeps the
  full information set and only damps the speed of adjustment.
- **Scope honesty: mostly NOT actionable as written.** TCA factors require a portfolio
  weight vector and an optimizer over τ. This repo is a signal-only, long-only EOD
  screener with no portfolio-construction or execution layer, so "implement TCA factors"
  is out of scope. What *is* in scope is the reduced form — measuring how much of the
  momentum screen's gross-to-net gap is churn rather than absent premium.
- Action queued: item 16 (scoped to the reduced form, not the full method).

### 2604.07880 — The Corporate Bond Factor Replication Crisis (Dickerson, Robotti & Rossetti, 2026-04-09)
Applies a bias-correction framework to a 108-signal "factor zoo" across nine thematic
clusters, Aug 2002 – Dec 2024 (269 months). Two named inflation sources: (i) a
**correlated errors-in-variables bias** — the same noisy transaction price enters both
the sorting signal and the return denominator, creating mechanical correlation; and
(ii) **asymmetric ex-post return filtering** — winsorization/filtering thresholds
computed from the *full sample* rather than from data available at portfolio formation.
- **EVIDENCE-GRADE: strong on method, medium on transfer.** Long disclosed period,
  disclosed universe, and — rare — a Benjamini-Hochberg FDR correction across all
  specifications rather than per-factor t-stats. Of 432 specifications, 119 had
  nominally significant premia (t>1.96); after correction only **26 (6.0%)** survive.
  Open-source artifacts released (Open Bond Asset Pricing, error-corrected TRACE).
  Downgraded on transfer only because the universe is corporate bonds — but both
  mechanisms are properties of *noisy prices*, not of bonds, so they carry to illiquid
  equities, which is where this repo's one validated edge lives.
- Quantified magnitudes: short-term reversal's premium falls from **−0.99% to −0.09%
  monthly** (>90% of the documented effect is bias). Value factors carry 36–45bps of
  bias, spread-based factors 15–18bps/month. The 6-month momentum premium of 0.30%/mo
  is **entirely** attributable to asymmetric ex-post winsorization — zero without it.
- **Doing-right #1, and it is the structural defence against mechanism (i):**
  `backtest_screeners.py:293` sets `entry_idx = signal_idx + 1` — entry is the close of
  the bar *after* the signal, with the signal-bar close preserved separately as
  `signal_price` (`:312-313`). The rationale is spelled out at `:275-285` (the 2026-08-22
  look-ahead fix). Because the sorting signal and the return denominator are drawn from
  **different bars**, the mechanical price-noise correlation the paper describes cannot
  form in this repo's screener backtests. This is a genuinely stronger position than the
  bond literature the paper indicts, and it was reached for a different stated reason
  (fill obtainability), which makes it a real independent convergence rather than luck.
- **Doing-right #2, against mechanism (ii):** `rloo_rescore.py:291` `winsorize_xs()`
  clips to **each day's own cross-section** — `np.nanpercentile(..., axis=1, keepdims=True)`
  at `:309-310` — and the docstring at `:301-303` records that it is applied identically
  to picks and peers so it "cannot move the advantage in a chosen direction." That is
  the point-in-time, symmetric form the paper says the bond literature failed to use.
- **Gap (verified): full-sample winsorization thresholds survive in three other places.**
  `factorial_screener_analysis.py:97-107` `winsorize()` takes `s.quantile(0.01), s.quantile(0.99)`
  over the **entire pooled series**, and it is still live at `:111`
  (`y = winsorize(df[horizon])`) feeding the OLS at the heart of the factorial screener
  analysis. Its own docstring at `:13-17` records that the primary split defence moved
  upstream into `factorial_screener_test.py` (exclusion, not winsorization), leaving this
  as "a light secondary guard" — but light or not, the thresholds are computed from data
  the formation date would not have had. Same pattern at
  `train_ppo_factor_weights.py:132-133` (`out["ret"].quantile([0.01, 0.99])` pooled, then
  `.clip()`), and `factor_zscore_panel.py:45-46` states outright that it adopts the
  "same convention as factorial_screener_analysis.py's winsorize()".
- **Precision caveat, stated so it is not overread later:** the repo's winsorization is
  *symmetric* (1st and 99th percentile both clipped), whereas the paper's fatal case is
  *asymmetric* filtering. The repo therefore has the milder member of the same family.
  The transferable hazard is the **full-sample threshold**, not the asymmetry, and the
  queued test should be read as measuring that and nothing more.
- Action queued: item 17.

### Weak/off-scope, one line each (triaged, not deep-read)
- **2602.00080** (Sheppert, "The GT-Score") — composite objective blending performance,
  significance, consistency and downside risk; but the headline metric is a
  "generalization ratio" (validation return / training return) on only **50 S&P 500
  names**, cost treatment undisclosed, and `deflated_sharpe.py` already gives this repo
  the multiple-testing half properly. Not deep-read.
- **2507.17211** (EFS: Evolutionary Factor Searching with LLMs) — does apply 0.1%/0.2%
  cost settings, but carries the per-query LLM spend profile this register has now
  rejected four times (2412.20138, 2603.16365, 2604.26747, 2503.09647). Discard.
- **2606.00060** (ML Bitcoin trading under transaction costs) — genuinely cost-aware and
  walk-forward, but crypto; same off-scope universe verdict as 2607.19453. Discard.
- **2603.21672** (Mislearning of Factor Risk Premia under Structural Breaks) — misspecified
  Bayesian learning framework; theoretical, no traded strategy and no cost treatment.
  Off-scope for technique extraction.
- **2601.10279** (Feng, Lan, Wang & Zhang) — resurfaced by today's query; **already
  registered 2026-08-25**, dedup hit, not re-triaged.

## Added 2026-08-28 (daily task, Friday gap query: point-in-time fundamentals / survivorship bias)

Citation-following from hub 2605.19337 returned **no new candidates for the fifth
consecutive day** — Semantic Scholar still lists exactly 3 citing papers (2607.19453,
2607.04958, 2606.08285), all already registered. **Acting on yesterday's note: this
edge should now be checked weekly (Mondays), not daily.** It has been dry since
2026-08-24 and costs a fetch every run for nothing.

**No paper was deep-read today and nothing was queued.** Three genuine search attempts
returned six candidates, every one of which fails triage — five of them because the
Friday query's 2026 literature on "point-in-time" has been almost entirely captured by
the LLM-benchmarking community, which is off-scope here for a reason worth recording
once (below) so future Friday runs stop re-triaging the same branch.

### Structural finding: the LLM look-ahead branch has zero surface area in this repo
The register has now rejected LLM-centric papers six times (2412.20138, 2603.16365,
2604.26747, 2503.09647, 2507.17211, and today's batch), but always on the **cost**
profile. Today's query surfaced a different sub-literature — *parametric* look-ahead
bias, i.e. an LLM trained after the fact already knowing how the period turned out
(2605.24564, 2601.13770). That hazard is not about cost at all, so it deserved a real
check rather than the standing cost rejection.
- **Verified, not assumed: there is no LLM anywhere in the signal path.** The only
  natural-language component is `sentiment_pipeline.py`, and it scores with VADER plus
  a hand-edited finance lexicon — `:66-67` instantiates `SentimentIntensityAnalyzer`,
  `:68-79` patches the lexicon, `:134` documents the scoring contract ("VADER with
  finance lexicon boost"). A fixed lexicon has no training corpus and therefore no
  future knowledge to leak. `grep -niE 'openai|anthropic|claude|gpt-|llm|llama'` over
  that file returns zero hits.
- The two learned components are fit on this repo's own panels (`factor_learning.py:88`
  LassoCV, `train_ppo_factor_weights.py`), so their leakage risk is the ordinary
  temporal-split kind already tracked as queue items 6/10/14 — not the parametric kind.
- **Verdict: not a gap, and not merely "too expensive" — structurally inapplicable.**
  Future runs should skip this branch on sight unless an LLM enters the signal path.

### Doing-right confirmation: survivorship (the other half of the Friday query)
Checked directly rather than trusted from the hub entry's one-line summary. The repo
does not merely disclose survivorship, it **bounds** it:
- `band_sip_backtest.py:20` — "DELISTING IS MODELLED, NOT DROPPED, AND IT DECIDES THE
  ANSWER", with 31.9% of the relevant names affected, and `:186` reports the SIP
  outcome under **both survivorship bounds** rather than picking one.
- `price_band_migration.py:23` — "SURVIVORSHIP IS REPORTED, NOT SILENTLY DROPPED."
- `backtest_liquidity_forward.py:172-175` — delisting-aware exit: a stock with no bar
  at t+63 exits at its last real close and is flagged `delisted_in_window`, rather than
  being inner-joined out of existence (`:43-45` gives the rationale).
- `sweep_piotroski_plus.py:40-45` — states the *residual* limitation honestly
  (screener.in serves listed companies only, so that particular route is an upper bound).
Nothing to queue: this is a stronger position than the papers surfaced today assume of
a personal pipeline.

### Weak/off-scope, one line each (triaged, not deep-read)
- **2601.13770** (Benhenda, "Look-Ahead-Bench: a Standardized Benchmark of Look-ahead
  Bias in Point-in-Time LLMs for Finance", 2026-01-20) — best-matched paper to today's
  query and it does release code (github.com/benstaf/lookaheadbench), but the abs page
  discloses neither universe nor date range, no cost treatment, and the hazard it
  measures cannot exist here per the VADER verification above. Not deep-read.
- **2605.24564** (Li, Wang & Ma, "Summoning the Oracle to Slay It", 2026-05-23) —
  proposes FinCAD, an inference-time Context-Aware Decoding fix for parametric
  look-ahead. Judged on returns/Sharpe/Spearman rather than MAPE, which is to its
  credit, but the universe is **five mega-cap equities**, costs are unmentioned, and
  the mechanism requires an LLM to decode from. Same inapplicability verdict.
- **2606.29771** (Qu & Chen, "CLQT", v1 2026-06-29 / v2 2026-08-02) — genuinely
  cost-aware (transaction *and* financing costs are a named pillar) and its diagnostic
  claim is real: the capability leader is not the Sharpe leader, because "the market
  path dominates a period's return." But it benchmarks **LLM portfolio-management
  agents**, and its transferable point — evaluate across distinct regimes rather than
  on one path — is already this repo's practice (`build_regimes.py`,
  `regime_tag_panel.py`, `strategy_regime_survival.py`, and the vs-benchmark reporting
  in the 2026-08-23 round). PDF fetch returned unparseable binary, so the universe,
  date range and cost figures could not be verified; graded on the abs page alone and
  **not** written up as though the full text had been read.
- **2605.30464** (Noguer i Alonso, "Distributional Portfolio Optimization", 2026-05-28)
  — surfaced for its point-in-time reconstitution record, but the abs page carries no
  detail on it, the backtest is K=25 DJIA, costs are unmentioned, and its own headline
  is a **negative** result (equal-weight, no-view Black-Litterman and Ledoit-Wolf
  shrinkage all beat every distributional method on Sharpe). Portfolio-construction
  scope this signal-only pipeline does not have. Discard.
- **2605.31201** (Point-in-Time Financial RAG with Frozen LLMs) — LLM retrieval
  architecture; same structural inapplicability, plus per-query spend. Discard.
- **2604.09060** ("Taming the Black Swan", momentum-gated hierarchical optimisation) —
  surfaced by the first query but off today's theme entirely; left untriaged for budget,
  not assessed. Noted here only so it is not counted as reviewed.

---

## Added 2026-08-29 (daily task, Saturday gap query: correlation-matrix eigenvalues / regime / effective dimension)

Note on dedup: the Saturday theme was already mined hard on 2026-08-23 (2604.17251 ORCA,
2608.09641 lower spectrum) with three weak entries (2601.06090, 2601.08571, 2507.14325).
Today's search returned those four again plus three genuinely new IDs. Only one passed.

### 2507.01918 — End-to-End Large Portfolio Optimization for Variance Minimization with Neural Networks through Covariance Cleaning (Bongiorno, Manolakis & Mantegna, v1 2025-07-02, v2 fetched)

Passed triage on evidence hygiene, which is the best in today's batch: out-of-sample
Jan-2000–Dec-2024, up to 1,000 US equities, headline metrics are Sharpe / realized
volatility / max drawdown (not MAPE), and the execution layer explicitly models market
orders at the auctions, empirical slippage, exchange fees and leverage financing.

**Doing-right:** the paper reports turnover next to variance — its own NN runs ~112%
turnover per 5 days at 2.9x gross leverage against QIS's 44% — i.e. it publishes the
number that would kill it net of cost rather than burying it. That is the standard this
repo's own estimator comparisons should meet.

**Gap (verified):** the repo builds its covariance matrices from the raw sample
estimator with no eigenvalue treatment at all. `portfolio_builder.py:217` is
`cov = R.cov().values * TRADING_DAYS`, fed straight into `port_var = lambda w: w @ cov @ w`
at `:222`; `mutual_fund_theorem.py:107` is the same line. Shrinkage in this repo is
applied only to *expected returns* — `_expected_returns()` at `portfolio_builder.py:190-200`
is James-Stein toward the cross-sectional mean — never to Σ. `mutual_fund_theorem.py:156`
already prints a warning naming the exact missing piece ("without shrinkage (Ledoit-Wolf)
or hard position constraints") when half-sample turnover exceeds 0.5, so the gap is one
the repo has already diagnosed on itself and not yet closed.

**Not adoptable:** the neural estimator itself. 240 independently trained BiLSTMs
(10 runs x 24 years, 100 epochs x 500 steps), and its edge over QIS is Sharpe 1.011 vs
0.942 frictionless — bought with 2.5x the turnover. No GPU here, and a long-only EOD
screener cannot pay that churn. The transferable content is the paper's *baseline table*,
not its model.

**Action queued:** item 18 — swap raw `R.cov()` for Ledoit-Wolf/QIS shrinkage at the two
sites above and measure, with turnover reported alongside realized volatility. The paper's
own "Average Oracle" baseline (eigenvalues estimated once on 1990–2000, frozen across the
whole 2000–2024 test window) reaches Sharpe 0.907 against QIS's 0.942 — within 4% at zero
re-estimation cost, which is the shape of thing this pipeline can actually run.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2608.26990** (DSA: Evidence-Aware LLM-Agent Orchestration for Multi-Market Stock
  Research, Zhu & Shi, 2026-08-27; surfaced by citation-following from hub 2605.19337) —
  architecturally the closest thing yet published to this repo (six regional market paths,
  fifteen bundled strategy skills), but the authors state plainly that their 1,457 passing
  contract tests establish "implementation conformance for the tested software contracts,
  not superior report quality, forecasting accuracy, or investment returns." No returns,
  no Sharpe, no date range, no costs. Zero evidence content by this register's bar; of
  interest as a design comparison only, never as a citation. Not deep-read.
- **2608.26128** (Gómez Morales, "Analysis of the Principal Components of Correlation
  Matrices of S&P 500 Financial Data from an Econophysics Perspective", 2026-06-23) —
  430 S&P 500 names, k-Means over the largest eigenvalue and dominant-eigenvector entries,
  transition matrices and inverse participation ratios. Self-described as "descriptive
  rather than predictive": no trading evaluation, no costs, no returns. Every mechanism it
  offers is already covered by 2604.17251's spectral descriptors and queue item 9. Discard.
- **1102.1339** ("Correlation of financial markets in times of crisis", 2011) — surfaced by
  the same query; pre-dates all three spectral papers already logged and adds no mechanism
  they lack. Not fetched, so nothing is asserted about its contents beyond the title;
  logged here only so it is not re-surfaced as unreviewed.

## Added 2026-08-31 (daily task, Monday gap query: CPCV / purging / embargo)

Dedup note: this theme already had a dedicated four-agent round on 2026-08-23 (see
"CPCV / embargo — dedicated research round"), so the query was re-aimed at the adjacent
question that round left open — *how do you grade a backtest after the purging is done*.
Citation-following from hub 2605.19337 returned exactly four citing papers
(2608.26990, 2607.19453, 2607.04958, 2606.08285), **all four already in the register**;
it produced no new candidates today. Both arXiv APIs (Semantic Scholar, export.arxiv.org)
returned HTTP 429 for the whole session, so search fell back to WebSearch + direct abs
fetches.

### 2608.23808 — Equity Strategy Backtesting: Luck or Edge? The MinervaScore as a Statistical Robustness Grade (Santoni, Jouanne & Scullin, v1 2026-08-24, v2 2026-08-26, q-fin.ST)

Passed triage on the strength of what it does with its own negative result. The paper
proposes a composite post-selection grade over five gates — Deflated Sharpe Ratio,
Probability of Backtest Overfitting, Superior Predictive Ability, Minimum Track Record
Length, and a regime-stability diagnostic — calibrated on 359,062 production backtest
records, and then reports that on pre-registered unseen real-market data the score
**showed no significant forward relationship** (Spearman rho_s = 0.013, one-sided
permutation p = 0.40). It also states that its improvement over a corrected DSR-alone
baseline is "modest".

**Doing-right:** it pre-registers the real-market test, publishes the null, and refuses
the obvious overclaim — the authors present the score "as an auditable validation and
reporting layer, rather than as evidence of demonstrated real-market predictability."
The AUROC 0.989 headline is explicitly confined to synthetic data with known ground truth.
That separation of synthetic-discrimination from real-market-prediction is the exact
discipline the weak entries in this register fail.

**Gap (verified, and the reason this entry exists):** of the five gates, this repo
implements one, mislabels a second, and has none of the other three.
- DSR — **real.** `deflated_sharpe.py:42` (`expected_max_sr`, López de Prado E[max SR])
  and `:52` (`dsr`, with skew/kurtosis denominator). Driven at `:61-93` over
  `reports/profitability_optimizer.csv` per market x regime, gate at DSR >= 0.95.
- PBO — **cited but not implemented.** `walk_forward_backtest.py:1086` carries the
  citation "Source: Bailey et al. (2014) — 'Probability of Backtest Overfitting.'", but
  the function it documents, `overfitting_report()` at `:1082`, computes
  `decay = (train - val)/abs(train)*100` from mean Sharpe per split (`:1094-1096`) and
  buckets it with hardcoded thresholds — HIGH >50%, MEDIUM >20% (`:1111-1116`). That is a
  Sharpe-decay heuristic. PBO is the CSCV quantity: the fraction of train/test partitions
  in which the in-sample-best configuration ranks below the out-of-sample median. The two
  are not the same statistic and the citation should not be attached to this function.
- SPA (Hansen), MTRL, regime-stability gate — **absent.** Grep over `*.py` for
  `superior predictive ability|minimum track record|min_trl|track_record|hansen` returns
  no implementation; the only `PBO`/`SPA` string hits are `cite_check.py:58` (an acronym
  allowlist) and `smallcap_screener.py:259` (an unrelated single-page-app error string).

**Second verified weakness, found while checking the above:** the trial count fed to the
DSR is the narrow one. `deflated_sharpe.py:70` builds `trials_sr` from only the rows of
`profitability_optimizer.csv` matching that market x regime — the generated report at
`:100` describes it as "best of 10 factors" — while `T` at `:77` is `best["n"]`, formation
weeks. Neither number accounts for configuration choices made elsewhere in the pipeline,
and nothing anywhere checks that `T` is large enough for the estimate to mean anything.
MinervaScore's opening sentence is precisely this failure: standard summaries "do not
record how many candidates were tried... or whether the available history is long enough
to support the result."

**Not adoptable:** the composite score itself. It is calibrated on 359k proprietary
backtest records this repo does not have, its component weights are fitted to that
population, and its own real-market test came back null — adopting the 0-100 display
would import a number with no demonstrated forward content. The transferable content is
the **gate list**, not the aggregation.

**Action queued:** items 19 (MTRL as a gate on the existing DSR verdicts) and 20 (replace
the mislabelled Sharpe-decay heuristic with real CSCV PBO, and fix the citation either way).

### 2512.12924 — Interpretable Hypothesis-Driven Trading: A Rigorous Walk-Forward Validation Framework for Market Microstructure Signals (Gagan Deep, Akash Deep & William Lamptey, 2025-12-15, q-fin.TR)

Passed triage as a **negative result worth keeping**, not as a technique source. 100 US
equities, 2015-2024 (2,475 days), walk-forward W=252 / H=63 / step=63 giving K=34 folds,
explicit cost model (`$1` fixed commission + 5 bps slippage, execution at next day's open).
Result: 140 trades, 0.55% annualized return, Sharpe 0.33, max drawdown -2.76%, beta 0.058,
aggregate p = 0.34, and 14 of 34 folds profitable.

**Doing-right:** publishes the null in the abstract, declines to dress it up, and states
that it reports all tests "without adjusting for multiple comparisons to maintain
transparency about statistical limitations" rather than quietly omitting the adjustment.
It also reports **fold-level profitability (41%)** next to aggregate Sharpe — a per-period
hit rate that survives a lucky single fold, which aggregate Sharpe does not.

**Relevance (verified):** four of the five hypothesis families it tests map directly onto
signals this repo already computes in `strategy_regime_survival.py:137-142` — `revert`
(mean reversion), `breakout`, `mom_st`/`mom126` (flow momentum), `trend`. The paper's
conclusion is that these patterns, derived from **daily OHLCV**, lack the information
arrival to pay: "daily OHLCV-based microstructure signals require elevated information
arrival and trading activity." This repo is a daily EOD OHLCV pipeline. The read-across is
direct, and the honest use of the paper is as a prior against expanding the
microstructure-signal family, not as a recipe.

**Its own weaknesses, stated plainly:** it computes no deflated Sharpe (it cites Bailey &
López de Prado in the literature review and then reports a raw Sharpe), applies no
multiple-testing correction across 5 hypothesis types x 100 securities, and its
walk-forward has **no purge or embargo gap** between the 252-day train and 63-day test
windows — the same omission already tracked here as queue item 6. So it is a useful null,
not a methodological exemplar.

**Action queued:** none. The actionable content is a do-not-build prior plus the
fold-level-profitability reporting habit, which is folded into item 20 rather than queued
separately.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2511.12490** (Mainak Singha, "Discovery of a 13-Sharpe OOS Factor: Drift Regimes
  Unlock Hidden Cross-Sectional Predictability", 2025-11-16) — EVIDENCE-GRADE: weak, and a
  near-perfect specimen of the disease 2608.23808 describes. Claims out-of-sample Sharpe
  "above 13" and 158.6% annualized at 12.0% volatility on S&P 500 names 2004-2024, with
  R-squared below 3% to standard risk factors. The abs page **does not disclose how many
  signal variants were searched** before this combination (value + short-term reversal,
  activated only when a stock shows >60% positive days in a trailing 63-day window) was
  selected — and a regime gate defined by a threshold on a trailing window is exactly the
  kind of parameter that gets tuned. The 1,000 randomization trials it does report test
  the sampling distribution of the chosen rule, not the selection process that produced it.
  A Sharpe of 13 on daily US equities is not a finding, it is a diagnostic. Not deep-read;
  logged here as the worked example for items 19-20.
- **2606.09025** (Zheli Xiong, "Continuous Cash-Overlay Filters for a Static
  Growth-Defensive Risk Sleeve", 2026-06-08, rev 2026-06-14) — 2 allocations (a risky ETF
  sleeve vs cash) over 2017-2026, headline 18.83% CAGR vs 16.62% buy-and-hold with max
  drawdown cut from -33.59% to -18.05%. No transaction-cost model stated. A single-sleeve
  tactical overlay on a 9-year window that contains one crash; the walk-forward label in
  the title does not offset a 2-asset universe. Off-scope for a cross-sectional screener.
- **2607.06117** (Zheli Xiong, "Relief-Gated Relative Rotation for QQQ-DIA Allocation",
  2026-07-07) — same author, same shape: **2 ETFs**, Sharpe 0.94 (2018 start) / 0.87
  (2022 start), and to its credit it does model 10 bps one-way cost — which is how you can
  see that it runs **354-506% annualized turnover**. Two instruments and a five-fold churn
  rate is not a result this pipeline can use. Off-scope.

---

## Added 2026-09-01 (daily task, Tuesday gap query: factor redundancy / spanning tests)

Citation-following from hub 2605.19337 returned the same four citing papers as the last
two runs (2608.26990, 2607.19453, 2607.04958, 2606.08285), **all already in the
register** — the hub's citation graph is exhausted for now. The Tuesday query was last
run 2026-08-25 (2601.10279, 2111.05072), so it was re-aimed from *which factor model
wins a spanning test* to *are my factors redundant through terms a correlation matrix
cannot see*. Five new candidates, two deep-read.

### 2503.23501 — Higher-Order Asset Pricing Factors via Forward Selection Fama-MacBeth Regression (Borri, Chetverikov, Liu & Tsyvinski, v1 2025-03-30, v2 2026-03-24)

EVIDENCE-GRADE: strong. 555 months (1973-10 to 2019-12), 484 characteristic-managed
portfolios, plus 148 zoo factors from Jensen, Kelly & Pedersen (2023) as the comparison
set. Metric is cross-sectional R-squared reported **both in- and out-of-sample**, not a
price-level error. No transaction-cost model, but it is an asset-pricing test rather than
a strategy backtest, so cost is not the load-bearing omission it would be for a signal.

Method: from 6 base factors (FF5 + momentum) build 57 candidates — 6 squares, 6 cubes,
15 pairwise products f_i·f_j, 30 mixed f_i·f_j². Forward-select by whichever candidate
most raises the Fama-MacBeth second-stage cross-sectional R², stopping when the next
addition buys less than 1 percentage point. Seven terms are selected (2 squares,
5 interactions). In-sample R² rises 31.2% → 58.7%; out-of-sample 8.9% → 14.8%. Only
**7 of 148 zoo factors stay significant at 5%** once the higher-order terms are in.

- Doing-right: nothing here yet — this is a clean gap.
- Gap (verified): the repo's redundancy diagnosis is **linear-only, on both sides**.
  `research/factor_redundancy.py:15-16` takes a *Pearson* correlation of the 10-factor
  matrix and eigendecomposes it, reporting participation ratio 4.92/10 (IN) and 4.53/10
  (US). The model that consumes those factors is equally linear: `factor_learning.py:43`
  `build_xy()` stacks the 10 raw `FACTORS` (`:37`) and nothing else, and `:88` fits
  `LassoCV` on that matrix. So a pair that is linearly near-orthogonal but related
  through a square or a product is invisible to the measurement *and* unavailable to the
  model — the same blind spot twice. `grep -rniE 'fama_macbeth|FamaMacBeth'` over the
  repo returns **zero implementations**; the only hit is a citation string in
  `paper_claim_audit.py:26`.
- Why it matters here specifically: the repo's 10 factors all come off ONE weekly close
  panel (`factor_learning.py:43` → `factor_library(close)`), which is exactly the
  condition under which the paper's result bites — a small base set whose apparent
  variety is higher-order structure, not new information. A PR of 4.92 measured
  linearly is an *upper* bound on independence, not a lower one.
- Action queued: item 21.

### 2602.20856 — Stochastic Discount Factors with Cross-Asset Spillovers (Avramov & He, 2026-02-24)

EVIDENCE-GRADE: mixed — excellent disclosure, unusable headline. Monthly CRSP
NYSE/AMEX/NASDAQ, 1963-01 to 2023-12, out-of-sample from 1973-02 on rolling 10-year
(120-month) windows, 138 firm-level signals across 13 themes from Jensen et al. (2023),
tested on 138 spread and 544 bivariate-sorted portfolios. Period, universe and window
are all stated — better than most of what this register sees.

Then the headline: annualised out-of-sample Sharpe **2.21** (spread) and **3.32**
(bivariate) versus 0.60 for self-predictive benchmarks, moderating to 1.58/2.21
post-2000. These are **gross**. The paper implements zero-cost leverage-two long-short
books rebalanced monthly and reports no turnover figure and no cost deduction anywhere.
A 3.32 Sharpe on monthly-rebalanced 544-portfolio long-short with costs unmeasured is
not a number this pipeline can borrow; the *method* is still worth taking.

Method worth taking: the estimation is not a neural net. It recasts max-Sharpe as a
managed-portfolio problem and solves it as a **ridge-penalised Britten-Jones (1999)
regression** — regress a vector of ones on the managed-portfolio return matrix, with λ
chosen by cross-validation — giving closed-form tangency weights.

- Gap (verified): the repo has no tangency/max-Sharpe factor combination at all.
  `grep -rniE 'ridge|tangency|britten'` finds ridge used only as a per-stock price
  ML engine (`full_us_market_scan.py:83`), and `fund_implementability.py:18` explicitly
  disclaims the tangency question. Factor weights come from `LassoCV`
  (`factor_learning.py:88`, an IR-agnostic MSE fit) and from PPO
  (`train_ppo_factor_weights.py`), with **no closed-form baseline between them**.
- Doing-right: the repo's own cost discipline is ahead of this paper's — queue item 16
  already treats net-of-cost churn as the question, which is precisely what a 3.32 gross
  Sharpe hides.
- Action queued: item 22 (the baseline, not the Sharpe claim).

### Weak/off-scope, one line each (triaged, not deep-read)

- **2604.04430** (Dickerson, Julliard & Mueller, "The Co-Pricing Factor Zoo",
  2026-04-06) — genuinely strong (Bayesian Model Averaging over "18 quadrillion models",
  out-of-sample Sharpe 1.5-1.8), but it prices **corporate bonds** jointly with stocks
  and needs Treasury term-structure controls and a BMA apparatus this pipeline has
  neither the data nor the reason to build. Same lead author as 2604.07880, already in
  the register. Off-scope, not weak.
- **2404.08129** (Borri, Chetverikov, Liu & Tsyvinski, "One Factor to Bind the
  Cross-Section of Returns", 2024-04-11) — the same team's precursor to 2503.23501: a
  non-linear single-factor model r_it = h(f_t·λ_i) + ε_it estimated by sieve, justified
  via Kolmogorov-Arnold. Only **171 assets** across mixed asset classes, and a
  nonparametric link function is a heavier lift than the forward-selection procedure for
  the same underlying insight. Logged as background to item 21; the successor is the
  actionable one.
- **2004.02670** (Arvanitis, Scaillet & Topaloglou, "Spanning analysis of stock market
  anomalies under Prospect Stochastic Dominance", 2020-04-06) — a subsampling +
  linear-programming test for whether anomalies expand the opportunity set *for
  prospect-theory investors*. The abs page discloses no universe, period or metric, and
  the prospect-utility framing does not map onto a screener that ranks on returns.
  Off-scope.

## Added 2026-09-03 (daily task, Thursday gap query: transaction-cost-aware factor evaluation)

Citation-following from hub 2605.19337 returned the **same four citing papers for the
fourth consecutive run** (2608.26990, 2607.19453, 2607.04958, 2606.08285), all already
in the register — the hub's citation graph remains exhausted. The Thursday query was
last run 2026-08-27 (Baldi-Lanfranchi, 2604.07880), so it was re-aimed from *do factor
premia survive their own trading costs* to *how do you report the cost sensitivity
itself* — i.e. breakeven cost as a first-class evaluation metric rather than a fixed
assumed charge. Six new candidates, one deep-read.

### 2603.01820 — Deep Learning for Financial Time Series: A Large-Scale Benchmark of Risk-Adjusted Performance (Saly-Kaufmann, Wood, Peter-Calliess & Zohren, 2026-03-02)

EVIDENCE-GRADE: strong on protocol, off-scope on models. Daily futures across five
asset classes (bonds, commodities, energy, FX, equity indices), 2010–2025, rolling
windows, fully out-of-sample. Headline metric is the **Sharpe ratio**, not a price-level
error — the benchmark is explicitly a position-sizing task, and the paper's own summary
notes that the models that top standard time-series benchmarks are *not* the ones that
top this one. The architectures themselves (xLSTM, PatchTST, VSN+LSTM, state-space
models) are out of scope here: they need GPU training of 50 independent runs per model,
which this pipeline neither has nor wants. The **evaluation apparatus** is the
transferable part.

Doing-right:
- **HAC t-statistics on Sharpe differences.** The paper tests significance with
  "heteroskedasticity and autocorrelation consistent t-statistics", Newey–West style.
  The repo already has exactly this: `newey_west_t()` at
  `code/python_files/rloo_rescore.py:385` ("t-stat of mean(x) with HAC (Bartlett)
  errors"), applied to per-date cohort series at `rloo_rescore.py:444-452` and
  documented in the emitted report at `rloo_rescore.py:514`. Not a gap.
- **Costs charged, not ignored.** Per-market cost assumptions exist at
  `confusion_matrix_eval.py:34` (`COST_BPS = {"IN": 40, "US": 15, "KR": 30, "JP": 25,
  "EU": 30, "CN": 35}`), deducted at `confusion_matrix_eval.py:80` and reported as a
  gross→net precision pair at `confusion_matrix_eval.py:132`. `sector_rotation.py:60`
  and `custom_indices.py:68` carry their own constants. Not a gap.
- **Seed robustness.** The paper re-runs at reduced budget (25 seeds, top 5) against its
  primary spec (50 runs, top 10 by validation loss) and checks rank stability. UNVERIFIED
  as a repo gap and deliberately not queued — the screener has no stochastic training
  loop for seeds to perturb, so the check has nothing to bite on.

Gap:
- **Breakeven cost is computed in one place, and it is not the product.** The paper
  defines it as "the maximum constant friction that specific asset's strategy can endure
  before its cumulative PnL is driven to zero", reported per asset in bps. The repo has
  a breakeven column only in `etf_builder.py:273` (header) / `:288` (the formula
  `be = edge / (tno * ppy) * 10_000 + COST_BPS`), and that variant answers a different
  and stricter question — the cost at which the scheme's *edge over the benchmark*
  vanishes, not at which its PnL vanishes. `quick_reference.py:18,293` is static
  documentation text, not a computation. `grep -rniE 'break[ _-]?even'` across
  `code/python_files/` finds nothing else. So the daily multi-market screen — the thing
  that actually emits the email — charges a fixed assumed cost per market and never
  inverts the question.

Action queued: item 23.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2603.14288** (Huang & Fan, "Beyond Prompting: An Autonomous Framework for Systematic
  Factor Investing via Agentic AI", v1 2026-03-15, v2 2026-04-06) — claims an annualized
  Sharpe of **3.11** and a **59.53% return** from long-short portfolios on
  LLM-self-generated signals, while the abs page discloses no universe size, no sample
  period and no transaction-cost treatment. A self-directed signal-search loop grading
  its own output on US equities is a data-snooping engine; the abstract's answer to that
  is an assertion of "strict empirical discipline" with no reported turnover. This is the
  implausible-headline pattern the triage rule exists to catch. Weak.
- **2511.17462** (Engel, Chen, Polak & Boier, "Scaling Conditional Autoencoders for
  Portfolio Optimization via Uncertainty-Aware Factor Selection", 2025-11-21) — the idea
  is good (rank latent factors by forecast uncertainty, keep the top-k most predictable)
  and the metrics are risk-adjusted (Sharpe, Sortino, Omega), but it requires training a
  high-dimensional conditional autoencoder on a firm-characteristic panel plus Chronos /
  XGBoost-RAPIDS quantile models, and the abstract reports no universe, no period and no
  cost model. Off-scope at this pipeline's scale, not weak on method.
- **2510.19271** (Barunik, Janasek & Sarkany, "Managing Portfolios Across the Return
  Distribution", v1 2025-10-22, v2 2026-06-23) — dynamic allocation targeting a chosen
  region of the payoff distribution; the downside-targeted policy is reported as giving
  both the best left-tail protection and the highest Sharpe. No cost treatment, universe
  or period on the abs page, and the repo's screener ranks candidates rather than running
  a dynamic allocation policy, so there is nothing here to attach it to. Off-scope.
- **2603.15652** and **2512.12420** — surfaced by the Thursday search and **not triaged**;
  the day's triage budget went to the four above. Neither has been fetched, so nothing is
  claimed about either. Left for a future Thursday.

---

## Added 2026-09-04 (daily task, Friday gap query: point-in-time fundamentals / survivorship bias)

Citation-following from hub 2605.19337 returned the same four citing papers for the
**fifth consecutive run** (2608.26990, 2607.19453, 2607.04958, 2606.08285), all already
in the register. Two web searches returned five new IDs; one passed triage and was
deep-read.

### 2608.27734 — What survives honest evaluation? Leakage-safe, search-aware assessment of LLM-driven trading strategy discovery (Eray Gençay, v1 2026-08-27, q-fin.ST)

**Why this one is not covered by the standing LLM rejection.** The 2026-08-28 structural
finding rejects LLM papers because no LLM sits in this repo's *signal path*. This paper's
contribution is not a signal — it is the **evaluation harness placed around a search**,
and this repo does run a search: `profitability_optimizer.csv` picks the best of 10
factors per market×regime, and a dozen `sweep_*` / `backtest_*` scripts have each tried
their own configurations. The LLM is only what generates candidates in the paper; the
grading machinery is agnostic to what produced them. Triaged on that basis, not on the
LLM framing.

Passes triage on every count: headline metric is **Sharpe with Deflated Sharpe and PBO**
(not MAPE/RMSE), universe is **453 US equities plus 39 multi-asset ETFs** (ETFs
2005–2026), design window 2017–2021 / evaluation 2022–2025 for E1–E4 and 2007–2016 /
2017–2025 for E5–E6b, and costs are modelled explicitly: **1bp commission, 2bp spread,
square-root market impact against trailing 21-day dollar volume, and 50bp annualised
borrow on short notional**.

Headline result, and it is a negative one honestly reported: **zero LLM-discovered
strategies survived**. In E3 (100-candidate search, N=102 trials) the agent's best posted
a design Sharpe of 1.69 that collapsed to an evaluation Sharpe of **0.18**, DSR 0.86 —
below the 0.95 certification threshold. The passive benchmarks certify instead:
equal-weight buy-and-hold **DSR 0.97**, SPY **DSR 0.94**. This is worth recording because
it converts this register's six prior LLM rejections — all made on *cost* grounds — into
a *statistical* one made by someone who actually ran the experiment.

- **Doing-right:** point-in-time liquidity. The paper re-selects its tradeable set
  point-in-time and the repo does the equivalent: `backtest_liquidity_forward.py:40`
  states the discipline ("Liquidity, DMA50 and DMA200 at date t use bars <= t only.
  Enforced by SQL"), `:64` sets `LIQ_WINDOW = 60`, `:83` computes the rolling turnover
  window, and `:172-175` exits a delisted name at its last real close rather than
  inner-joining it out. The paper's own survivorship handling is *weaker* than this —
  it fixes the constituent list to current names and argues the resulting bias only
  makes its null conservative.
- **Doing-right:** the cost model. The paper's square-root-impact-plus-participation-cap
  design already exists here — `execution_cost_model.py:8` describes exactly a
  "square-root market-impact model and a participation-rate (%ADV) cap", and
  `build_business_valuation_report.py:285` reports it in use with a 15%-ADV cap. The flat
  per-market constants at `confusion_matrix_eval.py:34` are the weaker path and are
  already queue item 23. Borrow cost on short notional is a real gap but a known one —
  `project_retrospective.py:122` already flags the un-netted short leg — so nothing new
  is queued for it.
- **Doing-right (already queued, not re-queued):** PBO. The paper runs CSCV over 16
  blocks. `walk_forward_backtest.py:1086` cites Bailey's PBO on a function (`:1082`) that
  computes train→val Sharpe decay, which is a different statistic. That mismatch is
  already **queue item 20** and is not duplicated here.
- **Gap — the trial count N is scoped to one sweep, not to the search.** This is the new
  finding. `deflated_sharpe.py:42-49` implements E[max SR] correctly and `:52-58` the DSR,
  but `:71-74` builds `trial_srs` from a single `market × regime` slice of
  `profitability_optimizer.csv`, so `n_trials` written at `:82` is 10 — the factors in
  that one comparison. The paper's N comes from a **persistent ledger of every evaluation
  the search ever performed** (N=102 in E3, against 100 candidates). Every additional
  configuration this repo has tried against the same markets — `sweep_piotroski_plus.py`,
  `backtest_zone_rules.py`, `backtest_pe_anomalies.py`, `backtest_tier_anomalies.py` —
  is a trial that should raise the bar the winner has to clear, and currently does not.
  Since E[max SR] grows with N, the present DSR figures are an **upper bound on
  significance**, not a neutral estimate.
- **Considered and declined:** making look-ahead inexpressible. The paper's neatest idea
  is architectural — a feature registry whose leaky family is excluded from the
  agent-selectable set, with the tool schema and server-side validation deriving from the
  same flag, so invalid constructs never reach evaluation rather than being discouraged.
  That is a control for an agent tool-server with an untrusted caller. Here the caller is
  one person and the discipline is per-script and documented (`backtest_liquidity_forward.py:40`).
  Not queued: the machinery costs more than the failure mode it removes at this scale.
- **Action queued:** item 24 (widen the DSR trial count to a persistent cross-sweep ledger).

### Weak/off-scope, one line each (triaged, not deep-read)
- **2604.09060** (Chakraborty & Singh, "Taming the Black Swan", v1 2026-04-10 / v2
  2026-05-18, cs.CE) — carried forward from 2026-08-28 where it was left explicitly
  untriaged; **now triaged and closed**. AEGIS is Sortino-optimised portfolio
  *allocation* (volatility-adjusted momentum filter + minimax correlation + SLSQP) over a
  2006–2025 walk-forward, but the abs page discloses no universe size, no cost treatment
  and no code or data release, and portfolio construction is scope this signal-only
  pipeline does not have. Discard; future Friday runs need not carry it again.
- **2604.18500** (QRAFTI: An Agentic Framework for Empirical Research in Quantitative
  Finance) — its only on-theme content is preprocessing (delisting returns, share-class
  aggregation, universe screens) sitting downstream of an LLM agent harness. Structurally
  inapplicable per the 2026-08-28 finding. Not deep-read.
- **2602.14233** ("Evaluating LLMs in Finance Requires Explicit Bias Consideration") —
  about bias in grading LLMs, with no signal-path surface here. Discard.
- **2601.07687** (Physics-Informed Singular-Value Learning for Cross-Covariances
  Forecasting) — belongs to the Saturday covariance-cleaning branch already mined on
  2026-08-29 via 2507.01918, not the Friday theme. **Not fetched and not assessed**;
  noted only so it is not counted as reviewed.

---

## Added 2026-09-07 (daily task, Monday gap query: CPCV / purging / embargo)

Dedup note: this is the third Monday pass on the purging/embargo theme (2026-08-23 round,
2026-08-31 grading-after-purging angle), so the query was re-aimed a third time — at
*which* leakage conventions actually cost you anything, rather than at how to purge or how
to grade. Citation-following from hub 2605.19337 returned exactly the same four citing
papers for the **sixth consecutive run** (2608.26990, 2607.19453, 2607.04958, 2606.08285),
all already registered. That branch is dry and should be considered exhausted until the
hub accrues new citations; future Monday runs can skip straight to the web query.

### 2605.23959 — When Alpha Disappears: A One-Switch Benchmark for Decision-Time Leakage in Financial Backtests (Fan Zhang, Zhen Li, Sijia Peng & Yu Chen, 2026-05-12, q-fin.RM)

Passed triage on data shape as much as on rigour: two **daily-OHLCV equity panels** —
S&P 500 constituents, 2010–2024, 439 retained tickers, and CSI 300, 186 tickers — six
model families, yearly tests 2016–2024, proportional costs at 0/5/10 bps with 5 bps as the
headline. That is this repo's exact data regime, which is rare in the leakage literature.

The design is the contribution: rather than declaring a backtest "leaky" or "clean", it
holds the data panel, walk-forward split, model family, horizon, portfolio rule and cost
convention fixed and **toggles one evaluation convention at a time** against a clean
`t+1`-open reference (features from information available by the close of day t, execution
at the t+1 open, labels as open-to-open returns). What comes out is a *ranking of how much
each convention inflates Sharpe*, which is far more useful than a binary verdict.

**The measured result — leakage is highly selective:**

| Convention | Effect | Magnitude |
|---|---|---|
| `TEMP_CENTER` — centered rather than trailing rolling statistics, so a day-t feature can depend on t+3 | **large** | ~+19 to +27 Sharpe (Ridge h=5: +19.43 US, +21.70 China) |
| `EXEC_OPEN` — signal built from the full day-t bar (post-open high/low/close/volume) but executed at the day-t **open** | **large** | ~+5 to +26 Sharpe (Ridge h=5: +21.65 US, +26.16 China) |
| `STRUCT_GRAPH` — symmetric 252-day correlation graphs centered on monthly anchors | weak | mean ~+0.10 Sharpe |
| `NORM_GLOBAL` — normalisation fitted on the full sample instead of the training split | weak | ~+0.07–0.09 Sharpe |
| `EXEC_CLOSE` — close-of-day signal paired with same-day close execution | weak | ~+0.06 Sharpe (US panel) |

**Doing-right:** it states plainly that the benchmark "is diagnostic rather than a claim of
tradable alpha", and the clean-reference Sharpes it reports are modest and believable
(Ridge h=5: 0.68 US, 0.84 China) — a paper that publishes a 0.68 baseline and then shows
its own violations manufacturing a 20-Sharpe strategy is demonstrating the failure mode
rather than selling a result.

**Verified against this repo (greps run today, not carried from prior entries):**

- **`TEMP_CENTER` — clean, confirmed.** `grep -rn "center *= *True" --include='*.py'` over
  `code/python_files/` returns hits **only** inside `.venv/` (networkx, torch, sklearn,
  patsy, polars library source). No pipeline code constructs a centered rolling statistic.
  This is the single largest inflation channel the paper measures and the repo does not
  touch it.
- **`EXEC_OPEN` — structurally impossible here, confirmed.** `grep -n '"Open"'` over
  `backtest_screeners.py`, `walk_forward_backtest.py`, `rloo_rescore.py` and
  `backtest_zone_rules.py` returns **zero hits**. The backtest paths read `Close`,
  `High`, `Low` and `Volume` and never reference the open at all, so the +5 to +26 Sharpe
  channel has no surface area. Worth recording explicitly: an "Open-aware execution model"
  would look like an upgrade and is in fact the entry point to the worst bug in the paper.
- **`NORM_GLOBAL` — clean in the signal path, confirmed.** `StandardScaler().fit_transform`
  on a full sample appears at `cluster_extra_markets.py:61`, `valuation_clustering.py:52`,
  `sector_analysis.py:216` and `pattern_discovery.py:251` — all four are descriptive
  clustering / PCA reporting, not return-generating. In the one place it would matter,
  `ml_signal_engine.py`, `StandardScaler` is **imported at :76 and never instantiated**
  (`grep -n "StandardScaler\|scaler\|\.fit(" ml_signal_engine.py` shows only the import,
  a comment at `:218`, and three bare `model.fit(...)` calls at `:319`, `:441`, `:518`).
  That engine retrains on a rolling `TRAIN_WINDOW = 252` (`:98`) and its one normalised
  feature, `close_norm`, is documented at `:135` as "Z-score normalized close vs 20-day
  window" — trailing, not global.
- **`EXEC_CLOSE` — this is what the repo does, and the paper prices it.** The convention is
  documented in the docstring at `backtest_screeners.py:270` ("Entry = signal bar close.
  Exit = close at T+N") and stamped at `:402` (`"entry_price": curr_close`, where
  `curr_close = closes[i]` at `:385`) and `:439` (`float(closes.iloc[i])`), with the same
  shape in `walk_forward_backtest.py:1362`. The signal and the fill are the **same bar's
  close**. Under the paper's measurement that is the mildest of the five violations,
  ~+0.06 Sharpe on the US panel — but it is one-directional and it is optimistic.

**Gap (the one that survives):** the repo's whole backtest estate assumes it can trade the
close it has just observed. Nothing in the codebase has ever measured what a one-bar delay
costs, and the volume-confirmation branch at `backtest_screeners.py:397` makes the
assumption slightly sharper than it looks — it compares `vols[i]`, the completed day-t
volume, against the trailing 20-day mean, so the decision genuinely needs the full bar,
which is exactly the information set the paper pairs with a t+1 fill rather than a t fill.

**Not adoptable:** the benchmark harness itself. Reproducing a one-switch panel means six
model families × two panels × five toggles × nine yearly tests, and this repo trains no
cross-sectional model that would sit in it. The transferable content is the **ranking**,
which converts "we should probably worry about leakage" into a priced list.

**Action queued:** item 25 (one-bar execution delay as a reported variant, not a
replacement).

### Weak/off-scope, one line each (triaged, not deep-read)

- **2603.13252** (Ursina Sanderink, "When Alpha Breaks: Two-Level Uncertainty for Safe
  Deployment of Cross-Sectional Stock Rankers", 2026-02-24, cs.AI) — EVIDENCE-GRADE: weak,
  and a near miss. Its validation design is the best thing about it and is genuinely on
  today's theme: 109 chronological walk-forward folds, Feb 2016–Feb 2025, a **90-trading-day
  embargo** between training and prediction, and overlapping labels purged — stricter than
  anything in this repo. But the headline metric is **AUROC** (~0.72 overall, ~0.75 in the
  2024 holdout), the abs page discloses **no universe size**, and **no transaction cost
  treatment** appears anywhere, so the paper never converts its ranking quality into
  anything a screener can bank. A DEUP-based epistemic tail-risk cap that the authors
  themselves downgrade to "a tail-risk guard rather than a continuous sizing denominator"
  is not worth deep-read budget against those disclosure gaps. Logged rather than
  discarded: if a v2 adds a universe and a cost model, the 90-day embargo design is worth
  revisiting.
- **2609.00731** (Pan, Ding & Giesecke, "Agentic Empirical Asset Pricing: Methodological
  Foundations", 2026-09-01, cs.AI) — LLM agents doing autonomous factor discovery on two US
  equity panels; no cost treatment stated and no date range on the abs page. Its one
  transferable observation — "no single metric ranks the systems consistently", hence
  multi-axis evaluation — is already the operating assumption behind queue items 19, 20 and
  24. Structurally inapplicable per the standing 2026-08-28 finding that this repo has no
  LLM agent surface. Not deep-read.
- **2602.00080** (GT-Score) — surfaced again by today's search (4-year train / 2-year
  validation / 30-day embargo). **Already in the register**; not re-triaged, listed only so
  the day's candidate count is honest.
- **q-fin.ST recent listing** (2609.04420, 2609.02660, 2608.29692, 2608.29669, 2608.29025,
  2608.30446) — skimmed as a block; none concerns backtest validation, leakage or
  evaluation methodology. Rare-event onset forecasting, forex trade durations, two
  language-model-representation covariance papers, Bitcoin option deep hedging, and neural
  correlation-matrix shrinkage. No candidates.

## Added 2026-09-08 (daily task, Tuesday gap query: factor redundancy / spanning tests)

Third Tuesday pass on this theme (2026-08-25 asked *which factor model wins a spanning
test*, 2026-09-01 asked *are my factors redundant through terms a correlation matrix
cannot see*), so it was re-aimed again — at **whether the repo's existing redundancy
verdict is inferentially valid at all**, rather than at finding more factors.
Citation-following from hub 2605.19337 returned a **new** citing paper for the first time
in seven runs (2609.04917, alongside the same four already-registered ones), so that
branch is no longer dry, only slow. Four new candidates, two deep-read.

### 2601.06499 — Cross-Market Alpha: Testing Short-Term Trading Factors in the U.S. Market via Double-Selection LASSO (Jin Du, Alexander Walter & Maxim Ulrich, v1 2026-01-10, v2 2026-05-21)

EVIDENCE-GRADE: moderate-to-strong on design, weak on costs. S&P 500 large caps,
2002–2022, monthly rebalancing — a real, disclosed, twenty-year universe. A library of
191 short-term price-volume and microstructure signals (built for the retail-heavy
Chinese A-share market) is tested against a control set of **151 fundamental factors**;
17 survive as non-redundant risk premia. The abs page does not state a transaction-cost
treatment, which for *short-term* signals is the disclosure that matters most, so the
17-signal headline should be read as gross. The transferable content is the method, not
the count.

**Doing-right:** the repo already runs L1 selection over its factor set —
`factor_learning.py:88` fits `LassoCV(cv=5, n_alphas=40)` on the train split of the 10
signals at `factor_learning.py:37-38` (`trend, revert, mom126, mom_st, golden_cross,
breakout, lowvol, mom252, qual_mom, def_revert`), per market, walk-forward, and grades
the survivors on an out-of-sample information ratio (`ls_book_ir`, `:62`) rather than on
in-sample fit. Sparse selection *plus* an OOS grade is more than most of this literature
does.

**Gap:** the repo converts that selection into an inference claim it cannot support.
`factor_learning.py:145` states, in the generated report, "Lasso zeroing a factor = that
factor adds nothing once the others are in (built-in selection — a principled cure for
the multiple-testing fragility the Deflated-Sharpe flagged)". Single-stage LASSO does not
license that reading: the penalty biases coefficients toward zero, selection is unstable
across resamples, and post-selection coefficients have no valid standard errors. This is
precisely the problem double-selection (Belloni–Chernozhukov–Hansen) exists to fix — run
LASSO twice, once of the outcome on the controls and once of the signal-of-interest on
the controls, take the **union** of selected controls, then refit unpenalised and read
off a coefficient with valid inference. `grep -rniE
'double.?selection|post.?selection|debias|desparsif|belloni|chernozhukov'` over the whole
repo returns nothing on this (the two `trading_financials.py:60,78` hits are an unrelated
trade-filter step named DEBIAS). So the *strongest* factual claim the learned-factor
report makes is the one part of it with no test behind it.

**Distinct from queue item 21**, which attacks the same report from the non-linearity
side (a Pearson participation ratio and a linear model share a blind spot). This is the
inference side: even restricted to the linear terms both already see, "zeroed ⇒ adds
nothing" is unwarranted. The two are complementary and neither subsumes the other.

**Action queued:** item 26.

### 2609.04917 — Artificial Intelligence in Equity and Crypto Markets: Progress, Profitability Evidence, and the Limits of Automated Investing (Linsen Zhu & Mengqing Cai, 2026-09-04)

EVIDENCE-GRADE: not applicable — a critical review of public research through
2026-08-31, no original panel. Registered for its framing, not its numbers. Its organising
device is an **"alpha-translation chain"**: information → stable signal → feasible
positions → executable orders → risk-adjusted net returns after costs. A method is graded
by the *furthest link it demonstrates*, not by its headline metric. Its verdict is that
progress is "real but mainly upstream", and that no general AI architecture in the public
record delivers persistent, cross-regime, capacity-aware net alpha.

**Doing-right:** this repo sits unusually far down that chain for a one-person estate.
`cost_vs_edge.py` exists precisely to ask whether the small-cap Piotroski edge survives
costs, and grounds its answer in Krauss, Krüger & Beerstecher (2015) — the same finding
that set the ₹1 crore/day liquidity floor. Capacity is treated as a first-class question,
not a footnote. Under the review's own grading the pipeline reaches the last link on at
least one strategy, which is more than the reviewed AI literature manages.

**Gap:** none actionable, and this is deliberately not queued. The review's remaining
criticisms — temporal contamination, survivorship, capacity — already map onto queue items
23, 24 and 25 and onto the standing 2026-08-28 finding that this repo has no LLM-agent
surface for its AI-specific critiques to attach to. Logged as a citable external prior for
the *next* time an AI-flavoured method is proposed here: the burden of proof is the last
link in the chain, and the public record has not met it.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2212.12845** (Wan, Li, Lu & Song, "Mining the Factor Zoo: Estimation of Latent Factor
  Models with Sufficient Proxies", 2022-12-25, stat.ME) — penalised reduced-rank
  regression for latent factor estimation with an increasing number of proxies, plus a
  heavy-tailed-robust variant. The abs page discloses **no universe, no date range, no
  evaluation metric and no cost treatment**; the claimed contribution is a convergence
  rate. Latent factors are also the wrong object here — this repo's 10 signals are named,
  interpretable and individually tradable, and replacing them with statistical factors
  would destroy the property that makes the mailer explainable. Off-scope.
- **1907.01670** (Zeng, Xia & Zhang, "Double Cross Validation for the Number of Factors in
  Approximate Factor Models", 2019-07-02) — surfaced by the query's "effective number of
  factors" clause and rejected on it. Pure econometric theory: consistency of a
  cross-validate-over-observations-then-over-variables rule as both dimensions grow, with
  no equity application. The repo's analogous quantity is already measured
  (`research/factor_redundancy.py` participation ratio, 4.92/10 IN and 4.53/10 US, per
  queue item 21), and a consistency proof for a different estimator does not change what
  to do about it. Not deep-read.
- **Citation-following, already registered** — 2608.26990, 2607.19453, 2607.04958,
  2606.08285 returned again (seventh consecutive run); listed only so the day's candidate
  count is honest. 2609.04917 was the one genuinely new hit and was deep-read above.

## Added 2026-09-09 (daily task, Wednesday gap query: learning-to-rank cross-sectional equity returns)

Citation-following from hub 2605.19337 returned **five** citing papers and **none of them
new** — 2609.04917 (deep-read yesterday), 2608.26990, 2607.19453, 2607.04958, 2606.08285,
all already in the register. Yesterday's note that the branch is "slow, not dead" survives
but today it was dead. Whole yield from the weekday gap query.

Second Wednesday pass on this theme. 2026-08-26 asked whether the repo should *train* a
ranker and correctly answered no — it has no learned cross-sectional model to re-fit. So
today was re-aimed at the half that pass left untouched and that does apply to a
rule-based screener: **the repo already ranks and already cuts to a top-N, and nothing has
ever checked that the ordering it cuts on carries information.** That question needs no
ranker, no GPU and no new data.

The re-aim also closed an open loop. The 2026-08-26 entry logged Poh et al. as paywalled
at pm-research.com and noted "a possible re-check if an open version appears" — the arXiv
preprint (2012.07149) surfaced on today's query and is registered below.

### 2012.07149 — Building Cross-Sectional Systematic Strategies By Learning to Rank (Poh, Lim, Zohren & Roberts, 2020-12-13)

The paper the 2026-08-26 entry could not verify. Reformulates cross-sectional portfolio
construction as a *ranking* problem rather than a prediction-then-sort problem, and
benchmarks four learning-to-rank algorithms (RankNet, LambdaMART, ListNet, ListMLE)
against a random baseline, two published momentum heuristics (Jegadeesh & Titman, Baz et
al.) and an MLP "regress-then-rank" baseline. Universe is actively traded NYSE firms
**1980–2019**, filtered at each monthly rebalance to names above $1 with valid prior-year
pricing. Selection is **100 long / 100 short, ~10% of the tradeable universe per
rebalance**. Headline: LambdaMART **Sharpe 2.156** vs **0.696** for the Baz heuristic and
**0.265** for the MLP — the "approximately threefold" claim in the abstract.

- **EVIDENCE-GRADE: medium-high on the mechanism, low on the number.** Graded up for the
  things this register keeps asking for and rarely gets: a real, named, reproducible
  universe (NYSE), a **40-year** window spanning many regimes, a disclosed selection rule,
  and — unusually — baselines that include the obvious cheap alternative rather than only
  strawmen. Graded down hard on one disclosure, which the paper is at least honest about:
  **transaction costs are not modelled at all.** Verbatim: "All returns in this section are
  computed without transaction costs to focus on the raw predictive ability of the models."
  A monthly-rebalanced 200-name long/short book is exactly the design where that omission
  is load-bearing, so the 2.156 is a gross number and the 3x ratio is not a net-of-cost
  claim. The paper also does not report turnover, which would have let a reader estimate
  the cost drag themselves. **Take the framing, not the Sharpe.**
- **Doing-right (verified): the repo separates selection skill from beta and from the
  liquidity tilt, which is a harder test than anything in this paper.**
  `rloo_rescore.py` scores each pick against a leave-one-out baseline of the *other*
  eligible names in the same market x date x liquidity tier (`rloo_rescore.py:271,281`),
  with the rationale stated at `:8-36` — raw forward return confounds the market day, the
  factor tilt and actual skill, and only the third is an edge. Overlapping forward windows
  are collapsed to one mean per (market, date) cohort with Newey-West HAC errors at lag h
  (`rloo_rescore.py:55-64` header). Poh et al. report a raw Sharpe against a random
  baseline; this is strictly the more demanding comparison.
- **Doing-right (verified): rank IC is already the house metric where a ranker exists.**
  `pead_liquidity_study.py:226` reports Spearman rank IC with a t-stat, and
  `backtest_ccc.py:258` builds a per-month IC series (both re-confirmed today; the
  2026-08-26 entry logged the latter and it has not drifted).
- **Gap (verified, and this is the day's finding): the ordering the mailer actually cuts on
  has never been validated.** The technical shortlist is produced by `_cap_technical()` —
  `signal_tracker.py:222` sorts by `score` descending and takes
  `TECHNICAL_TOP_PER_MARKET = 5` (`:210`) per market. The comment at `:195-207` records
  exactly how much work that cut does: the filter returned **2,110 passes in one run** and
  pushed the watchlist from 775 to 2,703 rows, so grade alone was "not enough of a bar" and
  the fix was to "rank by quality score and take the best few PER MARKET". That is a
  ~2,110 → ~25 reduction decided entirely by the ordering of one column. `score` for those
  rows is `Quality_Score` (`signal_tracker.py:152`). Nothing anywhere tests whether
  `Quality_Score` ranks forward returns *among names that already passed*: the rank-IC
  machinery at `pead_liquidity_study.py:226` and `backtest_ccc.py:258` is pointed at PEAD
  surprise and the CCC signal, not at this column, and `rloo_rescore.py` answers the
  different question of picked-vs-not-picked, not rank-6-vs-rank-4. Poh et al.'s result is
  precisely that a score built to separate good from bad is not automatically a good
  *ranker* — their MLP regress-then-rank baseline scores 0.265 against 2.156 on the same
  data. The repo is a score-then-cut design and has never measured its own ordering.
- **Gap: no rank hysteresis on that cut.** `grep -rniE
  'hysteres|turnover_cap|churn|drop_n|dropn|buffer.?zone' --include='*.py'` over
  `code/python_files/` returns no true hits (only `dropna` false positives). A name at rank
  6 today and rank 4 tomorrow enters and leaves the shortlist on score noise.
  `filter_watchlists.py:70` does hold `EVICT_SESSIONS = 5`, but that counter is documented
  at `:41` as counting sessions in which a name **does not pass the filter** — it is a
  different module tracking filter membership, not rank position, so it should not be
  credited as buffering the top-5 cut.
- **Action queued: item 27** (rank-IC-within-passers on `Quality_Score`).
- **Not queued: adopting LambdaMART.** Same verdict as 2026-08-26 and for the same reason —
  it needs a trained ranker this repo does not have. The gap above is the *prerequisite*
  diagnostic, and it is cheap; if the ordering turns out to be flat, no ranker is worth
  training on it either.

### Incidental finding (not from a paper — found while grep-verifying the above)

`signal_tracker.py:152` writes `"score": float(r.get("Quality_Score") or np.nan)` and
`:181` writes `"score": float(r.get("f_score") or np.nan)`. Both are falsy-zero bugs: a
genuine score of **0** is falsy, so `0 or np.nan` evaluates to `np.nan` and the row is
logged with a missing score. `f_score` is a Piotroski F-score on 0–9, so 0 is a legitimate
and reachable value. This does **not** change today's selection — `sort_values("score",
ascending=False)` puts NaN last by default, which is where a 0 would have sorted anyway —
so it is a data-quality bug in the ledger, not a picking bug. It matters because the ledger
is the input to any study of the score column, including queue item 27: a rank-IC run that
silently drops the worst-scoring rows would be measuring a truncated sample. Fix is
`pd.to_numeric(r.get(...), errors="coerce")`, matching what `:153-155` already does for
`price_at_signal`. Worth folding into item 27 rather than queueing separately.

### 2605.13407 — Vector-Quantized Discrete Latent Factors Meet Financial Priors: Dynamic Cross-Sectional Stock Ranking Prediction for Portfolio Construction (Namhyoung Kim & Jae Wook Song, 2026-05-13, IJCAI 2026)

PRISM-VQ: expert prior factors combined with vector-quantized discrete latent factors, VQ
acting as an information bottleneck and the discrete codes doubling as routing signals for
a mixture-of-experts. CSI 300 and S&P 500; **train 2009–2019, validate 2020–2021, test
2022–2024**; **contemporaneous index constituents** to avoid survivorship bias; costs
**5 bp at open and 15 bp at close** (20 bp round trip, asymmetric); portfolio rule is
**TopK-DropN with K=30, N=5**; trained on a single RTX 3090.

- **EVIDENCE-GRADE: medium, and off-scope as a model.** The *disclosure* is good — this is
  one of the few papers this register has seen that names its cost model, splits its dates,
  states its portfolio rule and says what survivorship treatment it used, all without being
  asked. The model itself is out of reach and out of character: VQ + MoE needs GPU training
  the pipeline does not have, and discrete latent codes would destroy the explainability
  that makes an emailed shortlist usable — the same objection already recorded against
  2212.12845. Cost-robustness detail sits in Appendix E, which was **not fetched**; the
  20 bp figure above is from the main text and the wider grid is UNVERIFIED here.
- **Doing-right (verified): asymmetric round-trip costs are already modelled and already
  used as a grading bar.** Confirmed by the existing register entries on `cost_vs_edge.py`
  (2026-09-08 deep-read of 2609.04917) rather than re-grepped today.
- **Gap: TopK-DropN has no analogue.** The mechanism is a one-line change in spirit — hold
  K names, and only evict a holding once it falls out of the top K+N rather than the top K,
  so a name hovering at the boundary is not churned every session. That is exactly the
  hysteresis the second gap above says is missing from `signal_tracker.py:222`, and it is
  the same idea reached from the turnover side rather than the noise side.
- **Action: folded into item 27, not queued separately.** Deliberate. A DropN buffer is a
  fix for churn, and it should not be applied before item 27 establishes whether the
  ordering being buffered means anything. If `Quality_Score` has no within-passer rank IC,
  the right change is to stop cutting on it, not to cut on it more smoothly. Sequencing
  matters here and a second queue item would invite doing them in the wrong order.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2607.19385** (Guo, Lu & Zhang, "STN-TGAT: Top-K Portfolio Construction via
  Prior-Guided Graph Attention with Learnable Soft-Threshold Sparsification", 2026-07-01) —
  does carry an explicit transaction-cost adjustment, which is more than most, but the
  evaluation is **Top-5 selected from the top 50 S&P 500 names**. A 5-of-50 mega-cap book
  is too concentrated for its Sharpe to mean much and too cap-biased to transfer to a
  screener whose established edge is in *illiquid* names. Graph attention also needs GPU
  training. Off-scope on universe and compute both.
- **2105.10019** (Poh et al., "Enhancing Cross-Sectional Currency Strategies by
  Context-Aware Learning to Rank with Self-Attention") — same group as 2012.07149 and
  surfaced alongside it, but the asset class is FX. No cross-sectional equity panel, and
  currency carry/momentum does not map onto a fundamentals-plus-breakout equity screen.
  Off-scope.
- **2509.16616** ("Learn to Rank Risky Investors: A Case Study of Predicting Retail
  Traders' Behaviour and Profitability") — matched the query on "learn to rank" only. The
  ranked objects are *traders*, not securities; there is no cross-sectional return panel
  and nothing to transfer. Discard.
- **Citation-following, already registered** — 2609.04917, 2608.26990 (registered at line
  917), 2607.19453, 2607.04958, 2606.08285 all returned again, **none new**; listed so the
  day's candidate count is honest. Eighth consecutive run with no new citation on this hub
  beyond yesterday's single hit.

---

## Added 2026-09-11 (daily task, Friday gap query: point-in-time fundamentals / survivorship bias)

### 0810.1922 — Look-Ahead Benchmark Bias in Portfolio Performance Evaluation (Gilles Daniel, Didier Sornette & Peter Wöhrmann, submitted 2008-10-10; Journal of Portfolio Management 36(1), Fall 2009)

The oldest paper in this register and the most directly useful Friday hit so far, because
it points at the half of survivorship the repo has *not* already disarmed. The familiar
version of the bias is on the **strategy** side — picking from a universe of survivors.
This paper is about the **benchmark** side: evaluating a strategy against an index whose
constituents are taken from the *end* of the test period rather than reconstructed as they
stood at each date. Universe is the running top-500 US capitalisations from **CRSP,
1926–2006**, benchmarked against the S&P 500. Quantified magnitude: **up to 8% per annum**
for the S&P 500, which also **overstates Sharpe and understates peak-to-valley drawdown** —
so it corrupts the risk side of the evaluation, not just the return side. Remedy proposed
is comparison against random strategies drawn under matched investment constraints.

- **EVIDENCE-GRADE: high.** Real long-horizon database (CRSP, 80 years), a named
  benchmark, a quantified bias in annualised return, and an explicit statement of which
  *other* statistics it distorts. Metric is return/Sharpe/drawdown, not price-level
  MAPE. Pre-dates the ML literature that fills the rest of this register, and is better
  specified than most of it.
- **Doing-right (verified today, and it is the strong case): the India price panel is
  genuinely survivorship-free.** Measured directly on
  `~/.cache/market-warehouse/ohlcv_adj/IN` (path from `signal_tracker.py:100` via
  `warehouse_paths.ohlcv_adj_in()`): **513 symbols present in `year=2016.parquet` are
  absent from `year=2026.parquet`**, and `DHFL`, `DENABANK` and `DISHMAN` are each present
  in 2016 and gone by 2026. The comment asserting this at `smallcap_screener.py:22-24` is
  correct, not aspirational.
- **Doing-right: the repo already refuses the strategy-side version of this bias, in
  writing.** `smallcap_screener.py:30-38` declines to backtest on the real Nifty Smallcap
  250 constituents *at all*, on the stated grounds that NSE publishes only the current list
  and projecting it backwards would embed exactly this bias — and records that a market-cap
  reconstruction reproduces today's list at only 71%. `band_sip_backtest.py:20-26` models
  delisting as **two explicit bounds** rather than inner-joining it away, and says the
  choice between them decides the answer (31.9% of the sample is affected).
  `sweep_piotroski_plus.py:40-45` states its own survivorship bound as an upper bound
  because screener.in serves listed companies only. This is better discipline than most
  papers in this register.
- **🔴 Gap — the benchmark side is where it leaks, and the leak is live.**
  `signal_tracker.py:436` falls back to `bench = wide.median(axis=1)`, labelled
  `"panel-median (equal-wt)"`, whenever the market's real benchmark is missing or stale —
  and the comment block at `:417-428` records that this fallback **does** fire for India,
  because NIFTYBEES stopped updating when an equity-only bhavcopy filter was added. That
  series is then used as a benchmark *level*: `:473-474` computes
  `bret = (ba.iloc[-1] / ba.iloc[0] - 1) * 100`, and `:479` reports
  `xret_pct = ret - bret`. **The median of a cross-section of price levels is not an index.**
  It is not survivor-biased — names drop out as they delist, which is point-in-time correct —
  but it is **composition-drifting**, which is the same class of error arriving from the
  opposite direction: the same panel goes from **1,654 symbols in 2016 to 7,073 in 2026**
  (measured today), so the median price level moves whenever the *membership* of the
  cross-section changes, independently of any market move. Chaining a return off it
  attributes compositional drift to the market.
- **This is not a re-report of the known bug — it is the part of it that was never fixed.**
  The session log at `LITERATURE_REGISTER.md:140` records that this fallback "produced a
  fabricated +46.77% 'vs bench' for India" and was "replaced with a real NIFTYBEES+NIFTY50
  splice" on 2026-08-22/23. That replacement went into the **research analysis script** —
  `research/stock_pick_performance.py:139-178` builds the spliced series, rescaled at the
  seam so the handoff has no jump. The **live tracker was not changed**:
  `signal_tracker.py:436` still constructs the median. So the fabricated-benchmark
  mechanism was diagnosed a month ago, fixed where it was found, and left in place in the
  module that writes the ledger everything else is graded against.
- **Action queued: item 28** (port the spliced benchmark into `signal_tracker.py`, and
  quantify what the median fallback has been reporting in the meantime).
- **Considered and declined: the random-strategy remedy.** The paper's fix — compare
  against random portfolios under matched constraints — is already present in stronger
  form. `rloo_rescore.py:271,281` scores picks against a leave-one-out baseline of the
  *other eligible names in the same liquidity tier*, which is a matched-constraint null
  with the constraint that actually binds here. Nothing to add.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2505.07078** (Li, Kim, Cucuringu & Ma, "Can LLM-based Financial Investing Strategies
  Outperform the Market in Long Run?", v1 2025-05-11 / v6 2026-06-26) — FINSABER: a
  genuinely well-built bias-aware backtester (delisted stocks explicitly included,
  2-year rolling windows on a 1-year step, two decades and 100+ symbols, finding that
  reported LLM advantages deteriorate under a broader cross-section). Failed on
  **redundancy, not quality**: every transferable piece is already in the repo — the panel
  is survivorship-free (measured above), `walk_forward_backtest.py` and
  `strategy_regime_survival.py` already do rolling-window and regime-conditional
  evaluation, and its headline conclusion is the same one 2609.04917 already carries in
  this register. The remaining content is an audit of LLM timing agents, which this
  pipeline does not run.
- **2603.27539** ("Toward Reliable Evaluation of LLM-Based Financial Multi-Agent Systems:
  Taxonomy, Coordination Primacy, and Cost Awareness") — evaluation taxonomy for
  multi-agent LLM systems. No cross-sectional equity panel, no security-level returns;
  the "cost awareness" is inference cost, not transaction cost. Off-scope.
- **2506.07993** ("Stochastic portfolio theory with price impact") — continuous-time
  theory, no backtest and no dataset. Matched the query on "price impact" only. Discard.
- **Citation-following, already registered** — 2609.04917, 2608.26990, 2607.19453,
  2607.04958, 2606.08285 returned again, **none new**. Ninth consecutive run in which this
  hub's citation list produced no new candidate; every hit came from the gap query.

## Added 2026-09-12 (daily task, Saturday gap query: correlation-matrix eigenvalues / regime / effective dimension)

Note on dedup: this is the **third** Saturday pass on this theme (2026-08-23, 2026-08-29).
Citation-following from hub 2605.19337 returned exactly five citing papers — 2609.04917,
2608.26990, 2607.19453, 2607.04958, 2606.08285 — **all five already in this register**, so
that branch is now exhausted until the hub accrues new citations. The plain gap query
likewise returned only already-logged IDs (2601.06090, 2507.01918, 2604.17251, 2507.14325,
2212.05504). A third search re-angled onto *covariance filtering / shrinkage* rather than
*regime detection* is what produced everything new below — the spectral-descriptor framing
was mined out, the estimator framing was not.

### 2309.17219 — Covariance matrix filtering and portfolio optimisation: the Average Oracle vs Non-Linear Shrinkage and all the variants of DCC-NLS (Christian Bongiorno & Damien Challet, submitted 2023-09-29)

This is the **source paper for the "Average Oracle" baseline** that queue item 18 already
names but was, until today, known to this register only second-hand through 2507.01918's
comparison table. Fetching it directly changes the item from "try a frozen-eigenvalue
estimator" to a specified method with published numbers.

Passes triage on the strictest reading of this register's bar: headline metric is Sharpe
(with realized volatility and turnover reported beside it), US equities at both 100 and
1,000 names, out-of-sample 2000-01 through 2021-12, weekly (5d) and monthly (20d)
rebalancing — and transaction costs are not merely "discussed" but **applied**: the paper
sets 5 bps, paid at each rebalance.

**Doing-right:** the paper's whole result is a turnover result. On 100-asset long-short
books at 5-day rebalancing it reports Average Oracle (AO1200) **Sharpe 1.229 at turnover
0.068** against DCC-QIS/QuEST **Sharpe 0.894–0.895 at turnover 1.307–1.308** — the
sophisticated estimator runs roughly **19x the turnover** for a *lower* Sharpe. This is the
same failure mode 2507.01918's neural estimator showed (112% vs 44% per 5 days) and the
same one queue item 18 was written to catch. Two independent papers by overlapping author
groups now say the identical thing: on this axis, variance reduction is bought with churn,
and churn is what kills the net number.

**Method, concretely (this is the part item 18 was missing):** eigen-decompose the
correlation matrix; replace its eigenvalues with a **fixed set calibrated once on an
earlier, outdated sample** and held time-independent thereafter, keeping the current
eigen*vectors*. The calibration itself is a bootstrap — repeated random draws of periods
and of assets, taking the covariance of each draw's "future" period against the
eigenvectors of its adjacent past period, then averaging. So the eigenvalues encode the
*average* influence of future on present rather than the current sample's noise. AO1200
denotes the calibration length. No training, no GPU, no new data — it is a bootstrap loop
plus an eigen-decomposition, which is exactly the scale this repo runs at.

**Gap (verified, and it corrects a prior entry — see the incidental finding below):** two
of the three covariance sites in this repo remain raw sample estimators.
`portfolio_builder.py:217` is `cov = R.cov().values * TRADING_DAYS`, fed into
`port_var = lambda w: w @ cov @ w` at `:222`; `mutual_fund_theorem.py:107` is the identical
line. Neither applies any eigenvalue treatment.

**Action queued:** item 29 — not a new experiment but a correction and sharpening of item
18: run its three-way comparison inside `etf_builder.py`'s existing rebalance loop, which
already has the harness, and use this paper's AO specification rather than the vague
"spectrum estimated once on the earliest third".

### 2609.09588 — Signal Correlation, IC, and PnL Dependence (Marc Nunes, 2026-09-09)

A pure theory paper — no universe, no date range, no backtest, no costs — and admitted here
deliberately, because the register's triage bar is aimed at *weak empirical* work (headline
MAPE on four correlated tech stocks) and not at a proof. Its result bears directly on a
measurement this repo already runs.

**The result:** signal correlation (across assets, at each date) and PnL correlation
(across dates, for scalar payoffs) are correlations over **different index sets**, and
practitioners routinely use the first as a proxy for the second. The paper decomposes
signal correlation into an uncentred IC cross-moment plus a "transverse similarity" term in
the orthogonal complement of the realized return direction, while Pearson PnL correlation
centres and dispersion-weights the IC series alone. Its main theorem is a
**non-identifiability** statement: absent constraints on the transverse geometry, neither
correlation bounds or orders the other. Two signals can look 0.9-correlated and have
near-independent PnL, or vice versa.

**Gap (verified):** `research/factor_redundancy.py` measures redundancy **entirely** in the
signal-correlation index set. `:65` is `corr = df.corr().values` over the ten factor
columns of `factor_learning.py`'s feature matrix; `:42-54` eigendecomposes exactly that
matrix to produce the participation ratio, eigenvalue entropy / effective rank and
absorption ratio; `:75-81` names the top-5 most correlated *pairs* from the same matrix.
The file's own docstring (`:15-16`) states the method as "Take Pearson correlation across
the 10 columns, eigendecompose it". Every redundancy number this repo has is therefore a
signal-side number, and this paper says it does not order the thing we actually care about
— whether two factors make money at the same times. The repo has never computed the
PnL-side matrix at all.

**Not adoptable:** the transverse-Gram-matrix machinery and the gauge-invariance argument.
The usable content is one sentence of the decomposition: the PnL-side quantity is the
Pearson correlation of the **per-date realized IC series**, which is cheap.

**Action queued:** item 30 — compute both matrices and print them side by side, rather than
replacing one with the other; the paper's point is that they are different objects, not
that the existing one is wrong.

### Incidental finding — a prior register entry overstated the gap it found

The 2026-08-29 entry for 2507.01918 asserts that "the repo builds its covariance matrices
from the raw sample estimator with no eigenvalue treatment at all". That is **not correct
as a blanket claim**, verified today by grep: `etf_builder.py:202` imports
`from sklearn.covariance import LedoitWolf` and `:227` computes
`cov = LedoitWolf().fit(hist.values).covariance_ * TRADING_DAYS`, with a comment at
`:224-226` giving the reason ("the sample covariance of 200 names on 252 days is
near-singular and its inverse is noise. Shrinkage is the minimum defensible treatment, not
an optimisation"). That module also already tracks `turnovers` per scheme (`:205`) across a
strictly-trailing rebalance loop (`:208-231`).

So the repo has three covariance sites, not two, and the third already does the right
thing. This matters practically rather than pedantically: item 18 was scoped as "build a
shrinkage comparison", when a shrinkage-and-turnover comparison harness already exists and
the work is to point it at the other two sites. Logged here because this register's own
instructions warn that prior summaries drift and must be re-grepped rather than trusted.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2601.15597** (Yang, Zhao & Chai, "Neural Nonlinear Shrinkage of Covariance Matrices for
  Minimum Variance Portfolio Optimization", 2026-01-22) — abstract fetched: a
  transformer-based network learns a nonlinear eigenvalue shrinkage function on top of
  Ledoit-Wolf, trained with portfolio risk as the loss. Headline metric is out-of-sample
  realized risk **only** — no Sharpe, no turnover, no transaction costs, no stated date
  range, and it requires training. Same shape as the two neural-shrinkage papers already
  logged (2507.01918, 2608.30446) and fails on the axis both of those at least reported.
  Not adoptable and not separately informative. Discard.
- **2511.10478** (Ruelloux, Bongiorno & Challet, "Noise-proofing Universal Portfolio
  Shrinkage", 2025-11-13) — abstract fetched: robustifies Kelly et al.'s UPSA by
  time-averaging the optimal penalty weights and substituting **Average Oracle eigenvalues**
  for the sample ones. Corroborating rather than new: its transferable content reduces to
  the same AO recommendation as 2309.17219 above, wrapped in UPSA machinery this repo does
  not run. Logged as supporting evidence for item 29, not separately actioned.
- **2510.19130** ("Denoising Complex Covariance Matrices with Hybrid ResNet and Random
  Matrix Theory: Cryptocurrency Portfolio Applications") — surfaced by the estimator query.
  Crypto universe and a trained ResNet: wrong asset class for this repo and wrong compute
  scale. Title and venue only; nothing asserted about its contents. Not fetched, not
  reviewed.
- **2410.03053** ("The Quadratic Optimization Bias Of Large Covariance Matrices"),
  **2507.01545** ("Covariance Matrix Estimation for Positively Correlated Assets"),
  **2609.04496** ("Portfolio Diversification and Concentration under Dependence Uncertainty:
  A Majorization Approach") — three estimation-theory papers surfaced by the same query.
  Not fetched, so nothing is asserted about their contents; logged by title only so they are
  not re-surfaced as unreviewed on a future Saturday.

## Added 2026-09-14 (daily task, Monday gap query: CPCV / purging / embargo)

Fourth Monday on this theme. Citation-following from hub 2605.19337 returned the same five
citing papers (2609.04917, 2608.26990, 2607.19453, 2607.04958, 2606.08285), all registered
— still dry. The plain CPCV query surfaced only registered IDs (2407.17645, 2512.12924) and a
software paper; a re-angled query on *deflated Sharpe / backtest overfitting* surfaced
2603.20319, and the q-fin.PM recent listing surfaced 2609.12477, a direct sequel to the
paper behind queue item 30.

### 2603.20319 — Implementation Risk in Portfolio Backtesting: A Previously Unquantified Source of Error (Dong Yin, Takeshi Miki, Vladislav Lesnichenko & Vasyl Gural, 2026-03-19, q-fin.PM)

Passed triage because cost is the independent variable here, not a footnote. The design runs
15 benchmark strategies through 5 engines: bt 1.1.0, vectorbt 0.26.2, Backtrader 1.9.78,
cvxportfolio 1.3.0, and the authors' reference implementation. The data is 30 stratified
buckets of 180 S&P 500 stocks. Four cost regimes: 0 bps, 18 bps (15 commission + 3
slippage), 36 bps, and 60 bps (50 + 10).

**Result:** at zero cost all five engines agree exactly (max divergence **0.000%**), so
**cost implementation is the sole source of disagreement**. Under costs, divergence tracks
cost intensity (Spearman **0.93**). It stays under ~0.75pp for most strategies but reaches
**3.61%** (18 bps) and **3.71%** (36 bps) for a monthly full-portfolio rotation. The
conventions named as drivers:
- pre- vs post-trade equity reporting
- cost charged on notional vs on the traded delta
- deduction before vs after reallocation
- integer vs fractional shares
- sell-first fill ordering
- whether the initial construction is charged
- the turnover definition

It also found seven undocumented engine defects, e.g. Backtrader silently undercharging
commissions 100× under the `percabs=False` default, and NautilusTrader double-charging
through a wrapper. **Conclusion Sensitivity Index = 0 on all 15:** engine choice never
flipped the sign of Sharpe.

**Doing-right (paper):** the zero-cost ablation isolates the mechanism cleanly, and the
reassuring result (no sign flips) is reported as prominently as the alarming one.

**Verified against this repo (greps run today):**
- **Engine defects — no surface area.** A grep for imports of `backtrader|vectorbt|zipline|nautilus_trader|bt|cvxportfolio|backtesting`
  across `code/python_files/` (excluding `.venv/`) returns nothing. Every backtest is
  hand-rolled.
- **But the repo runs at least five different cost conventions, which is exactly the
  paper's mechanism, spread across modules instead of engines:**
  1. Flat **20 bp round-trip** subtracted from each trade's percentage return:
     `backtest_screeners.py:174` and `:285` (`gross_ret - cost * 100`), and
     `walk_forward_backtest.py:156` and `:936`.
  2. **10 bp per side × L1 traded weight change**, with the first rebalance charged at
     `turn = 1.0` (the "initial construction charged" convention): `etf_builder.py:60` and
     `:240-243`.
  3. **Flat 100 bp per rebalance on the whole level**, whatever the turnover (the
     *notional* convention). Charged to every series including the null, so comparisons
     are cost-neutral: `custom_indices.py:41-42`, `:68` and `:146` (`lv *= (1 - cost)`).
  4. **Per-market round-trip hurdle** of 15–40 bp, with **India at 40**:
     `confusion_matrix_eval.py:34` and `:94`.
  5. **Zero commissions**: `cost_vs_edge.py:36`.
- **India's round-trip cost is 20 bp in (1) and 40 bp in (4)**, so the same market is
  costed twice as heavily in one module as in another.

**Gap:** nothing in the repo has checked whether any headline conclusion depends on which of
these conventions its module happened to use. The paper's CSI is the right, cheap question
to ask.

**Not adoptable:** the multi-engine harness, since the repo has no engines to cross-check.

**Action queued:** item 31.

### 2609.12477 — Large Signal Libraries: Equal-Weight Limits and the Divergent Spectra of Signals and PnL (Marc da Costa Nunes, 2026-09-11, q-fin.PM)

Admitted as theory, deliberately, like its companion 2609.09588 (2026-09-12). The abstract
states "No market-data empirical results are presented". It bears directly on queue item
30, which has not yet been implemented: a grep for `pnl_corr|ic_series|PnL-side` outside
the register and queue finds only the 2026-09-12 run log.

It separates four objects:
- the equal-weight signal
- signal PCs
- equal-weight PnL
- PnL PCs

The results:
- Once demeaned and normalised, cross-sectional signals over d assets lie on a sphere of
  dimension q = d−1. Under axial symmetry, their mean is signal-cloud PC1 exactly when
  its longitudinal second moment exceeds **1/q**.
- The payoff map **annihilates transverse signal components** (Theorem 7.1).
- Signal PC1 and PnL PC1 then diverge through two further channels. **Temporal
  centering** removes the mean IC path. **Dispersion weighting** reweights dates by
  a_t², which "can change the ordering of principal components even when all population
  moments are known exactly".

§12 proposes an empirical program. Two of its steps are cheap at this scale:
- **§12.5:** compare the spectra of the full signal kernel, its longitudinal part alone,
  the dispersion-weighted IC Gram matrix, and the centered PnL covariance.
- **§12.4:** an equal-centrality diagnostic, `CVsig = sd(G·1) / |mean(G·1)|`, the
  dispersion of the Gram matrix's row sums.

**Verified against this repo:**
- `factor_learning.py:7-13` combines the ten factors with **LassoCV / SGD**, not equal
  weights, so the equal-weight limit theory does not describe the live combiner.
- The one equal-weight composite is the PPO *baseline*,
  `train_ppo_factor_weights.py:147-149` (`w = np.full(n_factors, 1.0 / n_factors)`).
- `research/factor_redundancy.py:65` still computes only the cross-asset `df.corr()`.

**Gap:** item 30 as written would compute one PnL-side matrix. This paper shows that matrix
mixes two separable effects, transverse annihilation and longitudinal transformation. Without
the intermediate spectra, a disagreement between the two participation ratios cannot be
attributed to either effect.

**Action queued:** item 32, an amendment to item 30 rather than new work.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2609.08106** (Kunhan Guo, "Nyström Attention Matches Full Attention for Cross-Sectional
  Stock Prediction", 2026-09-08). Weak for this repo: the metric is Rank IC only, no cost
  treatment appears on the abs page, and it requires training a MASTER transformer. Its
  own finding counts against adoption: at ~3,500 stocks, cross-stock modules do not
  significantly beat a per-stock LSTM.
- **2609.06267** (Lei Liu, "Return-to-Present Curves", 2026-09-05, stat.AP). A performance
  *display* method (fixed evaluation date, varying purchase date). No evaluation metric and
  no costs. Off-scope.
- **2507.04176** (Nicolini, Manzi & Delatte, "skfolio: Portfolio Optimization in Python",
  2025-07). A software paper with no empirical results. Noted only because it ships CPCV
  with purging and embargo if the repo ever wants a library instead of hand-rolled splits.
- **2512.22476** (Kaihong Deng, "AutoQuant", v3 2026-08-07, ESWA). Crypto perpetual futures
  (BTC/ETH/SOL/AVAX), where funding and slippage dominate. Wrong asset class. Its one
  transferable point, that fee-only simulations overstate performance versus fully costed
  ones, is already covered by 2603.20319 above.
- **2609.12227** ("Seasonal Trading in Commodity Futures", q-fin.PM). Not fetched; logged by
  title so it isn't re-surfaced. Commodity futures are off-scope.

## Added 2026-09-15 (daily task, Tuesday gap query: effective number of factors / redundancy / spanning tests)

Citation-following from hub 2605.19337 is still dry. Semantic Scholar returns the same five citing
papers, all registered. The Tuesday query surfaced five registered IDs (2602.20856, 2606.19550,
2603.29751, 2603.16365, 2606.23596) and four new ones. The q-fin.PM recent listing added three more.

### 2604.15531 — Spurious Predictability in Financial Machine Learning (Sotirios D. Nikolopoulos, v1 2026-04-16, q-fin.ST / stat.ME / stat.ML)

The paper audits whole workflows in two stages.
- **Stage 1** runs the pipeline on five synthetic nulls with zero conditional mean: (A) white noise,
  (B) regime-switching volatility, (C) a bid-ask-bounce MA(1) "friction placebo", (D) a mean-zero
  factor null, and (E) GARCH. A workflow that produces significant walk-forward evidence on any of
  them is falsified.
- **Stage 2** measures selection inflation on real data for the workflows that survive.

Techniques extracted:
- **Effective multiplicity** (Eq. 4): `K_eff = K² / ‖Σ‖_F²`, where Σ is the correlation matrix of
  the K candidates' in-sample t-stats, shrunk with Schäfer–Strimmer when K is large. `K_eff = K`
  under independence and falls toward 1 as candidates become collinear.
- **Absolute magnitude gap** (Eq. 7): `ΔZ = max_k|Z_IS,k| − |Z_WF,k*|`, the in-sample winner minus
  its own walk-forward result. The paper prefers this explicitly to ratio forms, which blow up as
  the denominator nears zero. A stabilized ratio (Eq. 9, τ = 0.5) is offered only as an intra-study
  heuristic.
- **SPY case study:** a deep-learning directional pipeline earns annualized alpha of 0.39% versus
  buy-and-hold after 2015, with p = 0.931. The apparent signal is traced to threshold-induced
  activity clustering (trigger rate 69.4% in calm regimes, 88.7% in volatile ones).

Evidence grade: moderate. The simulations use 1,000 Monte Carlo replications per scenario. Costs are
confined to an appendix. The QuantAudit R package is promised only "upon journal publication". The
paper has a single author.

**Verified against this repo:**
- `code/python_files/deflated_sharpe.py:42-49` computes E[max SR] "from N independent trials"
  (docstring `:43`) with `N = len(trials)` (`:45`). `main()` feeds it every factor row for a
  market×regime (`:74`). The candidates are the ten factors, which item 1 already measured as
  highly redundant (PR 4.92/10 IN). So the nominal N over-counts, E[max] is overstated, and the DSR
  gate at `:81` is **too strict**, not too loose.
- `walk_forward_backtest.py:1099` computes `Sharpe_Decay% = (train − val)/|train|·100`. That is
  the ratio form the paper warns against: it is guarded only for `train == 0` and explodes as
  train approaches 0. It also averages across groups rather than tracking the selected winner.
- Placebo or synthetic-null runs: `grep -rniE 'placebo|shuffle|permutation'` finds nothing relevant.
  The only resampling is the Lo (2002) Sharpe bootstrap in `r_analysis.py:245`, which tests one
  series and not the selection workflow.

**Doing-right:** the repo already runs a multiple-testing correction on the factor optimiser
(`deflated_sharpe.py`), plus BH-FDR in `pead_sector_spillover.py:230`, and walk-forward
TRAIN/TEST/VAL splits.

**Gap:** DSR uses nominal N, the decay metric is a ratio, and no workflow has been run on a
known-null panel.

**Action queued:**
- **33:** report DSR under both N and K_eff, and add an absolute-gap column next to `Sharpe_Decay%`.
- **34:** a white-noise and factor-null falsification run of the factor-selection workflow.

### 2501.19213 — Testing for the Minimum Mean-Variance Spanning Set (Zhipeng Liao, Bin Wang & Wenyu Zhou, v1 2025-01-31, v3 2025-03-18, q-fin.PM)

The paper estimates the minimum spanning set (MSS), the smallest subset of assets that spans the
full mean-variance frontier.

Method:
- Regress each asset on all the others.
- Statistic: `M_i = max{√T|α̂_i|/s₁, √T|1'β̂_i − 1|/s₂}`. The first term tests the tangency
  (alpha) condition; the second tests the global-minimum-variance condition.
- Moving-block bootstrap with block length `ℓ = ⌊1.2·T^{1/4}⌋`, and step-down critical values
  that control the max over assets.

Data: the Ehsani–Linnainmaa (2022) set of 22 monthly factors (7 momentum variants + 15 standard),
1964-07 to 2019-12.

Result: nine factors form the MSS, ranked PCM, ACC, QMJ, SMB, MKT, IAM, MOM, STR, RVA. QMJ enters
through α alone; most of the others enter through the β (GMV) channel. In simulation, coverage
exceeds 0.9 only once T reaches 240 months, and T ≥ 180 is the practical floor. Costs are not
discussed.

Evidence grade: solid econometrics on a public dataset, but gross returns only.

**Verified against this repo:**
- Queue item 12 (`BACKTEST_QUEUE.md:111-123`) proposes an **α-only** spanning regression. It says
  to reuse "the exact feature matrix `research/factor_redundancy.py` already builds (`:64-65`)",
  which is the per-date cross-asset **signal** matrix.
- No spanning test exists yet: `grep -rniE 'spanning|GRS|gibbons'` over `code/python_files` and
  `research/` finds only prose uses of "spanning" and the portfolio optimiser's max-Sharpe weights.

**Gap:**
- **The object is wrong.** Spanning is defined on **return** series, so it must be run on the
  ten factors' PnL series (the object item 30 builds), not on signal values.
- **The test is half-built.** α-only misses the GMV condition, and in this paper that condition is
  how most MSS members qualify.
- **Sample size is binding.** At fortnightly forward horizons, T ≥ 180 *months* is out of reach on
  most of the panel. Even with the higher sampling frequency, expect wide bands.

**Action queued:** 35, an amendment to item 12.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2602.14670** (Yanlong Wang et al., "FactorMiner: A Self-Evolving Agent with Skills and
  Experience Memory for Financial Alpha Discovery", v1 2026-02-16, v2 2026-08-19). The abstract
  discloses no metric, universe, date range or cost treatment. It is LLM-agent formula mining.
  Weak.
- **2609.07946** (Devanathan, Tzikas & Boyd, "Simple Dynamic Stock/Bond/Gold Portfolios",
  2026-09-07). Costs are modelled, but it covers multi-asset allocation across three assets plus
  cash, 2006-2026. That is off-scope for a single-name equity screener.
- **2306.14004** ("Latent Factor Analysis in Short Panels"). Not fetched; logged by title from search.
- **2609.11905** ("Entropic Value-at-Risk parity for tempered stable returns"). Not fetched;
  risk-parity theory, off-scope.
- **2609.04712** ("Convex Modeling of Price Cross-Impact over Time"). Not fetched; an execution and
  market-impact model for a pipeline that places no orders, so off-scope.

---

## Added 2026-09-17 (daily task, Thursday gap query: transaction-cost-aware factor evaluation)

Citation-following from hub 2605.19337 is still dry. Semantic Scholar returns the same five citing
papers, all registered. Two Thursday searches plus the q-fin.PM recent listing produced six new
candidates. The two left untriaged on 2026-09-03 (2603.15652, 2512.12420) were fetched and triaged
today.

### 2607.06502 — What Useful Alphas? (Andrew Y. Chen & Ivo Welch, v1 2026-07-07, q-fin.GN)

About 200 published long-short anomalies from the Chen–Zimmermann open-source dataset
(openassetpricing.com), each implemented as in its original paper (mostly quintile/decile sorts).
CRSP, US only.

The results come as a 2×2 split: period (≤2005 vs ≥2006) × universe (all stocks vs "Standard",
meaning top 3,000 **and** top 90% of market cap). Median long-short return by cell:
- ≤2005, all stocks: 48 bp/month.
- ≤2005, Standard: 26 bp.
- ≥2006, all stocks: 19 bp.
- ≥2006, Standard: **7 bp**. Only 67% of anomalies are positive, the median t is 0.45 and the
  median annualised Sharpe is 0.11. A tight N1000/80% universe gives the same 7 bp.

Techniques extracted:
- **The investable-universe filter is the test.** Screening on market-cap coverage, not only
  a count or a liquidity rank, removes about half the pre-2005 premium on its own.
- **Empirical-Bayes luck adjustment across the whole library:** `r_adj = [1 − 1/Var(t)]·r`,
  where Var(t) is the cross-anomaly variance of t-stats. Post-2005 Standard gives Var(t) = 1.09,
  so the signal share is about 0.08. The best survivor's raw 66 bp becomes 6 bp. It is one line
  and needs no per-trial Sharpe model.
- **By category:** profitability (cash-based OP, R&D-adjusted OP, gross profitability) is the
  only group with a healthy post-2005 median. Momentum, value and intangibles are "essentially
  dead" in the Standard universe. Off-season and seasonal momentum are the exceptions, at about
  50 bp.
- **Costs** are cited from Chen & Velikov (2023), not re-estimated: legs turn over about 40% a
  month in stocks with about 4× the median NYSE spread. Net returns are about −1 bp/month
  post-2005, or +4 bp with cost-minimising execution.

Evidence grade: strong. The data is public, the universe is large and the split is pre-specified.
Caveats: US only, static implementations only (the authors say timing and ML combinations may
recover some return), and costs are borrowed rather than modelled.

**Verified against this repo:**
- The factor optimiser's library is entirely price-based: trend, revert, mom126, mom_st,
  golden_cross, breakout, lowvol, mom252, qual_mom, def_revert
  (`code/python_files/profitability_optimizer.py:29-50`). Those are the momentum and reversal
  families the paper finds dead in large caps. The one family that survives, profitability, is
  not in the library.
- The investable gate is `strategy_regime_survival.py:98-105`: it drops only the bottom
  **turnover tercile** plus a $1 price floor, keeping about two-thirds of every universe. That is
  far looser than top-3,000 plus 90% of cap. On IN's roughly 8.9k names
  (`liquidity.py:13`) about 5.9k survive. The panel loads only Close and Volume
  (`strategy_regime_survival.py:86`), so there is no market-cap field to apply the paper's filter.
- Books are **equally weighted** against an equal-weighted liquid universe
  (`profitability_optimizer.py:65-67`), and the output is labelled "Gross of costs"
  (`:151`).
- The sample starts in 2016 (`strategy_regime_survival.py:50`), so every result is already in
  the paper's weak post-2005 regime. There is no stale pre-publication period inflating it.
- Luck adjustment is Deflated Sharpe on the per-cell max (`deflated_sharpe.py:40-49, 74-81`).
  There is no cross-library shrinkage: a grep for `empirical.?bayes|shrink` over
  `deflated_sharpe.py`, `profitability_optimizer.py` and `strategy_regime_survival.py` finds
  only a prose use at `profitability_optimizer.py:10`.

**Doing-right:** post-2005-only sample; a liquidity gate exists; a multiple-testing gate exists
(DSR); the output is honestly labelled gross.

**Gap:** the gate is a turnover rank, not cap coverage. Scoring is equal-weight, which is exactly
the configuration where the paper's premia were microcap-driven. No library-wide shrinkage.
Profitability, the only surviving US family, is absent from the price-only factor library.

**Action queued:** 36.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2603.15652** (Davit Gondauri, "P vs NP Problem in Portfolio Optimization…", 2026-03-06,
  econ.EM). Cardinality-constrained Markowitz on about 94 Damodaran industry portfolios, with
  no date range and no costs. Off-scope.
- **2512.12420** (Lucius et al., "Deep Hedging with Reinforcement Learning…", 2025-12-13).
  SPX option hedging; costs are modelled but CIs overlap long-SPY. Options hedging is off-scope.
- **2607.18001** (Boris Belyakov, "AlphaZeroBeta…", 2026-07-20). CNN-GRU PPO market-neutral
  policy on seven indices, 2014-2024, with costs in the reward. It needs RL training and
  shorting. Off-scope.
- **2601.11958** (Zefeng Chen & Darcy Pu, "Autonomous Market Intelligence…", 2026-01-17). An
  LLM agent ranks Russell 1000 daily from April 2025; top-20 long-only FF5+Mom alpha is 18.4 bp/day,
  Sharpe 2.43, costs under 10% of gross. The window is about nine months and irreproducible by the
  authors' own statement. Weak on sample length.
- **2609.17609** (Marc da Costa Nunes, "Separated Signal Libraries: Packing, Saturation, and Joint
  Spectral Limits", 2026-09-14). Pure theory; the abstract says no market data are used. It
  follows 2609.12477 (registered), and nothing here is testable beyond item 32.
- **2512.16251** ("Interpretable Deep Learning for Stock Returns: A Consensus-Bottleneck Asset
  Pricing Model") and **2601.05975** ("DeePM", systematic macro). Not fetched; logged by title
  from search. Both are deep-learning pricing/allocation models, off-scope at this scale.

## Added 2026-09-18 (daily task, Friday gap query: point-in-time fundamentals / survivorship bias)

Citation-following from hub 2605.19337 is dry for the third run running: Semantic Scholar returns
the same five citing papers (2609.04917, 2608.26990, 2607.19453, 2607.04958, 2606.08285), all
already registered. Two Friday searches plus the q-fin.ST recent listing make three attempts and
produced eight candidates.

### 2609.20550 — Principal component error in high-dimensional factor models (Alex Bernstein, Lisa R. Goldberg, Nicholas Gunther, Alec N. Kercheval, Tian Lan, Yian Lin & Dayi Yao, 2026-09-17, math.ST)

Theory plus a three-factor simulation of the US public equity market. The setting is explicitly
"the number of variables grows with sample size bounded", which the authors note is "commonplace
in financial economics" — i.e. many assets, short window.

Techniques extracted:
- **Split the PC estimation error in two.** *Out-of-subspace error* is "the distance from an
  estimate to the subspace spanned by population factor exposures"; *in-subspace error* "arises
  from the fixed sample size of the latent factor returns". Both have almost-sure asymptotic
  limits as n grows with T bounded.
- **The out-of-subspace half is estimable from the data alone**, "providing an estimable floor
  for error". Theorem 2's estimator is the ratio `ℓ(p)/θⱼ(p)`, where `ℓ(p)` is the average of the
  n−k trailing sample eigenvalues of the dual covariance matrix and `θⱼ(p)` is the jth eigenvalue
  of `W(p) = YᵀY/(np)`. The in-subspace half "cannot be estimated from data alone".
- **In their US-equity simulation, out-of-subspace error dominates** — so the estimable floor is
  the larger piece, not a rounding term.

Evidence grade: it is a theory paper with a simulation, not a backtest, so the usual
Sharpe/cost/universe triage does not apply. Graded on its own terms the argument is clean and the
regime it assumes is exactly this repo's. Caveat: the simulation's n and T grids sit in Section 8,
which the arXiv HTML truncates at the point fetched today — the relative magnitudes above are
quoted from the abstract, not read off a table. Nothing below depends on those numbers.

**Verified against this repo:**
- `research/correlation_regime_spectrum.py` measures the market's correlation spectrum on a
  150-name target universe (`:34` `N_SYMBOLS = 150`) over a rolling **60-trading-day** window
  (`:35` `WINDOW = 60`, sliced at `:60`). Across the 299 windows in
  `correlation_regime_spectrum.csv` the names actually used range from **126 to 150**
  (126 only in the earliest windows, 2.3% of rows). **That is n/T between 2.1 and 2.5.** A
  126×126 correlation matrix estimated from 60 observations has rank at most 59: at least 67 of
  its eigenvalues are exactly zero before any market structure is read off it, and at n=150 it is
  at least 91.
  *(Corrected 2026-09-18 after running item 37(a): this entry first said the CSV carried 126 on
  every row, which is wrong — that is the first row only. The direction is unchanged and the
  rank deficiency is worse at the top of the range.)*
- The participation ratio and PC1 absorption ratio it reports come straight out of
  `spectral_stats()` in `research/factor_redundancy.py:43-54`, which eigendecomposes the raw
  Pearson correlation matrix with no shrinkage and no null model — the only defence is a
  numerical floor, `np.clip(ev, 1e-12, None)` (`:44`).
- BACKTEST_QUEUE item 9 already asks for a Marchenko–Pastur *descriptor* (λ₁−(1+√(n/T))² and m⁻)
  on `market_correlation_scan.py`'s nightly matrix. It does not ask whether the numbers already
  cited from this script (queue lines 21-22: "150-symbol NSE universe, rolling 60d windows")
  survive their own n/T.

**Doing-right:** the spectral work was correctly built as a measurement script, not a gate
("This is a MEASUREMENT script, not a new gate", `correlation_regime_spectrum.py:21`), so nothing
live depends on these numbers yet. Eigenvalues, not eigenvectors, are used — PR and AR₁ are
dominated by the large eigenvalues and so are far more robust than an eigenvector-based factor
model would be in the same regime.

**Gap:** the measurement lives in precisely the n>T regime this paper analyses, and no part of the
current code separates the market signal in PR/AR₁ from the dimension artefact. A PR of ~6.4 out
of 126 (`correlation_regime_spectrum.csv:2`) is not currently distinguishable from what the same
window length would produce on pure noise.

**Action queued:** 37.

### 2512.23847 — Detecting Lookahead Bias in LLM Forecasts (Zhenyu Gao, Wenxi Jiang & Yutong Yan, v1 2025-12-29, v2 2026-06-12, q-fin.GN)

A diagnostic, not a strategy. For a firm-date pair the authors put a **date-only recall query** to
the model and estimate "the probability that the LLM has internalized information about the
realized outcome", which they call **Lookahead Propensity (LAP)**. The test is the interaction of
LAP with the model's forecast in an accuracy regression: "a positive interaction between LAP and
the LLM forecast in an accuracy regression indicates lookahead-bias contamination."

Techniques extracted:
- **LAP as a per-observation contamination weight**, rather than a single yes/no verdict about a
  model. It is "materially positive throughout the in-sample period and collapses essentially to
  zero right after the training-data cutoff".
- **The post-cutoff sample as the placebo.** Applied to two tasks — news headlines predicting
  stock returns, and earnings-call transcripts predicting capex — "the LLM forecast's predictive
  power is amplified on high-LAP firm-date pairs, and the interaction loses significance on
  post-training-cutoff samples."

Evidence grade: sound for what it claims. Real firm-date data, a pre-specified placebo window, and
the headline is a regression interaction rather than an accuracy score. It is a validity test, so
there is no universe/cost triage to apply. Caveat: no transaction costs and no trading result
anywhere, and the abstract names neither the models nor the sample dates.

**Verified against this repo — the contamination channel does not exist here:**
- The only LLM call site in the pipeline is `extract_structured()` in
  `code/python_files/llm_extract.py`, and a grep for `llm_extract|extract_structured` across
  `code/python_files` (excluding `.venv`) finds exactly one caller:
  `code/python_files/promptfoo/provider.py:16,32` — the promptfoo regression harness. No scanner,
  scorer, backtest or mailer calls it.
- Its documented purpose is document parsing, not forecasting: SEBI DRHP filing text and
  broker-statement PDFs (`llm_extract.py:16-19`).
- Sentiment is **not** an LLM. `sentiment_pipeline.py:66-68` instantiates VADER with a
  finance-lexicon boost and `:134-135` scores each headline with it.

**Doing-right:** no LLM sits anywhere in the decision path, so no forecast in this repo can be
contaminated by parametric hindsight. This is worth recording as a deliberate property rather than
an accident, because several papers already in this register (2601.13770, 2605.24564, 2606.08285)
attack the same class of bias from different angles and none of it applies here.

**Gap:** none that is actionable today. The one thing to keep in view: if `extract_structured()`
is ever pointed at *historical* filings inside a backtest — the obvious temptation, given
`llm_extract.py:16-19` — the extracted "facts" become an LLM output indexed by a past date, and
this paper's LAP test becomes the right check before trusting them.

**Action queued:** none.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2607.18867** (Haozhe Jia, "HindsightBench: A Black-Box Behavioral Audit Protocol for
  Parametric Hindsight in Time-Indexed LLM Decision Tasks", v1 2026-07-21, v2 2026-08-10, cs.LG).
  Audits 15 models on a 258-node vintage-correct macro panel; finds effective cutoffs precede
  vendor-reported ones "by up to eight months", which invalidates calendar-window placebos. Real
  rigor, but it grades models, not strategies, and this repo runs no LLM in its decision path
  (see 2512.23847 above), so there is nothing here to act on.
- **2609.19013** ("Routing Frictions and Executable Liquidity in Fragmented Markets", q-fin.ST
  recent listing). Intraday order-routing microstructure; this is an EOD screener that places no
  orders. Off-scope.
- **2609.14733** ("WaVeFuse: Regime-Adaptive Equity Index Forecasting via Channel-Wise Wavelet
  Denoising and Vertical Attention Fusion") and **2609.12793** ("VertiFuseX: Generalizable
  Financial Forecasting via Multi-Stream Temporal Fusion"). Not fetched; logged by title from the
  q-fin.ST listing. Both are deep-learning index-forecasting architectures — the shape the budget
  cap exists to skip.
- **2609.14029** ("Special Markowitz: Thermodynamic Formalism for the Joint Regularisation of
  Returns and Covariance") and **2609.20264** (synthetic control under staggered adoption). Not
  fetched; a regularisation formalism and a treatment-effect estimator respectively, neither of
  which this pipeline has a place for.
- **2603.26797**. Surfaced only as a bare PDF link in the second search with no title; not
  fetched, not identified. Recorded so a later run does not treat it as new without checking.

## Added 2026-09-19 (daily task, Saturday gap query: correlation-matrix eigenvalues / regime / effective dimension)

Citation-following from hub 2605.19337 produced **one new paper** after three dry runs: Semantic
Scholar now returns six citing papers, five already registered (2609.04917, 2608.26990,
2607.19453, 2607.04958, 2606.08285) plus 2609.19705, triaged below. Two Saturday searches plus
the q-fin.PM and q-fin.ST recent listings make three attempts; seven candidates.

### 1102.4076 — The fine structure of spectral properties for random correlation matrices: an application to financial markets (G. Livan, S. Alfarano & E. Scalas, submitted 2011-02-20; Phys. Rev. E 84, 016113 (2011))

Old, and deliberately so: the Saturday rotation has now pulled six modern spectral papers into
this register and none of them supplies the thing this one does — a closed-form prediction for
where a *cluster* deposits its eigenvalues, checked against real data.

Techniques extracted:
- **The bulk is not noise; it is superposed cluster structure.** The paper's own framing: the
  large empirical bulks "have often been regarded as a consequence of the supposedly large amount
  of noise contained in financial data", and it challenges that by filtering the empirical matrix
  to expose clusters and watching the bulk decompose.
- **A block of N̄ mutually correlated assets with mean internal correlation ρ deposits N̄−1
  eigenvalues at exactly 1−ρ, plus one large eigenvalue at N̄ρ + (1−ρ).** That is the whole
  signature, and it lives in the *lower* spectrum. ρ is estimated as the mean off-diagonal
  correlation inside the block (their eq. 48).
- **Empirical check.** S&P500: 396 assets, T = 3400 daily returns, 1996–2009. FTSE350: 243
  assets, T = 1423, 2005–2010. Their filtering procedure (eq. 45–47) picks a tight block by
  `c_ij ≥ ρ_U`, then a weakly-correlated complement by two further thresholds, and reorders.
  In the S&P case the block found was **N̄ = 7 assets, ρ = 0.712, all of them energy-sector**,
  against a complement of 33 names with mean mutual correlation 0.099. Predicted small eigenvalue
  1 − 0.712 = **0.288**, which is what their eq. (49) reports.
- **Where it fails is as informative as where it works.** The FTSE spectrum matched the two-block
  model closely; the S&P one produced two large eigenvalues instead of one, and the paper
  attributes the discrepancy explicitly to "the unresolved correlation structure in the empirical
  S&P matrix, which gives rise to additional sub-clusters" — the predicted single large eigenvalue
  would have been N̄ρ + (1−ρ) = 5.272.

Evidence grade: **strong on its own terms, and the terms are not a backtest.** It is analytic
plus Monte Carlo plus two disclosed real universes over disclosed date ranges; there is no
strategy, no Sharpe and no cost model, because it makes no return claim. The usual triage bar
does not apply. Peer-reviewed in Phys. Rev. E, which the arXiv-preprint majority of this register
is not.

**Verified against this repo — and it lands on an already-queued item, not a new one.**
- `research/correlation_regime_spectrum.py` builds its matrix from `N_SYMBOLS = 150` (`:34`) over
  `WINDOW = 60` (`:35`, sliced `:60-64`); `correlation_regime_spectrum.csv` has 299 rows with
  `n_symbols` running **126 to 150**. n/T = 2.1 to 2.5, so rank ≤ 59 and between 67 and 91
  eigenvalues are identically zero. **Livan's 1−ρ signature is unreadable on this matrix**: the
  lower spectrum there is rank deficiency, not cluster tightness. Confirmed independently
  yesterday from the other direction — `research/spectrum_noise_null.md`'s independence null put
  PR at 41.8 against the analytic Marchenko–Pastur value n/(1+n/T) = 42.1.
- 🔴 **Queue item 9 points the same class of measurement at a matrix where it is worse.** Item 9
  asks for `m⁻ = count of eigenvalues below (1−√(n/T))²` on `market_correlation_scan.py`'s
  nightly matrix. That matrix is full-universe (the module's own docstring reports 2,225 resolved
  NSE symbols, `:220-222`) at `period: str = "1y"` (`:99`, default, threaded through `:261`,
  `:283`, `:295`, `:362`) — **T ≈ 250, n ≈ 2,225, n/T ≈ 8.9.** The lower MP edge (1−√8.9)² = 3.92
  sits *above* most of the spectrum, ~1,975 eigenvalues are identically zero, and m⁻ degenerates
  to a near-constant ≈ n − T that tracks how many tickers resolved that night, not the market.
  The source paper for m⁻, 2608.09641, ran n = 377 / 199 at w = 1000 — **n/T ≈ 0.38 / 0.20**, the
  opposite regime. Item 9 as written cannot produce the descriptor it names.
- Doing-right: both spectral scripts were built as measurement, not gates —
  `correlation_regime_spectrum.py` is research-only, and item 9's own instruction is "log them as
  a daily time series first; only then consider gating on them". Nothing live depends on either,
  so this is a wrong number never wired up rather than a wrong number in production.
- Doing-right, second: the repo reached Livan's conclusion empirically without the theory.
  `market_correlation_scan.py:189-197` documents that naive thresholding chains "everything
  transitively together via broad market beta", 57% of NSE and 37% of US into one component at
  0.55, and `mst_clusters`' docstring (`:216-234`) records that 0.7 broke it to ~23% and 0.8 to
  ~11%, "revealing clean real sector groups (fertilizer producers, cable TV operators, QSR
  franchise operators, pharma pairs)". That is Livan's superposition-of-blocks picture, found by
  hand.

Caveat: the two eigenvalue formulas are exact only for a homogeneous block; real blocks are not
equicorrelated, which is precisely why their S&P fit left a residual. Treat 1−ρ as a location to
look for mass, not a value to test equality against.

- Gap: the lower spectrum is unmeasurable anywhere in this repo at present, in both the research
  panel (n/T 2.1–2.5) and the nightly scan (n/T ≈ 8.9).
- Action queued: **item 38.**

### 2608.06618 — Beyond Co-Movement: Locality by Exposures Enables a Joint Factor-Graph Framework for Portfolio Diversification (Sara Chehab, Giorgos Iacovides, Parisa Yazdanparast & Danilo Mandic, 2026-08-06, q-fin.PM)

Proposes MINGLE, which "mutually regularises the factor and graph domains by redefining graph
locality through systematic factor exposure profiles, rather than via observed co-movements",
solved by ADMM over a joint objective (their eq. 5: factor reconstruction + exposure smoothness
on the graph + graph sparsity + degree barrier + factor decorrelation; hyperparameters k=6,
λ=0.1, α=2.2, δ=1.0, β=3.0, ω=0.997).

Evidence grade: **strong.** 300 equities — the 100 most actively traded from each of the S&P 500,
Nikkei 225 and STOXX 600, i.e. three of this repo's five markets — evaluated January 2019 to March
2026 on rolling 2-year windows, monthly rebalanced. Headline metric is **Sharpe and CAGR, not
MAPE**: 21.0% CAGR / 1.07 Sharpe at 0 bps for their best variant against 17.3% / 0.860 for
CutV-on-sample-covariance. **Transaction costs are modelled at 0, 10, 20 and 50 bps**, and the
ranking survives the top of that range (18.3% / 0.929 vs 16.1% / 0.800 at 50 bps). Paired
statistical testing is claimed. Disclosed universe, disclosed dates, costs addressed — this
clears the bar the weak-evidence section exists to catch.

Techniques extracted:
- **The central claim is about the distance function, not the cutoff.** Correlation neighbourhoods
  are "transient, window-specific"; exposure neighbourhoods capture "persistent economic
  structure".
- **A cheap diagnostic that needs none of the ADMM.** Their Figure 4 reports within-cluster edge
  weight as a multiple of between-cluster: **2.42× for correlation-based clustering against 5.30×
  for MINGLE** in calm markets. Separately, exposure-similarity graphs "align with GICS economic
  sectors, whereas correlation graphs do not".
- Cost: the B update is a Sylvester solve at **O(p³)**, tractable at p=300 on monthly windows. No
  GPU, no wall-clock figure given.

**Verified against this repo:**
- The repo's only asset-neighbourhood construction is correlation-based, and in both flavours
  MINGLE names: `compute_correlation_clusters` (`market_correlation_scan.py:156-181`) takes
  connected components of the `|corr| ≥ threshold` graph at `threshold: float = 0.55` (`:158`),
  and `build_mst`/`mst_clusters` (`:186-240`) does Mantegna single-linkage on
  `d_ij = √(2(1−ρ_ij))` (`:205-207`). Both are "locality by observed co-movement" exactly.
- 🔴 **The repo has already paid MINGLE's price and patched it with a threshold.** Per the
  docstrings cited above, the giant beta component ate 57% of NSE at 0.55, and the fix was to
  raise the cutoff to 0.7 — with the honest closing warning that "there's no universal 'right'
  cutoff... don't assume one number transfers across markets/periods". MINGLE's argument is that
  the non-transferability is a property of the *distance*, not of the cutoff, so no amount of
  tuning fixes it. That is a real gap and it is diagnosable without adopting MINGLE.
- **The inputs for the diagnostic already exist.** Per-stock factor exposures: `FACTORS` is a
  10-name list at `factor_learning.py:37-38` (trend, revert, mom126, mom_st, golden_cross,
  breakout, lowvol, mom252, qual_mom, def_revert) with `build_xy()` assembling the per-week
  cross-section, and `factor_zscore_panel.py:216` writes a z-scored continuous-factor panel for
  US + India to parquet. Sector labels already exist too — `watchlist_digest.py:252`
  (`market_cache/sector_map.json`) and `sector_valuation_history.py:27-28` (Damodaran map).
  🔴 But note `backtest_ccc.py:186`: `market_cache/sector_map.json` is **Europe-only**, so the
  sector-alignment half of the diagnostic needs the Damodaran map for IN/US, not that file.
- Doing-right: nothing consumes the clusters. Grepping every `.py`/`.sh` for
  `compute_correlation_clusters` / `market_correlation_scan` / `correlation_matrix.csv` returns
  only the module itself, `check_deps.py:62` listing it as a dependency, `ohlcv_cache.py:10`
  noting it re-downloads the universe, and four `symbol_master.py` comments. The scan writes
  `{prefix}_correlation_matrix.csv.zst` and a cluster report (`:328`, `:333`) and stops. No
  weighting, no screen and no email depends on a correlation cluster, so a wrong neighbourhood
  currently misleads a reader rather than a position.
- Doing-right, second: the repo's one documented use of a correlation cluster was as a *data-
  quality* probe, and it worked. `symbol_master.py:239-242` records that a 56-member cluster
  "turned out to be entirely J-REITs moving together on rate sentiment, not operating companies",
  which is how 63 leaking J-REITs were found. Co-movement locality is the right tool for that job
  even if it is the wrong tool for diversification — worth keeping straight before anything is
  replaced.

Caveat: MINGLE is a *portfolio-construction* method and this repo constructs no portfolio from
clusters, so adopting the ADMM itself would be borrowing machinery for a use that does not exist.
Only the Figure-4 diagnostic is in scope. Also, their 300-name universe is the most actively
traded decile of three large indices, which is the opposite of where this repo's documented edge
lives (`project_piotroski_plus`: illiquidity, not size) — so a result on their universe should not
be assumed to transfer to the NSE small-cap tail.

- Gap: no exposure-based neighbourhood exists, and the correlation-based one has never been
  compared against the sector labels the repo already carries.
- Action queued: **item 39.**

### Weak/off-scope, one line each (triaged, not deep-read)

- **2609.19705** (Mengxiao Wang & Nitesh Saxena, "SoK: Trading Agents or Market Crashers?
  Dissecting Robustness and Security Failures in Academic Financial LLM Trading Schemes",
  2026-09-17). The one new citation of the hub paper, and genuinely rigorous — their FARSIGHT
  framework audits 15 academic schemes and reports 80% failing a core robustness metric and 100%
  showing a security vulnerability. Off-scope for the same reason 2607.18867 was: the subject is
  LLM trading agents, and this repo runs no LLM in its decision path (verified 2026-09-18 at
  `llm_extract.py` / `promptfoo/provider.py:16,32`). Nothing to act on; re-read if an agent is
  ever wired in.
- **2601.04602** ("Forecasting Equity Correlations with Hybrid Transformer Graph Neural Network").
  Surfaced by the Saturday search. Not fetched: a transformer-GNN correlation *forecaster* is the
  GPU-training shape the budget cap exists to skip, and the repo's problem is measuring today's
  correlation structure correctly, not predicting next month's.
- **2606.23492** (Alswaidan, Jin & Varner, "Continuous Hidden Markov Models for Equity Returns:
  Heavy-Tail Emission Families and Regime-Conditional Value-at-Risk", 2026-06-22). Abstract
  fetched. Respectable validation — joint conditional-coverage test, walk-forward, a copula for
  cross-asset correlation, four panels including a CRSP cross-decade transfer — but the output is
  a regime-conditional VaR and this pipeline forecasts no risk budget and holds no positions it
  sizes. No date ranges or costs in the abstract. Filed as background, not actioned.
- **2609.13402** ("Diffusion models for dynamic volatility surface generation and data-driven
  hedging", q-fin.PM recent listing). Not fetched; options surfaces and hedging, neither of which
  this equity screener touches.
- **"Portfolio Diversification and Concentration under Dependence Uncertainty: A Majorization
  Approach"**. Named in the second search's q-fin listing with no arXiv ID returned; not fetched,
  not identified. Recorded so a later run does not treat it as new without checking.

## Added 2026-09-21 (daily task, Monday gap query: CPCV / purging / embargo)

Citation-following from hub 2605.19337 was dry. Semantic Scholar returns the same six citing
papers, and all six are already registered. The plain CPCV web search returned only registered
IDs (2407.17645, 2512.12924, 2507.04176, 2605.23959), plus 2209.05559 (DRL crypto; off-scope,
not triaged). An arXiv API query for "backtest overfitting / walk-forward / data snooping /
multiple testing" in q-fin, together with the q-fin.PM recent listing, gave eight new candidates.
That makes three search attempts.

### 2607.12248: When Directional Accuracy Lies: A Base-Rate-Honest Benchmark for LoRA-Adapted TimesFM on Equity Forecasting (Taizhen Cheung, v1 2026-07-14, v2 2026-07-15, q-fin.ST)

The model is a fine-tuned foundation model, which is off-scope here. What is in scope is the
evaluation protocol, and it names a trap this repo actually falls into.

Techniques extracted:
- **Score directional hits against the base rate, not against 50%.** The paper opens with an
  apparent ~80% directional accuracy and shows it is not skill. When the original conditions are
  recreated, a trivial "always-up" rule scores a base rate of ~0.70, and the fine-tuned model
  scores *below* that. The paper reports excess accuracy over always-up as its headline number.
- **Honest baselines side by side.** The baselines are zero-shot, always-up, random walk,
  persistence and AR(1).
- **Paired tests with multiplicity control.** McNemar and Diebold-Mariano, under
  Benjamini-Hochberg FDR.
- **Held-out-ticker stratification** inside expanding walk-forward folds. It is replicated on
  NASDAQ-100 and on S&P 500.

Evidence grade: **moderate, and it is a negative result.** The protocol is disclosed and seeded,
it covers two universes, and the multiplicity control is explicit. The abstract gives no date
range and no cost model, but no cost model is needed because the claim is "no directional skill".

**Verified against this repo:**
- Doing-right: the year-consistency screens count hits on **excess** return, not on raw return,
  so the base rate is already removed: `year_by_year_consistency_IN_full.py:48-49` and
  `factorial_screener_analysis_IN_technical.py:131-132` (`mean_excess_63d > 0`).
- Doing-right: BH-FDR and the deflated Sharpe already exist in `multiple_testing.py:34,46`.
- **Gap: the PEAD sector-spillover test uses exactly the 50% null the paper warns about.**
  `pead_sector_spillover.py:240-242` runs `binomtest(k, n, 0.5)` on
  "same_direction". Its own comment says the 50% is "expected under 'peers move independently of
  the news'". But `same_dir` compares the sign of the **raw**, non-market-adjusted
  leave-one-out peer mean with the surprise sign (`:167-172`). Under independence the chance of
  a match is p_up·f_beat + (1−p_up)·(1−f_beat), and that is only 0.5 when p_up or f_beat is
  exactly 0.5. Neither is: beats outnumber misses, and up days outnumber down days. Any positive
  tilt in both pushes the null above 0.5. All four versions inherit it, because v2, v3 and v4
  `import pead_sector_spillover as pss` (`_v2.py:39`, `_v3.py:50`, `_v4.py:68`).
- Minor: `dl_strategy_eval.py:185` reports a raw `hit_rate%` = `(sr > 0).mean()` with no
  buy-and-hold hit rate beside it. The same row reports alpha and Sharpe against B&H
  (`:177-182`), so the hit rate is secondary and was not queued.

Action queued: BACKTEST_QUEUE item 40.

### 2607.20168: Quantum Kernels and the Cross-Section of Stock Returns: Anatomy of a Vanishing Advantage (Junchi Shen, v1 2026-07-22, q-fin.PR)

Kept for its correction, not its quantum content.

Techniques extracted:
- **Universe selected with full-sample information is look-ahead.** An earlier 60-window version
  of the analysis screened the universe with full-sample information. That inflated the quantum
  kernel's stability metrics. Once the universe was rebuilt point-in-time over 170 walk-forward
  windows (Chinese A-shares, 2012–2025), the advantage vanished: ΔIC = +0.005, p = 0.42 against an
  RBF kernel-swap control.
- **Budget-equalised comparison across 11 models, with multiplicity-robust inference.** No
  pairwise difference survived.

Evidence grade: **moderate.** The window count, date range and control are disclosed. The metric
is IC only, with no cost model. The abstract page gives about 38k observations but not a stock
count.

**Verified against this repo: the lesson has already been learned, independently.**
`etf_builder.py:65-73` records the identical bug and the identical fix. Turnover had been ranked
over the whole period to pick a top 200, which showed "1/N beating SPY by 4.92 points a year — a
gap that is the UNIVERSE, not any scheme". The universe is now ranked on trailing data at each
rebalance. The re-entry engine's panel is still flagged "survivorship-lite top-200" at
`project_retrospective.py:67`, so that known gap is already tracked; nothing new to queue.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2609.14733** ("WaVeFuse", Bohra & Vijay, 2026-09-13). Already in the register and logs by ID
  from an earlier run. Headline figures are R² 0.81–0.96 and a mean Sharpe of 3.69 on four indices
  at 10 bp, which is too good for an index-timing claim. Not re-read.
- **2606.31251** (Ozimek, GAMLSS/ZAGA regime-conditional strategy comparison, 2026-06-30).
  S&P 500 only, one SVM strategy against buy-and-hold over 146 folds. It is a distributional-
  comparison method, and this screener compares no strategies at the return-distribution level.
  Not fetched.
- **2606.09478** (Fang & Ślepaczuk, CSI 300 regime-augmented HARQ plus XGBoost, 2026-06-08). One
  index, intraday/high-frequency inputs. It reports *weak* predictability after costs, which is
  an honest result but off-scope for an EOD cross-sectional screener.
- **2609.21271** (Cotton, "Nested Clustered Optimization Is One End of a Schur Bridge"). This is
  portfolio construction, and the repo builds no optimised portfolio. Listing only.
- **2608.24786** (Wysocki, learning-to-rank for the volatility risk premium on S&P 500 weekly
  options). The out-of-time Sharpe of 4.3–5.8 is options-only. Off-scope.
- **2608.14323** (Lin et al., homological sparse neural net on 94 characteristics, 1987–2016 US).
  It needs NN training on a characteristic panel the repo doesn't hold. Off-scope.

## Added 2026-09-23 (daily task, Wednesday gap query: learning-to-rank cross-sectional equity returns)

Citation-following from hub 2605.19337 returned **six** citing papers and **none new** —
2609.19705, 2609.04917, 2608.26990, 2607.19453, 2607.04958, 2606.08285, all already
registered. The newest of the six, 2609.19705, came off this same hub four days ago
(registered at line 2548), so the branch is alive but slow; today it yielded nothing.

Third Wednesday pass on this theme. Both prior passes (2026-08-26, 2026-09-09) landed on
the *mailer's* top-5 technical cut in `signal_tracker.py`. Today's query surfaced a paper
aimed at what happens **after** a screen rather than at the screen itself, and that pointed
at a second cut site the register has never looked at: `portfolio_builder.py`, which runs a
Markowitz optimiser on whatever the screen hands it. The finding below is there, not in the
mailer.

### 2604.17593 — Post-Screening Portfolio Selection (Yoshimasa Uematsu & Shinya Tanaka, submitted 2026-04-19, q-fin.PM)

Proposes **PS²**, a two-step framework for high-dimensional mean-variance investing: first
screen assets by a Lasso-type regression of a constant on excess returns with no intercept,
then estimate weights on the selected set with standard low-dimensional methods. Because
strong factors destroy the sparsity the screen relies on, they add **FPS²**, which defactors
returns before screening. Theoretical guarantees plus simulations plus an empirical
application on **S&P 500 constituents**.

- **EVIDENCE-GRADE: medium, and unusually honest about its own limit.** This is an
  econometrics paper — the load-bearing content is the theory and the simulations, and the
  empirical section is an illustration rather than a horse race, so there is no headline
  Sharpe to be sceptical of. Graded up for reporting a result against its own thesis: the
  conclusion states that **"transaction costs materially weaken the gains from active
  rebalancing"** when FPS² is applied to real S&P 500 data. A paper that runs the cost check
  and prints the answer that hurts it is worth more than one that reports a gross 2.1 Sharpe.
  Graded down because the abs page does not state the date range, rebalance frequency or
  typical selected-set size, and **the empirical section was not fetched in full** — those
  four facts are UNVERIFIED here and the cost sentence is from the conclusion as rendered by
  the HTML fetch, not from a table I read.
- **Doing-right (verified): the repo already tests something mean-variance cannot, and says
  why.** `fund_implementability.py:5-12` opens with "Mean-variance says nothing about whether
  a portfolio is purchasable", and measures min viable SIP, whole-share rounding drag and
  cash residual, on the stated ground that India has no fractional shares. The 🔴 note at
  `:33-36` records that rounding down is asymmetric and tilts realised weights toward cheap
  names — "a size/price tilt nobody chose and the backtest never modelled". That is an
  implementation-cost check on the optimiser's output, and it is more concrete than anything
  in this paper.
- **Doing-right (verified): expected returns are already shrunk.** `_expected_returns()`
  (`portfolio_builder.py:191-201`) applies James-Stein shrinkage of each name's mean toward
  the universe mean, λ=0.5 by default (`:375-376`), for the standard reason that sample means
  are the noisiest input to a mean-variance problem.
- **NOT a new gap — already queued: the covariance is the raw sample estimator.**
  `portfolio_builder.py:217` is `cov = R.cov().values * TRADING_DAYS` with no shrinkage or
  eigenvalue treatment, fed straight into `port_var` at `:224`. This is **queue item 18**,
  opened 2026-08-28 and revisited 2026-09-12, and is deliberately not re-queued. Noting one
  thing item 18 does not: at the CLI default `--max-holdings 25` (`:369`) the optimiser sees
  N=25 against LOOKBACK=504 daily observations (`:52`), so T/N ≈ 20 and the conditioning
  problem at the *default* is mild. Item 18's premise holds, but its urgency at this call
  site is lower than the "200 names on 252 days" case it quotes from elsewhere.
- **Gap (verified, and this is the day's finding): the post-screen universe is chosen by
  spreadsheet row order and silent truncation.** `build()` at `portfolio_builder.py:285-286`
  does `universe = picks["triple"] + picks["coffee"] + picks["other"]`, dedupes, then
  `[:max_holdings]` — default 25 (`:369`). `load_picks()` (`:62-100`) builds each of those
  three lists by iterating the scan workbook's sheets in row order (`:72-75`, `:79-82`,
  `:90-98`) and **sorts by nothing** — not score, not conviction, not liquidity, not
  correlation. Two consequences, both unchecked anywhere in the repo: (a) if `Triple_Hits`
  alone holds 25 or more names, the Coffee Can and multi-screen buckets never reach the
  optimiser at all and nothing prints that they were dropped — `:287` prints only the final
  count; (b) which names survive inside a bucket is decided by whatever order the scan wrote
  the sheet. PS²'s whole thesis is that the post-screen selection step is where the work is,
  and that it should be done on the return covariance structure rather than arbitrarily. This
  repo's post-screen selection is `[:25]` on an unsorted concatenation. It is the same disease
  as the mailer's top-5 cut (2026-09-09 entry, queue item 27) at a different site, and it is
  cheaper to test here because the outcome is a portfolio with a measurable out-of-sample
  Sharpe rather than a shortlist.
- **Action queued: item 41.**
- **Not queued: adopting PS²/FPS² itself.** The Lasso-of-a-constant screen and the defactoring
  step are aimed at a universe of hundreds where sparsity is the binding constraint. At N=25
  post-screen there is nothing to sparsify — the repo's screen has already done the
  dimension reduction PS² performs. Take the question the paper asks, not its estimator.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2104.12484** (Xin Zhang, Lan Wu & Zhixue Chen, "Constructing long-short stock portfolio
  with a new listwise learn-to-rank algorithm", 2021-04-26) — generalises ListMLE under a
  Plackett-Luce model to weight both ends of the rank list; headline is a **38% annual return
  and Sharpe 2** on China A-shares 2006–2019 with 68 factors, and the fetched abs page
  mentions **no transaction costs at all**. Three strikes for this repo: a gross long/short
  return in a market the pipeline has ~0 instruments seeded for, a headline number with no
  cost model, and a trained listwise ranker the repo does not have and has already twice
  declined to build (2026-08-26, 2026-09-09). Discard.
- **Lin, Su & Zhu, "Empirical Asset Pricing via Learning-to-Rank" (SSRN 6348379, dated
  2026-01-20) — COULD NOT FETCH, carried forward.** SSRN returned **HTTP 403**, so nothing
  here is verified and no grade is assigned. Recording it only so the lead is not lost: search
  snippets describe 94 firm characteristics over 1964–2024 and a claim that the LTR *philosophy*
  applied to an **ordered logit** matches the best ML return-forecast models. If that holds it
  is the most on-scope LTR result the register has seen — an ordered logit is trainable on a
  Mac and explainable in an email, which LambdaMART and PRISM-VQ are not. Re-check on a future
  Wednesday for an open version; do not cite the snippet figures until a page is actually
  fetched.

## Added 2026-09-26 (daily task, Saturday gap query: correlation-matrix eigenvalues / regime / effective dimension)

Citation-following from hub 2605.19337 was dry: Semantic Scholar returned six citing papers
and all six are already registered (2609.19705, 2609.04917, 2608.26990, 2607.19453,
2607.04958, 2606.08285), plus one duplicate record with no arXiv ID. This is the second pass
on the Saturday theme. The theme-specific WebSearch came back mostly with papers already
registered (2607.19005, 2608.09641, 2212.05504, 1102.4076), so the new candidates came from
the q-fin.PM and q-fin.ST recent listings. That makes three search attempts and eight
candidates. Three were deep-read.

### 2609.27113 — Active Portfolio Management in Concentrated Equity Markets (Brian Ceco, Xiaofei Shi & Ting-Kam Leonard Wong, 2026-09-22, q-fin.PM)

Stochastic portfolio theory. The investor allocates actively between the equal-weighted
portfolio and the cap-weighted market, using forecasts from a mean-reverting stochastic
diversity–dispersion (SDD) model. Market diversity is φ_ew = Σ(1/n)·log μ_i, the log
geometric mean of cap weights. Dispersion is the weighted average stock variance minus the
portfolio variance. Frictions are handled with a quadratic surrogate, calibrated so its
cumulative wealth effect matches proportional costs.

- **EVIDENCE-GRADE: medium-strong.** Uses CRSP S&P 500 constituents from 1977 to 2024 with
  time-varying membership, monthly rebalancing, and an out-of-sample window of 1995–2024.
  Transaction costs of 15 bp proportional are **deducted from wealth** out of sample rather
  than only assumed. The paper reports higher net cumulative return than both the EW and
  cap-weighted benchmarks, and a higher IR than EW. It states its own limits: the model
  fits dispersion less well, and the out-of-sample tail in 2008–09 and 2020 is heavier.
  Point figures from the results table were **not** extracted; only the prose claims were
  fetched.
- **The finding that transfers is the premise, not the controller.** Whether EW beats
  cap-weighted depends on the regime. EW lags when concentration and correlation rise,
  especially in bubbles, and the paper notes US diversity is now at its lowest since the
  dot-com peak.
- **Gap (verified): the repo measures edge against two different benchmarks and never
  reconciles them.** The mailer's primary evidence is benchmarked against an
  **equal-weight market** (`justified_mailer.py:16-17`; the email prints "edge vs
  equal-weight market" at `:267`). The forward tracker scores the same picks against
  **cap-weighted** NIFTYBEES/SPY (`signal_tracker.py:174`). Nothing in the repo computes
  market diversity or concentration: a grep for
  `diversity|herfindahl|hhi|absorption_ratio|concentration` finds only portfolio-weight HHI
  (`bundle_validation.py:105`) and PPO factor-weight concentration. By this paper's
  mechanism, a screen whose 2016→2026 edge was measured against EW could show a smaller or
  opposite live edge against cap-weight in a concentrating market. The repo would record
  that as signal decay when it is really a benchmark-regime effect.
- **Action queued: item 42.**
- **Not queued: the FBSDE allocation controller itself.** It allocates between two index
  portfolios, and this pipeline holds neither.

### 2609.29530 — The Impossible Trinity of Time-Series Validation: A Conservation Law among Training Sufficiency, Test Coverage, and Temporal Causality (Jiayu Li, 2026-09-02, q-fin.ST)

Proves that training sufficiency α, test coverage β and causality cannot all be had:
α+β ≤ 1+Λ, and α+min{β,δ/T} ≤ 1. Under β-mixing, leakage bias is bounded by distance to the
nearest future training point, not by the amount of future data. Expanding walk-forward is
exactly the causal Pareto frontier. Purged k-fold with an embargo trades distance for
coverage. Recommendation: denominate gaps and embargoes as H + c·τ with c ≈ 2–3 (label
horizon plus 2–3× the dependence scale).

- **EVIDENCE-GRADE: strong theory, synthetic only.** No real-data application. The single
  experiment runs 1-NN on T=3000 i.i.d. noise with an H=20 overlapping label: shuffled 5-fold
  reports IC +0.318±0.012, contiguous 5-fold +0.004±0.012. That is a clean,
  fully-disclosed demonstration of the failure it names. No costs, which is appropriate for
  a validation paper.
- **Doing-right (verified):** `purge_embargo.py` implements label-window purging (`:85-103`)
  plus an embargo, defaulting to `EMBARGO_DAYS = 252`, the longest evaluated horizon (`:82`).
  The total gap is therefore horizon + embargo = 2H. That matches the paper's form when the
  dependence scale τ is below H/2, which holds for daily equity returns. The walk-forward in
  `train_ppo_walk_forward.py:22` uses an **expanding** train window, which the paper proves
  is the causal frontier. `walk_forward_backtest.py:174-175` splits strictly
  chronologically, 60/20/20.
- **Gap (verified, low severity): one shuffled split survives.** `pattern_discovery.py:285`
  calls `train_test_split(X, y, test_size=0.25, random_state=42)` with sklearn's default
  `shuffle=True`. The rows are one cross-section: `extract_features` builds one row per stock
  at a single as-of date, and `_target_fwd21` at `:224` is the same 21-day window for every
  row. So train and test share the **identical** label window, and the printed
  "Model fit: R²" (`:293`) is an in-window cross-sectional fit that absorbs that month's
  market and sector move. It is not an out-of-sample forecast. This is a stronger form of
  the paper's shuffled-fold failure: coverage in time is zero. The script is a research
  stage (`pipeline_historical.py:48,74`) and is not in the mailer's decision path, so the
  severity is low. `dl_strategy_eval.py:31` does cite "our earlier pattern_discovery" as
  evidence.
- **Action queued: item 43.**

### 2609.26303 — Target alignment, dilution and forecast selection when cross-sectional forecasts share a common target (Masoud Soleimani, 2026-09-22, q-fin.ST)

Every standardized cross-sectional forecast splits exactly into a part aligned with the
common realized target, γ_i = ⟨s_i, y⟩, and an orthogonal part. An equal-weight pool of N
beats the no-information forecast only if mean alignment exceeds ½[ρ̄ + (1−ρ̄)/N]. Adding a
forecaster at equal weight mixes real improvement with **dilution**, and equal-weight
admission can reward dilution. The paper proposes a cautious greedy admission rule using
HAC standard errors and a max-t critical value.

- **EVIDENCE-GRADE: medium, with an honest null.** It has two small panels. The first is
  24 LLM forecasters on 60 US large caps, weekly from Jan 2021 to Jun 2026. The second is
  9 mechanical signals (momentum, reversal, volatility and others) on 42 ETFs, monthly from
  2005 to 2026. Mean alignment is ≈0 in both (0.006 and −0.011). Selection removes most of
  the dilution loss, **but no combination beats the no-information forecast**, and the paper
  says so. No transaction costs, which is less of an issue for a forecast-combination result
  than for a strategy claim.
- **Gap (verified): the repo counts screen votes at equal weight, including screens its own
  evidence says are non-positive.** `full_us_market_scan.py:994-1003` computes
  `screens_passed` as an unweighted sum of six booleans: Darvas BREAKOUT_BUY, **Golden
  Cross / above-200DMA**, **Piotroski f_strong**, Coffee Can, MF and BC. It admits names with
  ≥3. The repo's own evidence file rules out Golden Cross ("worst screen in every tested
  market", `justified_mailer.py:26`) and records US high-F Piotroski as **INVERTED**
  (`:20`). In this paper's terms, those are forecasters with non-positive alignment admitted
  at equal weight into a vote. That is the dilution case exactly, and in the US one vote
  points the wrong way. The multi-screen sheet then feeds `portfolio_builder.py`'s "other"
  bucket (queue item 41).
- **Action queued: item 44.**
- **Not queued: the HAC/max-t admission rule.** With 6 screens and a boolean vote, a
  leave-one-screen-out forward-return comparison answers the same question with no new
  machinery.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2609.27051** (Qu, Chen & Wang, "Propose, Don't Judge: An Anytime-Valid Referee for LLM
  Agents That Mine Investment Factors", 2026-09-22). Rigorous: a frozen e-value referee,
  planted-truth synthetic data, and a 10-year CSI 500 walk-forward. It honestly reports the
  price, about 500 trading days to admit a true factor and a lower Sharpe than an ungated
  portfolio. Off-scope because it assumes an LLM or bandit factor miner, and this repo has
  none. Worth re-reading if factor mining is ever automated.
- **2609.29887** (Liu & Hsieh, "Cost-Sensitive Online Window Size Selection for Portfolio
  Management", 2026-09-24). Regret bounds for Fixed Share/Hedge over lookback-window
  "experts" with turnover-inclusive loss. The abstract gives no empirical universe, dates or
  net figures, and the repo sizes no rebalanced book. Not fetched further.
- **2407.20380** (Achitouv, "Inferring financial stock returns correlation from complex
  network analysis", 2024-07-29). Built on simulated GBM with a headline "up to 50%" better
  return "on short time scale". No costs and no real out-of-sample test in the abstract.
  Weak.
- **2112.15321** (Nick James, "Evolutionary correlation, regime switching, spectral dynamics
  and optimal trading strategies for cryptocurrencies and equities", 2021-12-31).
  Descriptive RMT/PCA comparison of crypto and equity spectra; the portfolio section is
  crypto-only with no costs. Off-scope.
- **2609.27614** (Wouters & Diks, "Model-agnostic noise reduction for high-dimensional time
  series data", 2026-09-23). A lagged-covariance projection onto a low-dimensional dynamic
  subspace, illustrated on stock returns, with forecast-accuracy metrics only. Background
  for queue items 37–39's spectrum work; not actioned.

## Added 2026-09-28 (daily task, Monday gap query: CPCV / purging / embargo)

### 2608.23416 — Li, "The Axiomatic Trader: Latent Regularity, Information Budgets, and the Canonical Form of a Quantitative Investment System" (v1 2026-08-24, v3 2026-09-20)

- **What it is:** five axioms, from which the paper derives a five-stage canonical system.
  The stages are a declared representation, a capacity-bounded predictor, contiguous
  purged/embargoed block evaluation aggregated by CVaR at level 1/Λ (Λ = the declared
  recurrence bound), a "budgeted deflated search" and robust sizing. The information budget
  is `log N ≲ ½ρ²·n_eff`, where `n_eff = n/(H + ρ²_blk(2ℓ−1) + 2π_μ)` and H is label
  overlap. Sizing is capped at `1/(1+ϰ)` of Kelly, where ϰ is the fraction of the budget
  already spent. It prefers an ensemble over training perturbations to a single fit.
- **EVIDENCE-GRADE: medium-weak.** The theory is careful. The empirics are "one real daily
  series" and "twenty assets, seven block lengths", and the fetched text gives no tickers,
  dates or transaction costs. The claim "no axiom is so far overturned" is a consistency
  check, not a return result.
- **Doing-right (verified):**
  - Purge+embargo gap: `purge_embargo.py:85-143`.
  - Lower-tail aggregation across folds, not mean: `trading_reward.py:92` sets
    `CVAR_Q = 0.30`, and `:165` defines `pessimistic()`, which takes the mean of the worst
    30% of folds. This is the paper's stage-3 aggregation, with a fixed q in place of 1/Λ.
  - Deflated search: `multiple_testing.py:46` `deflated_sharpe(sr, n_trials, n_obs, ...)`.
    `deflated_sharpe.py:65-85` gates at DSR ≥ 0.95.
- **Gap (already queued; no new item):**
  - The budget inequality is another form of what items 19 (MTRL) and 24 (cross-sweep trial
    ledger) already require.
  - The one new element is the H term. `deflated_sharpe.py:77` passes `T = best["n"]`
    formation weeks as the raw sample size. If the forward-return label is longer than the
    2-week step (IR is annualised with √26), overlap shrinks n_eff and the DSR is optimistic.
    **UNVERIFIED:** this run did not check the label horizon in `profitability_optimizer.py`.
    Check it when item 19 is picked up.
- **Not queued:** Kelly-fraction sizing. The repo sizes no live book.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2609.23703** (Kirtac, "Financial Language Models as Applied AI Systems for News-Based
  Trading under Market Frictions", 2026-09-20). Frictions are handled well: costs,
  capacity, and OOS restricted to news after the model's training cutoff. But it needs paid
  Refinitiv News Analytics and CRSP, and the repo has no news signal. `llm_extract.py:1-19`
  is document extraction for DRHP and broker statements, not a signal. Off-scope.
- **2609.26349** (Abi Jaber, Gutekunst, Herdegen, Hobson, "Optimal Investment and
  Consumption … Integrated Variance Clocks", 2026-09-23). Continuous-time control theory.
  Off-scope.
- **2609.27786** (Hashimoto & Stillman, "Feasible Multi-Asset Optimal Execution under Cash
  Constraints"). An execution-algorithm paper; the repo places no orders. Off-scope.
- **2609.31260 / 2609.31379 / 2609.29108:** agentic LOB phase transitions, DeFi mempool
  sandwich leakage, and EU electricity trading architecture. All off-scope by title and
  listing.

## Added 2026-09-29 (daily task, Tuesday gap query: effective number of factors / redundancy / spanning)

### 2609.31263 — Walter, Zimmer & Ulrich, "Taming the Option Factor Zoo: A High-Dimensional Analysis" (2026-09-25, q-fin.CP)

- **What it is:** 137 option-implied characteristics for optionable US stocks, Feb 2004 –
  Jul 2023 (T = 234 months). They are screened to 20 long-short factors by GBR+SHAP, keeping
  the top factors up to 90% cumulative attribution. Each factor is then tested against 160
  equity factors (Jensen et al. 2023) in four ways:
  - Stewart–Love redundancy index from CCA: 91.0% of option-factor variance explained,
    against a **mechanical noise level of p_X/(T−1) = 160/233 ≈ 69%**.
  - GRS joint-alpha test: p = 0.25.
  - Maximum Sharpe ratio 3.35 → 3.74, not significant.
  - Feng–Giglio–Xiu double-selection LASSO: 8 of 20 factors have non-zero SDF loadings at
    5%, and 4 survive Bonferroni (|t| > 3.02). BH and the Harvey–Liu–Zhu t > 3 hurdle are
    also reported.
- **EVIDENCE-GRADE: medium.**
  - For: the tests are rigorous and the multiple-testing correction is layered.
  - Against: all results are in-sample, and the screen and the tests use the same months
    (the authors say so). Returns are gross; the authors state they ignore transaction
    costs. The option data is CBOE and the equity data CRSP/Compustat, both paid.
  - The option factors themselves are unusable here: the repo has no option data.
- **Doing-right (verified):**
  - BH FDR across the whole grid: `code/python_files/multiple_testing.py:35`,
    `factorial_screener_analysis.py:10`.
  - A Bonferroni threshold: `code/python_files/rloo_rescore.py:553`.
  - A spectral effective-factor count (participation ratio):
    `research/factor_redundancy.py:18,42-52`.
- **Gap:**
  - The spanning test itself is already queued (items 12 and 35).
  - The new, transferable element is the **noise floor**. With p regressors and T
    observations, pure noise explains about p/(T−1) of the variance. The repo's fortnightly
    factor series are short, so an unbenchmarked R² or redundancy figure will overstate
    redundancy. For example, 9 regressors over T = 40 gives a noise floor near 23%.
  - `factor_redundancy.py` reports its participation ratio with no noise benchmark
    (`:60-68`). It works on the pooled stock-week feature matrix, where n is large, so the
    floor matters there far less than for item 12's date-level series.
- **Action queued:** item 45, an amendment to items 12 and 35.
- **Not queued:** the GBR+SHAP screen. The repo has 10 factors, not 137, so there is
  nothing to screen.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2402.06635** (Kelly, Kuznetsov, Malamud & Zhang, "Large and Deep Factor Models", v3
  2026-06-29). A DNN-trained SDF via the Portfolio Tangent Kernel, on US equity data. It
  needs deep-network training and CRSP-scale data, and the abstract gives no universe,
  period or costs. Off-scope at this pipeline's scale.
- **2509.25606** ("Effective Model Pruning: Measure the Redundancy of …"). A neural-network
  pruning paper, surfaced by the keyword "redundancy". Off-scope by title.
- Semantic Scholar citations of 2605.19337 (six distinct) and the q-fin.PM/q-fin.TR recent
  listings: every entry was already registered.

## Added 2026-09-30 (daily task, Wednesday gap query: learning-to-rank cross-sectional equity returns)

Semantic Scholar's API returned HTTP 429 to curl. The same query through WebFetch listed
the same six citing papers as on 2026-09-23 (2609.19705, 2609.04917, 2608.26990,
2607.19453, 2607.04958, 2606.08285). None is new. The Wednesday WebSearch returned nine
already-registered IDs and one new one (1909.04497). Most candidates came from the recent
listings for q-fin.PM, q-fin.TR and q-fin.ST. Neither paper deep-read today is about
learning to rank. The theme has now run dry on four Wednesdays.

### 2609.35359 — From Cointegration to Out-of-Sample Failure: A Pairs-Trading Case Study on PEP-KO (Davide Graziano, submitted 2026-09-28)

This is one PEP–KO pair on daily adjusted closes, split three ways:
- **Statistics, 2013–2018.** Engle–Granger test. Half-life ≈ 31.9 trading days,
  β̂ = 1.662.
- **In-sample threshold optimisation, 2018–2023.** Best thresholds z_entry = 2.15 and
  z_exit = 0.50, with 0.20% costs. **Sharpe 0.67** over 99 trades.
- **Out-of-sample, 2023 to date.** All three variants lose money:
  - static: Sharpe −1.19
  - rolling OLS: Sharpe −1.05
  - Kalman: Sharpe −0.88
- **Post-hoc check on the OOS window.** Engle–Granger gives p = 0.12, and the hedge ratio
  reverses sign to β̂ = −0.24.

- **EVIDENCE-GRADE: medium on method, weak on generality (n = 1 pair).** It is graded up
  for doing the cost, sensitivity, walk-forward and deflation work, and for printing the
  result against itself.
  - Adjusted Sharpe (skew/kurtosis-corrected): **0.281**, against 0.67 raw.
  - Deflated Sharpe: **0.423**, with N = 901 policies.
  - **Without Feb–Apr 2020, the in-sample Sharpe falls from 0.67 to 0.28.**
  - Walk-forward folds are uneven. Fold 1 has Sharpe 2.14; folds 2 and 3 are one losing
    trade each.
- **Doing-right (verified):**
  - The repo already deflates its selected factor. `code/python_files/deflated_sharpe.py:52`
    has `dsr()`, `:42` has E[max SR] over the trials, and `:80` gates at 0.95.
  - `multiple_testing.py:46` carries a second implementation.
  - The repo runs no pairs strategy. `pattern_discovery.py:306-330` only lists pairs with
    return correlation > 0.80 as "pairs-trade candidates", in a historical stage
    (`pipeline_historical.py:48`).
- **Gap 1: the DSR is computed as if returns were normal.**
  - The call at `deflated_sharpe.py:78` is `dsr(sr_best, trials_sr, T)`, so skew = 0 and
    kurt = 3 take their defaults (`:52`). The docstring admits this (`:16-17`).
  - `reports/profitability_optimizer.csv` only carries
    `mean_excess, info_ratio, mean_book, hit, n`. No higher moments are available to pass
    in.
  - The paper shows the size of the error: fat tails alone cut its Sharpe by more than half
    (0.67 → 0.281).
  - Item 19 (MTRL) reuses the same bracket, so it inherits the same assumption.
- **Gap 2: no check that one window carries the result.** A grep for leave-one-window-out,
  crisis exclusion or best-N-periods sensitivity found nothing in `code/` or `research/`.
  The nearest thing is the sub-period tables in `smallcap_screener.py:232` and
  `sector_rotation.py:139`.
- **Minor:** `pattern_discovery.py:306-330` selects pairs by correlation, not
  cointegration. The paper shows that even a cointegrated pair can break out of sample.
  Nothing is queued for this: the stage is exploratory and it does not reach the mailer.
- **Action queued:** item 46.

### 2609.33524 — EverMine: Dissecting the Self-Evolution of Research Capabilities in Long-Horizon Alpha Research (Siyuan Li, Jiangfeng Zhang, Rui Yao, Weihua Qiu, Mingyang Xu, Zixuan Yuan, submitted 2026-09-27)

This is an LLM-agent alpha-mining study. The data is Binance Spot USDT, 60 pairs by
turnover, predicting 10-minute bars. Development runs 2025-01-01 to 2025-12-31 and OOS
2026-01-01 to 2026-06-30. The model is a 30-factor portfolio scored by IC. Costs are not
modelled.
- Evolving the agent's "capabilities" gave no consistent gain across 18 trajectories or 48
  continuation branches.
- Tuning parameters of factors already in the portfolio produced 12.8–40.0% of net
  improvement, and was positive in 16 of 18 trajectories.
- A factor's marginal value depends on the current portfolio and on submission order.
  Screened-out candidates, submitted in sequence, *lowered* final IC.
- **EVIDENCE-GRADE: weak for this pipeline.** The data is crypto intraday, costs are not
  modelled, and the order effects are tiny: ΔIC −0.0000175 and −0.0000067, well inside
  noise.
  - The honest null on "self-evolution" is a useful sanity note for the repo's agentic
    tooling.
  - The transferable point is conditional marginal value. The repo has no sequential
    factor-admission loop: a grep for marginal IC, forward selection or greedy addition
    found only `train_ppo_factor_weights.py:154`, a per-regime single-best-factor baseline.
- **Action queued:** none.

### Weak/off-scope, one line each (triaged, not deep-read)

- **1909.04497** (Wu et al., "Equity2Vec", v2 2021-10-27). A graph DL model with a news
  input. The abstract gives no universe, period or costs, and the model needs GPU training
  and a news feed. Off-scope.
- **2609.34169** (Foley et al., "From Word Counts to Context: Topic Models for Asset
  Pricing", 2026-09-28). Sentence-transformer versus LDA on 394,661 news articles, with a
  Sharpe of 1.03. The authors say their "available tests do not establish outperformance"
  and call for stricter point-in-time tests. It also needs a news corpus.
- **2609.35086** (Koa, Li & Huang, "RADAR", 2026-09-28). Retrieval-augmented diffusion for
  SDF portfolios. It claims "state-of-the-art" with no universe or costs in the abstract,
  and needs GPU training.
- **2609.33058** (Aldridge, "Evolution of Market Microstructure in the Age of AI",
  2026-09-27). A microstructure/HFT/AMM survey. Off-scope for an EOD screener.
- Listed but not triaged, off-scope by title: 2609.27654 (FedIncome), 2609.32686
  (reinsurance), 2609.32848 (CME HFT), 2609.33767 (option Greeks), 2609.33799 (CFMM),
  2609.35063 (liquidation), 2609.36257 (option replication), 2609.37872 (latent
  liquidity), 2609.37963 (AMM LPs).

## Added 2026-10-01 (daily task, Thursday gap query: transaction-cost-aware factor evaluation)

Semantic Scholar (via WebFetch) listed the same six papers citing the hub 2605.19337 as on
2026-09-30; none is new. The Thursday WebSearch returned seven already-registered IDs plus
Baldi-Lanfranchi (registered 2026-08-27) and one new ID (2604.04812). The q-fin.PM and
q-fin.TR recent listings added five new IDs. Nothing new is on the day's theme itself:
the cost-aware-factor literature reachable by free search appears exhausted after five
Thursdays.

### 2604.04812 — SysTradeBench: An Iterative Build-Test-Patch Benchmark for Strategy-to-Code Trading Systems with Drift-Aware Diagnostics (Yuchen Cao, Hanlin Zhang, Jacky Wai Keung, Yang Chen, Linqi Song, submitted 2026-04-06)

This benchmark scores LLM-generated trading code: 17 models, 12 strategies, 14 instruments
(5 US large caps daily, 3 crypto pairs at 1-min, CSI300 + 5 constituents). Train/Dev runs
2024-01-01 to 2025-01-01 and Test 2025. Gates: Parse → Schema → Exec → Determinism →
Anti-Leak → Audit.
- 61.8% of submissions pass every gate (parse alone: 78.4%). High-complexity strategies
  fail 35–71% of the time (Spearman ρ = −0.68).
- **Determinism gate:** 3 reruns with different seeds. SHA256 over the trade list
  (entry, exit, side, pnl) must match, with 1e-6 tolerance on floats.
- **Anti-leak gate:** an AST scan flags `shift(-k)` / forward indexing (a warning only).
  A runtime `LeakageGuard` proxy over the market data raises if code reads past the
  current bar, and that is a hard fail.
- **Rule drift:** canonicalised strategy-card checksums, plus action-trace edit distance on
  50-bar synthetic data (Δ ≥ 0.15 flagged).
- **EVIDENCE-GRADE: weak as trading evidence, useful as software method.** The OOS check
  is 235 sampled 10-bar windows at **zero cost**. The 0.1–20 bp sweep is "deferred to
  future work". The paper does not report leakage or nondeterminism rates. It offers no
  trading result to rely on, and none is taken from it.
- **Doing-right (verified):**
  - Threshold drift is hash-gated: `eval_contract.py:116,123-126,129-133`. The
    threshold values are SHA256-digested and `verify()` raises `ContractViolation` if
    they move without the recorded hash being updated. This is the same idea as the
    paper's strategy-card checksum.
  - A static grep for `shift(-` finds only research backtests building forward-return
    labels (e.g. `backtest_ccc.py:240`, `value_quality_ls_backtest.py:88`,
    `rloo_rescore.py:288`). It finds none in `custom_screener.py`, `price_bands.py`,
    `build_mailer.py` or `signal_tracker.py`. The AST layer would add nothing beyond
    that grep.
- **Gap:**
  - No runtime look-ahead test exists. `test_pipeline_invariants.py`, `test_strategies.py`,
    `test_eval_contract.py` and `test_screener_in.py` are the repo's test files, and the
    only "future" hit in them is EDGAR future instants (`test_pipeline_invariants.py:148`).
  - Nothing checks that the production scorer's picks for date *t* are unchanged when
    every bar after *t* is deleted.
  - Nothing reruns a scan and compares hashes. A grep for determinism/rerun/sha256 hit
    only `eval_contract.py` and the PPO `deterministic=True` flags.
  - Queue item 11 (2607.04958) labels availability-time sites; it does not test them.
- **Action queued:** item 47.

### Weak/off-scope, one line each (triaged, not deep-read)

- **2609.39261** (Yuan, Zhang & Su, "Jacobian Rank Collapse in Decision-Focused Learning",
  2026-09-30). Mostly ML theory. Its one equity result is a null: across 38 one-parameter
  index-tracking configs, DFL beats MSE by under 1.8%. No universe, period or costs are
  given in the abstract.
- **2609.38545** (Alzahrani, "Say, Echo, Do", 2026-09-29). The narrative-vs-positioning
  model is tested only in 29 *simulated* markets (AUC 0.90), and it needs a news corpus.
- **2609.39420** (Chernysh, Ekhtibarov & Zmitrovich, "QuantCode Model", 2026-09-30). This
  is a 35B–397B LLM fine-tune for Backtrader code generation. The metric is Judge Pass
  rate, with no trading evaluation; it needs GPU training.
- Listed but not triaged, off-scope by title: 2609.39569 (tontines), 2609.38765 (bond
  portfolio MDP).

## Added 2026-10-02 (daily task, Friday gap query: point-in-time fundamentals / survivorship bias)

Semantic Scholar (via WebFetch) still lists the same six papers citing the hub 2605.19337,
all of them already registered. The Friday WebSearch returned five registered IDs and three
new candidates. One of them passed triage.

### 2603.19380 — Survivorship Bias in Emerging Market Small-Cap Indices: Evidence from India's NIFTY Smallcap 250 (Harjot Singh Ranse, submitted 2026-03-19)

The paper rebuilds historical index membership from 2,459 NSE bhavcopy files
(2016-09-01 to 2025-09-30, sourced from Samco's public archive). Bhavcopies keep delisted
names. The universe is ranked 151–400, with **daily traded value used as a proxy for
market cap**. It then compares two daily-rebalanced equal-weight portfolios: the 252 current
survivors against all 1,437 stocks ever in the reconstructed index. The survivors return
26.17%/yr, the full set 21.23% (+4.94pp). Sharpe is 1.160 against 1.063. Of the stocks that
left the index, 16.1% delisted, 33.1% graduated and 33.2% were demoted. The paper itself
says these are "no transaction costs, no slippage" constituent returns (PDF l.1056).
- **Evidence grade: moderate-to-weak.**
  - The traded-value ranking is said to match today's list "100% (252 of 252)". That is the
    only ground truth available, and it is in-sample. The "85-90%" historical accuracy is an
    estimate with no reference to check it against.
  - The significance claim contradicts itself. The survivor return "exceeds 97.8% of
    resamples", which implies p≈0.022, yet the paper prints "p < 0.001" (PDF l.585).
  - The paper says delisting returns were inferred from last traded prices (l.1149).
  - The direction of the bias and the bhavcopy-panel method are sound.
- **Doing-right:** the repo already applies this paper's lesson, and more strictly.
  `code/python_files/smallcap_screener.py:20-36` validates its rules only on the price panel
  that keeps delisted names (DENABANK, DHFL, DISHMAN), approximates the small-cap band
  point-in-time by trailing turnover rank, and explicitly refuses to backtest the current
  constituent list. It also records that a market-cap reconstruction reproduces today's list
  at only **71%** (`smallcap_screener.py:34`). That makes the paper's 100% match with a
  similar liquidity proxy look tuned, not validated. `price_band_migration.py:23`
  reports survivorship instead of dropping it.
- **Gap:** none that is actionable. Real point-in-time membership would need NSE's
  index-maintenance announcements, which the repo already flags as a separate collection job
  (`smallcap_screener.py:34-36`).
- **Action queued:** none.
