#!/usr/bin/env python3
"""
test_pipeline_invariants.py — the offline invariants of the freshness stack.

Every check here corresponds to a defect that actually shipped. They are written
as assertions rather than prose so a regression fails loudly instead of being
rediscovered by reading a brief that quotes a stale price.

DELIBERATELY HERMETIC. No network, no warehouse, no user data — so it runs
identically on this laptop and on a CI runner that has neither. Where a module
genuinely cannot be imported without local data (refresh_panels resolves the
warehouse at import and raises by design), the check SKIPS with a stated reason
and the summary counts it. A suite that quietly covers less than it claims is
the same class of problem as a freshness metric that measures write time.

    test_pipeline_invariants.py          # run everything
    test_pipeline_invariants.py -v       # show each check
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS, FAIL, SKIP = [], [], []
VERBOSE = "-v" in sys.argv


def check(name):
    def deco(fn):
        try:
            fn()
        except _Skip as s:
            SKIP.append((name, str(s)))
            if VERBOSE:
                print(f"  —  {name}: skipped ({s})")
        except Exception as e:
            FAIL.append((name, f"{type(e).__name__}: {e}", traceback.format_exc()))
            print(f"  ❌ {name}: {type(e).__name__}: {e}")
        else:
            PASS.append(name)
            if VERBOSE:
                print(f"  ✅ {name}")
        return fn
    return deco


class _Skip(Exception):
    pass


# ── session clock ─────────────────────────────────────────────────────────────
@check("sessions: publication lag defers to the prior session")
def _():
    import market_sessions as ms

    # 02:00 IST is before the US publish instant (16:00 ET + 1h30) for that day's
    # close, so the answer must still be the previous session. Getting this wrong
    # is how a partial bar gets quoted as a close.
    at = dt.datetime(2026, 8, 20, 2, 0, tzinfo=ms.MARKETS["IN"].zone)
    got = ms.expected_session("US", at)
    assert got == dt.date(2026, 8, 18), got


@check("sessions: real holidays are not trading days")
def _():
    import market_sessions as ms

    try:
        import exchange_calendars  # noqa: F401
    except ImportError:
        raise _Skip("exchange_calendars not installed")
    # Four days weekends-only logic got wrong, measured 2026-08-20.
    for mkt, day in (("US", "2026-07-03"), ("JP", "2026-07-20"),
                     ("JP", "2026-08-11"), ("KR", "2026-08-17"),
                     ("KR", "2026-07-17")):     # the _EXTRA_CLOSURES override
        m = ms.MARKETS[mkt]
        hols = m.holidays() if m.holidays else set()
        assert not ms._is_session(m, dt.date.fromisoformat(day), hols), f"{mkt} {day}"
    # and a normal weekday still is one
    m = ms.MARKETS["US"]
    assert ms._is_session(m, dt.date(2026, 8, 20), set())


@check("sessions: expected never runs ahead of the clock")
def _():
    import market_sessions as ms

    at = dt.datetime(2026, 8, 20, 12, 0, tzinfo=dt.timezone.utc)
    for mkt in ms.MARKETS:
        assert ms.expected_session(mkt, at) <= at.date(), mkt


# ── bar validation ────────────────────────────────────────────────────────────
@check("panels: zero-range and out-of-range bars are rejected")
def _():
    try:
        import pandas as pd
        from refresh_panels import _invalid
    except Exception as e:                       # warehouse_paths raises w/o data
        raise _Skip(f"refresh_panels unavailable ({type(e).__name__})")
    df = pd.DataFrame({
        "Open":  [0.0,   5.58, 100.0, 100.0, 100.0],
        "High":  [0.0,   5.58, 110.0, 110.0,  90.0],
        "Low":   [0.0,   5.33,  90.0,  90.0, 110.0],
        "Close": [3831.0, 5.29, 105.0, 999.0, 100.0],
        "Volume": [4536, 1108351, 1, 1, 1]})
    got = list(_invalid(df))
    assert got == [True, True, False, True, True], got


# ── EDGAR parsing ─────────────────────────────────────────────────────────────
@check("edgar: offline parse invariants (restatement, span, future instants)")
def _():
    try:
        import us_fundamentals_edgar as M
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    assert M.self_test() == 0


@check("edgar: SEC retry predicate distinguishes transport from answers")
def _():
    try:
        import requests
        import us_fundamentals_edgar as M
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")

    def http(code):
        r = requests.Response()
        r.status_code = code
        return requests.HTTPError(response=r)

    assert M._sec_retryable(requests.Timeout("t"))
    assert M._sec_retryable(http(429))            # rate limited -> try again
    assert M._sec_retryable(http(503))
    assert not M._sec_retryable(http(404))        # no XBRL -> a real answer
    assert not M._sec_retryable(http(400))
    assert not M._sec_retryable(ValueError("x"))


@check("edgar: per-year tag merge spans a tag migration")
def _():
    try:
        import us_fundamentals_edgar as M
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    # The Visa shape: an old tag covering early years, a new one covering late
    # years. First-tag-wins returned NaN for every year the store keeps.
    doc = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            {"start": "2019-01-01", "end": "2019-12-31", "val": 100,
             "form": "10-K", "filed": "2020-02-01"}]}},
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            {"start": "2025-01-01", "end": "2025-12-31", "val": 400,
             "form": "10-K", "filed": "2026-02-01"}]}},
    }}}
    rows = {r["fy_end"]: r["revenue"] for r in M.parse_companyfacts(doc)}
    assert rows.get("2019-12-31") == 100, rows
    assert rows.get("2025-12-31") == 400, rows


# ── refresh planner ───────────────────────────────────────────────────────────
@check("ensure_fresh: budget is wall-clock, not monotonic")
def _():
    import time

    try:
        import ensure_fresh as E
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    t0 = time.time()
    r = E.run_step("/bin/sleep 20", 3)
    el = time.time() - t0
    assert r["code"] == "TIMEOUT", r
    assert el < 8, f"took {el:.1f}s — timeout did not fire on wall-clock"


@check("ensure_fresh: BLOCKING steps are planned before optional ones")
def _():
    try:
        import ensure_fresh as E
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    state = {"datasets": [
        {"id": "a.KR", "market": "KR", "verdict": "STALE", "depends_on": [],
         "refresh": "zzz_korea.py"},
        {"id": "b.US", "market": "US", "verdict": "STALE", "depends_on": [],
         "refresh": "aaa_us.py"},
    ]}
    # Alphabetically zzz_korea sorts last; by need, the US step must come FIRST.
    steps = E.plan(state, None, ["US"])
    assert steps[0]["blocking"] is True, steps
    assert steps[0]["cmd"] == "aaa_us.py", steps


# ── roster ────────────────────────────────────────────────────────────────────
@check("roster: outcomes are derived from what the log says happened")
def _():
    try:
        import mailer_roster as R
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    log = (
        "=== daily mailer Wed Aug 19 06:30:04 IST 2026 · data=0 send=1 ===\n"
        "[STEP] 1 x [13/13] send gates\n"
        "  ❌ send SUPPRESSED — price reconcile flagged 1 market(s)\n"
        "  draft saved → brief_today.html (Daily Market Brief — 19 Aug 2026 "
        "+ Picks (209 · 115 buy-zone · 8 bundles))\n"
        "[ALERT] 2 step(s) failed: reconcile: 1 market(s) stale scan prices\n"
        "  [alert] sent 'daily_mailer.sh failed' -> someone@example.com\n"
        "=== done Wed Aug 19 06:32:16 IST 2026 ===\n")
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "daily_mailer_20260819.log"
        p.write_text(log)
        runs = R.parse_log(p)
    assert len(runs) == 1, runs
    r = runs[0]
    # An ALERT email is also a "sent" line — it must not be mistaken for the brief.
    assert r.outcome == "SUPPRESSED", r.outcome
    assert r.n_failures == 2, r.n_failures
    assert (r.picks, r.buy_zone, r.bundles) == (209, 115, 8), r
    assert r.runtime_min == 2.2, r.runtime_min


@check("roster: a killed run is INCOMPLETE, not silently fine")
def _():
    try:
        import mailer_roster as R
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    log = ("=== daily mailer Fri Aug 15 06:30:00 IST 2026 · data=0 send=1 ===\n"
           "[STEP] 1 x [1/13] dependency check\n")     # no === done ===
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "daily_mailer_20260815.log"
        p.write_text(log)
        r = R.parse_log(p)[0]
    assert r.outcome == "INCOMPLETE", r.outcome
    assert r.finished == "", r.finished


def main() -> int:
    print("=== pipeline invariants ===")
    n = len(PASS) + len(FAIL) + len(SKIP)
    print(f"\n  {len(PASS)} passed · {len(FAIL)} failed · {len(SKIP)} skipped "
          f"({n} checks)")
    for name, reason in SKIP:
        print(f"    — skipped: {name} ({reason})")
    for name, msg, tb in FAIL:
        print(f"\n  ❌ {name}\n{tb}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
