#!/usr/bin/env python3
"""
signal_tracker.py — record filter passes on the day they happen, then measure
what actually followed.

WHY THIS IS WORTH MORE THAN ANOTHER BACKTEST
--------------------------------------------
Every backtest in this repo carries the same three wounds, and all three push
results in the flattering direction:

  * SURVIVORSHIP — screener.in and yfinance serve companies that still exist, so
    the names a quality screen should have avoided are invisible.
  * LOOKAHEAD RISK — a filing date proxy that is wrong by a month hands the
    strategy information it did not have.
  * SELECTION — the universe is whatever happened to be collected.

Forward tracking has none of them. A pick is written down TODAY, with today's
price, before the outcome exists. Nothing can be quietly dropped later, because
the record was made first. It is slow — a year of tracking buys one year of
evidence — but it is the only evidence here that cannot be talked up.

🔴 THE ONE RULE: signal_date is NEVER backfilled.
The moment a signal can be recorded with a past date, the whole exercise decays
into another backtest with the same wounds. `record` only ever stamps today.
A missed day is a gap in the record, and a gap is honest; a reconstructed entry
is not.

WHAT COUNTS AS A PASS
  technical  Quality_Grade A/B AND above a RISING EMA-50 AND a recomputed
             BREAKOUT_BUY (see breakout_quality.py — the stored Darvas_Signal
             was corrupt until 2026-07-21 and is not trusted here)
  fundamental  piotroski / roce_plus / debt_reduction from the India factor
             panel, and their combinations

    signal_tracker.py --record        # stamp today's passes (idempotent)
    signal_tracker.py --report        # performance since each signal date
    signal_tracker.py --report --min-days 21

🔴 --min-days IS this script's embargo, whether or not it was named that.
2026-08-23 research (4 agents; research/LITERATURE_REGISTER.md "CPCV / embargo"
section) found no single literature formula for embargo length, but multiple
sources argue the theoretically-motivated minimum is embargo >= the horizon
being evaluated (purge_embargo.py implements the precise version of this for
train/test/val splits — a different situation from this script, see below).

This script does NOT report fixed horizon columns (T+1d/T+1mo/etc, unlike
backtest_screeners.py's HORIZONS table) — each entry's return is measured from
signal_date to WHATEVER today's last panel bar is, so "days held" varies per
entry and grows without bound as an entry ages. There is no train/test split
here for purge_embargo.py's machinery to apply to directly. The embargo idea
still applies, just differently: --min-days is a floor on how much price
history an entry needs before its single as-of-today return is stable enough
to be worth aggregating, not a boundary between two label windows. A low
--min-days (the CLI example above uses 21) mixes very-fresh, noisy entries in
with mature ones inside the same "med ret" statistic — the "med days" column
`report()` prints alongside every result exists so the READER can judge that,
but the aggregate itself does not separate them. If this ledger's output is
ever consumed as an INPUT to a decision (e.g. weighting which screener to
trust more), raise --min-days for that specific use well past 21 (the report
already prints the oldest-entry age and a per-filter breakdown so an
appropriate floor can be chosen from real data, not guessed).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import data_registry as _dr
import warehouse_paths as _wh

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "cache_seed" / "signal_ledger.parquet"
# Warehouse dirs (year-partitioned parquet). Replaces the monolithic ltm panels
# and the per-market folklore of which repo held the good copy (the other
# US.parquet is the broken alphabetical collection).
# Read via _panel() and NOT by handing the directory to read_parquet: directory
# reads pull in every file present, so a stray year=YYYY.parquet.bak or .tmp is
# loaded as a second copy of that year and every bar in it silently doubles.
# That is exactly what happened to 2026 (fixed in warehouse_update.py 2026-07-31).
# 🔴 INDIA READS THE ADJUSTED PANEL, NOT THE RAW ONE. India is the only market
# with a real corporate-actions feed behind it, so price_adjuster.py can adjust
# the WHOLE panel (ohlcv_adj/IN) rather than patch a handful of symbols. Reading
# ohlcv/IN here instead meant every split and bonus printed as a crash: on
# 2026-08-25 trailing_returns.py reported hundreds of Indian names past ±90%,
# and warehouse_paths.ohlcv_adj_in() carries the same warning for exactly this
# reason — a consumer reaching for the raw panel must not silently get it.
#
# The raw panel stays raw ON PURPOSE: it is price_adjuster.py's INPUT, and
# adjusting it in place double-applies every factor on the next ingest.sh run.
# Fix consumers to read the adjusted panel; never "fix" the raw one.
#
# US keeps the raw panel because no adjusted panel exists for it — the global
# adjuster ships corrected_symbols.parquet, a patch overlay, not partitions.
#
# EU/JP/KR added 2026-09-16. This dict held only IN and US, and the skip branch
# in track() asserted those three "have no persisted panel — their scans fetch
# live and keep nothing". That stopped being true: the warehouse carries EU, JP
# and KR partitions with 11 year-files each, current to the same bar as IN and
# US. The stale entry cost real coverage — 3,812 of filter_watchlist.csv's 8,300
# rows (every EU, JP and KR name) scored as "no local price panel for this
# market" while the data sat on disk unread, and the ledger's EU/JP/KR entries
# were invisible to tracking unless someone passed --fetch-missing and re-pulled
# from yfinance what was already local.
#
# 🔴 CN IS DELIBERATELY EXCLUDED. Its partition exists and loads, but its last
# bar is 2026-07-01 — two and a half months stale. Adding it here would let the
# mailer price today's signals off July closes and report them as current, which
# is worse than the honest "no panel" skip it gets now. Add CN the day its
# ingest is fixed, not before.
PANELS = {
    "IN": _wh.ohlcv_adj_in(),
    "US": _wh.market("US"),
    "EU": _wh.market("EU"),
    "JP": _wh.market("JP"),
    "KR": _wh.market("KR"),
}


def _panel(p: Path, columns=None) -> pd.DataFrame:
    """Read a warehouse panel from its year partitions only."""
    return pd.concat(
        [pd.read_parquet(f, columns=columns) for f in sorted(p.glob("year=*.parquet"))],
        ignore_index=True,
    )


def resolve_symbol(sym: str, mkt: str, columns) -> str | None:
    """A ledger/watchlist symbol -> that panel's own column name, or None.

    Registering the EU/JP/KR panels above is only half the fix: the ledger and
    the watchlists disagree with the panels about ticker FORM for two of them,
    so a bare lookup moves those rows from "no_panel" to "not_in_panel" and
    tracks exactly as little as before.

        JP   ledger '1301'    panel '1301.T'
        KR   ledger '100030'  panel '000020.KS' / '263750.KQ'
             ...and KR codes have lost their leading zeros upstream, so '100'
             is really '000100' and needs re-padding to six digits.
        EU   already exchange-qualified on both sides — matches 100% as-is.

    🔴 THE KR SUFFIX IS LOOKED UP, NEVER INFERRED. .KS is KOSPI and .KQ is
    KOSDAQ — 946 and 1,833 of the panel respectively — and nothing in a 6-digit
    code says which. Guessing one silently mis-resolves two thirds of the
    market, and a wrong-but-plausible price is far worse here than a miss. The
    panel's own column list is the allowlist: a code matching no column stays
    unresolved and is COUNTED as not_in_panel, never approximated.
    """
    s = str(sym).strip().upper()
    if s in columns:
        return s
    if mkt == "JP":
        return f"{s}.T" if f"{s}.T" in columns else None
    if mkt == "KR":
        base = s.zfill(6)
        for suf in (".KS", ".KQ"):
            if base + suf in columns:
                return base + suf
        return None
    return None


# EU/JP/KR have no entry: no index ETF for them exists in the panels (checked
# 1306.T/1321.T, 069500.KS, EXS1.DE/ISF.L/MEUD.PA and others, none present), so
# `vs mkt` stays NaN for those markets and track() emits an explicit
# "no usable benchmark" note. That is the honest outcome — substituting a panel
# median for a benchmark is what india_benchmark()'s docstring exists to warn
# against. Wire a real index series in before adding a key here.
BENCH = {"IN": "NIFTYBEES", "US": "SPY"}
GOOD_GRADES = {"A", "B"}


def india_benchmark(wide: Optional[pd.DataFrame] = None) -> pd.Series:
    """The real NIFTY 50 line for India: NIFTYBEES panel bars spliced onto the
    NSE index series, rescaled at the seam so the handoff has no jump.

    🔴 THERE IS NO PANEL-MEDIAN FALLBACK, AND THERE MUST NEVER BE ONE AGAIN.
    This function used to be `wide.median(axis=1)` — the cross-sectional median
    CLOSE PRICE — whenever NIFTYBEES went stale. The 2026-08-22 audit caught it
    fabricating a **+46.77%** "vs bench" for India: the median fell from 230 in
    mid-June to 125 in August, a ~46% "index decline" that never happened. The
    panel's composition is not fixed day to day (1,654 symbols in year=2016,
    7,073 in year=2026), so the "return of the median" measures which names
    happened to have a bar, not what the market did. The fix was written into
    research/stock_pick_performance.py at the time and never ported back here,
    so the live tracker kept grading every India signal against the fabricated
    series for another three weeks. An entry with no real benchmark gets NaN —
    never a number that looks precise and is wrong.

    Two bugs in the earlier copies of this splice are fixed here:

      * THE SEAM IS THE LAST DATE PRESENT IN BOTH SERIES, not `n50.iloc[0]`.
        The old factor `nb.iloc[-1] / n50.iloc[0]` divides NIFTYBEES's last bar
        by the index's FIRST bar — six weeks apart as of 2026-09-11, and off by
        +0.69%. Anchoring on a shared date makes the factor exact by
        construction.
      * ONLY THE STRICTLY-AFTER TAIL IS APPENDED. A plain concat of the two
        series leaves duplicate dates wherever they overlap, and the callers
        below index with `.iloc[0]` / `.iloc[-1]`, which then pick arbitrarily
        between two values for the same day.

    🔴 THE NIFTYBEES LEG IS NOT SPLIT-ADJUSTED BEFORE 2020, AND IT IS SAFE ONLY
    FOR RECENT WINDOWS. Measured 2026-09-11: the series jumps **+89.9% on
    2019-12-19** — a corporate action, not a market move. The India adjuster
    works off the equity corporate-actions feed, and NIFTYBEES was filtered out
    of that feed as an ETF (ISIN prefix INF), which is the same filter that
    stops its bars updating. So the one instrument used to benchmark India is
    also the one the adjuster cannot see. This does NOT touch current tracking —
    the ledger starts 2026-07-13 and the window in use moves a maximum of 1.93%
    in a day — but a caller that reaches back past 2020 will get a fabricated
    +90% "market return", which is the same class of error this function exists
    to remove. The guard below shouts if that happens; fixing it properly needs
    ETF corporate actions the repo does not collect.

    `wide` is the caller's already-pivoted panel, passed in to avoid re-reading
    it; omitted, the panel is read here (which is what the research scripts do).
    """
    if wide is None:
        px = _panel(PANELS["IN"], columns=["Date", "Symbol", "Close"])
        px["Symbol"] = px["Symbol"].astype(str).str.upper()
        wide = px.pivot_table(index="Date", columns="Symbol", values="Close",
                              aggfunc="last").sort_index()
    nb = (wide[BENCH["IN"]].dropna().sort_index()
          if BENCH["IN"] in wide.columns else pd.Series(dtype=float))

    ic = pd.read_parquet(_dr.MARKET_CACHE / "exchange_extras" / "index_closes.parquet",
                         columns=["Index Name", "Index Date", "Closing Index Value"])
    ic = ic[ic["Index Name"] == "Nifty 50"]
    n50 = pd.Series(
        pd.to_numeric(ic["Closing Index Value"], errors="coerce").values,
        index=pd.to_datetime(ic["Index Date"], format="%d-%m-%Y", errors="coerce"),
    ).dropna().sort_index()
    n50 = n50[~n50.index.duplicated(keep="last")]

    if not len(nb):
        return n50                      # level is irrelevant; only ratios are used
    if not len(n50):
        return nb

    common = nb.index.intersection(n50.index)
    if len(common):
        seam = common.max()
        factor = float(nb[seam]) / float(n50[seam])
    else:
        # No shared date: anchor on the smallest gap available — NIFTYBEES's
        # last bar against the first index bar at or after it. Approximate, so
        # it is worth knowing when this branch is taken rather than the exact one.
        after = n50[n50.index >= nb.index.max()]
        if not len(after):
            return nb
        factor = float(nb.iloc[-1]) / float(after.iloc[0])
    tail = n50[n50.index > nb.index.max()] * factor
    out = pd.concat([nb, tail]).sort_index()

    # An index does not move 25% in a day. If one appears, it is an unadjusted
    # corporate action in the NIFTYBEES leg (see the docstring), and any return
    # chained across it is fiction. Warn rather than raise: callers working in
    # recent windows are unaffected, and a hard failure here would take down the
    # nightly report over a 2019 artifact it never touches.
    jumps = out.pct_change().abs()
    bad = jumps[jumps > 0.25]
    if len(bad):
        print(f"  ⚠ india_benchmark: {len(bad)} unadjusted jump(s) in the NIFTYBEES leg "
              f"({', '.join(f'{d:%Y-%m-%d} {v*100:+.0f}%' for d, v in bad.items())}). "
              f"Safe after {bad.index.max():%Y-%m-%d}; do NOT chain a return across it.",
              file=sys.stderr)
    return out


SCAN_DIRS = {
    "IN": ("indian_full_scan", "indian_full_scan_*.xlsx"),
    "US": ("us_full_scan", "us_full_scan_*.xlsx"),
    "KR": ("korea_scan", "korea_market_scan_*.xlsx"),
    "JP": ("japan_scan", "japan_market_scan_*.xlsx"),
    "EU": ("european_scan", "european_market_scan_broad_*.xlsx"),
}


def _latest(d: str, pat: str) -> Optional[Path]:
    fs = sorted((HERE / d).glob(pat))
    return fs[-1] if fs else None


def harvest_technical() -> pd.DataFrame:
    """Today's high-quality breakouts across every market that scanned."""
    rows = []
    for mkt, (d, pat) in SCAN_DIRS.items():
        f = _latest(d, pat)
        if not f:
            continue
        try:
            s = pd.read_excel(f, "All_Stocks")
        except Exception:
            continue
        if "Quality_Grade" not in s.columns:
            continue          # scan predates breakout_quality
        sym_col = "Symbol" if "Symbol" in s.columns else "Code"
        ok = s[
            s["Quality_Grade"].isin(GOOD_GRADES)
            & s.get("Above_EMA50", pd.Series(False, index=s.index)).fillna(False).astype(bool)
            & s.get("EMA50_Rising", pd.Series(False, index=s.index)).fillna(False).astype(bool)
            & (s.get("Recomputed_Signal", pd.Series("", index=s.index)) == "BREAKOUT_BUY")
        ]
        for _, r in ok.iterrows():
            rows.append({
                "symbol": str(r[sym_col]).strip().upper(), "market": mkt,
                "filter": "technical", "detail": f"grade {r['Quality_Grade']}",
                "score": float(r.get("Quality_Score") or np.nan),
                "price_at_signal": pd.to_numeric(
                    pd.Series([r.get("LTP") or r.get("LTP_KRW") or r.get("LTP_JPY")]),
                    errors="coerce").iloc[0],
                "source": f.name,
            })
    return pd.DataFrame(rows)


