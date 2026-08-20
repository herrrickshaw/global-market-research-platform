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


@check("panels: invalid EXISTING rows are evicted so a good fetch can replace them")
def _():
    try:
        import pandas as pd
        from refresh_panels import _invalid
    except Exception as e:
        raise _Skip(f"refresh_panels unavailable ({type(e).__name__})")
    # The merge keeps `old` on a (Symbol, Date) collision, which is right for
    # adjustment stability and made corruption PERMANENT: the 473 zero-range EU
    # bars would have shadowed every future fetch. Invalid old rows must be
    # dropped BEFORE the dedup so the good row wins.
    old = pd.DataFrame({"Symbol": ["AAL.L", "SAP.DE"], "Date": ["2026-08-18"] * 2,
                        "Open": [0.0, 100.0], "High": [0.0, 110.0],
                        "Low": [0.0, 90.0], "Close": [3831.0, 105.0],
                        "Volume": [1, 1]})
    new = pd.DataFrame({"Symbol": ["AAL.L"], "Date": ["2026-08-18"],
                        "Open": [3800.0], "High": [3850.0], "Low": [3790.0],
                        "Close": [3831.0], "Volume": [4536]})
    kept = old[~_invalid(old)]
    merged = pd.concat([kept, new], ignore_index=True).drop_duplicates(
        subset=["Symbol", "Date"], keep="first")
    row = merged[merged.Symbol == "AAL.L"].iloc[0]
    assert row["High"] == 3850.0, f"bad row survived: {row.to_dict()}"
    assert len(merged) == 2, merged          # SAP.DE untouched


@check("edgar: EPS uses weighted-average diluted, not a far-off cover-page count")
def _():
    try:
        import us_fundamentals_edgar as M
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    # The Visa shape. Its only dei counts are years stale; matching the NEAREST
    # with no distance bound gave FY2025 a ~469M share count against a real
    # ~1.9bn, and an EPS of 42.74 where Visa's is ~10.
    doc = {"facts": {
        "us-gaap": {
            "NetIncomeLoss": {"units": {"USD": [
                {"start": "2025-01-01", "end": "2025-12-31", "val": 20_000_000_000,
                 "form": "10-K", "filed": "2026-02-01"}]}},
            "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [
                {"start": "2025-01-01", "end": "2025-12-31", "val": 2_000_000_000,
                 "form": "10-K", "filed": "2026-02-01"}]}}},
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
            {"end": "2019-01-31", "val": 469_000_000}]}}}}}
    row = M.parse_companyfacts(doc)[-1]
    assert row["shares"] == 2_000_000_000, row["shares"]
    assert abs(row["net_income"] / row["shares"] - 10.0) < 0.01

    # And with NO usable share figure the answer must be None, never a guess:
    # a wrong EPS prices a mega-cap at a quarter of its multiple, a missing one
    # is merely missing.
    doc["facts"]["us-gaap"].pop("WeightedAverageNumberOfDilutedSharesOutstanding")
    assert M.parse_companyfacts(doc)[-1]["shares"] is None


@check("edgar: ifrs-full filers parse when us-gaap is absent")
def _():
    try:
        import us_fundamentals_edgar as M
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    # 20-F/40-F forms were already accepted but only us-gaap was ever searched,
    # so every IFRS filer parsed to zero rows: TSM, SHEL, BP, AZN, NVO and ~200
    # more ADRs. The reporting currency must be recorded, not assumed USD —
    # NVO files in DKK and SPOT in EUR.
    doc = {"facts": {"ifrs-full": {
        "Revenue": {"units": {"DKK": [
            {"start": "2025-01-01", "end": "2025-12-31", "val": 309_000_000_000,
             "form": "20-F", "filed": "2026-02-01"}]}},
        "ProfitLoss": {"units": {"DKK": [
            {"start": "2025-01-01", "end": "2025-12-31", "val": 102_000_000_000,
             "form": "20-F", "filed": "2026-02-01"}]}},
        "Assets": {"units": {"DKK": [
            {"end": "2025-12-31", "val": 400_000_000_000,
             "form": "20-F", "filed": "2026-02-01"}]}}}}}
    rows = M.parse_companyfacts(doc)
    assert rows, "IFRS filer parsed to zero rows"
    r = rows[-1]
    assert r["framework"] == "ifrs", r["framework"]
    assert r["currency"] == "DKK", r["currency"]
    assert r["revenue"] == 309_000_000_000


@check("edgar: successor-CIK retry fires for operating companies, not funds")
def _():
    try:
        import us_fundamentals_edgar as M
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    # XOM's mapped CIK returns a present-but-empty doc that still carries
    # `us-gaap` — a re-registered filer. An ETF carries `dei` alone and never
    # will, and retrying every fund cost 0.6 tickers/s against 4/s allowed.
    reregistered = {"entityName": "Exxon Mobil Corporation",
                    "facts": {"dei": {}, "us-gaap": {}}}
    fund = {"entityName": "SPDR S&P 500 ETF Trust", "facts": {"dei": {}}}
    assert M.resolve_by_name(fund, None, {}, tried=1) == (None, None)
    # the operating company gets past the namespace gate and into the lookup
    # (which finds nothing here because the index passed in is empty)
    assert M.resolve_by_name(reregistered, None, {"EXXON MOBIL CORP": []},
                             tried=1) == (None, None)


