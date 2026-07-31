#!/usr/bin/env python3
"""
amfi_nav_collect.py — Indian mutual-fund NAV history into the warehouse.

WHY (2026-07-28): the platform builds "mutual-fund-style" bundles
(portfolio_bundles.py) and validates them on HOLDINGS overlap against index/ETF
constituents (bundle_validation.py), but it has never held a single fund's
PERFORMANCE. "Fund-style" was a metaphor. This makes it measurable: AMFI
publishes daily NAV for every Indian scheme, free and unauthenticated, with
SEBI's own category taxonomy — the cleanest peer-grouping any of the five
markets offers. The scorecard that consumes this asks one question: did a
tier-driven book beat its CATEGORY, after costs, over the same window.

SOURCE. portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt=&todt=
  * www.amfiindia.com 302-redirects to portal.*; the portal host is used
    directly so a redirect-following change upstream can't silently break us.
  * Semicolon-delimited, with AMC and CATEGORY as bare header lines between
    blocks — the category is NOT a column, it is positional state while parsing.
  * Verified reachable from this machine and back to at least 2016-07. (SEBI and
    IMF are blocked here; AMFI is not — hence AMFI rather than a SEBI feed.)

WHAT IS DELIBERATELY NOT GUESSED
  * PLAN (Direct/Regular) and OPTION (Growth/IDCW) are parsed from the scheme
    name, and stay 'unknown' when the name does not say. They matter enormously
    — Direct and Regular are the same portfolio ~0.6-1.2%/yr apart, and IDCW NAV
    drops on every payout so it understates total return — so a wrong guess is
    worse than a null the scorecard can exclude. NB: Direct plans only exist from
    Jan 2013; pre-2013 rows legitimately have no plan token, and that is a fact
    about the era, not a parse failure.
  * SURVIVORSHIP is recorded, not corrected. funds.schemes keeps first_seen /
    last_seen per scheme, so a scheme that stops reporting is visible as dead
    rather than silently absent. Comparing a book only against schemes that
    still exist today flatters the book; the scorecard needs the dead ones, and
    they can only be captured by ingesting history as it was published.

APPEND-ONLY + IDEMPOTENT, like scripts/market_ingest.py: a (scheme_code,
nav_date) already present is never re-inserted, so re-running any number of
times a day appends 0 rows. Backfill is chunked by month and resumable — an
interrupted 10-year load restarts at the first missing month.

Usage:
  python3 scripts/amfi_nav_collect.py                    # incremental to today
  python3 scripts/amfi_nav_collect.py --backfill-years 10
  python3 scripts/amfi_nav_collect.py --from 2024-01-01 --to 2024-03-31
  python3 scripts/amfi_nav_collect.py --status
  python3 scripts/amfi_nav_collect.py --dry-run --from 2026-07-01 --to 2026-07-07
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import re
import sys
import time
import urllib.request

import pandas as pd
import psycopg2.extras

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import pg_client

DSN = "dbname=market_data host=/tmp user=umashankar"
SCHEMA = "funds"
URL = ("https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
       "?frmdt={frm}&todt={to}")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
CHUNK_DAYS = 30          # ~17MB/25 dates observed; a month keeps memory bounded
SLEEP_S = 1.5            # be a polite guest on a free public endpoint
AMFI_EPOCH = dt.date(2006, 4, 1)

# Native Postgres DDL for pg_client.ensure_schema() — no `pg.` ATTACH-alias
# prefix, Postgres type names (DOUBLE PRECISION not DuckDB's bare DOUBLE).
# Combines the old DDL (attached-catalog side) and PG_SETUP (postgres_execute
# side, since duckdb's pg extension couldn't CREATE INDEX/VIEW there) into
# one statement list — psycopg2 has no such split.
DDL = f"""
CREATE SCHEMA IF NOT EXISTS "{SCHEMA}";
CREATE TABLE IF NOT EXISTS "{SCHEMA}".nav (
  scheme_code BIGINT, nav_date DATE, nav DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS "{SCHEMA}".schemes (
  scheme_code BIGINT, scheme_name VARCHAR, isin_growth VARCHAR,
  isin_reinvest VARCHAR, amc VARCHAR, category VARCHAR,
  plan VARCHAR, option VARCHAR, first_seen DATE, last_seen DATE
);
CREATE TABLE IF NOT EXISTS "{SCHEMA}".ingest_log (
  run_at TIMESTAMP, frm_date DATE, to_date DATE, schemes_seen BIGINT,
  rows_appended BIGINT, total_rows BIGINT, status VARCHAR, detail VARCHAR
);
CREATE UNIQUE INDEX IF NOT EXISTS nav_pk
  ON "{SCHEMA}".nav (scheme_code, nav_date);
CREATE INDEX IF NOT EXISTS nav_date_ix ON "{SCHEMA}".nav (nav_date);
CREATE UNIQUE INDEX IF NOT EXISTS schemes_pk
  ON "{SCHEMA}".schemes (scheme_code);
CREATE OR REPLACE VIEW "{SCHEMA}".scheme_status AS
SELECT s.*,
       (SELECT max(nav_date) FROM "{SCHEMA}".nav) AS panel_last,
       CASE WHEN s.last_seen >= (SELECT max(nav_date) FROM "{SCHEMA}".nav)
                                 - INTERVAL '10 days'
            THEN 'alive' ELSE 'dead' END AS status
FROM "{SCHEMA}".schemes s;
"""

# Growth is tested BEFORE IDCW on purpose. Names carry both tokens often enough
# to matter ("Taurus Investor Education Pool - Unclaimed Dividend - Growth" is a
# GROWTH option of a dividend pool), and every IDCW variant observed lacks a
# standalone "Growth". Word-boundary anchored: the AMC "Groww" is not "Growth".
# "Cumulative" is the older name for the same thing (no payout, NAV accretes) —
# ICICI still ships it, and dropping those to 'unknown' would silently shrink
# the peer set. BONUS is a genuine THIRD option, not a growth variant: units are
# issued instead of cash, so its NAV series is not comparable to either and it
# gets its own label rather than being lumped into unknown.
RE_GROWTH = re.compile(r"\bgrowth\b|\bcumulative\b", re.I)
RE_BONUS = re.compile(r"\bbonus\b", re.I)
RE_IDCW = re.compile(r"\bidcw\b|income\s+distribution|\bdividend\b|"
                     r"\bpayout\b|reinvest", re.I)
# "Direct" first: "LIC MF ULIS (15 Yrs. Regular Premium ...)-Regular Plan-IDCW"
# carries "Regular" twice for unrelated reasons, so Regular is only concluded
# when Direct is absent.
RE_DIRECT = re.compile(r"\bdirect\b", re.I)
RE_REGULAR = re.compile(r"\bregular\b", re.I)
RE_CATEGORY = re.compile(r"schemes?\s*\(", re.I)


def classify_plan(name: str) -> str:
    if RE_DIRECT.search(name):
        return "direct"
    if RE_REGULAR.search(name):
        return "regular"
    return "unknown"


def classify_option(name: str) -> str:
    # Bonus first: "Nippon India Pharma Fund-Growth Plan-Bonus Option" carries
    # BOTH tokens, and the bonus mechanic is what makes its NAV incomparable.
    if RE_BONUS.search(name):
        return "bonus"
    if RE_GROWTH.search(name):
        return "growth"
    if RE_IDCW.search(name):
        return "idcw"
    return "unknown"


def fetch(frm: dt.date, to: dt.date, retries: int = 3) -> str:
    url = URL.format(frm=frm.strftime("%d-%b-%Y"), to=to.strftime("%d-%b-%Y"))
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:                       # noqa: BLE001
            last = e
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"AMFI fetch failed {frm}..{to}: {last}")


def parse(text: str) -> pd.DataFrame:
    """AMFI's report is a flat file with POSITIONAL state: category and AMC
    arrive as bare header lines and apply to every row until the next header."""
    rows, category, amc = [], None, None
    for ln in io.StringIO(text):
        ln = ln.rstrip("\n").strip()
        if not ln or ln.startswith("Scheme Code"):
            continue
        if ";" not in ln:
            if RE_CATEGORY.search(ln):
                category, amc = ln, None      # a new category resets the AMC
            else:
                amc = ln
            continue
        f = ln.split(";")
        if len(f) < 8:
            continue
        rows.append((f[0], f[1], f[2], f[3], f[4], f[7], amc, category))

    df = pd.DataFrame(rows, columns=["scheme_code", "scheme_name", "isin_growth",
                                     "isin_reinvest", "nav", "nav_date",
                                     "amc", "category"])
    if df.empty:
        return df
    df["scheme_code"] = pd.to_numeric(df.scheme_code, errors="coerce")
    df["nav"] = pd.to_numeric(df.nav, errors="coerce")      # "N.A." -> NaN
    df["nav_date"] = pd.to_datetime(df.nav_date, format="%d-%b-%Y",
                                    errors="coerce").dt.date
    for c in ("isin_growth", "isin_reinvest", "amc", "category"):
        df[c] = df[c].replace({"": None, "-": None})
    df = df.dropna(subset=["scheme_code", "nav", "nav_date"])
    df["scheme_code"] = df.scheme_code.astype("int64")
    df["plan"] = df.scheme_name.map(classify_plan)
    df["option"] = df.scheme_name.map(classify_option)
    return df


def connect():
    pg_client.connect()
    pg_client.ensure_schema([s.strip() for s in DDL.split(";") if s.strip()])
    return pg_client.get_connection()


def upsert(con, df: pd.DataFrame) -> int:
    """Append unseen (scheme_code, nav_date) and refresh the scheme master."""
    df = df.drop_duplicates(["scheme_code", "nav_date"], keep="last")

    # NAV — anti-join in pandas (was a DuckDB LEFT JOIN against the attached
    # table). Scoped to this chunk's scheme_codes (upsert() is called per
    # ~30-day CHUNK_DAYS window, never the full history at once), so the
    # existing-keys query stays bounded even across a 10-year backfill.
    with con.cursor() as cur:
        cur.execute(
            f'SELECT scheme_code, nav_date FROM "{SCHEMA}".nav '
            "WHERE scheme_code = ANY(%s)",
            # psycopg2 can't adapt numpy.int64 inside a list->ARRAY parameter
            # (unlike execute_values' row-tuple path) — cast to native int.
            ([int(x) for x in df.scheme_code.unique()],),
        )
        have = set(cur.fetchall())
    key = list(zip(df.scheme_code, df.nav_date))
    novel = df[[k not in have for k in key]]
    appended = len(novel)
    if appended:
        rows = pg_client.to_rows(novel, ["scheme_code", "nav_date", "nav"])
        pg_client.append_rows(SCHEMA, "nav", ["scheme_code", "nav_date", "nav"], rows)

    # Scheme master — widen first_seen / last_seen, never narrow (this IS the
    # survivorship record: a backfill of older months can only push first_seen
    # back, never drag last_seen backwards). Aggregated in pandas (was a
    # DuckDB TEMP VIEW), then ONE native INSERT ... ON CONFLICT DO UPDATE —
    # Postgres can express the widen-or-insert atomically here, unlike
    # DuckDB's attached-table access, which needed a separate UPDATE plus an
    # INSERT ... WHERE NOT EXISTS.
    def _last_non_null(s):
        s = s.dropna()
        return s.iloc[-1] if len(s) else None
    agg = df.groupby("scheme_code").agg(
        scheme_name=("scheme_name", _last_non_null),
        isin_growth=("isin_growth", _last_non_null),
        isin_reinvest=("isin_reinvest", _last_non_null),
        amc=("amc", _last_non_null),
        category=("category", _last_non_null),
        plan=("plan", _last_non_null),
        option=("option", _last_non_null),
        first_seen=("nav_date", "min"),
        last_seen=("nav_date", "max"),
    ).reset_index()
    cols = ["scheme_code", "scheme_name", "isin_growth", "isin_reinvest", "amc",
            "category", "plan", "option", "first_seen", "last_seen"]
    scheme_rows = pg_client.to_rows(agg, cols)
    if scheme_rows:
        try:
            with con.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    f'INSERT INTO "{SCHEMA}".schemes ({", ".join(cols)}) VALUES %s '
                    "ON CONFLICT (scheme_code) DO UPDATE SET "
                    "first_seen = LEAST(schemes.first_seen, EXCLUDED.first_seen), "
                    "last_seen = GREATEST(schemes.last_seen, EXCLUDED.last_seen), "
                    "scheme_name = EXCLUDED.scheme_name, category = EXCLUDED.category, "
                    "amc = EXCLUDED.amc, plan = EXCLUDED.plan, option = EXCLUDED.option, "
                    "isin_growth = COALESCE(EXCLUDED.isin_growth, schemes.isin_growth), "
                    "isin_reinvest = COALESCE(EXCLUDED.isin_reinvest, schemes.isin_reinvest)",
                    scheme_rows,
                )
            con.commit()
        except Exception:
            con.rollback()
            raise
    return appended


def log(con, frm, to, schemes, appended, total, status, detail=""):
    pg_client.append_rows(
        SCHEMA, "ingest_log",
        ["run_at", "frm_date", "to_date", "schemes_seen", "rows_appended",
         "total_rows", "status", "detail"],
        [(dt.datetime.now(), frm, to, schemes, appended, total, status, detail[:400])],
    )


def months(frm: dt.date, to: dt.date):
    cur = frm
    while cur <= to:
        end = min(cur + dt.timedelta(days=CHUNK_DAYS - 1), to)
        yield cur, end
        cur = end + dt.timedelta(days=1)


def status(con) -> int:
    try:
        with con.cursor() as cur:
            cur.execute(
                f'SELECT count(*), min(nav_date), max(nav_date) FROM "{SCHEMA}".nav'
            )
            n, mn, mx = cur.fetchone()
    except Exception as e:                            # noqa: BLE001
        con.rollback()
        print(f"funds.nav unavailable: {str(e)[:120]}")
        return 1
    print(f"\n=== AMFI NAV PANEL ===")
    print(f"  rows        : {n:,}")
    print(f"  date range  : {mn} -> {mx}")
    if not n:
        return 0
    with con.cursor() as cur:
        cur.execute(
            f"""SELECT count(*) FILTER (WHERE status='alive'),
                       count(*) FILTER (WHERE status='dead')
                FROM "{SCHEMA}".scheme_status"""
        )
        alive, dead = cur.fetchone()
    print(f"  schemes     : {alive + dead:,}  ({alive:,} alive · {dead:,} dead)")
    print("\n  EQUITY CATEGORIES (alive · growth option, the scorecard peer sets)")
    with con.cursor() as cur:
        cur.execute(f"""
            SELECT category, count(*) FILTER (WHERE plan='direct') AS direct,
                   count(*) FILTER (WHERE plan='regular') AS regular
            FROM "{SCHEMA}".scheme_status
            WHERE status='alive' AND option='growth' AND category ILIKE '%Equity%'
            GROUP BY category ORDER BY direct DESC LIMIT 15
        """)
        rows = cur.fetchall()
    for c, d, r in rows:
        print(f"    {d:4d} direct · {r:4d} regular   {c}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="frm", help="YYYY-MM-DD")
    ap.add_argument("--to", dest="to", help="YYYY-MM-DD")
    ap.add_argument("--backfill-years", type=float,
                    help="pull this many years back from today")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch + parse, report, write nothing")
    a = ap.parse_args()

    con = connect()
    if a.status:
        return status(con)

    today = dt.date.today()
    if a.frm:
        frm = dt.date.fromisoformat(a.frm)
    elif a.backfill_years:
        frm = today - dt.timedelta(days=int(a.backfill_years * 365.25))
    else:
        # Incremental: resume the day after the panel's high-water mark.
        with con.cursor() as cur:
            cur.execute(f'SELECT max(nav_date) FROM "{SCHEMA}".nav')
            mx = cur.fetchone()[0]
        frm = (mx + dt.timedelta(days=1)) if mx else today - dt.timedelta(days=30)
    to = dt.date.fromisoformat(a.to) if a.to else today
    frm = max(frm, AMFI_EPOCH)

    if frm > to:
        print(f"already current (panel through {to}) — nothing to fetch")
        log(con, frm, to, 0, 0, _total(con), "no_new_data")
        return 0

    print(f"AMFI NAV collect {frm} -> {to}  "
          f"({(to - frm).days + 1} days, {CHUNK_DAYS}-day chunks)")
    total_app = total_schemes = 0
    failures = []
    for c_frm, c_to in months(frm, to):
        try:
            df = parse(fetch(c_frm, c_to))
        except Exception as e:                        # noqa: BLE001
            print(f"  {c_frm}..{c_to}  FETCH FAILED — {str(e)[:90]}")
            failures.append(f"{c_frm}:{str(e)[:60]}")
            continue
        if df.empty:
            print(f"  {c_frm}..{c_to}  no rows (holiday window?)")
            continue
        n_s = df.scheme_code.nunique()
        if a.dry_run:
            print(f"  {c_frm}..{c_to}  parsed {len(df):>7,} rows · {n_s:,} schemes "
                  f"· plans {df.plan.value_counts().to_dict()} "
                  f"· options {df['option'].value_counts().to_dict()}  [DRY RUN]")
        else:
            app = upsert(con, df)
            total_app += app
            print(f"  {c_frm}..{c_to}  parsed {len(df):>7,} · appended {app:>7,} "
                  f"· {n_s:,} schemes")
        total_schemes = max(total_schemes, n_s)
        time.sleep(SLEEP_S)

    if a.dry_run:
        print("DRY RUN — nothing written")
        return 0

    tot = _total(con)
    st = "failed" if failures and not total_app else ("partial" if failures else "ok")
    log(con, frm, to, total_schemes, total_app, tot, st, "; ".join(failures))
    print(f"\nappended {total_app:,} rows · panel now {tot:,} rows · status {st}")
    if failures:
        print(f"  ⚠ {len(failures)} chunk(s) failed — re-run to fill "
              f"(append-only, so a re-run is safe)")
    return 0


def _total(con) -> int:
    with con.cursor() as cur:
        cur.execute(f'SELECT count(*) FROM "{SCHEMA}".nav')
        return cur.fetchone()[0]


if __name__ == "__main__":
    sys.exit(main())
