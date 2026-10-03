# Backtest Queue

Concrete, paper-motivated changes ready to test — populated by literature review,
consumed by hand (this file is never executed automatically). Each item traces to
a LITERATURE_REGISTER.md entry. Move an item to DONE with a one-line result link
when it's been run; do not delete history.

## Queued, priority order

1. ~~**Factor redundancy measurement**~~ — **DONE 2026-08-23**, see `research/factor_redundancy.py`
   / `factor_redundancy.md`. Participation ratio **4.92 of 10** (IN) / **4.53 of 10** (US) —
   the 10-factor set carries roughly HALF the information a truly independent set would.
   Worst pairs: golden_cross×breakout (r=+0.66/+0.65), plus the documented AND-combinations
   (lowvol×qual_mom r=+0.55–0.61, lowvol×def_revert r=+0.56). 263K/261K obs each.

2. **Ranking reformulation** — cross-sectional percentile cut replacing the fixed
   `pio >= 7` gate at `build_mailer.py:227`, keeping existing sort/top-15 truncation.
   Motivated by: 1809.09441 (RSR). Test via `factor_learning.py:62 ls_book_ir`.

3. ~~**Regime gate via correlation spectrum**~~ — **MEASURED 2026-08-23** (not yet
   gated — log-first per item 9's own instruction), see `research/correlation_regime_spectrum.py`
   / `.csv`. 150-symbol NSE universe, rolling 60d windows, 10.5y. Participation ratio
   ranges 3.5–24.1 (mean 12.3); the 5 LOWEST-PR windows in the entire 10.5-year sample
   are all March–May 2020 (COVID). Independent sanity check passed: mean PR during
   Feb–May 2020 = 6.0 vs Jun–Dec 2019 calm period = 9.4, PC1 absorbs 50–53% of variance
   at the crash's worst point vs 14–15% in the calmest windows. The metric carries real
   information the current gate (EMA-vs-index + vol percentile) does not have. Next step
   if pursued: decide a threshold and backtest it as an actual gate, not just log it.

4. **Wire execution_cost_model.py in** — currently imported by nothing
   (`grep -rl execution_cost_model` returns only its own file). Almgren-Chriss
   square-root impact + 15% ADV cap already implemented. Every paper reviewed this
   week shares the same flaw the repo could actually fix. Motivated by: nearly
   every paper in the register (gross-of-cost is the single most repeated
   evidence-grade problem found).

5. **Fundamental screens on `public.global_fundamentals`** — 111,411 US rows to
   1987, 14 markets, `filed` column available for real point-in-time discipline
   (not the FYE+90d proxy currently used in `pe_bands.py:82-93`). Deferred from
   2026-08-22 session for scope. Larger effort — schema/PIT-discipline work first.

6. **Purge+embargo function — NOT full CPCV** on `signal_tracker.py` and the gap
   in item 10. **RESEARCHED 2026-08-23** by 4 parallel agents (theory, critique,
   empirical, implementation) — see LITERATURE_REGISTER.md "CPCV/embargo" section
   for full sourcing. All four independently converged on the same conclusion:
   - **Purging rule** (AFML Ch.7 §7.4.1, p.105): drop any training row whose
     LABEL window overlaps a test row's label window — not just overlapping
     timestamps, overlapping *label formation periods*.
   - **Embargo length**: no single literature formula. mlfinlab's reference
     default is a % of the dataset (horizon-agnostic); ORCA (2604.17251) uses
     embargo = horizon (10d gap for a 10d target) but does NOT ablate it — one
     number reported, gap already baked in, not a before/after comparison
     (corrects the earlier register entry, which implied an ablation existed).
     Given the repo's own longest horizon is 252 trading days, **embargo = 252
     trading days is the conservative, source-justified choice** — apply the
     rule "≥ longest evaluated horizon", not the previously-guessed 21 days.
   - **CPCV's real value-add is a Sharpe *distribution* across C(N,k) combinatorial
     paths for detecting backtest overfitting** — NOT leakage prevention, which
     purge+embargo alone already solves. Cost grows fast (C(20,10)≈184,756 splits).
   - **CPCV is necessary-but-not-sufficient anyway**: it cannot catch selection
     bias across strategy configurations — that needs the deflated Sharpe ratio,
     which `deflated_sharpe.py` ALREADY implements here. Pairing purge+embargo
     with disciplined DSR bookkeeping (deflate by every configuration actually
     tried) is the better-justified addition than building full CPCV machinery.
   - mlfinlab (the reference implementation) is DEAD for reuse — closed-source,
     pulled from PyPI. `sklearn.model_selection.TimeSeriesSplit(gap=...)` is real
     (confirmed on the installed sklearn 1.9.0) but only a fixed-index-count gap,
     not label-horizon-aware purging — usable as a low-level primitive only.
     Hand-build: ~40-80 lines for purge+embargo, ~150-250 for full CPCV.
   **ACTION: hand-build a ~40-80 line purge+embargo function (embargo=252d),
   wire it into `signal_tracker.py`'s outcome-counting and item 10's
   walk-forward gap. Do not build full CPCV as a first move.**
   Motivated by: 2605.19337 §13.1.2 (original prompt), AFML Ch.7/12, 2604.17251,
   Arian/Norouzi M./Seco 2024 (Knowledge-Based Systems), eslazarev/purged-cross-validation.

7. **chop+HIGH-vol regime gate** — currently a warning string in the brief
   (`build_mailer.py:434`), not a hard demotion. Motivated by: 2607.15414.

8. **Sentiment relevance scoring, not gating** — turn the hard ticker-match gate
   in `sentiment_pipeline.py:443-452` into a relevance score multiplied into the
   existing provider-weighted mean (`:519-526`). Motivated by: 2603.19286.
   Coverage caveat: IN/US only.

9. **Spectral descriptors from the nightly correlation matrix** — sharpens and
   supersedes item 3 by giving it exact formulas. `market_correlation_scan.py`
   already builds the matrix (`:168` full-universe, `:311` MST path) and discards
   it after writing CSVs. One `np.linalg.eigvalsh` on that same matrix yields, in
   a few lines: absorption ratio AR_k (k∈{1,3,5}), eigenvalue entropy H, effective
   rank ER=exp(H), spectral gap λ₁/λ₂, condition number λ₁/λₙ, Marchenko–Pastur
   excess λ₁−(1+√(n/T))², and m⁻ = count of eigenvalues below (1−√(n/T))².
   Log them as a daily time series first; only then consider gating on them.
   Motivated by: 2604.17251 (upper spectrum), 2608.09641 (m⁻, lower spectrum),
   2607.19005. Cheap — no new data, no new fetch.

10. **Anti-leakage gap in the walk-forward split** — `walk_forward_backtest.py:173-181`
    splits 60/20/20 strictly chronologically with a zero-day gap: `test_start` is
    the next trading day after train ends, while forward returns are measured over
    8 horizons. Insert a gap equal to the longest evaluated horizon between each
    boundary and re-run to measure how much of the reported edge was overlap.
    Motivated by: 2604.17251 (10-day gap matched to a 10-day horizon). Complements
    item 6 (which covers the forward log, not the backtester).

11. **Availability-time vs reference-time column annotation** — audit every
    fundamentals read for whether it keys on when a datum was *available* or when
    it *refers to*. `pe_bands.py:82-93` already uses an FYE+90d availability proxy;
    the point-in-time `filed` column in item 5 is the real fix for that one site.
    The queued work is the cheap part: enumerate the sites and label them, so the
    discipline is checkable rather than folklore. Motivated by: 2607.04958.
    Explicitly NOT adopting the paper's type-and-effect system — out of scope.

12. **Factor spanning test on the 10-factor set** — regress each of the 10 `FACTORS`
    (`factor_learning.py:37`) on the other nine and report the intercept α with its
    t-stat; a factor whose α is insignificant is spanned by the rest and is a drop
    candidate. Reuse the exact feature matrix `research/factor_redundancy.py` already
    builds (`:64-65`) — no new data. Sharpens item 1: that item *counted* redundancy
    (PR 4.92/10 IN, 4.53/10 US), this one *names* which factors are redundant and
    attaches significance. Note the repo currently has no spanning test at all
    (`grep -rniE 'spanning.test|stepwise|orthogonaliz|residualiz|variance_inflation'
    --include='*.py'` = 0 hits); `LassoCV` at `factor_learning.py:88` is L1 shrinkage,
    not a spanning test — it yields no t-stat and answers a different question.
    Motivated by: 2601.10279 (Feng/Lan/Wang/Zhang, Management Science).

13. **Rolling factor redundancy — is 4.92/10 stable or a two-regime average?**
    `research/factor_redundancy.py:65` computes ONE `df.corr()` over the whole pooled
    panel, so item 1's headline is a full-sample point estimate with no time variation.
    2111.05072 finds the causal network among 11 US risk factors sparsifies long-term
    but **densifies under stress**, collapsing toward pure market exposure. Concrete
    test: apply the rolling-window loop already written in
    `research/correlation_regime_spectrum.py` (currently pointed at the 150-symbol NSE
    *stock* matrix) to the 10-factor matrix instead, and plot participation ratio over
    time. Falsifiable prediction to check: PR dips sharply in Mar–May 2020, the same
    windows item 3 already flagged as the 5 lowest-PR stock-correlation windows in
    10.5y. If it holds, the factor set is least diversified exactly when it matters
    most. Cheap — both halves of the code already exist, no new data or fetch.
    Motivated by: 2111.05072 (D'Acunto et al.), complements items 1, 3 and 9.

14. **Third purge+embargo site: `LassoCV(cv=5)` at `factor_learning.py:88`** — the
    outer 60/40 train/test split (`:84-85`) is chronologically clean, but the inner
    penalty-path CV is plain 5-fold KFold, so α is tuned on folds that sit *after* the
    fold being scored. Swap for a purged/embargoed splitter (or at minimum
    `TimeSeriesSplit`) once item 6's function exists. Not a new investigation — this is
    a previously-unnamed third site for the function item 6 already specifies
    (alongside `signal_tracker.py` and item 10's walk-forward gap). Found incidentally
    while grep-verifying item 12 on 2026-08-25.

15. **Limit-locked / untradable-bar guard beyond KR** — `_flag_stale_halted_days()` at
    `factorial_screener_test_KR.py:119` exists only in the KR screener
    (`grep -rln '_flag_stale_halted_days' --include='*.py'` → one file), yet India is
    the market with statutory daily price bands (±5/10/20%). 2507.07107 measures what
    this costs on a limit-band market: computing factors over closes nobody could
    transact at inflates IC by **18%** and cuts realized Sharpe by **0.44**. Concrete
    test, cheap and data-free: from the existing IN OHLCV panel, flag bars where
    (a) `Volume == 0`, or (b) `High == Low` (limit-locked, zero intraday range), or
    (c) `|Close/prev_Close - 1|` sits within ~0.3% of 5/10/20%. Count the flagged share
    per market, then re-run one settled screener backtest twice — once as-is, once with
    flagged bars excluded from signal formation — and report the IC and Sharpe delta.
    Falsifiable prediction: if Du's mechanism transfers, IN shows the largest degradation
    and US/EU (no daily bands) show ~none, which would also tell us whether the
    India-only edge in the validated-edge registry is partly this artefact. Secondary,
    one-line fix regardless of outcome: `backtest_liquidity_forward.py:74` filters
    `Volume >= 0` where `cost_vs_edge.py:130`, `backtest_piotroski_plus.py:77` and
    `daily_breakout_combo_us.py:82` all use `Volume > 0` — make it consistent.
    Motivated by: 2507.07107 (Du). Independent of items 1/3/9/12 (factor redundancy)
    and of items 6/10/14 (purge+embargo) — this is a data-hygiene item, not a
    validation-protocol one.

16. **Is momentum's net-of-cost failure a premium problem or a churn problem?** —
    Baldi-Lanfranchi (2024) shows TCU momentum (full rebalance to target every period)
    earns 0.64%/mo gross, pays 63bps/mo in costs, and nets 0.01%/mo — while the *same*
    signal traded at an optimized partial intensity pays 30bps/mo and nets 22x more,
    lifting annualized net Sharpe by 0.19. This repo measured momentum 12-1 at -14.11%
    vs bench (IN, n=3,541) and -15.08% (US, n=17,606) on 2026-08-23 and filed it as "no
    edge". That test used the full-rebalance form. Concrete, cheap test that does NOT
    require building a portfolio-construction layer: re-run the existing momentum 12-1
    backtest with a **hold-through rule** — once a name is in the top decile, keep it
    until it falls below a wider exit band (e.g. top 30%) instead of re-forming the
    basket from scratch each period — and report gross return, realized turnover, and
    net return for the standard form vs each of 2-3 band widths. Falsifiable prediction:
    if the paper's mechanism transfers, gross return falls modestly while turnover (and
    hence the cost drag at the repo's 0.2% round-trip, `backtest_screeners.py:176`) falls
    much faster, so the net gap to benchmark narrows. If net barely moves, momentum's
    failure here is a genuinely absent premium and the question is settled — which is a
    useful result either way. Explicitly OUT of scope: implementing TCA factors properly
    (needs a weight vector and an optimizer over trading intensity; this repo is
    signal-only with no execution layer). Related: the watchlist mailer's >5-session
    eviction rule is the repo's existing frequency heuristic and is the natural second
    place to apply the same measurement.
    Motivated by: Baldi-Lanfranchi (2024), Transaction-cost-aware Factors.

17. **Full-sample winsorization thresholds in the factorial-screener OLS** —
    2604.07880 quantifies what full-sample filtering thresholds do to a factor zoo: the
    6-month bond momentum premium of 0.30%/mo is *entirely* an artifact of ex-post
    winsorization, and across 432 specifications only 26 (6.0%) survive BH-FDR
    correction. This repo already gets it right in the two places that matter most —
    entry is the next bar, not the signal bar (`backtest_screeners.py:293`), which
    structurally prevents the correlated errors-in-variables half; and `rloo_rescore.py:291`
    `winsorize_xs()` clips within each day's own cross-section (`axis=1` at `:309-310`).
    But three sites still compute clip bounds from the whole pooled sample:
    `factorial_screener_analysis.py:97-107` (live at `:111`, feeding the OLS),
    `train_ppo_factor_weights.py:132-133`, and `factor_zscore_panel.py:45-46` (which
    explicitly adopts the same convention). Concrete test: re-fit
    `fit_factorial()` twice — once as-is, once with the clip bounds computed
    **within each formation year's own cross-section** (the `rloo_rescore.py:291` pattern,
    which already exists and is tested) — and report the coefficient, HC3 standard error
    and BH-adjusted p-value for every screener x horizon under both. Falsifiable
    prediction: if the effect is real, coefficients move within noise; if any screener's
    significance depends on pooled-sample bounds, that screener's effect is partly an
    artifact and should be re-graded. NOTE — do not overstate this: the repo's
    winsorization is **symmetric** (1/99 both tails), while the paper's fatal case is
    **asymmetric** filtering. The hazard being tested is the full-sample threshold alone,
    which is the milder member of the same family. Cheap: no new data, no fetch, one
    changed function and a re-fit. Secondary: `train_ppo_factor_weights.py:132` sits
    upstream of an RL training run, so a pooled bound there leaks across the
    chronological split made just below it at `:141`.
    Motivated by: 2604.07880 (Dickerson, Robotti & Rossetti). Independent of items
    6/10/14 (purge+embargo) and 15 (untradable bars) — this is a threshold-provenance
    item, adjacent to 15's data-hygiene family.

18. **Raw sample covariance in both optimisers — no eigenvalue treatment** —
    `portfolio_builder.py:217` computes `cov = R.cov().values * TRADING_DAYS` and feeds it
    unfiltered into `port_var = lambda w: w @ cov @ w` at `:222`; `mutual_fund_theorem.py:107`
    does the identical thing. The repo's only shrinkage is on *expected returns*
    (`_expected_returns()`, `portfolio_builder.py:190-200`, James-Stein toward the
    cross-sectional mean) — Sigma is never touched. `mutual_fund_theorem.py:156` already
    prints "without shrinkage (Ledoit-Wolf) or hard position constraints" as a warning when
    half-sample turnover exceeds 0.5, so this is a self-diagnosed gap that was never closed.
    Concrete test: re-run `optimise()` three ways on the same panel — raw `R.cov()` as-is,
    `sklearn.covariance.LedoitWolf` linear shrinkage, and a frozen-eigenvalue estimator
    (spectrum estimated once on the earliest third of the sample and held fixed for the
    rest, the paper's "Average Oracle") — and report, for each, out-of-sample realized
    volatility, max drawdown, Sharpe **and turnover**. Falsifiable prediction: if the
    warning at `:156` is right, raw-sample min-variance weights should show materially
    higher out-of-sample realized volatility and turnover than either shrunk version; if
    they do not, the warning is over-cautious and should be re-worded. 🔴 Turnover is not
    optional in this comparison — 2507.01918's own neural estimator wins on variance
    (Sharpe 1.011 vs QIS 0.942) while running 112% turnover per 5 days against QIS's 44%,
    which is how a lower-variance estimator loses money net of cost. Cheap: no new data,
    no fetch, no training; sklearn is already a dependency and the frozen-eigenvalue
    variant is ~15 lines of numpy. Note the standing caution from 2605.30464 (logged
    2026-08-28), whose headline negative result was that plain Ledoit-Wolf shrinkage beat
    every distributional method it tested — consistent with, not duplicative of, this item.
    Motivated by: 2507.01918 (Bongiorno, Manolakis & Mantegna). Independent of item 9
    (spectral descriptors as a *regime signal*) — this is Sigma-as-optimiser-input, a
    different use of the same matrix.

19. **Minimum Track Record Length — is the existing DSR gate resting on enough history?** —
    `deflated_sharpe.py:52` computes the deflated Sharpe and `:81` gates it at
    `survives = d >= 0.95`, writing `✅ real` / `⚠️ fragile` verdicts into
    `reports/deflated_sharpe.md` (`:104-107`). But `T` at `:77` is just `best["n"]`,
    formation weeks, passed straight into the DSR and never itself checked. DSR answers
    "did the winner beat the best-of-N benchmark"; it does not answer "is this sample long
    enough for that comparison to be stable." MTRL (Bailey & López de Prado) is the
    companion statistic and is about ten lines of the arithmetic already sitting in this
    file: `MTRL = 1 + [1 - skew*SR + (kurt-1)/4 * SR^2] * (Z_alpha / SR)^2`, i.e. the same
    bracket already computed as `denom**2` at `deflated_sharpe.py:57`. Concrete test:
    compute MTRL per market x regime, put it next to the `T_weeks` column already written
    to `reports/deflated_sharpe.csv` (`:82`), and flag every row whose DSR passed on fewer
    observations than its own MTRL requires. Falsifiable prediction: bear-regime rows have
    materially fewer formation weeks than bull rows, so if any bear cell currently carries
    `✅ real` while T_weeks < MTRL, that label is unearned and the report's verdict column
    is overstating its own evidence. Cheap: no new data, no fetch, no refit — one function
    and one extra column. Motivated by: 2608.23808 (Santoni, Jouanne & Scullin), whose
    MTRL gate is one of the three the repo lacks entirely.

20. **`overfitting_report()` is labelled PBO but computes Sharpe decay — replace it with
    real CSCV, or fix the citation** — `walk_forward_backtest.py:1086` cites "Bailey et al.
    (2014) — 'Probability of Backtest Overfitting'" on a function (`:1082`) that computes
    `decay = (train - val)/abs(train)*100` from per-split mean Sharpe (`:1094-1096`) and
    buckets it at hardcoded 50%/20% thresholds (`:1111-1116`). PBO is a different
    statistic: split the trial matrix into S even blocks, and over the C(S, S/2)
    train/test partitions record the out-of-sample rank of whichever configuration was
    best in-sample; PBO is the fraction of partitions where that rank falls below the
    median. The repo already has the required input — the market x regime x factor
    info-ratio matrix in `reports/profitability_optimizer.csv`, the same file
    `deflated_sharpe.py:65` reads. At S=8 that is C(8,4)=70 partitions, ~30 lines with
    `itertools.combinations`, no new data. Concrete test: compute real PBO on that matrix
    and compare its verdict against the existing `Overfit_Risk` HIGH/MEDIUM/LOW labels —
    if they disagree, the current thresholds are miscalibrated and the strategy matrix at
    `:1120` is selecting on a decay number that does not mean what its docstring claims.
    While in this function, also add **fold-level profitability** (share of splits with
    positive return) beside the mean-Sharpe columns — 2512.12924 reports 41% (14 of 34
    folds) next to its aggregate Sharpe 0.33, and the pair is far more informative than
    either alone. 🔴 Minimum acceptable outcome even if CSCV is not built: detach the
    Bailey citation from a function that does not implement it. Cheap: no new data, no
    fetch. Motivated by: 2608.23808 (Santoni, Jouanne & Scullin) for the gate, 2512.12924
    (Deep, Deep & Lamptey) for the fold-level metric. Independent of item 6 (purge+embargo,
    which is about leakage into the split); this is about grading what comes out of it.

21. **The factor-redundancy measurement and the factor model are both linear — neither
    can see a square or a product** — `research/factor_redundancy.py:15-16` reports
    participation ratio 4.92/10 (IN) and 4.53/10 (US) from a *Pearson* correlation of
    the 10-factor matrix, and `factor_learning.py:43` `build_xy()` hands `LassoCV`
    (`:88`) those same 10 raw columns and nothing else. Two factors that are linearly
    near-orthogonal but related through f_i^2 or f_i*f_j are therefore invisible to the
    diagnosis AND unavailable to the model — the identical blind spot on both sides, so
    4.92 is an *upper* bound on independence, not a lower one. Apply 2503.23501's
    procedure to the repo's own set: from the 10 `FACTORS` (`factor_learning.py:37`)
    build 10 squares + 45 pairwise products = 55 candidates (the paper builds 57 from
    6 base factors), then forward-select by whichever candidate most raises the
    Fama-MacBeth second-stage cross-sectional R-squared, stopping at the paper's
    <1 percentage point rule. Falsifiable prediction: if any raw factor `LassoCV`
    currently keeps (`:119` logs which) loses its weight once its own square or one of
    its products is admitted, that factor was never carrying independent information and
    the kept-factor count in `factor_learning.md` overstates the model's breadth. Grade
    the result on the repo's existing harness — OOS info ratio via
    `factor_learning.py:62 ls_book_ir` — not on R-squared alone. Cheap: no new data, no
    fetch, no new panel; `build_xy` already returns the matrix. 🔴 Note the repo has
    **no Fama-MacBeth implementation at all** (`grep -rniE 'fama_macbeth|FamaMacBeth'`
    = 0; `paper_claim_audit.py:26` is a citation string only), so this builds one — keep
    it in `research/`, not in the nightly path. Motivated by: 2503.23501 (Borri,
    Chetverikov, Liu & Tsyvinski), with 2404.08129 as background. Extends item 1, which
    measured the linear half of this question and is marked DONE.

22. **No closed-form max-Sharpe baseline sits between the Lasso and the PPO** — factor
    weights are produced either by `LassoCV` (`factor_learning.py:88`, an MSE fit that
    optimises nothing the book is graded on) or by PPO
    (`train_ppo_factor_weights.py`), with nothing cheap in between;
    `grep -rniE 'ridge|tangency|britten'` finds ridge only as a per-stock price ML
    engine (`full_us_market_scan.py:83`) and `fund_implementability.py:18` explicitly
    declines the tangency question. Add the ridge-penalised Britten-Jones (1999)
    estimator 2602.20856 uses: regress a vector of ones on the matrix of the 10 factor
    returns, cross-validate the shrinkage lambda, read off closed-form tangency weights.
    Concrete test: run it against both incumbents on the same `ls_book_ir`
    (`factor_learning.py:62`) OOS info ratio. Cheap and diagnostic either way — if a
    ~20-line closed form matches the PPO, the PPO's training cost is unearned; if it
    loses badly, that is the first evidence the repo has that the RL formulation is
    buying something. 🔴 Take the estimator, NOT the paper's numbers: its 2.21/3.32
    out-of-sample Sharpes are gross, on leverage-two long-short books rebalanced
    monthly, with no turnover figure and no cost deduction reported anywhere — the exact
    quantity item 16 exists to interrogate. Motivated by: 2602.20856 (Avramov & He).


## Done

(none yet)

23. **Invert the cost assumption: report breakeven bps per market, not net precision at
    an assumed charge** — `confusion_matrix_eval.py:34` hard-codes
    `COST_BPS = {"IN": 40, "US": 15, "KR": 30, "JP": 25, "EU": 30, "CN": 35}`, charges it
    at `:80`, and reports a gross→net precision pair at `:132`. Every one of those six
    numbers is an assumption no line in the repo derives or defends, and the report gives
    no way to see how close any market sits to its own cliff: IN at 40bp could be
    comfortable or one basis point from dead and the table reads identically. Add the
    inverse — solve for c* where the net edge hits zero and print `breakeven_bps`
    alongside `cost_bps` per market. The formula already exists in the repo, at
    `etf_builder.py:288` (`be = edge / (tno * ppy) * 10_000 + COST_BPS`), but in the
    benchmark-relative form; 2603.01820 uses the absolute form ("the maximum constant
    friction that specific asset's strategy can endure before its cumulative PnL is
    driven to zero"). Report both, per market — the gap between them is the size of the
    just-buy-the-index alternative. Cheap: no new data, no refit, one solve over the
    existing per-market series. Diagnostic either way — a market whose breakeven is 45bp
    against an assumed 40bp is not a live edge, it is rounding error, and this is the
    only test in the queue that would say so. Motivated by: 2603.01820
    (Saly-Kaufmann, Wood, Peter-Calliess & Zohren).

24. **The DSR trial count is scoped to one sweep, not to the whole search — widen N to a
    persistent cross-sweep ledger** — `deflated_sharpe.py:42-49` implements López de
    Prado's E[max SR] and `:52-58` the deflated Sharpe correctly, but `:71-74` builds
    `trial_srs` from a single `market == mkt & regime == regime` slice of
    `reports/profitability_optimizer.csv`, so the `n_trials` written at `:82` is 10 — the
    factors in that one comparison — and `:80` gates `survives` at 0.95 against a
    best-of-10 benchmark. The search that actually happened is much wider than 10: every
    configuration tried against the same markets in `sweep_piotroski_plus.py`,
    `sweep_piotroski_plus_us.py`, `backtest_zone_rules.py`, `backtest_pe_anomalies.py`
    and `backtest_tier_anomalies.py` is another draw from the same selection process.
    Because E[max SR] rises with N (`:49`), every DSR currently in
    `reports/deflated_sharpe.csv` is an **upper bound on significance**, and the
    `✅ real` / `⚠️ fragile` labels in `reports/deflated_sharpe.md` inherit that
    optimism. Concrete change: have each sweep append `(market, regime, variant, IR, n)`
    to one `reports/trial_ledger.csv`, then have `deflated_sharpe.py` read N and the
    trial-Sharpe dispersion from the ledger slice rather than from
    `profitability_optimizer.csv` alone, keeping both columns side by side
    (`n_trials_sweep`, `n_trials_ledger`, `DSR_sweep`, `DSR_ledger`). Falsifiable
    prediction: the India trend cell currently reported at DSR 0.994 is robust enough to
    survive the wider N, but at least one of the marginal cells that currently passes at
    ≥0.95 does not — and if none flips, that is itself the strongest statement this repo
    has made about its own factor set. Cheap: no new data, no refit, one append per sweep
    plus a different read path in one file. The repo already has the ledger habit
    (`decision_log.py`, and `dl.record(...)` at `deflated_sharpe.py:89`), so this is
    reusing an existing pattern rather than inventing one. Motivated by: 2608.27734
    (Gençay), whose N=102 comes from the agent's own recorded trial count and whose
    entire result — every discovered strategy failing, passive benchmarks certifying at
    DSR 0.97/0.94 — turns on counting trials honestly. Independent of item 19 (which
    fixes `T`, the sample length) and item 20 (which fixes the mislabelled PBO); this one
    fixes `N`, the third input to the same gate.

25. **Every backtest fills at the close it just saw — measure the one-bar delay instead of
    assuming it away** — `backtest_screeners.py:270` states the convention outright in its
    docstring ("Entry = signal bar close. Exit = close at T+N") and the code stamps it at
    `:402` (`"entry_price": curr_close`, from `curr_close = closes[i]` at `:385`) and
    `:439` (`float(closes.iloc[i])`), with `walk_forward_backtest.py:1362` carrying the
    same shape through `sig["entry"]`. Signal and fill are the same bar. The volume gate at
    `backtest_screeners.py:397` sharpens the problem rather than softening it: it tests
    `vols[i]`, the *completed* day-t volume, against the trailing 20-day mean, so the
    decision provably requires the finished bar — and then fills inside it. Concrete
    change: add an `ENTRY_DELAY_BARS` constant (default 0, so nothing moves silently) read
    by `compute_forward_returns` at `:257`, entering at `closes[signal_idx + delay]` and
    exiting at `closes[signal_idx + delay + offset]`, then run the existing screener
    backtest twice and report `ret_*` and `ret_*_delayed` side by side in
    `reports/backtest_screeners.csv`. No new data is needed — the `closes` array is already
    in hand and no `Open` column is required (deliberately: see below). Falsifiable
    prediction: net returns fall by a small, roughly uniform amount and the *ranking* of
    screeners is unchanged, which would make the whole estate's headline numbers safe to
    keep quoting; but if any screener's edge collapses under a single bar of delay — the
    Darvas breakout at `:388` is the likeliest, since it fires on the first close above the
    box top and a one-day-late fill buys the follow-through rather than the break — then
    that edge is an artifact of same-bar execution and the mailer has been surfacing it.
    Motivated by: 2605.23959 (Zhang, Li, Peng & Chen), whose one-switch benchmark prices
    this exact convention (`EXEC_CLOSE`) at ~+0.06 Sharpe on an S&P 500 daily-OHLCV panel —
    small, but one-directional and optimistic, and the only one of the paper's five
    violations this repo actually commits. **Do not "fix" this by moving to open-price
    execution.** The same paper measures `EXEC_OPEN` — signal built from the full day-t bar
    but filled at the day-t open — at +5 to +26 Sharpe of pure inflation, the worst channel
    it found. The repo is currently immune because `grep -n '"Open"'` over the four
    backtest modules returns zero hits; adding an open-price fill without also moving the
    feature cutoff back a day would import the paper's most damaging bug while looking like
    a realism upgrade. A one-bar close-to-close delay is the cheap, safe version of the
    same correction.

26. **The learned-factor report's strongest claim is its only untested one — replace
    single-LASSO selection with double-selection before repeating it** —
    `factor_learning.py:145` writes into `reports/factor_learning.md` that "Lasso zeroing
    a factor = that factor adds nothing once the others are in (built-in selection — a
    principled cure for the multiple-testing fragility the Deflated-Sharpe flagged)".
    That is a post-selection *inference* claim, and the single-stage `LassoCV` at
    `factor_learning.py:88` cannot support it: the L1 penalty shrinks coefficients toward
    zero, which factors survive is unstable across resamples, and post-selection
    coefficients have no valid standard errors. Concrete change, in `research/` only —
    **not** in the nightly path: for each of the 10 factors at `factor_learning.py:37-38`
    in turn, treat it as the signal-of-interest d and the other 9 as controls Z, then run
    Belloni–Chernozhukov–Hansen double selection — LASSO y on Z, LASSO d on Z, take the
    **union** of the two selected control sets, refit y on d plus that union
    *unpenalised* by OLS, and report d's coefficient with a heteroskedasticity-robust
    standard error clustered by week. Falsifiable prediction: at least one factor that
    `LassoCV` currently zeroes (`:119` logs which per market) comes back with a
    significant coefficient under double selection — meaning the report has been
    announcing "adds nothing" about a factor that does — and/or at least one *kept*
    factor's coefficient fails to clear its own standard error, meaning the kept count in
    `factor_learning.md` is padded. Either outcome changes what that report is allowed to
    say. Cheap: no new data and no new panel — `build_xy()` (`:43`) already returns the
    matrix, and `sklearn.linear_model` is already imported at `:27`; the whole thing is
    10 fits of a model already in the file. 🔴 Take the **method**, not the paper's
    numbers: 2601.06499's headline (17 of 191 short-term signals survive against 151
    fundamental controls, S&P 500, 2002–2022, monthly) states **no transaction-cost
    treatment**, which for short-horizon price-volume signals is the disclosure that
    matters most — read the 17 as gross and do not import the signals themselves.
    Motivated by: 2601.06499 (Du, Walter & Ulrich). **Complementary to item 21, not a
    duplicate**: item 21 asks whether the redundancy diagnosis can see non-linear terms
    at all; this asks whether the verdict is valid inference even on the linear terms
    both sides already see. Do item 21's Fama-MacBeth build first if only one is done —
    it produces the machinery this can reuse.

27. **The mailer's shortlist is a ~2,110 → ~25 cut decided entirely by one column's
    ordering, and that ordering has never been tested — measure its within-passer rank IC
    before changing anything else about it** — `signal_tracker.py:222` sorts the technical
    passes by `score` and keeps `TECHNICAL_TOP_PER_MARKET = 5` per market (`:210`). The
    comment at `:195-207` records the scale: the filter returned **2,110 passes in one
    run**, grade alone was "not enough of a bar", so the fix was "rank by quality score and
    take the best few PER MARKET". `score` for those rows is `Quality_Score`
    (`signal_tracker.py:152`). Nothing tests whether `Quality_Score` orders forward returns
    **among names that already passed** — `rloo_rescore.py` answers picked-vs-not-picked
    (its LOO baseline is the *other eligible names*, `:271,281`), which is a different
    question from rank-6-vs-rank-4, and the existing rank-IC code
    (`pead_liquidity_study.py:226`, `backtest_ccc.py:258`) is pointed at PEAD surprise and
    the CCC signal, not at this column. Concrete change, in `research/` only — **not** in
    the nightly path: take the technical rows from `cache_seed/signal_ledger.parquet`,
    restrict to passers only, and for each (market, date) cohort compute the Spearman rank
    IC of `Quality_Score` against h-day forward return from the back-adjusted panel
    (`~/.cache/market-warehouse/ohlcv_adj` — **the adjusted one**, per
    `rloo_rescore.py:44-48`, or raw splits manufacture fake advantages). Collapse to one IC
    per cohort and t-test with Newey-West HAC at lag h, reusing `rloo_rescore.py`'s
    correction rather than writing a new one. Report per market: India's is the one that
    matters most and the one most likely to differ. **Falsifiable prediction:** the
    within-passer rank IC is statistically indistinguishable from zero in at least one
    market — meaning the top-5 cut in that market is selecting arbitrarily among ~400
    equally-good names and its only real function is bounding the list length, which a
    liquidity or count rule would do more honestly. The opposite outcome is just as useful:
    a positive IC licenses the cut *and* makes it worth asking whether 5 is the right N.
    🔴 **Fix the falsy-zero first or the sample is truncated**: `signal_tracker.py:152`
    (`float(r.get("Quality_Score") or np.nan)`) and `:181` (same for `f_score`, a 0–9
    Piotroski score where 0 is legitimate) both turn a genuine **0** into NaN, so the
    worst-scoring rows are logged score-less. It does not change today's picks — NaN and 0
    both sort last — but a rank-IC run on the ledger would silently drop exactly the tail
    that anchors the correlation. Use `pd.to_numeric(..., errors="coerce")`, matching
    `:153-155`. **Do this before the IC run, and re-derive any affected history.**
    **Deferred until this resolves: TopK-DropN hysteresis.** 2605.13407 holds K names and
    only evicts one that falls out of the top K+N, which is the standard cure for the
    boundary churn `signal_tracker.py:222` currently has (verified absent: no
    `hysteres|turnover_cap|churn|drop_n|buffer.?zone` hits in `code/python_files/`; the
    `EVICT_SESSIONS = 5` at `filter_watchlists.py:70` counts *filter misses*, `:41`, in a
    different module, and is not rank buffering). Do **not** implement it first — smoothing
    a cut is only worth doing once the cut is known to mean something. Motivated by:
    2012.07149 (Poh, Lim, Zohren & Roberts) for the score-is-not-a-ranker framing —
    their regress-then-rank MLP scores Sharpe 0.265 against LambdaMART's 2.156 on the same
    NYSE 1980–2019 panel — and 2605.13407 (Kim & Song) for the DropN mechanism. 🔴 Take
    neither paper's numbers: 2012.07149 states outright that it models **no transaction
    costs**, and 2605.13407's model is GPU-trained and off-scope.

28. **The live tracker still grades India against a median price level — the fabricated
    benchmark was fixed in the research script and left in the pipeline.** On 2026-08-22/23
    this repo caught `signal_tracker.py`'s panel-median fallback reporting a **fabricated
    +46.77% "vs bench" for India** and replaced it with a real spliced series. The
    replacement lives in `research/stock_pick_performance.py:139-178` — NIFTYBEES bars
    through 2026-07-13 spliced onto the NIFTY 50 index series from 2026-07-14, rescaled at
    the seam so there is no jump. The live module was never changed:
    `signal_tracker.py:436` still does `bench, bench_name = wide.median(axis=1),
    "panel-median (equal-wt)"`, and `:417-428` records that this fallback **does** fire for
    India, because NIFTYBEES stopped updating when an equity-only bhavcopy filter was added
    (its last bar is a week behind the panel). The series is then used as a level:
    `:473-474` computes `bret = (ba.iloc[-1] / ba.iloc[0] - 1) * 100` and `:479` writes
    `xret_pct = ret - bret`. **A median of price levels across a changing cross-section is
    not an index.** It is not survivor-biased — delisted names lose their bars and drop out,
    which is point-in-time correct — but it is composition-drifting: the same panel holds
    **1,654 symbols in `year=2016.parquet` and 7,073 in `year=2026.parquet`** (measured
    2026-09-11 on `~/.cache/market-warehouse/ohlcv_adj/IN`), so the median level moves when
    the membership of the cross-section changes, with no market move behind it. Concrete
    change, two parts. **(a)** Lift `_india_benchmark()` out of
    `research/stock_pick_performance.py` into a shared helper and have `signal_tracker.py`
    use it for `IN`; keep a fallback, but make it a **return-chained equal-weight index**
    (mean of daily cross-sectional returns, cumulated) rather than a median of levels, and
    keep the existing practice of labelling a substituted benchmark rather than silently
    swapping it (`:437-441`). **(b)** Before changing anything, measure the damage in
    `research/` only: re-derive `xret_pct` for every ledger entry under both benchmarks and
    report the distribution of the difference per market and per filter. **Falsifiable
    prediction:** the median-level benchmark is biased *upward* over the 2016→2026 window —
    India's listed cross-section grew four-fold and newly listed small-caps enter at lower
    price levels than the incumbents, dragging the median down and so inflating every
    `xret_pct` computed against it — which would mean the recorded "median vs benchmark
    -2.74%, win rate 53%" is, for the affected rows, better than the truth rather than
    worse. The opposite sign is equally informative and equally cheap to get. 🔴 Read-only
    on the live path until (b) is done: this changes how every past signal is graded, so
    re-derive history rather than letting the new benchmark silently apply to old rows.
    Motivated by 0810.1922 (Daniel, Sornette & Wöhrmann, JPM 2009), which measures
    look-ahead **benchmark** bias at **up to 8%/annum** on the S&P 500 over CRSP 1926-2006
    and notes it also overstates Sharpe and understates drawdown — the benchmark side of
    survivorship, which this repo has disarmed thoroughly on the strategy side
    (`smallcap_screener.py:30-38`, `band_sip_backtest.py:20-26`) and not at all here.

29. **Item 18's harness already exists, and its premise was half-wrong — retarget rather
    than rebuild.** Item 18 says the repo applies no eigenvalue treatment anywhere. Verified
    2026-09-12: that holds for `portfolio_builder.py:217` (`cov = R.cov().values *
    TRADING_DAYS`, into `port_var` at `:222`) and `mutual_fund_theorem.py:107` (identical
    line), but **not** for `etf_builder.py`, which imports `LedoitWolf` at `:202`, computes
    `cov = LedoitWolf().fit(hist.values).covariance_ * TRADING_DAYS` at `:227`, and already
    accumulates per-scheme `turnovers` (`:205`) inside a strictly-trailing rebalance loop
    (`:208-231`) whose universe selection is point-in-time by trailing median turnover
    (`:213-215`). So the comparison item 18 asks for does not need a new backtest harness —
    it needs the two raw-covariance call sites routed through the one that already reports
    volatility *and* turnover together. **(a)** Factor the estimator out of `etf_builder.py`
    into a `cov_estimator(hist, method)` helper with three methods: raw `.cov()`,
    `LedoitWolf`, and Average Oracle. **(b)** Average Oracle, now specified rather than
    guessed (2309.17219 §method): eigendecompose the correlation matrix, keep the **current
    eigenvectors**, and replace the eigenvalues with a fixed set calibrated once on an
    earlier out-of-sample stretch — the calibration being a bootstrap over repeated random
    draws of periods *and* of assets, each draw taking the covariance of its "future" period
    against the eigenvectors of its adjacent past period, then averaging. Held
    time-independent thereafter; no refit at rebalance. **(c)** Report realized volatility,
    max drawdown, Sharpe **and turnover** for all three at both 5-day and 20-day rebalancing,
    the two frequencies the paper uses. **Falsifiable prediction, now with a number to beat:**
    the paper reports AO at **Sharpe 1.229 / turnover 0.068** against DCC-QIS at
    **0.894-0.895 / turnover 1.307-1.308** on 100 US names, 2000-2021, long-short, 5bps costs
    applied at each rebalance — a ~19x turnover gap in AO's favour. If the ordering here
    comes out AO ≥ LW > raw on Sharpe while AO also has the lowest turnover, the mechanism
    transfers; if AO's turnover advantage vanishes on a long-only Indian EOD book, that is
    the more interesting result and says the edge was a long-short artefact. 🔴 Do not
    import the paper's Sharpe as an expectation: it is long-short US at 5 bps, this repo is
    long-only multi-market at materially worse costs. Cheap: sklearn is already a
    dependency, AO is a bootstrap loop plus `eigh`, no new data and no training.
    Supersedes nothing in item 18 — it replaces item 18's "frozen-eigenvalue estimator
    (spectrum estimated once on the earliest third of the sample)" with the actual method,
    and removes its assumption that a turnover-reporting harness has to be written first.
    Motivated by: 2309.17219 (Bongiorno & Challet), corroborated by 2511.10478 (Ruelloux,
    Bongiorno & Challet) which reaches for the same AO eigenvalues from a different
    direction.

30. **Every redundancy number in this repo is measured in the index set the theory says
    doesn't order the one we care about.** `research/factor_redundancy.py` computes all of
    its output from one object: `corr = df.corr().values` at `:65`, the Pearson correlation
    **across assets at each date** of the ten factor columns in `factor_learning.py`'s
    feature matrix. `spectral_stats()` at `:42-54` eigendecomposes exactly that matrix for
    the participation ratio, eigenvalue entropy / effective rank and absorption ratio, and
    `:75-81` names the top-5 correlated pairs from it. The docstring states the method
    plainly at `:15-16`. 2609.09588 (Nunes, 2026-09-09) proves that signal correlation and
    **PnL** correlation are correlations over different index sets — across assets per date
    versus across dates for scalar payoffs — and that, absent constraints on the transverse
    geometry, **neither bounds nor orders the other**. Signal correlation decomposes into an
    uncentred IC cross-moment plus a transverse-similarity term; Pearson PnL correlation
    centres and dispersion-weights the IC series alone. So two factors reading 0.9 in
    `factor_redundancy.md` may have near-independent PnL, and two reading 0.2 may not
    diversify at all — and this repo has never computed the PnL-side matrix. Concrete
    change, and it is additive: **(a)** for each of the ten factors compute the per-date
    realized cross-sectional IC (Pearson of the normalized signal against demeaned forward
    returns) — a series per factor over the panel's dates. **(b)** Take the Pearson
    correlation **of those IC series across dates**; that is the PnL-side matrix. **(c)**
    Print both matrices, and both participation ratios, side by side in
    `factor_redundancy.md` — do not replace the existing one, the paper's point is that they
    are different objects, not that the signal-side number is wrong. **Falsifiable
    prediction:** the two participation ratios disagree materially, and specifically the
    PnL-side effective factor count is **higher** than the signal-side one — the ten factors
    all derive from one weekly close panel (`factor_library(close)`, docstring `:11-13`) and
    two of them (`qual_mom`, `def_revert`) are documented AND-combinations of two others,
    which is a construction guaranteed to inflate signal correlation, whereas their payoffs
    fire at different times. If the two agree closely, that is a real and reassuring result
    and means items 1/9's redundancy verdict can be taken at face value. Cheap: forward
    returns are already assembled by `build_xy()`, which `factor_redundancy.py` already
    imports; this is one extra series per factor and a second `corrcoef`. Read-only on the
    live path — `research/` only, same as the existing script.
    Motivated by: 2609.09588 (Marc Nunes), which sharpens the simulation finding of
    Sorensen, Qian, Schoen & Hua (2004) into an exact non-identifiability theorem.

31. **Five cost conventions, one question nobody has asked: does any conclusion depend on
    which one its module happened to use?**
    2603.20319 (Yin, Miki, Lesnichenko & Gural) ran 15 strategies through 5 engines. At
    zero cost the engines agree to 0.000%; under costs they diverge by up to 3.71%. Its
    conclusion is that cost *implementation* is the whole source of backtest disagreement.
    This repo has no engines, but it has the same mechanism spread across modules:
    - a flat 20 bp round-trip per trade (`backtest_screeners.py:174`, `:285`;
      `walk_forward_backtest.py:156`, `:936`)
    - 10 bp per side on L1 traded weight, first rebalance charged in full
      (`etf_builder.py:60`, `:240-243`)
    - a flat 100 bp of the whole level per rebalance, whatever the turnover
      (`custom_indices.py:68`, `:146`)
    - a per-market 15–40 bp hurdle (`confusion_matrix_eval.py:34`, `:94`)
    - zero commissions (`cost_vs_edge.py:36`)

    India alone is costed at **20 bp in one module and 40 bp in another**.

    Concrete change, `research/` only and read-only on the live path. For each module's
    headline number (net mean return or Sharpe per screen, horizon or scheme), recompute
    it under **one shared convention**: cost on the traded delta, per side, using the
    per-market bps table already at `confusion_matrix_eval.py:34`. Report the paper's
    **Conclusion Sensitivity Index**, i.e. whether any headline changes sign against its
    native convention, plus the size of each shift.

    **Falsifiable prediction:** CSI = 0 for the low-turnover, cost-neutral comparisons
    (`etf_builder` schemes, and `custom_indices` vs its own null, since both sides pay the
    same charge). Any sign flip shows up first in the **shortest horizons of
    `backtest_screeners.py` for India**, where moving from 20 to 40 bp doubles the hurdle
    on the smallest gross moves. If nothing flips, record that as the result: it means
    the five conventions are harmless inconsistency, not a hidden bias.
    Motivated by: 2603.20319.

32. **Amendment to item 30: compute the intermediate spectra, not just the two end points.**
    2609.12477 (Nunes, 2026-09-11), the sequel to 2609.09588 behind item 30, proves that
    two separable things happen between the signal-side and PnL-side matrices:
    - **transverse annihilation:** the payoff map kills signal components orthogonal to
      returns (Theorem 7.1)
    - **longitudinal transformation:** PnL covariance temporally centers the IC path and
      reweights dates by squared return dispersion, which can reorder PCs on its own

    Item 30 as written prints only the first and last matrices, so a gap between the two
    participation ratios could not be attributed to either effect. Add two intermediate
    objects to the same run, following the paper's §12.5:
    - (a) the **uncentred, un-weighted per-date IC Gram matrix** across the ten factors,
      which isolates the transverse effect
    - (b) the same Gram matrix **dispersion-weighted but uncentred**, which isolates the
      weighting

    Print four participation ratios in one row: signal corr → IC Gram → weighted IC Gram →
    centered PnL corr. Also print the §12.4 equal-centrality diagnostic,
    `CVsig = sd(G·1) / |mean(G·1)|`, on the signal matrix. It is the relevant check for the
    one equal-weight composite in the repo, the PPO baseline at
    `train_ppo_factor_weights.py:147-149`. `factor_learning.py` itself combines with
    LassoCV/SGD (`:7-13`), so this does not bear on the live combiner.

    Cost: three extra `corrcoef` / Gram calls on series item 30 already builds. Theory
    only; the paper presents no market-data results, so this is a measurement to make, not
    an edge to expect.
    Motivated by: 2609.12477.

33. **The Deflated-Sharpe gate counts correlated factors as independent trials. Report it
    under effective multiplicity too.** `deflated_sharpe.py:45` sets `N = len(trials)`, and
    `expected_max_sr()` assumes "N independent trials" (`:43`). The trials are the ten factor
    rows per market×regime (`:74`), which item 1 measured at a participation ratio of about
    4.9/10. Change:
    - **(a)** Build the K×K correlation of the trials' per-period return series (or of their
      t-stats), apply Schäfer–Strimmer shrinkage, and compute `K_eff = K² / ‖Σ‖_F²`.
    - **(b)** Write `n_eff`, `IR_exp_max_eff` and `DSR_eff` alongside the existing columns in
      `reports/deflated_sharpe.csv`. Do **not** replace the nominal-N gate.
    - **(c)** In `walk_forward_backtest.py`, add `Sharpe_Gap = train − val` (absolute) next to
      `Sharpe_Decay%` (`:1099`). The ratio explodes as `train` nears 0.

    Falsifiable prediction: `K_eff` is well below 10, E[max] falls, and at least one
    currently FAILing row flips to PASS. Any flip should be read as "the gate was harsh", not
    as a new edge. Cost: one `corrcoef` per market×regime. Research output only; the live
    gate is unchanged.
    Motivated by: 2604.15531.

34. **Run the factor-selection workflow on panels known to contain no signal (falsification
    audit).** No placebo or synthetic-null test exists: `grep -rniE 'placebo|shuffle|permutation'`
    finds nothing relevant, and `r_analysis.py:245` bootstraps one Sharpe series, not the
    selection step. Generate weekly close panels with the real panel's shape (same tickers and
    dates) under three of the paper's nulls:
    - **(A)** i.i.d. Gaussian returns, zero mean.
    - **(D)** one mean-zero market factor plus idiosyncratic noise.
    - **(C)** latent martingale returns observed through an MA(1) bid-ask bounce.

    Push each panel through `factor_library()` → `profitability_optimizer` → `deflated_sharpe`,
    about 50 replications per null. Pass criterion: the share of market×regime cells that
    "survive" is at or below about 5%. Anything materially above that means the workflow
    hallucinates signal, and every live PASS needs re-examining. Null (C) specifically tests
    whether the short-term reversal factors (`revert`, `mom_st`) pick up bounce. Cost:
    CPU-only on synthetic data; no fetch and no live-path change.
    Motivated by: 2604.15531.

35. **Amendment to item 12: spanning is a property of return series, and it has two
    conditions.** As written, item 12 regresses the signal feature matrix
    (`research/factor_redundancy.py:64-65`) and tests α alone. Correct it in three ways:
    - **(a)** Run the regression on the ten factors' **PnL/IC series across dates**, the object
      item 30 builds. Build item 30 first.
    - **(b)** For each factor, test both the intercept α **and** `1'β − 1` (the
      global-minimum-variance condition) and take the max of the two standardized statistics.
    - **(c)** Get critical values from a moving-block bootstrap (`ℓ = ⌊1.2·T^{1/4}⌋`) with a
      step-down over factors.

    Report which factors enter the minimum spanning set, and through which channel. Caveat,
    and state it in the output: the paper needs T ≥ 180 monthly observations for coverage, and
    most markets' fortnightly series here are far shorter. Treat any "spanned, drop it" verdict
    as provisional unless IN's deep 10-year panel reproduces it.
    Motivated by: 2501.19213.

36. **Re-score the factor library in a cap-coverage universe, value-weighted, with
    library-wide luck shrinkage.** The factor optimiser's investable gate
    (`strategy_regime_survival.py:98-105`) drops only the bottom turnover tercile, and it scores
    equal-weighted books (`profitability_optimizer.py:65-67`). Chen & Welch find exactly that
    configuration inflates anomaly premia several-fold relative to a top-N/90%-of-cap universe.
    Without changing the live path, add a research variant that does three things:
    - **(a)** Restrict each week to the names covering the top 90% of total traded value (a
      turnover-value proxy for cap coverage, because the panel carries only Close/Volume,
      `:86`). Also restrict to the top ~N by traded value, with N scaled to the market (about
      500 for IN/JP/KR/EU, 3,000 for US).
    - **(b)** Score the BUY book traded-value-weighted as well as equal-weighted.
    - **(c)** Over the full factor×market×regime table of IR t-stats, report
      `r_adj = (1 − 1/Var(t))·r` beside the existing DSR verdict.

    Output: a three-column comparison per cell (current gate EW / cap-coverage EW /
    cap-coverage VW) plus the shrinkage factor. Any cell whose PASS disappears under (a) or (b)
    is a microcap effect. Caveat: the paper is US-only and India's trend edge may behave
    differently, so report per market and do not generalise. CPU-only, existing panel, no fetch.
    Motivated by: 2607.06502.

37. **Establish that the correlation-spectrum measurement is measuring the market and not its
    own n/T.** `research/correlation_regime_spectrum.py` builds a **126-to-150**-name correlation
    matrix (the range across the 299 rows of `correlation_regime_spectrum.csv`; target `:34`
    `N_SYMBOLS = 150`) from a **60-day** window (`:35`, sliced `:60`) — n/T between 2.1 and 2.5,
    so the matrix has rank ≤ 59 and between 67 and 91 of its eigenvalues are identically zero
    before any market structure is read off it. Every PR and
    AR₁ number quoted from this script (including queue lines 21-22) is therefore a joint function
    of the market and of the window length, and nothing currently separates the two. Three cheap
    checks on the existing panel, no new data and no fetch:
    - **(a) Noise null.** Re-run the same loop on phase-randomised or IID-bootstrapped returns
      with the identical 126×60 shape, and print the null PR/AR₁ band beside the measured series.
      Any measured level inside that band is a dimension artefact; only excursions outside it are
      market signal. This also settles whether the 5 lowest-PR windows item 3 flagged are real.
    - **(b) n/T sweep.** Recompute PR at (n=126, T=60), (126, 252), (50, 60) and (50, 252). If the
      level moves with n/T but the *time pattern* does not, the ranking survives even though the
      level does not — say which of the two the downstream use needs.
    - **(c) Estimable error floor.** Report 2609.20550's out-of-subspace estimator per window —
      `ℓ(p)/θⱼ(p)`, with `ℓ(p)` the average of the n−k trailing sample eigenvalues of the dual
      covariance matrix and `θⱼ(p)` the jth eigenvalue of `W(p) = YᵀY/(np)` — as a floor on how
      much of the leading direction is estimation error. Their US-equity simulation has this half
      dominating.

    Caveat: the paper is theory plus a simulation, and its Section 8 grids were not read (the
    arXiv HTML truncated). Treat (c) as a diagnostic to log, not a correction to apply. Distinct
    from item 9, which adds MP *descriptors* to `market_correlation_scan.py`'s nightly matrix;
    this one asks whether the numbers already cited from the research script are admissible.
    Motivated by: 2609.20550.

    **(a) RUN 2026-09-18** — `research/spectrum_noise_null.py`, output
    `research/spectrum_noise_null.{csv,md}`. 299 windows, 200 replicates per window per null,
    seed 20260918, same panel and same `spectral_stats()`. Two answers, and the second is the
    one that matters:
    - **Not a dimension artefact — the measurement is clean.** Under an independence null (each
      column shuffled in time, marginals kept) PR sits at **41.8** with PC1 absorbing under
      **4.7%**; that matches the analytic Marchenko–Pastur value n/(1+n/T) = 42.1, which is a
      self-check on the simulation. Measured PR (mean **12.3**, min 3.5) is below the null band
      in **100.0%** of windows. Rank deficiency cannot manufacture a dominant common mode, so
      the gap is market structure. The numbers quoted at queue lines 21-22 are admissible.
    - 🔴 **But PR adds nothing over the mean pairwise correlation.** Against an equicorrelated
      null calibrated to each window's own ρ̄ (one common factor, same n, same T), measured PR
      falls **inside** the band in **97.0%** of windows. PR and ρ̄ correlate at **−0.931** across
      all 299 windows. **All five of the lowest-PR windows are inside their own band** — they are
      2020-03-30 through 2020-05-11, ρ̄ 0.47-0.50, i.e. real stress, but the eigendecomposition
      reports nothing the average pairwise correlation did not already say.
    - **Consequence for items 3 and 9:** before wiring any spectral descriptor into
      `market_regime.py`, show it beats plain ρ̄ — one number, no eigendecomposition. On this
      panel PR does not. Item 9's other descriptors (m⁻, spectral gap, MP excess) are untested
      and may still carry something PR does not; that is now the question to ask of them.
    - Caveat: Null B is Gaussian with homogeneous loadings, so "inside the band" means "not
      explained by ρ̄ alone", not "no structure beyond one factor". (b) and (c) are NOT run.

38. 🔴 **Fix item 9 before running it — its lower-spectrum descriptor is not computable on the
    matrix it points at, and add an n/T guard so it cannot silently return a number anyway.**
    Item 9 asks for `m⁻ = count of eigenvalues below (1−√(n/T))²` from
    `market_correlation_scan.py`'s nightly matrix. That matrix is full-universe (the module's own
    docstring reports 2,225 resolved NSE symbols, `:220-222`) at `period: str = "1y"` (`:99`,
    default, threaded through `:261`, `:283`, `:295`, `:362`): **T ≈ 250 against n ≈ 2,225, so
    n/T ≈ 8.9.** At that ratio the lower MP edge (1−√8.9)² = 3.92 sits above most of the spectrum,
    roughly 1,975 eigenvalues are identically zero by rank deficiency, and m⁻ collapses to a
    near-constant ≈ n − T that moves with how many tickers resolved that night rather than with
    the market. The source paper (2608.09641) ran n = 377 / 199 at w = 1000, i.e. n/T ≈ 0.38 /
    0.20 — the opposite regime. Three changes, all cheap, no new data:
    - **(a) Guard, not fix.** Wherever a lower-spectrum descriptor is computed, refuse to emit it
      unless **n < T**, and log the refusal with both numbers. The upper-spectrum descriptors item
      9 also names (AR_k, entropy, effective rank, spectral gap, MP excess) are fine at n > T and
      should still be emitted; only m⁻ and the condition number λ₁/λₙ are affected. λ₁/λₙ is
      meaningless at n > T for the same reason — λₙ is a numerical zero — so guard it too.
    - **(b) Give the lower spectrum a matrix it can live on.** Compute m⁻ on a sub-universe with
      n < T instead: the existing 150-name research panel at `period="2y"` (n/T ≈ 0.3), or the
      most-liquid 150 of the nightly universe at 1y (n/T = 0.6). State which universe the number
      refers to in the output — a market-wide claim from a liquid-150 matrix is a different claim.
    - **(c) Then look for Livan's block signature.** On that same n < T matrix, histogram the
      lower spectrum and check for mass accumulating near **1−ρ̄_block** for the tight blocks
      `mst_clusters` already finds at 0.7/0.8. A block of N̄ equicorrelated names at mean internal
      correlation ρ puts N̄−1 eigenvalues at 1−ρ and one at N̄ρ+(1−ρ). If the mass is there, the
      lower spectrum is counting *how many distinct tight groups exist and how tight they are* —
      which is information ρ̄ does not carry, and is therefore the thing the 2026-09-18 null run
      showed PR lacks.
    Caveat: the two formulas are exact only for a homogeneous block, and Livan et al.'s own S&P
    fit left a residual they attributed to unresolved sub-clusters (predicted single large
    eigenvalue 5.272, observed two large ones). Treat 1−ρ as where to look for mass, not a value
    to test equality against. Caveat 2: this supersedes nothing in item 9 except the m⁻ and
    condition-number lines; the rest of item 9 stands as written.
    Motivated by: 1102.4076, against 2608.09641 (item 9's source).

39. **Ask whether the correlation cluster report beats the sector labels the repo already has —
    MINGLE's Figure-4 diagnostic, without adopting MINGLE.** The only asset-neighbourhood
    construction in the repo is correlation-based, in both flavours 2608.06618 argues against:
    `compute_correlation_clusters` (`market_correlation_scan.py:156-181`, connected components at
    `threshold = 0.55`, `:158`) and `build_mst`/`mst_clusters` (`:186-240`, Mantegna single-linkage
    on `d_ij = √(2(1−ρ_ij))`, `:205-207`). The repo has already paid the price the paper predicts —
    the beta giant component ate 57% of NSE at 0.55 and the fix was to raise the cutoff to 0.7,
    closing with "there's no universal 'right' cutoff... don't assume one number transfers across
    markets/periods" (`:229-234`). The paper's claim is that the non-transferability is a property
    of the *distance*, not the cutoff. Test it on one market (IN, then US), no ADMM and no new data:
    - **(a) Build the exposure graph from what exists.** Use the 10 z-scored factor exposures per
      stock as the vector b_i — `FACTORS` at `factor_learning.py:37-38`, panel written by
      `factor_zscore_panel.py:216` — and define neighbourhood by exposure distance ‖b_i − b_j‖
      instead of by ρ_ij. This is MINGLE's redefinition of locality without its joint optimisation.
    - **(b) Score both graphs on the paper's own diagnostic.** Within-cluster mean edge weight as
      a multiple of between-cluster, in a calm window and a stressed one. Their reported figures
      are 2.42× for correlation against 5.30× for exposure-based. Report the repo's two numbers
      beside theirs.
    - **(c) Sector alignment, which is the part that decides whether the cluster report is worth
      keeping.** Score both graphs' agreement with sector labels (adjusted Rand or normalised
      mutual information). 🔴 Use the **Damodaran** map (`sector_valuation_history.py:27-28`) for
      IN/US — `market_cache/sector_map.json` is Europe-only per `backtest_ccc.py:186`, so
      `watchlist_digest.py:252`'s labels are the wrong source for this test. If the exposure graph
      recovers sectors and the correlation graph does not, then the correlation cluster report is a
      noisier restatement of a sector map the repo already ships, and should say so in its own
      output.
    Do NOT adopt MINGLE's ADMM: it is a portfolio-construction method and this repo builds no
    portfolio from clusters, so the machinery has no consumer. Only the diagnostic is in scope.
    Caveat: their 300-name universe is the most-actively-traded decile of the S&P 500, Nikkei 225
    and STOXX 600, which is the opposite end of the liquidity spectrum from where this repo's
    documented edge sits (illiquidity, not size), so a result there should not be assumed to
    transfer to the NSE small-cap tail — run it per market and report per market.
    Keep in mind what co-movement locality is *right* for: `symbol_master.py:239-242` records a
    56-member cluster that "turned out to be entirely J-REITs moving together on rate sentiment",
    which is how 63 leaking J-REITs were caught. That use is not in question here.
    Motivated by: 2608.06618.

