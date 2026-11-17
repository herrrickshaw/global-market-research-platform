#!/usr/bin/env python3
"""
pead_portfolio.py — turn the PEAD Q5 signal into a tradeable book.

The study (pead_liquidity_study.py) established the signal: forward 63-bar
index-relative excess by announcement-reaction quintile is flat across Q1-Q3
(+0.55/+0.59/+0.54) and lives entirely in Q5 (+2.43%), top-minus-bottom +1.88%
(t 4.93), surviving the removal of the 2020-21 regime (+1.48%, t 3.78).

🔴 THE STUDY'S QUINTILE IS NOT TRADEABLE. It used pd.qcut over the WHOLE sample,
so the Q5 breakpoint depended on the CARs of events that had not happened yet —
look-ahead of exactly the kind that cost 7.5 points in the ETF universe earlier
today. A portfolio has to decide "is this a big reaction?" using only reactions
it has already seen. So the threshold here is the trailing 80th percentile of
announcement CARs over a rolling window, recomputed at every event. That makes
the book strictly implementable and it WILL score lower than the study — the
study's number is an upper bound, not a forecast.

CONSTRUCTION
  * universe   : every NSE results filing, split-adjusted prices, symbols with
                 unexplained residual discontinuities excluded (287 of them).
  * signal     : announcement abnormal return over [day 0, day +1] vs Nifty-50,
                 where day 0 is the first bar at/after the filing timestamp.
  * entry      : day +2 (never overlapping the signal window).
  * hold       : 63 trading days, no early exit — a fixed horizon is the only
                 rule that cannot be tuned after the fact.
  * threshold  : trailing 80th percentile of CAR over TRAIL_DAYS, point-in-time.
  * dedupe     : one open position per symbol; a second filing while a position
                 is live is skipped, not doubled.

OUTPUT is fund_scorecard.py's schema, so the book is scored against real
Direct/Growth fund categories with costs and fee parity, exactly like the tier
and re-entry books were. exit_ret_pct is the RAW forward return — the scorecard
charges costs and compares to fund NAVs itself, so index-adjusting here would
double-count the benchmark.

Usage:
  python3 pead_portfolio.py --emit reports/pead_q5_events.csv
  python3 pead_portfolio.py --pct 90 --trail 504
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, "/Users/umashankar/scripts")

HOLD = 63
GAP = 2
SIG_WIN = 1
MIN_PRICE = 5.0
MIN_TURNOVER = 1e7        # Rs 1cr/day median — the tradeable floor used repo-wide
TRAIL_DAYS = 756          # ~3y of prior events to set the threshold
WARMUP_MIN = 200          # events needed before the threshold is trusted


def regime_ok_series(bench: pd.Series, mode: str, px: pd.DataFrame) -> pd.Series:
    """Point-in-time 'is it safe to be long' flag, per trading day.

    ma200    — index NAV above its own trailing 200-day mean. The plainest
               trend filter there is; nothing in it is fitted, which is the
               point: a filter tuned on this sample would just be the
               look-ahead problem wearing a different hat.
    breadth  — fraction of the panel above its own 200DMA > 50%. Same rule
               backtest_tier_anomalies.py already uses as its market gate.
    Both are shifted one day so the decision uses only bars strictly BEFORE
    the entry date.
    """
    if mode == "none":
        return pd.Series(True, index=bench.index)
    if mode == "ma200":
        nav = (1 + bench).cumprod()
        ok = nav > nav.rolling(200, min_periods=200).mean()
    else:                                   # breadth
        above = px > px.rolling(200, min_periods=200).mean()
        ok = above.mean(axis=1) > 0.50
    return ok.shift(1).fillna(False).reindex(bench.index).fillna(False)


def build(pct: float, trail: int, regime: str = "none") -> pd.DataFrame:
    import pead_liquidity_study as P
    from trading_reward import benchmark_series

    px, tv = P.load_prices()
    bad = P.contaminated(px)
    ev = P.load_events()
    bench = benchmark_series("IN").reindex(px.index).fillna(0.0)
    reg_ok = regime_ok_series(bench, regime, px)
    dates = px.index

    rows = []
    for e in ev.sort_values("filing_ts").itertuples():
        s_ = e.symbol
        if s_ not in px.columns or s_ in bad:
            continue
        i = dates.searchsorted(e.filing_ts.normalize(), side="left")
        if i < 60 or i + GAP + HOLD >= len(dates):
            continue
        s = px[s_]
        p0 = s.iloc[i]
        if not np.isfinite(p0) or p0 < MIN_PRICE:
            continue
        if not np.isfinite(tv[s_].iloc[i - 60:i].median()) or \
           tv[s_].iloc[i - 60:i].median() < MIN_TURNOVER:
            continue
        ce = min(i + SIG_WIN, len(dates) - 1)
        car = (s.iloc[ce] / s.iloc[i - 1] - 1) - ((1 + bench.iloc[i:ce + 1]).prod() - 1)
        j0, j1 = i + GAP, i + GAP + HOLD
        # regime gate evaluated at the ENTRY bar, from bars strictly before it
        if not bool(reg_ok.iloc[j0]):
            continue
        raw = s.iloc[j1] / s.iloc[j0] - 1
        if not np.isfinite(car) or not np.isfinite(raw):
            continue
        rows.append({"symbol": s_, "sig_date": dates[i], "entry_date": dates[j0],
                     "car": car, "raw_ret": raw})

    d = pd.DataFrame(rows).sort_values("sig_date").reset_index(drop=True)
    print(f"  {len(d):,} liquid, priced events with complete forward windows")

    # ── point-in-time threshold: trailing percentile of PRIOR reactions only ──
    thr = np.full(len(d), np.nan)
    car = d.car.values
    sig = d.sig_date.values
    for k in range(len(d)):
        lo = sig[k] - np.timedelta64(trail, "D")
        prior = car[:k][(sig[:k] >= lo)]
        if len(prior) >= WARMUP_MIN:
            thr[k] = np.percentile(prior, pct)
    d["thr"] = thr
    d = d.dropna(subset=["thr"])
    sel = d[d.car >= d.thr].copy()
    print(f"  {len(sel):,} selected above the trailing {pct:.0f}th percentile "
          f"(warm-up dropped {len(rows) - len(d):,})")

    # ── one open position per symbol ────────────────────────────────────────
    keep, open_until = [], {}
    for r in sel.itertuples():
        if open_until.get(r.symbol) is not None and r.entry_date < open_until[r.symbol]:
            continue
        keep.append(r.Index)
        open_until[r.symbol] = r.entry_date + pd.Timedelta(days=HOLD * 1.45)
    out = sel.loc[keep]
    print(f"  {len(out):,} after dropping overlapping positions in the same name")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pct", type=float, default=80.0)
    ap.add_argument("--regime", default="none", choices=("none","ma200","breadth"))
    ap.add_argument("--trail", type=int, default=TRAIL_DAYS)
    ap.add_argument("--emit", default="reports/pead_q5_events.csv")
    a = ap.parse_args()

    print(f"building PEAD book · pct={a.pct:.0f} · regime={a.regime}", flush=True)
    d = build(a.pct, a.trail, a.regime)
    if d.empty:
        print("no events selected")
        return 1

    yr = d.assign(y=d.entry_date.dt.year)
    print(f"\n  window {d.entry_date.min().date()} -> {d.entry_date.max().date()}")
    print(f"  raw 63-bar return: mean {d.raw_ret.mean():+.2%} · "
          f"median {d.raw_ret.median():+.2%} · win {(d.raw_ret > 0).mean():.0%}")
    print("  positions per year: " +
          " ".join(f"{y}:{n}" for y, n in yr.groupby('y').size().items()))

    book = pd.DataFrame({
        "market": "IN", "symbol": d.symbol,
        "evict_date": d.entry_date.dt.date,      # scorecard's entry column
        "rsi_at_evict": np.nan, "drift_at_evict": 0.0,
        "outcome": "PEAD_Q5", "days": HOLD,
        "exit_ret_pct": (d.raw_ret * 100).round(2),
    })
    out = HERE / a.emit
    book.to_csv(out, index=False)
    print(f"\nwrote {len(book):,} trades -> {out}")
    print(f"score with:\n  python3 fund_scorecard.py --events {out} --ter-bps 100")
    return 0


if __name__ == "__main__":
    sys.exit(main())
