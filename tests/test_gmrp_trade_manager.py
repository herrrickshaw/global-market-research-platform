"""Offline tests for put_call_parity/trade_manager.py with a fake in-memory broker."""
import json
import sys

import pytest

import gmrp_helpers as H

if H.ROOT not in sys.path:
    sys.path.insert(0, H.ROOT)

from put_call_parity import trade_manager as tm  # noqa: E402
from put_call_parity.broker import BrokerBase  # noqa: E402
from put_call_parity.config import INSTRUMENTS  # noqa: E402
from put_call_parity.parity_engine import ParitySignal  # noqa: E402


class FakeBroker(BrokerBase):
    def __init__(self, prices=None, fail_place=None, status_for=None):
        self.orders = []            # place_order kwargs, in order
        self.prices = prices or {}  # tradingsymbol -> average_price
        self.fail_place = fail_place or {}   # (symbol, side) -> exception
        self.status_for = status_for or {}   # tradingsymbol -> status dict override
        self._sym = {}

    def login(self): ...
    def get_quote(self, instruments): return {}
    def get_option_chain(self, underlying, expiry, exchange): return []
    def cancel_order(self, order_id): ...
    def get_positions(self): return []

    def place_order(self, tradingsymbol, exchange, transaction_type, quantity, order_type,
                    price=0.0, trigger_price=0.0, product="NRML", tag=""):
        key = (tradingsymbol, transaction_type)
        if key in self.fail_place:
            raise self.fail_place[key]
        self.orders.append(dict(tradingsymbol=tradingsymbol, exchange=exchange,
                                transaction_type=transaction_type, quantity=quantity,
                                order_type=order_type, product=product, tag=tag))
        oid = f"O{len(self.orders)}"
        self._sym[oid] = tradingsymbol
        return oid

    def get_order_status(self, order_id):
        sym = self._sym[order_id]
        if sym in self.status_for:
            return self.status_for[sym]
        return {"status": "COMPLETE", "average_price": self.prices.get(sym, 0.0)}


def _closed():
    with open("closed_positions.json") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def _no_sleep_and_tmp_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)           # closed_positions.json is written to cwd
    monkeypatch.setattr(tm.time, "sleep", lambda s: None)


def make_signal(direction="SHORT_CALL_LONG_PUT", instrument="BANKNIFTY", lots=2, strike=50000.0):
    return ParitySignal(instrument=instrument, expiry="2026-01-29", strike=strike, dte=10.0,
                        futures_price=50000.0, call_mid=300.0, put_mid=200.0,
                        call_symbol="CALL", put_symbol="PUT", futures_symbol="FUT",
                        theoretical_spread=0.0, observed_spread=100.0, raw_deviation=100.0,
                        transaction_cost=10.0, net_deviation=90.0, direction=direction, lots=lots)


# ── PositionBook ─────────────────────────────────────────────────────────────

def test_book_persists_and_reloads(tmp_path):
    p = tmp_path / "pos.json"
    b = tm.PositionBook(str(p))
    assert len(b) == 0 and b.get_all() == {}
    b.add("a", {"x": 1})
    b.add("b", {"x": 2})
    assert len(b) == 2 and b.get("a") == {"x": 1}
    assert json.loads(p.read_text()) == {"a": {"x": 1}, "b": {"x": 2}}
    b2 = tm.PositionBook(str(p))
    assert b2.get_all() == {"a": {"x": 1}, "b": {"x": 2}}


def test_book_remove_and_get_all_is_a_copy(tmp_path):
    p = tmp_path / "pos.json"
    b = tm.PositionBook(str(p))
    b.add("a", {})
    b.get_all().clear()
    assert len(b) == 1
    b.remove("missing")                   # no error, no write needed
    b.remove("a")
    assert len(b) == 0 and json.loads(p.read_text()) == {}
    assert b.get("a") is None