40. **Replace the 50% null in the PEAD sector-spillover binomial test with the base rate it
    actually faces.** `pead_sector_spillover.py:242` tests `binomtest(k, n, 0.5)`, but
    `same_direction` (`:172`) compares the sign of the *raw* peer mean with the surprise sign.
    Under "peers ignore the news" the chance of a match is
    p0 = p_up·f_beat + (1−p_up)·(1−f_beat), where p_up is the leader sector's unconditional share
    of up days for the leave-one-out peer mean and f_beat is the leader's share of positive
    surprises. Both are computable from panels the script already loads. Two changes, and nothing
    else in the study moves:
    - **(a)** Compute p0 per leader and use `binomtest(k, n, p0)`. Report `excess_hit = k/n − p0`
      beside the current `same_direction_hit_rate`.
    - **(b)** Alternatively, market-adjust the peer reaction before taking its sign (peer mean minus
      the same-day market return). The 0.5 null is then closer to right and (a) becomes a check.
    Re-run v1–v4 (all four import the v1 core) and count how many leaders stay significant after
    the existing FDR step. If most survive, fine. If they collapse, the spillover finding was a
    base-rate artefact and must be withdrawn wherever it is cited.
    Motivated by: 2607.12248.

41. **The optimiser's universe is chosen by spreadsheet row order and a silent truncation —
    find out whether that costs anything.** `portfolio_builder.py:285-286` builds the
    optimisation universe as `picks["triple"] + picks["coffee"] + picks["other"]`, dedupes,
    then truncates `[:max_holdings]` (default 25, `:369`). `load_picks()` (`:62-100`) fills
    those three lists by iterating scan-workbook sheets in row order and sorts by nothing.
    So the 25 names that reach the Markowitz step are "the first 25 rows of Triple_Hits,
    then Coffee_Can, then the multi-screen sheets", and if Triple_Hits alone has 25+ names
    the other buckets are dropped without a word — `:287` prints the final count only.
    Three cheap runs on the same scan output, same LOOKBACK=504 window, same `--max-weight
    0.15` cap, comparing out-of-sample Sharpe and max drawdown of the resulting max-Sharpe
    portfolio:
    - **(a) Row order (control)** — what ships today.
    - **(b) Score order** — sort the concatenated universe by the scan's own quality/conviction
      column before truncating, so the cut keeps the best 25 rather than the first 25. If (b)
      does not beat (a), the scan's score does not order the names it selects, which is the
      same question queue item 27 asks of `Quality_Score` in the mailer — run them together
      and treat a flat result at both sites as one finding, not two.
    - **(c) Redundancy-pruned** — greedily drop a name whose return correlation with an
      already-admitted name exceeds ~0.9 over the lookback, and let the next candidate in.
      This is the only part of PS² that transfers: its point is that the post-screen set
      should be chosen against the covariance structure, not arbitrarily.
    Also print, at `:287`, how many names each bucket contributed after truncation. A run
    where Coffee_Can silently contributed zero is a fact the operator should see, and that
    line costs nothing.
    Do this BEFORE item 18. Item 18 changes the covariance *estimator* for a fixed asset
    set; this changes the asset set. If the input set is arbitrary, a better estimator is
    polishing the wrong thing, and at N=25 against T=504 the conditioning problem item 18
    targets is mild at this call site anyway (T/N ≈ 20).
    Expect a small or null effect and report it either way — a null here is worth having,
    because it would mean the truncation is safe and the register can stop flagging it.
    Motivated by: 2604.17593.

