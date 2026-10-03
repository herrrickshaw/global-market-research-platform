#!/usr/bin/env python3
"""
run_stage.py — one entry point per seam.

    python3 -m services.run_stage collector
    python3 -m services.run_stage scoring
    python3 -m services.run_stage delivery [--dry-run]

WRAPPERS, NOT REWRITES. Each stage calls the code that already runs today —
bulk_fetcher, daily_scanner, the mailer — and adds exactly one thing: it
publishes what it produced to the bus, and reads what it needs from the bus
instead of waiting on a mutex. Rewriting the pipeline logic while also changing
its topology would make any regression impossible to attribute.

RUNS ON THE HOST TOO. Nothing here requires a container. That is the point of an
incremental cut-over: the same command works under launchd today and under
compose tomorrow, so the two can be compared on identical logic before anything
is switched off.

EXIT CODES, because a scheduler only sees these:
    0   did the work
    75  EX_TEMPFAIL — legitimately blocked by an upstream, try later
    1   failed
Anything that produces no output must NOT exit 0. That confusion is precisely
how the 2026-08-15 brief was lost with launchd recording success.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_bus as bus  # noqa: E402

EX_OK, EX_FAIL, EX_TEMPFAIL = 0, 1, 75


def _today() -> _dt.date:
    return _dt.datetime.now().date()


# ── collector ────────────────────────────────────────────────────────────────

def stage_collector(run_id: str, args) -> int:
    """Refresh quotes for every market, then publish what landed."""
    sys.path.insert(0, os.path.expanduser("~/backend"))
    from db import cassandra_client as cass
    from db.bulk_fetcher import fetch_market_quotes
    cass.connect()

    total, failures = 0, []
    for market in ("india", "us", "europe", "japan", "korea"):
        try:
            r = fetch_market_quotes(market, with_fundamentals=False)
            total += int(r.get("written") or 0)
            print(f"  {market}: {r.get('written')} written, {r.get('errors')} errors")
        except Exception as e:                                  # noqa: BLE001
            failures.append(f"{market}: {type(e).__name__}")
            print(f"  {market}: FAILED {type(e).__name__}: {str(e)[:120]}")

    # A partial collection is genuinely useful — four markets out of five still
    # feeds a brief — but it must not read as a clean run to whatever comes next.
    status = "ok" if not failures else ("degraded" if total else "failed")
    bus.publish("collector", run_id, status, asof=_today(),
                artifact="herrrickshaw.stock_quotes", rows=total, failures=failures)
    print(f"collector: {status}, {total} rows")
    return EX_OK if status != "failed" else EX_FAIL


# ── scoring ──────────────────────────────────────────────────────────────────

def stage_scoring(run_id: str, args) -> int:
    """Score whatever the collector last produced. Never waits for it."""
    upstream, verdict = bus.gate("collector", max_age_days=args.max_age)
    if verdict == "blocked":
        print("scoring: no collector artifact has ever passed — nothing to score")
        bus.publish("scoring", run_id, "failed", asof=_today(), reason="no upstream")
        return EX_TEMPFAIL
    if verdict == "degraded":
        print(f"scoring: ⚠️  newest collector artifact is {upstream['asof']}, "
              f"older than {args.max_age}d — scoring it anyway, marked degraded")

    sys.path.insert(0, os.path.expanduser("~/backend"))
    from db import cassandra_client as cass
    from db.quote_updater import get_market_quotes_df
    from scanners.daily_scanner import scan_darvas, scan_piotroski
    import pandas as pd
    cass.connect()

    counts, total = {}, 0
    for market in ("india", "us", "europe", "japan", "korea"):
        d = get_market_quotes_df(market)
        if d.empty:
            continue
        dar = pd.DataFrame(scan_darvas(d))
        pio = pd.DataFrame(scan_piotroski(d))
        buys = int((dar["signal"] == "BUY").sum()) if "signal" in dar else 0
        counts[market] = {"scanned": len(d), "darvas_buy": buys,
                          "piotroski_buy": int((pio["signal"] == "BUY").sum()) if "signal" in pio else 0}
        total += len(d)
        print(f"  {market}: {len(d)} scanned, {buys} darvas BUY")

    status = "ok" if verdict == "ok" else "degraded"
    bus.publish("scoring", run_id, status, asof=_today(), artifact="daily_scan",
                rows=total, per_market=counts, upstream_asof=str(upstream["asof"]))
    print(f"scoring: {status}, {total} rows scored")
    return EX_OK


# ── delivery ─────────────────────────────────────────────────────────────────

def stage_delivery(run_id: str, args) -> int:
    """
    The reason this change exists.

    Delivery has a hard deadline. It must never be blockable by a slow
    collector, and it must never exit 0 having sent nothing. It asks the bus for
    the newest passing scoring artifact, decides for itself whether that is
    fresh enough, and is explicit about which of the three outcomes happened.
    """
    max_age = int(os.environ.get("MAX_SCORES_AGE_DAYS", args.max_age))
    scores, verdict = bus.gate("scoring", max_age_days=max_age)

    if verdict == "blocked":
        print("delivery: 🔴 no scoring artifact has ever passed — NOT sending.")
        print("          This is a real failure, not a skip: exiting 75 so the")
        print("          scheduler records it rather than logging success.")
        bus.publish("delivery", run_id, "failed", asof=_today(), reason="no scores")
        return EX_TEMPFAIL

    degraded = verdict == "degraded"
    if degraded:
        print(f"delivery: ⚠️  newest scores are {scores['asof']}, older than "
              f"{max_age}d. Sending anyway and LABELLING the brief, because a "
              f"late brief that says it is late beats no brief at all — but a "
              f"silent stale one is what the 2026-07-15 gate exists to stop.")

    if args.dry_run:
        print(f"delivery: dry-run — would send using scores asof={scores['asof']} "
              f"({scores['rows']} rows), degraded={degraded}")
        return EX_OK

    sys.path.insert(0, os.path.expanduser("~/market-pipeline/code/python_files"))
    try:
        import subprocess
        cmd = ["./daily_mailer.sh", "--send"] + (["--draft"] if degraded and args.draft_on_degraded else [])
        r = subprocess.run(cmd, cwd=os.path.expanduser("~/market-pipeline/code/python_files"),
                           capture_output=True, text=True, timeout=3600)
        sent = "sent '" in (r.stdout or "")
        status = "failed" if not sent else ("degraded" if degraded else "ok")
        bus.publish("delivery", run_id, status, asof=_today(),
                    artifact="daily_brief", scores_asof=str(scores["asof"]),
                    exit_code=r.returncode)
        print(f"delivery: {status} (mailer rc={r.returncode})")
        return EX_OK if sent else EX_FAIL
    except Exception as e:                                       # noqa: BLE001
        bus.publish("delivery", run_id, "failed", asof=_today(), reason=str(e)[:200])
        traceback.print_exc()
        return EX_FAIL


STAGES = {"collector": stage_collector, "scoring": stage_scoring, "delivery": stage_delivery}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stage", choices=sorted(STAGES))
    p.add_argument("--max-age", type=int, default=1,
                   help="how many days old an upstream artifact may be (default 1)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--draft-on-degraded", action="store_true",
                   help="on degraded input, build a draft instead of sending")
    a = p.parse_args()
    run_id = os.environ.get("PIPELINE_RUN_ID") or bus.new_run_id()
    print(f"=== {a.stage} · run {run_id} ===")
    try:
        return STAGES[a.stage](run_id, a)
    except Exception:                                            # noqa: BLE001
        traceback.print_exc()
        try:
            bus.publish(a.stage, run_id, "failed", asof=_today(), reason="unhandled")
        except Exception:                                        # noqa: BLE001
            pass
        return EX_FAIL


if __name__ == "__main__":
    sys.exit(main())
