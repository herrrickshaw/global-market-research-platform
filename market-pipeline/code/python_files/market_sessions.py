#!/usr/bin/env python3
"""
market_sessions.py — the session clock. ONE answer to "what date should this be?"

WHY THIS MODULE EXISTS
──────────────────────
Every staleness incident in this pipeline has the same shape: a dataset was
judged fresh by WHEN WE TOUCHED IT rather than WHICH SESSION IT CONTAINS.

  * 2026-08-19. The US scan ran at 04:59 IST and was recorded as that morning's
    scan. 77.1% of its LTPs were an exact match to the 17 Aug close — the 18 Aug
    session never landed. `market_ingest.py --status` still reported
    `us … 2026-08-19, 0d, ok [fresh]`, because it counts rows present under a
    date stamp, not the session those rows describe.
  * The brief's own caveat said "scanned 19 Aug 04:59" over 17 Aug prices. The
    reader is told when we looked, never what they are looking at.
  * 2026-07-15. A GOLDEN_CROSS pick shipped quoting a seven-week-old price while
    every internal check passed.

A wall-clock timestamp cannot detect any of these, because in all three the
timestamp was correct. The only thing that distinguishes good data from stale
data is the SESSION DATE, and the only way to know whether that session date is
acceptable is to compare it against the session the exchange has actually
finished trading and published by now.

That comparison is what this module provides, and it deliberately lives apart
from any dataset, reader or scan: the clock must not be derivable from the data
it judges. `data_catalog.py` reads session dates OUT of files; this module says
what they SHOULD be; `data_state.py` compares the two.

THE TWO TIMES THAT MATTER
─────────────────────────
`close` alone is not enough. An exchange closing at 16:00 does not mean its EOD
data exists at 16:00 — NSE publishes the bhavcopy well after the bell, and
yfinance's daily bar settles later still. So each market carries:

    close_local   when trading stops, in the exchange's own timezone
    publish_lag   how long AFTER the close our SOURCE actually serves that
                  session's EOD bar

`expected_session(mkt, at)` returns the newest session that has both closed and
been published as of `at`. Before the lag elapses the answer is the PREVIOUS
session — which is correct, not conservative: asking for a bar the source has
not published yet is how you get a partial bar, and a partial bar quoted as a
close is the 2026-08-19 failure in a different costume.

The lags below are deliberately generous. A lag that is too short makes the
pipeline chase data that does not exist yet and then reports the resulting hole
as staleness; a lag that is too long only delays a refresh by minutes, because
`ensure_fresh.py` re-asks on every mailer request rather than once a night.

EUROPE IS A COMPOSITE. `europe_broad_list` spans 17 exchanges closing between
16:30 London and 17:30 CET. The expected session uses the LATEST-closing venue,
so "Europe is current" means every constituent venue has closed and published.

HOLIDAYS. NSE's real holiday list comes from `market_calendar.get_holidays()`.
The other markets fall back to weekends-only, which over-states the expected
session on their local holidays. That is handled at the verdict layer, not here:
`data_state.py` grades a one-session gap as CHECK rather than STALE, so an
unknown holiday is visible without being an alarm. Widening this to real
per-exchange calendars is the clean follow-up; guessing here would silently
suppress genuine staleness, which is the failure mode this file exists to end.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass, field
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc


# ── market definitions ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Market:
    code: str
    label: str
    venue: str            # the exchange(s) the close time refers to
    tz: str               # IANA zone of `venue`
    close_local: dt.time  # when trading stops there
    publish_lag: dt.timedelta   # close -> our source serves the EOD bar
    source: str           # the credible attribution shown to the reader
    holidays: Callable[[], set[str]] | None = field(default=None, compare=False)

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)


def _nse_holidays() -> set[str]:
    """Real NSE trading holidays, via the cached live list in market_calendar."""
    try:
        import market_calendar

        return set(market_calendar.get_holidays())
    except Exception:
        return set()


MARKETS: dict[str, Market] = {
    "IN": Market(
        "IN", "India", "NSE/BSE", "Asia/Kolkata", dt.time(15, 30),
        # Bhavcopy lands ~18:00 IST; 2.5h clears the tail of late-file days.
        dt.timedelta(hours=2, minutes=30),
        "NSE/BSE official bhavcopy", _nse_holidays,
    ),
    "US": Market(
        "US", "United States", "NYSE/NASDAQ", "America/New_York", dt.time(16, 0),
        # yfinance's daily bar settles within ~1h of the bell; 1.5h is margin.
        dt.timedelta(hours=1, minutes=30),
        "NASDAQ/NYSE consolidated close (yfinance)",
    ),
    "JP": Market(
        "JP", "Japan", "TSE", "Asia/Tokyo", dt.time(15, 30),
        dt.timedelta(hours=2), "Tokyo Stock Exchange close (yfinance)",
    ),
    "KR": Market(
        "KR", "Korea", "KRX", "Asia/Seoul", dt.time(15, 30),
        dt.timedelta(hours=2), "KRX KOSPI/KOSDAQ close (yfinance)",
    ),
    "EU": Market(
        # Latest-closing venue in the 17-exchange set (Xetra/Euronext 17:30 CET).
        "EU", "Europe", "Xetra/Euronext (latest of 17)", "Europe/Berlin",
        dt.time(17, 30), dt.timedelta(hours=2),
        "European exchange closes (yfinance)",
    ),
    "CN": Market(
        "CN", "China", "SSE/SZSE", "Asia/Shanghai", dt.time(15, 0),
        dt.timedelta(hours=2), "SSE/SZSE close (akshare)",
    ),
}


# ── the clock ─────────────────────────────────────────────────────────────────
def _is_session(m: Market, d: dt.date, hols: set[str]) -> bool:
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in hols


def close_utc(mkt: str, d: dt.date) -> dt.datetime:
    """UTC instant at which `d`'s session closes on `mkt`'s venue."""
    m = MARKETS[mkt]
    return dt.datetime.combine(d, m.close_local, tzinfo=m.zone).astimezone(UTC)


def publish_utc(mkt: str, d: dt.date) -> dt.datetime:
    """UTC instant from which `d`'s EOD bar is expected to be SERVABLE."""
    return close_utc(mkt, d) + MARKETS[mkt].publish_lag