def test_book_serialises_non_json_values_as_strings(tmp_path):
    from datetime import date
    b = tm.PositionBook(str(tmp_path / "p.json"))
    b.add("a", {"d": date(2026, 1, 2)})
    assert json.loads((tmp_path / "p.json").read_text())["a"]["d"] == "2026-01-02"


def test_book_default_path_is_config_position_file(tmp_path):
    b = tm.PositionBook()
    assert str(b._path) == tm.POSITION_FILE


# ── _wait_for_fill ───────────────────────────────────────────────────────────

class SeqBroker:
    def __init__(self, seq):
        self.seq = list(seq)
        self.calls = 0

    def get_order_status(self, oid):
        self.calls += 1
        return self.seq.pop(0) if len(self.seq) > 1 else self.seq[0]


def test_wait_for_fill_polls_until_complete_case_insensitive():
    b = SeqBroker([{"status": "OPEN"}, {"status": "pending"}, {"status": "filled", "average_price": 5}])
    out = tm._wait_for_fill(b, "o")
    assert out["average_price"] == 5 and b.calls == 3


@pytest.mark.parametrize("state", ["CANCELLED", "rejected"])
def test_wait_for_fill_raises_on_terminal_failure(state):
    b = SeqBroker([{"status": state, "status_message": "no margin"}])
    with pytest.raises(RuntimeError, match="no margin"):
        tm._wait_for_fill(b, "o")


def test_wait_for_fill_times_out(monkeypatch):
    t = {"now": 0.0}
    monkeypatch.setattr(tm.time, "time", lambda: t["now"])
    monkeypatch.setattr(tm.time, "sleep", lambda s: t.__setitem__("now", t["now"] + s))
    b = SeqBroker([{"status": "OPEN"}])
    with pytest.raises(TimeoutError, match="not filled within 5.0s"):
        tm._wait_for_fill(b, "o", timeout=5.0, poll=1.0)
    assert b.calls == 5


def test_wait_for_fill_missing_status_key_keeps_polling():
    b = SeqBroker([{}, {"status": "COMPLETE", "average_price": 1}])
    assert tm._wait_for_fill(b, "o")["average_price"] == 1


# ── enter_trade ──────────────────────────────────────────────────────────────

def test_enter_short_call_long_put_places_three_legs_and_records(tmp_path):
    br = FakeBroker(prices={"CALL": 300.5, "PUT": 199.5, "FUT": 50010.0})
    book = tm.PositionBook(str(tmp_path / "pos.json"))
    pid = tm.TradeManager(br, book).enter_trade(make_signal(lots=2))
    assert pid and pid.startswith("BANKNIFTY_2026-01-29_50000_")
    sides = [(o["tradingsymbol"], o["transaction_type"]) for o in br.orders]
    assert sides == [("CALL", "SELL"), ("PUT", "BUY"), ("FUT", "SELL")]
    assert all(o["quantity"] == 30 and o["order_type"] == "MARKET" and o["product"] == "NRML"
               and o["exchange"] == "NFO" and o["tag"] == "PCP_BANKNIFTY_50000" for o in br.orders)
    pos = book.get(pid)
    assert pos["entry_call_price"] == 300.5 and pos["entry_put_price"] == 199.5
    assert pos["entry_futures_price"] == 50010.0
    assert pos["qty"] == 30 and pos["lots"] == 2 and pos["entry_deviation"] == 100.0
    assert pos["segment"] == "NFO" and pos["exchange"] == "NSE"
    assert set(pos["order_ids"]) == {"call", "put", "fut"}


def test_enter_long_call_short_put_reverses_sides_and_custom_tag(tmp_path):
    br = FakeBroker()
    book = tm.PositionBook(str(tmp_path / "pos.json"))
    sig = make_signal("LONG_CALL_SHORT_PUT", instrument="CRUDEOIL", lots=1, strike=6000.4)
    tm.TradeManager(br, book).enter_trade(sig, tag_prefix="XY")
    assert [(o["tradingsymbol"], o["transaction_type"]) for o in br.orders] == \
        [("CALL", "BUY"), ("PUT", "SELL"), ("FUT", "BUY")]
    assert all(o["exchange"] == "MCX-FO" and o["quantity"] == 100 and o["tag"] == "XY_CRUDEOIL_6000"
               for o in br.orders)