42. **Report every screen's edge against both benchmarks, and split it by concentration
    regime.** The mailer's primary evidence measures edge against an **equal-weight market**
    (`justified_mailer.py:16-17`, printed at `:267`). The forward tracker scores the same
    picks against **cap-weighted** NIFTYBEES/SPY (`signal_tracker.py:174`). 2609.27113 shows
    the EW-minus-cap spread depends on the regime: EW lags while market concentration rises.
    It also notes US diversity is at its lowest since the dot-com peak. Without this check, a
    backtest edge measured against EW and a weaker live edge measured against cap-weight
    would be misread as decay. The check needs no market-cap history. For each tested market
    and window, compute the EW-minus-cap index spread from index pairs the repo already
    names (NIFTY50 vs "NIFTY50 Equal Weight", `sip_xirr_backtest.py:48`; SPY vs RSP for the
    US). Label each 21-day forward window as rising or falling concentration by the sign of
    the trailing spread. Then re-report each screen's 2016→2026 edge (i) against EW and (ii)
    against cap-weight, each split by that label. If the edge survives against cap-weight in
    concentrating windows, print that in the email. If it does not, the email's "edge vs
    equal-weight" line should say which benchmark and which regime it holds in.
    Motivated by: 2609.27113.

43. **Stop reporting `pattern_discovery.py`'s R² as a model fit — it is an in-window
    cross-sectional fit.** `pattern_discovery.py:285` uses `train_test_split` with the
    default `shuffle=True`. Every row shares one as-of date and the same `_target_fwd21`
    window (`:224`), so train and test are scored on the identical 21 days. The R² printed at
    `:293`, and the feature importances, absorb that month's common move. Cheapest fix:
    rename the printout to "in-window cross-sectional R² (not a forecast)". Proper fix: build
    the feature matrix at two as-of dates at least 21+2τ trading days apart, train on the
    earlier one and score on the later one, which is an expanding walk-forward in the sense
    of 2609.29530. Report both numbers side by side. Expect the causal R² to fall to about
    zero. If `dl_strategy_eval.py:31` still cites pattern_discovery as evidence afterwards,
    check it against the causal number.
    Motivated by: 2609.29530.

