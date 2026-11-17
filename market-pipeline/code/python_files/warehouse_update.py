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
# 🔴 RESOLVED, NOT HARDCODED — this line was an absolute path until 2026-08-17.
# The repo-local warehouse was migrated to the cloud store on 2026-08-14
# (~/scripts/market_paths.py). This file and price_adjuster.py were the two
# consumers missed in that sweep, so steps [7] and [7b] failed three days later
# against a directory that no longer existed. resolve() materialises from
# Dropbox when the local copy is cold, and raises with the exact fixing command
# instead of returning an empty directory — an empty glob is precisely how this
# presented ("no warehouse partitions at ..."), and it said nothing about why.
#
# Deliberately NO fallback to the old repo path. A fallback would silently pick
# up whatever stale copy happened to be lying there and let the panels diverge
# from the canonical store, which is a far worse failure than stopping.
sys.path.insert(0, str(Path.home() / "scripts"))
from market_paths import resolve as _resolve  # noqa: E402

WAREHOUSE = _resolve("ohlcv")
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

# ── split re-adjustment ──────────────────────────────────────────────────────
# THE ONE EXCEPTION TO APPEND-ONLY, and it exists because append-only is exactly
# what breaks on a split. Fresh bars arrive from the vendor already adjusted for
# any split that has happened; stored bars are on the OLD basis and nothing was
# re-adjusting them. The panel then holds one symbol on two different price
# bases, joined at the split date, and every window that straddles that date
# reports the split ratio as if it were a return.
#
# Found 2026-08-25 by trailing_returns.py, which flagged CISS +4,293.94% over
# one week. CISS did a 1-for-40 reverse split on 2026-08-19: the panel's
# 0.0685 close on 08-18 sits directly beside a 3.09 close on 08-19. The real
# move was +12.8%. Same shape for ELAB (1-for-10, printed +646.85%) and VCIG
# (1-for-15, printed +1,062.43%). A sweep of the last 45 days found 177 US and
# 9 IN symbols carrying the same discontinuity, so this was never about three
# microcaps — it is every split since the last full refetch of each panel.
#
# Splits BEFORE that refetch are already correct, which is what makes the bug
# invisible: CISS's January 1-for-20 and April 1-for-7 both show ~1.0x
# continuity. Only the incremental-append path is wrong, so the panel looks
# healthy everywhere except its most recent weeks.
#
# DETECTION IS A CHEAP SCREEN, NOT A NETWORK SWEEP. Asking yfinance for the
# split history of all 9,433 US symbols nightly is not affordable. But a split
# always leaves a price discontinuity at the seam between the panel's last bar
# and the first fresh one, so the DATA screens itself for free, and only the
# handful that trip the screen (typically 0-5 a night) cost a network call to
# confirm the exact ratio. Never INFER the ratio from the price jump: the jump
# is split × that day's real move, so 45.1x is a 1-for-40 plus 12.8%, and
# rounding it to "1-for-45" would bake the real move permanently into history.
SPLIT_SCREEN_HI = 3.0        # fresh/stored close above this -> possible reverse split
SPLIT_SCREEN_LO = 1 / 3.0    # ...below this -> possible forward split/bonus
# yfinance reports a split as the multiplier applied to SHARE COUNT: 2.0 for a
# 2-for-1, 0.025 for a 1-for-40 reverse. Price moves inversely, so putting
# stored history onto the new basis is price / value and volume * value.
SPLIT_SUFFIX = {"IN": ".NS"}  # US/JP/KR/EU symbols are already yfinance-shaped
# RATIO FROM THE VENDOR, DATE FROM THE PANEL. yfinance's split date and the bar
# where the price actually rebases routinely disagree by a few sessions — it may
# stamp an announcement or effective date, and the panel may be missing bars in
# between. LIMN split 2026-08-21 but the panel rebases 08-24; BRCC rebases 08-21
# against a recorded 08-24. Matching them exactly finds neither. So the window is
# generous, and what makes that safe is not the window but SPLIT_RATIO_TOL: the
# vendor's ratio must predict the jump the panel actually shows, or the match is
# rejected. The adjustment is then applied at the panel's own discontinuity,
# which is the only date the stored bars agree on.
SPLIT_WINDOW_PAD = pd.Timedelta(days=6)
SPLIT_RATIO_TOL = 2.0   # observed jump within this factor of the ratio's prediction


