#!/usr/bin/env python3
"""
Daily market ingest — append-only, per-geography, with a freshness ledger.

WHY: the pipeline re-scans each market from scratch every day and drops a
timestamped workbook (us_full_scan_20260714_1205.xlsx). Nothing accumulates: each
run's data is a fresh snapshot that overwrites nothing and is appended nowhere, so
there is no per-market history and no record of *when* each geography last got
real data. This script fixes both.

MODEL
  * India   -> true OHLCV time series (NSE/BSE bhavcopy), appended by trade_date.
               Lives in Postgres  bhavcopy.*  (see scripts/bhavcopy_to_db.py).
               ALSO snapshotted from its scan workbook like the other markets, so
               the per-ticker ledger has one uniform shape across geographies.
  * US/EU/JP/KR -> the scans emit a point-in-time snapshot (Symbol, Name, LTP,
               Prev_Close, Change%, Darvas_Signal) with the date only in the
               filename. Each day's snapshot is appended as dated rows to
               market_daily.snapshots, building the history the scans never kept.
               ALL workbook dates not yet in the table are backfilled — a gap in
               ingest runs no longer loses the intervening days.

APPEND-ONLY + IDEMPOTENT: a market/date already present is never re-inserted, so
re-running the routine any number of times a day appends 0 rows.

LEDGER: every run writes market_daily.ingest_log (run_at, market, source,
last_data_date, rows_appended, total_rows, status). Two read surfaces:
  * market_daily.freshness / --status  -> per-MARKET "when did it last get data?"
  * market_daily.ticker_freshness / --tickers -> per-TICKER (ticker, name,
    market, last_update) — the routine check. Names come from the workbook when
    it has a Name column (EU/JP/KR) and from market_daily.symbol_names
    (refreshed each run from symbol_master.parquet) otherwise.

Usage:
    python3 scripts/market_ingest.py                 # ingest all markets, then print status
    python3 scripts/market_ingest.py --status        # just the market-wise freshness table
    python3 scripts/market_ingest.py --tickers       # per-ticker: ticker, name, market, last update
    python3 scripts/market_ingest.py --tickers --market japan --limit 40
    python3 scripts/market_ingest.py --csv out.csv   # export the per-ticker ledger for extraction
    python3 scripts/market_ingest.py --market us     # ingest one geography
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

import psycopg2.extras

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import pg_client

HOME = Path("/Users/umashankar")
# The pipeline migrated out of ~/Downloads on 2026-07-16; honor an env override.
PF = Path(os.environ.get("MARKET_PIPELINE_DIR",
                         str(HOME / "market-pipeline" / "code" / "python_files")))
# Live tree, NOT ~/Downloads: launchd is TCC-denied all of ~/Downloads (the
# pipeline's founding failure mode) — the 2026-07-23 00:30 run tracebacked
# right here reading the Downloads copy. symbol_master.py writes to
# MARKET_CACHE; read the same tree it writes.
SYMBOL_MASTER = Path(os.environ.get(
    "MARKET_CACHE", str(HOME / "market-pipeline" / "market_cache"))) / "symbol_master.parquet"
DSN = "dbname=market_data host=/tmp user=umashankar"
SCHEMA = "market_daily"

# market -> (geography label, scan dir, filename glob)
SNAPSHOT_MARKETS = {
    "india":  ("India (NSE/BSE bhavcopy)",     "indian_full_scan", "indian_full_scan_*.xlsx"),
    "us":     ("United States (NASDAQ/NYSE)",  "us_full_scan",     "us_full_scan_*.xlsx"),
    "europe": ("Europe (17 exchanges)",        "european_scan",    "european_market_scan*.xlsx"),
    "japan":  ("Japan (TSE)",                  "japan_scan",       "japan_market_scan_*.xlsx"),
    "korea":  ("Korea (KOSPI/KOSDAQ)",         "korea_scan",       "korea_market_scan_*.xlsx"),
}
INDIA_LABEL = SNAPSHOT_MARKETS["india"][0]

# Native Postgres DDL for pg_client.ensure_schema() — no `pg.` ATTACH-alias
# prefix (psycopg2 talks to Postgres directly) and Postgres type names
# (DOUBLE PRECISION, not DuckDB's bare DOUBLE). Combines the old DDL (run via
# duckdb's attached-catalog side) and PG_SETUP (run via postgres_execute on
# the native side, since duckdb's pg extension couldn't CREATE VIEW/ALTER on
# the attached side) into one statement list — psycopg2 has no such split.
DDL = f"""
CREATE SCHEMA IF NOT EXISTS "{SCHEMA}";
CREATE TABLE IF NOT EXISTS "{SCHEMA}".snapshots (
  market VARCHAR, as_of_date DATE, symbol VARCHAR, ltp DOUBLE PRECISION,
  prev_close DOUBLE PRECISION, change_pct DOUBLE PRECISION, darvas_signal VARCHAR,
  source_file VARCHAR, name VARCHAR
);
CREATE TABLE IF NOT EXISTS "{SCHEMA}".ingest_log (
  run_at TIMESTAMP, market VARCHAR, geography VARCHAR, source VARCHAR,
  last_data_date DATE, rows_appended BIGINT, total_rows BIGINT,
  status VARCHAR, detail VARCHAR
);
ALTER TABLE "{SCHEMA}".snapshots ADD COLUMN IF NOT EXISTS name varchar;
CREATE TABLE IF NOT EXISTS "{SCHEMA}".symbol_names (
  symbol varchar PRIMARY KEY, name varchar, exchange varchar);
