# Methodology — assumptions, how to read the results, and the literature

This is the canonical reference for *how* the platform reaches a verdict, *what it assumes*,
and *which academic results* the inference rests on. Read it alongside
[`SYSTEM_REFERENCE.md`](SYSTEM_REFERENCE.md) (module map), [`PIPELINE_STAGES.md`](PIPELINE_STAGES.md)
(the 10 stages) and [`DATA_SUFFICIENCY.md`](DATA_SUFFICIENCY.md) (the power/coverage gate).

## The strategy in one paragraph

There is no universal strategy — each market has a **character** and the pipeline matches a
factor family to it. Prices that trend → momentum/breakout (long-only where shorting is run
over); multiples that mean-revert → value-reversion; repriced fundamentals → quality. A
candidate becomes a *strategy* only after it (1) has enough non-overlapping data to be
**powered**, (2) survives a **multiple-testing** correction, and (3) covers enough of the
**liquid** universe to be representative. Verdicts: **India** momentum + sector-relative value
(long-only); **Korea** full long/short (cheap∩hi-ROE vs hollow-overpriced); **US** short-horizon
value; **Europe** momentum; **Japan** value-reversion (strong, on deep data); **China** value
*fails* (a powered null). Momentum survives almost everywhere; value works only where the data
is deep enough to prove it.

## Assumptions (they bound every number)

| # | assumption | why | control |
|---|---|---|---|
| 1 | **Point-in-time** — fundamentals lagged to `filed` (else FYE+90d; +120d China) | no look-ahead alpha | `pit_eps()` |
| 2 | **Survivorship-biased universes** | dead names dropped | **read spreads (Q1−Q5, L−S), not levels** |
| 3 | **Gross of costs** | impact + borrow not deducted | net must clear Almgren-Chriss + locate |
| 4 | **Illiquidity-driven, small capacity (~$300–500k)** | edge decays with size | `execution_cost_model.py`, `cost_vs_edge.py` |
| 5 | **Non-overlapping t-stats** | overlap autocorrelates → inflated t | `nonoverlap_t()`, step = horizon |
| 6 | **Coverage bias** if <60% of liquid universe | covered names may be non-random | `data_sufficiency.py` flags "returns-only" |
| 7 | **Sample representativeness** — some panels selected (JP = EDINET-Bench task-sample) | magnitude may be biased | direction+significance still valid |

## How to read a result

**Quantitatively** — a finding is *trustworthy* only when all hold:

- `|t| ≳ 2` on **non-overlapping** observations (`deflated_sharpe.csv`, reversion reports)
- **Deflated Sharpe Ratio > 0.95** for technical factors (corrects for how many were tried)
- **≥ 15 non-overlapping observations** → powered (below → "can't conclude", *not* "no effect")
- **≥ 60% liquid coverage** → complete (below → "returns-only, coverage caveat")

Tiers: ✅ trust · 🟡 returns-only (powered but thin) · 🔴 can't conclude (underpowered). Only
three technical factors clear DSR>0.95 (IN-trend 0.994, KR-breakout 0.99, EU-mom 0.985); the
rest are fragile.

**Qualitatively** —

- **Character first:** a factor that beats a market's character is probably an artifact.
- **Convergence corroborates value:** rich PEs should fall toward the median and cheap PEs rise.
  Multiple converges **and** returns reward it → real (IN/JP/KR/US). Multiple converges but
  returns don't → mirage (China).
- **Nulls and flips are verdicts:** "China value fails" (powered null) and "Japan value works"
  (flipped once EDINET depth arrived) are results. A verdict that changes as data deepens is a
  statement about *power*, not about the world.
- **Discount magnitude on thin/selected samples**; keep the sign and the t.

## Worked example — why Japan flipped

With J-Quants free data (~2 years, ~11 non-overlap obs) Japan's value spread was insignificant
→ verdict "underpowered, can't conclude". With the Sakana **EDINET-Bench** panel (1,437 firms,
2011–2024, ~17–19 non-overlap obs) the *same test* gives **+6.6%/6M, t 4.84**. Nothing about
Japan changed — only the **power** did. This is the entire point of the sufficiency gate:
"not significant" on thin data must never be reported as "no effect."

## Literature (the inference rests on these)

- **Multiple-testing / overfitting:** Bailey & López de Prado (2014), *The Deflated Sharpe
  Ratio*, JPM; Harvey, Liu & Zhu (2016), *…and the Cross-Section of Expected Returns*, RFS;
  Harvey & Liu (2015), *Backtesting*, JPM. → `deflated_sharpe.py`.
- **Value / mean-reversion:** De Bondt & Thaler (1985), JF; Lakonishok, Shleifer & Vishny
  (1994), JF; Fama & French (1992). → `valuation_reversion_backtest.py`, `valuation_clustering.py`.
- **Momentum:** Jegadeesh & Titman (1993), JF; Moskowitz, Ooi & Pedersen (2012), *Time Series
  Momentum*, JFE. → `strategy_regime_survival.py`.
- **Quality (F-score):** Piotroski (2000), J. Accounting Research — *inverted in the US* in our
  tests (factors don't travel). → `scanners/piotroski.py`, `piotroski_plus`.
- **Execution / impact:** Almgren & Chriss (2000); Almgren et al. (2005). → `execution_cost_model.py`.
- **Liquidity / capacity:** Amihud (2002), JFM; Corwin & Schultz (2012), JF. → `cost_vs_edge.py`.
- **Factor selection:** Tibshirani (1996), *Lasso*, JRSS-B. → `factor_learning.py` (shadow mode).
- **Microstructure / HFT:** Gomber et al., *High-Frequency Trading*; `baobach/hft_papers`. →
  orchestration + cost realism.
- **Japanese data + LLM-vs-baseline:** Sugiura et al. (2025), *EDINET-Bench* (Sakana AI),
  arXiv:2506.08762 — the deep JP panel + independent evidence that a **naive persistence
  (momentum) baseline is hard to beat**, corroborating our universal-momentum finding
  (see [`SAKANA_COMPARISON.md`](SAKANA_COMPARISON.md)).

> Descriptive research pipeline. Not investment advice.
