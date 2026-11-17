#!/usr/bin/env python3
"""
collect_india_industry.py — per-ticker India sector/industry (closes E-005).

WHAT WAS ACTUALLY MISSING. Not a collector — the plumbing already existed end to
end. fetchers/providers/yahoo.py returns sector and industry, multi_source merges
them (its early-stop even tests for `sector`), quote_updater writes them, and
Cassandra stock_quotes has both columns. The data was simply never collected for
India, because Phase 2 of bulk_fetcher is documented as "run occasionally, not
daily" and costs 1-3h for the full universe. Coverage measured 2026-08-17:
189 of 3,484 India rows (5.4%).

That mattered because backtest_pe_anomalies ranks PE *within industry*
(MIN_IND=8 names per industry per month). With industry null the screen still
runs and still prints quintile spreads — they are just spreads over one
undifferentiated bucket, which is a different and much weaker claim than the one
the output appears to make. A silent wrong answer, not a crash.

🔴 SCOPE IS THE PARQUET, NOT THE UNIVERSE. The backtest reads 1,459 distinct
tickers; Cassandra holds 3,484. Collecting only what the consumer needs turns a
1-3h job into ~20 minutes. Pass --all to widen it to the Cassandra universe.

🔴 NARROW WRITES ONLY. Cassandra updates touch sector and industry and nothing
else. Going through upsert_quotes would rewrite every value column from a frame
that has none of them, blanking pe/roe/cmp for 1,459 names — the same
partial-row hazard as E-030, and the reason this does not reuse that path.

    python3 collect_india_industry.py --dry-run     # show what would be fetched
    python3 collect_india_industry.py               # collect + write PG (+Cassandra)
    python3 collect_india_industry.py --enrich      # write industry into the parquet
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")

FUND = os.environ.get(
    "MARKET_FUND_IN",
    os.path.expanduser("~/.cache/market-warehouse/fundamentals_history/"
                       "IN_screener_only_backup.parquet"))
DB = "market_data"
TABLE = "fundamentals.india_industry"

DDL = f"""
CREATE SCHEMA IF NOT EXISTS fundamentals;
CREATE TABLE IF NOT EXISTS {TABLE} (
    ticker      text PRIMARY KEY,   -- bare NSE symbol, as the parquet keys it
    yf_symbol   text,               -- what actually resolved (.NS or .BO)
    sector      text,
    industry    text,
    source      text,
    fetched_at  timestamptz DEFAULT now()
);
"""


def log(m: str) -> None:
    print(f"{dt.datetime.now():%H:%M:%S}  {m}", flush=True)


def psql(sql: str, fetch: bool = False) -> str:
    r = subprocess.run(["psql", "-d", DB, "-tAq", "-v", "ON_ERROR_STOP=1", "-c", sql],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"psql: {r.stderr.strip()[:300]}")
    return r.stdout.strip() if fetch else ""


def q(v) -> str:
    if v is None or v == "":
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


# ── fetch ────────────────────────────────────────────────────────────────────

class Throttled(Exception):
    """Yahoo said 429. NOT the same as 'this company has no industry'."""


def fetch_one(ticker: str, tries: int = 3) -> dict:
    """sector/industry for one bare symbol.

    Tries .NS then .BO. A numeric ticker is a BSE scrip code — those never
    resolve on .NS, so trying it first would burn a request and a retry on every
    one of them. Ordering the attempts by what the ticker looks like is the
    difference between ~20 minutes and ~40.

    🔴 A THROTTLE IS NOT A MISS, AND CONFLATING THEM CORRUPTS THE OUTPUT. The
    first version of this caught bare Exception and returned a null-industry row,
    so when Yahoo started 429-ing at roughly the 1,000th ticker every remaining
    name was recorded as "no industry available". The tell was in the counters:
    `resolved` froze at 976 while `miss` climbed by exactly the batch size and
    throughput ACCELERATED — failures returning faster than data. Those rows
    would then have been enriched into the parquet as genuinely-null industries,
    silently shrinking the within-industry universe the screen ranks on.
    Rate-limit now raises, so the caller can back off and the ticker stays
    unrecorded (and therefore retried) rather than being recorded as absent.
    """
    import yfinance as yf
    order = (".BO", ".NS") if str(ticker).isdigit() else (".NS", ".BO")
    for attempt in range(tries):
        throttled = False
        for suffix in order:
            sym = f"{ticker}{suffix}"
            try:
                info = yf.Ticker(sym).info or {}
            except Exception as exc:                               # noqa: BLE001
                if "ratelimit" in type(exc).__name__.lower() or "Too Many" in str(exc):
                    throttled = True
                    break
                continue
            sec, ind = info.get("sector"), info.get("industry")
            if sec or ind:
                return {"ticker": ticker, "yf_symbol": sym, "sector": sec,
                        "industry": ind, "source": "yfinance"}
        if not throttled:
            # Every suffix answered and none carried a classification: a real
            # miss (delisted, BSE-only code Yahoo does not cover, etc.).
            return {"ticker": ticker, "yf_symbol": None, "sector": None,
                    "industry": None, "source": "yfinance:miss"}
        if attempt < tries - 1:
            time.sleep(20 * (attempt + 1))
    raise Throttled(ticker)


def targets(use_all: bool) -> list[str]:
    if use_all:
        sys.path.insert(0, os.path.expanduser("~/backend"))
        from db import cassandra_client as cass
        if not cass.connect():
            raise RuntimeError("Cassandra unreachable and --all requested")
        rows = cass.session().execute(
            "SELECT yf_ticker FROM herrrickshaw.stock_quotes WHERE market='india'")
        return sorted({r.yf_ticker for r in rows})
    import pandas as pd
    return sorted(pd.read_parquet(FUND).ticker.astype(str).str.upper().unique())


def already_done() -> set[str]:
    """Resume support. A run that dies at ticker 900 must not re-fetch 1-899:
    that is 15 minutes of somebody else's rate limit for no new information."""
    try:
        out = psql(f"SELECT ticker FROM {TABLE} WHERE industry IS NOT NULL", fetch=True)
        return set(out.splitlines()) if out else set()
    except Exception:
        return set()