def _parts(panel: Path) -> list:
    """Year partitions ONLY.

    Never hand the directory to read_parquet — that pulls in whatever else is
    lying there (.bak, .tmp from an interrupted run) and double-counts bars.
    """
    return sorted(panel.glob("year=*.parquet"))


def _read_panel(panel: Path) -> pd.DataFrame:
    """Whole panel as one frame. Retained for callers that genuinely need it —
    update() no longer does, and should not start again: see _panel_stats."""
    return pd.concat([pd.read_parquet(p) for p in _parts(panel)], ignore_index=True)


def _read_years(panel: Path, years) -> pd.DataFrame:
    """Only the named year partitions."""
    want = {panel / f"year={y}.parquet" for y in years}
    got = [p for p in _parts(panel) if p in want]
    if not got:
        return pd.DataFrame(columns=COLS)
    return pd.concat([pd.read_parquet(p) for p in got], ignore_index=True)


def _con():
    import duckdb
    c = duckdb.connect()
    # Bounded: this runs inside a nightly pipeline beside other work, and the
    # point of the exercise is a smaller footprint, not a faster one bought with
    # a bigger one.
    c.execute("set threads to 4")
    c.execute("set memory_limit='1GB'")
    return c


def _panel_stats(panel: Path) -> dict:
    """Everything update() needs about the panel, WITHOUT materialising it.

    update() used to read all 16M US rows to learn four things — max date, row
    count, symbol count, and which years hold duplicate (Symbol, Date) keys — and
    then write exactly one year partition. Every one of those is an aggregate, so
    the read was pure overhead: DuckDB streams the parquet and returns scalars.

    The dedup years matter as much as the totals. _write_years must rewrite any
    year whose duplicates were collapsed, or the collapse is recomputed nightly
    and never persisted — so the scan reports WHERE the duplicates are, not just
    how many.
    """
    parts = _parts(panel)
    if not parts:
        return {}

    # 🔴 ONE PARTITION AT A TIME. count(distinct (Symbol, Date)) over the whole
    # panel builds a hash table with one entry per BAR — 16.3M for US — and that
    # single query held 1.19GB, more than the pandas read it replaced was ever
    # worth on an 8GB box. The panel is already year-partitioned, so the same
    # answer comes from per-file aggregates that combine trivially (sum, max,
    # set-union), bounding the hash table to one year (~1.3M) instead of all of
    # them. Streaming beats a smarter query here; scale came from the partition
    # layout that already existed.
    total = 0
    dup_years, dups = set(), 0
    symbols: set = set()
    mx = None
    con = _con()
    try:
        for p in parts:
            n, d, m = con.execute(
                f"""select count(*),
                           count(*) - count(distinct (Symbol, Date)),
                           max(Date)
                    from read_parquet('{p}')""").fetchone()
            total += int(n)
            if d:
                dups += int(d)
                try:
                    dup_years.add(int(p.stem.split("=")[1]))
                except Exception:
                    pass
            if m is not None and (mx is None or m > mx):
                mx = m
            # Symbol lists are tiny (9,850 for US) — a union across years costs
            # nothing and keeps the log line honest.
            symbols.update(r[0] for r in con.execute(
                f"select distinct Symbol from read_parquet('{p}')").fetchall())
    finally:
        con.close()
    return {"rows": total, "symbols": len(symbols), "max_date": pd.Timestamp(mx),
            "dup_years": dup_years, "dups": dups}


def _panel_last_bar(panel: Path) -> pd.DataFrame:
    """Last stored (Date, Close) per symbol — the left side of the split seam.

    One partition at a time, same reason as _panel_stats: QUALIFY collapses each
    year to one row per symbol (~9,850 for US) before anything crosses into
    pandas, so this never materialises a panel to learn a per-symbol scalar.
    """
    parts = _parts(panel)
    if not parts:
        return pd.DataFrame(columns=["Symbol", "Date", "Close"])
    con = _con()
    try:
        frames = [con.execute(
            f"""select Symbol, Date, Close from read_parquet('{p}')
                qualify row_number() over (partition by Symbol order by Date desc) = 1"""
        ).fetch_df() for p in parts]
    finally:
        con.close()
    d = pd.concat(frames, ignore_index=True)
    d["Date"] = pd.to_datetime(d["Date"])
    d["Symbol"] = d["Symbol"].astype(str).str.upper()
    # A symbol can appear in several years; its true last bar is the newest.
    return d.sort_values("Date").drop_duplicates("Symbol", keep="last")


