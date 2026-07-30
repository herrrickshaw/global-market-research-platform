#!/usr/bin/env python3
"""
nse_index_history.py — official NSE index levels + valuations into the warehouse.

WHY (2026-07-28). Comparing active funds to their OWN segment is the only
honest test of manager skill — a mid-cap fund beating Nifty-50 is mostly the
mid-cap segment beating large caps, not the manager. That test was capped at
4.6 years because the only per-segment benchmarks available were index FUNDS,
and Indian mid-cap index funds start 2020-10 while Nifty-500 index funds start
2023-05. On that short, exceptionally bullish window mid-cap active showed
+4.95pp of alpha with 87% of funds beating — a number nobody should act on
without a full cycle behind it.

The indices themselves go back much further. archives.nseindia.com publishes a
daily snapshot of EVERY index — verified reachable here back to at least
2016-04, same 13-column format throughout, with the index count growing 65 ->
109 as new indices launched.

WHAT THIS ADDS BEYOND LEVELS. The file carries **P/E, P/B and dividend yield per
index per day**. The platform currently has no segment-level valuation history
at all, so this is the input a valuation-timing or mean-reversion study would
need and has never had.

WHY THE DAILY ARCHIVE RATHER THAN niftyindices.com/reports/monthly-reports:
both are reachable, but monthly is 12 observations a year against ~250, and the
monthly reports are per-index PDFs/XLS requiring separate parsing per index
family. The daily CSV is one uniform request covering all indices at once.

NON-TRADING DAYS. A 404 means the market was shut; those dates are recorded in
a dead-date cache so a re-run never re-requests them — the same pattern the
bhavcopy fetcher uses. Without it, a decade of weekends is ~1,000 wasted
requests on every incremental run.

Usage — any python3 with pandas + duckdb (/usr/bin/python3 works; no yfinance):
  python3 scripts/nse_index_history.py --backfill-years 10
  python3 scripts/nse_index_history.py                    # incremental
  python3 scripts/nse_index_history.py --status
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import pg_client

DSN = "dbname=market_data host=/tmp user=umashankar"
SCHEMA = "indices"
URL = "https://archives.nseindia.com/content/indices/ind_close_all_{d}.csv"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
DEAD = Path.home() / ".local" / "state" / "nse_index_dead_dates.txt"
WORKERS = 6
EPOCH = dt.date(2016, 4, 1)

# Native Postgres DDL for pg_client.ensure_schema() — no `pg.` ATTACH-alias
# prefix, Postgres type names (DOUBLE PRECISION not DuckDB's bare DOUBLE).
DDL = f"""
CREATE SCHEMA IF NOT EXISTS "{SCHEMA}";
CREATE TABLE IF NOT EXISTS "{SCHEMA}".nse_daily (
  index_name VARCHAR, index_date DATE, open DOUBLE PRECISION,
  high DOUBLE PRECISION, low DOUBLE PRECISION, close DOUBLE PRECISION,
  points_change DOUBLE PRECISION, change_pct DOUBLE PRECISION,
  volume DOUBLE PRECISION, turnover_cr DOUBLE PRECISION,
  pe DOUBLE PRECISION, pb DOUBLE PRECISION, div_yield DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS "{SCHEMA}".ingest_log (
  run_at TIMESTAMP, frm DATE, to_ DATE, dates_fetched BIGINT,
  rows_appended BIGINT, total_rows BIGINT, status VARCHAR, detail VARCHAR
);
CREATE UNIQUE INDEX IF NOT EXISTS nse_daily_pk
  ON "{SCHEMA}".nse_daily (index_name, index_date);
CREATE INDEX IF NOT EXISTS nse_daily_date_ix ON "{SCHEMA}".nse_daily (index_date);
"""

COLMAP = {
    "Index Name": "index_name", "Index Date": "index_date",
    "Open Index Value": "open", "High Index Value": "high",
    "Low Index Value": "low", "Closing Index Value": "close",
    "Points Change": "points_change", "Change(%)": "change_pct",
    "Volume": "volume", "Turnover (Rs. Cr.)": "turnover_cr",
    "P/E": "pe", "P/B": "pb", "Div Yield": "div_yield",
}


def load_dead() -> set[str]:
    return set(DEAD.read_text().split()) if DEAD.exists() else set()


def save_dead(dead: set[str]) -> None:
    DEAD.parent.mkdir(parents=True, exist_ok=True)
    DEAD.write_text("\n".join(sorted(dead)))


def fetch_day(d: dt.date):
    """(date, DataFrame) on success · (date, None) when the market was shut ·
    raises only when the request itself failed, so a network problem is never
    mistaken for a holiday and cached as dead."""
    key = d.strftime("%d%m%Y")
    req = urllib.request.Request(URL.format(d=key), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return d, None                      # genuine non-trading day
        raise
    if "Index Name" not in body[:200]:
        return d, None
    df = pd.read_csv(io.StringIO(body))
    df = df.rename(columns={k: v for k, v in COLMAP.items() if k in df.columns})
    keep = [c for c in COLMAP.values() if c in df.columns]
    df = df[keep].copy()
    df["index_date"] = pd.to_datetime(df.index_date, format="%d-%m-%Y",
                                      errors="coerce").dt.date
    for c in keep:
        if c not in ("index_name", "index_date"):
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "", regex=False),
                                  errors="coerce")
    return d, df.dropna(subset=["index_name", "index_date"])


def connect():
    pg_client.connect()
    pg_client.ensure_schema([s.strip() for s in DDL.split(";") if s.strip()])
    return pg_client.get_connection()


def total(con) -> int:
    with con.cursor() as cur:
        cur.execute(f'SELECT count(*) FROM "{SCHEMA}".nse_daily')
        return cur.fetchone()[0]


def upsert(con, df: pd.DataFrame) -> int:
    """Anti-join in pandas (was a DuckDB LEFT JOIN against the attached
    table): keyed on the fetched data's own index_name/index_date, never a
    request string — see nse_index_tri.py's migration for why that matters."""
    df = df.drop_duplicates(["index_name", "index_date"], keep="last")
    with con.cursor() as cur:
        cur.execute(
            f'SELECT index_name, index_date FROM "{SCHEMA}".nse_daily '
            "WHERE index_name = ANY(%s)",
            (list(df.index_name.unique()),),
        )
        have = set(cur.fetchall())
    key = list(zip(df.index_name, df.index_date))
    novel = df[[k not in have for k in key]]
    n = len(novel)
    if n:
        cols = list(df.columns)
        rows = [tuple(None if v != v else v for v in r)   # NaN -> NULL
                for r in novel[cols].itertuples(index=False, name=None)]
        pg_client.append_rows(SCHEMA, "nse_daily", cols, rows)
    return n


def status(con) -> int:
    with con.cursor() as cur:
        cur.execute(f'SELECT count(*), min(index_date), max(index_date) '
                    f'FROM "{SCHEMA}".nse_daily')
        n, mn, mx = cur.fetchone()
    print(f"\n=== NSE INDEX PANEL ===\n  rows: {n:,}\n  range: {mn} -> {mx}")
    if not n:
        return 0
    with con.cursor() as cur:
        cur.execute(f'SELECT count(DISTINCT index_name) FROM "{SCHEMA}".nse_daily')
        n_idx = cur.fetchone()[0]
    print(f"  indices: {n_idx}")
    with con.cursor() as cur:
        cur.execute(f"""
            SELECT index_name, count(*) d, min(index_date) f, max(index_date) l,
                   avg(pe) FILTER (WHERE pe > 0) ape
            FROM "{SCHEMA}".nse_daily
            WHERE index_name IN ('Nifty 50','Nifty Midcap 150','Nifty Smallcap 250',
                                 'Nifty 500','Nifty Next 50')
            GROUP BY 1 ORDER BY 2 DESC""")
        rows = cur.fetchall()
    print("\n  KEY BENCHMARKS (the segment bars the fund comparison needs)")
    for nm, dd, f, l, ape in rows:
        print(f"    {nm:22s} {dd:>5,} days  {f} -> {l}  avg P/E {ape or 0:.1f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill-years", type=float)
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to", dest="to")
    ap.add_argument("--status", action="store_true")
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
        with con.cursor() as cur:
            cur.execute(f'SELECT max(index_date) FROM "{SCHEMA}".nse_daily')
            mx = cur.fetchone()[0]
        frm = (mx + dt.timedelta(days=1)) if mx else today - dt.timedelta(days=30)
    frm = max(frm, EPOCH)
    to = dt.date.fromisoformat(a.to) if a.to else today
    if frm > to:
        print(f"already current through {to}")
        return 0

    dead = load_dead()
    days = [frm + dt.timedelta(days=i) for i in range((to - frm).days + 1)]
    days = [d for d in days if d.weekday() < 5 and d.isoformat() not in dead]
    print(f"NSE index history {frm} -> {to} · {len(days)} candidate trading days "
          f"({len(dead)} known non-trading dates skipped)")

    appended = fetched = 0
    new_dead, failed = set(), []
    batch = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_day, d): d for d in days}
        for k, f in enumerate(as_completed(futs), 1):
            try:
                d, df = f.result()
            except Exception as e:                        # noqa: BLE001
                failed.append(f"{futs[f]}:{str(e)[:40]}")
                continue
            if df is None or df.empty:
                new_dead.add(d.isoformat())
                continue
            batch.append(df)
            fetched += 1
            if len(batch) >= 40:
                appended += upsert(con, pd.concat(batch, ignore_index=True))
                batch = []
                print(f"  {k}/{len(days)} · {fetched} trading days · "
                      f"{appended:,} rows appended", flush=True)
    if batch:
        appended += upsert(con, pd.concat(batch, ignore_index=True))

    save_dead(dead | new_dead)
    tot = total(con)
    st = "partial" if failed else "ok"
    pg_client.append_rows(
        SCHEMA, "ingest_log",
        ["run_at", "frm", "to_", "dates_fetched", "rows_appended", "total_rows",
         "status", "detail"],
        [(dt.datetime.now(), frm, to, fetched, appended, tot, st,
          "; ".join(failed[:5]))],
    )
    print(f"\n{fetched} trading days · appended {appended:,} · panel {tot:,} rows")
    if failed:
        print(f"  ⚠ {len(failed)} request(s) FAILED (not cached as holidays) — "
              f"re-run to fill")
    return 0


if __name__ == "__main__":
    sys.exit(main())
