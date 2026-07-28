#!/usr/bin/env python3
"""
warehouse_ohlcv_sync.py — keep the India parquet panel level with the bhavcopy.

THE LAG THIS FIXES. repos/global-market-data/warehouse/ohlcv/IN/year=*.parquet
is the panel behind almost every India study in this repo: pead_liquidity_study
.load_prices() reads it, and pe_bands, smallcap_screener, cluster_indices,
custom_indices and backtest_tier_anomalies all reach it from there. Nothing in
daily_pipeline.sh writes it. It was last built 2026-07-23 and ended 2026-07-22
while Postgres bhavcopy.cleaned_ohlcv — refreshed nightly at pipeline [1] — was
current to 2026-07-27, so fundamentals.india_pe_daily (rebuilt FROM the panel)
trailed live prices by five sessions and every P/E screen ran a week behind the
market it was screening.

WHY cleaned_ohlcv IS THE SOURCE. It is the collision-safe NSE+BSE merge. The
raw bhavcopy tables key on bare symbols, and NSE and BSE bare symbols COLLIDE —
loading India from anything else silently mixes two exchanges' prices for the
same ticker. cleaned_ohlcv is the only India source that resolves this, which is
why it is the one named here and the one the warehouse ledger uses.

APPEND-ONLY, BY DATE. Only trading dates strictly newer than the parquet's max
are added; existing rows are never rewritten. That matters because the parquet
carries history reaching back further than cleaned_ohlcv's ~1-year window, so a
full rebuild from this source would TRUNCATE the panel to the last twelve
months and quietly destroy every long-horizon backtest. The sync widens the
right edge and touches nothing else.

🔴 THIS DOES NOT ADJUST FOR SPLITS. The panel is raw Close by design —
india_split_adjust.py holds the factor table and load_prices() applies it at
read time. Appending raw rows keeps that contract. After a sync that crosses a
corporate action, rerun `india_split_adjust.py --build` so the new dates are
covered by the factor table too.

Usage:
  python3 warehouse_ohlcv_sync.py            # report the gap, change nothing
  python3 warehouse_ohlcv_sync.py --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

WH = Path("/Users/umashankar/repos/global-market-data/warehouse/ohlcv/IN")
DSN = "dbname=market_data host=/tmp user=umashankar"
SRC = "pg.bhavcopy.cleaned_ohlcv"
COLS = ["Date", "Symbol", "Open", "High", "Low", "Close", "Volume"]


def _con():
    import duckdb
    c = duckdb.connect()
    c.execute("INSTALL postgres")
    c.execute("LOAD postgres")
    c.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres, READ_ONLY)")
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the missing dates (default: report only)")
    ap.add_argument("--year", type=int, default=None,
                    help="year file to extend (default: the latest present)")
    a = ap.parse_args()

    files = sorted(WH.glob("year=*.parquet"))
    if not files:
        print(f"no parquet files under {WH}")
        return 1
    target = (WH / f"year={a.year}.parquet") if a.year else files[-1]
    if not target.exists():
        print(f"{target} does not exist")
        return 1

    c = _con()
    mx = c.execute(
        f"select max(Date)::DATE from read_parquet('{target}')").fetchone()[0]
    src_mx = c.execute(f"select max(trade_date) from {SRC}").fetchone()[0]
    year = int(target.stem.split("=")[1])

    gap = c.execute(f"""
        select trade_date, count(*) n from {SRC}
        where trade_date > DATE '{mx}'
          and extract(year from trade_date) = {year}
        group by 1 order by 1""").df()

    print(f"panel   : {target.name}  max {mx}")
    print(f"bhavcopy: {SRC}  max {src_mx}")
    if gap.empty:
        print("→ panel is level with the bhavcopy; nothing to do")
        return 0
    print(f"→ {len(gap)} trading date(s) missing, {int(gap.n.sum()):,} rows:")
    print(gap.to_string(index=False))
    if not a.apply:
        print("\n(dry run — pass --apply to write)")
        return 0

    before = c.execute(
        f"select count(*) from read_parquet('{target}')").fetchone()[0]
    tmp = target.with_suffix(".parquet.tmp")
    # Read the existing file fully before writing: DuckDB cannot stream from a
    # parquet it is simultaneously replacing, so the union goes to a temp file
    # and is moved into place only after it is complete. A half-written panel
    # here would take out every India study at once.
    c.execute(f"""
        COPY (
            select * from read_parquet('{target}')
            UNION ALL
            select trade_date::TIMESTAMP as "Date", symbol as "Symbol",
                   open as "Open", high as "High", low as "Low",
                   close as "Close", volume::BIGINT as "Volume"
            from {SRC}
            where trade_date > DATE '{mx}'
              and extract(year from trade_date) = {year}
        ) TO '{tmp}' (FORMAT PARQUET)""")
    after = c.execute(f"select count(*) from read_parquet('{tmp}')").fetchone()[0]
    added = after - before
    if added != int(gap.n.sum()):
        tmp.unlink(missing_ok=True)
        print(f"ABORT: expected +{int(gap.n.sum()):,} rows, temp file has "
              f"+{added:,}. Nothing written.")
        return 1
    tmp.replace(target)
    new_mx = c.execute(
        f"select max(Date)::DATE from read_parquet('{target}')").fetchone()[0]
    print(f"\n✓ {before:,} → {after:,} rows (+{added:,}) · max now {new_mx}")
    print("  rerun india_split_adjust.py --build if the new dates cross a "
          "corporate action, then rebuild pe_bands.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