def test_enter_failure_on_first_leg_unwinds_nothing(tmp_path):
    br = FakeBroker(fail_place={("CALL", "SELL"): RuntimeError("down")})
    book = tm.PositionBook(str(tmp_path / "pos.json"))
    assert tm.TradeManager(br, book).enter_trade(make_signal()) is None
    assert br.orders == [] and len(book) == 0


def test_enter_failure_on_third_leg_unwinds_filled_legs(tmp_path):
    br = FakeBroker(fail_place={("FUT", "SELL"): RuntimeError("margin")})
    book = tm.PositionBook(str(tmp_path / "pos.json"))
    assert tm.TradeManager(br, book).enter_trade(make_signal(lots=1)) is None
    placed = [(o["tradingsymbol"], o["transaction_type"], o["tag"]) for o in br.orders]
    assert placed[:2] == [("CALL", "SELL", "PCP_BANKNIFTY_50000"), ("PUT", "BUY", "PCP_BANKNIFTY_50000")]
    # unwind: reverse of the two legs that exist
    assert placed[2:] == [("CALL", "BUY", "UNWIND_PCP_BANKNIFTY_50000"),
                          ("PUT", "SELL", "UNWIND_PCP_BANKNIFTY_50000")]
    assert len(book) == 0


def test_unwind_failure_is_swallowed_and_continues(tmp_path):
    br = FakeBroker(fail_place={("FUT", "SELL"): RuntimeError("margin"),
                                ("CALL", "BUY"): RuntimeError("also down")})
    book = tm.PositionBook(str(tmp_path / "pos.json"))
    assert tm.TradeManager(br, book).enter_trade(make_signal()) is None
    assert ("PUT", "SELL") in [(o["tradingsymbol"], o["transaction_type"]) for o in br.orders]


def test_unwind_unknown_direction_places_nothing(tmp_path):
    br = FakeBroker()
    mgr = tm.TradeManager(br, tm.PositionBook(str(tmp_path / "p.json")))
    sig = make_signal("NONE")
    mgr._emergency_unwind({"call": "O1"}, {}, sig, INSTRUMENTS["BANKNIFTY"], 15, "T")
    assert br.orders == []


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="trade_manager.py:enter_trade records order_ids[leg] before _wait_for_fill, so a "
                          "REJECTED leg is 'unwound' with an opposite market order, opening a position "
                          "that never existed")
def test_rejected_leg_is_not_unwound(tmp_path):
    br = FakeBroker(status_for={"PUT": {"status": "REJECTED", "status_message": "x"}})
    tm.TradeManager(br, tm.PositionBook(str(tmp_path / "p.json"))).enter_trade(make_signal())
    unwound = [o["tradingsymbol"] for o in br.orders if o["tag"].startswith("UNWIND_")]
    assert "PUT" not in unwound


def test_rejected_leg_aborts_entry_and_unwinds_prior_filled_leg(tmp_path):
    br = FakeBroker(status_for={"PUT": {"status": "REJECTED", "status_message": "x"}})
    book = tm.PositionBook(str(tmp_path / "p.json"))
    assert tm.TradeManager(br, book).enter_trade(make_signal()) is None
    assert ("CALL", "BUY") in [(o["tradingsymbol"], o["transaction_type"]) for o in br.orders]
    assert "FUT" not in [o["tradingsymbol"] for o in br.orders]
    assert len(book) == 0


# ── exit_trade / pnl ─────────────────────────────────────────────────────────