def harvest_fundamental() -> pd.DataFrame:
    """Most recent rebalance's factor passes from the India panel."""
    p = HERE / "cache_seed" / "india_factor_panel.parquet"
    if not p.exists():
        return pd.DataFrame()
    d = pd.read_parquet(p)
    d = d[d["year"] == d["year"].max()]
    combos = [
        ("piotroski", d["piotroski"]),
        ("roce_plus", d["roce_plus"]),
        ("debt_reduction", d["debt_reduction"]),
        ("piotroski+debt", d["piotroski"] & d["debt_reduction"]),
        ("piotroski+roce", d["piotroski"] & d["roce_plus"]),
        ("triple", d["piotroski"] & d["roce_plus"] & d["debt_reduction"]),
    ]
    rows = []
    for name, mask in combos:
        for _, r in d[mask.fillna(False)].iterrows():
            rows.append({"symbol": str(r["ticker"]).strip().upper(), "market": "IN",
                         "filter": name, "detail": f"F={r.get('f_score')}",
                         "score": float(r.get("f_score") or np.nan),
                         "price_at_signal": np.nan, "source": "india_factor_panel"})
    return pd.DataFrame(rows)


WATCHLIST = HERE / "watchlist.csv"
# Filters strong enough to earn a watchlist slot. Recording EVERY pass would add
# ~50 debt_reduction names a day and drown the list within a week — the ledger
# tracks all of them regardless, so nothing is lost by being selective here.
WATCHLIST_FILTERS = {"triple", "piotroski+debt", "piotroski+roce", "technical"}

