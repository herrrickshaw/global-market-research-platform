#!/usr/bin/env python3
"""
build_ticker_reference.py — one consolidated ticker dictionary for the rest
of the repos to read, instead of each script re-deriving name/market/
freshness/liquidity/earnings facts independently.

THIS IS A JOIN, NOT A NEW COLLECTOR
------------------------------------
Every field below already exists somewhere in this repo; the gap was that
no single place brought them together:
  - ticker, market, name, last_update  <- market_daily.ticker_freshness (existing view)
  - turnover_usd, liquidity tier       <- liquidity.py's cached index + liquidity.tier()
                                           (existing, built 2026-07-18 — NOT rebuilt here)
  - last_earnings_date (JP/KR/CN)      <- fundamentals.intl_pit_quarterly (this session)
  - last_earnings_date (India)         <- market_cache/nse_xbrl/pit_quarterly.parquet (existing)
  - next_earnings_date, eps_estimate   <- fundamentals.next_earnings (this session, JP/KR/CN)
Market-name normalisation ("india" <-> "IN") reuses watchlist_markets.norm()
rather than a new alias map.

COVERAGE TODAY (see --status)
------------------------------
last_earnings_date / next_earnings_date are populated for India (full) and
for whatever slice of JP/KR/CN yf_intl_pit_fundamentals.py has collected so
far (a trickling backfill, see that script's own docstring) — NULL
elsewhere until collected. US/Europe have no PIT earnings source wired
into this table yet; liquidity and freshness are populated for every
market liquidity.py and ticker_freshness already cover.

    build_ticker_reference.py --build     # (re)build market_daily.ticker_reference
    build_ticker_reference.py --status    # column-by-column population %
"""

from __future__ import annotations

import sys
import pandas as pd

import pg_client
import liquidity
import watchlist_markets as WM
import repo_registry as RR

SCHEMA = "market_daily"
TABLE = "ticker_reference"


def _ticker_freshness() -> pd.DataFrame:
    conn = pg_client.get_connection()
    return pd.read_sql("SELECT market, ticker AS symbol, name, last_update FROM market_daily.ticker_freshness", conn)


def _liquidity() -> pd.DataFrame:
    idx = liquidity._load_index()
    if idx.empty:
        return pd.DataFrame(columns=["symbol", "market_code", "turnover_usd", "liquidity_tier"])
    idx = idx.rename(columns={"Symbol": "symbol", "Market": "market_code", "turnover_usd": "turnover_usd"})
    idx["liquidity_tier"] = [liquidity.tier(t, m) for t, m in zip(idx["turnover_usd"], idx["market_code"])]
    return idx[["symbol", "market_code", "turnover_usd", "liquidity_tier"]]


def _intl_earnings_history() -> pd.DataFrame:
    conn = pg_client.get_connection()
    return pd.read_sql(
        """SELECT market AS market_code, symbol, MAX(period_end) AS last_earnings_date
           FROM fundamentals.intl_pit_quarterly GROUP BY market, symbol""", conn)


def _intl_next_earnings() -> pd.DataFrame:
    conn = pg_client.get_connection()
    return pd.read_sql(
        """SELECT market AS market_code, symbol, next_earnings_date, eps_estimate AS next_eps_estimate
           FROM fundamentals.next_earnings""", conn)


def _india_earnings_history() -> pd.DataFrame:
    path = RR.MARKET_PIPELINE / "market_cache" / "nse_xbrl" / "pit_quarterly.parquet"
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "last_earnings_date"])
    df = pd.read_parquet(path, columns=["symbol", "filing_date"])
    g = df.groupby("symbol")["filing_date"].max().reset_index()
    g["last_earnings_date"] = pd.to_datetime(g["filing_date"]).dt.date
    return g[["symbol", "last_earnings_date"]]


def build() -> pd.DataFrame:
    if not pg_client.connect():
        print("Postgres unavailable", file=sys.stderr)
        return pd.DataFrame()

    base = _ticker_freshness()
    base["market_code"] = base["market"].map(WM.norm)

    liq = _liquidity()
    base = base.merge(liq, on=["symbol", "market_code"], how="left")

    hist_intl = _intl_earnings_history()
    next_intl = _intl_next_earnings()
    base = base.merge(hist_intl, on=["symbol", "market_code"], how="left")
    base = base.merge(next_intl, on=["symbol", "market_code"], how="left")

    hist_in = _india_earnings_history()
    if not hist_in.empty:
        in_mask = base["market_code"] == "IN"
        merged_in = base.loc[in_mask, ["symbol"]].merge(hist_in, on="symbol", how="left")
        base.loc[in_mask, "last_earnings_date"] = merged_in["last_earnings_date"].values

    base = base.rename(columns={"symbol": "ticker"})
    out_cols = ["market_code", "market", "ticker", "name", "last_update", "turnover_usd",
                "liquidity_tier", "last_earnings_date", "next_earnings_date", "next_eps_estimate"]
    base = base[out_cols]

    pg_client.ensure_schema([
        f'''CREATE TABLE IF NOT EXISTS "{SCHEMA}"."{TABLE}" (
            market_code varchar,
            market varchar,
            ticker varchar NOT NULL,
            name text,
            last_update date,
            turnover_usd double precision,
            liquidity_tier varchar,
            last_earnings_date date,
            next_earnings_date date,
            next_eps_estimate double precision,
            updated_at timestamp DEFAULT now(),
            UNIQUE (market_code, ticker)
        )''',
    ])
    columns = out_cols
    rows = pg_client.to_rows(base, columns)
    n = pg_client.upsert_rows(SCHEMA, TABLE, columns, rows, conflict_cols=["market_code", "ticker"])
    print(f"upserted {n} rows into {SCHEMA}.{TABLE}")
    return base


def status() -> None:
    if not pg_client.connect():
        print("Postgres unavailable", file=sys.stderr)
        return
    conn = pg_client.get_connection()
    df = pd.read_sql(f'SELECT * FROM "{SCHEMA}"."{TABLE}"', conn)
    if df.empty:
        print("table empty — run --build first")
        return
    print(f"{len(df):,} rows total\n")
    for col in ["turnover_usd", "liquidity_tier", "last_earnings_date", "next_earnings_date"]:
        pct = 100 * df[col].notna().mean()
        print(f"  {col:22s} {pct:5.1f}% populated")
    print()
    print(df.groupby("market_code").agg(
        rows=("ticker", "size"),
        liquidity_known=("liquidity_tier", lambda s: s.notna().sum()),
        earnings_known=("last_earnings_date", lambda s: s.notna().sum()),
        upcoming_known=("next_earnings_date", lambda s: s.notna().sum()),
    ))


if __name__ == "__main__":
    if "--build" in sys.argv:
        build()
    elif "--status" in sys.argv:
        status()
    else:
        print(__doc__)