def expected_session(mkt: str, at: dt.datetime | None = None) -> dt.date:
    """Newest session that has both closed AND been published as of `at`.

    Walks back from `at`'s local date until it finds a trading day whose publish
    instant has passed. The walk is bounded — 14 days covers the longest holiday
    run on any of these venues — and returns the last candidate rather than
    raising, so a pathological calendar degrades to an obviously-old date the
    verdict layer will flag, not to an exception inside the mailer.
    """
    m = MARKETS[mkt]
    at = (at or dt.datetime.now(UTC)).astimezone(UTC)
    hols = m.holidays() if m.holidays else set()
    d = at.astimezone(m.zone).date()
    for _ in range(14):
        if _is_session(m, d, hols) and publish_utc(mkt, d) <= at:
            return d
        d -= dt.timedelta(days=1)
    return d


def previous_session(mkt: str, d: dt.date) -> dt.date:
    """The trading day immediately before `d` on `mkt`."""
    m = MARKETS[mkt]
    hols = m.holidays() if m.holidays else set()
    c = d - dt.timedelta(days=1)
    for _ in range(14):
        if _is_session(m, c, hols):
            return c
        c -= dt.timedelta(days=1)
    return c


def sessions_between(mkt: str, lo: dt.date, hi: dt.date) -> list[dt.date]:
    """Trading days in (lo, hi] — i.e. how many sessions a dataset is behind."""
    m = MARKETS[mkt]
    hols = m.holidays() if m.holidays else set()
    out, d = [], hi
    while d > lo and len(out) < 400:
        if _is_session(m, d, hols):
            out.append(d)
        d -= dt.timedelta(days=1)
    return sorted(out)


def is_open(mkt: str, at: dt.datetime | None = None) -> bool:
    """Is `mkt` trading right now? Used to loosen drift tolerances, never to
    excuse a stale session date."""
    m = MARKETS[mkt]
    at = (at or dt.datetime.now(UTC)).astimezone(m.zone)
    hols = m.holidays() if m.holidays else set()
    if not _is_session(m, at.date(), hols):
        return False
    # Every venue here opens in the morning and closes the same local day.
    open_local = {"IN": dt.time(9, 15), "US": dt.time(9, 30), "JP": dt.time(9, 0),
                  "KR": dt.time(9, 0), "EU": dt.time(9, 0), "CN": dt.time(9, 30)}[m.code]
    return open_local <= at.time() <= m.close_local


def vintage(mkt: str, session: dt.date, at: dt.datetime | None = None) -> str:
    """One human sentence naming what a price IS — for the brief's caveat.

    Deliberately states the session and the venue, never the fetch time. A
    reader who is told "scanned 19 Aug 04:59" cannot tell 18 Aug prices from
    17 Aug ones; a reader told "17 Aug close (NYSE)" can.
    """
    m = MARKETS[mkt]
    c = close_utc(mkt, session).astimezone(m.zone)
    age = ""
    if at is not None:
        n = len(sessions_between(mkt, session, expected_session(mkt, at)))
        if n == 1:
            age = " · 1 session behind"
        elif n > 1:
            age = f" · {n} sessions behind"
    return (f"{session:%d %b %Y} close ({m.venue}, {c:%H:%M %Z})"
            f" — {m.source}{age}")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="session clock: what date should the data be?")
    ap.add_argument("--at", help="ISO instant to evaluate at (default: now, UTC)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    at = dt.datetime.fromisoformat(a.at) if a.at else dt.datetime.now(UTC)
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)

    rows = []
    for code, m in MARKETS.items():
        s = expected_session(code, at)
        rows.append({
            "market": code, "venue": m.venue, "expected_session": s.isoformat(),
            "closed_utc": close_utc(code, s).isoformat(),
            "published_utc": publish_utc(code, s).isoformat(),
            "open_now": is_open(code, at), "source": m.source,
            "vintage": vintage(code, s, at),
        })

    if a.json:
        print(json.dumps({"at": at.isoformat(), "markets": rows}, indent=2))
        return 0

    print(f"=== EXPECTED SESSION as of {at.astimezone():%Y-%m-%d %H:%M %Z} ===")
    print(f"  {'MKT':4} {'VENUE':28} {'SESSION':11} {'PUBLISHED (local)':22} OPEN")
    for r in rows:
        m = MARKETS[r["market"]]
        pub = dt.datetime.fromisoformat(r["published_utc"]).astimezone()
        pub_s = f"{pub:%Y-%m-%d %H:%M %Z}"
        print(f"  {r['market']:4} {m.venue[:28]:28} {r['expected_session']:11} "
              f"{pub_s:22} {'yes' if r['open_now'] else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
