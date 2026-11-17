"""
infrastructure/ipo/legacy_adapter.py
========================================
Infrastructure Adapter — wraps the EXISTING ipo_tracker.py / ipo_monitor.py
scripts as the IPO bounded context's data source, without touching or
reimplementing their logic.

WHY AN ADAPTER, NOT A REWRITE
──────────────────────────────
ipo_tracker.py (739 lines) and ipo_monitor.py (107 lines) are working, live
code — bhavcopy-diff discovery, yfinance download/enrichment, gate-scoped
screening, and universe-snapshot new-listing detection across six markets.
Rewriting them inside stock_ddd would duplicate tested logic for zero
behavioural gain. This module is the ONLY place in the IPO bounded context
that imports them; domain/ipo/entities.py never does.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

# ipo_tracker.py / ipo_monitor.py live in the parent code/python_files dir,
# not inside stock_ddd — same path-injection pattern as
# infrastructure/market_data/composite_repository.py.
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import ipo_monitor as _monitor  # noqa: E402
import ipo_tracker as _tracker  # noqa: E402

from domain.ipo.entities import IpoListing, ListingGateStage, NewListingEvent  # noqa: E402
from domain.shared.value_objects import Exchange, Percentage, Price, Ticker  # noqa: E402

# Read thresholds directly off ipo_tracker's own module constants (highest
# first) so a change to GATE_* there is picked up here automatically — this
# is never a copied literal that could drift out of sync.
_GATE_ORDER = [
    (_tracker.GATE_COFFEE_CAN, ListingGateStage.COFFEE_CAN),
    (_tracker.GATE_PIOTROSKI, ListingGateStage.PIOTROSKI),
    (_tracker.GATE_BULL_CARTEL, ListingGateStage.BULL_CARTEL),
    (_tracker.GATE_GOLDEN_CROSS, ListingGateStage.GOLDEN_CROSS),
    (_tracker.GATE_MAGIC_FORMULA, ListingGateStage.MAGIC_FORMULA),
    (_tracker.GATE_DARVAS, ListingGateStage.DARVAS),
]


def _gate_stage(trading_bars: int) -> ListingGateStage:
    for threshold, stage in _GATE_ORDER:
        if trading_bars >= threshold:
            return stage
    return ListingGateStage.PRICE_ONLY


def _price_or_none(value) -> Optional[Price]:
    return Price(float(value), "INR") if value is not None else None


def _row_to_listing(row: dict) -> IpoListing:
    """Maps one dict row from ipo_tracker.enrich_ipo() onto IpoListing."""
    listing_date = None
    if row.get("Listing_Date"):
        try:
            listing_date = date.fromisoformat(row["Listing_Date"])
        except ValueError:
            pass
    gain = row.get("Listing_Gain_%")
    bars = int(row.get("Trading_Bars") or 0)
    return IpoListing(
        ticker=Ticker(row["Symbol"], Exchange.NSE),
        company_name=row.get("Company_Name") or row["Symbol"],
        sector=row.get("Sector") or "—",
        listing_date=listing_date,
        listing_price=_price_or_none(row.get("Listing_Price_₹")),
        current_price=_price_or_none(row.get("Current_LTP_₹")),
        listing_gain=Percentage(float(gain)) if gain is not None else None,
        all_time_high=_price_or_none(row.get("ATH_₹")),
        all_time_low=_price_or_none(row.get("ATL_₹")),
        days_listed=int(row.get("Days_Listed") or 0),
        trading_bars=bars,
        market_cap_cr=row.get("MCap_Cr"),
        trailing_pe=row.get("Trailing_PE"),
        pe_zone=row.get("PE_Zone") or "⚪ N/A",
        gate_stage=_gate_stage(bars),
        screeners_available=row.get("Screeners_Available") or "",
        note=row.get("Note") or "",
    )


def discover_and_enrich_ipo_listings(
    lookback_days: int = _tracker.LOOKBACK_DAYS,
    verbose: bool = False,
) -> List[IpoListing]:
    """
    Behaviour-preserving wrap of ipo_tracker's discover -> download -> enrich
    pipeline. ipo_tracker.main() additionally runs screen_ipo() and writes an
    Excel workbook; this only surfaces the enriched listings as entities for
    callers inside stock_ddd (e.g. application/queries).
    """
    symbols = _tracker.discover_new_listings(lookback_days=lookback_days, verbose=verbose)
    if not symbols:
        return []
    ohlc_map = _tracker.download_ipo_ohlc(symbols, verbose=verbose)
    return [_row_to_listing(_tracker.enrich_ipo(sym, ohlc_map.get(sym))) for sym in symbols]


def check_new_listings(
    markets: List[str],
    seed: bool = False,
    verbose: bool = False,
) -> List[NewListingEvent]:
    """Behaviour-preserving wrap of ipo_monitor.check()."""
    found = _monitor.check(markets, seed=seed, verbose=verbose)
    today = date.today()
    return [
        NewListingEvent(
            market=mkt,
            new=tuple(diff["new"]),
            delisted=tuple(diff["delisted"]),
            as_of=today,
        )
        for mkt, diff in found.items()
    ]
