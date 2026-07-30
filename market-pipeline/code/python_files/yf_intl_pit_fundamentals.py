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

2026-07-31 EXTENSION — the rest of Tier 3 (market_tiers.py)
-------------------------------------------------------------
Checked ~/repos/global-stock-screener/cache_seed/fundamentals_history/
before building anything new (per the user's own instruction to check
already-collected data first): every Tier 3 market outside JP/KR/CN
already has a fundamentals_history/{market}.parquet file there. BUT —
same test as SCREENER_RESEARCH_DATA_SOURCES.md §2 applied to each one —
EVERY SINGLE ONE has `(filed - fy_end).std() == 0.0`: the exact same
fabricated fy_end+90d pattern already found for JP/KR/CN, just never
checked for these markets before. So the existing files don't solve the
PIT problem — but they're not useless either: AU/CA/DE/HK/SA/TW have real
density (139-913 tickers) and — unlike yfinance's own quarterly_income_stmt
(~5-6 quarters, revenue/net_income only) — genuinely deep history (AU:
2021-2026) with a much richer field set (revenue, net_income, gross_profit,
total_assets, current_assets, current_liabilities, shares, equity,
long_term_debt, cfo). BR/CH/SE/SG have only 1-4 tickers (unusable); UK/ZA
have no file at all.

So the collector now has TWO paths depending on what's available per
market:
  - LOCAL_ENRICHED_MARKETS (AU/CA/DE/HK/SA/TW): keep the rich local
    financial data, replace ONLY the fake `filed` date with a real one
    matched against yfinance earnings_dates (greedy two-pointer match on
    sorted dates — each fy_end row consumes the next unused announcement
    >= that fy_end within 240 days, so nearby periods never double-claim
    the same announcement). One yfinance call per symbol (earnings_dates
    only — no quarterly_income_stmt call needed, the local file already
    has the figures).
  - PURE_YF_MARKETS (BR/CH/SE/SG/UK/ZA, no usable local file): same
    quarterly_income_stmt-based path already built for JP/KR/CN.
Universe source also differs: JP/KR/CN come from cache.symbol_master
(has full coverage there); the local-enriched markets' universe IS the
local file's own ticker list (defines exactly which symbols need fixing);
the pure-yfinance markets use screener_kit's own per-market symbol list
(symbol_master doesn't cover them, screener_kit already does — same
source weekly_extended_scan.py uses for their OHLCV).
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
# market -> local fundamentals_history/{X}.parquet stem, only where density
# was actually checked and found usable (>100 tickers) — see module docstring.
LOCAL_ENRICHED_MARKETS = {"AU": "AU", "CA": "CA", "DE": "DE", "HK": "HK", "SA": "SA", "TW": "TW"}
# no usable local file (1-4 tickers) or none at all — pure yfinance path,
# same mechanics as JP/KR/CN, universe from screener_kit instead of symbol_master.
PURE_YF_MARKETS = ["BR", "CH", "SE", "SG", "UK", "ZA"]
LOCAL_EXTRA_COLS = ["gross_profit", "total_assets", "current_assets",
                    "current_liabilities", "shares_out", "equity",
                    "long_term_debt", "cfo"]
ALL_MARKETS = list(MARKET_EXCHANGES) + list(LOCAL_ENRICHED_MARKETS) + PURE_YF_MARKETS
SCHEMA = "fundamentals"
TABLE = "intl_pit_quarterly"
CONSECUTIVE_FAILURE_LIMIT = 15


def _symbol_master() -> pd.DataFrame:
    import data_registry as R
    path = R.MARKET_CACHE / "symbol_master.parquet"
    return pd.read_parquet(path)


def _local_fundamentals(market: str) -> pd.DataFrame:
    import repo_registry as RR
    stem = LOCAL_ENRICHED_MARKETS[market]
    path = RR.fundamentals_history(stem)
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def universe(market: str) -> list:
    """Symbol list in stable HASH order, not alphabetical — a plain sort
    clusters low-numbered/older tickers first (confirmed live: the initial
    numeric-prefix block is disproportionately delisted/no-data names), the
    same alphabetical-prefix-sample bias nse_xbrl_results.py's own docstring
    warns an interrupted run must never produce. Hash order is stable
    across runs (so --limit resumes make steady, reproducible progress)
    without favoring any lexical region of the universe."""
    import hashlib
    if market in MARKET_EXCHANGES:
        df = _symbol_master()
        exchanges = MARKET_EXCHANGES[market]
        syms = df[df["exchange"].isin(exchanges)]["yf_symbol"].dropna().unique().tolist()
    elif market in LOCAL_ENRICHED_MARKETS:
        syms = _local_fundamentals(market)["ticker"].dropna().unique().tolist()
    elif market in PURE_YF_MARKETS:
        import screener_kit as kit
        syms = list(kit.load(market).keys())
    else:
        raise ValueError(f"unknown market '{market}'")
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


