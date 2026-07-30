#!/usr/bin/env python3
"""
bridge_ratios_to_cassandra.py — real per-symbol P/E, P/B, ROE, market by market.

Generalized from bridge_eu_ratios_to_cassandra.py (2026-07-30), which fixed
Europe alone. Building US next made the SAME three fragile pieces necessary a
second time — the sparse-trailing-date price join, the plausibility backstop,
the fundamentals_source write-safety — and duplicating those into a third,
fourth, fifth near-identical file (Japan/Korea/China are the obvious next
targets) was worse than generalizing now. bridge_eu_ratios_to_cassandra.py is
superseded by `--market EUROPE` here; it is left in place rather than deleted,
since deleting someone's working script is not this script's call to make.

WHY THIS EXISTS AT ALL. completeness_graph.py's Cassandra audit found
`fundamentals_source` — a column that already existed, already populated —
showing 99-100% of EVERY market's rows as `median_imputed`, not measured.
`stock_quotes` reports "100% populated" regardless; a median-imputed ROE ranks
identically to a measured one in anything that sorts on the column. This script
closes that gap from data already collected, market by market, rather than
launching a new extraction per market.

WHY THIS IS FIXABLE FROM DATA ALREADY HERE. public.global_fundamentals
(Postgres) carries RAW financial-statement fields per ticker per fiscal
period — revenue, net_income, equity, shares — for every market this repo
tracks. It has no pe/pb columns; those need a PRICE, which the OHLCV warehouse
(repos/global-market-data/warehouse/ohlcv/<MKT>) already has, same yf_ticker
convention as Cassandra's `instruments` table.

  eps  = net_income / shares
  bvps = equity / shares
  pe   = latest_close / eps    (only if eps > 0 — a P/E on a loss is undefined)
  pb   = latest_close / bvps   (only if bvps > 0)
  roe  = net_income / equity   (a fraction, e.g. 0.098, NOT a percent — matches
                                the convention already in Cassandra's rows)

Per ticker, the LATEST fiscal period with COMPLETE fields is used — the newest
filing for a ticker is often the incomplete one (fields still arriving), and an
incomplete row would either crash the ratio or silently mismatch numerator and
denominator across periods.

🔴 THE PANEL'S OWN max(Date) IS A SPARSE TRAILING ROW, IN EVERY MARKET CHECKED
SO FAR. Europe's max date carried 15 of ~1,610 symbols; US's carried 9 of
~7,600. Filtering to `Date = max(Date)` leaves almost nothing to join against.
A window function picks each symbol's own most recent close instead of
assuming the whole panel shares one "latest day".

WRITE SAFETY. `UPDATE ... SET pe=?, pb=?, roe=?, fundamentals_source=?` touches
ONLY those four columns — never cmp/rsi/ema_*/etc — so this cannot repeat the
UNSET/None tombstone bug fixed in quote_updater.py (that bug was specific to a
single INSERT carrying all 41 columns). fundamentals_source is set to
'derived_price_join' on every row this script writes, not left at whatever it
was — a ratio this script computes is genuinely derived from filed financials
+ a traded price, and leaving the old 'median_imputed' label in place (a
mistake made and then caught in the Europe run) would make it indistinguishable
from a placeholder to the very audit this exists to satisfy.

PLAUSIBILITY IS PER-MARKET, NOT GLOBAL. LSE (.L) quotes in pence while
global_fundamentals reports UK filings in pounds — confirmed on CVSG.L, not
inferred — and produced pe=14,581 uncorrected before a /100 fix. Each market
gets its own known-quirk table (empty until something is actually confirmed
broken, per the same standard as the .L fix) plus a plausibility ceiling as a
backstop for whatever hasn't been individually verified yet. A dropped row is
a reported coverage gap, not a wrong number reported with confidence.

Usage:
  python3 bridge_ratios_to_cassandra.py --market US              # dry run
  python3 bridge_ratios_to_cassandra.py --market US --apply
  python3 bridge_ratios_to_cassandra.py --market EUROPE --apply
"""
from __future__ import annotations

import argparse
import glob
import sys

import duckdb
import pandas as pd

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import pg_client

DSN = "dbname=market_data host=/tmp user=umashankar"
WAREHOUSE = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv"

