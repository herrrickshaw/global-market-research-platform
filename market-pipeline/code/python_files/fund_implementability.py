#!/usr/bin/env python3
"""
fund_implementability.py — can a retail investor actually HOLD this portfolio?

WHY THIS TEST DOES NOT EXIST IN THE STANDARD TOOLKIT. Mean-variance says nothing
about whether a portfolio is purchasable. It assumes infinitely divisible assets,
which is fine for an institution and false for an Indian retail investor: India
has no fractional share ownership, so every position must be a WHOLE number of
shares. A 50-stock portfolio containing a Rs 1.5 lakh share cannot be held at
Rs 5,000/month at any weighting — the optimiser will happily hand you weights
that cannot be executed, and its Sharpe is then a number about a portfolio nobody
can own.

Two facts from the masaladeutsch series make this concrete rather than academic:
fractional investing still is not available for Indian stocks ("A Slice of MRF
Still Isn't Legal"), while the monthly SIP is how retail actually invests
("The Rs 10-a-Day SIP Already Exists"). Together they mean the real question is
not "what is the tangency portfolio" but "what is the smallest SIP that tracks it,
and what does whole-share rounding cost".

WHAT IT MEASURES
  * min viable SIP — the smallest monthly rupee amount at which every intended
    position gets at least one share.
  * rounding drag — the tracking error between intended weights and the weights
    you actually end up holding after rounding down to whole shares. This is a
    real, permanent cost of a concentrated or high-priced portfolio, and it falls
    hardest on exactly the small investor the SIP is meant to serve.
  * cash residual — money that cannot be deployed because it buys no whole share.

🔴 ROUNDING DRAG IS NOT SYMMETRIC AND THAT IS THE POINT. Rounding DOWN to whole
shares systematically under-weights expensive stocks and leaves cash idle, so a
portfolio's realised weights drift toward its cheap names — a size/price tilt
nobody chose and the backtest never modelled.

    python3 fund_implementability.py --index "Nifty Alpha 50"
    python3 fund_implementability.py --index "Nifty 50" --sip 5000 25000 100000
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys

import numpy as np
import pandas as pd


def psql_csv(q: str) -> pd.DataFrame:
    r = subprocess.run(["psql", "-d", "market_data", "-c",
                        f"COPY ({q}) TO STDOUT WITH CSV HEADER"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300])
    return pd.read_csv(io.StringIO(r.stdout))


def constituents(index_name: str) -> list[str]:
    d = psql_csv("SELECT DISTINCT symbol FROM indices.nse_membership "
                 f"WHERE index_name ILIKE '{index_name}'")
    return sorted(d.symbol.astype(str).str.upper())


def prices(symbols: list[str]) -> pd.Series:
    """Latest close per symbol from the India bhavcopy — the price a retail buyer
    actually faces, not an index level."""
    inlist = ",".join(f"'{s}'" for s in symbols)
    d = psql_csv(
        "SELECT DISTINCT ON (symbol) symbol, close FROM bhavcopy.cleaned_ohlcv "
        f"WHERE symbol IN ({inlist}) AND close > 0 "
        "ORDER BY symbol, trade_date DESC")
    return d.set_index(d.symbol.str.upper()).close.astype(float)


def simulate(px: pd.Series, weights: pd.Series, sip: float) -> dict:
    """Buy whole shares closest to `weights` for a budget of `sip`."""
    target_value = weights * sip
    shares = np.floor(target_value / px)                 # can't buy a fraction
    spent = shares * px
    residual = sip - spent.sum()

    # Spend the residual greedily on whatever still fits — what an actual broker
    # order would do, rather than leaving the cash idle by assumption.
    for sym in (target_value - spent).sort_values(ascending=False).index:
        if residual >= px[sym]:
            n = int(residual // px[sym])
            shares[sym] += n
            residual -= n * px[sym]
    spent = shares * px
    held = spent / spent.sum() if spent.sum() > 0 else spent

    active = (shares > 0).sum()
    # Tracking error here is the weight gap you are stuck with from day one,
    # before any market movement — a floor on how well this can track.
    te = float(np.sqrt(((held - weights) ** 2).sum()))
    return {"sip": sip, "names_held": int(active), "names_intended": len(weights),
            "coverage_%": active / len(weights) * 100,
            "residual_rs": float(residual), "residual_%": residual / sip * 100,
            "tracking_err": te,
            "max_weight_gap_%": float((held - weights).abs().max() * 100)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--index", default="Nifty Alpha 50")
    p.add_argument("--sip", type=float, nargs="*",
                   default=[1000, 5000, 10000, 25000, 50000, 100000, 500000])
    a = p.parse_args()

    syms = constituents(a.index)
    if not syms:
        print(f"no constituents for {a.index!r}"); return 1
    px = prices(syms).dropna()
    missing = set(syms) - set(px.index)
    # Equal weight: the honest default when we do not hold NSE's actual weights
    # (factsheets publish only the top 10). Stated rather than implied.
    w = pd.Series(1 / len(px), index=px.index)

    print(f"# Implementability — {a.index}\n")
    print(f"{len(px)} of {len(syms)} constituents priced"
          + (f" ({len(missing)} unpriced: {sorted(missing)[:5]})" if missing else ""))
    print(f"Equal-weighted. Price range Rs {px.min():,.2f} – Rs {px.max():,.2f} "
          f"(median Rs {px.median():,.2f})")
    print(f"Most expensive: {px.idxmax()} at Rs {px.max():,.0f}\n")

    # The floor below which the portfolio simply cannot be held in full.
    min_full = px.sum()
    print(f"🔴 Minimum to hold ONE share of every name: Rs {min_full:,.0f}")
    print(f"   At equal weight the binding constraint is the priciest name: a SIP")
    print(f"   below Rs {px.max() * len(px):,.0f} cannot give {px.idxmax()} its full weight.\n")

    rows = [simulate(px, w, s) for s in a.sip]
    t = pd.DataFrame(rows)
    print(t.to_string(index=False, float_format=lambda x: f"{x:12,.2f}"))

    ok = t[t["coverage_%"] >= 99]
    print()
    if len(ok):
        print(f"✅ Full coverage from Rs {ok.sip.min():,.0f}/month.")
    else:
        print(f"🔴 No tested SIP holds every name. Largest tested "
              f"Rs {t.sip.max():,.0f} reaches {t['coverage_%'].max():.0f}% of names.")
    small = t.iloc[0]
    print(f"At Rs {small.sip:,.0f} the investor holds {small.names_held} of "
          f"{small.names_intended} names, leaves Rs {small.residual_rs:,.0f} "
          f"({small['residual_%']:.1f}%) undeployed, and starts with a tracking "
          f"error of {small.tracking_err:.3f} before the market moves at all.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
