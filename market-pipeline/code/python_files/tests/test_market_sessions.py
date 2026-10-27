"""``market_sessions`` — the session clock every freshness verdict hangs on.

A wrong answer here is graded as staleness (or worse, as freshness) everywhere
downstream, so the publish-lag boundaries are pinned to the minute.
"""
from __future__ import annotations

import datetime as dt

import pytest

import market_sessions as ms

UTC = dt.timezone.utc
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
ET_STD = dt.timezone(dt.timedelta(hours=-5))      # late Oct 2026 is still EDT (-4)
EDT = dt.timezone(dt.timedelta(hours=-4))


@pytest.fixture(autouse=True)
def no_live_holiday_fetch(monkeypatch):
    """Never reach market_calendar's live NSE list from a unit test."""
    monkeypatch.setattr(ms, "_nse_holidays", lambda: {"2026-10-20", "2026-11-05"})
    m = ms.MARKETS["IN"]
    monkeypatch.setitem(ms.MARKETS, "IN", ms.Market(
        m.code, m.label, m.venue, m.tz, m.close_local, m.publish_lag, m.source,
        lambda: {"2026-10-20", "2026-11-05"}, m.cal))


class TestIndia:
    def test_03_00_ist_tuesday_expects_mondays_close(self):
        at = dt.datetime(2026, 10, 27, 3, 0, tzinfo=IST)
        assert ms.expected_session("IN", at) == dt.date(2026, 10, 26)

    def test_before_bhavcopy_lag_still_expects_previous_session(self):
        # Close 15:30 + 2h30 lag = 18:00 IST. At 17:59 the 27th is not yet servable.
        at = dt.datetime(2026, 10, 27, 17, 59, tzinfo=IST)
        assert ms.expected_session("IN", at) == dt.date(2026, 10, 26)

    def test_at_publish_instant_expects_todays_session(self):
        at = dt.datetime(2026, 10, 27, 18, 0, tzinfo=IST)
        assert ms.expected_session("IN", at) == dt.date(2026, 10, 27)

    def test_monday_morning_expects_friday(self):
        at = dt.datetime(2026, 10, 26, 6, 30, tzinfo=IST)
        assert ms.expected_session("IN", at) == dt.date(2026, 10, 23)

    def test_live_nse_holiday_is_skipped(self):
        # 2026-10-20 injected as a holiday above: a Wednesday-morning run expects Monday.
        at = dt.datetime(2026, 10, 21, 6, 30, tzinfo=IST)
        assert ms.expected_session("IN", at) == dt.date(2026, 10, 19)

    def test_is_open_respects_bell_times(self):
        assert ms.is_open("IN", dt.datetime(2026, 10, 27, 9, 15, tzinfo=IST))
        assert ms.is_open("IN", dt.datetime(2026, 10, 27, 15, 30, tzinfo=IST))
        assert not ms.is_open("IN", dt.datetime(2026, 10, 27, 9, 14, tzinfo=IST))
        assert not ms.is_open("IN", dt.datetime(2026, 10, 27, 15, 31, tzinfo=IST))
        assert not ms.is_open("IN", dt.datetime(2026, 10, 25, 11, 0, tzinfo=IST))   # Sunday


class TestUS:
    def test_us_bar_not_expected_until_90_minutes_after_the_bell(self):
        # 16:00 ET close + 1h30 = 17:30 ET.
        assert ms.expected_session("US", dt.datetime(2026, 10, 27, 17, 29, tzinfo=EDT)) \
            == dt.date(2026, 10, 26)
        assert ms.expected_session("US", dt.datetime(2026, 10, 27, 17, 30, tzinfo=EDT)) \
            == dt.date(2026, 10, 27)

    def test_2026_08_19_us_scan_at_04_59_ist_expects_the_prior_us_session(self):
        # 04:59 IST Wed = 19:29 ET Tue: the Tue 18 Aug bar is published, so
        # a scan holding 17 Aug closes is one session stale — the incident.
        at = dt.datetime(2026, 8, 19, 4, 59, tzinfo=IST)
        assert ms.expected_session("US", at) == dt.date(2026, 8, 18)

    def test_independence_day_observed_is_not_a_session(self):
        xc = pytest.importorskip("exchange_calendars")
        assert dt.date(2026, 7, 3) not in ms._sessions_for("XNYS", 2026)


class TestKoreaAndJapan:
    def test_kr_constitution_day_2026_is_closed_by_local_override(self):
        pytest.importorskip("exchange_calendars")
        assert dt.date(2026, 7, 17) not in ms._sessions_for("XKRX", 2026)

    def test_jp_mountain_day_is_a_holiday(self):
        pytest.importorskip("exchange_calendars")
        assert dt.date(2026, 8, 11) not in ms._sessions_for("XTKS", 2026)


class TestHelpers:
    def test_previous_session_skips_weekend(self):
        assert ms.previous_session("US", dt.date(2026, 10, 26)) == dt.date(2026, 10, 23)

    def test_sessions_between_counts_trading_days_only(self):
        got = ms.sessions_between("US", dt.date(2026, 10, 22), dt.date(2026, 10, 27))
        assert got == [dt.date(2026, 10, 23), dt.date(2026, 10, 26), dt.date(2026, 10, 27)]

    def test_vintage_names_the_session_not_the_fetch_time(self):
        s = ms.vintage("IN", dt.date(2026, 10, 26),
                       at=dt.datetime(2026, 10, 27, 6, 30, tzinfo=IST))
        assert s.startswith("26 Oct 2026 close (NSE/BSE, 15:30")
        assert "behind" not in s

    def test_vintage_flags_sessions_behind(self):
        s = ms.vintage("US", dt.date(2026, 10, 23),
                       at=dt.datetime(2026, 10, 27, 6, 30, tzinfo=IST))
        assert "1 session behind" in s