44. **Leave-one-screen-out test of the six-screen vote.** `full_us_market_scan.py:994-1003`
    admits a name to the multi-screen sheet when `screens_passed >= 3` out of six equally
    weighted booleans. Two of those votes are **Golden Cross/above-200DMA**, which the
    repo's own evidence calls the worst screen in every tested market
    (`justified_mailer.py:26`), and **Piotroski f_strong**, which is **INVERTED** for the US
    (`:20`). 2609.26303 proves that equal-weight admission of a non-aligned forecaster is
    pure dilution. For each tested market, on the PIT panel, compare the 21-day forward
    excess return (against both benchmarks, see item 42) of the ≥3-of-6 cohort with the six
    leave-one-out cohorts, each ≥3 of the remaining 5. Also run ≥2-of-4 with GC and
    Piotroski both dropped in the US. If dropping GC or US-Piotroski raises forward excess
    return or leaves it flat, remove that vote. The multi-screen sheet feeds
    `portfolio_builder.py`'s "other" bucket (item 41), so run this first, before item 41's
    score-order arm. As with item 41, report a null too.
    Motivated by: 2609.26303.

45. **Amendment to items 12 and 35: benchmark every redundancy R² against its noise floor.**
    When item 12/35 regresses each factor's date-level PnL/IC series on the other nine,
    report next to each R² the mechanical level that pure noise would reach,
    `p/(T−1)` (p = 9 regressors, T = dated observations in that market).
    Optionally also report the Stewart–Love redundancy index from a CCA of each factor
    against the rest, with the same floor.

    Call a factor "redundant" only when its R² clearly exceeds the floor and item 35's α and
    `1'β−1` tests agree. The fortnightly series are short: at T = 40 the floor is about 23%,
    so an R² of 30% there is close to noise.

    Apply the same caveat to `research/factor_redundancy.py`'s participation ratio
    (`:60-68`). It has no benchmark, but it pools stock-weeks, so there the floor is small.
    Motivated by: 2609.31263.