@check("ccc: computed from filings, and NaN when an input is genuinely absent")
def _():
    try:
        import pandas as pd
        import cash_conversion_cycle as C
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    # Apple's FY2025 filings give -71.1 days; Walmart's +2.8. Both are
    # well-known figures, which is what makes them a usable check on the
    # arithmetic rather than on our own store.
    df = pd.DataFrame({
        "ticker": ["AAPL", "XOM"],
        "fy_end": ["2025-09-27", "2025-12-31"],
        "receivables": [66_243_000_000, 40_000_000_000],
        "inventory": [6_446_000_000, None],          # XOM files no generic
        "payables": [79_000_000_000, 60_000_000_000],  # inventory or COGS tag
        "cost_of_revenue": [204_000_000_000, None],
        "revenue": [416_161_000_000, 332_238_000_000],
    })
    # A real temp parquet, so this exercises the actual read path rather than a
    # mock of it — Path.exists cannot be patched on an instance anyway.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "US_current.parquet"
        df.to_parquet(tmp, index=False)
        orig = C.STORE["US"]
        C.STORE["US"] = tmp
        try:
            out = C.from_filings("US")
        finally:
            C.STORE["US"] = orig
    got = dict(zip(out["ticker"], out["ccc"]))
    assert "AAPL" in got, out
    assert abs(got["AAPL"] - (-71.1)) < 2.0, got["AAPL"]
    # XOM must be DROPPED, not imputed: substituting total expenses for a
    # missing COGS produces a confident number with no meaning.
    assert "XOM" not in got, "a filer with no COGS/inventory was given a CCC"


@check("ccc: screener.in only fills tickers the filings could not")
def _():
    try:
        import pandas as pd
        import cash_conversion_cycle as C
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    import unittest.mock as mock
    prim = pd.DataFrame({"ticker": ["A"], "fy_end": ["2025-03-31"], "dso": [1.0],
                         "dio": [1.0], "dpo": [1.0], "ccc": [1.0],
                         "source": ["filings"]})
    fb = pd.DataFrame({"ticker": ["A", "B"], "fy_end": [pd.NaT, pd.NaT],
                       "dso": [float("nan")] * 2, "dio": [float("nan")] * 2,
                       "dpo": [float("nan")] * 2, "ccc": [99.0, 5.0],
                       "source": ["screener.in"] * 2})
    with mock.patch.object(C, "from_filings", return_value=prim), \
         mock.patch.object(C, "from_screener", return_value=fb):
        out = C.ccc("IN")
    by = dict(zip(out["ticker"], out["source"]))
    # A is covered by filings, so the scrape must NOT override it — otherwise a
    # third-party number silently wins over our own computation.
    assert by["A"] == "filings", by
    assert by["B"] == "screener.in", by
    with mock.patch.object(C, "from_filings", return_value=prim), \
         mock.patch.object(C, "from_screener", return_value=fb):
        assert set(C.ccc("IN", allow_fallback=False)["ticker"]) == {"A"}


@check("catalog: a report depends on its scan, so a refresh rebuilds both")
def _():
    try:
        import data_catalog as dc
    except Exception as e:
        raise _Skip(f"data_catalog unavailable ({type(e).__name__})")
    # 2026-08-19: scan.US reached 18 Aug while combined_US_..._0459.json still
    # held 17 Aug prices under a 19 Aug filename. The brief reads BOTH, so a
    # planner that refreshes only the scan ships mismatched halves.
    ds = {d.id: d for d in dc.catalog()}
    for m in ("IN", "US"):
        assert f"report.{m}" in ds, f"report.{m} not registered"
        assert f"scan.{m}" in ds[f"report.{m}"].depends_on, ds[f"report.{m}"].depends_on
    assert "report.IN" in ds["brief"].depends_on, ds["brief"].depends_on
    assert "report.US" in ds["brief"].depends_on, ds["brief"].depends_on


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


@check("ensure_fresh: a chatty child does not deadlock on the pipe buffer")
def _():
    import time

    try:
        import ensure_fresh as E
    except Exception as e:
        raise _Skip(f"module unavailable ({type(e).__name__})")
    # Popen(stdout=PIPE) with the drain AFTER the wait loop deadlocks any child
    # that exceeds the ~64KB pipe buffer — it blocks on write and is killed as a
    # TIMEOUT it never earned. Every real step here prints per batch with -u and
    # goes far past 64KB, so this would have burned the whole 06:30 budget.
    t0 = time.time()
    r = E.run_step("/bin/sh -c 'for i in $(seq 1 20000); do echo "
                   "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa; done'", 20)
    el = time.time() - t0
    assert r["code"] == 0, f"chatty child did not exit cleanly: {r['code']}"
    assert el < 15, f"took {el:.1f}s — output drain is blocking"
    assert r["tail"], "output was lost"


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
