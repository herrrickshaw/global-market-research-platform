#!/usr/bin/env python3
"""
ticker_exchange_map.py — one canonical ticker -> EXCHANGE table, as a ready
reference.

WHY
---
Every ticker must be exchange-qualified. A bare symbol is ambiguous: `RELIANCE`
names one instrument on NSE and another on BSE, and bare symbols collide across
markets outright. On 2026-07-31 that ambiguity let 8,802 Shenzhen, Shanghai,
Taiwan, Sydney, HK and Singapore bars be written into the INDIA price panel with
nothing looking wrong — among bare tickers a foreign symbol reads as an
unfamiliar local smallcap. This table makes market membership a lookup instead
of a guess about ticker shape.

NOT TO BE CONFUSED WITH build_ticker_reference.py
  That builds `market_daily.ticker_reference` in Postgres: name, freshness,
  liquidity tier and earnings dates keyed on (market_code, ticker). It carries
  no exchange column and is left alone. This module is the venue dimension, and
  joins that table for names/liquidity where the ticker matches.

WHAT IT FIXES ABOUT THE EXISTING SOURCES
  * `global-ticker-universe` has an `exchange` column, but it is COARSE:
    "NSE/BSE", "SSE+SZSE", "NYSE/NASDAQ/AMEX", "Xetra + Frankfurt" each cover two
    or three venues. The precise venue is in the yfinance suffix, so exchange is
    re-derived from the suffix (.NS -> NSE, .BO -> BSE) and given an ISO 10383 MIC.
  * US symbols are bare and unresolvable from a suffix. The NASDAQ Trader symbol
    directory supplies the true listing exchange per symbol (N=NYSE, Q=Nasdaq,
    A=NYSE American, P=NYSE Arca, Z=Cboe BZX, V=IEX) plus an ETF flag — worth
    carrying, since ETFs reaching a stock screen has been a recurring failure.

    ticker_exchange_map.py            # build -> cache_seed/ticker_exchange_reference.parquet
    ticker_exchange_map.py --verify   # report coverage, write nothing
    ticker_exchange_map.py --lookup RELIANCE.NS 000001.SZ AAPL
"""

from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "cache_seed" / "ticker_exchange_reference.parquet"
UNIVERSE = Path("/Users/umashankar/repos/global-ticker-universe/data")
NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"

# suffix -> (exchange, MIC, country ISO-2). The yfinance suffix IS the venue.
SUFFIX_MAP = {
    "NS":  ("National Stock Exchange of India", "XNSE", "IN"),
    "BO":  ("BSE Ltd",                          "XBOM", "IN"),
    "SS":  ("Shanghai Stock Exchange",          "XSHG", "CN"),
    "SZ":  ("Shenzhen Stock Exchange",          "XSHE", "CN"),
    "T":   ("Tokyo Stock Exchange",             "XTKS", "JP"),
    "KS":  ("Korea Exchange (KOSPI)",           "XKRX", "KR"),
    "KQ":  ("Korea Exchange (KOSDAQ)",          "XKOS", "KR"),
    "TW":  ("Taiwan Stock Exchange",            "XTAI", "TW"),
    "TWO": ("Taipei Exchange",                  "ROCO", "TW"),
    "HK":  ("Hong Kong Stock Exchange",         "XHKG", "HK"),
    "L":   ("London Stock Exchange",            "XLON", "GB"),
    "DE":  ("Xetra",                            "XETR", "DE"),
    "F":   ("Boerse Frankfurt",                 "XFRA", "DE"),
    "PA":  ("Euronext Paris",                   "XPAR", "FR"),
    "AS":  ("Euronext Amsterdam",               "XAMS", "NL"),
    "BR":  ("Euronext Brussels",                "XBRU", "BE"),
    "LS":  ("Euronext Lisbon",                  "XLIS", "PT"),
    "IR":  ("Euronext Dublin",                  "XDUB", "IE"),
    "MI":  ("Borsa Italiana",                   "XMIL", "IT"),
    "MC":  ("BME Spanish Exchanges",            "XMAD", "ES"),
    "ST":  ("Nasdaq Stockholm",                 "XSTO", "SE"),
    "HE":  ("Nasdaq Helsinki",                  "XHEL", "FI"),
    "CO":  ("Nasdaq Copenhagen",                "XCSE", "DK"),
    "OL":  ("Oslo Bors",                        "XOSL", "NO"),
    "SW":  ("SIX Swiss Exchange",               "XSWX", "CH"),
    "VI":  ("Vienna Stock Exchange",            "XWBO", "AT"),
    "WA":  ("Warsaw Stock Exchange",            "XWAR", "PL"),
    "AT":  ("Athens Stock Exchange",            "XATH", "GR"),
    "AX":  ("Australian Securities Exchange",   "XASX", "AU"),
    "NZ":  ("New Zealand Exchange",             "XNZE", "NZ"),
    "TO":  ("Toronto Stock Exchange",           "XTSE", "CA"),
    "V":   ("TSX Venture Exchange",             "XTSX", "CA"),
    "SA":  ("B3 Brasil Bolsa Balcao",           "BVMF", "BR"),
    "BA":  ("Bolsa de Comercio de Buenos Aires", "XBUE", "AR"),
    "JO":  ("Johannesburg Stock Exchange",      "XJSE", "ZA"),
    "ME":  ("Moscow Exchange",                  "MISX", "RU"),
    "SR":  ("Saudi Exchange (Tadawul)",         "XSAU", "SA"),
    "SI":  ("Singapore Exchange",               "XSES", "SG"),
    "AE":  ("Abu Dhabi Securities Exchange",    "XADS", "AE"),
}

