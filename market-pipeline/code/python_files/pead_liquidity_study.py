#!/usr/bin/env python3
"""
pead_liquidity_study.py — PEAD x illiquidity, India, 3-month horizon, FULL panel.

WHY THIS PAIR AT THIS HORIZON. The cost wall decides the horizon: rebalancing
weekly turns the book ~52x/yr, which at India's ~50bp round trip is 26%/yr of
drag before any alpha — no documented equity anomaly is that large. At 3 months
the drag is ~2%. And BazaarTalks/RESEARCH_PAPER_DETAILED.md already validated
exactly two signals in that neighbourhood: post-earnings-announcement drift
(information coefficient 0.010 -> 0.102 once events are dated with REAL filing
dates, and concentrated in less-efficient/emerging markets — Brazil +0.24, US
~0) and the Amihud liquidity premium (+4.24%/quarter, t=2.16, over ten years).
India is the favourable market for both.

FULL DATASET, not the earlier subset (user, 2026-07-28). The prior work ran on
`pit_quarterly.parquet` — 9,456 parsed filings. This uses `results_index.parquet`:
**152,879 filings, 2,797 symbols, 2015-10 -> 2026-07**, the entire NSE results
index.

  That is possible because the signal here needs NO earnings estimate. Sorting
  on SUE would require parsed EPS (only 9,456 available) and an expectation
  model. The classic SUE-FREE formulation sorts on the market's OWN reaction —
  the announcement-window abnormal return — and asks whether the drift
  continues in that direction. It needs filing dates and prices, both of which
  exist for the whole panel. The cost is that it measures drift-after-reaction
  rather than drift-after-surprise; those are the same phenomenon in the PEAD
  literature and the SUE-free version is the more conservative of the two.

NO LOOK-AHEAD, by construction:
  * day 0 = first trading day ON OR AFTER the filing timestamp, so a filing at
    21:29 (they happen) can never inform a same-day price.
  * signal  = abnormal return over [day 0, day +1], index-relative.
  * forward = 63 trading days starting day +2. The signal window and the
    measurement window do not overlap by even one bar.
  * illiquidity is computed on the 60 bars BEFORE day 0 only.

MEASUREMENT DEFENCES, each one earned by a failure found today:
  * prices are SPLIT-ADJUSTED (india_split_adjust). The raw panel carries 71
    fake ~-90% days in the top-200 alone.
  * symbols whose residual discontinuity is still unexplained (bonus issues,
    demergers — MINDTREE 2016, BAJAJFINSV 2022, BAJFINANCE 2025, VEDL, PEL) are
    EXCLUDED, not silently included. A fake -50% inside a forward window would
    read as a spectacular PEAD reversal.
  * every return is INDEX-RELATIVE (Nifty-50 total return), because a rising
    market makes every quantile look profitable.
  * results are reported BY YEAR. A signal that lives in one regime is not a
    signal — today's tier book was +40.9% in 2021 and negative in every other.

Usage:
  python3 pead_liquidity_study.py
  python3 pead_liquidity_study.py --horizon 63 --quantiles 5
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

XBRL = Path("/Users/umashankar/market-pipeline/market_cache/nse_xbrl/results_index.parquet")
OUT_MD = HERE / "reports" / "pead_liquidity_study.md"

SIG_WIN = 1          # announcement window = [0, +1]
GAP = 2              # forward return starts here — no overlap with the signal
ILLIQ_WIN = 60       # trailing bars for Amihud
MIN_PRICE = 5.0      # sub-Rs5 names are quoted in ticks; their returns are noise
RESID_DROP = 0.30    # unexplained discontinuity => symbol excluded


def load_prices():
    """Split-adjusted India panel. REFUSES to run unadjusted.

    The factor table lives under market-pipeline/data/, which is gitignored, so
    a fresh checkout will not have it. Falling back to raw prices would run the
    whole study on a panel carrying 71 fake ~-90% days in the top-200 alone and
    report the result as if it were adjusted — the silent-degradation failure
    mode that cost 4.9 points on the tier book. Rebuild is one command.
    """
    from india_split_adjust import load_raw, adjust, OUT as FAC
    if not FAC.exists():
        raise SystemExit(
            f"MISSING {FAC}\n"
            "The India panel is split-UNADJUSTED without it and every number "
            "below would be wrong.\n"
            "Rebuild (needs yfinance — the venv python, not the login default):\n"
            "  /Users/umashankar/market-pipeline/code/python_files/.venv/bin/"
            "python3 scripts/india_split_adjust.py --build"
        )
    fac = pd.read_parquet(FAC)
    raw = load_raw()
    px = raw.pivot_table(index="Date", columns="Symbol", values="Close").sort_index()
    tv = (raw.assign(_t=raw.Close * raw.Volume)
             .pivot_table(index="Date", columns="Symbol", values="_t").sort_index())
    px = adjust(px, fac)
    return px, tv


def contaminated(px: pd.DataFrame) -> set[str]:
    """Symbols still showing an unexplained one-day collapse after split
    adjustment — bonuses and demergers this pipeline cannot yet correct."""
    r = px.pct_change(fill_method=None)
    bad = ((r < -RESID_DROP) & (r.shift(-1) < 0.20)).any()
    return set(bad[bad].index)


def load_events() -> pd.DataFrame:
    d = pd.read_parquet(XBRL, columns=["symbol", "filingDate", "relatingTo",
                                       "financialYear", "period"])
    d["filing_ts"] = pd.to_datetime(d.filingDate, format="mixed", errors="coerce")
    d = d.dropna(subset=["symbol", "filing_ts"])
    # One event per (symbol, reporting period): the index carries several rows
    # per filing (consolidated / standalone / cumulative restatements). The
    # EARLIEST timestamp is when the market actually learned it.
    d = (d.sort_values("filing_ts")
           .groupby(["symbol", "financialYear", "relatingTo"], as_index=False)
           .first())
    return d[["symbol", "filing_ts"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horizon", type=int, default=63)
    ap.add_argument("--quantiles", type=int, default=5)
    a = ap.parse_args()

    print("loading split-adjusted India panel …", flush=True)
    px, tv = load_prices()
    bad = contaminated(px)
    print(f"  {px.shape[1]:,} symbols x {len(px):,} bars · "
          f"{len(bad)} excluded for unexplained discontinuity", flush=True)

    ev = load_events()
    print(f"  {len(ev):,} de-duplicated filing events "
          f"({ev.symbol.nunique():,} symbols, "
          f"{ev.filing_ts.min().date()} -> {ev.filing_ts.max().date()})", flush=True)

    rets = px.pct_change(fill_method=None)
    # Index proxy: equal-weight of the panel is NOT the index (it is a small/mid
    # basket that returned 23.9% vs Nifty's 16.9%). Use the real benchmark.
    from trading_reward import benchmark_series
    bench = benchmark_series("IN").reindex(px.index).fillna(0.0)

    # Amihud illiquidity: |return| per unit of rupee turnover, trailing.
    illiq_all = (rets.abs() / tv.replace(0, np.nan)).rolling(ILLIQ_WIN).mean()

    dates = px.index
    rows = []
    skipped = 0
    for e in ev.itertuples():
        sym = e.symbol
        if sym not in px.columns or sym in bad:
            skipped += 1
            continue
        # day 0 = first bar strictly at/after the filing timestamp
        i = dates.searchsorted(e.filing_ts.normalize(), side="left")
        if i < ILLIQ_WIN or i + GAP + a.horizon >= len(dates):
            skipped += 1
            continue
        s = px[sym]
        p0 = s.iloc[i]
        if not np.isfinite(p0) or p0 < MIN_PRICE:
            skipped += 1
            continue
        # announcement abnormal return, index-relative
        car_end = min(i + SIG_WIN, len(dates) - 1)
        r_sig = s.iloc[car_end] / s.iloc[i - 1] - 1
        b_sig = (1 + bench.iloc[i:car_end + 1]).prod() - 1
        # forward, starting AFTER a full gap bar
        j0, j1 = i + GAP, i + GAP + a.horizon
        r_fwd = s.iloc[j1] / s.iloc[j0] - 1
        b_fwd = (1 + bench.iloc[j0 + 1:j1 + 1]).prod() - 1
        if not np.isfinite(r_sig) or not np.isfinite(r_fwd):
            skipped += 1
            continue
        rows.append({
            "symbol": sym, "date": dates[i], "year": dates[i].year,
            "car": r_sig - b_sig,
            "fwd_excess": r_fwd - b_fwd,
            "illiq": illiq_all[sym].iloc[i - 1],
            "turnover": tv[sym].iloc[i - ILLIQ_WIN:i].median(),
        })
    d = pd.DataFrame(rows).dropna(subset=["car", "fwd_excess"])
    print(f"  usable events: {len(d):,}  (skipped {skipped:,})", flush=True)

    L = []
    def out(s=""):
        print(s); L.append(s)

    out(f"# PEAD x illiquidity — India, {a.horizon}-bar forward, FULL panel")
    out()
    out(f"- events        : **{len(d):,}** across {d.symbol.nunique():,} symbols, "
        f"{d.year.min()}–{d.year.max()}")
    out(f"- signal        : announcement abnormal return [0,+{SIG_WIN}], "
        f"index-relative")
    out(f"- forward       : {a.horizon} bars from day +{GAP}, index-relative "
        f"(no overlap with the signal window)")
    out(f"- excluded      : {len(bad)} symbols with unexplained discontinuities")
    out()

    # ── 1. PEAD: does the drift continue in the direction of the reaction? ──
    d["q"] = pd.qcut(d.car, a.quantiles, labels=False, duplicates="drop")
    out(f"## 1. PEAD — forward excess by announcement-reaction quantile")
    out()
    out("| quantile | n | mean CAR | mean fwd excess | median | win% |")
    out("|---|--:|--:|--:|--:|--:|")
    for q, g in d.groupby("q"):
        out(f"| Q{int(q)+1}{' (worst reaction)' if q == 0 else ' (best reaction)' if q == d.q.max() else ''} "
            f"| {len(g):,} | {g.car.mean():+.2%} | **{g.fwd_excess.mean():+.2%}** | "
            f"{g.fwd_excess.median():+.2%} | {(g.fwd_excess > 0).mean():.0%} |")
    hi = d[d.q == d.q.max()].fwd_excess
    lo = d[d.q == 0].fwd_excess
    spread = hi.mean() - lo.mean()
    se = np.sqrt(hi.var(ddof=1) / len(hi) + lo.var(ddof=1) / len(lo))
    t = spread / se if se else np.nan
    ic = d.car.corr(d.fwd_excess, method="spearman")
    ic_t = ic * np.sqrt((len(d) - 2) / max(1e-9, 1 - ic ** 2))
    out()
    out(f"- **top-minus-bottom spread: {spread:+.2%}  (t = {t:.2f})**")
    out(f"- rank IC (Spearman): **{ic:+.4f}**  (t = {ic_t:.2f})")
    out(f"- verdict: **{'PEAD PRESENT' if abs(t) > 2 and spread > 0 else 'NO PEAD'}**")
    out()

    # ── 2. conditional on illiquidity (the paper's mechanism) ──────────────
    d2 = d.dropna(subset=["illiq"]).copy()
    if len(d2) > 100:
        d2["lq"] = pd.qcut(d2.illiq.rank(method="first"), 3, labels=["liquid", "mid", "illiquid"])
        out("## 2. PEAD conditional on Amihud illiquidity")
        out()
        out("| liquidity tier | n | top-minus-bottom | t | rank IC |")
        out("|---|--:|--:|--:|--:|")
        for tier, g in d2.groupby("lq", observed=True):
            g = g.copy()
            g["q"] = pd.qcut(g.car, a.quantiles, labels=False, duplicates="drop")
            h, l = g[g.q == g.q.max()].fwd_excess, g[g.q == 0].fwd_excess
            if len(h) < 30 or len(l) < 30:
                continue
            sp = h.mean() - l.mean()
            s_e = np.sqrt(h.var(ddof=1) / len(h) + l.var(ddof=1) / len(l))
            tt = sp / s_e if s_e else np.nan
            i_c = g.car.corr(g.fwd_excess, method="spearman")
            out(f"| {tier} | {len(g):,} | {sp:+.2%} | {tt:.2f} | {i_c:+.4f} |")
        out()

    # ── 3. by year — a one-regime signal is not a signal ────────────────────
    out("## 3. By year (regime robustness)")
    out()
    out("| year | n | top-minus-bottom | rank IC |")
    out("|---|--:|--:|--:|")
    for y, g in d.groupby("year"):
        if len(g) < 200:
            continue
        g = g.copy()
        g["q"] = pd.qcut(g.car, a.quantiles, labels=False, duplicates="drop")
        h, l = g[g.q == g.q.max()].fwd_excess, g[g.q == 0].fwd_excess
        if len(h) < 20 or len(l) < 20:
            continue
        out(f"| {y} | {len(g):,} | {h.mean() - l.mean():+.2%} | "
            f"{g.car.corr(g.fwd_excess, method='spearman'):+.4f} |")
    out()
    out("> Every return is index-relative (Nifty-50 total return), so a rising "
        "market cannot make a quantile look profitable. Signal and forward "
        "windows never overlap. Prices are split-adjusted; symbols with "
        "unexplained residual discontinuities are excluded.")

    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"\nwrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
