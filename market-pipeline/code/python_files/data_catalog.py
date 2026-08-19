#!/usr/bin/env python3
"""
data_catalog.py — what data exists, where it lives, what it depends on, and
WHICH SESSION IT ACTUALLY CONTAINS.

WHY THIS MODULE EXISTS
──────────────────────
`warehouse_catalog.py` already answers "which file is authoritative for X". It
does not answer "is that file current, and what has to be refreshed first if it
is not". Those two questions are what actually break the pipeline:

  * 2026-08-19. THREE US price stores were at three different vintages at the
    same instant — `market_cache/ohlc/*.parquet` at 17 Aug (what the scan read),
    `bhavcopy_cache/ohlcv_US.parquet` at 14 Aug, and the warehouse panel at
    17 Aug — with nothing in the system comparing them to each other or to the
    session the NYSE had actually finished. The scan quoted 17 Aug closes into a
    19 Aug brief.
  * The same morning, `ohlcv_JAPAN.parquet` held a bar dated 19 Aug for a
    session that was still trading. A forming bar stored as a close.

So each dataset here declares four things a path alone cannot express:
    probe        read the session date OUT of the content
    depends_on   what must be current BEFORE this can be
    refresh      the command that brings it forward
    source       the credible attribution shown to the reader

MEDIAN, NOT MAX — THE MOST IMPORTANT DECISION IN THIS FILE
──────────────────────────────────────────────────────────
For a store made of many units (7,699 per-ticker parquets; 5,829 symbols in a
panel) the probe reports the MEDIAN symbol's last session, not the newest.

`market_ingest.py --status` used max-like logic and reported
`us … 2026-08-19, 0d, ok [fresh]` on a morning when two thirds of the universe
was two sessions behind: a handful of symbols refreshed, the maximum moved, and
the store was declared current. Staleness that affects 66% of symbols must not
be concealable by the 1% that succeeded. The median moves only when the bulk of
the store moves, which is the property actually being asserted.

`n_at_expected` is reported alongside it so a partial refresh is visible as a
partial refresh rather than rounded to pass or fail.

PROBES ARE CHEAP AND CONTENT-BASED. Never mtime — every incident above had a
correct mtime. Per-ticker stores are sampled over a fixed liquid list rather
than walked, so a probe costs milliseconds and can run on every mailer request.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import market_sessions as ms

# Paths resolve in data_registry — its contract is "import them from here, do
# not re-derive them", and the 2026-07-20 TCC outage was caused by exactly one
# module re-deriving MARKET_CACHE privately. This file adds a SESSION dimension
# on top of that registry; it does not fork its path knowledge.
import data_registry as R

HOME = Path.home()
PIPE = Path(__file__).resolve().parent
BHAV = R.BHAV_CACHE
MCACHE = R.MARKET_CACHE

# A fixed, deliberately liquid sample. Liquid names are the ones a reader acts
# on and the ones a broken refresh strands most visibly; they also always trade,
# so a missing bar is unambiguous rather than a thin-volume gap.
LIQUID = {
    "US": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM",
           "WMT", "UNH", "V", "TSLA"],
    "IN": ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "SBIN",
           "BHARTIARTL", "ITC", "LT", "AXISBANK"],
    "JP": ["7203.T", "6758.T", "9984.T", "8306.T", "6501.T", "7267.T"],
    "KR": ["005930.KS", "000660.KS", "051910.KS", "005380.KS", "035420.KS"],
    "EU": ["ASML.AS", "SAP.DE", "SHEL.L", "AZN.L", "MC.PA", "SIE.DE"],
    "CN": ["600519.SS", "601318.SS", "000858.SZ"],
}


@dataclass
class Probe:
    """What a store actually holds. `session` is the median unit's last bar."""
    session: dt.date | None
    n_units: int = 0
    n_at_expected: int = 0
    detail: str = ""
    error: str = ""