CREATE OR REPLACE VIEW "{SCHEMA}".ticker_freshness AS
WITH snap AS (
  SELECT market, symbol, name, as_of_date,
         row_number() OVER (PARTITION BY market, symbol ORDER BY as_of_date DESC) rn
  FROM "{SCHEMA}".snapshots
  WHERE market <> 'india'
),
india AS (
  -- India's truth is the bhavcopy OHLCV series, not the scan snapshot: it covers
  -- the full ~5k-symbol universe with real trade dates.
  SELECT symbol, max(trade_date) AS last_update
  FROM bhavcopy.cleaned_ohlcv GROUP BY symbol
)
SELECT s.market, s.symbol AS ticker,
       COALESCE(NULLIF(NULLIF(s.name, 'nan'), 'None'), n.name) AS name,
       s.as_of_date AS last_update
FROM snap s LEFT JOIN "{SCHEMA}".symbol_names n ON n.symbol = s.symbol
WHERE s.rn = 1
UNION ALL
SELECT 'india', i.symbol, n.name, i.last_update
FROM india i LEFT JOIN "{SCHEMA}".symbol_names n ON n.symbol = i.symbol;
"""


def connect():
    pg_client.connect()
    pg_client.ensure_schema([s.strip() for s in DDL.split(";") if s.strip()])
    return pg_client.get_connection()


def refresh_symbol_names(con) -> None:
    """Refresh the symbol->name lookup from symbol_master.parquet (dedup, NSE first)."""
    if not SYMBOL_MASTER.exists():
        return
    import pandas as pd
    df = pd.read_parquet(SYMBOL_MASTER)
    df = df[df.symbol.notna() & df.name.notna()].copy()
    rank = {"NSE": 0, "BSE": 1}
    df["_rn"] = df["exchange"].map(lambda e: rank.get(e, 2))
    df = df.sort_values("_rn").drop_duplicates("symbol", keep="first")
    rows = list(df[["symbol", "name", "exchange"]].itertuples(index=False, name=None))
    pg_client.delete_and_insert(SCHEMA, "symbol_names", "", (), rows,
                                ["symbol", "name", "exchange"], truncate=True)


def _date_from_name(p: Path) -> dt.date | None:
    m = re.search(r"(20\d{6})", p.name)
    return dt.datetime.strptime(m.group(1), "%Y%m%d").date() if m else None


def log(con, market, geo, source, last_date, appended, total, status, detail=""):
    pg_client.append_rows(
        SCHEMA, "ingest_log",
        ["run_at", "market", "geography", "source", "last_data_date",
         "rows_appended", "total_rows", "status", "detail"],
        [(dt.datetime.now(), market, geo, source, last_date, appended, total, status, detail)],
    )


def ingest_india(con) -> None:
    """India already has a real OHLCV series; record its true high-water mark."""
    try:
        with con.cursor() as cur:
            cur.execute("SELECT count(*) FROM bhavcopy.bhavcopy_ohlcv")
            n = cur.fetchone()[0]
            cur.execute("SELECT max(trade_date) FROM bhavcopy.bhavcopy_ohlcv")
            mx = cur.fetchone()[0]
    except Exception as e:
        con.rollback()   # a failed statement poisons the whole transaction until rolled back
        log(con, "india", INDIA_LABEL, "bhavcopy", None, 0, 0, "failed", str(e)[:180])
        print(f"  india    FAILED  {str(e)[:70]}")
        return
    with con.cursor() as cur:
        cur.execute(
            f"""SELECT max(last_data_date) FROM "{SCHEMA}".ingest_log
                WHERE market='india' AND status<>'failed'"""
        )
        prev = cur.fetchone()[0]
    status = "ok" if (prev is None or mx > prev) else "no_new_data"
    log(con, "india", INDIA_LABEL, "bhavcopy", mx, 0, n, status,
        "append handled by scripts/bhavcopy_to_db.py --incremental")
    print(f"  india    {status:12s} last_data={mx}  total_rows={n:,}")


def _load_snapshot_file(con, market: str, geo: str, f: Path, as_of: dt.date) -> int:
    """Read one workbook's All_Stocks sheet and append it as dated rows."""
    import pandas as pd
    df = pd.read_excel(f, sheet_name="All_Stocks")

    # Column encodings diverge per market — the same divergence already documented
    # for the Darvas sheets. US/India: Symbol/LTP/Prev_Close/Darvas_Signal (no
    # Name). Europe: Symbol/Name/LTP. Japan: YF_Ticker/Code/Name/LTP_JPY +
    # Trend_Signal. Korea: Code/Name/YF_Ticker/LTP_KRW + Trend_Signal. Take the
    # first column that exists; missing ones become all-NULL rather than crashing.
    def col(*names):
        for n in names:
            if n in df.columns:
                return df[n]
        return None

    def num(*names):
        c = col(*names)
        return pd.to_numeric(c, errors="coerce") if c is not None else pd.Series([None] * len(df))

    def text(*names):
        c = col(*names)
        return c.astype(str) if c is not None else pd.Series([None] * len(df))

    sym = col("Symbol", "YF_Ticker", "Code")
    if sym is None:
        raise ValueError(f"no symbol column; got {list(df.columns)[:8]}")

    out = pd.DataFrame({
        "market": market,
        "as_of_date": as_of,
        "symbol": sym.astype(str),
        "ltp": num("LTP", "LTP_JPY", "LTP_KRW", "LTP_EUR", "LTP_GBP"),
        "prev_close": num("Prev_Close", "Previous_Close"),
        "change_pct": num("Change%", "Change_%"),
        "darvas_signal": text("Darvas_Signal", "Trend_Signal"),
        "source_file": f.name,
        "name": text("Name", "Company", "Company_Name"),
    })
    cols = ["market", "as_of_date", "symbol", "ltp", "prev_close",
            "change_pct", "darvas_signal", "source_file", "name"]
    rows = [tuple(None if v != v else v for v in r)   # NaN -> NULL
            for r in out[cols].itertuples(index=False, name=None)]
    pg_client.append_rows(SCHEMA, "snapshots", cols, rows)
    return len(out)


