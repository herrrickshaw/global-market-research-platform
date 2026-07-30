# repo_registry.py
# ================
# THE one place that knows where SIBLING REPOS live and what cross-repo data
# paths point to. Companion to data_registry.py, which owns LOCAL dataset
# paths within this repo — this one owns paths that cross into
# ~/repos/global-market-data, ~/repos/global-stock-screener, and ~/scripts.
#
# WHY THIS EXISTS
# ───────────────
# An architecture survey found 65+ hardcoded ~/repos/... absolute paths
# scattered across scripts (129 files reference a sibling-repo path in some
# form) — the same fragmentation-causes-real-bugs pattern already found and
# fixed for Postgres/Cassandra access (see pg_client.py, cassandra_client.py).
# One concrete instance: the split/bonus-adjusted India OHLCV path was
# hardcoded independently in FOUR places — data_registry.py's own
# `warehouse.ohlcv_adj_in` Dataset entry, plus cost_intimation_drift.py,
# pit_event_studies.py, and validate_intimation_drift.py — none importing
# from any of the other three. A path typo or a repo move needed fixing four
# times, and nothing would have caught a stale copy.
#
# SCOPE
# ─────
# Two sibling repos hold real data this repo consumes:
#   global-market-data      OHLCV warehouse (raw + split-adjusted), long-term
#                           seed panels, a JP sector reference table
#   global-stock-screener   Fundamentals history cache, long-term seed panels
#                           (the GOOD copy for most markets — see below)
#
# 🔴 TWO REPOS HOLD OVERLAPPING LTM OHLCV DATA OF DIVERGENT QUALITY.
# global-market-data's cache_seed/ltm/US.parquet was an interrupted
# collection (see reference_us_price_panel_broken.md) — cost_vs_edge.py and
# daily_breakout_combo_us.py already redirect to global-stock-screener's copy
# instead, tracked only in code comments until now. `ltm_seed()` below
# defaults to the good repo; `ltm_seed_gmd()` is the other repo's copy,
# named separately so reaching for it is a deliberate choice, not a default.
#
# THIS IS DELIBERATELY A PLAIN MODULE OF CONSTANTS/FUNCTIONS, NOT A SERVICE —
# no discovery, no config file, no network call. Adding a new cross-repo path
# means adding one line here, nothing more. Only the paths with more than one
# call site (or with a real divergent-copy trap, like the LTM case above) are
# registered — this is a foundation new/changed call sites should use, not a
# mechanical rewrite of all 129 existing ones in one pass.
#
# CONTRACT
# ────────
#   * Import roots/paths from here; do not re-derive `~/repos/...` yourself.
#   * stdlib only (Path) — importable from both interpreters this repo runs
#     under (the venv's 3.9, and /usr/bin/python3), same constraint as
#     data_registry.py.
from __future__ import annotations

from pathlib import Path

HOME = Path.home()

# ── repo roots ──────────────────────────────────────────────────────────────
MARKET_PIPELINE = HOME / "market-pipeline"
SCRIPTS = HOME / "scripts"
BACKEND = HOME / "backend"
GLOBAL_MARKET_DATA = HOME / "repos" / "global-market-data"
GLOBAL_STOCK_SCREENER = HOME / "repos" / "global-stock-screener"

# ── global-market-data: OHLCV warehouse ─────────────────────────────────────
_GMD_WAREHOUSE = GLOBAL_MARKET_DATA / "warehouse"


def ohlcv_warehouse(market: str) -> Path:
    """Raw daily OHLCV, year-partitioned parquet directory. market: one of
    US/IN/CN/JP/KR/EU."""
    return _GMD_WAREHOUSE / "ohlcv" / market.upper()


def ohlcv_adj_warehouse(market: str = "IN") -> Path:
    """Split/bonus-adjusted OHLCV, year-partitioned parquet directory.
    India is the only market with a full adjustment history today (789
    events applied, validated 7/7 vs yfinance's independent adjustment) —
    use for ANY multi-month return calc; raw closes fake -90% crashes
    through splits. Written by price_adjuster.py."""
    return _GMD_WAREHOUSE / "ohlcv_adj" / market.upper()


# Backward-compatible alias for the one pre-existing call site
# (data_registry.py's `warehouse.ohlcv_adj_in` Dataset) — same path.
OHLCV_ADJ_IN = _GMD_WAREHOUSE / "ohlcv_adj" / "IN"

JP_SECTORS = GLOBAL_MARKET_DATA / "reference" / "jp_sectors.parquet"


def ltm_seed_gmd(market: str) -> Path:
    """global-market-data's own long-term-seed copy. 🔴 US IS A KNOWN
    INTERRUPTED/INCOMPLETE COLLECTION — prefer ltm_seed() below unless you
    have a specific reason to read this repo's copy instead."""
    return GLOBAL_MARKET_DATA / "cache_seed" / "ltm" / f"{market.upper()}.parquet"


# ── global-stock-screener: fundamentals + long-term seed ────────────────────

def fundamentals_history(market: str) -> Path:
    """Per-market fundamentals cache feeding factor panels/screeners."""
    return (GLOBAL_STOCK_SCREENER / "cache_seed" / "fundamentals_history"
            / f"{market.upper()}.parquet")


def ltm_seed(market: str, *, use_market_data: bool = False) -> Path:
    """Long-term-seed OHLCV panel. Defaults to global-stock-screener's copy
    — the good one for US/JP/KR/CN (global-market-data's US copy is a known
    interrupted collection, see the module docstring). Pass
    use_market_data=True only if you deliberately want that other repo's
    copy instead."""
    if use_market_data:
        return ltm_seed_gmd(market)
    return GLOBAL_STOCK_SCREENER / "cache_seed" / "ltm" / f"{market.upper()}.parquet"


DAMODARAN_COMPANIES = GLOBAL_STOCK_SCREENER / "reference_seed" / "damodaran_companies.parquet"
