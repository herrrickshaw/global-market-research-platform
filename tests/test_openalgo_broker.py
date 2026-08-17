"""
test_openalgo_broker.py — the OpenAlgo adapter's mapping, with no network.

WHY MOCKED AND NOT LIVE. Reaching a real OpenAlgo instance needs the operator's
running service and a broker key, so a live test would be un-runnable in CI and
would place real orders if anyone got the flags wrong. Every failure this guards
against is a MAPPING failure — field renames, a date format, a filter — which is
exactly what a fixture proves and a live call obscures behind network noise.

The fixtures are copied verbatim from docs.openalgo.in response samples, so a
breaking upstream change surfaces here as a red test rather than as an empty
option chain at 09:15.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.expanduser("~"))
from put_call_parity import broker as B  # noqa: E402


@pytest.fixture()
def ob():
    o = B.OpenAlgoBroker.__new__(B.OpenAlgoBroker)
    o.apikey, o.base, o.strategy_tag, o._session = "k", "http://x", "t", None
    return o


# --- expiry formats -------------------------------------------------------
# 🔴 The regression this exists for: /expiry and /search return "30-DEC-25",
# /optionchain wants "30DEC25". Feeding one to the other returns an EMPTY chain
# with status=success — indistinguishable from a genuine holiday, and silent.

@pytest.mark.parametrize("src,chain,iso", [
    ("10-JUL-25", "10JUL25", "2025-07-10"),
    ("30-DEC-25", "30DEC25", "2025-12-30"),
    ("2025-07-10", "10JUL25", "2025-07-10"),
    ("30DEC25", "30DEC25", "2025-12-30"),
])
def test_expiry_conversions(ob, src, chain, iso):
    assert ob._expiry_to_chain_format(src) == chain
    assert ob._expiry_to_iso(src) == iso


# --- option chain ---------------------------------------------------------

CHAIN = {"status": "success", "underlying": "NIFTY", "underlying_ltp": 26215.55,
         "atm_strike": 26200.0, "chain": [{
             "strike": 26100.0,
             "ce": {"symbol": "NIFTY30DEC2526100CE", "ltp": 180.5, "bid": 180.0,
                    "ask": 181.0, "oi": 45000, "volume": 1200, "lotsize": 65},
             "pe": {"symbol": "NIFTY30DEC2526100PE", "ltp": 60.2, "bid": 60.0,
                    "ask": 60.5, "oi": 38000, "volume": 900, "lotsize": 65}}]}


def test_chain_flattens_to_kite_contract(ob):
    """OpenAlgo pairs ce/pe per strike; strategy.py consumes a flat Kite list."""
    ob._post = lambda p, pay, tries=3: CHAIN
    rows = ob.get_option_chain("NIFTY", "30-DEC-25", "NSE_INDEX")
    assert [r["instrument_type"] for r in rows] == ["CE", "PE"]
    required = {"strike", "instrument_type", "tradingsymbol", "last_price",
                "bid", "ask", "oi", "volume", "instrument_token", "exchange"}
    for r in rows:
        assert required.issubset(r), f"missing {required - set(r)}"
        # OI drives the min-500 liquidity filter; losing it silently admits
        # untradeable strikes into the signal.
        assert r["oi"] > 0
        # OpenAlgo has no numeric token — the symbol IS the identifier. None
        # here would look like a token that failed to resolve.
        assert r["instrument_token"] == r["tradingsymbol"]


# --- quotes + depth -------------------------------------------------------

QUOTE = {"data": {"open": 760.0, "high": 774.0, "low": 758.15, "ltp": 769.6,
                  "ask": 769.6, "bid": 769.4, "prev_close": 746.9, "volume": 9362799}}
DEPTH = {"data": {"oi": 161265750,
                  "asks": [{"price": 769.6, "quantity": 767}],
                  "bids": [{"price": 769.4, "quantity": 886}]}}


def test_quote_merges_depth_into_kite_shape(ob):
    """strategy.py reads data['depth']['buy'][0]['price'].

    /quotes alone has no ladder, so without the merge every leg would fall back
    to LTP and the parity deviation would be measured against a price nobody can
    trade at.
    """
    ob._post = lambda path, pay, tries=3: {"quotes": QUOTE, "depth": DEPTH}[path]
    q = ob.get_quote(["NFO:SBIN"])["NFO:SBIN"]
    bid = q["depth"]["buy"][0]["price"]
    ask = q["depth"]["sell"][0]["price"]
    assert (bid, ask) == (769.4, 769.6)
    assert (bid + ask) / 2 == pytest.approx(769.5)
    assert q["last_price"] == 769.6
    assert q["oi"] == 161265750          # carried from /depth, absent in /quotes


def test_quote_survives_depth_failure(ob):
    """A missing ladder must degrade to LTP, not lose the quote entirely."""
    def _post(path, pay, tries=3):
        if path == "depth":
            raise RuntimeError("depth unavailable")
        return QUOTE
    ob._post = _post
    q = ob.get_quote(["NFO:SBIN"])["NFO:SBIN"]
    assert q["last_price"] == 769.6
    assert q["depth"] == {"buy": [], "sell": []}


# --- futures lookup -------------------------------------------------------

SEARCH = {"status": "success", "data": [
    {"symbol": "BANKNIFTY30DEC25FUT", "name": "BANKNIFTY", "expiry": "30-DEC-25",
     "instrumenttype": "FUT", "lotsize": 15, "token": "NSE_FO|1"},
    {"symbol": "BANKNIFTY27NOV25FUT", "name": "BANKNIFTY", "expiry": "27-NOV-25",
     "instrumenttype": "FUT", "lotsize": 15, "token": "NSE_FO|2"},
    {"symbol": "BANKNIFTY30DEC2550000CE", "name": "BANKNIFTY", "expiry": "30-DEC-25",
     "instrumenttype": "CE", "lotsize": 15, "token": "x"},
    {"symbol": "NIFTY30DEC25FUT", "name": "NIFTY", "expiry": "30-DEC-25",
     "instrumenttype": "FUT", "lotsize": 65, "token": "y"}]}


def test_futures_contracts_filter_and_sort(ob):
    """Closes the hole that left Upstox/Angel unable to price parity at all."""
    ob._post = lambda p, pay, tries=3: SEARCH
    rows = ob.get_futures_contracts("BANKNIFTY", "NFO")
    assert [r["tradingsymbol"] for r in rows] == [
        "BANKNIFTY27NOV25FUT", "BANKNIFTY30DEC25FUT"]      # sorted, nearest first
    assert all(r["instrument_type"] == "FUT" for r in rows)  # CE excluded
    assert all(r["name"] != "NIFTY" for r in rows)           # other underlying excluded
    # ISO expiry: strategy.py now compares as a plain string across all adapters.
    assert rows[0]["expiry"] == "2025-11-27"


def test_expiries_normalised_to_iso_and_sorted(ob):
    """/expiry returns DD-MMM-YY; _nearest_expiries compares ISO strings.

    This is the one that feeds the whole scan loop — get it wrong and the run
    completes having examined nothing, reporting 'no opportunities'.
    """
    ob._post = lambda p, pay, tries=3: {"status": "success",
                                        "data": ["31-JUL-25", "10-JUL-25", "07-AUG-25"]}
    assert ob.get_expiries("NIFTY", "NFO") == ["2025-07-10", "2025-07-31", "2025-08-07"]


def test_default_expiries_is_empty_not_raising():
    class Bare(B.BrokerBase):
        def login(self): ...
        def get_quote(self, i): return {}
        def get_option_chain(self, u, e, x): return []
        def place_order(self, *a, **k): return ""
        def get_order_status(self, o): return {}
        def cancel_order(self, o): ...
        def get_positions(self): return []
    assert Bare().get_expiries("X", "NFO") == []


def test_default_futures_contracts_is_empty_not_raising():
    """BrokerBase's default must not raise — an abstractmethod here would turn
    Upstox/Angel's silent gap into an import-time outage."""
    class Bare(B.BrokerBase):
        def login(self): ...
        def get_quote(self, i): return {}
        def get_option_chain(self, u, e, x): return []
        def place_order(self, *a, **k): return ""
        def get_order_status(self, o): return {}
        def cancel_order(self, o): ...
        def get_positions(self): return []
    assert Bare().get_futures_contracts("X", "NFO") == []


# --- error handling -------------------------------------------------------

def test_domain_error_raises_despite_http_200(ob):
    """OpenAlgo returns HTTP 200 with {"status":"error"} for domain failures.

    Without this check the caller gets {} and reads it as 'no data' — the same
    class of silent-empty that this whole adapter's comments keep warning about.
    """
    class R:
        status_code = 200
        def raise_for_status(self): ...
        def json(self): return {"status": "error", "message": "Invalid symbol"}
    ob._session = type("S", (), {"post": lambda *a, **k: R()})()
    with pytest.raises(RuntimeError, match="Invalid symbol"):
        ob._post("quotes", {"symbol": "NOPE", "exchange": "NSE"})
