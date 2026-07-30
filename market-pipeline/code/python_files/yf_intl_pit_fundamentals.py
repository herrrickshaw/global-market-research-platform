#!/usr/bin/env python3
"""
yf_intl_pit_fundamentals.py — point-in-time JP/KR/CN fundamentals via yfinance.

THE GAP THIS CLOSES
-------------------
fundamentals_history/{JP,KR,CN}.parquet's `filed` column is fabricated —
fy_end + exactly 90 days for every row (std()==0, confirmed in
SCREENER_RESEARCH_DATA_SOURCES.md §2) — so any fundamentals-gated screener
conclusion (Piotroski, Coffee Can, Magic Formula, Bull Cartel) for these
three markets has carried a synthetic, not observed, point-in-time date: a
real look-ahead-bias risk that was flagged but not fixed by the 2026-07-31
data-linkage audit.

yfinance's Ticker.earnings_dates gives the ACTUAL announcement date (with
reported EPS + consensus estimate + surprise%). Confirmed working live for
Japan (7203.T), Korea KOSPI+KOSDAQ (005930.KS / 196170.KQ), and China
SSE+SZSE (600519.SS / 000001.SZ) — China was previously "untested" per
SCREENER_RESEARCH_DATA_SOURCES.md §2a. Reported EPS at a given announcement
date was verified to exactly match quarterly_income_stmt's Diluted EPS for
the corresponding period-end (7203.T: the 2025-08-06 announcement's
Reported EPS of 64.56 equals the 2025-06-30 column exactly), confirming an
announcement can be safely matched to "the last completed quarter-end at or
before that date."

DESIGN
------
* earnings_dates supplies filing_date + eps_reported/eps_estimate/surprise —
  more complete than quarterly_income_stmt's own EPS rows, which are sparse
  (often NaN except the single most recent quarter).
* quarterly_income_stmt supplies Total Revenue + Net Income — row names
  confirmed IDENTICAL across JP/KR/CN (yfinance normalizes these), which is
  what makes one shared collector safe instead of three market-specific
  parsers.
* Matching is BY DATE, not position: each earnings_dates row pairs with the
  quarterly_income_stmt period-end that is the latest one <= the
  announcement date.
* Checkpointed per (market, symbol) via the on-disk cache itself — a full
  universe run (JP 3,550 + KOSPI 943 + KOSDAQ 1,821 + SSE 2,310 + SZSE
  2,893 ≈ 11,500 symbols, 2 yfinance calls each) is meant to trickle across
  many off-hours sessions, same pattern as nse_xbrl_results.py /
  xbrl.pit_quarterly for India — this script does not try to finish in one
  run and isn't sized to.
* Raw per-symbol response is cached to parquet before any Postgres write —
  a matching bug must never cost the fetched source data; --load can always
  be re-run from cache without re-fetching.
* Consecutive-failure circuit breaker, same discipline as
  nse_xbrl_results.py — a throttle/block must stop the run, not burn the
  window fetching nothing.

    yf_intl_pit_fundamentals.py --collect --market JP --limit 200
    yf_intl_pit_fundamentals.py --collect --market ALL --limit 300
    yf_intl_pit_fundamentals.py --load                      # cache -> Postgres
    yf_intl_pit_fundamentals.py --status
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

try:
    import data_registry as _R
    ROOT = _R.MARKET_CACHE / "intl_pit"
except Exception:
    ROOT = Path(__file__).resolve().parent / "cache_seed" / "intl_pit"

ROOT.mkdir(parents=True, exist_ok=True)

MARKET_EXCHANGES = {
    "JP": ["JAPAN"],
    "KR": ["KOSPI", "KOSDAQ"],
    "CN": ["SSE", "SZSE"],
}
SCHEMA = "fundamentals"
TABLE = "intl_pit_quarterly"
CONSECUTIVE_FAILURE_LIMIT = 15


def _symbol_master() -> pd.DataFrame:
    import data_registry as R
    path = R.MARKET_CACHE / "symbol_master.parquet"
    return pd.read_parquet(path)


def universe(market: str) -> list:
    """Symbol list in stable HASH order, not alphabetical — a plain sort
    clusters low-numbered/older tickers first (confirmed live: the initial
    numeric-prefix block is disproportionately delisted/no-data names), the
    same alphabetical-prefix-sample bias nse_xbrl_results.py's own docstring
    warns an interrupted run must never produce. Hash order is stable
    across runs (so --limit resumes make steady, reproducible progress)
    without favoring any lexical region of the universe."""
    import hashlib
    df = _symbol_master()
    exchanges = MARKET_EXCHANGES[market]
    syms = df[df["exchange"].isin(exchanges)]["yf_symbol"].dropna().unique().tolist()
    return sorted(syms, key=lambda s: hashlib.md5(s.encode()).hexdigest())


def cache_dir(market: str) -> Path:
    d = ROOT / market
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_path(market: str, symbol: str) -> Path:
    safe = symbol.replace("/", "_")
    return cache_dir(market) / f"{safe}.parquet"


def _fetch_one(market: str, symbol: str) -> pd.DataFrame:
    """One symbol's PIT panel: earnings_dates joined to quarterly revenue/
    net income by nearest period-end <= announcement date. Empty frame (not
    None) on no data — cached as such so it isn't retried every run."""
    import yfinance as yf

    t = yf.Ticker(symbol)
    ed_full = t.earnings_dates
    if ed_full is None or ed_full.empty:
        return pd.DataFrame(), None

    # The upcoming report (Reported EPS still NaN, only an estimate) is the
    # "next earnings date" callers actually want — captured separately
    # below, not treated as a history row.
    upcoming = ed_full[ed_full["Reported EPS"].isna()]
    next_row = None
    if not upcoming.empty:
        next_date = pd.to_datetime(upcoming.index.max()).tz_localize(None)
        est = upcoming.loc[upcoming.index.max(), "EPS Estimate"]
        next_row = {
            "symbol": symbol,
            "next_earnings_date": next_date.date(),
            "eps_estimate": float(est) if pd.notna(est) else None,
        }

    ed = ed_full[ed_full["Reported EPS"].notna()].copy()
    if ed.empty:
        return pd.DataFrame(), next_row
    ed.index = pd.to_datetime(ed.index).tz_localize(None)
    ed = ed.sort_index()

    qi = t.quarterly_income_stmt
    revenue_row = qi.loc["Total Revenue"] if qi is not None and "Total Revenue" in qi.index else None
    income_row = qi.loc["Net Income"] if qi is not None and "Net Income" in qi.index else None
    period_ends = sorted(qi.columns) if qi is not None else []

    out_rows = []
    for filing_date, r in ed.iterrows():
        period_end = None
        for pe in reversed(period_ends):
            if pe <= filing_date:
                period_end = pe
                break
        revenue = float(revenue_row[period_end]) if (revenue_row is not None and period_end in revenue_row.index
                                                       and pd.notna(revenue_row[period_end])) else None
        net_income = float(income_row[period_end]) if (income_row is not None and period_end in income_row.index
                                                         and pd.notna(income_row[period_end])) else None
        out_rows.append({
            "symbol": symbol,
            "period_end": (period_end.date() if period_end is not None else filing_date.date()),
            "filing_date": filing_date.to_pydatetime(),
            "eps_reported": float(r["Reported EPS"]) if pd.notna(r["Reported EPS"]) else None,
            "eps_estimate": float(r["EPS Estimate"]) if pd.notna(r["EPS Estimate"]) else None,
            "surprise_pct": float(r["Surprise(%)"]) if pd.notna(r["Surprise(%)"]) else None,
            "revenue": revenue,
            "net_income": net_income,
        })
    out = pd.DataFrame(out_rows)
    if out.empty:
        return out, next_row
    # A quarter can appear more than once (a later announcement re-reports/
    # revises the same period_end, e.g. 000001.SZ's 2025-06-30 quarter was
    # announced twice, 2025-08-22 and 2025-10-24) — keep the EARLIEST
    # filing_date per period_end, since PIT semantics care about when the
    # market first learned the number, not a later restatement. Also
    # required for (market,symbol,period_end)'s UNIQUE constraint downstream.
    out = out.sort_values("filing_date").drop_duplicates("period_end", keep="first")
    return out, next_row