# `technical` needs a HARD CAP that the fundamental filters do not.
#
# It fired 110 times on 2026-07-21 while only the Korea scanner emitted
# Quality_Grade. Once breakout_quality was wired into the other four scanners
# the same filter returned 2,110 passes in one run and pushed the watchlist from
# 775 rows to 2,703 — a "watchlist" nobody can act on. The filter is not broken:
# 2,110 of ~15,000 names is a ~14% hit rate, which is what a grade-A/B breakout
# screen should return. It is simply not a shortlist.
#
# Grade alone is not enough of a bar — grade A is still 595 names/day, and any
# daily intake compounds. So: rank by quality score and take the best few PER
# MARKET. Per-market, not global, because a global top-N would hand the whole
# list to whichever market happened to scan the most names — the Korea skew
# again, pointed the other way (US alone was 1,044 of the 2,110).
#
# The ledger still records every pass, so nothing is lost for analysis; this
# bounds only what earns a tracked watchlist slot.
TECHNICAL_MIN_GRADE = {"grade A"}     # detail string as harvest_technical writes it
TECHNICAL_TOP_PER_MARKET = 5


def _cap_technical(new: pd.DataFrame) -> pd.DataFrame:
    """Keep only the strongest few `technical` passes per market."""
    if new.empty or "filter" not in new.columns:
        return new
    tech = new[new["filter"] == "technical"]
    rest = new[new["filter"] != "technical"]
    if tech.empty:
        return new
    keep = (tech[tech["detail"].isin(TECHNICAL_MIN_GRADE)]
            .sort_values("score", ascending=False)
            .groupby("market", group_keys=False)
            .head(TECHNICAL_TOP_PER_MARKET))
    return pd.concat([rest, keep], ignore_index=True)


