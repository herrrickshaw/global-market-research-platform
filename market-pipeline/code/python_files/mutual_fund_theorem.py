#!/usr/bin/env python3
"""
mutual_fund_theorem.py — two-fund separation over NSE indices. Step 1.

THE IDEA. Tobin's mutual fund theorem: with a risk-free asset available, every
mean-variance investor holds the SAME risky portfolio — the tangency (max-Sharpe)
portfolio — and expresses risk appetite only through how much of it they hold
against cash. If that holds here, the question "which NSE factor index should a
fund track?" has a single answer, and everything else is leverage.

This is step one deliberately: build the frontier, find the tangency portfolio,
and then STRESS IT before believing a single weight.

🔴 MEAN-VARIANCE OPTIMISATION IS AN ERROR MAXIMISER, and on this dataset that is
not a footnote — it is the finding. Markowitz weights are Σ⁻¹(μ−rf), so the
optimiser loads onto whichever asset has the most overstated mean and the most
understated covariance. Michaud (1989) named this "error maximisation". Estimated
means are the weak link: the standard error on a 10-year annualised mean equity
return is several percentage points, which is the same order as the differences
being optimised over. Equity indices from ONE market make it worse — they are
90%+ correlated, so Σ is near-singular and its inverse amplifies noise.

That is why this script reports the split-sample weight comparison alongside the
headline portfolio. If first-half and second-half weights disagree violently, the
tangency portfolio is an artefact of the sample and no fund should be built on
it — however good its in-sample Sharpe looks.

🔴 AND THE BENCHMARK IS MIDCAP 150, NOT NIFTY 50. index_risk_metrics.py measured
Nifty Midcap 150 at Sharpe 0.58 over ten years against Nifty 50's 0.36 and Alpha
50's 0.61. A tangency portfolio that cannot beat a plain midcap index has bought
complexity for nothing.

    python3 mutual_fund_theorem.py
    python3 mutual_fund_theorem.py --long-only
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys

import numpy as np
import pandas as pd

RF = 0.065
TRADING_DAYS = 252

# Long-lived indices only. A tangency portfolio over assets with different start
# dates silently optimises over different periods per asset, which is the
# incubation bias of index_risk_metrics.py wearing a portfolio disguise.
CANDIDATES = [
    "Nifty 50", "Nifty 500", "Nifty Midcap 150", "Nifty Smallcap 250",
    "Nifty Alpha 50", "Nifty50 Value 20", "Nifty Low Volatility 50",
    "Nifty100 Low Volatility 30", "NIFTY50 Equal Weight",
    "NIFTY Alpha Low-Volatility 30", "NIFTY Alpha Quality Low-Volatility 30",
    "NIFTY Alpha Quality Value Low-Volatility 30",
]


def load_returns(min_days: int = 1800) -> pd.DataFrame:
    q = ("COPY (SELECT index_name, index_date, close FROM indices.nse_daily "
         "WHERE close > 0 ORDER BY index_name, index_date) TO STDOUT WITH CSV HEADER")
    r = subprocess.run(["psql", "-d", "market_data", "-c", q],
                       capture_output=True, text=True, timeout=300)
    d = pd.read_csv(io.StringIO(r.stdout), parse_dates=["index_date"])
    d = d[d.index_name.isin(CANDIDATES)]
    px = d.pivot(index="index_date", columns="index_name", values="close").sort_index()
    keep = [c for c in px.columns if px[c].notna().sum() >= min_days]
    # dropna AFTER selecting columns: one short series would otherwise truncate
    # the common window for every asset, which is how a 10-year study quietly
    # becomes a 2-year one.
    return px[keep].dropna().pct_change().dropna()


def tangency(mu: np.ndarray, cov: np.ndarray, rf: float, long_only: bool) -> np.ndarray:
    excess = mu - rf
    if not long_only:
        w = np.linalg.pinv(cov) @ excess          # pinv: cov is near-singular here
        return w / w.sum()
    from scipy.optimize import minimize
    n = len(mu)
    neg_sharpe = lambda w: -((w @ excess) / np.sqrt(w @ cov @ w))
    res = minimize(neg_sharpe, np.repeat(1 / n, n), method="SLSQP",
                   bounds=[(0, 1)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}])
    return res.x


def describe(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> tuple:
    r = w @ mu
    v = np.sqrt(w @ cov @ w)
    return r, v, (r - rf) / v


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--long-only", action="store_true",
                   help="no shorting — what a mutual fund can actually hold")
    p.add_argument("--rf", type=float, default=RF)
    a = p.parse_args()

    rets = load_returns()
    names = list(rets.columns)
    mu = rets.mean().values * TRADING_DAYS
    cov = rets.cov().values * TRADING_DAYS
    print(f"# Two-fund separation over {len(names)} long-lived NSE indices")
    print(f"{len(rets):,} common trading days, "
          f"{rets.index.min():%Y-%m-%d} to {rets.index.max():%Y-%m-%d}, RF {a.rf:.1%}\n")

    # How correlated are these really? It governs how trustworthy Σ⁻¹ is.
    c = rets.corr().values
    off = c[~np.eye(len(c), dtype=bool)]
    print(f"Pairwise correlation: median {np.median(off):.2f}, min {off.min():.2f}, "
          f"max {off.max():.2f}")
    print(f"Covariance condition number: {np.linalg.cond(cov):,.0f}   "
          f"(>1e4 means the inverse is amplifying noise)\n")

    w = tangency(mu, cov, a.rf, a.long_only)
    r, v, s = describe(w, mu, cov, a.rf)
    kind = "long-only" if a.long_only else "unconstrained"
    print(f"## Tangency portfolio ({kind})\n")
    for n, wi in sorted(zip(names, w), key=lambda x: -abs(x[1])):
        if abs(wi) > 0.005:
            print(f"   {n:<44}{wi:>8.1%}")
    print(f"\n   return {r:.2%}   vol {v:.2%}   SHARPE {s:.3f}")

    bench = "Nifty Midcap 150"
    if bench in names:
        i = names.index(bench)
        bs = (mu[i] - a.rf) / np.sqrt(cov[i, i])
        print(f"   vs {bench}: Sharpe {bs:.3f} "
              f"({'tangency wins' if s > bs else '🔴 BENCHMARK WINS'})")

    # ── the stress test that decides whether any of this is usable ───────────
    print(f"\n## Split-sample stability — the test that matters\n")
    half = len(rets) // 2
    ws = []
    for lbl, sub in (("first half", rets.iloc[:half]), ("second half", rets.iloc[half:])):
        m2 = sub.mean().values * TRADING_DAYS
        c2 = sub.cov().values * TRADING_DAYS
        w2 = tangency(m2, c2, a.rf, a.long_only)
        ws.append(w2)
        _, _, s2 = describe(w2, m2, c2, a.rf)
        print(f"   {lbl:<12} ({sub.index.min():%Y-%m}–{sub.index.max():%Y-%m}) "
              f"in-sample Sharpe {s2:.3f}")
    turnover = np.abs(ws[0] - ws[1]).sum() / 2
    print(f"\n   weight turnover between halves: {turnover:.1%}")
    print("   largest disagreements:")
    for n, d_ in sorted(zip(names, ws[1] - ws[0]), key=lambda x: -abs(x[1]))[:5]:
        print(f"     {n:<44}{d_:>+8.1%}")
    if turnover > 0.5:
        print("\n   🔴 Over half the portfolio changes between halves. These weights")
        print("      describe the sample, not the market. Do not build a fund on them")
        print("      without shrinkage (Ledoit-Wolf) or hard position constraints.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
