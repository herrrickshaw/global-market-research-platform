"""
domain/ipo/entities.py
=========================
IPO / New-Listing Domain — Value Objects.

DOMAIN CONCEPTS
───────────────
IpoListing      : A stock that listed within the tracking window, carrying
                  the same fields ipo_tracker.enrich_ipo() already computes
                  (listing price/gain, ATH/ATL, sector, PE) plus a
                  ListingGateStage classification.

NewListingEvent : One market's new-listing/delisting diff for a single run
                  of ipo_monitor.check() (its universe-snapshot-diff path —
                  SEC/JPX/KRX/SGX/Eastmoney/bhavcopy — independent of the
                  NSE-specific enrichment IpoListing wraps).

These are VALUE OBJECTS (Evans 2003) — immutable, equality by value. They
wrap output that already exists; they do not recompute it. See
infrastructure/ipo/legacy_adapter.py for the mapping from ipo_tracker.py's
and ipo_monitor.py's raw dict rows onto these entities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional, Tuple

from domain.shared.value_objects import Percentage, Price, Ticker


class ListingGateStage(str, Enum):
    """
    Mirrors ipo_tracker.py's GATE_* trading-bar thresholds (35 / 60 / 200 /
    252 / 504 / 756) — which screeners are statistically meaningful yet,
    given how many trading bars a new listing has accumulated.

    Kept as an independent domain enum rather than importing the legacy
    module's constants directly: legacy_adapter.py reads the actual
    threshold VALUES off ipo_tracker.py at runtime (see `_GATE_ORDER`
    there), so the two cannot silently drift apart, while the domain
    layer itself stays free of any import from infrastructure/legacy code.
    """
    PRICE_ONLY    = "PRICE_ONLY"     # < 35 bars:  LTP, listing gain, ATH/ATL only
    DARVAS        = "DARVAS"         # 35+  bars:  + Darvas Box breakout
    MAGIC_FORMULA = "MAGIC_FORMULA"  # 60+  bars:  + Magic Formula
    GOLDEN_CROSS  = "GOLDEN_CROSS"   # 200+ bars:  + 50/200 DMA
    BULL_CARTEL   = "BULL_CARTEL"    # 252+ bars:  + quarterly growth
    PIOTROSKI     = "PIOTROSKI"      # 504+ bars:  + F-Score
    COFFEE_CAN    = "COFFEE_CAN"     # 756+ bars:  full suite


@dataclass(frozen=True)
class IpoListing:
    """
    A newly-listed stock under IPO tracking.

    Immutable snapshot of what ipo_tracker.enrich_ipo() already computed for
    one symbol — this entity does not re-derive any of it.
    """
    ticker:              Ticker
    company_name:        str
    sector:              str
    listing_date:        Optional[date]
    listing_price:       Optional[Price]
    current_price:       Optional[Price]
    listing_gain:        Optional[Percentage]
    all_time_high:       Optional[Price]
    all_time_low:        Optional[Price]
    days_listed:         int
    trading_bars:        int
    market_cap_cr:       Optional[float]
    trailing_pe:         Optional[float]
    pe_zone:             str
    gate_stage:          ListingGateStage
    screeners_available: str
    discovery_source:    str = "bhavcopy_diff"  # ipo_tracker.discover_new_listings()
    note:                str = ""

    @property
    def is_screenable(self) -> bool:
        """False only when there was no OHLC data at all (enrich_ipo's 'no_ohlc' note)."""
        return self.note != "no_ohlc"

    @property
    def is_profitable_since_listing(self) -> bool:
        return bool(self.listing_gain and self.listing_gain.value > 0)


@dataclass(frozen=True)
class NewListingEvent:
    """
    One market's new-listing/delisting diff for a single ipo_monitor.check() run.
    """
    market:   str
    new:      Tuple[str, ...]
    delisted: Tuple[str, ...]
    as_of:    date

    @property
    def has_activity(self) -> bool:
        return bool(self.new or self.delisted)
