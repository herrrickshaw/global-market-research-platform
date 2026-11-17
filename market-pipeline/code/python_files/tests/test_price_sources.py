"""``price_sources`` witnesses, with HTTP stubbed.

The contract every source must honour: return ``{"price","date"}`` for the last
COMPLETED session on/before ``asof``, or ``{"error"}``; never a live tick; never
leak the API key into an error string (it is persisted in a public repo).
"""
from __future__ import annotations

import datetime as dt

import pytest

import price_sources as ps

# A stand-in credential that is long enough to trip the redaction regex but has
# zero entropy, so gitleaks (pre-commit) does not mistake it for a real key.
KEY = "A" * 20


class _Resp:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(ps, "_key", lambda name: KEY)


class TestAlphaVantage:
    def test_picks_newest_bar_on_or_before_asof(self, monkeypatch):
        body = {"Time Series (Daily)": {
            "2026-10-27": {"4. close": "700.0"},
            "2026-10-26": {"4. close": "688.20"},
            "2026-10-23": {"4. close": "692.80"}}}
        monkeypatch.setattr(ps, "_get", lambda url, **kw: _Resp(body))
        r = ps._alphavantage("HDFCBANK", dt.date(2026, 10, 26))
        assert r == {"price": 688.2, "date": dt.date(2026, 10, 26)}

    def test_queries_bse_not_nse(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(ps, "_get", lambda url, **kw: seen.setdefault("url", url) and _Resp({}))
        ps._alphavantage("INFY", dt.date(2026, 10, 26))
        assert "symbol=INFY.BSE" in seen["url"]

    def test_quota_note_is_an_error_not_a_price(self, monkeypatch):
        body = {"Note": "Thank you for using Alpha Vantage! Our standard API rate limit is 25"}
        monkeypatch.setattr(ps, "_get", lambda url, **kw: _Resp(body))
        r = ps._alphavantage("INFY", dt.date(2026, 10, 26))
        assert "error" in r and r["error"].startswith("av:")

    def test_2026_08_18_api_key_is_redacted_from_quota_message(self, monkeypatch):
        body = {"Information": f"We have detected your API key as {KEY} and our standard"}
        monkeypatch.setattr(ps, "_get", lambda url, **kw: _Resp(body))
        r = ps._alphavantage("INFY", dt.date(2026, 10, 26))
        assert KEY not in r["error"]
        assert "<redacted>" in r["error"]

    def test_non_200_is_an_error(self, monkeypatch):
        monkeypatch.setattr(ps, "_get", lambda url, **kw: _Resp({}, status=503))
        assert ps._alphavantage("INFY", dt.date(2026, 10, 26)) == {"error": "http 503"}

    def test_missing_key_is_inert(self, monkeypatch):
        monkeypatch.setattr(ps, "_key", lambda name: None)
        assert "error" in ps._alphavantage("INFY", dt.date(2026, 10, 26))


class TestTwelveData:
    def test_picks_newest_bar_on_or_before_asof(self, monkeypatch):
        body = {"values": [{"datetime": "2026-10-27", "close": "1170"},
                           {"datetime": "2026-10-26", "close": "1166"},
                           {"datetime": "2026-10-23", "close": "1153.8"}]}
        monkeypatch.setattr(ps, "_get", lambda url, **kw: _Resp(body))
        assert ps._twelvedata("INFY", dt.date(2026, 10, 26)) == \
            {"price": 1166.0, "date": dt.date(2026, 10, 26)}

    def test_status_error_body_is_an_error_and_redacted(self, monkeypatch):
        body = {"status": "error", "message": f"key {KEY} exceeded quota"}
        monkeypatch.setattr(ps, "_get", lambda url, **kw: _Resp(body))
        r = ps._twelvedata("BSE", dt.date(2026, 10, 26))
        assert "error" in r and KEY not in r["error"]


class TestYFinance:
    """Drop the in-progress session: a row stamped today is a live tick."""

    @pytest.fixture
    def history(self, monkeypatch):
        import pandas as pd

        def _install(rows: dict[dt.date, float]):
            idx = pd.DatetimeIndex([pd.Timestamp(d) for d in rows])
            df = pd.DataFrame({"Close": list(rows.values())}, index=idx)

            class _T:
                def __init__(self, sym): ...
                def history(self, **kw): return df

            import types
            fake = types.SimpleNamespace(Ticker=_T)
            monkeypatch.setitem(__import__("sys").modules, "yfinance", fake)

        return _install

    def test_2026_08_18_todays_row_is_dropped(self, history):
        today = dt.date.today()
        history({today - dt.timedelta(days=1): 688.05, today: 695.0})
        r = ps._yfinance("HDFCBANK", today)
        assert r["date"] == today - dt.timedelta(days=1) and r["price"] == 688.05

    def test_2026_08_12_nan_close_is_no_answer_not_nan(self, history):
        today = dt.date.today()
        history({today - dt.timedelta(days=2): 688.05, today - dt.timedelta(days=1): float("nan")})
        r = ps._yfinance("HDFCBANK", today)
        assert r["price"] == 688.05

    def test_only_todays_row_is_no_completed_session(self, history):
        today = dt.date.today()
        history({today: 695.0})
        assert "error" in ps._yfinance("HDFCBANK", today)


class TestFetchAll:
    def test_every_registered_source_is_asked(self, monkeypatch):
        calls = []
        monkeypatch.setattr(ps, "SOURCES", {
            "a": lambda s, d: calls.append("a") or {"price": 1.0, "date": d},
            "b": lambda s, d: calls.append("b") or {"error": "x"}})
        out = ps.fetch_all("X", dt.date(2026, 10, 26), polite=0)
        assert calls == ["a", "b"] and set(out) == {"a", "b"}