# NASDAQ Trader "Listing Exchange" letter -> (exchange, MIC).
US_EXCHANGE = {
    "N": ("New York Stock Exchange",  "XNYS"),
    "Q": ("Nasdaq Stock Market",      "XNAS"),
    "A": ("NYSE American",            "XASE"),
    "P": ("NYSE Arca",                "ARCX"),
    "Z": ("Cboe BZX",                 "BATS"),
    "V": ("Investors Exchange (IEX)", "IEXG"),
}

_SFX = re.compile(r"\.([A-Za-z]{1,3})$")

COLS = ["yf_symbol", "base_ticker", "suffix", "exchange", "exchange_mic",
        "country", "market_code", "market_name", "exchange_group",
        "name", "is_etf", "liquidity_tier", "turnover_usd", "validated"]


def _suffix(sym: str):
    m = _SFX.search(str(sym))
    return m.group(1).upper() if m else None


def _nasdaq() -> pd.DataFrame:
    """NASDAQ Trader directory, indexed by EVERY symbol spelling it publishes.

    yfinance and NASDAQ disagree on how to write share classes, preferreds and
    warrants, which is the whole reason ~1% of US symbols fail a naive join:

        class      BRK-B    <-> BRK.B
        preferred  ABR-PD   <-> ABR$D   (NASDAQ Symbol column: ABR-D)
        warrant    ACHR-WT  <-> ACHR.W  (NASDAQ Symbol column: ACHR+)

    Indexing on Symbol, NASDAQ Symbol and CQS Symbol together, then trying the
    transformed spellings below, resolves them without hand-maintained aliases.
    """
    n = pd.read_csv(NASDAQ_URL, sep="|")
    n = n[n["Symbol"].notna()]
    if "Test Issue" in n.columns:
        n = n[n["Test Issue"] != "Y"]
    n["Symbol"] = n["Symbol"].astype(str).str.strip().str.upper()
    frames = [n.assign(_key=n["Symbol"])]
    for c in ("NASDAQ Symbol", "CQS Symbol"):
        if c in n.columns:
            alt = n[n[c].notna()].copy()
            alt["_key"] = alt[c].astype(str).str.strip().str.upper()
            frames.append(alt)
    allk = pd.concat(frames, ignore_index=True)
    return allk.drop_duplicates(subset=["_key"], keep="first").set_index("_key")


_PREF = re.compile(r"-P([A-Z])$")
_WT = re.compile(r"-(WT|WS)$")


def _us_candidates(sym: str) -> list[str]:
    """yfinance spelling -> the spellings NASDAQ Trader might use."""
    s = str(sym).upper()
    out = [s]
    if _PREF.search(s):
        out.append(_PREF.sub(r"$\1", s))       # ABR-PD -> ABR$D
        out.append(_PREF.sub(r"-\1", s))       # ABR-PD -> ABR-D
    if _WT.search(s):
        out.append(_WT.sub(".W", s))           # ACHR-WT -> ACHR.W
        out.append(_WT.sub("+", s))            # ACHR-WT -> ACHR+
    if "-" in s:
        out.append(s.replace("-", "."))        # BRK-B  -> BRK.B
    return out


def _us_lookup(syms, table: pd.DataFrame, col: str):
    """First candidate spelling that hits the directory wins."""
    vals = []
    for s in syms:
        v = None
        for c in _us_candidates(s):
            if c in table.index:
                v = table.at[c, col]
                break
        vals.append(v)
    return vals


def _pg_reference() -> pd.DataFrame:
    q = ("copy (select ticker, name, liquidity_tier, turnover_usd "
         "from market_daily.ticker_reference) to stdout with csv header")
    out = subprocess.run(["psql", "-d", "market_data", "-c", q],
                         capture_output=True, text=True, timeout=180)
    t = pd.read_csv(io.StringIO(out.stdout))
    t["ticker"] = t["ticker"].astype(str).str.strip()
    return t.drop_duplicates(subset=["ticker"], keep="first").set_index("ticker")