def _confirm_split(market: str, sym: str, lo: pd.Timestamp,
                   hi: pd.Timestamp) -> list:
    """Real splits for `sym` in (lo, hi] as [(value, date), ...], oldest first.

    A LIST, not one cumulative number, because the repair path needs each split
    placed at its own date: with two unadjusted splits d1 < d2, bars before d1
    are wrong by both and bars between them by only the second. Applying each
    independently gets that right for free; a single product would over-adjust
    the middle stretch. The seam path is the degenerate case where every stored
    bar precedes all of them, so sequential application there just multiplies
    out — which is what CISS needs, having split three times in 2026.

    Returns [] on any doubt. A missed split leaves one visible bad return; a
    fabricated one silently corrupts ten years of history. The errors are not
    symmetric, so this fails toward doing nothing.
    """
    try:
        import yfinance as yf
        s = yf.Ticker(sym + SPLIT_SUFFIX.get(market, "")).splits
    except Exception as e:
        print(f"     {sym}: split lookup failed ({type(e).__name__}) — not adjusting")
        return []
    if s is None or not len(s):
        return []
    # NORMALISE TO MIDNIGHT. yfinance stamps a split at the session open
    # (09:30 local), panel Dates are midnight. Compared raw, a split on the
    # newest bar's own day sits ABOVE `hi` and is missed — which is exactly
    # VCIG's 2026-08-24 1-for-15, the most recent and most urgent case.
    idx = pd.to_datetime(s.index).tz_localize(None).normalize()
    s = pd.Series(s.values, index=idx).sort_index()
    hit = s[(s.index >= lo) & (s.index <= hi)]
    hit = hit[hit > 0]
    return [(float(v), d) for d, v in hit.items()]


def _match_jump(market: str, sym: str, when: pd.Timestamp, prev_when: pd.Timestamp,
                jump: float) -> Optional[float]:
    """Cumulative split value explaining `jump` at `when`, or None.

    The gate is agreement, not proximity: a 1-for-40 predicts a 40x rebase, so a
    45.1x jump matches (the extra 12.8% is that day's real move) and a 4x jump
    does not. Without this the widened window would happily attach an unrelated
    split from the neighbouring week to a genuine move.
    """
    events = _confirm_split(market, sym, prev_when - SPLIT_WINDOW_PAD,
                            when + SPLIT_WINDOW_PAD)
    if not events:
        return None
    value = 1.0
    for v, _ in events:
        value *= v
    if value <= 0:
        return None
    predicted = 1.0 / value
    ratio = jump / predicted
    if not (1 / SPLIT_RATIO_TOL) <= ratio <= SPLIT_RATIO_TOL:
        print(f"     {sym}: split {value:g} predicts {predicted:.1f}x but panel "
              f"shows {jump:.1f}x — rejected, not adjusting")
        return None
    return value


def _detect_splits(market: str, panel: Path, new: pd.DataFrame,
                   last_old: pd.Timestamp) -> dict:
    """Symbols whose stored history is on a stale price basis.

    Screens on the discontinuity at the seam (free), then confirms only the
    flagged handful against yfinance (cheap because the screen is tight).
    """
    if new.empty:
        return {}
    first_new = (new.sort_values("Date")
                    .drop_duplicates("Symbol", keep="first")[["Symbol", "Date", "Close"]]
                    .rename(columns={"Date": "new_date", "Close": "new_close"}))
    last_bar = (_panel_last_bar(panel)
                .rename(columns={"Date": "old_date", "Close": "old_close"}))
    seam = first_new.merge(last_bar, on="Symbol", how="inner")
    seam = seam[(seam["old_close"] > 0) & (seam["new_close"] > 0)]
    if seam.empty:
        return {}
    seam["jump"] = seam["new_close"] / seam["old_close"]
    flagged = seam[(seam["jump"] > SPLIT_SCREEN_HI) | (seam["jump"] < SPLIT_SCREEN_LO)]
    if flagged.empty:
        return {}

    print(f"  {market}: {len(flagged)} symbol(s) crossed the split screen — confirming")
    out = {}
    for r in flagged.itertuples():
        value = _match_jump(market, r.Symbol, r.new_date, r.old_date, r.jump)
        if value is None:
            # Not a split — a genuine microcap move, or a vendor bad print. Left
            # alone deliberately: this function corrects corporate actions, and
            # silently smoothing a real 4x would be a different and worse bug.
            print(f"     {r.Symbol}: {r.jump:.1f}x jump, no matching split — left as-is")
            continue
        out[r.Symbol] = [(value, r.new_date)]
        print(f"     {r.Symbol}: split {value:g} at {r.new_date.date()} "
              f"(seam {r.old_close:g} -> {r.new_close:g}, {r.jump:.1f}x) — adjusting history")
    return out


