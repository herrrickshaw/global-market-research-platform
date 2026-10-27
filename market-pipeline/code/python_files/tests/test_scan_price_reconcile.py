"""Send gate 1 of 2: ``scan_price_reconcile`` — is the scan today's, and does it
agree with live quotes?

The quorum arithmetic and the stale-workbook check are where every historical
false suppression lived (2026-07-28 NVDA, 2026-08-01 Saturday, 2026-08-12 n=8).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import scan_price_reconcile as spr


class TestQuorum:
    @pytest.mark.parametrize("n,expected", [
        (1, 2), (2, 2), (3, 2), (4, 3), (5, 3), (6, 4), (7, 4), (8, 5), (12, 7),
    ])
    def test_strict_majority_with_floor_of_two(self, n, expected):
        assert spr._quorum(n) == expected

    def test_2026_08_12_half_of_eight_does_not_fail(self):
        # 4/8 breaching used to suppress; a majority of 8 is 5.
        assert 4 < spr._quorum(8)


class TestScanAge:
    def test_today_is_zero(self):
        assert spr.scan_age_days(f"us_full_scan_{dt.date.today():%Y%m%d}_0314.xlsx") == 0

    def test_yesterday_is_one(self):
        y = dt.date.today() - dt.timedelta(days=1)
        assert spr.scan_age_days(f"indian_full_scan_{y:%Y%m%d}_0300.xlsx") == 1

    def test_unparseable_is_none(self):
        assert spr.scan_age_days("notes.xlsx") is None
        assert spr.scan_age_days("x_99999999_0000.xlsx") is None


@pytest.fixture
def market(monkeypatch, scan_workbook, tmp_path):
    """Point the IN market at a temp workbook and stub every I/O seam."""
    monkeypatch.setattr(spr, "HERE", tmp_path)
    monkeypatch.setattr(spr, "warehouse_prev_close",
                        lambda m: pd.DataFrame(columns=["symbol", "ltp"]))
    monkeypatch.setattr(spr, "market_open_now", lambda m: False)

    def _make(prices: dict[str, float], stamp=None):
        rows = [{"Symbol": s, "LTP": p, "Turnover_USD": 1_000_000 - i}
                for i, (s, p) in enumerate(prices.items())]
        return scan_workbook("indian_full_scan", "indian_full_scan", rows, stamp)

    return _make


SCAN = {"HDFCBANK": 688.05, "ICICIBANK": 1403.0, "RELIANCE": 1201.8, "INFY": 1166.0,
        "BHARTIARTL": 1917.5, "SBIN": 850.0, "TCS": 3100.0, "ITC": 420.0}


def _fresh(monkeypatch, quotes: dict[str, float]):
    monkeypatch.setattr(spr, "fresh_quotes", lambda tickers: {
        t: quotes[t.removesuffix(".NS")] for t in tickers if t.removesuffix(".NS") in quotes})


class TestReconcile:
    def test_matching_live_quotes_pass(self, market, monkeypatch):
        market(SCAN)
        _fresh(monkeypatch, SCAN)
        assert spr.reconcile("IN", sample=8, tolerance=2.0) is True

    def test_2026_08_01_yesterdays_workbook_fails_before_any_price_is_compared(
            self, market, monkeypatch):
        market(SCAN, stamp=dt.date.today() - dt.timedelta(days=1))
        called = []
        monkeypatch.setattr(spr, "fresh_quotes", lambda t: called.append(t) or {})
        assert spr.reconcile("IN", sample=8, tolerance=2.0) is False
        assert called == [], "a stale workbook must not be excused by live prices"

    def test_closed_market_one_breach_fails(self, market, monkeypatch):
        market(SCAN)
        live = dict(SCAN, RELIANCE=1300.0)
        _fresh(monkeypatch, live)
        assert spr.reconcile("IN", sample=8, tolerance=2.0) is False

    def test_2026_07_28_in_session_one_breach_is_drift_not_failure(self, market, monkeypatch):
        market(SCAN)
        monkeypatch.setattr(spr, "market_open_now", lambda m: True)
        _fresh(monkeypatch, dict(SCAN, RELIANCE=1300.0))     # 8% move, one name
        assert spr.reconcile("IN", sample=8, tolerance=2.0) is True

    def test_in_session_majority_breach_still_fails(self, market, monkeypatch):
        market(SCAN)
        monkeypatch.setattr(spr, "market_open_now", lambda m: True)
        live = {s: p * 1.10 for s, p in SCAN.items()}          # the whole sample moved
        _fresh(monkeypatch, live)
        assert spr.reconcile("IN", sample=8, tolerance=2.0) is False

    def test_warehouse_signature_majority_fails_regardless_of_session(self, market, monkeypatch):
        # Scan LTP == yesterday's warehouse close to the cent on 5/8 names: a
        # re-served cache, and no live market reproduces exact equality.
        market(SCAN)
        wh = pd.DataFrame({"symbol": list(SCAN)[:5], "ltp": list(SCAN.values())[:5]})
        monkeypatch.setattr(spr, "warehouse_prev_close", lambda m: wh)
        monkeypatch.setattr(spr, "market_open_now", lambda m: True)
        _fresh(monkeypatch, SCAN)
        assert spr.reconcile("IN", sample=8, tolerance=2.0) is False

    def test_yfinance_outage_falls_back_to_signature_only(self, market, monkeypatch):
        market(SCAN)
        _fresh(monkeypatch, {})
        assert spr.reconcile("IN", sample=8, tolerance=2.0) is True

    def test_no_workbook_at_all_is_a_skip(self, monkeypatch, tmp_path):
        monkeypatch.setattr(spr, "HERE", tmp_path)
        assert spr.reconcile("IN", sample=8, tolerance=2.0) is True
