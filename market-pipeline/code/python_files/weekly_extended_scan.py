#!/usr/bin/env python3
"""
weekly_extended_scan.py — Tier 3 markets (see market_tiers.py): weekly
refresh + Darvas signal + freshness ledger, for every market outside the
daily Tier 1 (India/US) / Tier 2 (Europe/Japan/Korea) pipeline.

THIS IS WIRING, NOT NEW INFRASTRUCTURE
----------------------------------------
screener_kit.py already has real, working OHLCV seed data for all 20 of
its declared markets (confirmed live 2026-07-31 — every one has a cached
parquet, most ~4-5 weeks stale) plus kit.update()/kit.screen() to refresh
and screen any of them. liquidity.py's build_index() already iterates
kit.MARKETS. None of that needed building. What was missing:

  1. Nothing calls kit.update()/kit.screen() for Tier 3 markets on any
     schedule — the data just sits there aging.
  2. Nothing writes Tier 3 results into market_daily.snapshots, so
     market_ingest.py's existing ticker_freshness view (already market-
     agnostic — `WHERE market <> 'india'`, no code change needed) has
     nothing to UNION them in from. This is why market_daily.ticker_reference
     showed 0% coverage for China/HK/etc even though liquidity_index.parquet
     already had real turnover data for them — the JOIN base
     (ticker_freshness) simply never had those markets' rows.

This script writes directly into market_daily.snapshots in the exact shape
market_ingest.py's _load_snapshot_file() already produces for the other
markets (market, as_of_date, symbol, ltp, prev_close, change_pct,
darvas_signal, source_file, name) — no schema change, no new view.

    weekly_extended_scan.py                # every Tier 3 market
    weekly_extended_scan.py --market CN     # one market
    weekly_extended_scan.py --skip-update   # screen/write from cached data only
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from functools import partial

import pandas as pd

import market_tiers
import pg_client
from iter_utils import for_each_fail_soft

SCHEMA = "market_daily"


def _snapshot_rows(market: str, data: dict, darvas_signals: dict) -> pd.DataFrame:
    """One row per symbol with usable OHLCV — the freshness ledger's unit,
    independent of whether the symbol passed any screen."""
    rows = []
    for sym, df in data.items():
        if df is None or len(df) < 2 or "Close" not in df.columns:
            continue
        last = df.iloc[-1]
        prev = df.iloc[-2]
        rows.append({
            "market": market,
            "as_of_date": df.index[-1].date(),
            "symbol": sym,
            "ltp": float(last["Close"]),
            "prev_close": float(prev["Close"]),
            "change_pct": (float(last["Close"]) / float(prev["Close"]) - 1) * 100
                          if prev["Close"] else None,
            "darvas_signal": darvas_signals.get(sym, ""),
            "source_file": "weekly_extended_scan.py",
            "name": None,
        })
    return pd.DataFrame(rows)


def run_market(market: str, do_update: bool = True) -> int:
    import screener_kit as kit

    if do_update:
        try:
            result = kit.update(market, verbose=True)
            print(f"[{market}] update: {result}")
        except Exception as e:
            print(f"[{market}] update FAILED (continuing on cached data): {e}", file=sys.stderr)

    data = kit.load(market)
    if not data:
        print(f"[{market}] no data available — skipped")
        return 0

    try:
        signals_df = kit.screen("darvas", market)
        darvas_signals = dict(zip(signals_df["Symbol"], signals_df.get("Note", "BREAKOUT_BUY")))
    except Exception as e:
        print(f"[{market}] darvas screen failed (continuing without signals): {e}", file=sys.stderr)
        darvas_signals = {}

    snap = _snapshot_rows(market, data, darvas_signals)
    if snap.empty:
        print(f"[{market}] no snapshot rows built")
        return 0

    cols = ["market", "as_of_date", "symbol", "ltp", "prev_close",
            "change_pct", "darvas_signal", "source_file", "name"]
    rows = pg_client.to_rows(snap, cols)
    # Re-running the same market on the same day (a retry, or --skip-update
    # smoke test followed by a real run) must not double-append — delete any
    # existing rows for the (market, date)s in this batch first, in the same
    # transaction as the insert, matching market_ingest.py's own
    # already-loaded-this-date guard for the other markets in this table.
    dates = sorted(snap["as_of_date"].unique().tolist())
    n = pg_client.delete_and_insert(
        SCHEMA, "snapshots", "market = %s AND as_of_date = ANY(%s)", (market, dates),
        rows, cols)
    print(f"[{market}] wrote {n} snapshot rows ({len(darvas_signals)} darvas signals)")
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default=None, help="one Tier 3 market code, default: all")
    ap.add_argument("--skip-update", action="store_true", help="screen cached data only, no refresh fetch")
    args = ap.parse_args()

    if not pg_client.connect():
        print("Postgres unavailable", file=sys.stderr)
        return 1

    markets = [args.market.upper()] if args.market else market_tiers.TIER3
    print(f"=== weekly extended scan {dt.datetime.now():%Y-%m-%d %H:%M:%S} — "
          f"{len(markets)} Tier 3 markets ===")
    # run_market curried to Callable[[str], int] and driven through the
    # shared fail-soft runner (iter_utils.py) instead of a bespoke
    # try/except — one market's unexpected failure still can't take the
    # rest of the run down with it, now via the same wiring
    # yf_intl_pit_fundamentals.py uses for the identical shape.
    results = for_each_fail_soft(
        markets, partial(run_market, do_update=not args.skip_update), label=lambda m: m)
    total = sum(n for n in results.values() if n)
    print(f"=== done — {total} total snapshot rows across {len(markets)} markets ===")

    try:
        import liquidity
        liquidity.build_index(verbose=True)
    except Exception as e:
        print(f"liquidity index rebuild failed (continuing): {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