@dataclass
class Dataset:
    id: str
    kind: str                 # prices | scan | snapshot | brief
    market: str
    location: str
    source: str
    probe_fn: Callable[[], Probe] = field(repr=False)
    refresh: str | None = None
    depends_on: tuple[str, ...] = ()
    note: str = ""
    authority: str = "working"   # canonical | working | derived

    def probe(self) -> Probe:
        try:
            return self.probe_fn()
        except Exception as e:                       # a probe must never crash a send
            return Probe(None, error=f"{type(e).__name__}: {e}")


# ── probe primitives ──────────────────────────────────────────────────────────
def _duck():
    import duckdb

    return duckdb.connect()


def _median(dates: list[dt.date]) -> dt.date | None:
    if not dates:
        return None
    s = sorted(dates)
    return s[len(s) // 2]


def _probe_parquet(path: Path | str, date_col: str = "Date",
                   sym_col: str = "Symbol", market: str | None = None,
                   expected: dt.date | None = None) -> Probe:
    """Median last-bar date across symbols in a single long-format parquet."""
    p = str(path)
    if not glob.glob(p):
        return Probe(None, error=f"missing: {p}")
    con = _duck()
    cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{p}')").fetchall()]
    dc = next((c for c in cols if c.lower() == date_col.lower()), None)
    sc = next((c for c in cols if c.lower() == sym_col.lower()), None)
    if dc is None:
        return Probe(None, error=f"no '{date_col}' column in {p}")
    if sc is None:                                    # single-series file
        mx = con.execute(f'SELECT max("{dc}") FROM read_parquet(\'{p}\')').fetchone()[0]
        return Probe(_as_date(mx), 1, 1 if _as_date(mx) == expected else 0)
    rows = con.execute(
        f'SELECT "{sc}", max("{dc}") m FROM read_parquet(\'{p}\') GROUP BY 1'
    ).fetchall()
    dates = [_as_date(r[1]) for r in rows if r[1] is not None]
    med = _median(dates)
    at_exp = sum(1 for d in dates if expected and d >= expected)
    return Probe(med, len(dates), at_exp,
                 detail=f"{len(dates):,} symbols")


def _probe_per_ticker(dirpath: Path, market: str, expected: dt.date | None) -> Probe:
    """Median last bar over the LIQUID sample of a per-ticker parquet store.

    Sampled, not walked: 7,699 files is ~8s of stat+read, and this probe runs on
    every mailer request. The sample is fixed so the number is comparable day to
    day rather than drifting with whatever happened to be readable.
    """
    if not dirpath.exists():
        return Probe(None, error=f"missing: {dirpath}")
    con = _duck()
    dates: list[dt.date] = []
    missing: list[str] = []
    for t in LIQUID.get(market, []):
        f = dirpath / f"{t}.parquet"
        if not f.exists():
            missing.append(t)
            continue
        try:
            mx = con.execute(f"SELECT max(Date) FROM read_parquet('{f}')").fetchone()[0]
            if mx is not None:
                dates.append(_as_date(mx))
        except Exception:
            missing.append(t)
    if not dates:
        return Probe(None, error=f"no readable sample in {dirpath}")
    med = _median(dates)
    at_exp = sum(1 for d in dates if expected and d >= expected)
    d = f"{len(dates)}/{len(LIQUID.get(market, []))} liquid sampled"
    if missing:
        d += f", absent: {','.join(missing[:4])}"
    return Probe(med, len(dates), at_exp, detail=d)


def _probe_warehouse(market: str, expected: dt.date | None) -> Probe:
    try:
        import warehouse_paths as wh

        root = wh.root()
    except Exception as e:
        return Probe(None, error=f"warehouse unresolved: {e}")
    src = f"{root}/ohlcv/{market}/*.parquet"
    if not glob.glob(src):
        return Probe(None, error=f"missing: {src}")
    return _probe_parquet(src, "Date", "Symbol", market, expected)


def _probe_scan(market: str, expected: dt.date | None) -> Probe:
    """A scan's session is the session its PRICES describe, not its filename.

    This is the check that would have caught 2026-08-19 on its own. The workbook
    was named `..._20260819_0459.xlsx` and its mtime was that morning; its prices
    were 17 Aug closes. Filename and mtime both agreed with each other and both
    were wrong, so the session is recovered by matching the workbook's LTPs back
    against dated bars in the price store.
    """
    import pandas as pd

    pat, sym_col, px_col, suffix = SCAN_SPEC[market]
    files = sorted(glob.glob(str(PIPE / pat)))
    if not files:
        return Probe(None, error=f"no scan workbook: {pat}")
    latest = files[-1]
    df = pd.read_excel(latest, "All_Stocks")[[sym_col, px_col]].dropna()
    sample = [s for s in LIQUID.get(market, []) if s in set(df[sym_col].astype(str))]
    if not sample:
        return Probe(None, error=f"no liquid sample in {Path(latest).name}")
    px = {r[sym_col]: float(r[px_col]) for _, r in
          df[df[sym_col].astype(str).isin(sample)].iterrows()}

    store = PRICE_STORE_FOR[market]
    con = _duck()
    dates: list[dt.date] = []
    for t, v in px.items():
        d = _match_session(con, store, market, t, v)
        if d:
            dates.append(d)
    if not dates:
        return Probe(None, detail=f"{Path(latest).name}: prices unmatched in store",
                     error="cannot date scan prices against price store")
    med = _median(dates)
    at_exp = sum(1 for d in dates if expected and d >= expected)
    return Probe(med, len(dates), at_exp,
                 detail=f"{Path(latest).name}: {len(dates)}/{len(px)} priced-matched")


def _match_session(con, store: str, market: str, ticker: str, price: float
                   ) -> dt.date | None:
    """Newest session in `store` whose close equals `price` (to 0.05%)."""
    try:
        if store.endswith(".parquet") or "*" in store:
            src, sym = store, "Symbol"
        else:
            f = Path(store) / f"{ticker}.parquet"
            if not f.exists():
                return None
            src, sym = str(f), None
        where = f"AND \"{sym}\" = '{ticker}'" if sym else ""
        q = (f"SELECT max(Date) FROM read_parquet('{src}') "
             f"WHERE abs(Close - {price}) / nullif({price},0) < 0.0005 {where}")
        r = con.execute(q).fetchone()[0]
        return _as_date(r) if r is not None else None
    except Exception:
        return None


def _probe_pg_snapshots(market: str, expected: dt.date | None) -> Probe:
    """Postgres snapshots, judged by PRICE MOVEMENT rather than row presence.

    `market_daily.snapshots` carried 18 and 19 Aug rows for NVDA holding the
    17 Aug close. Row presence under a date stamp is not evidence that the date
    means anything, so this probe reports the newest as_of_date whose prices
    actually DIFFER from the prior date's. A carried-forward date is reported as
    the last date that moved.
    """
    label = PG_LABEL[market]
    sql = f"""
      WITH d AS (SELECT DISTINCT as_of_date FROM market_daily.snapshots
                 WHERE market='{label}' ORDER BY as_of_date DESC LIMIT 6),
      p AS (SELECT s.as_of_date, s.symbol, s.ltp,
                   lag(s.ltp) OVER (PARTITION BY s.symbol ORDER BY s.as_of_date) prev
            FROM market_daily.snapshots s JOIN d ON d.as_of_date = s.as_of_date
            WHERE s.market='{label}')
      SELECT as_of_date, count(*) n, sum(CASE WHEN prev IS NOT NULL AND ltp <> prev
                                              THEN 1 ELSE 0 END) moved
      FROM p GROUP BY 1 ORDER BY 1 DESC"""
    r = subprocess.run(["psql", "-d", "market_data", "--csv", "-c", sql],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return Probe(None, error=f"psql: {r.stderr.strip()[:120]}")
    lines = [l for l in r.stdout.strip().splitlines()[1:] if l]
    if not lines:
        return Probe(None, error=f"no snapshots for market={label}")
    stamped = dt.date.fromisoformat(lines[0].split(",")[0])
    moved_on = None
    for l in lines:
        d, n, moved = l.split(",")
        if int(moved or 0) > int(n or 1) * 0.2:      # a real session moves most prices
            moved_on = dt.date.fromisoformat(d)
            break
    eff = moved_on or stamped
    note = "" if eff == stamped else f"stamped {stamped} but prices last moved {eff}"
    return Probe(eff, 0, 1 if expected and eff >= expected else 0, detail=note)


FUND_MAX_AGE_DAYS = 30


def _probe_fundamentals(path: Path) -> Probe:
    """Fundamentals freshness = when the COLLECTOR last ran, per ticker.

    Deliberately not graded against a trading session: annual filings do not
    arrive daily, so a session comparison would report permanent staleness and
    train the operator to ignore the row. The median ticker's `collected_at` is
    the honest measure of whether the store is being maintained — median for the
    same reason as everywhere else here, so a handful of freshly-refetched names
    cannot carry a stale store.
    """
    if not path.exists():
        return Probe(None, error=f"missing: {path}")
    con = _duck()
    rows = con.execute(
        f"SELECT ticker, max(collected_at) c FROM read_parquet('{path}') GROUP BY 1"
    ).fetchall()
    if not rows:
        return Probe(None, error="store empty")
    stamps = sorted(str(r[1])[:10] for r in rows if r[1])
    if not stamps:
        return Probe(None, error="no collected_at stamps")
    med = dt.date.fromisoformat(stamps[len(stamps) // 2])
    age = (dt.date.today() - med).days
    n_fresh = sum(1 for s in stamps
                  if (dt.date.today() - dt.date.fromisoformat(s)).days <= FUND_MAX_AGE_DAYS)
    # The reported date is the median COLLECTION date, stated as such. It is not
    # massaged toward today to look current — data_state grades `fundamentals`
    # by collection age, not against a trading session.
    return Probe(med, len(stamps), n_fresh,
                 detail=f"{len(rows):,} tickers · median collected {med} "
                        f"({age}d ago) · {n_fresh:,} within {FUND_MAX_AGE_DAYS}d")


def _probe_brief() -> Probe:
    p = PIPE / "brief_today.html"
    if not p.exists():
        return Probe(None, error="brief_today.html absent")
    m = dt.datetime.fromtimestamp(p.stat().st_mtime)
    return Probe(m.date(), 1, 1, detail=f"built {m:%d %b %H:%M}")


def _as_date(v) -> dt.date | None:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v)[:10])


# ── wiring tables ─────────────────────────────────────────────────────────────
SCAN_SPEC = {
    "IN": ("indian_full_scan/indian_full_scan_*.xlsx", "Symbol", "LTP", ".NS"),
    "US": ("us_full_scan/us_full_scan_*.xlsx", "Symbol", "LTP", ""),
    "JP": ("japan_scan/japan_market_scan_*.xlsx", "YF_Ticker", "LTP_JPY", ""),
    "KR": ("korea_scan/korea_market_scan_*.xlsx", "YF_Ticker", "LTP_KRW", ""),
    "EU": ("european_scan/european_market_scan_*.xlsx", "Symbol", "LTP", ""),
}

# Which store each market's scan actually reads — the thing that must be current
# BEFORE the scan runs. US is the per-ticker tree, not either of the two
# whole-market US parquets that also exist and were both staler on 2026-08-19.
PRICE_STORE_FOR = {
    "US": str(MCACHE / "ohlc"),
    "IN": str(BHAV / "assembled_long.parquet"),
    "JP": str(BHAV / "ohlcv_JAPAN.parquet"),
    "KR": str(BHAV / "ohlcv_KOREA.parquet"),
    "EU": str(BHAV / "ohlcv_EUROPE.parquet"),
}

PG_LABEL = {"IN": "india", "US": "us", "JP": "japan", "KR": "korea", "EU": "europe"}


def _mk(expected: dict[str, dt.date]) -> list[Dataset]:
    """Build the catalog bound to the session each market is expected to hold."""
    E = expected.get
    ds: list[Dataset] = [
        # ── TIER 1 · raw EOD stores ───────────────────────────────────────────
        Dataset("bhav.assembled", "prices", "IN", str(BHAV / "assembled_long.parquet"),
                "NSE/BSE official bhavcopy",
                lambda: _probe_parquet(BHAV / "assembled_long.parquet", expected=E("IN")),
                refresh=STORE_REFRESH["IN"], authority="canonical",
                note="India EOD of record. Rebuilt incrementally in mailer step [3/13]."),
        Dataset("bhav.cleaned", "prices", "IN", str(BHAV / "cleaned_long.parquet"),
                "derived from bhav.assembled",
                lambda: _probe_parquet(BHAV / "cleaned_long.parquet", expected=E("IN")),
                depends_on=("bhav.assembled",), authority="derived",
                note="Cleaned India panel the scan and _as_of_html read."),
        Dataset("cache.ohlc.US", "prices", "US", str(MCACHE / "ohlc"),
                "NASDAQ/NYSE close (yfinance)",
                lambda: _probe_per_ticker(MCACHE / "ohlc", "US", E("US")),
                refresh=STORE_REFRESH["US"], authority="canonical",
                note="🔴 THE store the US scan reads (7,699 per-ticker parquets). "
                     "Stranded at 17 Aug on 2026-08-19 when 3,872 incremental "
                     "refreshes died on a yfinance SQLite cache error."),
    ]
    for mkt, f in (("JP", "ohlcv_JAPAN.parquet"), ("KR", "ohlcv_KOREA.parquet"),
                   ("EU", "ohlcv_EUROPE.parquet")):
        ds.append(Dataset(
            f"cache.ohlcv.{mkt}", "prices", mkt, str(BHAV / f),
            ms.MARKETS[mkt].source,
            (lambda p=BHAV / f, m=mkt: _probe_parquet(p, expected=E(m))),
            refresh=STORE_REFRESH[mkt], authority="canonical",
            note=f"{mkt} scan input."))
    ds.append(Dataset(
        "cache.ohlcv.US_legacy", "prices", "US", str(BHAV / "ohlcv_US.parquet"),
        "NASDAQ/NYSE close (yfinance)",
        lambda: _probe_parquet(BHAV / "ohlcv_US.parquet", expected=E("US")),
        authority="derived",
        note="🔴 A SECOND US panel, not what the scan reads and not refreshed by "
             "any current job — 14 Aug while the scan store held 17 Aug. Retire "
             "it or wire it; leaving it is how the wrong file gets read."))
    for mkt in ("IN", "US", "JP", "KR", "EU"):
        ds.append(Dataset(
            f"warehouse.ohlcv.{mkt}", "prices", mkt,
            f"$WAREHOUSE/ohlcv/{mkt}", ms.MARKETS[mkt].source,
            (lambda m=mkt: _probe_warehouse(m, E(m))),
            # IN is assembled from the bhavcopy, not fetched by refresh_panels.
            refresh=(None if mkt == "IN" else f"refresh_panels.py --markets {mkt}"),
            authority="canonical",
            note="Deep panel behind regime/backtests. Reconcile Check 1 compares "
                 "the scan against THIS — so when both are stale the check passes."))

    # ── TIER 2 · scans (depend on their price store) ──────────────────────────
    for mkt in ("IN", "US", "JP", "KR", "EU"):
        dep = {"IN": "bhav.assembled", "US": "cache.ohlc.US"}.get(mkt, f"cache.ohlcv.{mkt}")
        ds.append(Dataset(
            f"scan.{mkt}", "scan", mkt, SCAN_SPEC[mkt][0], ms.MARKETS[mkt].source,
            (lambda m=mkt: _probe_scan(m, E(m))),
            refresh=SCAN_REFRESH[mkt], depends_on=(dep,), authority="derived",
            note="Session recovered from the workbook's PRICES, not its filename."))

    # ── TIER 3 · derived ──────────────────────────────────────────────────────
    for mkt in ("IN", "US", "JP", "KR", "EU"):
        ds.append(Dataset(
            f"pg.snapshots.{mkt}", "snapshot", mkt, f"market_daily.snapshots [{PG_LABEL[mkt]}]",
            "derived from scans",
            (lambda m=mkt: _probe_pg_snapshots(m, E(m))),
            refresh="python3 ~/scripts/market_ingest.py", depends_on=(f"scan.{mkt}",),
            authority="derived",
            note="Judged by price MOVEMENT — a carried-forward date reports the "
                 "last date that actually moved."))
    # ── fundamentals ──────────────────────────────────────────────────────────
    # Registered 2026-08-19. This store was invisible to every freshness surface
    # while THREE consumers disagreed about which US fundamentals file to read:
    # financial_ratios.py read this one, data_quality.py audited a different and
    # staler `fundamentals_history/US.parquet` (4,597 tickers vs 5,802), and the
    # collector drew its universe from a dead price panel. Same shape as the
    # three-US-price-stores problem, one layer up.
    #
    # Judged on FILING recency, not session: a 10-K lands once a year, so the
    # meaningful question is "has the collector run", which `collected_at`
    # answers. FUND_MAX_AGE_DAYS mirrors the collector's own FRESH_DAYS.
    ds.append(Dataset(
        "fundamentals.US", "fundamentals", "US",
        str(MCACHE / "fundamentals" / "US_current.parquet"),
        "SEC EDGAR companyfacts (us-gaap + ifrs-full)",
        lambda: _probe_fundamentals(MCACHE / "fundamentals" / "US_current.parquet"),
        refresh="us_fundamentals_edgar.py", authority="canonical",
        note="US fundamentals of record. IFRS filers and successor-CIK names "
             "were absent until 2026-08-19."))

    ds.append(Dataset(
        "brief", "brief", "*", "brief_today.html", "derived from scans",
        _probe_brief, refresh="./daily_mailer.sh --send",
        depends_on=tuple(f"scan.{m}" for m in ("IN", "US")), authority="derived",
        note="The deliverable. Its caveat must name each market's session."))
    return ds


# The REAL commands, lifted from daily_mailer.sh / daily_research.sh. A refresh
# command that does not exist is worse than none: `ensure_fresh.py` would report
# a fix it cannot perform, which reads as "handled".
SCAN_REFRESH = {
    "IN": "scan_bhavcopy.py",
    "US": "full_us_market_scan.py --workers 10 --min-price 2",
    "JP": "full_japan_market_scan.py --workers 3",
    "KR": "full_korea_market_scan.py --workers 3",
    "EU": "full_european_market_scan.py --universe data/europe_broad_list.csv",
}

# Price-store refreshers. India comes from the official bhavcopy; every other
# market's working store is rebuilt by its own scan, so the store and the scan
# share a command — refreshing the store IS running the scan.
STORE_REFRESH = {
    "IN": "bhavcopy_history.py 400",
    "US": SCAN_REFRESH["US"],
    "JP": SCAN_REFRESH["JP"],
    "KR": SCAN_REFRESH["KR"],
    "EU": SCAN_REFRESH["EU"],
}


def catalog(at: dt.datetime | None = None) -> list[Dataset]:
    at = at or dt.datetime.now(ms.UTC)
    expected = {m: ms.expected_session(m, at) for m in ms.MARKETS}
    return _mk(expected)


def by_id(at: dt.datetime | None = None) -> dict[str, Dataset]:
    return {d.id: d for d in catalog(at)}


def main() -> int:
    ap = argparse.ArgumentParser(description="dataset registry: location, deps, source")
    ap.add_argument("--kind"); ap.add_argument("--market"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ds = [d for d in catalog()
          if (not a.kind or d.kind == a.kind) and (not a.market or d.market == a.market)]
    if a.json:
        print(json.dumps([{k: v for k, v in d.__dict__.items() if k != "probe_fn"}
                          for d in ds], indent=2, default=str))
        return 0
    print(f"{'ID':26} {'KIND':9} {'MKT':4} {'AUTH':10} DEPENDS ON")
    for d in ds:
        print(f"{d.id:26} {d.kind:9} {d.market:4} {d.authority:10} "
              f"{','.join(d.depends_on) or '-'}")
        print(f"{'':26} ↳ {d.location}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