def _apply_splits(market: str, panel: Path, splits: dict, dry: bool) -> int:
    """Put stored history for `splits` onto the post-split basis.

    Rewrites EVERY year partition, because a split invalidates a symbol's whole
    history, not just the current year — but strictly one partition at a time,
    so the footprint stays at one year regardless of how deep the panel is. That
    is why this is not folded into the main merge: routing it through
    _write_years would mean adding every year to `changed_years` and reading the
    entire panel back into one frame, which is the 1.63GB peak the DuckDB stats
    path was written to remove.
    """
    if dry:
        print(f"  {market}: dry-run, {len(splits)} split(s) not applied"); return 0
    touched = 0
    for part in _parts(panel):
        d = pd.read_parquet(part)
        d["Symbol"] = d["Symbol"].astype(str).str.upper()
        d["Date"] = pd.to_datetime(d["Date"])
        n = 0
        for sym, events in splits.items():
            for value, when in events:
                # Bars strictly BEFORE the split are the stale ones. Applying
                # each event at its own date is what makes multiple unadjusted
                # splits compose correctly: a bar older than both gets divided
                # twice, one between them only once.
                m = (d["Symbol"] == sym) & (d["Date"] < when)
                if not m.any():
                    continue
                for c in ("Open", "High", "Low", "Close"):
                    if c in d.columns:
                        d.loc[m, c] = (d.loc[m, c] / value).astype(d[c].dtype, errors="ignore")
                if "Volume" in d.columns:
                    d.loc[m, "Volume"] = (d.loc[m, "Volume"] * value).astype(
                        d["Volume"].dtype, errors="ignore")
                n += int(m.sum())
        if not n:
            continue
        bak_dir = BACKUP / panel.name
        bak_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(part, bak_dir / f"{part.name}.presplit.bak")
        tmp = part.with_suffix(".parquet.tmp")
        d.to_parquet(tmp, compression="zstd", index=False)
        tmp.replace(part)
        touched += n
        print(f"  ✅ {market}: {part.name} re-adjusted ({n:,} bars)")
    if not touched:
        print(f"  {market}: split confirmed but no stored bars matched — nothing to adjust")
    return touched


