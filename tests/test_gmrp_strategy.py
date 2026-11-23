"""Offline tests for put_call_parity/strategy.py (fake broker, fixed clock, tmp cwd)."""
import importlib
import logging
import sys
from datetime import date

import pytest

import gmrp_helpers as H

if H.ROOT not in sys.path:
    sys.path.insert(0, H.ROOT)


class _FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 1, 1)


@pytest.fixture()
def st(monkeypatch, tmp_path):
    """Import strategy with logging.basicConfig neutralised (it opens parity_trader.log)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(logging, "basicConfig", lambda *a, **k: None)
    monkeypatch.setattr(logging, "FileHandler", lambda *a, **k: logging.NullHandler())
    sys.modules.pop("put_call_parity.strategy", None)
    mod = importlib.import_module("put_call_parity.strategy")
    monkeypatch.setattr(mod, "date", _FixedDate)
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    yield mod
    sys.modules.pop("put_call_parity.strategy", None)


class KiteLike:
    def __init__(self, instruments):
        self._i = instruments

    def instruments(self, segment):
        self.segment = segment
        return self._i


class FakeBroker:
    """BrokerBase duck: has .kite for instrument lookups."""

    def __init__(self, instruments=(), quotes=None, chain=None, chain_exc=None, quote_exc=None):
        self.kite = KiteLike(list(instruments))
        self.quotes = quotes or {}
        self.chain = chain or []
        self.chain_exc = chain_exc
        self.quote_exc = quote_exc
        self.chain_calls = []

    def get_quote(self, syms):
        if self.quote_exc:
            raise self.quote_exc
        return {s: self.quotes[s] for s in syms if s in self.quotes}

    def get_option_chain(self, underlying, expiry, exchange):
        self.chain_calls.append((underlying, expiry, exchange))
        if self.chain_exc:
            raise self.chain_exc
        return self.chain


def inst(name="BANKNIFTY", expiry="2026-01-29", typ="CE", sym="BNF"):
    return {"name": name, "expiry": expiry, "instrument_type": typ, "tradingsymbol": sym}


# -- _nearest_expiries ---------------------------------------------------------

def test_nearest_expiries_filters_dte_window_dedupes_and_sorts(st):
    b = FakeBroker([
        inst(expiry=date(2026, 1, 29)), inst(expiry="2026-01-29", typ="PE"),   # dup (date & str forms)
        inst(expiry="2026-01-03"),     # dte 2  -> included (>= MIN_DTE)
        inst(expiry="2026-01-02"),     # dte 1  -> excluded
        inst(expiry="2026-01-31"),     # dte 30 -> included (<= MAX_DTE)
        inst(expiry="2026-02-01"),     # dte 31 -> excluded
        inst(name="OTHER", expiry="2026-01-10"),
    ])
    assert st._nearest_expiries(b, "BANKNIFTY") == ["2026-01-03", "2026-01-29", "2026-01-31"]
    assert b.kite.segment == "NFO"


def test_nearest_expiries_broker_without_kite_is_empty(st):
    class NoKite:
        pass
    assert st._nearest_expiries(NoKite(), "BANKNIFTY") == []


# -- futures lookups -----------------------------------------------------------

FUT = inst(typ="FUT", sym="BNFJAN")


def test_futures_quote_mid_of_depth(st):
    q = {"NFO:BNFJAN": {"depth": {"buy": [{"price": 100.0}], "sell": [{"price": 102.0}]}, "last_price": 50}}
    assert st._get_futures_quote(FakeBroker([FUT], quotes=q), "BANKNIFTY", "2026-01-29") == 101.0


def test_futures_quote_falls_back_to_last_price_when_one_side_empty(st):
    q = {"NFO:BNFJAN": {"depth": {"buy": [{"price": 0}], "sell": [{"price": 102.0}]}, "last_price": 99.5}}
    assert st._get_futures_quote(FakeBroker([FUT], quotes=q), "BANKNIFTY", "2026-01-29") == 99.5
    q = {"NFO:BNFJAN": {"depth": None, "last_price": 98.0}}
    assert st._get_futures_quote(FakeBroker([FUT], quotes=q), "BANKNIFTY", "2026-01-29") == 98.0


def test_futures_quote_missing_contract_or_error_returns_none(st):
    assert st._get_futures_quote(FakeBroker([FUT]), "BANKNIFTY", "2026-02-26") is None
    assert st._get_futures_quote(FakeBroker([inst(typ="CE")]), "BANKNIFTY", "2026-01-29") is None
    b = FakeBroker([FUT], quote_exc=RuntimeError("down"))
    assert st._get_futures_quote(b, "BANKNIFTY", "2026-01-29") is None


def test_futures_quote_unquoted_symbol_gives_none(st):
    assert st._get_futures_quote(FakeBroker([FUT]), "BANKNIFTY", "2026-01-29") is None


def test_futures_symbol_found_default_and_error(st):
    assert st._get_futures_symbol(FakeBroker([FUT]), "BANKNIFTY", "2026-01-29") == "BNFJAN"
    assert st._get_futures_symbol(FakeBroker([FUT]), "BANKNIFTY", "2026-02-26") == "BANKNIFTY"
    assert st._get_futures_symbol(FakeBroker([FUT]), "CRUDEOIL", "2026-01-29") == "CRUDEOIL"

    class Boom:
        class kite:
            @staticmethod
            def instruments(seg):
                raise RuntimeError("x")
    assert st._get_futures_symbol(Boom(), "BANKNIFTY", "2026-01-29") == "BANKNIFTY"


# -- _refresh_option_prices ----------------------------------------------------

POS = {"segment": "NFO", "call_symbol": "C", "put_symbol": "P"}


def test_refresh_option_prices_uses_depth_then_last_price(st):
    q = {"NFO:C": {"depth": {"buy": [{"price": 10.0}], "sell": [{"price": 12.0}]}, "last_price": 11.0},
         "NFO:P": {"depth": {"buy": [{"price": 0}], "sell": [{}]}, "last_price": 7.0}}
    out = st._refresh_option_prices(FakeBroker(quotes=q), POS)
    assert out == {"call_bid": 10.0, "call_ask": 12.0, "put_bid": 7.0, "put_ask": 7.0}


def test_refresh_option_prices_missing_quote_defaults_zero(st):
    out = st._refresh_option_prices(FakeBroker(quotes={}), POS)
    assert out == {"call_bid": 0, "call_ask": 0, "put_bid": 0, "put_ask": 0}


def test_refresh_option_prices_quote_failure_returns_empty(st):
    assert st._refresh_option_prices(FakeBroker(quote_exc=RuntimeError("x")), POS) == {}


# -- Strategy -----------------------------------------------------------------

def chain_rows(strike, call_mid, put_mid, oi=1000):
    return [
        {"strike": strike, "instrument_type": "CE", "bid": call_mid - 1, "ask": call_mid + 1, "oi": oi,
         "tradingsymbol": f"C{strike}"},
        {"strike": strike, "instrument_type": "PE", "bid": put_mid - 1, "ask": put_mid + 1, "oi": oi,
         "tradingsymbol": f"P{strike}"},
    ]


def fut_quote(mid=50000.0):
    return {"NFO:BNFJAN": {"depth": {"buy": [{"price": mid - 1}], "sell": [{"price": mid + 1}]}}}


class _TM:
    def __init__(self):
        self.entered = []
        self.exited = []

    def enter_trade(self, sig):
        self.entered.append(sig)
        return f"pid{len(self.entered)}"

    def exit_trade(self, pid, reason):
        self.exited.append((pid, reason))


def make(st, broker, tmp_path):
    s = st.Strategy.__new__(st.Strategy)
    s.broker = broker
    s.engine = st.ParityEngine(r=0.0)
    s.book = st.PositionBook(str(tmp_path / "pos.json"))
    s.tm = _TM()
    return s


def test_init_uses_given_broker_or_get_broker(st, monkeypatch):
    b = FakeBroker()
    s = st.Strategy(broker=b)
    assert s.broker is b and s.engine.r == st.RISK_FREE_RATE
    monkeypatch.setattr(st, "get_broker", lambda name: ("built", name))
    assert st.Strategy().broker == ("built", st.BROKER)


def test_scan_instrument_no_expiries(st, tmp_path):
    assert make(st, FakeBroker(), tmp_path)._scan_instrument("BANKNIFTY") == []


def test_scan_instrument_collects_signals(st, tmp_path):
    insts = [inst(typ="FUT", sym="BNFJAN"), inst(expiry="2026-01-29", typ="CE")]
    b = FakeBroker(insts, quotes=fut_quote(), chain=chain_rows(50000, 400, 200))
    sigs = make(st, b, tmp_path)._scan_instrument("BANKNIFTY")
    assert len(sigs) == 1 and sigs[0].futures_symbol == "BNFJAN" and sigs[0].expiry == "2026-01-29"
    assert b.chain_calls == [("BANKNIFTY", "2026-01-29", "NFO")]


def test_scan_instrument_skips_expiry_without_futures_price_or_chain(st, tmp_path):
    b = FakeBroker([inst(expiry="2026-01-29")], chain=chain_rows(50000, 400, 200))
    assert make(st, b, tmp_path)._scan_instrument("BANKNIFTY") == []
    assert b.chain_calls == []
    insts = [inst(typ="FUT", sym="BNFJAN"), inst(expiry="2026-01-29")]
    b = FakeBroker(insts, quotes=fut_quote(), chain_exc=RuntimeError("x"))
    assert make(st, b, tmp_path)._scan_instrument("BANKNIFTY") == []
    b = FakeBroker(insts, quotes=fut_quote(), chain=[])
    assert make(st, b, tmp_path)._scan_instrument("BANKNIFTY") == []


def _position(**kw):
    p = {"position_id": "p1", "instrument": "BANKNIFTY", "expiry": "2026-01-29", "strike": 50000.0,
         "direction": "SHORT_CALL_LONG_PUT", "lots": 1, "qty": 15, "call_symbol": "C", "put_symbol": "P",
         "futures_symbol": "BNFJAN", "entry_deviation": 200.0, "segment": "NFO"}
    p.update(kw)
    return p


def _mon_broker(call_mid, put_mid, fut=50000.0, with_fut=True):
    q = {"NFO:C": {"depth": {"buy": [{"price": call_mid - 1}], "sell": [{"price": call_mid + 1}]}},
         "NFO:P": {"depth": {"buy": [{"price": put_mid - 1}], "sell": [{"price": put_mid + 1}]}}}
    q.update(fut_quote(fut))
    return FakeBroker([FUT] if with_fut else [], quotes=q)


def test_monitor_no_positions_is_noop(st, tmp_path):
    s = make(st, _mon_broker(300, 200), tmp_path)
    s._monitor_positions()
    assert s.tm.exited == []


@pytest.mark.parametrize("call_mid,expect", [(240, "PROFIT_TARGET"), (700, "STOP_LOSS"), (300, None)])
def test_monitor_exits_on_profit_target_and_stop_loss_only(st, tmp_path, call_mid, expect):
    s = make(st, _mon_broker(call_mid, 200), tmp_path)
    s.book.add("p1", _position())
    s._monitor_positions()
    if expect is None:
        assert s.tm.exited == []
    else:
        assert len(s.tm.exited) == 1 and s.tm.exited[0][0] == "p1"
        assert s.tm.exited[0][1].startswith(expect)


def test_monitor_skips_when_quotes_or_futures_unavailable(st, tmp_path):
    s = make(st, FakeBroker([FUT], quote_exc=RuntimeError("x")), tmp_path)
    s.book.add("p1", _position())
    s._monitor_positions()
    s2 = make(st, _mon_broker(240, 200, with_fut=False), tmp_path)
    s2.book.add("p1", _position())
    s2._monitor_positions()
    assert s.tm.exited == [] and s2.tm.exited == []


def _run_once(st, s, monkeypatch):
    def sleep(sec):
        raise KeyboardInterrupt
    monkeypatch.setattr(st.time, "sleep", sleep)
    s.run()


def test_run_enters_best_signal_up_to_free_slots(st, tmp_path, monkeypatch):
    insts = [inst(typ="FUT", sym="BNFJAN"), inst(expiry="2026-01-29")]
    ch = chain_rows(50000, 400, 200) + chain_rows(50100, 700, 200)
    s = make(st, FakeBroker(insts, quotes=fut_quote(), chain=ch), tmp_path)
    monkeypatch.setattr(st, "MAX_OPEN_POSITIONS", 1)
    _run_once(st, s, monkeypatch)
    assert [x.strike for x in s.tm.entered] == [50100.0]      # one slot -> highest net deviation


def test_run_skips_duplicate_strike(st, tmp_path, monkeypatch):
    insts = [inst(typ="FUT", sym="BNFJAN"), inst(expiry="2026-01-29")]
    s = make(st, FakeBroker(insts, quotes=fut_quote(), chain=chain_rows(50000, 400, 200)), tmp_path)
    s.book.add("x", _position(strike=50000.0))
    _run_once(st, s, monkeypatch)
    assert s.tm.entered == []


def test_run_full_book_skips_scan(st, tmp_path, monkeypatch):
    insts = [inst(typ="FUT", sym="BNFJAN"), inst(expiry="2026-01-29")]
    s = make(st, FakeBroker(insts, quotes=fut_quote(), chain=chain_rows(50000, 400, 200)), tmp_path)
    monkeypatch.setattr(st, "MAX_OPEN_POSITIONS", 1)
    s.book.add("x", _position(strike=1.0))
    _run_once(st, s, monkeypatch)
    assert s.tm.entered == [] and s.broker.chain_calls == []


def test_run_survives_unhandled_error(st, tmp_path, monkeypatch):
    s = make(st, FakeBroker(), tmp_path)
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RuntimeError("bad")
    s._monitor_positions = boom
    sleeps = []

    def sleep(sec):
        sleeps.append(sec)
        if len(sleeps) >= 1:
            raise KeyboardInterrupt
    monkeypatch.setattr(st.time, "sleep", sleep)
    with pytest.raises(KeyboardInterrupt):      # raised from the error handler's own sleep(5)
        s.run()
    assert calls["n"] == 1 and sleeps == [5]


def test_run_sleeps_remaining_scan_interval(st, tmp_path, monkeypatch):
    s = make(st, FakeBroker(), tmp_path)
    calls = {"n": 0}

    def fake_time():
        calls["n"] += 1
        return 100.0 if calls["n"] == 1 else 110.0   # logging also reads the clock
    monkeypatch.setattr(st.time, "time", fake_time)
    seen = []

    def sleep(sec):
        seen.append(sec)
        raise KeyboardInterrupt
    monkeypatch.setattr(st.time, "sleep", sleep)
    s.run()
    assert seen == [st.SCAN_INTERVAL_SECONDS - 10.0]
