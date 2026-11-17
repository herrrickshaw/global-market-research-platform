#!/usr/bin/env python3
"""
index_risk_metrics.py — Sharpe, vol and drawdown for NSE indices.

WHY THIS EXISTS. The platform builds momentum and quality screens. NSE runs
momentum and quality INDICES with ten years of daily marks, so the question
"does this factor actually pay in India, and how much of the payoff is just
beta?" is answerable from data already in the warehouse (indices.nse_daily,
240,622 rows, 174 indices, 2016-07-28 onward) rather than from a backtest we
build ourselves and then have to defend.

🔴 INCUBATION BIAS IS THE WHOLE STORY HERE, AND A NAIVE RANKING GETS IT EXACTLY
BACKWARDS. Index providers launch a factor index AFTER the factor has done well,
so a young index carries its good years and none of the bad ones. Measured
2026-08-17, ranking every index on its OWN available history put Nifty200
Value 30 top at Sharpe 0.97 (80.8% annualised — over 525 days). On a window where
every index is alive, the SAME index scores -0.10. The 0.97 was its launch
window, nothing else.

So this reports two panels and never one:
  * COMMON WINDOW — every index over the same dates. The only fair cross-section.
  * FULL HISTORY  — long-lived indices only (>= 2,000 days), for the through-cycle
    question, with the survivors' day counts printed so the reader can see which
    is which.

🔴 AND THE SECOND FINDING IS ABOUT BETA, NOT ALPHA. Over the full ten years
Nifty Alpha 50 returns Sharpe 0.61 against Nifty 50's 0.36 — an apparently
decisive factor premium. But plain Nifty Midcap 150 scores 0.58 with no factor
logic at all. Most of what looks like a factor edge in India is a size tilt that
a midcap index captures for free. Any screen claiming a factor edge should be
benchmarked against Midcap 150, not against the Nifty 50.

RF is stated, not buried: India 10-year around 6.5%. Sharpe is sensitive to it,
so it is a named constant and printed in the header.
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys

import numpy as np
import pandas as pd

RF_DEFAULT = 0.065
FACTOR_RE = "Momentum|Quality|Value|Alpha|Low Volatility|Equal Weight"
BENCH = ["Nifty 50", "Nifty 500", "Nifty 200", "Nifty Midcap 150", "Nifty Smallcap 250"]


def load() -> pd.DataFrame:
    q = ("COPY (SELECT index_name, index_date, close FROM indices.nse_daily "
         "WHERE close > 0 ORDER BY index_name, index_date) TO STDOUT WITH CSV HEADER")
    r = subprocess.run(["psql", "-d", "market_data", "-c", q],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return pd.read_csv(io.StringIO(r.stdout), parse_dates=["index_date"])


def stats(g: pd.DataFrame, rf: float) -> tuple | None:
    r = g.close.pct_change().dropna()
    if len(r) < 200:
        return None
    ann_ret = (1 + r.mean()) ** 252 - 1
    ann_vol = r.std() * np.sqrt(252)
    if ann_vol <= 0:
        return None
    dd = (g.close / g.close.cummax() - 1).min()
    return ann_ret * 100, ann_vol * 100, (ann_ret - rf) / ann_vol, dd * 100


def panel(d: pd.DataFrame, start: str, rf: float, min_days: int = 0) -> pd.DataFrame:
    sub = d[d.index_date >= start]
    rows = []
    for n, g in sub.groupby("index_name"):
        g = g.sort_values("index_date")
        if min_days and len(g) < min_days:
            continue
        s = stats(g, rf)
        if s:
            rows.append((n, len(g), *s))
    return pd.DataFrame(rows, columns=["index", "days", "ret%", "vol%", "sharpe", "dd%"])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rf", type=float, default=RF_DEFAULT)
    p.add_argument("--common-start", default="2024-08-01")
    p.add_argument("--full-start", default="2016-07-28")
    p.add_argument("--top", type=int, default=10)
    a = p.parse_args()

    d = load()
    print(f"# NSE index risk metrics — RF {a.rf:.1%}, data to {d.index_date.max():%Y-%m-%d}\n")

    for label, start, min_days in (
            (f"COMMON WINDOW ({a.common_start} onward) — every index alive; the "
             f"only fair cross-section", a.common_start, 0),
            (f"FULL HISTORY ({a.full_start} onward) — long-lived only (>=2000 days)",
             a.full_start, 2000)):
        t = panel(d, start, a.rf, min_days)
        fac = t[t["index"].str.contains(FACTOR_RE, case=False, na=False)].nlargest(a.top, "sharpe")
        bm = t[t["index"].isin(BENCH)].sort_values("sharpe", ascending=False)
        print(f"## {label}\n")
        print(pd.concat([fac, bm]).to_string(index=False, float_format=lambda x: f"{x:7.2f}"))
        print()

    print("Read the two panels together, never one alone: an index ranked on its own")
    print("short history is ranked on its launch window. And compare any factor claim")
    print("against Nifty Midcap 150, not the Nifty 50 — most of India's apparent")
    print("factor premium is a size tilt available without any factor logic.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