def next_earnings_path(market: str) -> Path:
    return ROOT / f"next_earnings_{market}.parquet"


def collect(market: str, limit: int, refresh: bool = False) -> None:
    syms = universe(market)
    pending = syms if refresh else [s for s in syms if not cache_path(market, s).exists()]
    print(f"[{market}] universe={len(syms)} pending={len(pending)} (limit this run={limit})")

    ne_path = next_earnings_path(market)
    next_map = (pd.read_parquet(ne_path).set_index("symbol").to_dict("index")
                if ne_path.exists() else {})

    done = 0
    consecutive_failures = 0
    for symbol in pending[:limit]:
        try:
            df, next_row = _fetch_one(market, symbol)
            df.to_parquet(cache_path(market, symbol), index=False)
            if next_row:
                next_map[symbol] = {"next_earnings_date": next_row["next_earnings_date"],
                                     "eps_estimate": next_row["eps_estimate"]}
            elif symbol in next_map:
                del next_map[symbol]  # no longer has an upcoming report on file
            consecutive_failures = 0
            done += 1
        except Exception as e:
            consecutive_failures += 1
            print(f"  ERROR {symbol}: {e}", file=sys.stderr)
            if consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT:
                print(f"  {consecutive_failures} consecutive failures — stopping "
                      f"(possible rate limit/block, not assumed without this check)", file=sys.stderr)
                break
        time.sleep(0.35)

    if next_map:
        ne_df = pd.DataFrame([{"symbol": s, **v} for s, v in next_map.items()])
        ne_df.to_parquet(ne_path, index=False)

    remaining = len(pending) - done
    print(f"[{market}] collected this run: {done}  remaining: {max(remaining, 0)}  "
          f"upcoming-earnings on file: {len(next_map)}")


