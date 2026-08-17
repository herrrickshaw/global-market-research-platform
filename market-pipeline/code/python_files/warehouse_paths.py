#!/usr/bin/env python3
"""
warehouse_paths.py — the single seam between this package and the price warehouse.

WHY THIS MODULE EXISTS. Until 2026-08-17, thirty-three files in this directory
each hardcoded `/Users/umashankar/repos/global-market-data/warehouse/...`. When
that tree was migrated to the cloud store on 2026-08-14 (~/scripts/market_paths.py),
two of those files were repointed and the rest were not — so ingest steps [7] and
[7b] failed three days later against a directory that no longer existed (E-033),
and nine more pipeline-critical scripts were one cleanup away from the same fate.

A path that appears in thirty-three files cannot be moved. It can only be moved
here once, which is the entire point: after this, relocating the warehouse is a
one-line change in market_paths.DATASETS, not a thirty-three-file sweep.

🔴 NO FALLBACK TO THE OLD PATH, DELIBERATELY. If resolution fails these raise.
The tempting alternative — fall back to the repo copy — is what turns a loud
five-second failure into a silent divergence: the repo copies still exist today,
so a fallback would quietly serve month-old panels to a backtest that reports a
confident number from them. Stopping is strictly better than answering wrongly.

RESOLUTION IS CACHED per process. `market_paths.resolve()` will materialise the
tree from Dropbox on a cold cache, and thirty-three module-level imports must not
each pay for (or race on) that. The first call in a process does the work; the
rest are dictionary hits.
"""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path.home() / "scripts"))
from market_paths import resolve as _resolve  # noqa: E402


@lru_cache(maxsize=None)
def ohlcv() -> Path:
    """The year-partitioned OHLCV root — what was `.../warehouse/ohlcv`."""
    return _resolve("ohlcv")


@lru_cache(maxsize=None)
def root() -> Path:
    """The warehouse root itself — what was `.../warehouse`.

    Derived from ohlcv()'s parent rather than resolved separately: the two must
    never be able to point at different trees, which a second DATASETS entry
    would eventually allow.
    """
    return ohlcv().parent


def market(mkt: str) -> Path:
    """One market's partition directory, e.g. market('IN') -> .../ohlcv/IN."""
    return ohlcv() / mkt.upper()


@lru_cache(maxsize=None)
def ohlcv_adj_in() -> Path:
    """Split/bonus-adjusted India panel — what was `.../warehouse/ohlcv_adj/IN`.

    India is the only market with an adjusted panel; price_adjuster.py builds it
    and load_prices() reads it. Raw closes fake -90% crashes through every split
    without it, so a consumer reaching for this must not silently get the raw one.
    """
    return _resolve("ohlcv_adj_in")


def factors() -> Path:
    """The split/bonus factor table at the warehouse root."""
    return root() / "adjustment_factors.parquet"


if __name__ == "__main__":
    print(f"  ohlcv        {ohlcv()}")
    print(f"  root         {root()}")
    print(f"  ohlcv_adj/IN {ohlcv_adj_in()}")
    print(f"  factors      {factors()}")
    for m in ("IN", "US", "JP", "KR", "EU", "CN"):
        p = market(m)
        print(f"  {m:<3} {len(list(p.glob('year=*.parquet'))):>3} partitions  {p}")