# market -> (global_fundamentals market code, Cassandra market partition key,
# OHLCV warehouse subdir, price-panel glob — US spans multiple year files,
# Europe/others currently ship one)
MARKETS = {
    "US":     ("US", "us",     "US",     "year=2026.parquet"),
    "EUROPE": ("EU", "europe", "EU",     "year=2026.parquet"),
    "JAPAN":  ("JP", "japan",  "JP",     "year=2026.parquet"),
    "KOREA":  ("KR", "korea",  "korea",  "year=2026.parquet"),
    "CHINA":  ("CN", "china",  "CN",     "year=2026.parquet"),
    "INDIA":  ("IN", "india",  "IN",     "year=2026.parquet"),
}

# Per-market quoting quirks, confirmed on a specific ticker before being added —
# never a guess extrapolated from a suffix pattern alone. Each entry:
# (predicate over the ticker column, divisor applied to `close`).
KNOWN_QUIRKS = {
    "EUROPE": [(lambda t: t.str.endswith(".L"), 100)],   # LSE: GBp vs GBP, see CVSG.L
}

MAX_PLAUSIBLE_PE = 200
MAX_PLAUSIBLE_PB = 50

# 🔴 A RATIO CAN BE PLAUSIBLE AND STILL WRONG IF THE FUNDAMENTALS ARE STALE.
# Found building the US bridge: 328 of 3,465 candidate symbols (9.5%) had their
# most recent COMPLETE fiscal row from 2009-2010 — RTX, PCG, AON, CMI, DKS, all
# real large-caps, not obscure delistings — a genuine collection gap in
# global_fundamentals for those specific tickers, not a bug in this script.
# Joining a 2009 EPS against a 2026 price produced RTX pe=0.077 (implying an
# EPS near $2,763) — plausible-LOOKING (the >200 ceiling only rejects
# implausibly HIGH values) and confidently wrong, which is worse than the
# median_imputed placeholder it would replace: at least a placeholder doesn't
# masquerade as a specific number tied to a real ticker's real current price.
# 2 years is not a guess — Europe's own "good" bulk clusters at 0.58y with a
# max of 2.58y and only 8/424 past 2y, so this is where the genuinely current
# data already ends, in the one market checked before US surfaced the problem.
MAX_FISCAL_AGE_YEARS = 2.0

# 🔴 INDIA REPORTS net_income/equity IN ₹ CRORE, shares IN ABSOLUTE UNITS.
# Confirmed on RELIANCE, not guessed: net_income=43851, equity=566235 (both
# ~crore-scale numbers) against shares=1.35e10 (a real absolute share count —
# Reliance's actual FY24 bonus roughly doubled it from ~6.77e9). Unscaled,
# eps = 43851/1.35e10 ≈ 0.0000032 — every India candidate's P/E blows up
# through the >200 ceiling, which is why the first dry run returned ZERO
# symbols out of 1,417 candidates. Scaled by 1e7 (1 crore = 10,000,000): eps
# = 32.4, matching Reliance's real known EPS — the exact ₹crore convention
# already solved once this session for a DIFFERENT source (screener.in), same
# fix, same number, independently re-derived here rather than assumed.
FUND_SCALE = {"INDIA": 1e7}


def load_fundamentals(fund_code: str) -> pd.DataFrame:
    pg_client.connect()
    d = pd.read_sql("""
        SELECT ticker, fy_end, net_income, equity, shares
        FROM public.global_fundamentals
        WHERE market = %s
          AND net_income IS NOT NULL
          AND equity IS NOT NULL
          AND shares IS NOT NULL
          AND shares > 0
    """, pg_client.get_connection(), params=[fund_code])
    d["fy_end"] = pd.to_datetime(d.fy_end)
    return d.sort_values("fy_end").drop_duplicates("ticker", keep="last")


def load_latest_price(panel_dir: str, panel_glob: str) -> pd.Series:
    files = sorted(glob.glob(f"{WAREHOUSE}/{panel_dir}/{panel_glob}"))
    if not files:
        raise SystemExit(f"no price panel found at {WAREHOUSE}/{panel_dir}/{panel_glob}")
    c = duckdb.connect()
    src = ", ".join(f"'{f}'" for f in files)
    d = c.execute(f"""
        SELECT Symbol, Close FROM (
            SELECT Symbol, Close, Date,
                   row_number() OVER (PARTITION BY Symbol ORDER BY Date DESC) rn
            FROM read_parquet([{src}])
            WHERE Close IS NOT NULL
        ) WHERE rn = 1
    """).df()
    return d.set_index("Symbol").Close


