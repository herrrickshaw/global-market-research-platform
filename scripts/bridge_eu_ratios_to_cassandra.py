#!/usr/bin/env python3
"""
bridge_eu_ratios_to_cassandra.py — real per-symbol P/E, P/B, ROE for Europe.

WHY THIS EXISTS. The completeness audit found Cassandra's europe fundamentals
were not what they looked like: `stock_quotes` reports "100% populated" for
pe/pb/roe, but 17% of a 500-row sample (85 of 500) shared the EXACT SAME
(pe, pb, roe) triple — 20.32778 / 1.6513 / 10.48694 — across completely
different tickers (1SXP.F, 1U1.F, 3IN.L, ...). That is a fallback/placeholder
value standing in for real data, not a quality-score artifact like the JP/KR/CN
contamination fixed earlier today — the plausibility check in
completeness_graph.py only catches LOW-CARDINALITY WHOLE numbers, so a single
repeated decimal constant slipped past it. (Extending that check is a separate,
smaller fix — see the note at the bottom.)

WHY THIS IS FIXABLE FROM DATA ALREADY HERE, not a new extraction job.
public.global_fundamentals (Postgres) carries RAW financial-statement fields
per ticker per fiscal period — revenue, net_income, equity, shares, roe, roa —
for 1,159 European tickers. It has no pe/pb columns; those need a PRICE, which
this repo already has: repos/global-market-data/warehouse/ohlcv/EU (1,616
symbols, same yf_ticker convention as Cassandra's `instruments` table — no
format translation needed). 442 tickers have BOTH. This script joins them
rather than fetching anything new.

  eps  = net_income / shares
  bvps = equity / shares
  pe   = latest_close / eps    (only if eps > 0 — a P/E on a loss is undefined)
  pb   = latest_close / bvps   (only if bvps > 0)
  roe  = net_income / equity   (a fraction, e.g. 0.098 — matching the convention
                                already in Cassandra's india rows, NOT a percent)

Per ticker, the LATEST fiscal period with COMPLETE fields (net_income, equity,
shares all present) is used — the most recent filing is not always the most
complete one (many global_fundamentals rows have partial NaNs), and picking an
incomplete row would either crash the ratio or silently produce one from a
mismatched numerator/denominator pair.

WRITE SAFETY. Cassandra UPDATE ... SET pe = ?, pb = ?, roe = ? touches ONLY
those three columns — never cmp/rsi/ema_*/etc — so this cannot repeat the
UNSET/None tombstone bug fixed in quote_updater.py this morning (that bug was
specific to a single prepared INSERT carrying all 41 columns; a targeted UPDATE
never had that failure mode). Rows are ONLY written when a real, positive-price,
positive-denominator ratio was computed — no fallback, no placeholder, matching
what the .cql loaders already do for India/China/Korea/Japan.

WHAT THIS DOES NOT FIX. Coverage is 442 of the ~1,700+ instrument europe
universe (global_fundamentals's own limit, not this script's) — the remaining
~1,150+ instruments still show whatever they showed before (many still the
fallback constant, since nothing here overwrites what it cannot verify). And
hong_kong is untouched: it has NO OHLCV panel anywhere in this repo's
warehouse (CN/EU/IN/JP/KR/US exist, HK does not), so pe/pb there would need a
NEW price collection, not a join — flagged, not attempted here.

Usage:
  python3 bridge_eu_ratios_to_cassandra.py             # dry run, report only
  python3 bridge_eu_ratios_to_cassandra.py --apply      # write to Cassandra
"""
from __future__ import annotations

import argparse
import sys

import duckdb
import pandas as pd

DSN = "dbname=market_data host=/tmp user=umashankar"
EU_PANEL = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/EU/year=2026.parquet"


def load_fundamentals() -> pd.DataFrame:
    c = duckdb.connect()
    c.execute("INSTALL postgres")
    c.execute("LOAD postgres")
    c.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres, READ_ONLY)")
    d = c.execute("""
        SELECT ticker, fy_end, net_income, equity, shares
        FROM pg.public.global_fundamentals
        WHERE market = 'EU'
          AND net_income IS NOT NULL
          AND equity IS NOT NULL
          AND shares IS NOT NULL
          AND shares > 0
    """).df()
    # latest COMPLETE fiscal period per ticker, not merely the latest filing —
    # the newest row for a ticker is often the incomplete one (fields still
    # filling in), so filtering to complete rows FIRST then taking the max
    # fy_end picks the most recent filing that is actually usable.
    d["fy_end"] = pd.to_datetime(d.fy_end)
    d = d.sort_values("fy_end").drop_duplicates("ticker", keep="last")
    return d


def load_latest_price() -> pd.Series:
    """The latest close PER SYMBOL, not the panel's single latest date.

    🔴 THE PANEL'S OWN max(Date) IS A SPARSE TRAILING ROW. 2026-07-22 (the max)
    carries only 15 of ~1,610 symbols; 2026-07-21 and every day before it carry
    the full universe. Filtering to `Date = max(Date)` first produced 15 prices
    total and, after the fundamentals join, exactly ONE symbol survived end to
    end — not because 439 tickers lacked data, but because the price side of
    the join had almost nothing to match against. A window function picks each
    symbol's own most recent row instead of assuming they share one.
    """
    c = duckdb.connect()
    d = c.execute(f"""
        SELECT Symbol, Close FROM (
            SELECT Symbol, Close, Date,
                   row_number() OVER (PARTITION BY Symbol ORDER BY Date DESC) rn
            FROM read_parquet('{EU_PANEL}')
            WHERE Close IS NOT NULL
        ) WHERE rn = 1
    """).df()
    return d.set_index("Symbol").Close


