"""
oilprice_benchmark.py
======================
Independent WTI crude-oil benchmark used to sanity-check the broker's
CRUDEOIL futures quote before it feeds the put-call parity calculation.

MCX Crude Oil futures track NYMEX WTI. A broker feed that has gone stale or
returned a garbage quote would otherwise flow straight into
theoretical_cp_spread() and could trigger a false arbitrage signal on real
money. This module fetches a WTI spot price from OilPriceAPI independently
and flags a large divergence instead.

Not a hard dependency: any failure (missing key, network error, rate limit,
plan restriction) degrades to "benchmark unavailable" rather than blocking
the strategy — see check_crude_futures_price().
"""

import logging
import os
import time
from typing import Optional, Tuple

from .config import (
    OILPRICEAPI_BASE_URL,
    OILPRICEAPI_CACHE_SECONDS,
    OILPRICEAPI_COMMODITY_CODE,
    OILPRICEAPI_ENABLED,
    OILPRICEAPI_MAX_DEVIATION_PCT,
    USD_INR_FALLBACK_RATE,
)

log = logging.getLogger(__name__)

_cache = {"value": None, "fetched_at": 0.0}


def _fetch_usd_inr_rate() -> float:
    """Live USD/INR via yfinance; falls back to the static config rate."""
    try:
        import yfinance as yf
        rate = yf.Ticker("INR=X").fast_info.get("lastPrice")
        if rate:
            return float(rate)
    except Exception as exc:
        log.debug("USD/INR live rate unavailable, using fallback: %s", exc)
    return USD_INR_FALLBACK_RATE


def _fetch_wti_usd_per_bbl() -> Optional[float]:
    """
    WTI price in USD/barrel from OilPriceAPI's `WTI_USD` commodity, which is
    itself front-month NYMEX futures (confirmed via /v1/commodities/WTI_USD:
    instrument="front_month_futures", settlement_venue="NYMEX") even though
    /v1/prices/latest labels the response type "spot_price". OilPriceAPI's
    separate dedicated futures endpoint (opa_get_futures / contract="CL")
    requires a Professional-plan upgrade and returns 403 on lower plans —
    this is the accessible route to a NYMEX-linked benchmark.
    """
    api_key = os.environ.get("OILPRICEAPI_KEY", "")
    if not api_key:
        log.debug("OILPRICEAPI_KEY not set — crude benchmark disabled")
        return None
    import requests
    try:
        resp = requests.get(
            OILPRICEAPI_BASE_URL,
            params={"by_code": OILPRICEAPI_COMMODITY_CODE},
            headers={"Authorization": f"Token {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        return float(resp.json()["data"]["price"])
    except Exception as exc:
        log.warning("OilPriceAPI fetch failed: %s", exc)
        return None


def get_wti_benchmark_inr_per_bbl(force_refresh: bool = False) -> Optional[float]:
    """WTI spot price converted to Rs/barrel, cached for OILPRICEAPI_CACHE_SECONDS."""
    if not OILPRICEAPI_ENABLED:
        return None

    now = time.time()
    if (not force_refresh and _cache["value"] is not None
            and (now - _cache["fetched_at"]) < OILPRICEAPI_CACHE_SECONDS):
        return _cache["value"]

    usd_per_bbl = _fetch_wti_usd_per_bbl()
    if usd_per_bbl is None:
        return None

    inr_per_bbl = usd_per_bbl * _fetch_usd_inr_rate()
    _cache["value"] = inr_per_bbl
    _cache["fetched_at"] = now
    return inr_per_bbl


def check_crude_futures_price(broker_price: float) -> Tuple[bool, Optional[str]]:
    """
    Compare the broker's CRUDEOIL futures quote against the independent WTI
    benchmark. Returns (ok, reason). ok=True both when the quote is within
    tolerance and when the benchmark itself is unavailable — absence of a
    benchmark is not evidence the broker quote is wrong (fail-open).
    """
    benchmark = get_wti_benchmark_inr_per_bbl()
    if benchmark is None:
        return True, None

    deviation = abs(broker_price - benchmark) / benchmark
    if deviation > OILPRICEAPI_MAX_DEVIATION_PCT:
        return False, (
            f"CRUDEOIL broker futures={broker_price:.2f} vs WTI benchmark="
            f"{benchmark:.2f} Rs/bbl — {deviation:.1%} deviation exceeds "
            f"{OILPRICEAPI_MAX_DEVIATION_PCT:.0%} tolerance"
        )
    return True, None
