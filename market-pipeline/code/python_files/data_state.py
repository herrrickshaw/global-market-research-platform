#!/usr/bin/env python3
"""
data_state.py — grade every dataset against the session it SHOULD hold.

`data_catalog.probe()` says what a store contains. `market_sessions` says what
it ought to contain. This module is the comparison, and it is the replacement
for `market_ingest.py --status`, which on 2026-08-19 reported

    us   United States (NASDAQ/NYSE)   2026-08-19   0d   176,062   ok [fresh]

on a morning when two thirds of the US universe was two sessions behind and the
brief was suppressed for quoting 17 Aug prices. That table was not lying about
its own metric — rows really had been written under a 19 Aug stamp. It was
measuring the wrong thing. Freshness is a property of the SESSION the data
describes, never of the moment it was written.

VERDICTS
────────
    CURRENT  session == expected
    AHEAD    session  > expected — a bar exists for a session that has not
             closed-and-published yet. NOT good news: it is a forming intraday
             bar being stored as a close. `ohlcv_JAPAN.parquet` held a 19 Aug
             bar at 07:00 IST on 19 Aug while the TSE was still trading.
    CHECK    exactly one session behind. Graded separately from STALE because
             only NSE has a real holiday calendar wired in; a single-session gap
             on US/JP/KR/EU is as likely to be an unlisted local holiday as a
             failure. Visible, not alarming.
    STALE    two or more sessions behind. No holiday explains this.
    ERROR    the probe could not read the store at all.

ROOT CAUSE, NOT SYMPTOM COUNT
─────────────────────────────
Staleness propagates: a stale price store yields a stale scan yields a stale
snapshot yields a stale brief. Reporting four failures for one cause is how a
real fix gets lost in noise, so each row names the OLDEST STALE ANCESTOR that
explains it. On 2026-08-19 that collapses eleven red rows to one:
`cache.ohlc.US`.

`--json` is the machine surface `ensure_fresh.py` plans from; `--strict` exits
non-zero if anything is STALE or ERROR, so a caller can gate a send on it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import data_catalog as dc
import market_sessions as ms

CURRENT, AHEAD, CHECK, STALE, ERROR = "CURRENT", "AHEAD", "CHECK", "STALE", "ERROR"
_ICON = {CURRENT: "✅", AHEAD: "⚠️ ", CHECK: "🟡", STALE: "🔴", ERROR: "❌"}

# Two different questions, deliberately two different sets.
#   _BAD    — "should this fail a build?" STALE/ERROR only. A single session gap
#             on a market whose holidays we do not know is not worth blocking a
#             send over; that judgement belongs to the reconcile gate, which has
#             independent witnesses.
#   _BEHIND — "is this not current?" Includes CHECK, because ROOT-CAUSE
#             PROPAGATION and REFRESH PLANNING must both see it. On 2026-08-19
#             every US row was CHECK (one session behind), so excluding CHECK
#             here left `scan.US` orphaned from `cache.ohlc.US` — the two facts
#             that only mean something together. Refreshing is idempotent and
#             cheap: if a gap really was a holiday the refresh is a no-op and the
#             grade stays CHECK, which is self-correcting. Not refreshing on the
#             chance it might be a holiday is what shipped 17 Aug prices.
_BAD = {STALE, ERROR}
_BEHIND = {CHECK, STALE, ERROR}


def grade(ds: dc.Dataset, at: dt.datetime) -> dict:
    if ds.market == "*":                       # the brief itself: judged by its inputs
        p = ds.probe()
        return {"id": ds.id, "kind": ds.kind, "market": ds.market,
                "verdict": CURRENT if p.session else ERROR, "session": p.session,
                "expected": None, "behind": 0, "detail": p.detail, "error": p.error,
                "location": ds.location, "source": ds.source,
                "depends_on": list(ds.depends_on), "refresh": ds.refresh,
                "n_units": p.n_units, "n_at_expected": p.n_at_expected}

    # Fundamentals are graded on COLLECTION AGE, never against a trading session.
    # A 10-K arrives once a year, so "is this store the same date as yesterday's
    # close?" has no meaningful answer — asking it renders every fundamentals row
    # permanently off-session, which is precisely the kind of always-red metric
    # that teaches an operator to stop reading the table.
    if ds.kind == "fundamentals":
        p = ds.probe()
        age = (at.date() - p.session).days if p.session else None
        if p.session is None:
            v = ERROR
        elif age <= dc.FUND_MAX_AGE_DAYS:
            v = CURRENT
        elif age <= dc.FUND_MAX_AGE_DAYS * 3:
            v = CHECK
        else:
            v = STALE
        return {"id": ds.id, "kind": ds.kind, "market": ds.market, "verdict": v,
                "session": p.session, "expected": None, "behind": 0,
                "detail": p.detail, "error": p.error, "location": ds.location,
                "source": ds.source, "depends_on": list(ds.depends_on),
                "refresh": ds.refresh, "n_units": p.n_units,
                "n_at_expected": p.n_at_expected, "authority": ds.authority}

    exp = ms.expected_session(ds.market, at)
    p = ds.probe()
    if p.session is None:
        v, behind = ERROR, None
    elif p.session > exp:
        v, behind = AHEAD, -len(ms.sessions_between(ds.market, exp, p.session))
    elif p.session == exp:
        v, behind = CURRENT, 0
    else:
        behind = len(ms.sessions_between(ds.market, p.session, exp))
        v = CHECK if behind == 1 else STALE
    return {"id": ds.id, "kind": ds.kind, "market": ds.market, "verdict": v,
            "session": p.session, "expected": exp, "behind": behind,
            "detail": p.detail, "error": p.error, "location": ds.location,
            "source": ds.source, "depends_on": list(ds.depends_on),
            "refresh": ds.refresh, "n_units": p.n_units,
            "n_at_expected": p.n_at_expected, "authority": ds.authority}


def _root_cause(rows: dict[str, dict]) -> None:
    """Annotate each bad row with the oldest stale ancestor explaining it."""
    def walk(rid: str, seen: frozenset[str]) -> str:
        r = rows.get(rid)
        if not r or rid in seen:
            return rid
        for dep in r.get("depends_on", []):
            d = rows.get(dep)
            if d and d["verdict"] in _BEHIND:
                return walk(dep, seen | {rid})
        return rid
    for rid, r in rows.items():
        r["root_cause"] = walk(rid, frozenset()) if r["verdict"] in _BEHIND else None


def evaluate(at: dt.datetime | None = None, markets: list[str] | None = None) -> dict:
    at = at or dt.datetime.now(ms.UTC)
    rows = {}
    for d in dc.catalog(at):
        if markets and d.market not in markets and d.market != "*":
            continue
        rows[d.id] = grade(d, at)
    _root_cause(rows)
    worst = STALE if any(r["verdict"] in _BAD for r in rows.values()) else CURRENT
    return {"at": at.isoformat(), "worst": worst, "datasets": list(rows.values())}


def provenance(markets: list[str], at: dt.datetime | None = None) -> list[dict]:
    """Per-market facts for the reader-facing caveat: WHICH session, from WHERE.

    The brief's caveat used to report the scan file's mtime — "scanned 19 Aug
    04:59" — which on 2026-08-19 sat above prices from the 17 Aug close. Both
    halves of that line were true and together they were misleading: the reader
    is told when we looked and never what they are looking at, so a two-day-old
    price is indistinguishable from a fresh one.

    So each row states the SESSION the quoted prices belong to, the venue and
    local time that session closed, the credible source, and — when the data is
    behind — how far behind, in sessions. `stale` is the flag the template uses
    to decide whether the caveat needs to lead with a warning rather than a
    footnote.
    """
    at = at or dt.datetime.now(ms.UTC)
    state = evaluate(at, markets)
    rows = []
    for m in markets:
        scan = next((r for r in state["datasets"] if r["id"] == f"scan.{m}"), None)
        if not scan:
            continue
        mk = ms.MARKETS[m]
        sess, exp = scan["session"], scan["expected"]
        behind = scan["behind"] or 0
        rows.append({
            "market": m, "label": mk.label, "venue": mk.venue,
            "session": sess, "expected": exp, "behind": behind,
            "verdict": scan["verdict"],
            "stale": scan["verdict"] in _BEHIND,
            "ahead": scan["verdict"] == AHEAD,
            "closed_local": (ms.close_utc(m, sess).astimezone(mk.zone)
                             if sess else None),
            "source": mk.source,
            "vintage": ms.vintage(m, sess, at) if sess else "unknown",
        })
    return rows


def render(st: dict, verbose: bool = False) -> None:
    at = dt.datetime.fromisoformat(st["at"]).astimezone()
    print(f"=== DATA STATE as of {at:%Y-%m-%d %H:%M %Z} ===")
    print(f"  {'':2} {'DATASET':26} {'MKT':4} {'HOLDS':11} {'EXPECTED':11} {'':7} DETAIL")
    for r in st["datasets"]:
        s = r["session"].isoformat() if r["session"] else "—"
        e = r["expected"].isoformat() if r["expected"] else "—"
        b = ("" if not r["behind"] else
             f"-{r['behind']}s" if r["behind"] > 0 else f"+{-r['behind']}s")
        d = r["error"] or r["detail"]
        if r["verdict"] in _BEHIND and r.get("root_cause") and r["root_cause"] != r["id"]:
            d = f"caused by {r['root_cause']}" + (f" · {d}" if d else "")
        if r["n_units"] and r["verdict"] in _BEHIND:
            d = f"{r['n_at_expected']}/{r['n_units']} at expected · {d}"
        print(f"  {_ICON[r['verdict']]} {r['id']:26} {r['market']:4} {s:11} {e:11} "
              f"{b:7} {d[:64]}")
        if verbose:
            print(f"     ↳ {r['location']}  [{r['source']}]")

    behind = [r for r in st["datasets"] if r["verdict"] in _BEHIND]
    roots = sorted({r["root_cause"] for r in behind if r.get("root_cause")})
    print()
    if not behind:
        print("  ✅ every dataset holds its expected session.")
    else:
        print(f"  {len(behind)} dataset(s) not current — {len(roots)} root cause(s):")
        for rid in roots:
            r = next(x for x in st["datasets"] if x["id"] == rid)
            downstream = [x["id"] for x in behind
                          if x.get("root_cause") == rid and x["id"] != rid]
            print(f"    {_ICON[r['verdict']]} {rid}  holds {r['session']}, "
                  f"expected {r['expected']}")
            print(f"       {r['location']}")
            if downstream:
                print(f"       strands: {', '.join(downstream)}")
            if r["refresh"]:
                print(f"       fix: {r['refresh']}")
    ahead = [r for r in st["datasets"] if r["verdict"] == AHEAD]
    if ahead:
        print(f"\n  ⚠️  {len(ahead)} dataset(s) hold a bar for an UNCLOSED session "
              f"(forming intraday bar stored as a close):")
        for r in ahead:
            print(f"      {r['id']}: holds {r['session']}, latest published {r['expected']}")


def main() -> int:
    ap = argparse.ArgumentParser(description="grade data freshness by SESSION, not by write time")
    ap.add_argument("--at", help="ISO instant to evaluate at")
    ap.add_argument("--markets", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 if anything STALE/ERROR")
    # --require-current is the SEND GATE, and it is deliberately stricter than
    # --strict: it fails on CHECK too. One session behind is a perfectly fine
    # state for a research panel and a completely unacceptable one for the prices
    # a brief quotes this morning — which is exactly what shipped on 2026-08-19,
    # where every US row graded CHECK and the brief had to be suppressed.
    ap.add_argument("--require-current", nargs="*", metavar="ID_OR_KIND",
                    help="exit 1 unless these datasets (or kinds) hold their "
                         "expected session; combine with --markets")
    a = ap.parse_args()

    at = dt.datetime.fromisoformat(a.at) if a.at else dt.datetime.now(ms.UTC)
    if at.tzinfo is None:
        at = at.replace(tzinfo=ms.UTC)
    st = evaluate(at, a.markets)

    if a.json:
        print(json.dumps(st, indent=2, default=str))
    else:
        render(st, a.verbose)

    if a.require_current is not None:
        want = set(a.require_current) or {"scan"}
        sel = [r for r in st["datasets"]
               if r["id"] in want or r["kind"] in want]
        bad = [r for r in sel if r["verdict"] in _BEHIND]
        if not sel:
            print(f"\n  ❌ --require-current matched no datasets: {sorted(want)}")
            return 1
        if bad:
            print(f"\n  🔴 NOT CURRENT — {len(bad)} required dataset(s):")
            for r in bad:
                print(f"     {r['id']}: holds {r['session']}, expected {r['expected']}"
                      f"  (root cause: {r.get('root_cause') or r['id']})")
            return 1
        print(f"\n  ✅ all {len(sel)} required dataset(s) current.")
        return 0
    return 1 if (a.strict and st["worst"] in _BAD) else 0


if __name__ == "__main__":
    sys.exit(main())
