#!/usr/bin/env python3
"""
filter_watchlists.py — one independent membership track per (filter, market),
generalizing the combined 3-tier buy/watch/hold/sold/evicted system
(watchlist.csv / watchlist_digest.py) into single-criterion lists: "which
names currently pass Piotroski", "which currently pass the EMA trend
condition", "which currently show a Darvas breakout" — tracked separately so
each filter's own real-world performance can be measured on its own, not
blended into one combined recommendation.

DESIGN CHOICE: one CSV (`filter_watchlist.csv`) with a `filter` column, not N
separate physical files. Functionally this gives literally-separate
membership tracks per filter (a name's darvas membership evicts/purges
completely independently of its piotroski membership, even for the same
symbol+market) while sharing one state-machine implementation instead of
duplicating add/evict/purge logic N times. `--export-filter NAME` writes a
single-filter CSV if a standalone file is ever wanted.

FILTER REGISTRY — each filter declares exactly which markets it covers.
🔴 Coverage is NOT uniform across markets and this script does not pretend
otherwise — check FILTERS below and the per-run coverage report before
trusting a market/filter combination that isn't listed:
  darvas       — IN, US, KR, JP, EU (Darvas_Signal == BREAKOUT_BUY; universal
                 column across every market's scan)
  ema          — US, KR, JP, EU (Above_EMA50 & EMA50_Rising; India's scan
                 sheet has NO EMA columns at all, confirmed 2026-08-23 — do
                 not add IN here without also adding real EMA computation
                 to indian_full_scan's All_Stocks output)
  piotroski    — IN only (Piotroski_Score column exists ONLY in India's scan
                 sheet, confirmed 2026-08-23; threshold >=7 matches the
                 existing convention at build_mailer.py:227)
  golden_cross — IN, US, KR, JP, EU (GC_Signal == GOLDEN_CROSS; rare, expect
                 single-digit daily counts)

STATE MACHINE per (symbol, market, filter) — same session-based convention as
the existing watchlist (EVICT_SESSIONS=5, PURGE_SESSIONS=15, matching
watchlist_digest.py's PURGE_SELL_SESSIONS=15):
  not listed, passes today          -> ADD (status=active, miss_count=0)
  active, passes today              -> miss_count resets to 0, last_pass updated
  active, does NOT pass today       -> miss_count += 1
  active, miss_count > 5            -> EVICT (status=evicted, evicted_date=today)
  evicted, passes again             -> RE-ADD as active (miss_count=0) -- a
                                        name is free to re-qualify; eviction
                                        is not a permanent ban
  evicted, sessions since evicted_date > 15  -> PURGE (archived, dropped from
                                        the active file)

    filter_watchlists.py --record              # scan today's latest xlsx per market, update memberships
    filter_watchlists.py --report               # performance since entry_date, per filter x market
    filter_watchlists.py --report --min-days 5
    filter_watchlists.py --export-filter piotroski
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import signal_tracker as ST  # noqa: E402 -- reuse SCAN_DIRS, PANELS, BENCH, _panel
import validation_registry as VR  # noqa: E402 -- MECE backtest-status partition, 2026-08-23

OUT = HERE / "filter_watchlist.csv"
PURGED_ARCHIVE = HERE / "filter_watchlist_purged.csv"
EVICT_SESSIONS = 5
PURGE_SESSIONS = 15

SYM_COLS = {"IN": "Symbol", "US": "Symbol", "EU": "Symbol", "KR": "Code", "JP": "Code"}
PRICE_COLS = {"IN": "LTP", "US": "LTP", "EU": "LTP", "KR": "LTP_KRW", "JP": "LTP_JPY"}


def _darvas_pass(s: pd.DataFrame) -> pd.Series:
    return s.get("Darvas_Signal", pd.Series("", index=s.index)) == "BREAKOUT_BUY"


def _ema_pass(s: pd.DataFrame) -> pd.Series:
    return (s.get("Above_EMA50", pd.Series(0, index=s.index)).fillna(0).astype(bool)
           & s.get("EMA50_Rising", pd.Series(0, index=s.index)).fillna(0).astype(bool))


def _piotroski_pass(s: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(s.get("Piotroski_Score", pd.Series(np.nan, index=s.index)),
                         errors="coerce") >= 7


def _golden_cross_pass(s: pd.DataFrame) -> pd.Series:
    return s.get("GC_Signal", pd.Series("", index=s.index)) == "GOLDEN_CROSS"


FILTERS = {
    "darvas":       {"markets": ["IN", "US", "KR", "JP", "EU"], "pass_fn": _darvas_pass},
    "ema":          {"markets": ["US", "KR", "JP", "EU"],        "pass_fn": _ema_pass},
    "piotroski":    {"markets": ["IN"],                          "pass_fn": _piotroski_pass},
    "golden_cross": {"markets": ["IN", "US", "KR", "JP", "EU"], "pass_fn": _golden_cross_pass},
}


def _latest_scan(mkt: str) -> pd.DataFrame | None:
    d, pat = ST.SCAN_DIRS[mkt]
    f = ST._latest(d, pat)
    if not f:
        return None
    try:
        s = pd.read_excel(f, "All_Stocks")
    except Exception:
        return None
    s.attrs["source_file"] = f.name
    return s


def _load() -> pd.DataFrame:
    if OUT.exists():
        d = pd.read_csv(OUT)
        for c in ("entry_date", "last_pass_date", "evicted_date"):
            if c in d.columns:
                d[c] = pd.to_datetime(d[c], errors="coerce")
        return d
    return pd.DataFrame(columns=["symbol", "market", "filter", "status", "entry_date",
                                 "entry_price", "last_pass_date", "miss_count",
                                 "evicted_date", "last_price"])


def update_membership(wl: pd.DataFrame, filt: str, mkt: str, passing: set,
                      prices: dict, today: pd.Timestamp,
                      evict_sessions: int = EVICT_SESSIONS,
                      purge_sessions: int = PURGE_SESSIONS) -> tuple[pd.DataFrame, dict]:
    """Pure state-transition function, factored out of record() so the
    add/evict/purge boundary conditions are directly unit-testable against a
    synthetic wl + a synthetic `passing` set, without needing a real scan
    xlsx on disk. See test_filter_watchlists.py.

    `wl` is mutated via .loc/.at on a copy and returned; `passing` is the set
    of upper-cased symbols that pass `filt` in `mkt` as of `today`; `prices`
    maps symbol -> last-traded price (may be NaN/missing, handled)."""
    wl = wl.copy()
    stats = {"added": 0, "revived": 0, "still_passing": 0, "missed": 0,
            "evicted": 0, "purged": 0}

    existing = wl[(wl["filter"] == filt) & (wl["market"] == mkt)]
    existing_syms = set(existing["symbol"])

    for sym in passing:
        px = prices.get(sym)
        idx = wl[(wl["filter"] == filt) & (wl["market"] == mkt)
                & (wl["symbol"] == sym)].index
        if len(idx) == 0:
            wl = pd.concat([wl, pd.DataFrame([{
                "symbol": sym, "market": mkt, "filter": filt, "status": "active",
                "entry_date": today, "entry_price": px, "last_pass_date": today,
                "miss_count": 0, "evicted_date": pd.NaT, "last_price": px,
            }])], ignore_index=True)
            stats["added"] += 1
        else:
            i = idx[0]
            was_evicted = wl.at[i, "status"] == "evicted"
            wl.loc[i, ["status", "last_pass_date", "miss_count", "last_price"]] = \
                ["active", today, 0, px]
            if was_evicted:
                wl.at[i, "evicted_date"] = pd.NaT
                stats["revived"] += 1
            else:
                stats["still_passing"] += 1

    for sym in existing_syms - passing:
        idx = wl[(wl["filter"] == filt) & (wl["market"] == mkt)
                & (wl["symbol"] == sym)].index
        if len(idx) == 0:
            continue
        i = idx[0]
        if wl.at[i, "status"] == "evicted":
            continue  # already evicted, handled by the purge pass below
        wl.at[i, "miss_count"] = int(wl.at[i, "miss_count"] or 0) + 1
        stats["missed"] += 1
        if wl.at[i, "miss_count"] > evict_sessions:
            wl.at[i, "status"] = "evicted"
            wl.at[i, "evicted_date"] = today
            stats["evicted"] += 1

    # purge pass, scoped to this (filt, mkt) only -- record() calls this once
    # per (filt, mkt) pair, so a global purge here would re-scan rows already
    # handled by an earlier iteration; harmless (idempotent) but wasteful, so
    # the filter is kept.
    if len(wl):
        # pd.concat with an empty/all-NA starting frame can leave evicted_date
        # as float64 (all-NaN) instead of datetime -- coerce explicitly before
        # date arithmetic rather than relying on concat's dtype inference.
        wl["evicted_date"] = pd.to_datetime(wl["evicted_date"], errors="coerce")
        ev = (wl["filter"] == filt) & (wl["market"] == mkt) & (wl["status"] == "evicted")
        stale = ev & wl["evicted_date"].notna() & \
            ((today - wl["evicted_date"]).dt.days > purge_sessions)
        if stale.any():
            purged_rows = wl[stale]
            purged_rows.to_csv(PURGED_ARCHIVE, mode="a", index=False,
                               header=not PURGED_ARCHIVE.exists())
            wl = wl[~stale]
            stats["purged"] = int(stale.sum())

    return wl, stats


def record() -> int:
    wl = _load()
    today = pd.Timestamp(date.today())
    scans = {}  # market -> All_Stocks df, fetched once even though multiple filters share a market
    coverage = []
    totals = {"added": 0, "revived": 0, "still_passing": 0, "missed": 0,
             "evicted": 0, "purged": 0}

    for filt, cfg in FILTERS.items():
        for mkt in cfg["markets"]:
            if mkt not in scans:
                scans[mkt] = _latest_scan(mkt)
            s = scans[mkt]
            if s is None:
                coverage.append((filt, mkt, "NO SCAN FILE FOUND"))
                continue
            sym_col, price_col = SYM_COLS[mkt], PRICE_COLS[mkt]
            if sym_col not in s.columns:
                coverage.append((filt, mkt, f"missing symbol column {sym_col}"))
                continue
            try:
                pass_mask = cfg["pass_fn"](s)
            except Exception as e:
                coverage.append((filt, mkt, f"pass_fn error: {e}"))
                continue
            passing = set(s.loc[pass_mask.fillna(False), sym_col].astype(str).str.upper())
            prices = dict(zip(s[sym_col].astype(str).str.upper(),
                              pd.to_numeric(s.get(price_col), errors="coerce")))
            coverage.append((filt, mkt, f"{len(passing)} passing / {len(s)} scanned"
                            f" ({s.attrs.get('source_file', '?')})"))

            wl, stats = update_membership(wl, filt, mkt, passing, prices, today)
            for k in totals:
                totals[k] += stats[k]

    wl["validation_status"] = [VR.status_of(f, m).status for f, m in zip(wl["filter"], wl["market"])]
    wl.to_csv(OUT, index=False)

    print("  coverage:")
    for filt, mkt, msg in coverage:
        print(f"    {filt:<13} {mkt:<3}  {msg}")
    print(f"\n  added={totals['added']} revived={totals['revived']} "
          f"still_passing={totals['still_passing']} missed={totals['missed']} "
          f"evicted={totals['evicted']} purged={totals['purged']}")
    print(f"  -> {OUT}  ({len(wl)} active+evicted rows)")
    return 0


def report(min_days: int = 5) -> int:
    wl = _load()
    if wl.empty:
        print("  no filter watchlist yet -- run --record first"); return 1
    today = pd.Timestamp(date.today())
    wl["days_held"] = (today - wl["entry_date"]).dt.days
    ready = wl[(wl["status"].isin(["active", "evicted"])) & (wl["days_held"] >= min_days)
              & wl["entry_price"].notna() & (wl["entry_price"] > 0)]

    print("=" * 88)
    print(f"  FILTER WATCHLIST PERFORMANCE — {len(wl)} tracked (active+evicted), "
          f"{len(ready)} aged >= {min_days}d with a priced entry")
    print("=" * 88)

    validated_pairs = [k for k, v in VR.REGISTRY.items() if v.status == VR.VALIDATED_EDGE]
    live = wl[wl["status"] == "active"]
    print(f"\n  VALIDATED EDGE (act on these — {len(validated_pairs)} of "
          f"{len(VR.REGISTRY)} filter/market pairs backtested positive):")
    for filt, mkt in validated_pairs:
        v = VR.status_of(filt, mkt)
        names = sorted(live[(live["filter"] == filt) & (live["market"] == mkt)]["symbol"])
        print(f"    {filt}/{mkt}: {v.evidence}")
        print(f"      currently active ({len(names)}): {', '.join(names) if names else '(none)'}")

    rows = []
    skipped = {"no_panel": 0, "not_in_panel": 0, "too_early": 0}
    for (filt, mkt), grp in ready.groupby(["filter", "market"]):
        p = ST.PANELS.get(mkt)
        if not p or not p.exists():
            skipped["no_panel"] += len(grp)
            continue
        px = ST._panel(p, columns=["Date", "Symbol", "Close"])
        px["Symbol"] = px["Symbol"].astype(str).str.upper()
        wide = px.pivot_table(index="Date", columns="Symbol", values="Close",
                              aggfunc="last").sort_index()
        panel_end = wide.index.max()
        for _, r in grp.iterrows():
            sym = r["symbol"]
            if sym not in wide.columns:
                skipped["not_in_panel"] += 1
                continue
            s = wide[sym].dropna()
            after = s[s.index >= r["entry_date"]]
            if after.empty:
                # entered today (or later than the panel's last bar) -- there
                # is no forward price yet, by construction. Not a failure;
                # see signal_tracker.py's identical convention/comment.
                skipped["too_early"] += 1
                continue
            last_px = float(after.iloc[-1])
            ret = (last_px / r["entry_price"] - 1) * 100
            rows.append({"filter": filt, "market": mkt, "symbol": sym,
                        "status": r["status"], "ret_pct": ret,
                        "days_held": r["days_held"]})

    d = pd.DataFrame(rows)
    skip_msg = ", ".join(f"{k}={v}" for k, v in skipped.items() if v) or "none"
    if d.empty:
        print(f"\n  nothing scoreable yet — skipped: {skip_msg}")
        if skipped["too_early"] and not skipped["no_panel"] and not skipped["not_in_panel"]:
            print(f"  (all {skipped['too_early']} skips are 'too_early' — everything was "
                  f"entered today/after the panel's last bar. This is expected on the "
                  f"first --record run; re-check after the price panel advances.)")
        return 0

    print(f"\n  {'filter':<13}{'market':<7}{'n':>5}{'med ret%':>10}{'win%':>7}{'med days':>10}  status")
    print(f"  {'-'*55}")
    for (filt, mkt), g in d.groupby(["filter", "market"]):
        status = VR.status_of(filt, mkt).status
        print(f"  {filt:<13}{mkt:<7}{len(g):>5}{g.ret_pct.median():>10.2f}"
              f"{(g.ret_pct>0).mean()*100:>6.0f}%{g.days_held.median():>10.0f}  {status}")
    print(f"\n  skipped: {skip_msg}")
    return 0


def export_filter(name: str) -> int:
    wl = _load()
    sub = wl[wl["filter"] == name]
    if sub.empty:
        print(f"  no rows for filter={name!r}"); return 1
    out = HERE / f"filter_watchlist_{name}.csv"
    sub.to_csv(out, index=False)
    print(f"  -> {out}  ({len(sub)} rows)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--min-days", type=int, default=5)
    ap.add_argument("--export-filter", type=str, default=None)
    a = ap.parse_args()
    if a.export_filter:
        return export_filter(a.export_filter)
    if a.record:
        return record()
    if a.report:
        return report(a.min_days)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
