#!/usr/bin/env python3
"""
warehouse_insights.py — turn 12GB of bars into a small table you can actually query.

THE PROBLEM THIS SOLVES
-----------------------
The price history is ~33M distinct bars. Every question anyone actually asks of it
("what is liquid in Korea", "what is near its high", "what has 10y of history")
is a per-SYMBOL question, and answering one by scanning 33M rows is why nobody
asks. This derives one row per symbol — coverage, liquidity, trend, risk — into a
file small enough to open instantly and keep in git.

    bulk bars      ~33M rows   parquet warehouse (846MB) / Postgres (12GB)
    this index     ~24k rows   one per symbol, queryable in milliseconds

The bulk stays as the reference you rebuild from; this is what you read.

WHY THE PARQUET WAREHOUSE, NOT POSTGRES
---------------------------------------
Measured 2026-08-02, they are NOT the same data and parquet wins on every axis
that matters here:

    freshness   parquet 2026-07-31   vs   Postgres 2026-07-01..07-17 (unscheduled
                                          bulk loads, advances only by hand)
    integrity   parquet deduped      vs   Postgres 14% duplicate rows overall,
                                          KOREA 49.9% — double-loaded, and legal
                                          under a UNIQUE index on
                                          (stock_id, date, batch_id): a re-run
                                          mints a new batch_id and inserts a
                                          complete second copy
    size        846 MB               vs   12 GB

An index built on the Postgres copy would inherit those duplicates and silently
double Korea's bar counts and halve its liquidity percentiles. China was the one
market Postgres held uniquely (291 symbols back to 2011-01-04); it has been
extracted to warehouse/ohlcv/CN, so the parquet side is now a superset.

🔴 MEMORY. This runs on an 8GB machine that has been losing processes to jetsam.
Everything is a DuckDB aggregate over ONE market partition at a time — never a
concat, never a full materialisation. Peak RSS is bounded by the largest single
year, not by the corpus.

    warehouse_insights.py --build
    warehouse_insights.py --top liquidity --market IN --n 15
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
WH = Path("/Users/umashankar/repos/global-market-data/warehouse/ohlcv")
OUT = HERE / "cache_seed" / "warehouse_insights.parquet"
MARKETS = ["IN", "US", "JP", "KR", "EU", "CN"]


def _con():
    import duckdb
    c = duckdb.connect()
    c.execute("set threads to 4")
    c.execute("set memory_limit='1GB'")
    return c


def build() -> int:
    frames = []
    con = _con()
    for mkt in MARKETS:
        # 🔴 PREFER SPLIT/BONUS-ADJUSTED BARS. The raw partitions carry unadjusted
        # closes, and on the first build that made HDFCBANK read -63.2% from its
        # 52w high with a -62.9% 1y return. That is not a crash, it is a 1:1
        # bonus: the printed price halves and every return metric derived from it
        # is wrong by the ratio of the corporate action. A screen built on raw
        # closes ranks corporate actions as crashes, which is worse than having
        # no screen — it is confidently wrong in a way that looks like a signal.
        #
        # The cost is freshness: ohlcv_adj/IN is rebuilt by price_adjuster.py in
        # ingest.sh [7b/7] and currently trails the raw partition. Adjustment
        # matters more than recency for RETURN and DRAWDOWN, so adjusted wins —
        # but the source and its as-of date are recorded per market rather than
        # silently chosen, because "last_close" from a stale partition is a
        # different claim from "last_close" today.
        # THREE bases, not two, because that is what actually exists:
        #
        #   adjusted     IN only — a real corporate-actions feed (23,480 events)
        #                supports adjusting the WHOLE panel.
        #   RAW+patch    US/JP/KR — no feed exists, so price_adjuster_global.py
        #                DETECTS splits from the panel and keeps only those a
        #                yfinance cross-check confirms. That yielded 16 symbols
        #                across three markets (JP 7, KR 4, US 5) out of ~16,000.
        #                It writes corrected_symbols.parquet — a PATCH, not year
        #                partitions — and overlaying it is honest; calling the
        #                market "adjusted" on the back of 16 symbols would not be.
        #   RAW          everything else.
        #
        # Collapsing the middle case into "adjusted" is the tempting error: it
        # would silence this index's warning for 99.9% of symbols that are still
        # unadjusted, which is worse than no adjustment at all.
        adj = WH.parent / "ohlcv_adj" / mkt
        adj_years = sorted(adj.glob("year=*.parquet"))
        patch = adj / "corrected_symbols.parquet"

        if adj_years:
            parts, kind = adj_years, "adjusted"
        else:
            parts, kind = sorted((WH / mkt).glob("year=*.parquet")), "RAW"
        if not parts:
            print(f"  {mkt}: no partitions — skipped")
            continue
        files = "[" + ",".join(f"'{p}'" for p in parts) + "]"

        n_patched = 0
        if kind == "RAW" and patch.exists():
            import pandas as _pd
            n_patched = _pd.read_parquet(patch, columns=["Symbol"]).Symbol.nunique()
            kind = f"RAW+{n_patched}corr"
            # Overlay: drop the patched symbols from raw, then union the patch.
            src_sql = (f"select Symbol, Date, Open, High, Low, Close, Volume "
                       f"from read_parquet({files}) "
                       f"where Symbol not in (select distinct Symbol from "
                       f"read_parquet('{patch}')) "
                       f"union all "
                       f"select Symbol, Date, Open, High, Low, Close, Volume "
                       f"from read_parquet('{patch}')")
        else:
            src_sql = (f"select Symbol, Date, Open, High, Low, Close, Volume "
                       f"from read_parquet({files})")

        # One pass, all per-symbol aggregates. Ordered aggregates (last/first by
        # date) avoid a self-join, which on 16M rows is the difference between
        # seconds and swapping.
        q = f"""
        with b as (
            select Symbol, Date, Open, High, Low, Close, Volume,
                   Close * Volume as turnover
            from ({src_sql})
            where Close is not null and Close > 0
        ),
        agg as (
            select Symbol,
                   count(*)                                    as n_bars,
                   min(Date)                                   as first_bar,
                   max(Date)                                   as last_bar,
                   last(Close order by Date)                   as last_close,
                   max(High)                                   as hi_all,
                   min(Low)                                    as lo_all,
                   median(turnover)                            as med_turnover,
                   -- 252-day window stats, computed by filtering rather than a
                   -- window function: cheaper and exact enough for a screen.
                   max(case when Date >= (select max(Date) from b) - INTERVAL 365 DAY
                            then High end)                     as hi_52w,
                   min(case when Date >= (select max(Date) from b) - INTERVAL 365 DAY
                            then Low  end)                     as lo_52w,
                   avg(case when Date >= (select max(Date) from b) - INTERVAL 200 DAY
                            then Close end)                    as ma_200,
                   first(Close order by Date)                  as first_close,
                   last(Close order by Date) filter (
                       where Date <= (select max(Date) from b) - INTERVAL 365 DAY
                   )                                           as close_1y_ago
            from b group by Symbol
        )
        select '{mkt}' as market, '{kind}' as price_basis, * from agg
        """
        d = con.execute(q).df()
        if kind == "adjusted":
            flag = ""
        elif n_patched:
            flag = (f"  ⚠️ {n_patched} symbols split-corrected; the rest are RAW "
                    f"— returns still distorted where a split went undetected")
        else:
            flag = "  ⚠️ RAW closes — returns distorted by splits/bonuses"
        print(f"  {mkt}: {len(d):,} symbols indexed  [{kind}, to "
              f"{pd.to_datetime(d.last_bar).max().date()}]{flag}")
        frames.append(d)
    con.close()

    if not frames:
        print("  nothing indexed"); return 1
    idx = pd.concat(frames, ignore_index=True)

    # Derived fields in pandas — cheap on ~24k rows, and clearer than more SQL.
    idx["pct_from_52w_high"] = (idx.last_close / idx.hi_52w - 1) * 100
    idx["above_200dma"] = idx.last_close > idx.ma_200
    idx["ret_1y_pct"] = (idx.last_close / idx.close_1y_ago - 1) * 100
    idx["years_history"] = (
        pd.to_datetime(idx.last_bar) - pd.to_datetime(idx.first_bar)
    ).dt.days / 365.25
    # Liquidity tier by within-market turnover rank — comparable across markets
    # in a way raw local-currency turnover is not.
    idx["liq_pctile"] = idx.groupby("market").med_turnover.rank(pct=True) * 100

    OUT.parent.mkdir(parents=True, exist_ok=True)
    idx.to_parquet(OUT, compression="zstd", index=False)
    mb = OUT.stat().st_size / 1048576
    print(f"\n  -> {OUT.name}: {len(idx):,} symbols across {idx.market.nunique()} "
          f"markets, {mb:.1f} MB")
    print(f"     (indexes ~{idx.n_bars.sum():,} bars)")
    return 0


def top(metric: str, market: str, n: int) -> int:
    if not OUT.exists():
        print("  no index — run --build first"); return 1
    d = pd.read_parquet(OUT)
    if market:
        d = d[d.market == market.upper()]
    cols = ["market", "Symbol", "last_bar", "last_close", "med_turnover",
            "liq_pctile", "pct_from_52w_high", "ret_1y_pct", "years_history",
            "above_200dma"]
    key = {"liquidity": "med_turnover", "return": "ret_1y_pct",
           "history": "years_history", "near_high": "pct_from_52w_high"}.get(metric)
    if key is None:
        print(f"  unknown metric {metric!r}; try: liquidity|return|history|near_high")
        return 1
    d = d.dropna(subset=[key]).sort_values(key, ascending=False).head(n)
    print(d[cols].to_string(index=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--top", default="")
    ap.add_argument("--market", default="")
    ap.add_argument("--n", type=int, default=15)
    a = ap.parse_args()
    if a.build:
        return build()
    if a.top:
        return top(a.top, a.market, a.n)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
