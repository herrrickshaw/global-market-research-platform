#!/usr/bin/env python3
"""
sector_rotation.py — rotate across NIFTY sectoral indices, tested honestly.

DATA. `indices.nse_daily` carries 14 sectoral indices with the full 10-year
daily history AND their P/E, P/B and dividend yield — collected today. The
valuation leg is the genuinely new capability: nothing else in this warehouse
has sector-level P/E history, so "is Pharma expensive versus its own past" was
previously unanswerable.

🔴 THE FACTSHEET SECTOR WEIGHTS CANNOT DRIVE THIS. They are a SINGLE SNAPSHOT
(2026-06-30) — niftyindices publishes only the current month and keeps no dated
archive, established while collecting them. Backtesting a rotation on one
snapshot of weights would be pure look-ahead. The weights are useful for
IMPLEMENTATION (mapping a chosen sector to the stocks that constitute it), not
as a signal. The signals here come from the sectoral index HISTORY instead.

SIGNALS, each point-in-time and each tested ALONE before any combination:
  mom      trailing 12-1 total return (skip the last month — short-term
           reversal is a documented opposite effect)
  value    P/E z-score against the sector's OWN trailing history, sign-flipped
           so cheap ranks high. Cross-sector P/E levels are not comparable
           (Media averages 187, Energy 14), so the z-score is WITHIN sector.
  trend    index above its own 200-day mean

PROTOCOL, all of it earned by failures earlier today:
  * benchmark is Nifty 500 with dividends accrued from the archive's own
    div_yield — validated against the official TRI as within 0.17pp
  * every return index-relative: a rising market must not make a sector look good
  * walk-forward, monthly formation, no parameter fitted on the sample
  * costs charged per rebalance
  * reported BY SUB-PERIOD — a signal that lives in one regime is not a signal
  * each signal reported separately, so a combination cannot hide a dead leg

Usage:
  python3 sector_rotation.py
  python3 sector_rotation.py --hold 63 --top 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT_MD = HERE / "reports" / "sector_rotation.md"
DSN = "dbname=market_data host=/tmp user=umashankar"

# Deliberately EXCLUDES Nifty Financial Services and Nifty PSU Bank: both
# overlap Nifty Bank heavily, and three correlated financials in a 14-name
# universe would let one sector occupy most of a top-3 book.
SECTORS = ["Nifty Auto", "Nifty Bank", "Nifty Commodities", "Nifty Energy",
           "Nifty FMCG", "Nifty IT", "Nifty Infrastructure", "Nifty Media",
           "Nifty Metal", "Nifty Pharma", "Nifty Realty",
           "Nifty Services Sector"]
BENCH = "Nifty 500"
COST_BPS = 20.0          # index-level exposure (ETF/futures), not single stocks


def load():
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")
    d = con.execute("""SELECT index_name, index_date, close, pe, div_yield
                       FROM pg.indices.nse_daily""").df()
    d["index_date"] = pd.to_datetime(d.index_date)
    px = d.pivot_table(index="index_date", columns="index_name", values="close").sort_index()
    pe = d.pivot_table(index="index_date", columns="index_name", values="pe").sort_index()
    dy = d.pivot_table(index="index_date", columns="index_name", values="div_yield").sort_index()
    # total return = price return + accrued yield (validated within 0.17pp of TRI)
    tr = px.pct_change(fill_method=None).add(dy.ffill().fillna(0) / 100 / 252, fill_value=0)
    return px, pe, tr


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hold", type=int, default=63)
    ap.add_argument("--top", type=int, default=3)
    a = ap.parse_args()

    px, pe, tr = load()
    cols = [c for c in SECTORS if c in px.columns]
    print(f"{len(cols)} sectors · {px.index.min().date()} → {px.index.max().date()}",
          flush=True)
    bench_tr = tr[BENCH]

    rows = []
    for i in range(504, len(px) - a.hold, 21):
        hist_px = px[cols].iloc[:i]
        hist_pe = pe[cols].iloc[:i]
        # ── signals, strictly trailing ──────────────────────────────────────
        mom = (hist_px.iloc[-1] / hist_px.iloc[-252] - 1) - \
              (hist_px.iloc[-1] / hist_px.iloc[-21] - 1)
        pe_now = hist_pe.iloc[-1]
        pe_hist = hist_pe.iloc[-504:]
        value = -((pe_now - pe_hist.mean()) / pe_hist.std())      # cheap = high
        trend = (hist_px.iloc[-1] > hist_px.iloc[-200:].mean()).astype(float)
        # forward, index-relative
        fwd = ((1 + tr[cols].iloc[i:i + a.hold]).prod() - 1) - \
              ((1 + bench_tr.iloc[i:i + a.hold]).prod() - 1)
        rec = {"date": px.index[i], "eq": fwd.mean()}
        for nm, sig in (("mom", mom), ("value", value), ("trend", trend),
                        ("mom+value", mom.rank() + value.rank())):
            s = sig.dropna()
            if len(s) < a.top + 2:
                continue
            pick = s.nlargest(a.top).index
            rec[nm] = fwd.reindex(pick).mean() - COST_BPS / 10_000
        rows.append(rec)

    d = pd.DataFrame(rows).dropna(subset=["eq"])
    L = []
    def out(s=""):
        print(s); L.append(s)

    out(f"# Sector rotation — {len(cols)} NIFTY sectoral indices, "
        f"{a.hold}-bar hold, top {a.top}")
    out()
    out(f"- {len(d)} monthly formations, {d.date.min().date()} → {d.date.max().date()}")
    out(f"- returns are EXCESS over {BENCH} total return · {COST_BPS:.0f}bp charged")
    out(f"- `eq` = hold all {len(cols)} sectors equally (the null: rotation adds nothing)")
    out()
    out("| signal | mean excess | median | win% | t | vs equal-weight |")
    out("|---|--:|--:|--:|--:|--:|")
    for nm in ("eq", "mom", "value", "trend", "mom+value"):
        if nm not in d:
            continue
        v = d[nm].dropna()
        t = v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))
        vs = "" if nm == "eq" else f"{(v.mean() - d['eq'].mean()) * 100:+.2f}pp"
        out(f"| {'**' + nm + '**' if nm != 'eq' else nm} | {v.mean():+.2%} | "
            f"{v.median():+.2%} | {(v > 0).mean():.0%} | {t:.2f} | {vs} |")
    out()
    out("## by sub-period")
    out()
    out("| period | " + " | ".join(k for k in ("eq", "mom", "value", "trend", "mom+value")
                                   if k in d) + " |")
    out("|---" * (1 + sum(k in d for k in ("eq", "mom", "value", "trend", "mom+value"))) + "|")
    for lbl, lo, hi in (("2018-2020", "2018-01-01", "2020-10-31"),
                        ("2020-2023", "2020-11-01", "2023-12-31"),
                        ("2024-2026", "2024-01-01", "2026-12-31")):
        g = d[(d.date >= lo) & (d.date <= hi)]
        if len(g) < 6:
            continue
        cells = " | ".join(f"{g[k].mean():+.2%}" for k in
                           ("eq", "mom", "value", "trend", "mom+value") if k in d)
        out(f"| {lbl} (n={len(g)}) | {cells} |")
    out()
    out("> A signal must beat `eq` — holding every sector equally — not merely be "
        "positive. Beating zero only says sectors outran the benchmark on "
        "average, which is a property of the universe, not of the rotation.")
    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"\nwrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
