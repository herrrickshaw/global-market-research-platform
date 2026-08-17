#!/usr/bin/env python3
"""
sip_xirr_backtest.py — what a monthly SIP actually earned, vs the headline CAGR.

WHY THE HEADLINE NUMBER IS THE WRONG ONE. Every return figure this platform has
produced — Sharpe, annualised return, factor spreads — assumes a single lump sum
at the start. Indian retail does not invest that way; it invests monthly ("The
Rs 10-a-Day SIP Already Exists"). Those are different questions with different
answers, and the gap is not a rounding detail:

  * CAGR is TIME-weighted. It answers "what did the index do", and every rupee
    counts equally regardless of when it arrived.
  * XIRR is MONEY-weighted. It answers "what did the investor earn", and weights
    each rupee by how long it was actually invested.

A SIP buys more units when prices are low, so in a market that falls then
recovers, XIRR EXCEEDS the CAGR — the investor did better than the index. In a
market that rises steadily and then stalls, XIRR falls BELOW it, because most of
the money arrived near the top. Quoting CAGR to a SIP investor is quoting a
number about a portfolio they never held.

🔴 AND THE TWO CAN RANK FUNDS DIFFERENTLY, which is the operational point. A
volatile index with a strong finish can beat a smooth one on CAGR while losing
on XIRR, because the SIP investor's later — larger — instalments bought the
expensive units. Any fund recommendation built on CAGR alone is therefore
answering a question the reader did not ask.

XIRR is solved by bisection rather than Newton: cashflow sign patterns here are
regular enough that bisection cannot diverge, and a silently non-converged IRR is
exactly the kind of plausible-looking wrong number this codebase keeps finding.

    python3 sip_xirr_backtest.py
    python3 sip_xirr_backtest.py --years 5 --monthly 10000
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys

import numpy as np
import pandas as pd

DEFAULT_INDICES = [
    "Nifty 50", "Nifty 500", "Nifty Midcap 150", "Nifty Smallcap 250",
    "Nifty Alpha 50", "Nifty50 Value 20", "Nifty Low Volatility 50",
    "NIFTY50 Equal Weight", "Nifty100 Low Volatility 30",
    "NIFTY Alpha Quality Value Low-Volatility 30",
]


def load() -> pd.DataFrame:
    q = ("COPY (SELECT index_name, index_date, close FROM indices.nse_daily "
         "WHERE close > 0 ORDER BY index_name, index_date) TO STDOUT WITH CSV HEADER")
    r = subprocess.run(["psql", "-d", "market_data", "-c", q],
                       capture_output=True, text=True, timeout=300)
    return pd.read_csv(io.StringIO(r.stdout), parse_dates=["index_date"])


def xirr(dates: list, amounts: list, lo: float = -0.99, hi: float = 10.0) -> float:
    """Money-weighted return, by bisection.

    Bisection over Newton deliberately: Newton needs a derivative and a decent
    starting guess and can wander off on an irregular cashflow, returning a
    number that looks fine. Bisection either brackets a root or reports that it
    could not — which is the failure mode worth having.
    """
    t0 = dates[0]
    yrs = np.array([(d - t0).days / 365.0 for d in dates])
    amt = np.array(amounts, dtype=float)

    def npv(r: float) -> float:
        return float((amt / (1.0 + r) ** yrs).sum())

    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return float("nan")                     # no sign change: no bracketed root
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def run_one(px: pd.Series, monthly: float) -> dict:
    """Invest `monthly` on the first trading day of each month; hold to the end."""
    m = px.resample("MS").first().dropna()      # first available price each month
    if len(m) < 24:
        return {}
    units, dates, flows = 0.0, [], []
    for d, p in m.items():
        units += monthly / p
        dates.append(d)
        flows.append(-monthly)                  # outflow from the investor
    end_d, end_p = px.index[-1], px.iloc[-1]
    final = units * end_p
    dates.append(end_d)
    flows.append(final)                         # terminal inflow

    invested = monthly * len(m)
    years = (end_d - m.index[0]).days / 365.0
    lump_units = invested / px.loc[px.index >= m.index[0]].iloc[0]
    lump_final = lump_units * end_p

    return {
        "months": len(m), "years": round(years, 1),
        "invested": invested, "sip_final": final,
        "sip_xirr_%": xirr(dates, flows) * 100,
        "sip_multiple": final / invested,
        # Lump sum of the SAME total at the SAME start — the like-for-like
        # comparison. Comparing a SIP against an index CAGR alone would compare
        # different amounts of money invested for different lengths of time.
        "lump_cagr_%": ((lump_final / invested) ** (1 / years) - 1) * 100 if years > 0 else np.nan,
        "lump_multiple": lump_final / invested,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--monthly", type=float, default=5000)
    p.add_argument("--years", type=float, default=0, help="0 = all available history")
    p.add_argument("--indices", nargs="*", default=DEFAULT_INDICES)
    a = p.parse_args()

    d = load()
    rows = []
    for name in a.indices:
        g = d[d.index_name == name].sort_values("index_date")
        if g.empty:
            continue
        s = g.set_index("index_date").close
        if a.years:
            s = s[s.index >= s.index.max() - pd.Timedelta(days=int(a.years * 365))]
        r = run_one(s, a.monthly)
        if r:
            rows.append({"index": name, **r})
    if not rows:
        print("no index matched"); return 1

    t = pd.DataFrame(rows).sort_values("sip_xirr_%", ascending=False)
    t["xirr_minus_cagr"] = t["sip_xirr_%"] - t["lump_cagr_%"]
    print(f"# SIP vs lump sum — Rs {a.monthly:,.0f}/month\n")
    print(t[["index", "years", "months", "sip_xirr_%", "lump_cagr_%",
             "xirr_minus_cagr", "sip_multiple", "lump_multiple"]]
          .to_string(index=False, float_format=lambda x: f"{x:9.2f}"))

    # Does the ordering actually change? That is the operational question.
    by_x = list(t.sort_values("sip_xirr_%", ascending=False)["index"])
    by_c = list(t.sort_values("lump_cagr_%", ascending=False)["index"])
    print(f"\nRank by XIRR : {by_x[0]}  >  {by_x[1]}  >  {by_x[2]}")
    print(f"Rank by CAGR : {by_c[0]}  >  {by_c[1]}  >  {by_c[2]}")
    if by_x[:3] != by_c[:3]:
        print("🔴 The two measures DISAGREE on the top three. A fund ranked on CAGR is")
        print("   not the fund a monthly investor would have done best in.")
    else:
        print("Top three agree — here the choice of measure does not change the pick.")
    print(f"\nMean XIRR − CAGR gap: {t.xirr_minus_cagr.mean():+.2f} pts "
          f"(negative = the SIP investor trailed the index, because later, larger")
    print(f"instalments bought units at higher prices).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