def load(markets: list) -> int:
    import pg_client
    if not pg_client.connect():
        print("Postgres unavailable — nothing loaded", file=sys.stderr)
        return 0
    pg_client.ensure_schema([
        f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"',
        f'''CREATE TABLE IF NOT EXISTS "{SCHEMA}"."{TABLE}" (
            market varchar NOT NULL,
            symbol varchar NOT NULL,
            period_end date NOT NULL,
            filing_date timestamp,
            eps_reported double precision,
            eps_estimate double precision,
            surprise_pct double precision,
            revenue double precision,
            net_income double precision,
            src varchar,
            loaded_at timestamp DEFAULT now(),
            UNIQUE (market, symbol, period_end)
        )''',
        f'''CREATE TABLE IF NOT EXISTS "{SCHEMA}"."next_earnings" (
            market varchar NOT NULL,
            symbol varchar NOT NULL,
            next_earnings_date date,
            eps_estimate double precision,
            src varchar,
            updated_at timestamp DEFAULT now(),
            UNIQUE (market, symbol)
        )''',
    ])
    columns = ["market", "symbol", "period_end", "filing_date", "eps_reported",
               "eps_estimate", "surprise_pct", "revenue", "net_income", "src"]
    ne_columns = ["market", "symbol", "next_earnings_date", "eps_estimate", "src"]
    total = 0
    for market in markets:
        frames = []
        for p in cache_dir(market).glob("*.parquet"):
            df = pd.read_parquet(p)
            if not df.empty:
                frames.append(df)
        if frames:
            panel = pd.concat(frames, ignore_index=True)
            panel["market"] = market
            panel["src"] = "yfinance_earnings_dates"
            rows = pg_client.to_rows(panel, columns)
            n = pg_client.upsert_rows(SCHEMA, TABLE, columns, rows, conflict_cols=["market", "symbol", "period_end"])
            print(f"[{market}] upserted {n} history rows ({panel['symbol'].nunique()} symbols)")
            total += n
        else:
            print(f"[{market}] no history cached yet")

        ne_path = next_earnings_path(market)
        if ne_path.exists():
            ne_df = pd.read_parquet(ne_path)
            if not ne_df.empty:
                ne_df["market"] = market
                ne_df["src"] = "yfinance_earnings_dates"
                ne_rows = pg_client.to_rows(ne_df, ne_columns)
                n2 = pg_client.upsert_rows(SCHEMA, "next_earnings", ne_columns, ne_rows,
                                            conflict_cols=["market", "symbol"])
                print(f"[{market}] upserted {n2} next-earnings rows")
                total += n2
    return total


def status() -> None:
    for market in MARKET_EXCHANGES:
        syms = universe(market)
        cached = list(cache_dir(market).glob("*.parquet"))
        with_data = sum(1 for p in cached if pd.read_parquet(p).shape[0] > 0)
        print(f"{market}: universe={len(syms):>6,}  cached={len(cached):>6,}  "
              f"({with_data:,} with ≥1 filing)  remaining={len(syms) - len(cached):>6,}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--load", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--market", default="ALL", choices=["ALL", *MARKET_EXCHANGES.keys()])
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if already cached")
    args = ap.parse_args()

    markets = list(MARKET_EXCHANGES) if args.market == "ALL" else [args.market]

    if args.collect:
        for m in markets:
            collect(m, args.limit, refresh=args.refresh)
    elif args.load:
        load(markets)
    elif args.status:
        status()
    else:
        ap.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