def sync_watchlist(new: pd.DataFrame) -> int:
    """Add today's strongest passes to watchlist.csv as the `signal` tier.

    Existing rows are never touched: a name already held or sold keeps that
    status. A stock you own that re-passes a filter is still a holding, and
    demoting it to `signal` would lose the more important fact.
    """
    if new.empty or not WATCHLIST.exists():
        return 0
    wl = pd.read_csv(WATCHLIST)
    have = {(str(r["symbol"]).upper(), str(r["market"]).upper())
            for _, r in wl.iterrows()}
    added = 0
    new = _cap_technical(new)
    add_rows = []
    for _, r in new[new["filter"].isin(WATCHLIST_FILTERS)].iterrows():
        k = (r["symbol"], r["market"])
        if k in have:
            continue
        d = f"{pd.Timestamp(r['signal_date']):%Y-%m-%d}"
        px = pd.to_numeric(r.get("price_at_signal"), errors="coerce")
        # entry_date/entry_price stamped at ADD time — the digest's zone/return
        # columns need them, and reconstructing later means parsing notes.
        add_rows.append({"symbol": r["symbol"], "market": r["market"],
                         "status": "signal", "note": f"{r['filter']} {d}",
                         "entry_date": d,
                         "entry_price": round(float(px), 4) if pd.notna(px) else None})
        have.add(k); added += 1
    if added:
        # concat + to_csv, NOT a hand-rolled 4-column csv.writer: the watchlist
        # grew entry_date/entry_price columns (2026-07-23) and a fixed-header
        # rewrite here would silently shear them off on the next signal day.
        pd.concat([wl, pd.DataFrame(add_rows)], ignore_index=True).to_csv(
            WATCHLIST, index=False)
    return added


