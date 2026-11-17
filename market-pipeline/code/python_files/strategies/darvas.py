#!/usr/bin/env python3
# Darvas Box — Nicolas Darvas ("How I Made $2,000,000 in the Stock Market", 1960).
# A stock consolidates in a "box" (confirmed resistance = box top, confirmed
# support = box bottom) for several bars; buy on a breakout above the box top,
# sell on a breakdown below the box bottom.
#
# Box detection is scan_core.compute_darvas_box — the one implementation the
# full_*_market_scan.py scripts call. This module used to carry its own copy
# "kept in sync", and it had drifted: it still zero-filled NaN bars (a missing
# final close read as price 0 → BREAKDOWN_SELL, the Korea 2026-07-21 incident
# scan_core had already fixed) and matched columns by substring. Delegating
# makes "Darvas" mean the same thing everywhere by construction.
from __future__ import annotations

import sys
from pathlib import Path

from .base import StockData, Result

_PF = str(Path(__file__).resolve().parents[1])     # python_files, home of scan_core
if _PF not in sys.path:
    sys.path.insert(0, _PF)
import scan_core as _scan_core  # noqa: E402

META = {"name": "Darvas Box", "slug": "darvas", "category": "technical",
        "description": "Nicolas Darvas box breakout: price breaks above a confirmed "
                       "consolidation range (box top) after several bars of support.",
        "needs": "price"}

CONFIRM = 3   # bars either side of a candidate box edge that must not exceed it
_NO_SIGNAL = ("INSUFFICIENT_DATA", "NO_DATA", "NO_BOX")


def _compute_box(df) -> dict:
    """Box top/bottom detection with the current bar excluded from box formation."""
    return _scan_core.compute_darvas_box(df, confirm=CONFIRM, decimals=2)


def screen(s: StockData) -> Result | None:
    df = s.ohlcv
    if df is None or len(df) < CONFIRM + 5:
        return None
    box = _compute_box(df)
    if box["signal"] in _NO_SIGNAL:
        return None
    passed = box["signal"] == "BREAKOUT_BUY"
    return Result(s.symbol, META["slug"], passed=passed,
                  score=box.get("position_in_box_pct"),   # further above the box ranks higher
                  metrics={"LTP": box["current_price"], "Box_Top": box["box_top"],
                           "Box_Bottom": box["box_bottom"],
                           "Position_in_Box%": box.get("position_in_box_pct"),
                           "Upside_to_Top%": box.get("upside_to_top_pct")},
                  note=box["signal"])