46. **Give the DSR gate real moments, and check whether one window carries the chosen
    factor.** Two parts, sharing one per-period series.

    **Part (a): pass empirical moments into the DSR.**
    - `deflated_sharpe.py:78` calls `dsr(sr_best, trials_sr, T)` with the default skew = 0
      and kurt = 3.
    - `reports/profitability_optimizer.csv` stores only `mean_excess, info_ratio,
      mean_book, hit, n`, so no moments exist to pass in.
    - Have `profitability_optimizer.py` also write each factor's fortnightly excess-return
      series, or its skew and kurtosis.
    - Pass the chosen factor's skew and kurt into `dsr()`.
    - Report DSR under normal and under empirical moments side by side, and flag any
      market × regime cell whose `survives_0.95` flips.
    - Item 19's MTRL uses the same bracket and should take the same moments.

    **Part (b): single-window sensitivity.**
    - For each chosen factor, recompute IR after dropping its best three consecutive
      fortnights. Also recompute it after dropping Feb–May 2020 where that falls inside
      the sample.
    - Mark the cell `⚠️ concentrated` if IR falls by more than half.

    Prediction: bear-regime cells are the most exposed on both counts, because they have
    short T and crash-driven fat tails.

    Cost: this needs no new data and no refit, only the per-period series the optimiser
    already computes internally. Motivated by: 2609.35359. In that paper fat tails cut the
    Sharpe from 0.67 to 0.281, and removing Feb–Apr 2020 cut it to 0.28.

47. **Truncation-invariance and rerun-hash tests for the production scorer.** This is a
    test, not a backtest.
    (a) Pick 3 past dates *t* per market. Run the daily scorer once on the OHLCV/
        fundamentals panel, and once on the same panel with every row after *t* deleted.
        Assert that the date-*t* picks, scores and zones are identical. Any difference is
        look-ahead by construction.
    (b) Run the same scan twice and assert that the SHA256 hashes of the sorted
        (ticker, score, zone) lists match.
    Add both to `test_pipeline_invariants.py`. This turns item 11's labels into an
    executable check. Cost: minutes of CPU, no new data.
    Motivated by: 2604.04812 (a runtime LeakageGuard is a hard gate there; static
    `shift(-k)` scans are only warnings).
