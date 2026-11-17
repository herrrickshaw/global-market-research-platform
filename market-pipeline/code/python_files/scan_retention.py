#!/usr/bin/env python3
"""
scan_retention.py — expire old scan workbooks, but only ones already ingested.

WHY NOT `find -mtime +N -delete`
-------------------------------
market_ingest.ingest_snapshot() globs EVERY workbook in a scan dir and appends
"every workbook date not yet in the table (backfills ingest gaps)". The files are
therefore not disposable by age: an un-ingested day deleted on age alone is gone
from market_daily.snapshots permanently, and nothing would report it — the table
would simply never have that date, and the gap is indistinguishable from a day
the scan did not run.

So a file is expendable only when BOTH hold:

    its date is already present in market_daily.snapshots for that market
    its date is older than --keep-days

The second clause is not redundant. Ingestion having happened is not the same as
ingestion being correct, and the recent window is what anyone debugging a bad
brief actually opens. Age alone is unsafe; ingested-ness alone throws away the
evidence you need soonest.

WHAT IT RECLAIMS. Files far outnumber dates (39-48 files against 15-17 ingested
dates per market) because an intraday re-run writes a second workbook for the
same day and market_ingest keeps only the newest per date. Those superseded
same-day duplicates are pure waste and go first.

    scan_retention.py                 # dry run — prints, deletes nothing
    scan_retention.py --apply
    scan_retention.py --apply --keep-days 21
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# scan dir -> (filename glob, market key in market_daily.snapshots)
DIRS = {
    "indian_full_scan": ("indian_full_scan_*.xlsx", "india"),
    "us_full_scan":     ("us_full_scan_*.xlsx", "us"),
    "japan_scan":       ("japan_market_scan_*.xlsx", "japan"),
    "korea_scan":       ("korea_market_scan_*.xlsx", "korea"),
    "european_scan":    ("european_market_scan*.xlsx", "europe"),
}
_DATE = re.compile(r"(20\d{6})")


def _file_date(p: Path):
    m = _DATE.search(p.name)
    if not m:
        return None
    import datetime as dt
    try:
        return dt.datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _ingested() -> dict:
    """{market: {dates already in market_daily.snapshots}}.

    A hard requirement, not an optimisation: with no DB there is no way to know
    what is safe to delete, so the tool refuses rather than falling back to age.
    """
    import psycopg2
    try:
        import data_registry as R
        dsn = R.PG_DSN
    except Exception:
        dsn = "dbname=market_data host=/tmp user=umashankar"
    con = psycopg2.connect(dsn)
    cur = con.cursor()
    cur.execute("select market, as_of_date from market_daily.snapshots group by 1,2")
    out: dict = {}
    for mkt, d in cur.fetchall():
        out.setdefault(mkt, set()).add(d)
    con.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--apply", action="store_true", help="actually delete")
    ap.add_argument("--keep-days", type=int, default=10)
    a = ap.parse_args()

    import datetime as dt
    cutoff = dt.date.today() - dt.timedelta(days=a.keep_days)

    try:
        ingested = _ingested()
    except Exception as e:
        print(f"  🔴 cannot reach Postgres ({type(e).__name__}) — refusing to delete "
              f"anything, because ingestion state is the only thing that makes a "
              f"workbook expendable")
        return 1

    total_n, total_b = 0, 0
    for sub, (glob, mkt) in DIRS.items():
        d = HERE / sub
        if not d.is_dir():
            continue
        have = ingested.get(mkt, set())
        files = sorted(d.glob(glob))
        # Newest file per date is what market_ingest would use; older same-date
        # files are already superseded and never read again.
        by_date: dict = {}
        for f in files:
            fd = _file_date(f)
            if fd:
                by_date.setdefault(fd, []).append(f)

        drop, keep_unin, keep_recent = [], 0, 0
        for fd, fs in by_date.items():
            fs = sorted(fs)
            newest = fs[-1]
            drop.extend(fs[:-1])              # superseded same-day re-runs
            if fd not in have:
                keep_unin += 1                # NOT yet ingested — never delete
            elif fd > cutoff:
                keep_recent += 1
            else:
                drop.append(newest)

        n = len(drop)
        b = sum(f.stat().st_size for f in drop if f.exists())
        total_n += n; total_b += b
        print(f"  {sub:<20} {len(files):>3} files / {len(by_date):>3} dates  ->  "
              f"drop {n:>3} ({b/1048576:>6.1f} MB)   keep: {keep_recent} recent, "
              f"{keep_unin} un-ingested")
        if a.apply:
            for f in drop:
                try:
                    f.unlink()
                except Exception as e:
                    print(f"    could not delete {f.name}: {type(e).__name__}")

    print(f"\n  {'DELETED' if a.apply else 'WOULD DELETE'}: {total_n} files, "
          f"{total_b/1048576:.1f} MB"
          f"{'' if a.apply else '   (re-run with --apply)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
