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
    # 🔴 JP/KR/EU WERE NEVER HERE, and that — not any failure — is why those three
    # panels sat frozen at 2026-07-22/23 for ten days. There was no error to find:
    # no scheduled process had ever folded a bar into them. Their file mtimes are
    # all 23 Jul because a one-off backfill built them and nothing succeeded it.
    #
    # What made it invisible: daily_research.sh DOES scan all three every morning,
    # and [R13]'s ledger reports them "0d ok [fresh]" — but that ledger tracks the
    # SCAN SNAPSHOTS (market_ingest.py reads japan_scan/*.xlsx), a different asset
    # from these OHLCV panels. A green light on one store masked a ten-day-stale
    # other, which is the same failure shape as zone_regime.json's empty `asof`.
    "JP": WAREHOUSE / "JP",
    "KR": WAREHOUSE / "KR",
    "EU": WAREHOUSE / "EU",
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
    """India bhavcopy bars -> long frame.

    READS THE INDIA SEED PARQUET, NOT THE SHARED LMDB — this is the whole point.
    bhavcopy_store's LMDB is not an India store. `build()` called with no `hist`
    deliberately globs every cleaned_long_<MKT>.parquet into one store ("ingest
    every market seed present"), which is what screener_kit does; while
    bhavcopy_history rebuilds the same store from an India-only dict. Both paths
    rmtree it first, so the store's universe is simply whoever wrote last.

    That stayed invisible while no per-market seeds existed. On 2026-07-31 a new
    weekly-extended-scan job began calling screener_kit.update() per market,
    which materialised 15 seeds and rebuilt the store global (23,868 symbols) —
    and this function, believing it was reading India, folded 8,802 Shenzhen,
    Shanghai, Taiwan, Sydney, HK and Singapore bars into the INDIA panel.

    bs.CLEANED is India by construction (screener_kit._seed_name("IN") is exactly
    "cleaned_long.parquet"), so reading it removes the ambiguity at source rather
    than filtering after the fact. It is also cheaper: this function scans every
    symbol regardless, so the LMDB's keyed access never bought anything here.
    """
    try:
        import bhavcopy_store as bs
    except Exception:
        return pd.DataFrame()

    if bs.CLEANED.exists():
        d = pd.read_parquet(bs.CLEANED)
        if not d.empty and {"Symbol", "Date", "Close"} <= set(d.columns):
            d["Date"] = pd.to_datetime(d["Date"])
            d["Symbol"] = d["Symbol"].astype(str).str.upper()
            return d[[c for c in COLS if c in d.columns]]
        print(f"  IN: {bs.CLEANED.name} unusable — falling back to the LMDB")
    else:
        print(f"  IN: {bs.CLEANED.name} missing — falling back to the LMDB")

    # Fallback only. The store may hold any market, so the result is passed
    # through the same exchange allowlist the merge uses.
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
    if not out:
        return pd.DataFrame()
    df = pd.concat(out, ignore_index=True)
    kept = _drop_foreign("IN", df)
    return pd.DataFrame() if kept is None else kept


def _fresh_cached(name: str):
    """Fold from ohlcv_cache's per-market long panel.

    The JP/KR/EU scans already download real OHLCV to compute EMA50/200DMA and
    already persist it here — ohlcv_JAPAN/KOREA/EUROPE.parquet were current to
    2026-07-31 while the warehouse panels sat at 07-22/23. Nothing was missing;
    nothing was wired.

    Deliberately NOT sourced from the scan workbooks, which is the other obvious
    candidate and is wrong: japan_scan/*.xlsx carries LTP + derived metrics and no
    Open/High/Low/Volume at all, so folding those would invent three-quarters of
    every bar. A Close-only row that LOOKS like a bar is worse here than no row.
    """
    def _f() -> pd.DataFrame:
        try:
            import ohlcv_cache as _oc
            cdir = _oc.CACHE_DIR
        except Exception:
            cdir = HERE.parent.parent / "data" / "bhavcopy_cache"
        f = Path(cdir) / f"ohlcv_{name}.parquet"
        if not f.exists():
            return pd.DataFrame()
        try:
            d = pd.read_parquet(f)
        except Exception:
            return pd.DataFrame()
        if d.empty or not {"Date", "Symbol", "Close"} <= set(d.columns):
            return pd.DataFrame()
        return d[[c for c in COLS if c in d.columns]]
    return _f


FRESH = {"US": _fresh_us, "IN": _fresh_in,
         "JP": _fresh_cached("JAPAN"),
         "KR": _fresh_cached("KOREA"),
         "EU": _fresh_cached("EUROPE")}

# Which exchange suffixes legitimately belong to each market. Membership is
# decided HERE, by an explicit table — not by ticker shape. "Carries a suffix"
# is not evidence of foreignness: tickers are supposed to be exchange-qualified,
# so `.NS` in the India panel is correct and `.SZ` is not, and only a table can
# tell those apart. When the panels move to fully exchange-qualified symbols,
# this map is the one place that changes.
_MARKET_SUFFIXES = {
    # Membership is decided by an exchange ALLOWLIST, never by ticker shape.
    # JP is .T; KR is .KS (KOSPI) and .KQ (KOSDAQ); EU is the 19 European
    # exchange suffixes already enumerated in CLAUDE.md — without the full set a
    # legitimate .VI or .WA name reads as foreign and gets stripped from its own
    # market's fold.
    "JP": {"T"},
    "KR": {"KS", "KQ"},
    # The last five (Istanbul, Budapest, Prague, Tallinn, Vilnius) are NOT in
    # CLAUDE.md's 17-exchange list, but they ARE in the EU panel — 8/4/2/1/1
    # symbols. Enforcing the documented list instead of the actual one would have
    # dropped their fresh bars while every other EU name updated, freezing 16
    # symbols mid-panel: a partial staleness that no row-count guard can see and
    # nothing downstream would report. The allowlist has to describe the panel
    # that exists, not the one the docs describe.
    "EU": {"DE", "F", "L", "PA", "MI", "MC", "ST", "HE", "CO", "OL",
           "AS", "BR", "LS", "IR", "SW", "WA", "AT", "VI",
           "IS", "BD", "PR", "TL", "VS"},
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
