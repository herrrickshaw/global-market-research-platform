#!/usr/bin/env python3
"""
band_sip_backtest.py — SIP into a price band, and which band is actually forecastable.

TWO QUESTIONS, ONE ENGINE.

1. DOES MONTHLY AVERAGING RESCUE THE CHEAP BAND? sip_xirr_backtest showed the SIP
   advantage rising with volatility (Smallcap 250 +2.62 pts, Nifty 50 -0.23), and
   price_band_migration showed Rs 0-50 is the most volatile, most right-skewed
   segment on the market — mean 31.8% against a median of 4.9%. If averaging
   monetises dispersion, the cheap band is where it should show up most. If it
   does not survive delisting, that is a finding too.

2. WHICH BAND IS MONETISABLE WITH HIGH PREDICTABILITY? A high mean is worth
   little if the outcome is a coin flip. This scores each band on DISPERSION and
   PERSISTENCE, not on average return: hit rate, IQR, band stickiness, and the
   mean/median ratio (a right-skew detector — the further above 1, the more the
   average is a story about a handful of names nobody reliably picks).

🔴 DELISTING IS MODELLED, NOT DROPPED, AND IT DECIDES THE ANSWER. 31.9% of
Rs 0-50 names are gone within 12 months against 18.2% for Rs 250-1000. Excluding
them — the default if you simply inner-join — hands the cheap band a survivorship
bonus exactly where it is largest. Both bounds are therefore reported:
  * OPTIMISTIC: a vanished holding is sold at its last observed price.
  * REALISTIC : a vanished holding goes to ZERO.
The truth lies between; suspensions often do return something, and delistings
often do not. Quoting only the optimistic bound is how cheap-stock backtests get
published.

🔴 AND THE BASKET IS FORMED FROM THE RAW PRICE, PRICED ON THE ADJUSTED SERIES —
band membership is what the investor sorts on, returns must survive splits.

    python3 band_sip_backtest.py
    python3 band_sip_backtest.py --monthly 5000 --start 2018-01
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

import numpy as np
import pandas as pd

RAW = os.path.expanduser("~/.cache/market-warehouse/ohlcv/IN")
ADJ = os.path.expanduser("~/.cache/market-warehouse/ohlcv_adj/IN")

# Finer than price_band_migration: Rs 250-1000 is split at 500 so the
# Rs 500-1000 slice can be judged on its own rather than averaged with Rs 250-500.
EDGES = [0, 50, 250, 500, 1000, np.inf]
LABELS = ["Rs 0-50", "Rs 50-250", "Rs 250-500", "Rs 500-1000", "Rs 1000+"]


def load(path: str, with_volume: bool = False) -> pd.DataFrame:
    """Month-end observation per symbol, plus that month's median traded value.

    🔴 MEDIAN, NOT MEAN, AND VALUE, NOT SHARES. A single block deal lifts a mean
    turnover far above what the stock trades on a normal day, which is exactly
    the illusion of liquidity a small-cap filter has to survive; the median is
    what an investor meets on an ordinary morning. And rupees rather than share
    count, because 100k shares of a Rs 10 stock is Rs 1m while the same of a
    Rs 1,000 stock is Rs 100m — filtering on share count would systematically
    admit the cheapest, thinnest names, which is the opposite of the intent.
    """
    cols = ["Date", "Symbol", "Close"] + (["Volume"] if with_volume else [])
    fs = sorted(glob.glob(f"{path}/*.parquet"))
    d = pd.concat((pd.read_parquet(f, columns=cols) for f in fs), ignore_index=True)
    d["Date"] = pd.to_datetime(d["Date"])
    d["Symbol"] = d["Symbol"].astype(str).str.upper()
    d["ym"] = d["Date"].values.astype("datetime64[M]")
    d = d.sort_values("Date")
    last = d.groupby(["Symbol", "ym"], as_index=False).last()
    if with_volume:
        d["turnover"] = d["Close"] * d["Volume"].fillna(0)
        med = (d.groupby(["Symbol", "ym"], as_index=False)["turnover"].median()
                 .rename(columns={"turnover": "turnover_med"}))
        last = last.merge(med, on=["Symbol", "ym"], how="left")
    return last


def xirr(years: np.ndarray, amt: np.ndarray, lo=-0.999, hi=10.0) -> float:
    npv = lambda r: float((amt / (1.0 + r) ** years).sum())
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def sip_into_band(panel: pd.DataFrame, band: str, monthly: float,
                  zero_on_exit: bool) -> dict:
    """Each month, split `monthly` equally across every name then in `band`.

    Buy-and-hold to the end: no rebalancing, no selling on band exit. That is
    deliberate — rebalancing would import a momentum/reversal decision the study
    is not testing, and 'I bought cheap stocks monthly and held' is the behaviour
    actually being asked about.
    """
    months = sorted(panel.ym.unique())
    last_ym = months[-1]
    last_px = (panel[panel.ym == last_ym].set_index("Symbol").adj)
    # Last observed adjusted price per symbol, for names that vanish mid-sample.
    final_seen = panel.sort_values("ym").groupby("Symbol").adj.last()

    # 🔴 TIME RUNS FORWARD FROM THE FIRST CASHFLOW, NOT BACKWARD FROM THE END.
    # The first version of this measured each outflow as time REMAINING to the
    # horizon and placed every terminal inflow at t=0, which discounts the
    # instalments while leaving the proceeds undiscounted — exactly inverted. It
    # produced -17% XIRR alongside a 3.2x multiple, and the contradiction between
    # those two numbers is the only reason it was caught. A sign error in the
    # time axis does not raise; it just returns a confident wrong rate.
    end = pd.Timestamp(last_ym)
    t0 = pd.Timestamp(months[0])
    yrs, flows, terminal = [], [], 0.0
    for ym in months[:-1]:
        cur = panel[(panel.ym == ym) & (panel.band == band)]
        if cur.empty:
            continue
        per = monthly / len(cur)
        units = per / cur.set_index("Symbol").adj      # equal rupee per name
        alive = units.index.intersection(last_px.index)
        terminal += float((units.loc[alive] * last_px.loc[alive]).sum())
        gone = units.index.difference(last_px.index)
        if len(gone) and not zero_on_exit:
            terminal += float((units.loc[gone] * final_seen.loc[gone]).sum())
        yrs.append((pd.Timestamp(ym) - t0).days / 365.0)
        flows.append(-monthly)
    if not flows:
        return {}
    # One terminal inflow at the horizon, holding everything bought along the way.
    yrs.append((end - t0).days / 365.0)
    flows.append(terminal)
    y = np.array(yrs); f = np.array(flows)
    invested = -f[f < 0].sum()
    final = f[f > 0].sum()
    return {"invested": invested, "final": final, "multiple": final / invested,
            "xirr_%": xirr(y, f) * 100}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--monthly", type=float, default=5000)
    p.add_argument("--start", default="2016-01")
    p.add_argument("--horizon", type=int, default=12)
    p.add_argument("--min-turnover", type=float, default=1_000_000,
                   help="minimum MEDIAN daily traded value in rupees for a name to be "
                        "bought that month (default Rs 10 lakh/day). 0 disables. A "
                        "Rs 5,000 monthly instalment split across a band is tiny per "
                        "name, so this is not about market impact — it is about "
                        "whether the stock trades at all on an ordinary day.")
    a = p.parse_args()

    raw = load(RAW, with_volume=True).rename(columns={"Close": "raw"})[
        ["Symbol", "ym", "raw", "turnover_med"]]
    adj = load(ADJ).rename(columns={"Close": "adj"})[["Symbol", "ym", "adj"]]
    m = raw.merge(adj, on=["Symbol", "ym"]).query("raw >= 1 and adj > 0")
    m = m[m.ym >= pd.Timestamp(a.start)]
    m["band"] = pd.cut(m.raw, EDGES, labels=LABELS, right=False)

    print(f"# SIP into a price band — Rs {a.monthly:,.0f}/month, "
          f"{m.ym.min():%Y-%m} to {m.ym.max():%Y-%m}\n")

    # 🔴 THE FILTER APPLIES AT PURCHASE TIME ONLY, using that month's own traded
    # value. Screening on turnover measured later — or over the whole sample —
    # would be lookahead: it silently drops the names that went on to become
    # untradeable, which is precisely the risk the filter exists to price.
    if a.min_turnover > 0:
        before = len(m)
        by_band_before = m.groupby("band", observed=True).size()
        m = m[m.turnover_med.fillna(0) >= a.min_turnover]
        by_band_after = m.groupby("band", observed=True).size()
        print(f"## Liquidity filter: median daily turnover >= Rs {a.min_turnover:,.0f}\n")
        print(f"{'band':<14}{'before':>10}{'after':>10}{'kept %':>9}")
        for b in LABELS:
            bb = int(by_band_before.get(b, 0)); aa = int(by_band_after.get(b, 0))
            if bb:
                print(f"{b:<14}{bb:>10,}{aa:>10,}{aa/bb*100:>9.1f}")
        print(f"{'TOTAL':<14}{before:>10,}{len(m):>10,}{len(m)/before*100:>9.1f}\n")
    print("## 1. SIP outcome by band — both survivorship bounds\n")
    print(f"{'band':<14}{'names/mo':>9}{'XIRR opt':>10}{'XIRR real':>11}"
          f"{'mult opt':>10}{'mult real':>10}{'delist drag':>13}")
    rows = []
    for b in LABELS:
        n = m[m.band == b].groupby("ym").size().mean()
        opt = sip_into_band(m, b, a.monthly, zero_on_exit=False)
        real = sip_into_band(m, b, a.monthly, zero_on_exit=True)
        if not opt:
            continue
        drag = opt["xirr_%"] - real["xirr_%"]
        rows.append((b, n, opt["xirr_%"], real["xirr_%"], opt["multiple"],
                     real["multiple"], drag))
        print(f"{b:<14}{n:>9.0f}{opt['xirr_%']:>10.2f}{real['xirr_%']:>11.2f}"
              f"{opt['multiple']:>10.2f}{real['multiple']:>10.2f}{drag:>13.2f}")

    # ── predictability, which is a different question from return ────────────
    fwd = m[["Symbol", "ym", "adj", "band"]].copy()
    fwd["ym"] = fwd["ym"] - pd.DateOffset(months=a.horizon)
    fwd = fwd.rename(columns={"adj": "adj_f", "band": "band_f"})
    j = m.merge(fwd, on=["Symbol", "ym"], how="left")
    s = j.dropna(subset=["adj_f"]).copy()
    s["ret"] = (s.adj_f / s.adj - 1) * 100

    print(f"\n## 2. Predictability by band ({a.horizon}M forward, survivors only)\n")
    print(f"{'band':<14}{'n':>8}{'hit%':>7}{'median':>8}{'mean':>8}"
          f"{'mean/med':>10}{'IQR':>8}{'sticky%':>9}{'gone%':>7}")
    for b in LABELS:
        g = s[s.band == b]
        if len(g) < 500:
            continue
        med, mean = g.ret.median(), g.ret.mean()
        iqr = g.ret.quantile(.75) - g.ret.quantile(.25)
        sticky = (g.band_f.astype(str) == b).mean() * 100
        gone = 1 - j[j.band == b].adj_f.notna().mean()
        print(f"{b:<14}{len(g):>8,}{(g.ret > 0).mean()*100:>7.1f}{med:>8.1f}{mean:>8.1f}"
              f"{mean/med if med else np.nan:>10.2f}{iqr:>8.1f}{sticky:>9.1f}{gone*100:>7.1f}")

    print("\nmean/med near 1 = symmetric and forecastable; far above 1 = the average is")
    print("carried by a few names, and the typical holder does not get it. IQR is the")
    print("width of the middle half of outcomes — narrower is more predictable.")

    # ── return per unit of dispersion: the band-level answer ─────────────────
    # A SIP return is only usable if it is repeatable, so score each band on
    # XIRR-under-the-REALISTIC-delisting-assumption divided by the width of its
    # outcome distribution. This is deliberately the pessimistic XIRR: using the
    # optimistic one would reward precisely the bands whose names disappear.
    print("\n## 3. Return per unit of dispersion — realistic XIRR / IQR\n")
    disp = {b: (s[s.band == b].ret.quantile(.75) - s[s.band == b].ret.quantile(.25))
            for b in LABELS if len(s[s.band == b]) >= 500}
    scored = []
    for b, _n, _xo, xr, _mo, _mr, _d in rows:
        if b in disp and disp[b]:
            scored.append((b, xr, disp[b], xr / disp[b]))
    scored.sort(key=lambda x: -x[3])
    print(f"{'band':<14}{'XIRR real':>11}{'IQR':>8}{'ratio':>9}")
    for b, xr, iq, ratio in scored:
        print(f"{b:<14}{xr:>11.2f}{iq:>8.1f}{ratio:>9.3f}")
    best, worst = scored[0], scored[-1]
    gone_pct = {b: (1 - j[j.band == b].adj_f.notna().mean()) * 100 for b in LABELS
                if len(j[j.band == b])}
    print(f"\n🔴 {best[0]} carries the best return-per-dispersion ({best[3]:.3f}), "
          f"{worst[0]} the worst ({worst[3]:.3f}).")
    print(f"   {best[0]}: {gone_pct.get(best[0], float('nan')):.1f}% of holdings vanish "
          f"within {a.horizon}M, against {gone_pct.get(worst[0], float('nan')):.1f}% "
          f"for {worst[0]}.")
    if a.min_turnover > 0:
        print(f"\n   Filtered at Rs {a.min_turnover:,.0f}/day median turnover. Compare")
        print("   against --min-turnover 0: a band whose ranking collapses once its")
        print("   names must actually trade was never harvesting a return, it was")
        print("   harvesting the absence of a price.")

    # ── lot size / segment: what could NOT be verified ───────────────────────
    #
    # 🔴 LOT SIZE IS 1 ON THE MAIN BOARD, BUT THAT IS NOT THE WHOLE UNIVERSE.
    # NSE cash equity trades in single shares — of 2,775 EQ symbols in the
    # bhavcopy only ONE ever carried NewBrdLotQty > 1 — so whole-share rounding
    # (fund_implementability.py) is the binding constraint there, not lots.
    #
    # The SME segment is different: NSE Emerge and BSE SME trade in LOTS, often
    # Rs 1 lakh or more per lot, which makes a Rs 5,000 monthly instalment
    # impossible regardless of price. And this panel cannot tell us which names
    # those are: it holds 6,703 symbols against the bhavcopy's 2,775 EQ names, so
    # the series of the remainder is simply unknown from data on hand.
    #
    # That gap is not evenly spread, and it falls exactly where it hurts: only
    # ~32% of Rs 0-50 names could be confirmed as main-board EQ, against ~41%
    # of the panel overall. So the cheap band's result rests disproportionately
    # on names that may be SME-listed, BSE-only, or since suspended — i.e. on
    # names a retail SIP might not be able to buy in the first place.
    try:
        eq = set(subprocess.run(
            ["psql", "-d", "market_data", "-tAq", "-c",
             'select distinct "TckrSymb" from bhavcopy.nse_raw'],
            capture_output=True, text=True, timeout=120).stdout.split())
        if eq:
            print("\n## 4. Segment verification — can these even be bought in "
                  "single shares?\n")
            print(f"{'band':<14}{'symbols':>9}{'confirmed EQ':>14}{'unverified':>12}")
            for b in LABELS:
                syms = set(m[m.band == b].Symbol.unique())
                if not syms:
                    continue
                ok = len(syms & eq)
                print(f"{b:<14}{len(syms):>9,}{ok:>14,}{len(syms)-ok:>12,}")
            print("\n   'Unverified' is NOT 'bad' — most are BSE-only listings that")
            print("   trade in single shares too. But SME lots (Rs 1 lakh+) live in")
            print("   this group, and a Rs 5,000 instalment cannot buy one. The cheap")
            print("   band carries the largest unverified share, so its result is the")
            print("   least safe to act on.")
    except Exception as exc:                                       # noqa: BLE001
        print(f"\n   (segment check skipped: {type(exc).__name__})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
