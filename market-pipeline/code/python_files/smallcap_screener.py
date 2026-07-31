#!/usr/bin/env python3
"""
smallcap_screener.py — the Nifty Smallcap 250, minus the names you shouldn't own.

THE FINDING THIS IS BUILT ON. Over 2016-08 → 2026-07, active small-cap funds
beat the Nifty Smallcap 250 by **+2.22pp/yr with 92% of funds beating**, and in
the pre-bull 2016-2020 sub-period by **+4.78pp with 92% beating**. That hit rate,
stable across opposite regimes, is the only fund-category alpha in the whole
Indian panel that survives a full cycle — Large Cap, Flexi Cap and ELSS all sit
within ±0.3pp of their own segment.

The mechanism is visible in the raw numbers: over 2016-2020 the Smallcap 250
index returned **1.95%/yr** while the median small-cap manager made **6.72%**.
The index is capitalisation-weighted and must hold everything in the band —
including names in terminal decline. A manager simply declines to own them.
So this is an EXCLUSION screener, not a selection screener: start from the
index and remove, rather than hunt for winners.

TWO MODES, because the honest test and the usable tool need different universes:

  --validate  Do the exclusion rules add value? Run on the PRICE PANEL, whose
              6,731 symbols include delisted names (DENABANK, DHFL, DISHMAN are
              all in there), so it is survivorship-FREE. Small-cap band is
              approximated point-in-time by trailing turnover rank.
  --screen    Apply the rules to TODAY's actual 250 constituents. A screener
              looking forward has no survivorship problem — the bias only bites
              when you project a current membership list backwards.

🔴 WHY THERE IS NO HISTORICAL BACKTEST ON THE REAL CONSTITUENTS. NSE publishes
only the CURRENT list. Reconstructing history from it, or from
fundamentals.ratios market caps (1,300 tickers, all companies that exist TODAY),
would embed exactly the survivorship that cost 7.5 points in the ETF study
earlier — a universe assembled from survivors makes any rule look good. A
market-cap reconstruction reproduces today's list at only 71% anyway. Real
point-in-time membership needs NSE's index-maintenance announcements, which is
a separate collection job.

EXCLUSIONS — price/volume only, all computable point-in-time. Fundamental
screens are deliberately absent: fundamentals.ratios is a CURRENT snapshot
(1,309 tickers, one fiscal year), so any fundamental rule would be applied with
hindsight.

  downtrend   below the 200-day moving average
  distress    more than 50% below the 3-year high
  blowup      trailing volatility in the top decile of the band
  untradeable median turnover below the ₹1cr floor used repo-wide

Usage:
  python3 smallcap_screener.py --validate
  python3 smallcap_screener.py --screen
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, "/Users/umashankar/scripts")

CONSTITUENTS = "https://niftyindices.com/IndexConstituent/ind_niftysmallcap250list.csv"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
BAND_LO, BAND_HI = 200, 450     # turnover-rank proxy for the small-cap band
MIN_TURNOVER = 1e7
HOLD = 63                        # quarterly rebalance
COST_BPS = 100.0                 # small caps: wider than the 50bp large-cap floor


_FUND = {"pe": None, "z": None, "eps": None}


def load_fundamentals(index):
    """Point-in-time P/E / TTM-EPS panels, aligned to the price calendar.

    Unblocked 2026-07-28: these exclusions were impossible while
    fundamentals.ratios held a single fiscal year. fundamentals.india_pe_daily
    now carries 1,957,213 daily observations over 1,744 symbols from the NSE
    XBRL parse, and its TTM EPS is stamped at each quarter's FILING date — so a
    lookup at bar i uses only what the market could already see.
    """
    if _FUND["pe"] is not None:
        return
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute("ATTACH 'dbname=market_data host=/tmp user=umashankar' AS pg (TYPE postgres)")
    d = con.execute("""SELECT symbol, obs_date, pe, pe_z
                       FROM pg.fundamentals.india_pe_daily""").df()
    d["obs_date"] = pd.to_datetime(d.obs_date)
    for key, col in (("pe", "pe"), ("z", "pe_z")):
        _FUND[key] = (d.pivot_table(index="obs_date", columns="symbol", values=col)
                       .reindex(index).ffill())
    # 🔴 TTM EPS MUST NOT COME FROM india_pe_daily. That table only stores rows
    # with pe > 0, so loss-makers are ABSENT rather than negative — the
    # `lossmaking` rule silently never fired (0 flagged in a 250-name band).
    # Source it from the quarterly table instead, where losses survive.
    q = con.execute("""SELECT symbol, period_end, filing_date, eps
                       FROM pg.fundamentals.india_quarterly
                       WHERE eps IS NOT NULL""").df()
    q["period_end"] = pd.to_datetime(q.period_end)
    q["filing_date"] = pd.to_datetime(q.filing_date)
    q = (q.sort_values(["symbol", "period_end"])
           .drop_duplicates(["symbol", "period_end"], keep="last"))
    q["ttm"] = np.nan
    for _s, g in q.groupby("symbol"):
        e = g.eps.rolling(4).sum()
        span = (g.period_end - g.period_end.shift(3)).dt.days
        q.loc[g.index, "ttm"] = e.where(span.between(255, 300)).values
    q = q.dropna(subset=["ttm"])
    _FUND["eps"] = (q.pivot_table(index="filing_date", columns="symbol",
                                  values="ttm", aggfunc="last")
                     .reindex(index, method="ffill"))


def flags(px: pd.DataFrame, tv: pd.DataFrame, i: int, cols,
          fundamentals: bool = False) -> pd.DataFrame:
    """Exclusion flags as of bar i, from bars strictly before it."""
    hist = px[cols].iloc[max(0, i - 756):i]
    last = hist.iloc[-1]
    ma200 = hist.iloc[-200:].mean()
    hi3y = hist.max()
    vol = hist.iloc[-126:].pct_change(fill_method=None).std()
    turn = tv[cols].iloc[max(0, i - 60):i].median()
    f = pd.DataFrame({
        "downtrend": last < ma200,
        "distress": last < 0.50 * hi3y,
        "blowup": vol > vol.quantile(0.90),
        "untradeable": turn < MIN_TURNOVER,
    })
    if fundamentals:
        load_fundamentals(px.index)
        # bar i-1: strictly before the decision bar, and the underlying TTM is
        # already lagged to its filing date, so this is doubly point-in-time
        eps = _FUND["eps"].iloc[i - 1].reindex(cols)
        z = _FUND["z"].iloc[i - 1].reindex(cols)
        eps_yr = (_FUND["eps"].iloc[max(0, i - 253)].reindex(cols)
                  if i > 253 else pd.Series(np.nan, index=cols))
        # NaN = no fundamental coverage. Do NOT exclude on absence — that would
        # silently screen out every name the XBRL parse has not reached and
        # dress a coverage gap up as a signal.
        f["lossmaking"] = (eps <= 0).fillna(False)
        f["overvalued"] = (z > 2.0).fillna(False)
        f["earnings_fall"] = ((eps < eps_yr * 0.5) & (eps_yr > 0)).fillna(False)
    f["excluded"] = f.drop(columns=["excluded"], errors="ignore").any(axis=1)
    return f


def validate(a) -> int:
    global HOLD
    HOLD = a.hold
    import pead_liquidity_study as P
    px, tv = P.load_prices()
    bad = P.contaminated(px)
    px = px.drop(columns=[c for c in bad if c in px.columns]); tv = tv[px.columns]
    dates = px.index

    # WARM-UP. Was 756 bars (3 years) because the distress rule references a
    # 3-year high — which pushed the first formation to 2019-01 and so SKIPPED
    # the 2016-2020 bear, the exact regime where small-cap fund alpha was
    # largest (+4.78pp, 92% beating). But flags() already degrades gracefully:
    # hist is `max(0, i-756):i`, so early periods simply use a shorter, still
    # strictly-trailing window. The real binding constraint is the 200-day
    # moving average, so the warm-up is that plus a small buffer.
    #   CONSEQUENCE, stated: before 2019 the "3-year high" is a since-inception
    #   high over a shorter window, which makes `distress` HARDER to trigger
    #   (less time to have fallen 50% from a peak). The early sub-period
    #   therefore understates that rule rather than flattering it.
    rows = []
    for i in range(a.warmup, len(px) - HOLD, 21):
        turn = tv.iloc[i - 260:i].median().dropna().sort_values(ascending=False)
        band = [c for c in turn.index[BAND_LO:BAND_HI] if c in px.columns]
        if len(band) < 100:
            continue
        f = flags(px, tv, i, band, fundamentals=a.fundamentals)
        fwd = (px[band].iloc[i + HOLD] / px[band].iloc[i] - 1).dropna()
        keep = fwd.index[~f.excluded.reindex(fwd.index).fillna(True)]
        drop = fwd.index[f.excluded.reindex(fwd.index).fillna(True)]
        if len(keep) < 20 or len(drop) < 5:
            continue
        rows.append({"date": dates[i], "n_all": len(fwd), "n_keep": len(keep),
                     "all": fwd.mean(), "keep": fwd[keep].mean(),
                     "dropped": fwd[drop].mean(),
                     **{k: fwd[fwd.index.intersection(f.index[f[k]])].mean()
                        for k in f.columns if k != "excluded"}})
    d = pd.DataFrame(rows)
    if d.empty:
        print("no periods"); return 1

    cost = COST_BPS / 10_000
    print(f"# Small-cap exclusion rules — survivorship-free validation\n")
    print(f"- {len(d)} monthly formations, {d.date.min().date()} → {d.date.max().date()}")
    print(f"- band = trailing turnover ranks {BAND_LO}-{BAND_HI} "
          f"(~{d.n_all.mean():.0f} names), {HOLD}-bar hold, {COST_BPS:.0f}bp charged")
    print(f"- panel INCLUDES delisted names, so this has no survivorship lift\n")
    print("| leg | mean 63-bar return | ann. | vs full band |")
    print("|---|--:|--:|--:|")
    for lbl, col in (("full band (the index proxy)", "all"),
                     ("SCREENED (exclusions removed)", "keep"),
                     ("the excluded names", "dropped")):
        m = d[col].mean() - (cost if col != "all" else cost)
        ann = (1 + m) ** 4 - 1
        print(f"| {lbl} | {m:+.2%} | {ann:+.2%} | "
              f"{(m - (d['all'].mean() - cost)) * 100:+.2f}pp |")
    print()
    print("## marginal effect of each exclusion (mean forward return of names it removes)")
    print()
    print("| rule | mean fwd | vs band | verdict |")
    print("|---|--:|--:|---|")
    base = d["all"].mean()
    for k in [c for c in ("downtrend", "distress", "blowup", "untradeable",
                          "lossmaking", "overvalued", "earnings_fall") if c in d]:
        v = d[k].dropna()
        if v.empty:
            continue
        diff = v.mean() - base
        print(f"| {k} | {v.mean():+.2%} | {diff * 100:+.2f}pp | "
              f"{'excluding helps' if diff < 0 else 'EXCLUDING HURTS'} |")
    sp = d.keep - d["all"]
    t = sp.mean() / (sp.std(ddof=1) / np.sqrt(len(sp)))
    print(f"\n- screened-minus-band per period: **{sp.mean():+.2%}**  (t = {t:.2f}, "
          f"n={len(sp)})")

    # Sub-periods: the whole point of extending the warm-up is to test the rules
    # in the 2016-2020 bear that motivated them, not just the bull that followed.
    print("\n## by sub-period (does it work in the regime it was built for?)\n")
    print("| period | n | band | screened | edge | t |")
    print("|---|--:|--:|--:|--:|--:|")
    for lbl, lo, hi in (("2016-2020 bear", "2016-01-01", "2020-10-31"),
                        ("2020-2026 bull", "2020-11-01", "2026-12-31")):
        g = d[(d.date >= lo) & (d.date <= hi)]
        if len(g) < 8:
            continue
        e = (g.keep - g["all"])
        tt = e.mean() / (e.std(ddof=1) / np.sqrt(len(e)))
        print(f"| {lbl} | {len(g)} | {g['all'].mean():+.2%} | {g.keep.mean():+.2%} | "
              f"**{e.mean():+.2%}** | {tt:.2f} |")
    return 0


def screen(a) -> int:
    import urllib.request
    import pead_liquidity_study as P
    # Constituent list is cached: it changes semi-annually at index review, so a
    # transient network failure must not take down a nightly pipeline step. Fetch
    # when possible, fall back to the cache, and only fail when neither exists.
    cache = HERE / "cache_seed" / "smallcap250_constituents.csv"
    try:
        req = urllib.request.Request(CONSTITUENTS, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read()
        if b"Symbol" not in body[:400]:
            raise ValueError("not the constituent CSV (SPA shell?)")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(body)
        cons = pd.read_csv(io.BytesIO(body))
    except Exception as e:                                # noqa: BLE001
        if not cache.exists():
            print(f"constituent fetch failed and no cache: {str(e)[:80]}")
            return 1
        print(f"  ⚠ constituent fetch failed ({str(e)[:50]}) — using cache "
              f"from {dt.date.fromtimestamp(cache.stat().st_mtime)}")
        cons = pd.read_csv(cache)
    syms = [s.strip() for s in cons.Symbol.dropna()]
    px, tv = P.load_prices()
    have = [s for s in syms if s in px.columns]
    f = flags(px, tv, len(px) - 1, have, fundamentals=a.fundamentals)
    f = f.join(cons.set_index(cons.Symbol.str.strip())[["Company Name", "Industry"]])
    keep = f[~f.excluded]
    print(f"# Nifty Smallcap 250 — exclusion screen, {px.index[-1].date()}\n")
    print(f"- constituents {len(syms)} · priced in panel {len(have)} · "
          f"**KEEP {len(keep)}** · excluded {int(f.excluded.sum())}\n")
    print("| rule | names removed |")
    print("|---|--:|")
    for k in ("downtrend", "distress", "blowup", "untradeable"):
        print(f"| {k} | {int(f[k].sum())} |")
    print(f"\n## excluded by sector (where the index is carrying dead weight)\n")
    ex = f[f.excluded]
    vc = ex.Industry.value_counts().head(8)
    print("| industry | excluded | of total in index |")
    print("|---|--:|--:|")
    tot = f.Industry.value_counts()
    for ind, n in vc.items():
        print(f"| {ind} | {n} | {tot.get(ind, 0)} |")
    out = HERE / "reports" / "smallcap_screen.csv"
    f.reset_index().rename(columns={"index": "symbol"}).to_csv(out, index=False)
    print(f"\nwrote {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--fundamentals", action="store_true",
                    help="add loss-making / overvalued / earnings-collapse rules")
    ap.add_argument("--warmup", type=int, default=220,
                    help="bars before the first formation (200DMA + buffer)")
    ap.add_argument("--hold", type=int, default=63,
                    help="bars held before rebalance: 63=quarterly, 252=annual, 756=3y (Coffee-Can-ish)")
    ap.add_argument("--screen", action="store_true")
    a = ap.parse_args()
    if a.validate:
        # PERSIST THE VALIDATION, don't just print it. The headline this screen
        # rests on — screened-minus-band +3.07%/126 bars, t 8.75 — was quoted in
        # custom_indices.py while living nowhere on disk: --validate printed it
        # to a terminal and --screen wrote only the picks CSV. A number a reader
        # cannot check without re-running a multi-minute job is unsourced in
        # practice, however true it is. Output is teed so the console behaviour
        # is unchanged and the artefact exists.
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = validate(a)
        body = buf.getvalue()
        print(body, end="")
        # Hold period is IN THE FILENAME. The screen's headline changes with it
        # — +1.76% (t 6.09) at the default 63 bars, +3.07% (t 8.75) at 126 —
        # and custom_indices.py quoted the 126-bar figure while the default run
        # would have overwritten it with the 63-bar one, so whichever ran last
        # would silently define "the" result. Both are legitimate; they answer
        # different questions (quarterly vs semi-annual rebalance) and both need
        # to exist on disk for either to be checkable.
        rp = HERE / "reports" / f"smallcap_validation_hold{a.hold}.md"
        rp.parent.mkdir(exist_ok=True)
        rp.write_text(
            f"# Small-cap exclusion screen — validation\n\n"
            f"Generated {dt.date.today()} by "
            f"`smallcap_screener.py --validate"
            f"{' --fundamentals' if a.fundamentals else ''} "
            f"--hold {a.hold} --warmup {a.warmup}`. Survivorship-free: the band "
            f"is reconstructed point-in-time at each formation.\n\n{body}")
        print(f"\nwrote {rp}")
        return rc
    if a.screen:
        return screen(a)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
