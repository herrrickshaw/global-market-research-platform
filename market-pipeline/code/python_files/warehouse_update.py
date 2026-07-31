#!/usr/bin/env python3
"""
warehouse_update.py — fold new bars from the daily stores into the deep panels.

THE PROBLEM THIS REMOVES
------------------------
Two price stores exist per market, with opposite strengths, and NOTHING merged
them:

    LFS ltm panel     10.5y deep   but 8-19 days STALE
    daily store       current      but ~36 bars (IN) / 5.1y (US)

Every analysis then had to pick, and picking wrong was silent. It went wrong
three separate times on 2026-07-21 alone:

  * A 3-year return computed from the India LMDB would have reported a 36-DAY
    move, because the LMDB is a rolling window and looks like a price history.
  * watchlist_pnl read BOTH entry and current price from the LFS panel, so
    anything added in the last 8 days had entry == ltp and printed "+0.0%" —
    which reads as "went nowhere", not "no time has passed".
  * Two US panels exist; one is an interrupted alphabetical collection missing
    CME/CMI, and a day of results ran on it.

The fix is not "remember which store to use". It is to make the deep panel
CURRENT, so there is one answer. History and freshness stop being a trade-off.

DESIGN
------
* APPEND-ONLY on (Symbol, Date). Existing bars are never rewritten — a
  corrected close from a vendor must not silently alter a price a past decision
  was made on. New dates only.
* IDEMPOTENT. Running twice adds nothing the second time.
* VERIFIED BEFORE WRITE. Row count must not fall and the last bar must not move
  backwards, or the write is refused. A merge that loses history is worse than a
  stale panel, because staleness is visible and truncation is not.
* ATOMIC. Writes to a temp file and renames, so an interrupted run cannot leave
  a half-written panel where a 10-year history used to be.

    warehouse_update.py                # update all configured markets
    warehouse_update.py --market IN
    warehouse_update.py --dry-run      # report what would change
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

HERE = Path(__file__).resolve().parent
# The WAREHOUSE replaces the monolithic ltm panels (2026-07-22). Year-partitioned
# zstd parquet: a daily update rewrites ONLY the current-year file (~8MB for IN)
# instead of a 68-184MB monolith, so each push uploads one small LFS object
# rather than re-uploading append-only history in full. Measured before the
# change: partitioning costs +7% on disk and cuts daily LFS growth ~10x.
WAREHOUSE = Path("/Users/umashankar/repos/global-market-data/warehouse/ohlcv")
PANELS = {
    "IN": WAREHOUSE / "IN",
    "US": WAREHOUSE / "US",
}
# Backups live OUTSIDE the dataset directory. A pre-write .bak kept beside the
# partition it backs up is read straight back as a second copy of that year:
# pyarrow discovers every file under the panel dir, not just year=*.parquet, and
# a .bak is itself valid parquet. That silently doubled every 2026 bar (IN
# 338,851 dup keys, US 1,207,003) until the merge guard tripped over its own
# dedup and froze the panel for four days.
BACKUP = WAREHOUSE.parent / "_backup" / "ohlcv"
COLS = ["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"]


def _read_panel(panel: Path) -> pd.DataFrame:
    """Read a panel from its year partitions ONLY.

    Never hand the directory to read_parquet — that pulls in whatever else is
    lying there (.bak, .tmp from an interrupted run) and double-counts bars.
    """
    parts = sorted(panel.glob("year=*.parquet"))
    return pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)


def _fresh_us() -> pd.DataFrame:
    """Per-ticker parquets from market_cache -> long frame."""
    try:
        import data_registry as R
    except Exception:
        return pd.DataFrame()
    out = []
    for f in R.OHLC_DIR.glob("*.parquet"):
        try:
            d = pd.read_parquet(f)
        except Exception:
            continue
        if d.empty or "Close" not in d.columns:
            continue
        d = d.reset_index()
        dcol = next((c for c in d.columns if str(c).lower() in ("date", "index")), None)
        if dcol is None:
            continue
        d = d.rename(columns={dcol: "Date"})
        d["Symbol"] = f.stem.upper()
        out.append(d[[c for c in COLS if c in d.columns]])
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def _fresh_in() -> pd.DataFrame:
    """bhavcopy LMDB -> long frame."""
    try:
        import bhavcopy_store as bs
    except Exception:
        return pd.DataFrame()
    out = []
    for sym in bs.symbols():
        try:
            d = bs.get(sym)
        except Exception:
            continue
        if d is None or d.empty or "Close" not in d.columns:
            continue
        d = d.reset_index()
        dcol = next((c for c in d.columns if str(c).lower() in ("date", "index")), None)
        if dcol is None:
            continue
        d = d.rename(columns={dcol: "Date"})
        d["Symbol"] = str(sym).upper()
        out.append(d[[c for c in COLS if c in d.columns]])
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


FRESH = {"US": _fresh_us, "IN": _fresh_in}

# Which exchange suffixes legitimately belong to each market. Membership is
# decided HERE, by an explicit table — not by ticker shape. "Carries a suffix"
# is not evidence of foreignness: tickers are supposed to be exchange-qualified,
# so `.NS` in the India panel is correct and `.SZ` is not, and only a table can
# tell those apart. When the panels move to fully exchange-qualified symbols,
# this map is the one place that changes.
_MARKET_SUFFIXES = {
    "IN": {"NS", "BO"},        # NSE, BSE
    "US": set(),               # US panel is bare today; add NYSE/NASDAQ codes here
}
# Bare (unsuffixed) symbols are what both panels hold today, so they are accepted
# as legacy. They are the reason the 2026-07-31 contamination was invisible: a
# foreign ticker among bare ones reads as an unfamiliar local smallcap.
_SUFFIX_RE = re.compile(r"\.([A-Za-z]{1,3})$")
# Above this share the fresh source is not merely dirty, it is the WRONG MARKET —
# drop-and-continue would quietly rebuild the panel from another country's data.
_FOREIGN_REFUSE_FRAC = 0.20


def _drop_foreign(market: str, new: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Strip tickers whose exchange does not belong to `market`.

    Returns None to refuse the merge outright when the fresh source looks like a
    different market entirely.
    """
    allowed = _MARKET_SUFFIXES.get(market)
    if allowed is None:
        return new
    syms = new["Symbol"].unique()
    bad = set()
    for s in syms:
        m = _SUFFIX_RE.search(str(s))
        if m and m.group(1).upper() not in allowed:
            bad.add(s)
    if not bad:
        return new
    frac = len(bad) / max(len(syms), 1)
    if frac > _FOREIGN_REFUSE_FRAC:
        print(f"  ❌ {market}: {len(bad):,}/{len(syms):,} fresh tickers ({frac:.0%}) carry an "
              f"exchange not in {sorted(allowed) or '{bare}'} — fresh source looks like the "
              f"wrong market, refusing")
        return None
    print(f"  ⚠️  {market}: dropped {len(bad):,} tickers from other exchanges "
          f"(e.g. {sorted(bad)[:5]})")
    return new[~new["Symbol"].isin(bad)]


