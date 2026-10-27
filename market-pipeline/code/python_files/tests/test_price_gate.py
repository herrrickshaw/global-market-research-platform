"""``price_gate`` — the one gate between a built brief and the send.

Steps 1 and 2 (workbook age, warehouse signature) and 3b (US live spot-check)
are tested here with every I/O seam stubbed. Step 3a, the witness jury, has
its own suite in test_validate_brief.py; here it is only stubbed to prove the
gate wires its verdict and reason through.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

import price_gate as pg


class TestQuorum:
    @pytest.mark.parametrize("n,expected", [
        (1, 2), (2, 2), (3, 2), (4, 3), (5, 3), (6, 4), (7, 4), (8, 5), (12, 7),
    ])
    def test_strict_majority_with_floor_of_two(self, n, expected):
        assert pg._quorum(n) == expected

    def test_2026_08_12_half_of_eight_does_not_fail(self):
        assert pg._quorum(8) > 4


SCAN = {"AAPL": 230.0, "MSFT": 420.0, "NVDA": 120.0, "AMZN": 185.0,
        "GOOGL": 165.0, "META": 500.0, "TSLA": 250.0, "AVGO": 170.0}
IN_SCAN = {"HDFCBANK": 688.05, "ICICIBANK": 1403.0, "RELIANCE": 1201.8, "INFY": 1166.0,
           "BHARTIARTL": 1917.5, "SBIN": 850.0, "TCS": 3100.0, "ITC": 420.0}


@pytest.fixture
def seams(monkeypatch, scan_workbook, tmp_path):
    """Point the gate at a temp tree and stub Postgres, Yahoo and the clock."""
    monkeypatch.setattr(pg, "HERE", tmp_path)
    monkeypatch.setattr(pg, "warehouse_prev_close",
                        lambda m: pd.DataFrame(columns=["symbol", "ltp"]))
    monkeypatch.setattr(pg.ms, "is_open", lambda m, at=None: False)
    calls = {"fresh": 0}

    def fresh(quotes: dict[str, float]):
        def _f(tickers):
            calls["fresh"] += 1
            return {t: quotes[t.removesuffix(".NS")] for t in tickers
                    if t.removesuffix(".NS") in quotes}
        monkeypatch.setattr(pg, "fresh_quotes", _f)

    def make(market: str, prices: dict[str, float], stamp=None):
        d, p = {"US": ("us_full_scan", "us_full_scan"),
                "IN": ("indian_full_scan", "indian_full_scan")}[market]
        rows = [{"Symbol": s, "LTP": px, "Turnover_USD": 1_000_000 - i}
                for i, (s, px) in enumerate(prices.items())]
        return scan_workbook(d, p, rows, stamp)

    return make, fresh, calls


class TestUSStaleness:
    def test_matching_live_quotes_pass(self, seams):
        make, fresh, _ = seams
        make("US", SCAN)
        fresh(SCAN)
        assert pg.staleness("US") == (True, "")

    def test_2026_08_01_yesterdays_workbook_fails_before_any_price_is_compared(self, seams):
        make, fresh, calls = seams
        make("US", SCAN, stamp=dt.date.today() - dt.timedelta(days=1))
        fresh(SCAN)
        ok, why = pg.staleness("US")
        assert not ok and why.startswith("US: stale workbook")
        assert calls["fresh"] == 0, "a stale workbook must not be excused by live prices"

    def test_closed_market_one_breach_fails(self, seams):
        make, fresh, _ = seams
        make("US", SCAN)
        fresh(dict(SCAN, NVDA=130.0))
        ok, why = pg.staleness("US")
        assert not ok and "1/8 stale vs live (worst NVDA" in why

    def test_2026_07_28_in_session_one_breach_is_drift_not_failure(self, seams, monkeypatch):
        make, fresh, _ = seams
        make("US", SCAN)
        monkeypatch.setattr(pg.ms, "is_open", lambda m, at=None: True)
        fresh(dict(SCAN, NVDA=130.0))                          # 8% move, one name
        assert pg.staleness("US") == (True, "")

    def test_in_session_majority_breach_still_fails(self, seams, monkeypatch):
        make, fresh, _ = seams
        make("US", SCAN)
        monkeypatch.setattr(pg.ms, "is_open", lambda m, at=None: True)
        fresh({s: p * 1.10 for s, p in SCAN.items()})         # the whole sample moved
        ok, why = pg.staleness("US")
        assert not ok and "8/8 stale" in why

    def test_warehouse_signature_majority_fails_regardless_of_session(self, seams, monkeypatch):
        make, fresh, _ = seams
        make("US", SCAN)
        wh = pd.DataFrame({"symbol": list(SCAN)[:5], "ltp": list(SCAN.values())[:5]})
        monkeypatch.setattr(pg, "warehouse_prev_close", lambda m: wh)
        monkeypatch.setattr(pg.ms, "is_open", lambda m, at=None: True)
        fresh(SCAN)
        ok, why = pg.staleness("US")
        assert not ok and "re-served yesterday's closes (5/8" in why

    def test_yfinance_outage_falls_back_to_signature_only(self, seams):
        make, fresh, _ = seams
        make("US", SCAN)
        fresh({})
        assert pg.staleness("US") == (True, "")

    def test_no_workbook_at_all_is_a_skip(self, seams):
        assert pg.staleness("US") == (True, "")


class TestINStaleness:
    def test_india_never_spot_checks_yahoo_the_jury_does_that(self, seams):
        # Yahoo is one of the jury's witnesses; asking it again, undated, is the
        # same-source double check this module exists to remove.
        make, fresh, calls = seams
        make("IN", IN_SCAN)
        fresh(IN_SCAN)
        assert pg.staleness("IN") == (True, "")
        assert calls["fresh"] == 0

    def test_india_still_fails_on_signature_and_age(self, seams, monkeypatch):
        make, fresh, _ = seams
        make("IN", IN_SCAN)
        wh = pd.DataFrame({"symbol": list(IN_SCAN)[:6], "ltp": list(IN_SCAN.values())[:6]})
        monkeypatch.setattr(pg, "warehouse_prev_close", lambda m: wh)
        ok, why = pg.staleness("IN")
        assert not ok and why.startswith("IN: re-served")


class TestRun:
    @pytest.fixture
    def jury(self, monkeypatch):
        calls = []

        def install(ok: bool, reason: str = ""):
            def validate(sample, tol):
                calls.append((sample, tol))
                return {"ok": ok, "reason": reason, "scan": "x.xlsx", "asof": "2026-10-27",
                        "verified": 6, "checks": [], "mute": {}}
            monkeypatch.setattr(pg.validate_brief, "validate", validate)
        return install, calls

    def test_all_clear_exits_0_and_clears_the_reason_file(self, seams, jury, tmp_path):
        make, fresh, _ = seams
        make("IN", IN_SCAN)
        make("US", SCAN)
        fresh(SCAN)
        install, calls = jury
        install(True)
        rf = tmp_path / "state" / "price_gate_reason.txt"
        assert pg.run(["IN", "US"], sample=6, reason_file=rf) == 0
        assert rf.read_text() == ""
        assert calls == [(6, pg.validate_brief.PRICE_TOL_PCT)]

    def test_jury_mismatch_names_the_market_and_reason(self, seams, jury, tmp_path):
        make, fresh, _ = seams
        make("IN", IN_SCAN)
        make("US", SCAN)
        fresh(SCAN)
        install, _ = jury
        install(False, "1 price mismatch(es) beyond 2.0%: BSE (ours 3359.0, yfinance 3230.8 3.97%)")
        rf = tmp_path / "state" / "price_gate_reason.txt"
        assert pg.run(["IN", "US"], reason_file=rf) == 1
        assert rf.read_text().startswith("IN: 1 price mismatch(es) beyond 2.0%: BSE")

    def test_stale_india_workbook_skips_the_jury_to_save_quota(self, seams, jury, tmp_path):
        make, fresh, _ = seams
        make("IN", IN_SCAN, stamp=dt.date.today() - dt.timedelta(days=1))
        install, calls = jury
        install(True)
        rf = tmp_path / "state" / "price_gate_reason.txt"
        assert pg.run(["IN"], reason_file=rf) == 1
        assert calls == [], "a stale workbook must not spend Alpha Vantage quota"
        assert "IN: stale workbook" in rf.read_text()

    def test_us_failure_and_india_pass_report_only_the_us(self, seams, jury, tmp_path):
        make, fresh, _ = seams
        make("IN", IN_SCAN)
        make("US", SCAN)
        fresh(dict(SCAN, NVDA=130.0))
        install, _ = jury
        install(True)
        rf = tmp_path / "state" / "price_gate_reason.txt"
        assert pg.run(["IN", "US"], reason_file=rf) == 1
        assert rf.read_text().startswith("US: 1/8 stale vs live")