def _scan_discontinuities(panel: Path, since: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    """Split-shaped jumps already sitting INSIDE stored history.

    The seam screen only sees the boundary between stored and fresh, so it
    cannot help with splits ingested before this code existed — those are now
    interior to the panel. Same test, applied to consecutive stored bars.

    Pushed entirely into DuckDB: the lag() runs over the parquet and only the
    handful of flagged rows cross into pandas. Reading Date/Symbol/Close for
    all 16.3M US bars to diff them in pandas would cost about a gigabyte to
    find ~200 rows.
    """
    parts = _parts(panel)
    if not parts:
        return pd.DataFrame()
    files = "[" + ", ".join(f"'{p}'" for p in parts) + "]"
    where = f"and Date >= DATE '{since.date()}'" if since is not None else ""
    con = _con()
    try:
        return con.execute(f"""
            select Symbol, Date, prev_date, prev_close, Close,
                   Close / prev_close as jump
            from (
                select Symbol, Date, Close,
                       lag(Close) over (partition by Symbol order by Date) as prev_close,
                       lag(Date)  over (partition by Symbol order by Date) as prev_date
                from read_parquet({files})
                where Close is not null {where}
            )
            where prev_close > 0 and Close > 0
              and (Close / prev_close > {SPLIT_SCREEN_HI}
                   or Close / prev_close < {SPLIT_SCREEN_LO})
            order by Symbol, Date
        """).fetch_df()
    finally:
        con.close()


def repair(market: str, dry: bool, since: Optional[pd.Timestamp] = None) -> int:
    """One-off: re-adjust splits that were ingested before the seam check existed.

    Separate entry point rather than part of the nightly run, because it rewrites
    every year partition and re-reads split history for every flagged symbol.
    That is right once, and wasteful every night — the seam check is what keeps
    the panel correct from here on.
    """
    panel = PANELS.get(market)
    if not panel or not panel.exists() or not _parts(panel):
        print(f"  {market}: no warehouse partitions at {panel}"); return 1

    hits = _scan_discontinuities(panel, since)
    if hits.empty:
        print(f"  {market}: no split-shaped discontinuities in stored history"); return 0
    hits["Date"] = pd.to_datetime(hits["Date"])
    hits["prev_date"] = pd.to_datetime(hits["prev_date"])
    print(f"  {market}: {len(hits)} discontinuity bar(s) across "
          f"{hits['Symbol'].nunique()} symbol(s) — confirming against yfinance")

    splits, unexplained = {}, []
    for r in hits.itertuples():
        # Per FLAGGED BAR, not per symbol: a symbol with two unadjusted splits
        # needs each one matched and dated separately, and collapsing them to one
        # symbol-wide window would ask yfinance to explain both jumps at once.
        value = _match_jump(market, r.Symbol, r.Date, r.prev_date, r.jump)
        if value is None:
            unexplained.append((r.Symbol, r.Date.date(), float(r.jump)))
            continue
        splits.setdefault(r.Symbol, []).append((value, r.Date))

    n_ev = sum(len(v) for v in splits.values())
    print(f"  {market}: {n_ev} split(s) confirmed across {len(splits)} symbol(s), "
          f"{len(unexplained)} unexplained (left untouched)")
    if unexplained:
        # Surfaced, never silently adjusted. These are real moves, halts, or bad
        # vendor prints, and each is a judgement call a human should make.
        for sym, when, jump in unexplained[:15]:
            print(f"     ? {sym} {when} {jump:.1f}x")
        if len(unexplained) > 15:
            print(f"     ... and {len(unexplained) - 15} more")
    if not splits:
        return 0
    _apply_splits(market, panel, splits, dry)
    return 0


def _fresh_us(since=None) -> pd.DataFrame:
    """Per-ticker parquets from market_cache -> long frame, filtered AT THE SCAN.

    Was: read all 7,699 files into pandas and concat to a 7.5M-row frame, then
    throw away 99.1% of it because only bars strictly newer than the panel are
    ever merged. DuckDB applies the date predicate while scanning, so the 66k
    rows that survive are the only ones that ever exist in memory — measured
    7,506,205 -> 66,304 rows.

    Symbol comes from the FILENAME (these files carry no Symbol column), via
    read_parquet(filename=true). union_by_name tolerates the schema drift across
    a cache written over months; a file with no Date column yields NULL and is
    dropped by the predicate, which is the same outcome as the old `dcol is None`
    skip.
    """
    try:
        import data_registry as R
    except Exception:
        return pd.DataFrame()
    files = sorted(R.OHLC_DIR.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    where = f"where Date > TIMESTAMP '{pd.Timestamp(since)}'" if since is not None else ""
    con = _con()
    try:
        d = con.execute(f"""
            select regexp_extract(filename, '([^/]+)\\.parquet$', 1) as Symbol,
                   Date, Open, High, Low, Close, Volume
            from read_parquet('{R.OHLC_DIR}/*.parquet',
                              filename=true, union_by_name=true)
            {where}""").df()
    except Exception as e:
        print(f"  US: duckdb scan failed ({type(e).__name__}) — falling back to pandas")
        d = _fresh_us_pandas()
    finally:
        con.close()
    return d


def _fresh_us_pandas() -> pd.DataFrame:
    """Original per-file pandas path. Kept as the fallback ONLY — it materialises
    the whole cache and is what the DuckDB scan above exists to avoid."""
    import data_registry as R
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


def _fresh_in(since=None) -> pd.DataFrame:
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

    if bs.CLEANED.exists() and since is not None:
        con = _con()
        try:
            d = con.execute(
                f"select {', '.join(COLS)} from read_parquet('{bs.CLEANED}') "
                f"where Date > TIMESTAMP '{pd.Timestamp(since)}'").df()
            if not d.empty:
                d["Symbol"] = d["Symbol"].astype(str).str.upper()
                return d
            # Empty is a legitimate answer ("already current"), not a failure —
            # return it rather than falling through to the full pandas read.
            return d
        except Exception:
            pass
        finally:
            con.close()

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
    def _f(since=None) -> pd.DataFrame:
        try:
            import ohlcv_cache as _oc
            cdir = _oc.CACHE_DIR
        except Exception:
            cdir = HERE.parent.parent / "data" / "bhavcopy_cache"
        f = Path(cdir) / f"ohlcv_{name}.parquet"
        if not f.exists():
            return pd.DataFrame()
        if since is not None:
            # Same pushdown as US: JAPAN alone is 900k rows of which ~19k are new.
            con = _con()
            try:
                return con.execute(
                    f"select {', '.join(COLS)} from read_parquet('{f}') "
                    f"where Date > TIMESTAMP '{pd.Timestamp(since)}'").df()
            except Exception:
                pass
            finally:
                con.close()
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


def update(market: str, dry: bool, skip_splits: bool = False) -> int:
    panel = PANELS.get(market)
    if not panel or not panel.exists() or not any(panel.glob("year=*.parquet")):
        print(f"  {market}: no warehouse partitions at {panel}"); return 1

    # ── stats WITHOUT materialising the panel ────────────────────────────────
    # The whole panel used to be read here to learn four scalars and then write
    # one year partition. On an 8GB machine that peaked at 1.63GB for US and was
    # a direct contributor to jetsam pressure. DuckDB streams the same answers.
    st = _panel_stats(panel)
    if not st:
        print(f"  {market}: no warehouse partitions at {panel}"); return 1
    raw_rows, deduped = st["rows"], st["dups"]
    dup_years, last_old = st["dup_years"], st["max_date"]
    old_rows = raw_rows - deduped

    # Dedup FIRST, so the guard's baseline is the set of distinct BARS. The
    # invariant that matters is "no bar disappears", not "no row disappears" —
    # only the former is history loss, and conflating them is what froze this
    # panel for four days: a .bak kept inside the dataset dir was read back as a
    # second copy of 2026, the merge's dedup correctly collapsed it, and the
    # row-count check read that collapse as truncation and refused every run.
    # The .bak is now written outside the panel and _read_panel() globs only
    # year=*.parquet, so this should find nothing; it stays as a cheap residual
    # defense, and any non-zero count here means a new writer is double-feeding.
    print(f"  {market} panel: {old_rows:,} rows, {st['symbols']:,} symbols, "
          f"last bar {last_old.date()}")
    if deduped:
        print(f"  {market}: {deduped:,} duplicate (Symbol, Date) rows collapsed "
              f"(panel held {raw_rows:,}) — years {sorted(dup_years)}")

    # Push the strictly-newer-dates rule INTO the source scan. It was already the
    # merge's rule; applying it at read time instead of after materialising means
    # the discarded 99% is never allocated.
    fresh = FRESH[market](since=last_old)

    # 🔴 EMPTY NOW MEANS "ALREADY CURRENT", NOT "SOURCE MISSING". Before the
    # pushdown, an empty frame could only mean the source was unreadable, so
    # returning here was right. Now the predicate runs inside the scan, so the
    # ordinary up-to-date case ALSO returns empty — and this early return fired
    # before the duplicate-repair branch below, which would silently skip a
    # pending repair on any panel that had nothing new to append. Fall through
    # with an empty `new` instead, and let the existing logic decide.
    if fresh.empty:
        fresh = pd.DataFrame(columns=COLS)
        fresh["Date"] = pd.to_datetime(fresh["Date"])
    else:
        fresh["Date"] = pd.to_datetime(fresh["Date"])
        fresh["Symbol"] = fresh["Symbol"].astype(str).str.upper()
    # NOTE the log semantics changed with the pushdown: this is now the count of
    # rows NEWER than the panel, not the size of the whole source. US used to
    # print 7,506,205 here and merge 66,300 of them; it now prints the 66,300.
    if not fresh.empty:
        print(f"  {market} fresh : {len(fresh):,} new rows, "
              f"{fresh['Symbol'].nunique():,} symbols, "
              f"last bar {fresh['Date'].max().date()}")

    # STRICTLY NEWER DATES ONLY. Re-importing an overlapping date would let a
    # vendor's revised close overwrite the price a past decision was recorded
    # against, silently changing history.
    new = fresh[fresh["Date"] > last_old].copy()
    if not new.empty:
        new = _drop_foreign(market, new)
        if new is None:
            return 1
    if new.empty and not deduped:
        print(f"  {market}: already current — 0 new bars"); return 0

    # ── re-adjust history for any split at the seam ──────────────────────────
    # BEFORE the merge reads `old`, so the partitions it loads are already on the
    # new basis and the append lands on a continuous series. Running it after
    # would write the stale bars back out and leave the seam broken for a day.
    if not new.empty and not skip_splits:
        splits = _detect_splits(market, panel, new, last_old)
        if splits:
            _apply_splits(market, panel, splits, dry)

    # ── load ONLY the partitions this write will touch ───────────────────────
    # Closed years cannot change under the strictly-newer-dates rule, so reading
    # them was always pure cost. Dedup years join the set because their file
    # changes on disk even with no fresh bar — skip them and the collapse is
    # recomputed nightly and never persisted.
    changed_years = (set(new["Date"].dt.year.unique()) if not new.empty else set()) | dup_years
    old = _read_years(panel, changed_years)
    if old.empty and not new.empty:
        print(f"  ❌ {market}: year partitions for {sorted(changed_years)} unreadable — refusing")
        return 1
    old["Date"] = pd.to_datetime(old["Date"])
    old["Symbol"] = old["Symbol"].astype(str).str.upper()
    old = old[COLS].drop_duplicates(subset=["Symbol", "Date"], keep="first")
    old_slice_rows = len(old)

    if new.empty:
        # Repair even with nothing to append, or the duplicates only ever get
        # cleaned by luck — when fresh bars happen to land in the same year.
        print(f"  {market}: 0 new bars, writing duplicate repair only")
        return _write_years(market, panel, old, dup_years, dry)

    for c in COLS:
        if c not in new.columns:
            new[c] = pd.NA
    new = new[COLS]
    # Match the panel's dtypes so the concat does not silently widen float32 to
    # float64 and double the file.
    for c in ("Open", "High", "Low", "Close"):
        if c in old.columns:
            new[c] = new[c].astype(old[c].dtype, errors="ignore")

    merged = pd.concat([old, new], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Symbol", "Date"], keep="first")
    merged = merged.sort_values(["Symbol", "Date"]).reset_index(drop=True)

    added = len(merged) - old_slice_rows
    print(f"  {market}: +{added:,} bars across {new['Symbol'].nunique():,} symbols "
          f"({last_old.date()} -> {merged['Date'].max().date()})")

    # ── refuse a write that loses anything ────────────────────────────────────
    # Evaluated on the CHANGED YEARS, which is exactly equivalent to the old
    # whole-panel check: partitions outside this set are not rewritten, so no row
    # or symbol in them can be lost by definition. Checking only what is at risk
    # is what makes the whole-panel read unnecessary.
    if len(merged) < old_slice_rows:
        print(f"  ❌ {market}: merge LOST rows in years {sorted(changed_years)} "
              f"({old_slice_rows:,} -> {len(merged):,}) — refusing")
        return 1
    if merged["Date"].max() < last_old:
        print(f"  ❌ {market}: last bar moved BACKWARDS — refusing"); return 1
    lost = set(old["Symbol"]) - set(merged["Symbol"])
    if lost:
        print(f"  ❌ {market}: {len(lost)} symbols vanished — refusing"); return 1

    return _write_years(market, panel, merged, changed_years, dry)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fold fresh bars into the deep panels")
    ap.add_argument("--market", choices=list(PANELS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-split-check", action="store_true",
                    help="skip split detection (offline runs — the screen needs "
                         "yfinance to confirm a ratio, and never guesses one)")
    ap.add_argument("--repair-splits", action="store_true",
                    help="one-off: re-adjust splits ingested before the seam "
                         "check existed. Rewrites every year partition — run "
                         "with --dry-run first")
    ap.add_argument("--since", type=str, default=None,
                    help="with --repair-splits, only scan bars from this date "
                         "(YYYY-MM-DD) forward")
    a = ap.parse_args()
    rc = 0
    for m in ([a.market] if a.market else list(PANELS)):
        if a.repair_splits:
            rc |= repair(m, a.dry_run,
                         pd.Timestamp(a.since) if a.since else None)
        else:
            rc |= update(m, a.dry_run, a.no_split_check)
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())
