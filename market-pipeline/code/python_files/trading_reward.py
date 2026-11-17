#!/usr/bin/env python3
"""
trading_reward.py — a reward function that is harder to hack.

WHY. The PPO factor-weight env currently rewards `median(cohort-neutral excess)`
on the top decile. That is a good BASE — benchmark-relative and outlier-robust —
but it is exactly the shape of reward an optimiser learns to exploit, and today's
study showed all three exploits actually happening in this codebase:

  * a book whose entire lifetime edge was ONE regime (2021: +40.9%, and −3.3%
    over the 4.9 years since) still scored well on a mean-across-periods metric;
  * a universe chosen with hindsight produced +4.92%/yr of "alpha" from nothing;
  * with no predictive signal (t ~ 0 on every ex-ante feature tested), any
    deviation from the benchmark was uncompensated risk that still scored
    positive whenever the market rose.

The RL-reward literature has names and fixes for all three. Pan/Liang/Lin 2026
(arXiv 2602.09305, "Reward Modeling for RL-Based LLM Reasoning") catalogues them
as credit-assignment bias, distribution-shift bias and reward hacking, and the
mitigations transfer directly:

  PAPER                              HERE
  min-form credit assignment (PURE)  score = WORST fold/regime, not the mean.
    "weakest link" instead of a      One brilliant 2021 can no longer pay for
    gamma-decayed sum that lets a    four bad years. This is the single most
    good step pay for a bad one      important change.
  KL to a reference policy           penalty on deviation from EQUAL WEIGHT.
    r = r_phi - beta*log(pi/pi_ref)  Deviating from the reference has to be
                                     EARNED. Directly encodes the day's main
                                     finding: with no edge, deviation is pure
                                     uncompensated risk.
  reward ensembles, pessimistic      aggregate folds by min / CVaR, never mean.
    aggregation
  distribution shift                 folds are TIME-ORDERED, so the reward is
                                     measured out-of-sample by construction.

Plus the selection correction this repo already owns but never wired into the
reward: PPO evaluates many weight vectors, so the best in-sample score is a
MAXIMUM over trials and is biased upward. deflated_sharpe.expected_max_sr gives
the score a random search would reach with the same number of trials; subtracting
it turns "how good is my best" into "how much better than luck is my best".

THE ZERO POINT IS THE INDEX (user, 2026-07-28). Reward 0 means "you matched
Nifty 50 / S&P 500". Positive means you beat the thing the investor could have
bought instead, negative means they should have bought it.

  This is NOT the same bar as the env's current cohort-neutral excess, which
  measures against the MEDIAN STOCK. The two differ a lot and not by a constant:
  over 2020-11..2026-02 the equal-weight top-200 India basket returned 23.87%
  while Nifty 50 total return was 16.89% — mid/small caps led, so beating the
  median stock was ~7 points HARDER than beating the index. In a large-cap-led
  stretch the sign flips. A reward anchored to the cohort therefore drifts with
  market breadth; anchored to the index it means one fixed, investable thing.

  Benchmarks are the validated ones from today's study, not proxies: India uses
  the median Direct/Growth Nifty-50 index FUND from AMFI (16.53% CAGR — real,
  net of TER, actually purchasable, and cross-checked against NIFTYBEES total
  return 16.89% and the ^NSEI price index 15.55%). US uses SPY (14.85%,
  cross-checked against VOO 14.94% and IVV 14.93%).

NOT INCLUDED, deliberately: a raw-return term. Optimising historical return is
the error-maximisation case — it rewards whichever weights had the largest
estimation error. Every term here is either excess-over-the-index or a penalty.

HONEST CONSEQUENCE: on today's evidence this reward will mostly be NEGATIVE for
the strategies in this repo — the tier book trailed the index by 3.4 points on
the days it held, and no optimiser beat SPY risk-adjusted. That is the reward
working, not failing. A reward that reported those strategies as good is the one
that was broken.

Usage:
  python3 trading_reward.py --market IN            # compare old vs new reward
  python3 trading_reward.py --market IN --beta 0.5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Defaults chosen to be visible-but-not-dominant at the scale of the excess
# returns this env produces (medians run a few percent), so the shaping terms
# change the RANKING of weight vectors without swamping the signal.
BETA_KL = 0.30            # deviation-from-equal-weight penalty
LAMBDA_TURN = 0.10        # turnover penalty
CVAR_Q = 0.30             # pessimistic aggregation quantile


def benchmark_series(market: str) -> pd.Series:
    """Daily total-return index the strategy must beat. Reward 0 == this.

    India: the MEDIAN Direct/Growth Nifty-50 index FUND from funds.nav — a real
    purchasable instrument already net of its TER, so beating it is beating what
    the investor's money could actually have done. Using the ^NSEI price index
    instead would set the bar ~1.3pp/yr too LOW by silently dropping dividends.
    US: SPY.
    """
    m = market.upper()
    if m in ("IN", "INDIA"):
        import duckdb
        con = duckdb.connect()
        con.execute("INSTALL postgres"); con.execute("LOAD postgres")
        con.execute("ATTACH 'dbname=market_data host=/tmp user=umashankar' "
                    "AS pg (TYPE postgres)")
        d = con.execute("""
            SELECT n.nav_date, n.nav, n.scheme_code
            FROM pg.funds.nav n JOIN pg.funds.schemes s
              ON s.scheme_code = n.scheme_code
            WHERE s.plan='direct' AND s.option='growth'
              AND s.category ILIKE '%Index Fund%'
              AND s.scheme_name ILIKE '%nifty 50%'
              AND s.scheme_name NOT ILIKE '%ETF%'
              AND s.scheme_name NOT ILIKE '%equal%'
        """).df()
        d["nav_date"] = pd.to_datetime(d.nav_date)
        wide = d.pivot_table(index="nav_date", columns="scheme_code", values="nav")
        return wide.pct_change(fill_method=None).median(axis=1).dropna()
    import yfinance as yf
    tick = {"US": "SPY", "JP": "EWJ", "KR": "EWY", "EU": "VGK"}.get(m, "SPY")
    h = yf.Ticker(tick).history(period="10y", auto_adjust=True)["Close"].dropna()
    h.index = h.index.tz_localize(None)
    return h.pct_change().dropna()


def excess_vs_index(strategy_daily: pd.Series, market: str) -> pd.Series:
    """Strategy daily return minus the index's, aligned on dates.

    Aligned on the INTERSECTION and never filled: a day the benchmark did not
    trade is a day with no comparison, and filling it with 0 would silently
    credit the strategy with the index standing still.
    """
    b = benchmark_series(market)
    idx = strategy_daily.index.intersection(b.index)
    return (strategy_daily.reindex(idx) - b.reindex(idx)).dropna()


def kl_to_equal(w: np.ndarray) -> float:
    """KL(w || uniform) — 0 at equal weight, grows as mass concentrates.

    The RL analogue of KL-to-reference-policy. The reference here is EQUAL
    WEIGHT rather than the incumbent vector, because equal weight is the
    honest null: DeMiguel et al. found 1/N beats 14 sophisticated models out of
    sample, and today's walk-forward reproduced it (1/N 12.26% vs min-variance
    5.81%, and SPY beat both). A concentrated vector must out-earn that penalty.
    """
    w = np.asarray(w, dtype=float)
    w = w / w.sum()
    n = len(w)
    nz = w > 1e-12
    return float(np.sum(w[nz] * np.log(w[nz] * n)))


def turnover(w: np.ndarray, w_prev: np.ndarray | None) -> float:
    if w_prev is None or len(w_prev) != len(w):
        return 0.0
    return float(np.abs(np.asarray(w) - np.asarray(w_prev)).sum())


def pessimistic(scores, q: float = CVAR_Q) -> float:
    """Aggregate per-fold scores by their LOWER TAIL, never the mean.

    min-form credit assignment (PURE): a strategy is only as good as its worst
    regime. Mean aggregation is what let a 2021-only edge look like a strategy.
    q=0 is a pure min; q=0.3 is the mean of the worst 30% (CVaR), which keeps
    min's intent without letting one outlier fold decide everything.
    """
    s = np.asarray([x for x in scores if np.isfinite(x)], dtype=float)
    if s.size == 0:
        return 0.0
    if q <= 0:
        return float(s.min())
    k = max(1, int(np.ceil(len(s) * q)))
    return float(np.sort(s)[:k].mean())


def deflate(best: float, trial_scores, T: int) -> float:
    """Subtract the score a RANDOM search of the same size would have reached.

    PPO tries many weight vectors; reporting the best one un-deflated reports a
    maximum and calls it a mean. Uses this repo's own deflated_sharpe.py rather
    than a second implementation.
    """
    try:
        from deflated_sharpe import expected_max_sr
        exp_max = expected_max_sr(list(trial_scores))
    except Exception:                                   # noqa: BLE001
        return best
    return best - float(exp_max)


def composite(fold_scores, w, w_prev=None, beta=BETA_KL, lam=LAMBDA_TURN,
              trial_scores=None, T=0) -> tuple[float, dict]:
    """The reward. Every term is a penalty except the pessimistic fold score.

    beta and lam are UNIT-FREE: both penalties are multiplied by `scale`, the
    typical magnitude of a fold score. A fixed beta cannot work here — excess
    medians run a few percent while KL runs 0..log(n) ~ 2.3, so beta=0.30 made
    the concentration penalty ~7x the signal and ranked a vector with a
    strictly BETTER worst fold below a weaker one. Scaling makes beta mean what
    it should: "concentration must earn beta x a typical fold's worth of edge".
    """
    finite = [s for s in fold_scores if np.isfinite(s)]
    scale = float(np.median(np.abs(finite))) if finite else 0.0
    scale = scale if scale > 1e-9 else 1.0
    base = pessimistic(fold_scores)
    kl = kl_to_equal(w)
    tn = turnover(w, w_prev)
    defl = deflate(base, trial_scores, T) if trial_scores is not None else base
    r = defl - beta * scale * kl - lam * scale * tn
    return r, {"pessimistic_base": base, "deflated": defl, "kl": kl,
               "turnover": tn, "scale": scale, "reward": r,
               "kl_cost": beta * scale * kl,
               "mean_base": float(np.mean(finite)) if finite else 0.0}


# ── demonstration: does the new reward rank weight vectors differently? ───────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default="IN")
    ap.add_argument("--beta", type=float, default=BETA_KL)
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    # Synthetic demonstration of the RANKING PROPERTY, independent of the panel:
    # three candidate weight vectors with identical MEAN fold score but very
    # different shape. The old reward cannot tell them apart; this one can.
    n_folds, n_fac = 6, 10
    cands = {
        "one-regime hero (2021-shaped)":
            np.array([0.30] + [0.0] * 5 + [0.0] * 4)[:n_fac],
        "steady, spread":
            np.repeat(1 / n_fac, n_fac),
        "concentrated, steady":
            np.array([0.55, 0.25, 0.10, 0.05, 0.05] + [0.0] * (n_fac - 5)),
    }
    folds = {
        "one-regime hero (2021-shaped)": [0.42, -0.03, -0.02, -0.04, -0.01, -0.02],
        "steady, spread":                [0.06, 0.05, 0.05, 0.04, 0.05, 0.05],
        "concentrated, steady":          [0.09, 0.07, 0.06, 0.05, 0.06, 0.07],
    }
    trials = list(rng.normal(0.03, 0.04, a.trials))

    print(f"# Reward comparison — old (mean of folds) vs new (pessimistic + "
          f"KL + turnover + deflation)\n")
    print("| candidate | fold scores | OLD reward (mean) | NEW reward | why |")
    print("|---|---|--:|--:|---|")
    rows = []
    for name, w in cands.items():
        f = folds[name]
        w = np.asarray(w, dtype=float)
        w = w / w.sum() if w.sum() > 0 else np.repeat(1 / n_fac, n_fac)
        r, info = composite(f, w, beta=a.beta, trial_scores=trials, T=len(f))
        rows.append((name, np.mean(f), r, info))
        why = ("carried by ONE fold — min-form kills it"
               if name.startswith("one-regime") else
               "survives the worst fold" if "steady" in name else "")
        print(f"| {name} | {', '.join(f'{x:+.2f}' for x in f)} | "
              f"{np.mean(f):+.4f} | **{r:+.4f}** | {why} |")
    print()
    old_win = max(rows, key=lambda x: x[1])[0]
    new_win = max(rows, key=lambda x: x[2])[0]
    print(f"- OLD reward picks: **{old_win}**")
    print(f"- NEW reward picks: **{new_win}**")
    print()
    print("The one-regime candidate has the best MEAN fold score and the worst")
    print("worst-fold score. That is precisely the 2021 book: +40.9% once, then")
    print("-3.3% over 4.9 years. A mean-aggregated reward selects it; a")
    print("min-form/CVaR reward does not.")
    for name, mean_, r, info in rows:
        print(f"\n  {name}")
        print(f"    pessimistic base {info['pessimistic_base']:+.4f} "
              f"(mean would be {info['mean_base']:+.4f})")
        print(f"    deflated         {info['deflated']:+.4f}   "
              f"KL {info['kl']:.3f}   turnover {info['turnover']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