def _enter(tmp_path, direction="SHORT_CALL_LONG_PUT", instrument="BANKNIFTY"):
    entry = FakeBroker(prices={"CALL": 300.0, "PUT": 200.0, "FUT": 50000.0})
    book = tm.PositionBook(str(tmp_path / "pos.json"))
    pid = tm.TradeManager(entry, book).enter_trade(make_signal(direction, instrument, lots=2))
    return book, pid


def test_exit_unknown_position_returns_false(tmp_path):
    mgr = tm.TradeManager(FakeBroker(), tm.PositionBook(str(tmp_path / "p.json")))
    assert mgr.exit_trade("nope") is False


def test_exit_short_call_position_reverses_and_computes_pnl(tmp_path):
    book, pid = _enter(tmp_path)
    br = FakeBroker(prices={"CALL": 250.0, "PUT": 230.0, "FUT": 49900.0})
    ok = tm.TradeManager(br, book).exit_trade(pid, reason="PROFIT_TARGET")
    assert ok is True
    assert [(o["tradingsymbol"], o["transaction_type"]) for o in br.orders] == \
        [("CALL", "BUY"), ("PUT", "SELL"), ("FUT", "BUY")]
    assert all(o["tag"] == f"EXIT_{pid[:20]}" and o["exchange"] == "NFO" and o["quantity"] == 30
               for o in br.orders)
    assert len(book) == 0
    log = _closed()
    assert len(log) == 1
    rec = log[0]
    # sold call 300 -> 250: +50 ; bought put 200 -> 230: +30 ; sold fut 50000 -> 49900: +100 ; qty 30
    assert rec["pnl"] == (50 + 30 + 100) * 30
    assert rec["exit_reason"] == "PROFIT_TARGET"
    assert rec["exit_prices"] == {"call": 250.0, "put": 230.0, "fut": 49900.0}
    assert "exit_time" in rec and rec["position_id"] == pid


def test_exit_long_call_position_pnl(tmp_path):
    book, pid = _enter(tmp_path, "LONG_CALL_SHORT_PUT")
    br = FakeBroker(prices={"CALL": 350.0, "PUT": 150.0, "FUT": 50100.0})
    assert tm.TradeManager(br, book).exit_trade(pid) is True
    assert [(o["tradingsymbol"], o["transaction_type"]) for o in br.orders] == \
        [("CALL", "SELL"), ("PUT", "BUY"), ("FUT", "SELL")]
    rec = _closed()[0]
    assert rec["pnl"] == (50 + 50 + 100) * 30
    assert rec["exit_reason"] == ""


def test_exit_appends_to_existing_closed_log(tmp_path):
    book, pid = _enter(tmp_path)
    with open("closed_positions.json", "w") as f:
        json.dump([{"old": 1}], f)
    tm.TradeManager(FakeBroker(), book).exit_trade(pid)
    log = _closed()
    assert log[0] == {"old": 1} and len(log) == 2


def test_exit_leg_failure_keeps_position_and_returns_false(tmp_path):
    book, pid = _enter(tmp_path)
    br = FakeBroker(fail_place={("PUT", "SELL"): RuntimeError("down")})
    assert tm.TradeManager(br, book).exit_trade(pid) is False
    assert len(book) == 1 and book.get(pid) is not None
    # the other legs were still attempted
    assert [o["tradingsymbol"] for o in br.orders] == ["CALL", "FUT"]
    import os
    assert not os.path.exists("closed_positions.json")


def test_calculate_pnl_missing_exit_price_defaults_to_zero(tmp_path):
    mgr = tm.TradeManager(FakeBroker(), tm.PositionBook(str(tmp_path / "p.json")))
    pos = {"direction": "SHORT_CALL_LONG_PUT", "lots": 1, "qty": 10, "entry_call_price": 5.0,
           "entry_put_price": 3.0, "entry_futures_price": 100.0}
    assert mgr._calculate_pnl(pos, {}, INSTRUMENTS["BANKNIFTY"]) == (5 - 0) * 10 + (0 - 3) * 10 + (100 - 0) * 10
