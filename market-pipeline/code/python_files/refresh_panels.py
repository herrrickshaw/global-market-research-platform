#!/usr/bin/env python3
"""
refresh_panels.py — incremental refresh of the gmd warehouse OHLCV panels.

Extends warehouse/ohlcv/<MKT> from each panel's max date to today for the
panel's own symbol universe, via yf.download batches. Unblocks the pending
signal scores that accumulate whenever a panel goes stale (JP/KR/EU ended
2026-07-01/02 with ~2,000 scores waiting).

Semantics: increments are fetched auto_adjust=True — the SAME convention the
panels were collected under. A symbol that split between the panel's last
assembly and today will therefore carry a residual break at its ex-date (old
rows in the old adjusted base). That is expected and handled downstream:
ALWAYS re-run price_adjuster_global.py after a refresh (staleness trigger in
claims.yaml `non-india-panels-already-adjusted`).

    refresh_panels.py --markets JP KR EU
    refresh_panels.py --markets US            # any warehouse market except IN
                                              # (IN comes from bhavcopy, not yf)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd
import yfinance as yf
import warehouse_paths as _wh

WH = _wh.root()
BATCH = 50
COLS = ["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"]


def _invalid(df):
    """Boolean mask of structurally impossible bars.

    🔴 2026-08-20. The only check here was `dropna(subset=["Close"])`, so a
    yfinance PARTIAL RESPONSE — Close populated, Open/High/Low all 0.00 — went
    straight into the panel. Measured on the EU panel: 473 of the 1,600 rows
    written for 2026-08-18 look like

        AAL.L   Open 0.00  High 0.00  Low 0.00  Close 3831.00  Volume 4536

    The Close is real; the rest is a hole. That silently corrupts everything
    derived from the range — Darvas box_top/box_bottom, ATR, true range — and
    makes `Close > High` trivially true for every one of them. Against a
    baseline of 1-3 bad rows a day across the whole panel, this was a single
    bad ingest, not drift.

    A bar is rejected rather than repaired: there is no honest way to infer a
    high and low that were never delivered, and a fabricated range is worse
    than a missing bar because nothing downstream can tell it was invented.
    """
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    return (
        c.isna() | (c <= 0)
        | h.isna() | l.isna() | (h <= 0) | (l <= 0)
        | (h < l) | (c > h) | (c < l)
        | ((o.notna()) & (o > 0) & ((o > h) | (o < l)))
    )


def refresh(market: str, backfill_days: int = 0) -> None:
    con = duckdb.connect()
    src = f"{WH}/ohlcv/{market}/*.parquet"
    syms, dmax = con.execute(
        f"SELECT list(DISTINCT Symbol), max(Date) FROM read_parquet('{src}')"
    ).fetchone()
    dmax = pd.Timestamp(dmax)
    # --backfill-days re-fetches a window that is ALREADY covered, so evicted
    # invalid bars can be refilled. Without it, dropping a bad row just leaves a
    # hole: the normal path only ever fetches forward from dmax+1.
    if backfill_days:
        cutoff = dmax - pd.Timedelta(days=backfill_days)
        start = cutoff.strftime("%Y-%m-%d")
        print(f"  {market}: {len(syms)} symbols, panel ends {dmax.date()}, "
              f"BACKFILL re-fetching {start} -> today")
    else:
        cutoff = dmax
        start = (dmax + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        print(
            f"  {market}: {len(syms)} symbols, panel ends {dmax.date()}, "
            f"fetching {start} -> today"
        )
        if dmax >= pd.Timestamp.now().normalize() - pd.Timedelta(days=1):
            print(f"  {market}: already fresh")
            return

    frames = []
    for i in range(0, len(syms), BATCH):
        batch = syms[i : i + BATCH]
        try:
            d = yf.download(
                batch,
                start=start,
                auto_adjust=True,
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception as e:
            print(f"    batch {i // BATCH}: download failed ({e}) — skipped")
            continue
        if d is None or d.empty:
            continue
        for s in batch:
            try:
                sub = d[s].dropna(subset=["Close"])
            except KeyError:
                continue
            if sub.empty:
                continue
            sub = sub.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
            sub["Symbol"] = s
            frames.append(sub)
        if (i // BATCH) % 10 == 0:
            print(f"    …batch {i // BATCH + 1}/{(len(syms) - 1) // BATCH + 1}")

    if not frames:
        print(f"  {market}: nothing fetched")
        return
    new = pd.concat(frames, ignore_index=True)
    new["Date"] = pd.to_datetime(new["Date"]).dt.tz_localize(None)
    new = new[new["Date"] > cutoff][COLS]

    # Reject structurally impossible bars BEFORE they reach the panel, and say
    # how many — a silent drop here would be the same class of problem as the
    # silent write it replaces.
    bad = _invalid(new)
    if bad.any():
        by_date = new.loc[bad].groupby(new.loc[bad, "Date"].dt.date).size()
        print(f"  {market}: ⚠ dropped {int(bad.sum()):,} structurally invalid "
              f"bar(s) of {len(new):,} fetched "
              f"(zero/absent high-low, or close outside its own range)")
        for d, n in by_date.sort_index().items():
            print(f"      {d}: {n:,}")
        new = new[~bad]
    if new.empty:
        print(f"  {market}: nothing valid to write")
        return
    print(
        f"  {market}: {len(new):,} new rows "
        f"({new.Date.min().date()} -> {new.Date.max().date()})"
    )

    # merge into year partitions atomically, dedup on (Symbol, Date)
    for y, g in new.groupby(new["Date"].dt.year):
        p = WH / "ohlcv" / market / f"year={y}.parquet"
        if p.exists():
            old = pd.read_parquet(p)
            old["Date"] = pd.to_datetime(old["Date"])
            # 🔴 CORRUPTION WAS PERMANENT. `keep="first"` with `old` concatenated
            # first means an existing row always wins, which is right for
            # adjustment stability — increments are fetched auto_adjust=True and
            # re-fetching a valid bar would churn its adjusted base — but it also
            # meant a bad row could NEVER be corrected by a later fetch. The 473
            # zero-range EU bars from 2026-08-18 would have survived every future
            # refresh.
            #
            # So old rows keep priority, EXCEPT the structurally invalid ones:
            # those are evicted here, which makes them eligible to be replaced by
            # a good fetch instead of shadowing it forever. Valid rows are
            # untouched, so adjustment semantics are unchanged.
            old_bad = _invalid(old)
            if old_bad.any():
                print(f"    year={y}: evicting {int(old_bad.sum()):,} invalid "
                      f"existing row(s) so a good fetch can replace them")
                old = old[~old_bad]
            merged = pd.concat([old, g], ignore_index=True).drop_duplicates(
                subset=["Symbol", "Date"], keep="first"
            )
        else:
            merged = g
        tmp = p.with_suffix(".parquet.tmp")
        merged.sort_values(["Symbol", "Date"]).to_parquet(
            tmp, compression="zstd", index=False
        )
        tmp.replace(p)
        print(f"    year={y}: {len(merged):,} rows")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", nargs="+", required=True)
    ap.add_argument("--backfill-days", type=int, default=0,
                    help="re-fetch this many days already covered, to refill "
                         "bars evicted as structurally invalid")
    a = ap.parse_args()
    for m in a.markets:
        if m == "IN":
            print("  IN is bhavcopy-fed (daily_pipeline) — skipping")
            continue
        refresh(m, a.backfill_days)
    print(
        "NOTE: re-run price_adjuster_global.py for refreshed markets "
        "(residual-split staleness trigger)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
