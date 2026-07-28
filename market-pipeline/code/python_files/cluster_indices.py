#!/usr/bin/env python3
"""
cluster_indices.py — do stocks flock? Testing NSE's sector taxonomy against the data.

THE HYPOTHESIS. "Birds of a feather flock together": stocks that co-move form
natural groups. Index providers assert those groups a priori via an industry
taxonomy (NSE publishes an `Industry` label per constituent) and build sectoral
indices on it. If co-movement is real but the OFFICIAL taxonomy captures it
poorly, then the published sectoral indices are mis-specified and better baskets
exist — which is a concrete, testable claim, and a defensible thing to put in
front of an index provider.

THE TEST, and why it is falsifiable. At each formation date, group the liquid
universe three ways using ONLY trailing data, then measure how tightly each
grouping holds together in the FORWARD window it never saw:

    DATA     hierarchical clustering on 1 − correlation of trailing returns
    OFFICIAL NSE's own `Industry` label from the constituent lists
    RANDOM   groups of identical sizes, shuffled — the null

Metric is mean within-group pairwise forward correlation. RANDOM sets the floor
(≈ the market's average pairwise correlation, since any random basket inherits
market beta). A grouping is only informative to the extent it beats RANDOM, and
NSE's taxonomy is only worth its status if it beats — or at least matches —
what falls out of the data with no domain knowledge at all.

🔴 GROUP COUNT IS A CONFOUND — the first run got this wrong. At k=15 the
clustering yielded only 4 usable groups (~58 names each) against 16 official
industries (~14 each), and larger groups are mechanically more heterogeneous.
On that unfair footing OFFICIAL "won" by +0.0467 (t −7.77). Sweeping k until the
granularity is comparable reverses it:

    k    data groups   vs random   vs OFFICIAL
    15        4          +0.0379    −0.0467  (t  −7.77)
    30        6          +0.0807    −0.0039  (t  −0.55)
    45        8          +0.1118    +0.0272  (t   4.37)
    60       10          +0.1420    +0.0574  (t  13.27)
    80       11          +0.1598    +0.0752  (t  17.62)

  So the honest statement is: at comparable granularity the data beats the
  taxonomy, and any single-k claim in either direction is an artefact. Default
  is k=45 (8 groups) as the closest fair match to 16 official industries once
  MIN_GROUP filtering is applied. Note the residual: higher k means smaller
  groups, which raises within-group correlation mechanically, so the +0.0752 at
  k=80 should NOT be read as the effect size.

  Possible outcomes, all interesting:
    DATA > OFFICIAL > RANDOM   taxonomy captures some structure, misses some
    OFFICIAL ≈ DATA > RANDOM   taxonomy is already near-optimal, leave it alone
    both ≈ RANDOM              co-movement is market-wide; SECTOR INDICES ARE
                               NOISE and the sector-rotation null earlier today
                               (every signal lost to equal-weight) was predicted

WHY THIS ALSO FIXES THE THEMATIC INDICES. custom_indices.py's THEMES are fixed
lists written today — every member survived to be named, so their histories
flatter the theme and cannot be read as backtests. Clusters here are DISCOVERED
from trailing returns at each formation, so membership is point-in-time and a
company that later failed is grouped while it still traded. That is the same
standard the SML* indices meet.

Usage:
  python3 cluster_indices.py --test
  python3 cluster_indices.py --test --k 12 --hold 126
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, "/Users/umashankar/scripts")

TOTAL_MKT = "https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CACHE = HERE / "cache_seed" / "nse_total_market_sectors.csv"
OUT_MD = HERE / "reports" / "cluster_indices.md"
UNIV, LOOKBACK, MIN_GROUP = 300, 252, 4


def sectors() -> pd.DataFrame:
    try:
        req = urllib.request.Request(TOTAL_MKT, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            b = r.read()
        if b"Symbol" not in b[:400]:
            raise ValueError("not the constituent CSV")
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_bytes(b)
        d = pd.read_csv(io.BytesIO(b))
    except Exception as e:                                # noqa: BLE001
        if not CACHE.exists():
            raise SystemExit(f"sector list unavailable and no cache: {e}")
        print(f"  ⚠ sector fetch failed ({str(e)[:40]}) — using cache")
        d = pd.read_csv(CACHE)
    d["Symbol"] = d.Symbol.str.strip()
    return d.set_index("Symbol").Industry


def within_corr(fwd: pd.DataFrame, groups: dict) -> float:
    """Mean within-group pairwise correlation in the forward window."""
    vals = []
    C = fwd.corr()
    for mem in groups.values():
        mem = [m for m in mem if m in C.columns]
        if len(mem) < 2:
            continue
        sub = C.loc[mem, mem].values
        iu = np.triu_indices(len(mem), 1)
        v = sub[iu]
        v = v[np.isfinite(v)]
        if len(v):
            vals.append(v.mean())
    return float(np.mean(vals)) if vals else np.nan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--k", type=int, default=45, help="number of data clusters")
    ap.add_argument("--hold", type=int, default=126)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    import pead_liquidity_study as P

    ind = sectors()
    px, tv = P.load_prices()
    bad = P.contaminated(px)
    px = px.drop(columns=[c for c in bad if c in px.columns]); tv = tv[px.columns]
    rets = px.pct_change(fill_method=None)
    dates = px.index
    rng = np.random.default_rng(a.seed)
    print(f"{px.shape[1]:,} symbols · {len(ind):,} with an NSE Industry label",
          flush=True)

    rows = []
    for i in range(LOOKBACK + 21, len(px) - a.hold, 63):
        turn = tv.iloc[i - 252:i].median().dropna().sort_values(ascending=False)
        uni = [c for c in turn.index[:UNIV] if c in ind.index]
        hist = rets[uni].iloc[i - LOOKBACK:i].dropna(axis=1, thresh=int(LOOKBACK * .9))
        uni = list(hist.columns)
        if len(uni) < 80:
            continue
        hist = hist.fillna(0.0)
        fwd = rets[uni].iloc[i:i + a.hold].fillna(0.0)

        C = hist.corr().fillna(0.0)
        D = np.clip(1 - C.values, 0, 2)
        np.fill_diagonal(D, 0.0)
        lab = fcluster(linkage(squareform(D, checks=False), "average"),
                       a.k, criterion="maxclust")
        data_g = {}
        for s, L in zip(uni, lab):
            data_g.setdefault(L, []).append(s)
        data_g = {k: v for k, v in data_g.items() if len(v) >= MIN_GROUP}

        off_g = {}
        for s in uni:
            off_g.setdefault(ind.get(s, "?"), []).append(s)
        off_g = {k: v for k, v in off_g.items() if len(v) >= MIN_GROUP}

        # random groups matching the OFFICIAL size profile, so the null is not
        # advantaged or handicapped by group-size differences
        shuf = list(uni); rng.shuffle(shuf)
        rnd_g, p = {}, 0
        for k, mem in off_g.items():
            rnd_g[k] = shuf[p:p + len(mem)]; p += len(mem)

        rows.append({
            "date": dates[i], "n": len(uni),
            "data": within_corr(fwd, data_g),
            "official": within_corr(fwd, off_g),
            "random": within_corr(fwd, rnd_g),
            "n_data": len(data_g), "n_off": len(off_g),
        })

    d = pd.DataFrame(rows).dropna()
    L = []
    def out(s=""):
        print(s); L.append(s)

    out("# Birds of a feather — does NSE's sector taxonomy capture co-movement?")
    out()
    out(f"- {len(d)} quarterly formations, {d.date.min().date()} → {d.date.max().date()}")
    out(f"- universe: top {UNIV} by trailing turnover with an NSE Industry label "
        f"(~{d.n.mean():.0f} usable)")
    out(f"- groups: {d.n_data.mean():.0f} data clusters vs {d.n_off.mean():.0f} "
        f"official industries · forward window {a.hold} bars")
    out(f"- metric: **mean within-group pairwise correlation in the FORWARD "
        f"window** (never seen by the grouping)")
    out()
    out("| grouping | mean within-group fwd corr | vs random | t vs random |")
    out("|---|--:|--:|--:|")
    for k, lbl in (("random", "RANDOM (the null)"),
                   ("official", "OFFICIAL NSE Industry"),
                   ("data", "DATA clusters (trailing corr)")):
        v = d[k]
        if k == "random":
            out(f"| {lbl} | {v.mean():.4f} | — | — |")
            continue
        diff = d[k] - d["random"]
        t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
        out(f"| **{lbl}** | {v.mean():.4f} | **{diff.mean():+.4f}** | {t:.2f} |")
    dv = d["data"] - d["official"]
    t = dv.mean() / (dv.std(ddof=1) / np.sqrt(len(dv)))
    out()
    out(f"- **DATA minus OFFICIAL: {dv.mean():+.4f}  (t = {t:.2f})** — "
        f"data clusters beat the taxonomy in {(dv > 0).mean():.0%} of formations")
    out()
    out("## by sub-period")
    out()
    out("| period | n | random | official | data |")
    out("|---|--:|--:|--:|--:|")
    for lbl, lo, hi in (("2017-2020", "2017-01-01", "2020-12-31"),
                        ("2021-2026", "2021-01-01", "2026-12-31")):
        g = d[(d.date >= lo) & (d.date <= hi)]
        if len(g) < 4:
            continue
        out(f"| {lbl} | {len(g)} | {g['random'].mean():.4f} | "
            f"{g['official'].mean():.4f} | {g['data'].mean():.4f} |")
    out()
    out("> RANDOM is the floor, not zero: any basket inherits market beta, so "
        "even shuffled groups co-move. A taxonomy earns its status only by "
        "beating it. Clusters are rebuilt from trailing returns at every "
        "formation, so membership is point-in-time — unlike a named thematic "
        "list, which every surviving member was chosen to be in.")
    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"\nwrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
