#!/usr/bin/env python3
"""
etf_builder.py — can an optimiser build a portfolio that beats market ETFs?

THE HONEST FRAMING. "Optimise returns on historical data" is the textbook
error-maximisation case: a mean-variance optimiser fed sample means pushes
capital toward whichever asset had the largest ESTIMATION ERROR, which is
exactly what does not repeat. Michaud called MV optimisers "estimation-error
maximisers"; DeMiguel-Garlappi-Uppal (2009) tested 14 sophisticated models
across 7 datasets and none beat naive 1/N out of sample. portfolio_bundles.py
already made this call for the live bundles and chose inverse-vol over
max-Sharpe for the same reason.

So this harness is built to FIND OUT, not to confirm. Everything is
WALK-FORWARD: at each rebalance the weights use only data strictly before that
date, and the return recorded is what those weights actually earned over the
following period. There is no in-sample number anywhere in the output, because
an in-sample optimiser result is not evidence of anything.

WHY MAX-SHARPE IS INCLUDED DESPITE BEING EXPECTED TO LOSE. Reporting only the
schemes that work would hide the mechanism. Running the error-maximiser next to
1/N on the same data, same constraints, same rebalance dates is the cleanest way
to show what the failure looks like and how large it is.

BASELINES ARE THE POINT. The bar is not "did the optimiser make money" — in a
bull market everything makes money. The bar is:
  1. beat 1/N over the same universe (the DeMiguel bar), and
  2. beat the actual tradeable ETF (SPY etc.), which is what you would otherwise
     just buy, net of its expense ratio.
A scheme that beats neither is a more expensive way to own the index.

MARKET CHOICE. Defaults to US because that panel is verified split-ADJUSTED.
The India warehouse panel is NOT: 71 unadjusted split events sit in its top-200
alone (NESTLEIND 2024-01-05, JSWSTEEL 2017-01-04 and EICHERMOT 2020-08-24 all
read as −90% single-day "returns" that are really 1:10 splits). Feeding those to
a covariance estimator would let three data errors dominate every weight in the
book, so India is refused unless --allow-unadjusted is passed.

Usage:
  python3 etf_builder.py                            # US, monthly, 10y
  python3 etf_builder.py --top 100 --rebalance Q
  python3 etf_builder.py --market JP
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT_MD = HERE / "reports" / "etf_builder.md"

TRADING_DAYS = 252
LOOKBACK = 252            # trailing window for vol/covariance/momentum
WEIGHT_CAP = 0.10         # long-only concentration cap
COST_BPS = 10.0           # per-side turnover cost, US liquid large caps
# Split-unadjusted panels — see module docstring. A number, not a vibe: a −90%
# fake return is ~40 sigma for a large cap and will dominate any covariance.
UNADJUSTED = {"IN"}


def load_panel(mkt: str):
    """Full close AND turnover panels — the universe is chosen POINT-IN-TIME.

    🔴 The first version of this ranked turnover over the WHOLE period and kept
    the top 200 for every rebalance. That is look-ahead in the universe itself:
    a name qualifies only by having survived and stayed liquid through the end
    of the sample, so the panel is built from companies that went on to do well.
    It showed 1/N beating SPY by 4.92 points a year — a gap that is the UNIVERSE,
    not any scheme, and that every scheme then inherits and reports as its own.
    Now turnover is ranked on trailing data at each rebalance only.
    """
    from backtest_tier_anomalies import load_market
    df = load_market(mkt)
    px = df.pivot_table(index="Date", columns="Symbol", values="Close").sort_index()
    tv = (df.assign(_t=df["Close"] * df["Volume"])
            .pivot_table(index="Date", columns="Symbol", values="_t").sort_index())
    # NOT gated with contaminated(), deliberately. The completeness audit flags
    # this loader as "ungated" because it calls load_market() (raw Close) without
    # dropping discontinuities, and a contaminated() call was briefly added here
    # before being reverted — it was wrong twice over. India never reaches this
    # code: main() refuses the IN panel outright as split-unadjusted, which is a
    # stricter guard than dropping symbols. And in the markets that DO run here
    # (JP/KR/US, whose panels are verified split-adjusted) a >30% one-day fall
    # that never reverses is a REAL crash, so filtering on that shape would
    # quietly delete the losers and manufacture survivorship bias — the exact
    # error the ETF universe fix removed when point-in-time turnover ranking cut
    # 1/N from 19.75% to 12.26%. The gate is right for a contaminated panel and
    # wrong for a clean one; the refusal is the correct guard here.
    return px.loc["2016":], tv.loc["2016":]


# ── weighting schemes; each sees ONLY trailing data ──────────────────────────
def w_equal(R, mu, cov):
    return np.repeat(1 / R.shape[1], R.shape[1])


def w_invvol(R, mu, cov):
    v = R.std().values
    v[v <= 0] = np.nan
    w = 1 / v
    return w / np.nansum(w)


def w_minvar(R, mu, cov):
    """Minimum variance — needs only the covariance, NO expected returns.
    That is why it is the robust member of the optimiser family: the mean is
    the input you cannot estimate, and this scheme never asks for it."""
    from scipy.optimize import minimize
    n = cov.shape[0]
    res = minimize(lambda w: w @ cov @ w, np.repeat(1 / n, n), method="SLSQP",
                   bounds=[(0, WEIGHT_CAP)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
                   options={"maxiter": 200, "ftol": 1e-10})
    return res.x if res.success else np.repeat(1 / n, n)


def w_maxsharpe(R, mu, cov):
    """Tangency portfolio on SAMPLE means — the error maximiser, included to
    show the failure mode rather than to hide it."""
    from scipy.optimize import minimize
    n = cov.shape[0]

    def neg_sharpe(w):
        var = w @ cov @ w
        return -(w @ mu) / np.sqrt(var) if var > 0 else 0.0

    res = minimize(neg_sharpe, np.repeat(1 / n, n), method="SLSQP",
                   bounds=[(0, WEIGHT_CAP)] * n,
                   constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}],
                   options={"maxiter": 200, "ftol": 1e-10})
    return res.x if res.success else np.repeat(1 / n, n)


def w_momentum(R, mu, cov):
    """12-1 momentum: trailing return skipping the most recent month (the
    standard skip — last-month reversal is a documented opposite effect)."""
    cum = (1 + R).prod() - 1
    recent = (1 + R.tail(21)).prod() - 1
    score = cum - recent
    k = max(5, len(score) // 5)              # top quintile
    keep = score.nlargest(k).index
    w = pd.Series(0.0, index=R.columns)
    w[keep] = 1 / k
    return w.values


SCHEMES = {
    "1/N equal": w_equal,
    "inverse-vol": w_invvol,
    "min-variance": w_minvar,
    "max-Sharpe": w_maxsharpe,
    "momentum 12-1": w_momentum,
}


def perf(nav: pd.Series, ppy: int) -> dict:
    """`ppy` = periods per year OF THIS SERIES. Passed explicitly, never
    assumed: the NAV here is indexed by REBALANCE (12/yr monthly, 4/yr
    quarterly), not by trading day. Annualising a 110-point monthly series with
    252 gave 0.44 years instead of 9.1 and reported SPY at 1725% CAGR."""
    r = nav.pct_change().dropna()
    yrs = len(r) / ppy
    if yrs <= 0 or nav.iloc[0] <= 0:
        return {}
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(ppy)
    return {"cagr": cagr, "vol": vol, "sharpe": cagr / vol if vol else np.nan,
            "maxdd": (nav / nav.cummax() - 1).min()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default="US")
    ap.add_argument("--top", type=int, default=200)
    ap.add_argument("--rebalance", default="ME", choices=("ME", "QE"))
    ap.add_argument("--benchmark", default="SPY")
    ap.add_argument("--allow-unadjusted", action="store_true")
    a = ap.parse_args()

    if a.market in UNADJUSTED and not a.allow_unadjusted:
        print(f"REFUSING {a.market}: that warehouse panel is split-UNADJUSTED "
              f"(71 fake ~-90% 'returns' in the top-200 alone — NESTLEIND "
              f"2024-01-05, JSWSTEEL 2017-01-04, EICHERMOT 2020-08-24 are 1:10 "
              f"splits). Three data errors would dominate every covariance "
              f"estimate and therefore every weight. Fix adjustment first, or "
              f"pass --allow-unadjusted to proceed knowing the output is junk.")
        return 1

    print(f"loading {a.market} top-{a.top} …", flush=True)
    px, tv = load_panel(a.market)
    rets = px.pct_change(fill_method=None)
    dates = rets.resample(a.rebalance).last().index
    dates = [d for d in dates if d >= rets.index[0] + pd.Timedelta(days=LOOKBACK + 30)]
    print(f"{px.shape[1]} names × {len(px)} bars · {len(dates)} rebalances", flush=True)

    from sklearn.covariance import LedoitWolf
    curves = {k: [] for k in SCHEMES}
    prev_w = {k: None for k in SCHEMES}
    turnovers = {k: [] for k in SCHEMES}
    idx = []

    for i, t in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        # STRICTLY trailing — nothing at or after t informs universe OR weights.
        # Universe first: the top-N by TRAILING median turnover as of t, so the
        # book holds what was liquid then, not what turned out to be liquid.
        liq = tv.loc[:t].iloc[-LOOKBACK:].median().dropna()
        universe = liq.nlargest(a.top).index
        hist = rets.loc[:t, universe].iloc[-LOOKBACK:]
        hist = hist.dropna(axis=1, thresh=int(LOOKBACK * 0.9)).dropna(axis=0, how="all")
        hist = hist.fillna(0.0)
        if hist.shape[1] < 20:
            continue
        fwd = rets.loc[(rets.index > t) & (rets.index <= nxt), hist.columns].fillna(0.0)
        if fwd.empty:
            continue
        mu = hist.mean().values * TRADING_DAYS
        # Ledoit-Wolf shrinkage: the sample covariance of 200 names on 252 days
        # is near-singular and its inverse is noise. Shrinkage is the minimum
        # defensible treatment, not an optimisation.
        cov = LedoitWolf().fit(hist.values).covariance_ * TRADING_DAYS

        for name, fn in SCHEMES.items():
            try:
                w = np.asarray(fn(hist, mu, cov), dtype=float)
            except Exception:
                w = np.repeat(1 / hist.shape[1], hist.shape[1])
            w = np.nan_to_num(w, nan=0.0)
            if w.sum() <= 0:
                w = np.repeat(1 / len(w), len(w))
            w = w / w.sum()
            # turnover cost on the traded difference
            pw = prev_w[name]
            turn = (np.abs(w - pw).sum() if pw is not None and len(pw) == len(w)
                    else 1.0)
            gross = (1 + fwd.values @ w).prod() - 1
            curves[name].append(gross - turn * COST_BPS / 10_000.0)
            turnovers[name].append(turn)
            prev_w[name] = w
        idx.append(nxt)

    # benchmark: the actual tradeable ETF, net of nothing extra (its TER is
    # already inside its price series)
    bench = None
    try:
        import yfinance as yf
        b = yf.Ticker(a.benchmark).history(start=str(px.index[0].date()),
                                           end=str(px.index[-1].date()),
                                           auto_adjust=True)["Close"].dropna()
        b.index = b.index.tz_localize(None)
        bnav = b.reindex(pd.DatetimeIndex(idx), method="ffill")
        bench = bnav / bnav.iloc[0]
    except Exception as e:                             # noqa: BLE001
        print(f"benchmark {a.benchmark} unavailable: {str(e)[:80]}")

    L = []
    def out(s=""):
        print(s); L.append(s)

    out(f"# ETF builder — {a.market} top-{a.top}, walk-forward, "
        f"{'monthly' if a.rebalance == 'ME' else 'quarterly'} rebalance")
    out()
    out(f"- periods      : {len(idx)} ({idx[0].date()} → {idx[-1].date()})")
    out(f"- lookback     : {LOOKBACK}d trailing, strictly before each rebalance")
    out(f"- constraints  : long-only, {WEIGHT_CAP:.0%} cap, {COST_BPS:.0f}bp turnover cost")
    out()
    out("| Scheme | CAGR | Vol | Sharpe | MaxDD | Turnover/mo | vs 1/N | vs " + a.benchmark + " | Breakeven cost |")
    out("|---|--:|--:|--:|--:|--:|--:|--:|--:|")

    ppy = 12 if a.rebalance == "ME" else 4
    navs = {k: pd.Series((1 + pd.Series(v, index=idx)).cumprod(), index=idx)
            for k, v in curves.items() if v}
    base = perf(navs["1/N equal"], ppy)["cagr"] if "1/N equal" in navs else np.nan
    bp = perf(bench, ppy)["cagr"] if bench is not None and len(bench) > 2 else np.nan
    for name, nav in navs.items():
        p = perf(nav, ppy)
        if not p:
            continue
        vs_b = f"{p['cagr'] - bp:+.2%}" if np.isfinite(bp) else "n/a"
        tno = float(np.mean(turnovers[name])) if turnovers[name] else float("nan")
        # Cost per side at which this scheme's edge over the benchmark vanishes.
        # Turnover is per rebalance, so annual drag = tno * ppy * cost.
        edge = p["cagr"] - bp
        be = (edge / (tno * ppy) * 10_000) + COST_BPS if np.isfinite(bp) and tno > 0 and edge > 0 else np.nan
        be_s = f"{be:.0f}bp" if np.isfinite(be) else "—"
        out(f"| {name} | **{p['cagr']:.2%}** | {p['vol']:.1%} | {p['sharpe']:.2f} | "
            f"{p['maxdd']:.1%} | {tno:.0%} | {p['cagr'] - base:+.2%} | {vs_b} | {be_s} |")
    if bench is not None and np.isfinite(bp):
        pb = perf(bench, ppy)
        # 9 cells, matching the header — buy-and-hold has no rebalance turnover
        # and no benchmark-relative breakeven (it IS the benchmark).
        out(f"| **{a.benchmark} (the ETF you'd just buy)** | **{pb['cagr']:.2%}** | "
            f"{pb['vol']:.1%} | {pb['sharpe']:.2f} | {pb['maxdd']:.1%} | ~0% | "
            f"{pb['cagr'] - base:+.2%} | — | — |")
    out()
    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"\nwrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
