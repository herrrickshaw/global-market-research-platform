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


BHAV = Path("/Users/umashankar/market-pipeline/data/bhavcopy_cache")
SUPPLEMENT = BHAV / "ohlcv_EUROPE_supplement.parquet"


def fetch_missing_prices(batch: int = 80, period: str = "1mo",
                         verbose: bool = True) -> dict:
    """Close history for EU tickers the scan panel does not price.

    ohlcv_EUROPE.parquet is built from the European SCAN universe
    (europe_broad_list.csv, 996 symbols). The filings cover a different and
    larger set, so 687 tickers had fundamentals and no price — and pe/pb need
    both. That single gap was the whole of Europe's ratio shortfall: 417 of the
    687 have shares and positive net income, i.e. they would price immediately.

    Fetched with yfinance DIRECTLY rather than through data_sources.fetch().
    That path returns 0/8 on these tickers — and 0/4 on SAP.DE, BMW.DE,
    NOKIA.HE and NOVO-B.CO, which are four of the largest listings in Europe —
    while a plain yf.download of the same symbols resolves 58/60. The multi
    source layer is broken for European symbols; that is a separate bug and is
    NOT fixed here, it is only routed around, deliberately and visibly.
    """
    import pandas as _pd
    import yfinance as yf
    import duckdb
    import financial_ratios as FR

    con = duckdb.connect()
    store = _pd.read_parquet(OUT).sort_values(["ticker", "fy_end"])
    latest = store.groupby("ticker").tail(1)
    priced = set(FR._latest_closes(con, BHAV / "ohlcv_EUROPE.parquet")["symbol"])
    missing = [t for t in latest["ticker"] if t not in priced]
    if verbose:
        print(f"  {len(missing)} EU tickers have fundamentals but no price — fetching")

    frames, ok = [], 0
    for i in range(0, len(missing), batch):
        chunk = missing[i:i + batch]
        try:
            d = yf.download(chunk, period=period, progress=False,
                            group_by="ticker", threads=True, auto_adjust=False)
        except Exception as e:                                 # noqa: BLE001
            if verbose:
                print(f"    batch {i//batch+1}: {type(e).__name__} — skipped")
            continue
        for t in chunk:
            try:
                sub = d[t] if t in d.columns.get_level_values(0) else None
            except Exception:                                  # noqa: BLE001
                sub = None
            if sub is None or "Close" not in sub or not sub["Close"].notna().any():
                continue
            g = sub.dropna(subset=["Close"]).reset_index()[
                ["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
            g["Symbol"] = t
            frames.append(g)
            ok += 1
        if verbose:
            print(f"    batch {i//batch+1}/{(len(missing)-1)//batch+1}: {ok} resolved so far")

    if not frames:
        return {"missing": len(missing), "resolved": 0, "written": None}
    out = _pd.concat(frames, ignore_index=True)
    for c in ("Open", "High", "Low", "Close"):
        out[c] = _pd.to_numeric(out[c], errors="coerce").astype("float32")
    out["Volume"] = _pd.to_numeric(out["Volume"], errors="coerce").fillna(0).astype("int64")
    out.to_parquet(SUPPLEMENT, compression="zstd", index=False)
    return {"missing": len(missing), "resolved": ok,
            "symbols": int(out["Symbol"].nunique()),
            "max_date": str(_pd.to_datetime(out["Date"]).max().date()),
            "written": str(SUPPLEMENT)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--with-prices", action="store_true",
                    help="also fetch closes for tickers the scan panel misses")
    a = ap.parse_args()
    s = build(a.dry_run)
    for k, v in s.items():
        print(f"  {k}: {v}")
    if a.with_prices and not a.dry_run:
        print("\n  ── supplementary price fetch ──")
        for k, v in fetch_missing_prices().items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