def build() -> pd.DataFrame:
    val = pd.read_csv(UNIVERSE / "validated_universe_flat.csv")
    glo = pd.read_csv(UNIVERSE / "global_universe_flat.csv")
    val["validated"], glo["validated"] = True, False
    d = (pd.concat([val, glo], ignore_index=True)
           .drop_duplicates(subset=["yf_symbol"], keep="first")     # validated wins
           .rename(columns={"exchange": "exchange_group"}))
    d["yf_symbol"] = d["yf_symbol"].astype(str).str.strip()
    d["suffix"] = d["yf_symbol"].map(_suffix)
    d["base_ticker"] = [s[: -(len(x) + 1)] if x else s
                        for s, x in zip(d["yf_symbol"], d["suffix"])]
    print(f"  universe: {len(d):,} symbols ({int(d.validated.sum()):,} validated)")

    m = d["suffix"].map(SUFFIX_MAP)
    d["exchange"] = [x[0] if isinstance(x, tuple) else None for x in m]
    d["exchange_mic"] = [x[1] if isinstance(x, tuple) else None for x in m]
    d["country"] = [x[2] if isinstance(x, tuple) else None for x in m]
    d["is_etf"] = pd.NA
    d["name"] = pd.NA

    us = d["suffix"].isna()
    try:
        n = _nasdaq()
        key = list(d.loc[us, "yf_symbol"].str.upper())
        lx = _us_lookup(key, n, "Listing Exchange")
        d.loc[us, "exchange"] = [US_EXCHANGE.get(v, (None, None))[0] for v in lx]
        d.loc[us, "exchange_mic"] = [US_EXCHANGE.get(v, (None, None))[1] for v in lx]
        d.loc[us, "country"] = "US"
        d.loc[us, "is_etf"] = [v == "Y" for v in _us_lookup(key, n, "ETF")]
        d.loc[us, "name"] = _us_lookup(key, n, "Security Name")
        print(f"  NASDAQ directory: {len(n):,} symbol spellings -> "
              f"{int(d.loc[us, 'exchange'].notna().sum()):,} of {int(us.sum()):,} "
              f"US venues resolved, {int(d.loc[us, 'is_etf'].sum()):,} ETFs flagged")
    except Exception as e:
        print(f"  NASDAQ directory unavailable ({type(e).__name__}) — US venue blank")

    try:
        t = _pg_reference()
        d["name"] = d["name"].fillna(d["yf_symbol"].map(t["name"]))
        d["liquidity_tier"] = d["yf_symbol"].map(t["liquidity_tier"])
        d["turnover_usd"] = d["yf_symbol"].map(t["turnover_usd"])
        print(f"  market_daily.ticker_reference: {len(t):,} rows -> "
              f"{int(d['liquidity_tier'].notna().sum()):,} liquidity tiers joined")
    except Exception as e:
        print(f"  Postgres enrich skipped ({type(e).__name__})")
    for c in ("liquidity_tier", "turnover_usd"):
        if c not in d.columns:
            d[c] = pd.NA

    return d[COLS].sort_values(["country", "exchange", "yf_symbol"]).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--verify", action="store_true", help="report coverage, write nothing")
    ap.add_argument("--lookup", nargs="+", metavar="SYM", help="print rows for these symbols")
    a = ap.parse_args()

    if a.lookup:
        if not OUT.exists():
            print("build it first"); return 1
        d = pd.read_parquet(OUT)
        got = d[d.yf_symbol.str.upper().isin([s.upper() for s in a.lookup])]
        print(got[["yf_symbol", "exchange", "exchange_mic", "country", "name"]]
              .to_string(index=False) if len(got) else "  no match")
        return 0

    d = build()
    unres = d[d.exchange.isna()]
    print(f"\n  rows {len(d):,} | exchanges {d.exchange.nunique()} | "
          f"countries {d.country.nunique()} | unresolved venue {len(unres):,} "
          f"({len(unres) / len(d) * 100:.1f}%)")
    if len(unres):
        print(f"  unresolved: {unres.suffix.value_counts(dropna=False).head(6).to_dict()}")
    print(f"  duplicate yf_symbol: {int(d.yf_symbol.duplicated().sum())}")
    print("\n" + d.groupby(["country", "exchange"]).size()
          .sort_values(ascending=False).head(15).to_string())

    if a.verify:
        print("\n  --verify: not written"); return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.to_parquet(OUT, compression="zstd", index=False)
    print(f"\n  -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