def record() -> int:
    today = pd.Timestamp(date.today())
    new = pd.concat([harvest_technical(), harvest_fundamental()], ignore_index=True)
    if new.empty:
        print("  no filter passes today"); return 0
    new["signal_date"] = today

    # Fill missing entry prices from the price panel, but ONLY as of today.
    for mkt, grp in new.groupby("market"):
        p = PANELS.get(mkt)
        if not p or not p.exists():
            continue
        px = _panel(p, columns=["Date", "Symbol", "Close"])
        px["Symbol"] = px["Symbol"].astype(str).str.upper()
        last = px.sort_values("Date").groupby("Symbol")["Close"].last()
        miss = new["price_at_signal"].isna() & (new["market"] == mkt)
        # Through resolve_symbol, not a bare .map: a JP signal recorded as
        # '1301' has to find the panel's '1301.T' or it silently keeps a null
        # entry price, and a null price_at_signal is exactly what made 121
        # backfilled rows untrackable and the report structurally empty.
        new.loc[miss, "price_at_signal"] = new.loc[miss, "symbol"].map(
            lambda s: last.get(resolve_symbol(s, mkt, last.index))
        )

    old = pd.read_parquet(LEDGER) if LEDGER.exists() else pd.DataFrame()
    if not old.empty:
        # Idempotent per day: re-running must not duplicate or re-stamp. An
        # existing (symbol, filter, date) row is left exactly as first written.
        key = ["symbol", "filter", "signal_date"]
        merged = pd.concat([old, new], ignore_index=True)
        before = len(merged)
        merged = merged.drop_duplicates(subset=key, keep="first")
        added = len(merged) - len(old)
        print(f"  {len(new)} passes today; {added} new, "
              f"{before - len(merged)} already recorded")
    else:
        merged, added = new, len(new)
        print(f"  {added} passes recorded (ledger created)")

    LEDGER.parent.mkdir(exist_ok=True)
    merged.to_parquet(LEDGER, index=False)
    for f, n in new["filter"].value_counts().items():
        print(f"     {f:<18} {n}")
    print(f"  → {LEDGER}  ({len(merged)} total entries)")

    n_wl = sync_watchlist(new)
    print(f"  watchlist: +{n_wl} signal name(s)"
          if n_wl else "  watchlist: no new names (all already tracked)")
    return 0