def _fetch_one_local(market: str, symbol: str, local_df: pd.DataFrame) -> tuple:
    """PIT panel for one symbol sourced from the local fundamentals_history
    file — real revenue/net_income/balance-sheet fields, deeper history
    than yfinance's own quarterly_income_stmt — with its FAKE `filed` date
    (confirmed fy_end+90d constant, see module docstring) replaced by a
    REAL announcement date from yfinance earnings_dates.

    Matching is a greedy two-pointer walk over both date-sorted lists: each
    fy_end row consumes the NEXT unused announcement >= that fy_end (within
    240 days), so two nearby periods can never claim the same announcement.
    Only needs earnings_dates — no quarterly_income_stmt call, the local
    file already has the figures."""
    import yfinance as yf

    rows = local_df[local_df["ticker"] == symbol].sort_values("fy_end")
    if rows.empty:
        return pd.DataFrame(), None

    t = yf.Ticker(symbol)
    ed_full = t.earnings_dates
    if ed_full is None or ed_full.empty:
        return pd.DataFrame(), None

    upcoming = ed_full[ed_full["Reported EPS"].isna()]
    next_row = None
    if not upcoming.empty:
        next_date = pd.to_datetime(upcoming.index.max()).tz_localize(None)
        est = upcoming.loc[upcoming.index.max(), "EPS Estimate"]
        next_row = {"symbol": symbol, "next_earnings_date": next_date.date(),
                    "eps_estimate": float(est) if pd.notna(est) else None}

    ed = ed_full[ed_full["Reported EPS"].notna()].copy()
    if ed.empty:
        return pd.DataFrame(), next_row
    ed.index = pd.to_datetime(ed.index).tz_localize(None)
    ed = ed.sort_index()
    announce_dates = ed.index.tolist()

    out_rows, ai = [], 0
    for _, r in rows.iterrows():
        fy_end = pd.Timestamp(r["fy_end"])
        while ai < len(announce_dates) and announce_dates[ai] < fy_end:
            ai += 1
        if ai >= len(announce_dates) or (announce_dates[ai] - fy_end).days > 240:
            continue
        filing_date = announce_dates[ai]
        ai += 1  # consumed — the next fy_end row can't reuse this announcement
        eps_row = ed.loc[filing_date]
        row = {
            "symbol": symbol, "period_end": fy_end.date(),
            "filing_date": filing_date.to_pydatetime(),
            "eps_reported": float(eps_row["Reported EPS"]) if pd.notna(eps_row["Reported EPS"]) else None,
            "eps_estimate": float(eps_row["EPS Estimate"]) if pd.notna(eps_row["EPS Estimate"]) else None,
            "surprise_pct": float(eps_row["Surprise(%)"]) if pd.notna(eps_row["Surprise(%)"]) else None,
            "revenue": r.get("revenue"), "net_income": r.get("net_income"),
            "gross_profit": r.get("gross_profit"), "total_assets": r.get("total_assets"),
            "current_assets": r.get("current_assets"), "current_liabilities": r.get("current_liabilities"),
            "shares_out": r.get("shares"), "equity": r.get("equity"),
            "long_term_debt": r.get("long_term_debt"), "cfo": r.get("cfo"),
        }
        out_rows.append(row)
    out = pd.DataFrame(out_rows)
    return out, next_row


def next_earnings_path(market: str) -> Path:
    return ROOT / f"next_earnings_{market}.parquet"


def collect(market: str, limit: int, refresh: bool = False) -> None:
    syms = universe(market)
    pending = syms if refresh else [s for s in syms if not cache_path(market, s).exists()]
    print(f"[{market}] universe={len(syms)} pending={len(pending)} (limit this run={limit})")
    local_df = _local_fundamentals(market) if market in LOCAL_ENRICHED_MARKETS else None

    ne_path = next_earnings_path(market)
    next_map = (pd.read_parquet(ne_path).set_index("symbol").to_dict("index")
                if ne_path.exists() else {})

    done = 0
    consecutive_failures = 0
    for symbol in pending[:limit]:
        try:
            if local_df is not None:
                df, next_row = _fetch_one_local(market, symbol, local_df)
            else:
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
    extra_cols_ddl = ", ".join(f'"{c}" double precision' for c in LOCAL_EXTRA_COLS)
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
            {extra_cols_ddl},
            src varchar,
            loaded_at timestamp DEFAULT now(),
            UNIQUE (market, symbol, period_end)
        )''',
        # Extra balance-sheet columns (LOCAL_ENRICHED_MARKETS only) added
        # 2026-07-31 — ALTER guards the case where the table already
        # existed from before this extension (JP/KR/CN loaded first).
        *[f'ALTER TABLE "{SCHEMA}"."{TABLE}" ADD COLUMN IF NOT EXISTS "{c}" double precision'
          for c in LOCAL_EXTRA_COLS],
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
    columns = (["market", "symbol", "period_end", "filing_date", "eps_reported",
                "eps_estimate", "surprise_pct", "revenue", "net_income"]
               + LOCAL_EXTRA_COLS + ["src"])
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
            for c in LOCAL_EXTRA_COLS:  # pure-yfinance markets never populate these
                if c not in panel.columns:
                    panel[c] = None
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
    for market in list(MARKET_EXCHANGES) + list(LOCAL_ENRICHED_MARKETS) + PURE_YF_MARKETS:
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
    ap.add_argument("--market", default="ALL", choices=["ALL", *ALL_MARKETS])
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if already cached")
    args = ap.parse_args()

    markets = ALL_MARKETS if args.market == "ALL" else [args.market]

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