def write_pg(rows: list[dict]) -> int:
    vals = ",".join(
        f"({q(r['ticker'])},{q(r['yf_symbol'])},{q(r['sector'])},"
        f"{q(r['industry'])},{q(r['source'])},now())" for r in rows)
    psql(f"INSERT INTO {TABLE} (ticker,yf_symbol,sector,industry,source,fetched_at) "
         f"VALUES {vals} ON CONFLICT (ticker) DO UPDATE SET "
         f"yf_symbol=EXCLUDED.yf_symbol, sector=EXCLUDED.sector, "
         f"industry=EXCLUDED.industry, source=EXCLUDED.source, "
         f"fetched_at=EXCLUDED.fetched_at")
    return len(rows)


def write_cassandra(rows: list[dict]) -> int:
    """Narrow UPDATE — sector and industry only. See the module note."""
    sys.path.insert(0, os.path.expanduser("~/backend"))
    try:
        from db import cassandra_client as cass
        if not cass.connect():
            log("  Cassandra unreachable — PG copy is still authoritative, skipping")
            return 0
        s = cass.session()
        stmt = s.prepare("UPDATE herrrickshaw.stock_quotes SET sector=?, industry=? "
                         "WHERE market=? AND yf_ticker=?")
        n = 0
        for r in rows:
            if not (r["sector"] or r["industry"]):
                continue
            s.execute(stmt, (r["sector"], r["industry"], "india", r["ticker"]))
            n += 1
        return n
    except Exception as exc:                                       # noqa: BLE001
        log(f"  Cassandra write skipped: {type(exc).__name__}: {str(exc)[:100]}")
        return 0