MAX_PLAUSIBLE_PE = 200    # a P/E above this is a unit/data error far more often
MAX_PLAUSIBLE_PB = 50     # than a genuine multiple — see the .L note below


def build_ratios() -> pd.DataFrame:
    f = load_fundamentals()
    px = load_latest_price()
    f["close"] = f.ticker.map(px)
    f = f.dropna(subset=["close"])

    # 🔴 LSE (.L) QUOTES IN PENCE, global_fundamentals REPORTS UK FILINGS IN
    # POUNDS. Confirmed on CVSG.L: currency='GBP', net_income/equity/shares in
    # pounds, but its yfinance Close of 1301 is GBp — i.e. GBP 13.01, not 1301.
    # Uncorrected this produced pe=14,581 / pb=358 for a stock that is not
    # actually 100x overvalued. This is a known, documented LSE/yfinance
    # quoting convention (not inferred from this one ticker) — every `.L`
    # ticker's currency field says GBP while its price series is GBp.
    is_lse = f.ticker.str.endswith(".L")
    f.loc[is_lse, "close"] = f.loc[is_lse, "close"] / 100

    f["eps"] = f.net_income / f.shares
    f["bvps"] = f.equity / f.shares
    f["roe"] = f.net_income / f.equity
    f["pe"] = (f.close / f.eps).where(f.eps > 0)
    f["pb"] = (f.close / f.bvps).where(f.bvps > 0)

    # 🔴 PLAUSIBILITY BACKSTOP FOR EXCHANGES NOT INDIVIDUALLY VERIFIED. .L was
    # confirmed and corrected above. Other suffixes in this universe (.SW
    # Swiss, .ST Stockholm, .CO Copenhagen, .OL Oslo, ...) may carry their own
    # quoting quirks (centimes, öre, whatever) that have NOT been checked one
    # by one here — this filter is a safety net against shipping an obviously
    # broken ratio from an unverified convention, not a substitute for doing
    # that per-exchange verification. A dropped row here is a coverage gap
    # reported honestly, not a wrong number reported confidently.
    implausible = (f.pe.abs() > MAX_PLAUSIBLE_PE) | (f.pb.abs() > MAX_PLAUSIBLE_PB)
    n_dropped = int(implausible.sum())
    if n_dropped:
        print(f"  dropped {n_dropped} symbol(s) with |pe|>{MAX_PLAUSIBLE_PE} or "
              f"|pb|>{MAX_PLAUSIBLE_PB} — likely an unverified currency/unit "
              f"convention on that exchange, not a real multiple")
    f = f[~implausible]

    return f[["ticker", "fy_end", "close", "pe", "pb", "roe"]].dropna(
        subset=["pe", "pb"], how="all")


def write_cassandra(d: pd.DataFrame) -> tuple[int, int]:
    from cassandra.cluster import Cluster
    from cassandra.query import UNSET_VALUE

    s = Cluster(["127.0.0.1"]).connect("herrrickshaw")
    # 🔴 fundamentals_source MUST BE SET, not just pe/pb/roe. Found only after
    # writing 424 rows without it: the column already exists and was already
    # populated ('median_imputed' for ~all rows in every market, confirmed
    # 2026-07-30), and every row this script fixes with a REAL derived ratio
    # was left carrying that stale imputed label — indistinguishable from
    # imputed to anything that reads the flag (including the very audit that
    # is about to be built to report measured-vs-imputed coverage). A ratio
    # this script computes is genuinely derived from filed financials + a
    # traded price, not a placeholder, so it is labeled accordingly.
    stmt = s.prepare(
        "UPDATE stock_quotes SET pe = ?, pb = ?, roe = ?, "
        "fundamentals_source = 'derived_price_join' "
        "WHERE market = 'europe' AND yf_ticker = ?"
    )
    written = skipped = 0
    for r in d.itertuples():
        pe = float(r.pe) if pd.notna(r.pe) else UNSET_VALUE
        pb = float(r.pb) if pd.notna(r.pb) else UNSET_VALUE
        roe = float(r.roe) if pd.notna(r.roe) else UNSET_VALUE
        if pe is UNSET_VALUE and pb is UNSET_VALUE:
            skipped += 1
            continue
        s.execute(stmt, (pe, pb, roe, r.ticker))
        written += 1
    s.shutdown()
    return written, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    d = build_ratios()
    print(f"{len(d):,} europe symbols with a real, derivable ratio "
          f"(price + complete fundamentals)")
    print(d.describe()[["pe", "pb", "roe"]].round(2).to_string())
    print()
    print(d.head(8)[["ticker", "fy_end", "close", "pe", "pb", "roe"]]
          .round(3).to_string(index=False))

    if not a.apply:
        print("\n(dry run — pass --apply to write to Cassandra)")
        return 0

    written, skipped = write_cassandra(d)
    print(f"\nwrote {written:,} symbol(s) to Cassandra · skipped {skipped:,} "
          f"(no positive-denominator ratio)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
