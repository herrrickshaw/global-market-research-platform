#!/usr/bin/env python3
"""
peer_warranted.py — Bhojraj-Lee peer selection, tested against NSE's taxonomy.

THE CLAIM BEING TESTED. Bhojraj & Lee (2002), "Who Is My Peer? A Valuation-Based
Approach to the Selection of Comparable Firms" (JAR), argues that industry
classification is a poor way to pick comparables, and that firms should instead
be grouped by their WARRANTED MULTIPLE — the multiple their fundamentals imply.
Bhojraj, Lee & Oler (2003) found GICS beats SIC/NAICS specifically at explaining
valuation-multiple variation, so the taxonomy is not worthless; the question is
whether a fitted multiple beats it.

The user's framing is the mechanism: peers get marked off each other's
multiples, so a good peer set should show LOW dispersion in actual P/E.

METHOD, following the paper's shape:
  1. At each formation year, regress log(P/E) cross-sectionally on fundamentals
     — profitability (ROE), growth (revenue YoY), leverage, size, asset
     efficiency. The FITTED value is the warranted multiple.
  2. Peers = the k firms nearest in warranted multiple.
  3. Score each grouping by dispersion of ACTUAL log P/E within it, out of
     sample. Lower = tighter comparables.
  Compared against: NSE Industry (the incumbent) and random groups of equal
  size (the floor, since any group inherits market-wide valuation drift).

🔴 THE REGRESSION IS FIT ON PRIOR YEARS ONLY. Fitting on the same cross-section
being scored would guarantee a win — the fitted value is constructed to explain
that year's multiples. Coefficients come from years strictly before the
formation year, so the warranted multiple is a genuine forecast.

🔴 LOG P/E THROUGHOUT. A multiple is ratio-scale and right-skewed; 10->20 must
count the same as 40->80. This is the same correction applied to pe_bands.py
after raw-P/E banding produced z-scores of +78.

DATA. fundamentals.india_pe_daily (screener path — the validated one, 28.5%
median error against fundamentals.ratios) joined to the screener fundamentals.

Usage:
  python3 peer_warranted.py
  python3 peer_warranted.py --k 15
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
DSN = "dbname=market_data host=/tmp user=umashankar"
SRC = ("/Users/umashankar/repos/global-stock-screener/"
       "cache_seed/fundamentals_history/IN_screener_only_backup.parquet")
OUT_MD = HERE / "reports" / "peer_warranted.md"
MIN_GROUP = 5


def dispersion(groups: dict, lpe: pd.Series) -> float:
    """Median absolute deviation of log P/E within a group, averaged."""
    v = []
    for mem in groups.values():
        s = lpe.reindex([m for m in mem if m in lpe.index]).dropna()
        if len(s) >= 4:
            v.append((s - s.median()).abs().median())
    return float(np.mean(v)) if v else np.nan


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--k", type=int, default=12, help="peers per group")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")
    pe = con.execute("""SELECT symbol, obs_date, pe FROM pg.fundamentals.india_pe_daily
                        WHERE pe > 0""").df()
    pe["obs_date"] = pd.to_datetime(pe.obs_date)
    pe["year"] = pe.obs_date.dt.year
    # one P/E per symbol-year: the last observation of that year
    pe = (pe.sort_values("obs_date").groupby(["symbol", "year"], as_index=False)
            .agg(pe=("pe", "last")))
    pe["lpe"] = np.log(pe.pe)

    f = pd.read_parquet(SRC)
    f["fy_end"] = pd.to_datetime(f.fy_end)
    f["year"] = f.fy_end.dt.year
    f["equity"] = f.equity_capital.fillna(0) + f.reserves.fillna(0)
    f["roe"] = f.net_income / f.equity.replace(0, np.nan)
    f["lev"] = f.borrowings / f.equity.replace(0, np.nan)
    f["size"] = np.log(f.revenue.clip(lower=1))
    f["turn"] = f.revenue / f.capital_employed.replace(0, np.nan)
    f = f.sort_values(["ticker", "year"])
    f["growth"] = f.groupby("ticker").revenue.pct_change()
    f = f.rename(columns={"ticker": "symbol"})
    X = ["roe", "lev", "size", "turn", "growth"]
    d = pe.merge(f[["symbol", "year", "industry", *X]], on=["symbol", "year"],
                 how="inner").dropna(subset=["lpe"])
    for c in X:
        d[c] = d.groupby("year")[c].transform(
            lambda s: s.clip(s.quantile(.02), s.quantile(.98)))
    d = d.dropna(subset=X)
    print(f"{len(d):,} symbol-years · {d.symbol.nunique():,} symbols · "
          f"{d.year.min()}-{d.year.max()}", flush=True)

    rng = np.random.default_rng(a.seed)
    rows = []
    years = sorted(d.year.unique())
    for y in years:
        train = d[d.year < y]
        test = d[d.year == y]
        if len(train) < 300 or len(test) < 80:
            continue
        # warranted multiple: coefficients from PRIOR years only
        A = np.column_stack([np.ones(len(train)), train[X].values])
        beta, *_ = np.linalg.lstsq(A, train.lpe.values, rcond=None)
        B = np.column_stack([np.ones(len(test)), test[X].values])
        warranted = B @ beta

        t = test.set_index("symbol")
        lpe = t.lpe
        order = pd.Series(warranted, index=t.index).sort_values()
        # contiguous blocks of k in warranted space = nearest-multiple peers
        wl = {i: list(order.index[i:i + a.k])
              for i in range(0, len(order) - MIN_GROUP + 1, a.k)}
        ind = {}
        for s, g in t.groupby("industry"):
            if len(g) >= MIN_GROUP:
                ind[s] = list(g.index)
        shuf = list(t.index); rng.shuffle(shuf)
        rnd, p = {}, 0
        for s, mem in ind.items():
            rnd[s] = shuf[p:p + len(mem)]; p += len(mem)

        rows.append({"year": y, "n": len(test),
                     "warranted": dispersion(wl, lpe),
                     "industry": dispersion(ind, lpe),
                     "random": dispersion(rnd, lpe),
                     "n_wl": len(wl), "n_ind": len(ind)})

    r = pd.DataFrame(rows).dropna()
    L = []
    def out(s=""):
        print(s); L.append(s)

    out("# Bhojraj-Lee warranted-multiple peers vs NSE Industry")
    out()
    out(f"- {len(r)} formation years, {r.year.min()}-{r.year.max()} · "
        f"~{r.n.mean():.0f} firms each")
    out(f"- peers per group: {a.k} · groups: ~{r.n_wl.mean():.0f} warranted vs "
        f"~{r.n_ind.mean():.0f} industries")
    out(f"- metric: **median absolute deviation of log P/E within a group** "
        f"(lower = tighter comparables)")
    out(f"- regression coefficients fit on years STRICTLY BEFORE each formation")
    out()
    out("| grouping | dispersion of log P/E | vs random | t vs random |")
    out("|---|--:|--:|--:|")
    for k, lbl in (("random", "RANDOM (the floor)"),
                   ("industry", "NSE Industry"),
                   ("warranted", "WARRANTED multiple (Bhojraj-Lee)")):
        v = r[k]
        if k == "random":
            out(f"| {lbl} | {v.mean():.4f} | — | — |")
            continue
        diff = r[k] - r["random"]
        t = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff)))
        out(f"| **{lbl}** | {v.mean():.4f} | **{diff.mean():+.4f}** | {t:.2f} |")
    dv = r.warranted - r.industry
    t = dv.mean() / (dv.std(ddof=1) / np.sqrt(len(dv)))
    out()
    out(f"- **WARRANTED minus INDUSTRY: {dv.mean():+.4f}  (t = {t:.2f})** — "
        f"warranted is tighter in {(dv < 0).mean():.0%} of years "
        f"(negative = better)")
    out()
    out("| year | n | random | industry | warranted |")
    out("|---|--:|--:|--:|--:|")
    for x in r.itertuples():
        out(f"| {x.year} | {x.n} | {x.random:.4f} | {x.industry:.4f} | "
            f"{x.warranted:.4f} |")
    out()
    out("> Lower dispersion means the group's members actually trade on similar "
        "multiples, which is what a comparable set is for. RANDOM is the floor "
        "rather than zero because every group inherits market-wide valuation "
        "drift. Coefficients are estimated out of sample, so the warranted "
        "multiple is a forecast and not a restatement of the year being scored.")
    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"\nwrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