def _write_years(market: str, panel: Path, frame: pd.DataFrame, years, dry: bool) -> int:
    """Rewrite exactly the year partitions named in `years`, atomically."""
    if dry:
        print(f"  {market}: dry-run, not written"); return 0
    for y in sorted(years):
        g = frame[frame["Date"].dt.year == y]
        part = panel / f"year={y}.parquet"
        bak_dir = BACKUP / panel.name
        bak_dir.mkdir(parents=True, exist_ok=True)
        bak = bak_dir / f"year={y}.parquet.bak"
        if part.exists():
            shutil.copy2(part, bak)
        tmp = part.with_suffix(".parquet.tmp")
        g.to_parquet(tmp, compression="zstd", index=False)
        tmp.replace(part)
        print(f"  ✅ {market}: year={y} written ({len(g):,} rows)")
    return 0


def update(market: str, dry: bool) -> int:
    panel = PANELS.get(market)
    if not panel or not panel.exists() or not any(panel.glob("year=*.parquet")):
        print(f"  {market}: no warehouse partitions at {panel}"); return 1

    old = _read_panel(panel)
    old["Date"] = pd.to_datetime(old["Date"])
    old["Symbol"] = old["Symbol"].astype(str).str.upper()
    old = old[COLS]

    # Dedup FIRST, so the guard's baseline is the set of distinct BARS. The
    # invariant that matters is "no bar disappears", not "no row disappears" —
    # only the former is history loss, and conflating them is what froze this
    # panel for four days: a .bak kept inside the dataset dir was read back as a
    # second copy of 2026, the merge's dedup correctly collapsed it, and the
    # row-count check read that collapse as truncation and refused every run.
    # The .bak is now written outside the panel and _read_panel() globs only
    # year=*.parquet, so this should find nothing; it stays as a cheap residual
    # defense, and any non-zero count here means a new writer is double-feeding.
    raw_rows = len(old)
    dup_mask = old.duplicated(subset=["Symbol", "Date"], keep="first")
    dup_years = set(old.loc[dup_mask, "Date"].dt.year.unique())
    old = old[~dup_mask].reset_index(drop=True)
    deduped = raw_rows - len(old)

    last_old = old["Date"].max()
    print(f"  {market} panel: {len(old):,} rows, {old['Symbol'].nunique():,} symbols, "
          f"last bar {last_old.date()}")
    if deduped:
        print(f"  {market}: {deduped:,} duplicate (Symbol, Date) rows collapsed "
              f"(panel held {raw_rows:,}) — years {sorted(dup_years)}")

    fresh = FRESH[market]()
    if fresh.empty:
        print(f"  {market}: no fresh data available — nothing to do"); return 0
    fresh["Date"] = pd.to_datetime(fresh["Date"])
    fresh["Symbol"] = fresh["Symbol"].astype(str).str.upper()
    print(f"  {market} fresh : {len(fresh):,} rows, {fresh['Symbol'].nunique():,} symbols, "
          f"last bar {fresh['Date'].max().date()}")

    # STRICTLY NEWER DATES ONLY. Re-importing an overlapping date would let a
    # vendor's revised close overwrite the price a past decision was recorded
    # against, silently changing history.
    new = fresh[fresh["Date"] > last_old].copy()
    if not new.empty:
        new = _drop_foreign(market, new)
        if new is None:
            return 1
    if new.empty:
        if deduped:
            # Repair even with nothing to append, or the duplicates only ever get
            # cleaned by luck — when fresh bars happen to land in the same year.
            print(f"  {market}: 0 new bars, writing duplicate repair only")
            return _write_years(market, panel, old, dup_years, dry)
        print(f"  {market}: already current — 0 new bars"); return 0

    for c in COLS:
        if c not in new.columns:
            new[c] = pd.NA
    new = new[COLS]
    # Match the panel's dtypes so the concat does not silently widen float32 to
    # float64 and double the file.
    for c in ("Open", "High", "Low", "Close"):
        if c in old.columns:
            new[c] = new[c].astype(old[c].dtype, errors="ignore")

    merged = pd.concat([old[COLS], new], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Symbol", "Date"], keep="first")
    merged = merged.sort_values(["Symbol", "Date"]).reset_index(drop=True)

    added = len(merged) - len(old)
    print(f"  {market}: +{added:,} bars across {new['Symbol'].nunique():,} symbols "
          f"({last_old.date()} -> {merged['Date'].max().date()})")

    # ── refuse a write that loses anything ────────────────────────────────────
    if len(merged) < len(old):
        print(f"  ❌ {market}: merge LOST rows ({len(old):,} -> {len(merged):,}) — refusing")
        return 1
    if merged["Date"].max() < last_old:
        print(f"  ❌ {market}: last bar moved BACKWARDS — refusing"); return 1
    lost = set(old["Symbol"]) - set(merged["Symbol"])
    if lost:
        print(f"  ❌ {market}: {len(lost)} symbols vanished — refusing"); return 1

    # Write ONLY the partitions that changed — in practice the current year.
    # Closed years never change under the strictly-newer-dates rule, so a daily
    # run touches one ~8MB file, which is the entire point of partitioning.
    # Years the dedup touched must be included too: they changed on disk even
    # though no fresh bar reaches them, and skipping them would leave the
    # duplicates in place to be re-collapsed on every future run.
    changed_years = set(new["Date"].dt.year.unique()) | dup_years
    return _write_years(market, panel, merged, changed_years, dry)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fold fresh bars into the deep panels")
    ap.add_argument("--market", choices=list(PANELS))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rc = 0
    for m in ([a.market] if a.market else list(PANELS)):
        rc |= update(m, a.dry_run)
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