def ingest_snapshot(con, market: str) -> None:
    """Append every workbook date not yet in the table (backfills ingest gaps)."""
    geo, sub, glob = SNAPSHOT_MARKETS[market]
    files = sorted((PF / sub).glob(glob))
    if not files:
        log(con, market, geo, sub, None, 0, 0, "missing", f"no workbook in {sub}/")
        print(f"  {market:8s} MISSING      no scan workbook in {sub}/")
        return

    # newest file per date, so an intraday re-run supersedes the 00:30 one
    by_date: dict[dt.date, Path] = {}
    for f in files:
        d = _date_from_name(f)
        if d is not None:
            by_date[d] = f
    if not by_date:
        log(con, market, geo, files[-1].name, None, 0, 0, "failed", "no date in filename")
        print(f"  {market:8s} FAILED       cannot parse dates in {sub}/")
        return

    with con.cursor() as cur:
        cur.execute(f'SELECT DISTINCT as_of_date FROM "{SCHEMA}".snapshots WHERE market=%s', (market,))
        have = {r[0] for r in cur.fetchall()}
    todo = sorted(d for d in by_date if d not in have)
    latest = max(by_date)

    appended = 0
    for d in todo:
        f = by_date[d]
        try:
            n = _load_snapshot_file(con, market, geo, f, d)
        except Exception as e:
            con.rollback()
            log(con, market, geo, f.name, d, 0, 0, "failed", str(e)[:180])
            print(f"  {market:8s} FAILED       {d}: {str(e)[:60]}")
            continue
        appended += n

    with con.cursor() as cur:
        cur.execute(f'SELECT count(*) FROM "{SCHEMA}".snapshots WHERE market=%s', (market,))
        total = cur.fetchone()[0]
    if appended:
        log(con, market, geo, by_date[latest].name, latest, appended, total, "ok",
            f"backfilled {len(todo)} date(s): {', '.join(str(d) for d in todo)}")
        print(f"  {market:8s} ok           last_data={latest}  "
              f"(+{appended:,} across {len(todo)} date(s), total {total:,})")
    else:
        log(con, market, geo, by_date[latest].name, latest, 0, total, "no_new_data",
            f"{latest} already ingested")
        print(f"  {market:8s} no_new_data  last_data={latest}  (+0, total {total:,})")


