#!/usr/bin/env python3
"""
reentry_book.py — test the RE-ENTRY thesis: buy at the anomaly trigger.

CONTEXT. fund_scorecard.py settled the other book: "buy every evicted name at
eviction" compounds at 4.84% at fee parity against Indian fund category medians
of 15.9–23.8% and passive Nifty-50 at 16.53% — last or next-to-last in all ten
rankable categories, with its entire lifetime gain coming from 2021 and −3.3%
over the 4.9 years since. That verdict did NOT touch the re-entry thesis,
because backtest_tier_anomalies.py stopped measuring at the anomaly touch and
re-entry returns begin exactly there. The extension added
reentry_ret_{21,63,126} / bench_ret_* / reentry_excess_*; this reads them.

TWO QUESTIONS, DELIBERATELY SEPARATE:
  1. IS THERE AN EDGE?  Excess return vs the equal-weight index of the same
     universe over the same window, paired per event. This is the honest test:
     raw forward return after a rebound in a bull market says almost nothing.
  2. WOULD IT BEAT FUNDS?  Emit the trades in fund_scorecard.py's schema
     (entry date, holding days, total return) and rank the resulting book
     against real Direct/Growth peers, with costs and fee parity.

OVERLAP. backtest_tier_anomalies.py deliberately did NOT extend its re-eviction
block to cover the re-entry horizon — doing so would have changed the eviction
stream and invalidated the already-computed scorecard. So the same symbol can
produce re-entry windows that overlap. A book cannot hold the same name twice
over the same days, so overlaps are dropped here, keeping the FIRST (the one a
live engine would actually have taken). The count dropped is reported, never
silent.

Usage:
  python3 reentry_book.py                       # IN, 63d
  python3 reentry_book.py --horizon 21 --market US
  python3 reentry_book.py --emit reentry_events.csv    # then feed to fund_scorecard
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
EVENTS = HERE / "reports" / "tier_anomaly_events.csv"
OUT_MD = HERE / "reports" / "reentry_book.md"


def dedupe_overlaps(df: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, int]:
    """Keep the first of any overlapping re-entry windows in the same symbol."""
    keep, dropped = [], 0
    for (_, _), g in df.groupby(["market", "symbol"], sort=False):
        open_until = pd.Timestamp.min
        for r in g.sort_values("trigger_date").itertuples():
            t = pd.Timestamp(r.trigger_date)
            if t < open_until:
                dropped += 1
                continue
            keep.append(r.Index)
            open_until = t + pd.Timedelta(days=horizon)
    return df.loc[keep], dropped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default="IN")
    ap.add_argument("--horizon", type=int, default=63, choices=(21, 63, 126))
    ap.add_argument("--events", default=str(EVENTS))
    ap.add_argument("--emit", help="write trades in fund_scorecard.py schema")
    a = ap.parse_args()

    ev = pd.read_csv(a.events)
    col, xcol, bcol = (f"reentry_ret_{a.horizon}", f"reentry_excess_{a.horizon}",
                       f"bench_ret_{a.horizon}")
    if col not in ev.columns:
        print(f"{col} missing — re-run backtest_tier_anomalies.py "
              "(the extension adds the re-entry columns)")
        return 1

    an = ev[(ev.market == a.market) & (ev.outcome == "ANOMALY")].copy()
    total_anom = len(an)
    an = an.dropna(subset=[col, xcol, "trigger_date"])
    censored = total_anom - len(an)
    if an.empty:
        print(f"no uncensored {a.horizon}d re-entry events for {a.market}")
        return 1
    an["trigger_date"] = pd.to_datetime(an.trigger_date)
    an, dropped = dedupe_overlaps(an, a.horizon)

    L = []
    def out(s=""):
        print(s); L.append(s)

    x, raw, bench = an[xcol], an[col], an[bcol]
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    out(f"# Re-entry book — {a.market}, buy at anomaly trigger, hold {a.horizon}d")
    out()
    out(f"- events        : **{len(an)}** "
        f"(of {total_anom} anomalies · {censored} right-censored · "
        f"{dropped} overlapping dropped)")
    out(f"- window        : {an.trigger_date.min().date()} → "
        f"{an.trigger_date.max().date()}")
    out()
    out("## 1. Is there an edge? (excess vs equal-weight index, same window)")
    out()
    out(f"| | median | mean |")
    out(f"|---|--:|--:|")
    out(f"| re-entry raw | {raw.median():+.2f}% | {raw.mean():+.2f}% |")
    out(f"| benchmark | {bench.median():+.2f}% | {bench.mean():+.2f}% |")
    out(f"| **excess** | **{x.median():+.2f}%** | **{x.mean():+.2f}%** |")
    out()
    out(f"- win rate (excess > 0): **{(x > 0).mean():.0%}**")
    out(f"- paired t on excess   : **t = {t:.2f}** (n={len(x)})")
    verdict = ("EDGE" if abs(t) > 2 and x.mean() > 0 else
               "NO EDGE" if abs(t) <= 2 else "NEGATIVE EDGE")
    out(f"- verdict              : **{verdict}**")
    out()

    # by year — an edge concentrated in one regime is not an edge
    an["year"] = an.trigger_date.dt.year
    out("## 2. By year (a single-regime edge is not an edge)")
    out()
    out("| Year | n | excess median | excess mean | win% |")
    out("|---|--:|--:|--:|--:|")
    for y, g in an.groupby("year"):
        gx = g[xcol]
        out(f"| {y} | {len(g)} | {gx.median():+.2f}% | {gx.mean():+.2f}% | "
            f"{(gx > 0).mean() * 100:.0f}% |")
    out()

    if a.emit:
        # fund_scorecard.py schema: entry date, holding days, total return.
        book = pd.DataFrame({
            "market": an.market, "symbol": an.symbol,
            "evict_date": an.trigger_date.dt.date,   # ENTRY = the trigger
            "rsi_at_evict": an.get("rsi_at_trigger"),
            "drift_at_evict": 0.0, "outcome": "REENTRY",
            "days": a.horizon, "exit_ret_pct": an[col],
        })
        book.to_csv(a.emit, index=False)
        out(f"> wrote {len(book)} trades → `{a.emit}` "
            f"(feed to `fund_scorecard.py --events {a.emit}`)")

    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"\nwrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