def build_ratios(market: str) -> pd.DataFrame:
    fund_code, _, panel_dir, panel_glob = MARKETS[market]
    f = load_fundamentals(fund_code)
    px = load_latest_price(panel_dir, panel_glob)
    f["close"] = f.ticker.map(px)
    f = f.dropna(subset=["close"])

    scale = FUND_SCALE.get(market)
    if scale:
        f["net_income"] = f.net_income * scale
        f["equity"] = f.equity * scale

    for predicate, divisor in KNOWN_QUIRKS.get(market, []):
        mask = predicate(f.ticker)
        f.loc[mask, "close"] = f.loc[mask, "close"] / divisor

    age_years = (pd.Timestamp.now() - f.fy_end).dt.days / 365.25
    stale = age_years > MAX_FISCAL_AGE_YEARS
    n_stale = int(stale.sum())
    if n_stale:
        print(f"  dropped {n_stale} symbol(s) whose latest complete fiscal row "
              f"is >{MAX_FISCAL_AGE_YEARS:.0f}y old — a real collection gap for "
              f"those tickers, not something safe to pair with today's price")
    f = f[~stale]

    f["eps"] = f.net_income / f.shares
    f["bvps"] = f.equity / f.shares
    f["roe"] = f.net_income / f.equity
    f["pe"] = (f.close / f.eps).where(f.eps > 0)
    f["pb"] = (f.close / f.bvps).where(f.bvps > 0)

    implausible = (f.pe.abs() > MAX_PLAUSIBLE_PE) | (f.pb.abs() > MAX_PLAUSIBLE_PB)
    n_dropped = int(implausible.sum())
    if n_dropped:
        print(f"  dropped {n_dropped} symbol(s) with |pe|>{MAX_PLAUSIBLE_PE} or "
              f"|pb|>{MAX_PLAUSIBLE_PB} — likely an unverified currency/unit "
              f"convention, or a non-operating security (warrant/unit/preferred) "
              f"whose 'fundamentals' don't describe an operating company")
    f = f[~implausible]

    return f[["ticker", "fy_end", "close", "pe", "pb", "roe"]].dropna(
        subset=["pe", "pb"], how="all")


def write_cassandra(d: pd.DataFrame, cass_market: str) -> tuple[int, int]:
    from cassandra.cluster import Cluster
    from cassandra.query import UNSET_VALUE

    # Same cluster/keyspace as backend/db/cassandra_client.py:17
    # (KEYSPACE = 'herrrickshaw') — intentionally NOT imported from there:
    # this is a short-lived manual CLI run (--market X --apply), not the
    # long-lived FastAPI server process cassandra_client.py's singleton
    # lifecycle is designed for, and backend/ has no existing import
    # relationship with market-pipeline/scripts/ (verified by grep — the
    # Postgres side above uses pg_client.py precisely because that mirrors
    # an established pattern; this would be new coupling instead). If
    # host/keyspace ever need to be genuinely shared, the right unit to
    # extract is a small constants module, not this session-lifecycle import.
    s = Cluster(["127.0.0.1"]).connect("herrrickshaw")
    stmt = s.prepare(
        "UPDATE stock_quotes SET pe = ?, pb = ?, roe = ?, "
        "fundamentals_source = 'derived_price_join' "
        "WHERE market = ? AND yf_ticker = ?"
    )
    written = skipped = 0
    for r in d.itertuples():
        pe = float(r.pe) if pd.notna(r.pe) else UNSET_VALUE
        pb = float(r.pb) if pd.notna(r.pb) else UNSET_VALUE
        roe = float(r.roe) if pd.notna(r.roe) else UNSET_VALUE
        if pe is UNSET_VALUE and pb is UNSET_VALUE:
            skipped += 1
            continue
        s.execute(stmt, (pe, pb, roe, cass_market, r.ticker))
        written += 1
    s.shutdown()
    return written, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", required=True, choices=sorted(MARKETS))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    _, cass_market, _, _ = MARKETS[a.market]
    d = build_ratios(a.market)
    print(f"{len(d):,} {a.market} symbols with a real, derivable ratio "
          f"(price + complete fundamentals)")
    if len(d):
        print(d.describe()[["pe", "pb", "roe"]].round(2).to_string())
        print()
        print(d.head(8)[["ticker", "fy_end", "close", "pe", "pb", "roe"]]
              .round(3).to_string(index=False))

    if not a.apply:
        print("\n(dry run — pass --apply to write to Cassandra)")
        return 0

    written, skipped = write_cassandra(d, cass_market)
    print(f"\nwrote {written:,} symbol(s) to Cassandra ({cass_market}) · "
          f"skipped {skipped:,} (no positive-denominator ratio)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