def _track_via_yf(grp: pd.DataFrame, mkt: str, min_days: int) -> list:
    """Forward-track EU/JP/KR signals from yfinance — markets with no local panel.

    Symbol conventions are the watchlist's, reused rather than re-derived:
    Korea's bare codes have lost their leading zeros (38880 is 038880) and need
    re-padding plus a .KS/.KQ board suffix; Japan needs .T; EU symbols already
    carry their exchange suffix.

    No benchmark: there is no index series for these markets in any local store,
    and inventing one from the handful of shortlisted names would compare each
    signal against itself. `xret_pct` stays NaN and the summary shows it as such.
    """
    try:
        import yfinance as yf
        from watchlist_pnl import _yf_candidates
    except ImportError:
        return []
    # Drop entries that cannot possibly have a forward bar BEFORE hitting the
    # network. 1,069 of the 1,119 EU/JP/KR entries are stamped today, so fetching
    # the whole group would make 1,119 sequential requests to track 50.
    grp = grp[pd.to_datetime(grp["signal_date"]) < pd.Timestamp(date.today())]
    out = []
    for _, r in grp.iterrows():
        sd = pd.Timestamp(r["signal_date"])
        entry_px = r.get("price_at_signal")
        for t in _yf_candidates(mkt, str(r["symbol"])):
            try:
                h = yf.Ticker(t).history(start=(sd - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
                                         auto_adjust=False)
            except Exception:
                continue
            if h is None or h.empty or "Close" not in h.columns:
                continue
            c = pd.to_numeric(h["Close"], errors="coerce").dropna()
            if c.empty:
                continue
            idx = pd.to_datetime(c.index).tz_localize(None)
            after = c[idx >= sd]
            if after.empty:
                break                     # resolved, but no bar since the signal
            entry, basis = entry_px, "signal-price"
            if entry != entry or not entry:
                prior = c[idx <= sd]
                if prior.empty:
                    break
                entry, basis = float(prior.iloc[-1]), "panel-close"
            last_dt = pd.to_datetime(after.index[-1]).tz_localize(None)
            out.append({**r.to_dict(), "entry_used": entry, "basis": basis,
                        "as_of": last_dt, "benchmark": None,
                        "held_days": (last_dt - sd).days,
                        "ret_pct": (float(after.iloc[-1]) / entry - 1) * 100,
                        "xret_pct": np.nan})
            break
    return out


def report(min_days: int, fetch_missing: bool = False) -> int:
    if not LEDGER.exists():
        print("  no ledger yet — run --record first"); return 1
    led = pd.read_parquet(LEDGER)
    led["signal_date"] = pd.to_datetime(led["signal_date"])
    today = pd.Timestamp(date.today())
    led["days_held"] = (today - led["signal_date"]).dt.days

    ready = led[led["days_held"] >= min_days]
    print("=" * 82)
    print(f"  SIGNAL TRACKER — {len(led)} entries, {led['signal_date'].nunique()} signal dates")
    print(f"  {led['signal_date'].min():%Y-%m-%d} → {led['signal_date'].max():%Y-%m-%d}")
    print("=" * 82)
    if ready.empty:
        print(f"\n  Nothing has aged {min_days}+ days yet.")
        print("  That is the point: this measures the FUTURE, so it starts empty and")
        print("  earns its evidence. Come back after the horizon has actually passed.")
        print(f"\n  oldest entry is {int(led['days_held'].max())} days old")
        for f, n in led["filter"].value_counts().items():
            print(f"     {f:<18} {n:>4} tracked")
        return 0

    # Why an entry drops out matters as much as the return, so count the reasons
    # rather than silently `continue`. The old version skipped anything without a
    # price_at_signal and printed "no aged entries could be priced" — which was
    # true but useless: ALL 121 trackable entries were backfilled golden_cross
    # rows that never recorded an entry price, so the report was structurally
    # empty and looked like a data outage.
    rows, skipped = [], {"no_panel": 0, "not_in_panel": 0, "signal_after_panel": 0,
                         "no_entry_price": 0}
    bench_notes = []
    for mkt, grp in ready.groupby("market"):
        p = PANELS.get(mkt)
        if not p or not p.exists():
            # Until 2026-09-16 this branch caught EU/JP/KR and the comment here
            # said they "have no persisted panel". They do, and they are now in
            # PANELS, so those markets take the local path above. What still
            # lands here is a market with no partition at all (CN is held out
            # deliberately — see PANELS for why) or a panel missing from disk.
            # --fetch-missing pulls such rows from yfinance; off by default
            # because this is otherwise a pure read of local stores.
            if fetch_missing:
                got = _track_via_yf(grp, mkt, min_days)
                rows.extend(got)
                skipped["no_panel"] += len(grp) - len(got)
            else:
                skipped["no_panel"] += len(grp)
            continue
        px = _panel(p, columns=["Date", "Symbol", "Close"])
        px["Symbol"] = px["Symbol"].astype(str).str.upper()
        wide = px.pivot_table(index="Date", columns="Symbol", values="Close",
                              aggfunc="last").sort_index()
        panel_end = wide.index.max()
        # BENCHMARK, with a staleness check.
        #
        # NIFTYBEES is in the IN panel but stops updating: it is an ETF (ISIN
        # prefix INF) and the equity-only bhavcopy filter — added after an ETF
        # shipped as a golden-cross pick — leaves it behind the panel. Using it
        # regardless yields a benchmark window of <2 bars for every recent
        # signal, so `vs mkt` came out NaN for all 52 India entries with no
        # explanation. India therefore splices the real NIFTY 50 index onto it;
        # see india_benchmark() for the construction and for why the panel
        # median that used to sit here is gone.
        b = BENCH.get(mkt)
        bench, bench_name = None, None
        if mkt == "IN":
            try:
                bench, bench_name = india_benchmark(wide=wide), "NIFTYBEES+NIFTY50"
            except Exception as e:                            # noqa: BLE001
                bench_notes.append(f"IN: {b}+NIFTY50 splice unavailable "
                                   f"({type(e).__name__}: {str(e)[:60]}) — `vs mkt` is NaN")
        elif b in wide.columns:
            cand = wide[b].dropna()
            if len(cand) and cand.index.max() >= panel_end - pd.Timedelta(days=3):
                bench, bench_name = cand, b
        if bench is not None and bench.index.max() < panel_end - pd.Timedelta(days=3):
            bench_notes.append(
                f"{mkt}: {bench_name} last bar {bench.index.max():%Y-%m-%d} vs panel "
                f"{panel_end:%Y-%m-%d} — stale, `vs mkt` is NaN rather than substituted")
            bench, bench_name = None, None
        if bench is None and mkt != "IN":
            bench_notes.append(f"{mkt}: no usable benchmark ({b!r}) — `vs mkt` is NaN")
        for _, r in grp.iterrows():
            sym = resolve_symbol(r["symbol"], mkt, wide.columns)
            if sym is None:
                skipped["not_in_panel"] += 1
                continue
            # A signal stamped today has no forward price yet. That is not a
            # failure — it is what forward tracking means — but it must be
            # reported as "too early", never folded into the sample.
            if pd.Timestamp(r["signal_date"]) > panel_end:
                skipped["signal_after_panel"] += 1
                continue
            s = wide[sym].dropna()
            after = s[s.index >= r["signal_date"]]
            if after.empty:
                skipped["signal_after_panel"] += 1
                continue

            # ENTRY PRICE, with its provenance labelled — the watchlist model.
            #   signal-price = recorded when the filter fired (a record)
            #   panel-close  = the panel's close on the signal date (an estimate:
            #                  no fill, no slippage, and for a backfilled row it
            #                  is only close to what the brief actually quoted)
            entry, basis = r.get("price_at_signal"), "signal-price"
            if entry != entry or not entry:
                prior = s[s.index <= r["signal_date"]]
                if prior.empty:
                    skipped["no_entry_price"] += 1
                    continue
                entry, basis = float(prior.iloc[-1]), "panel-close"

            ret = (after.iloc[-1] / entry - 1) * 100
            bret = np.nan
            if bench is not None:
                ba = bench[bench.index >= r["signal_date"]].dropna()
                if len(ba) > 1:
                    bret = (ba.iloc[-1] / ba.iloc[0] - 1) * 100
            rows.append({**r.to_dict(), "entry_used": entry, "basis": basis,
                         "as_of": after.index[-1], "benchmark": bench_name,
                         "held_days": (after.index[-1] - pd.Timestamp(r["signal_date"])).days,
                         "ret_pct": ret,
                         "xret_pct": ret - bret if bret == bret else np.nan})

    if not rows:
        print("\n  no aged entries could be priced. Why:")
        for k, v in skipped.items():
            if v:
                print(f"     {k:<20} {v:>5}")
        return 0
    r = pd.DataFrame(rows)
    print(f"\n  TRACKED: {len(r)} of {len(ready)} entries, each from its own shortlist date\n")

    print(f"  {'filter':<18} {'market':<7} {'n':>4} {'med ret':>9} {'med vs mkt':>11} "
          f"{'win%':>6} {'med days':>9}  basis")
    print("  " + "-" * 78)
    for (f, m), g in r.groupby(["filter", "market"]):
        bases = "/".join(sorted(g["basis"].unique()))
        xr = g["xret_pct"].dropna()
        print(f"  {f:<18} {m:<7} {len(g):>4} {g['ret_pct'].median():>8.2f}% "
              f"{(xr.median() if len(xr) else float('nan')):>10.2f}% "
              f"{((xr > 0).mean()*100 if len(xr) else float('nan')):>5.0f}% "
              f"{g['held_days'].median():>8.0f}  {bases}")

    if bench_notes:
        print("\n  benchmark substitutions:")
        for n in bench_notes:
            print(f"     {n}")

    if any(skipped.values()):
        print(f"\n  NOT TRACKED — {sum(skipped.values())} entries, by reason:")
        labels = {
            "signal_after_panel": "signalled today / after the panel's last bar — too early, "
                                  "by design",
            "no_panel":           "market has no price panel (EU/JP/KR are not configured)",
            "not_in_panel":       "symbol absent from its market's panel",
            "no_entry_price":     "no entry price and no panel bar on the signal date",
        }
        for k, v in skipped.items():
            if v:
                print(f"     {v:>5}  {labels[k]}")

    n_est = int((r["basis"] == "panel-close").sum())
    if n_est:
        print(f"\n  ⚠ {n_est} of {len(r)} use a panel-close entry, not a recorded signal price.")
        print("    Backfilled rows never stored what the brief quoted, so their entry is")
        print("    the panel's close that day — close to it, but not the same number.")
    print("\n  'med vs mkt' is the number that matters — beating the index, not the")
    print("  sign of the raw return. n is small early on; treat it as a diary, not")
    print("  a result, until each filter has dozens of entries across many dates.")

    out = HERE / "reports" / "signal_tracking.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["symbol", "market", "filter", "detail", "score", "signal_date", "as_of",
            "held_days", "entry_used", "basis", "ret_pct", "xret_pct", "benchmark",
            "provenance", "source"]
    r[[c for c in cols if c in r.columns]].sort_values(
        ["market", "signal_date", "ret_pct"], ascending=[True, True, False]
    ).to_csv(out, index=False)
    print(f"\n  → {out.relative_to(HERE)}  ({len(r)} rows, one per shortlisted name)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Forward-track filter passes")
    ap.add_argument("--record", action="store_true", help="stamp today's passes")
    ap.add_argument("--report", action="store_true", help="performance since signal")
    ap.add_argument("--min-days", type=int, default=5)
    ap.add_argument("--fetch-missing", action="store_true",
                    help="track EU/JP/KR from yfinance (no local panel)")
    a = ap.parse_args()
    if a.record:
        return record()
    if a.report:
        return report(a.min_days, a.fetch_missing)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