def enrich_parquet() -> None:
    """Fill the parquet's industry column from the canonical PG table.

    Kept as a separate step, not folded into the collect: the parquet is the
    E-004 reconstruction and rewriting it is the one destructive act here, so it
    should be an explicit choice rather than a side effect of a network job that
    might have half-failed.
    """
    import pandas as pd
    out = psql(f"SELECT ticker||'\t'||coalesce(industry,'') FROM {TABLE} "
               f"WHERE industry IS NOT NULL", fetch=True)
    if not out:
        log("🔴 nothing in the table yet — collect first"); return
    m = dict(l.split("\t", 1) for l in out.splitlines() if "\t" in l)
    d = pd.read_parquet(FUND)
    before = d.industry.notna().sum()
    d["industry"] = d.ticker.astype(str).str.upper().map(m)
    after = d.industry.notna().sum()
    bak = FUND + ".pre_industry"
    if not os.path.exists(bak):
        pd.read_parquet(FUND).to_parquet(bak, compression="zstd")
        log(f"  kept a pre-write copy at {os.path.basename(bak)}")
    d.to_parquet(FUND, compression="zstd", index=False)
    log(f"  parquet industry: {before:,} -> {after:,} of {len(d):,} rows "
        f"({after/len(d)*100:.1f}%), {d.ticker.nunique():,} tickers")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--all", action="store_true", help="Cassandra universe, not just the parquet's")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--enrich", action="store_true", help="write industry into the parquet and exit")
    p.add_argument("--workers", type=int, default=6,
                   help="keep modest: yfinance throttles, and this shares a limit "
                        "with the daily brief's validation calls (default 6)")
    p.add_argument("--limit", type=int, default=0, help="stop after N (for a smoke test)")
    a = p.parse_args()

    psql(DDL)
    if a.enrich:
        enrich_parquet(); return 0

    want = targets(a.all)
    done = already_done()
    todo = [t for t in want if t not in done]
    if a.limit:
        todo = todo[:a.limit]
    log(f"{len(want):,} tickers in scope, {len(done):,} already collected, "
        f"{len(todo):,} to fetch")
    if a.dry_run:
        log(f"dry-run — first 10: {todo[:10]}")
        return 0
    if not todo:
        log("nothing to do"); return 0

    t0, got, miss, throttled, batch = time.time(), 0, 0, 0, []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(fetch_one, t): t for t in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                r = fut.result()
            except Throttled:
                # Deliberately NOT written: an unrecorded ticker is retried on
                # the next run, whereas a null-industry row would look collected.
                throttled += 1
                continue
            except Exception:
                miss += 1
                continue
            batch.append(r)
            got += 1 if r["industry"] else 0
            miss += 0 if r["industry"] else 1
            # Flush in batches so a crash keeps its progress — the resume query
            # reads PG, so anything unflushed is re-fetched.
            if len(batch) >= 100:
                write_pg(batch); batch = []
                log(f"  {i}/{len(todo)}  resolved={got} miss={miss} "
                    f"throttled={throttled} ({i/(time.time()-t0):.1f}/s)")
            # Bail out rather than grind: once Yahoo is refusing in bulk, every
            # further request deepens the block and returns nothing.
            if throttled >= 25:
                log(f"🔴 {throttled} tickers rate-limited — stopping. "
                    f"{len(todo) - i:,} not attempted; re-run later to resume.")
                for f in futs:
                    f.cancel()
                break
    if batch:
        write_pg(batch)
    if throttled:
        log(f"⚠️  {throttled} left UNRECORDED so they are retried, not "
            f"mistaken for companies without an industry")

    log(f"collected {got:,} with industry, {miss:,} without, in {time.time()-t0:.0f}s")

    # Read back from PG rather than keeping the rows in memory: batches are
    # flushed and cleared as we go (so a crash keeps its progress), which means
    # the in-process list is not the full set. PG is the record here.
    back = psql(f"SELECT ticker||'\t'||coalesce(sector,'')||'\t'||coalesce(industry,'') "
                f"FROM {TABLE} WHERE industry IS NOT NULL", fetch=True)
    rows = []
    for line in back.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            rows.append({"ticker": parts[0], "sector": parts[1] or None,
                         "industry": parts[2] or None})
    log(f"mirrored {write_cassandra(rows):,} rows into Cassandra (sector/industry only)")

    cov = psql(f"SELECT count(*)||' rows, '||count(industry)||' with industry, '"
               f"||count(distinct industry)||' distinct' FROM {TABLE}", fetch=True)
    log(f"{TABLE}: {cov}")
    log("next: --enrich to write it into the parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