def status(con) -> None:
    with con.cursor() as cur:
        cur.execute(f"""
            SELECT market, geography, source, last_data_date, total_rows, status, run_at
            FROM (SELECT *, row_number() OVER (PARTITION BY market ORDER BY run_at DESC) rn
                  FROM "{SCHEMA}".ingest_log) t
            WHERE rn=1 ORDER BY market
        """)
        rows = cur.fetchall()
    today = dt.date.today()
    print(f"\n=== MARKET DATA FRESHNESS (as of {today}) ===")
    print(f"  {'MARKET':8s} {'GEOGRAPHY':32s} {'LAST DATA':11s} {'AGE':>4s} {'ROWS':>11s}  STATUS")
    for m, geo, _src, last, total, st, _run in rows:
        age = (today - last).days if last else None
        flag = "STALE" if (age is None or age > 4) else "fresh"
        print(f"  {m:8s} {(geo or '')[:32]:32s} {str(last):11s} {str(age)+'d' if age is not None else '  -':>4s} "
              f"{total or 0:>11,}  {st} [{flag}]")


def tickers(con, market: str, limit: int | None, csv_path: str | None) -> None:
    """The per-ticker routine check: ticker, name, market, date of last update."""
    import pandas as pd
    where = "" if market == "all" else f"WHERE market = '{market}'"
    q = f"""SELECT ticker, name, market, last_update
            FROM "{SCHEMA}".ticker_freshness {where}
            ORDER BY market, ticker"""
    if csv_path:
        pd.read_sql(q, con).to_csv(csv_path, index=False)
        with con.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM ({q}) t")
            n = cur.fetchone()[0]
        print(f"wrote {n:,} tickers -> {csv_path}")
        return
    with con.cursor() as cur:
        cur.execute(q + (f" LIMIT {limit}" if limit else ""))
        rows = cur.fetchall()
        cur.execute(f"SELECT count(*) FROM ({q}) t")
        total = cur.fetchone()[0]
    today = dt.date.today()
    print(f"\n=== PER-TICKER FRESHNESS ({total:,} tickers, as of {today}) ===")
    print(f"  {'TICKER':14s} {'NAME':40s} {'MARKET':8s} {'LAST UPDATE':11s} {'AGE':>4s}")
    for t, name, m, last in rows:
        age = (today - last).days if last else None
        print(f"  {t:14s} {(name or '')[:40]:40s} {m:8s} {str(last):11s} "
              f"{str(age)+'d' if age is not None else '  -':>4s}")
    if limit and total > limit:
        print(f"  … {total - limit:,} more (use --csv to export all)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="all",
                    choices=["all", "india", "us", "europe", "japan", "korea"])
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--tickers", action="store_true",
                    help="per-ticker ledger: ticker, name, market, last update")
    ap.add_argument("--limit", type=int, default=50, help="rows to print with --tickers")
    ap.add_argument("--csv", metavar="PATH",
                    help="export the per-ticker ledger to CSV (implies --tickers)")
    a = ap.parse_args()
    con = connect()
    if a.status:
        status(con); sys.exit(0)
    if a.tickers or a.csv:
        tickers(con, a.market, a.limit, a.csv); sys.exit(0)
    print("=== daily market ingest (append-only) ===")
    refresh_symbol_names(con)
    for m in SNAPSHOT_MARKETS:
        if a.market in ("all", m):
            ingest_snapshot(con, m)
    if a.market in ("all", "india"):
        ingest_india(con)   # last, so status shows the true OHLCV high-water mark
    status(con)
