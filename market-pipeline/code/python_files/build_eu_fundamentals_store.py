#!/usr/bin/env python3
"""
build_eu_fundamentals_store.py — EU_current.parquet from public.global_fundamentals.

WHY THIS EXISTS
───────────────
Europe was parked out of the brief's per-name coverage on the stated grounds
that its "fundamentals are quality scores in `pb`; ratios table has no EU rows"
(watchlist_markets.PARKED). The second half was true — fundamentals.ratios holds
only us/korea/india. The first half pointed at the wrong table: Postgres
public.global_fundamentals has 4,666 real filed line-item rows for 1,159 EU
tickers, 97% carrying share counts and 100% carrying a `filed` date, which is
everything the point-in-time rule needs. No new data source is required; the
rows were simply never turned into ratios.

This writes them into the same store shape financial_ratios.py already reads for
India/US/Korea (KR_current.parquet), so EU joins the existing pipeline rather
than growing a parallel one.

TWO THINGS EUROPE DOES THAT NO OTHER MARKET HERE DOES
─────────────────────────────────────────────────────
1. It is SEVEN CURRENCIES, not one: EUR 840 tickers · GBP 176 · DKK 106 ·
   SEK 15 · CHF 9 · NOK 8 · PLN 5. Every other market in financial_ratios.py is
   a single currency named in its MARKETS tuple. So the store carries a
   per-row `currency` column and financial_ratios uses it when present.

   Rows whose FILING currency does not match their EXCHANGE currency are
   dropped, not converted. A cross-listed name filing in EUR and trading in SEK
   would otherwise produce a PE off by the FX rate, and silently — an invented
   number is worse than a missing one. FX conversion would also break the
   "never mixed" rule financial_ratios.py is explicit about.

2. LSE quotes in PENCE. A .L close of 277.5 is £2.775, not £277.50. Left
   uncorrected every UK PE and PB would be 100x too high and every UK name
   would look catastrophically expensive — the kind of error that looks like a
   finding. Handled in financial_ratios._price_scale(), not here, because it is
   a property of the PRICE feed rather than of the filings.

COVERAGE CEILING, STATED UP FRONT
─────────────────────────────────
1,159 EU tickers have fundamentals but only 440 of them have a price in
ohlcv_EUROPE.parquet. PE/PB need both, so EU ratios will cover ~440 names, not
1,159. That is a real limit of the price feed, not of this script.

Usage:  python3 build_eu_fundamentals_store.py [--dry-run]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

import data_registry as R

PSQL = "/opt/homebrew/bin/psql"
OUT = R.FUND_DIR / "EU_current.parquet"

# yfinance suffix -> the currency that exchange QUOTES in. Used to reject rows
# whose filing currency disagrees, rather than converting them.
EXCHANGE_CCY = {
    "L": "GBP", "DE": "EUR", "F": "EUR", "PA": "EUR", "AS": "EUR", "BR": "EUR",
    "LS": "EUR", "IR": "EUR", "MI": "EUR", "MC": "EUR", "VI": "EUR",
    "HE": "EUR", "AT": "EUR", "ST": "SEK", "CO": "DKK", "OL": "NOK",
    "SW": "CHF", "WA": "PLN", "IS": "TRY",
}

# global_fundamentals column -> the name financial_ratios.build_market expects.
COLMAP = {
    "ticker": "ticker", "fy_end": "fy_end", "shares": "shares",
    "equity": "stockholders_equity", "net_income": "net_income",
    "revenue": "revenue", "total_assets": "total_assets",
    "gross_profit": "gross_profit", "cfo": "cfo",
    "current_assets": "current_assets", "current_liabilities": "current_liabilities",
    "ebit": "ebit", "long_term_debt": "long_term_debt",
    "source": "source", "currency": "currency",
}


def _fetch() -> pd.DataFrame:
    cols = ", ".join(COLMAP)
    sql = (f"COPY (SELECT {cols} FROM public.global_fundamentals "
           f"WHERE market='EU' AND fy_end IS NOT NULL) TO STDOUT WITH CSV HEADER")
    p = subprocess.run([PSQL, "-d", "market_data", "-tAc", sql],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"psql failed: {p.stderr.strip()[:300]}")
    from io import StringIO
    return pd.read_csv(StringIO(p.stdout))


def build(dry_run: bool = False) -> dict:
    raw = _fetch()
    if raw.empty:
        raise RuntimeError("no EU rows in public.global_fundamentals")
    df = raw.rename(columns=COLMAP)

    df["_sfx"] = df["ticker"].astype(str).str.rsplit(".", n=1).str[-1].str.upper()
    df["_exch_ccy"] = df["_sfx"].map(EXCHANGE_CCY)

    n0 = len(df)
    unknown = df["_exch_ccy"].isna()
    df = df[~unknown]
    mismatch = df["currency"].str.upper() != df["_exch_ccy"]
    dropped_mismatch = int(mismatch.sum())
    df = df[~mismatch].drop(columns=["_sfx", "_exch_ccy"])

    df["fy_end"] = pd.to_datetime(df["fy_end"], errors="coerce")
    df = df.dropna(subset=["fy_end"]).sort_values(["ticker", "fy_end"])
    # Stored as 'YYYY-MM-DD' STRINGS, matching IN/US/KR. financial_ratios
    # concatenates all markets into one frame before writing parquet; a
    # datetime64 fy_end here against object elsewhere makes the combined column
    # object-dtype and pyarrow refuses it ("Expected bytes, got a Timestamp").
    df["fy_end"] = df["fy_end"].dt.strftime("%Y-%m-%d")
    # build_market wants total_debt; global_fundamentals has no such column and
    # it falls back to long_term_debt, so declare it NULL rather than guess.
    df["total_debt"] = pd.NA
    df["free_cash_flow"] = pd.NA

    summary = {
        "rows_in": n0,
        "dropped_unknown_exchange": int(unknown.sum()),
        "dropped_currency_mismatch": dropped_mismatch,
        "rows_out": len(df),
        "tickers": int(df["ticker"].nunique()),
        "currencies": df["currency"].value_counts().to_dict(),
        # ISO strings sort lexicographically, so max() is still the latest date.
        "latest_fy": str(df["fy_end"].max()),
    }
    if not dry_run:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(OUT, compression="zstd", index=False)
        summary["written"] = str(OUT)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    s = build(a.dry_run)
    for k, v in s.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
