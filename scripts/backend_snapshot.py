#!/usr/bin/env python3
"""
backend_snapshot.py — record the Cassandra-only backend facts before the DB goes down.

WHY THIS EXISTS. Two things the daily audit needs to check live behind Cassandra,
and Cassandra is deliberately down when the audit runs:

    cassandra-stop   00:12          audit / daily_mailer   03:00 · 06:30 · ~07:00
    cassandra-start  09:00

So the 2026-08-18 audit could verify neither of them and had to report both as
"unverified":

  1. The Darvas rescore (E-001/E-028). `scan_darvas` now gates imputed
     fundamentals out of score AND max_score and thresholds on a fraction of what
     was evaluable. The regression signal is the BUY share — 31.4% before the fix,
     7.4% after. Nothing in the nightly chain prints it. The only Darvas number in
     daily_mailer_*.log is the US scan's box-breakout count, which is a DIFFERENT
     screen with a different denominator; reading it as this one is how a rescore
     regression would slip through looking fine.

  2. stock_quotes_history depth (E-012). The table is the walk-forward substrate
     the rescore is "not return-calibrated" against yet, so its row count and
     snapshot_date coverage are the thing to watch accumulate.

WHY HERE AND NOT A NEW JOB. This repo's own lesson (see the intl-PIT trickle added
to run_fundamentals_offhours.sh rather than a fresh plist): a second uncoupled
schedule drifts away from the thing it is meant to observe. cassandra_window.sh
stop already runs at the last moment Cassandra is guaranteed up, so the capture
rides that job and needs no clock of its own. If Cassandra is already down there is
nothing to snapshot and nothing to fail — the caller ignores our exit code.

🔴 SNAPSHOT, NOT LIVE STATE. Everything written here is as of the 00:12 capture, so
`captured_at` is part of the payload and every consumer must read it. A reader that
treats this as current would be making exactly the stale-data mistake the send
gates exist to catch.

Usage:
  backend_snapshot.py            # write state/backend_snapshot.json
  backend_snapshot.py --print    # also dump the payload to stdout
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path("/Users/umashankar/backend")
OUT = Path("/Users/umashankar/market-pipeline/code/python_files/state/backend_snapshot.json")

# The markets the daily scan actually covers. china/hong_kong/canada are in the
# backend's MARKETS list but carry no seeded quotes, and an empty frame would drag
# the BUY share's denominator around for no reason.
MARKETS = ["india", "us", "europe", "japan", "korea"]


def _darvas() -> dict:
    """BUY/WATCH/AVOID counts over the live universe, all markets pooled.

    Pooled deliberately: the 7.4% baseline in daily_scanner.py is a single figure
    over 16,192 names, so a per-market breakdown would not be comparable to it.
    Per-market counts ride along for diagnosis.

    lazy_load is left at its default False. Passing True is the bug this snapshot
    exists to detect, so hardcoding it here would make the check unable to fail.
    """
    import pandas as pd
    from db.quote_updater import get_market_quotes_df
    from scanners.daily_scanner import scan_darvas

    per, frames = {}, []
    for m in MARKETS:
        try:
            df = get_market_quotes_df(m)
        except Exception as exc:
            per[m] = {"error": str(exc)[:200]}
            continue
        if df is None or df.empty:
            per[m] = {"universe": 0}
            continue
        frames.append((m, df))

    total = {"BUY": 0, "WATCH": 0, "AVOID": 0}
    universe = 0
    for m, df in frames:
        rows = scan_darvas(df)
        c = {"BUY": 0, "WATCH": 0, "AVOID": 0}
        for r in rows:
            s = r.get("signal")
            if s in c:
                c[s] += 1
        # scan_darvas returns a row per input name, so len(df) is the denominator
        # even when a signal is missing.
        per[m] = {"universe": int(len(df)), **c}
        universe += int(len(df))
        for k in total:
            total[k] += c[k]

    out = {"universe": universe, **total, "per_market": per}
    if universe:
        out["buy_pct"] = round(100.0 * total["BUY"] / universe, 2)
        out["flagged_pct"] = round(
            100.0 * (total["BUY"] + total["WATCH"]) / universe, 2)
    return out


def _history() -> dict:
    """Depth of stock_quotes_history.

    COUNT(*) on a Cassandra table is a full scan and will warn; this one is small
    (it started accumulating 2026-08-15) and runs once a day against a DB about to
    be shut down anyway. If it ever gets big enough to time out, that is itself the
    answer — swap to counting distinct snapshot_date only.
    """
    from db.cassandra_client import session, KEYSPACE
    s = session()
    if s is None:
        raise RuntimeError("no Cassandra session — connect() did not succeed")
    n = s.execute(f"SELECT COUNT(*) FROM {KEYSPACE}.stock_quotes_history").one()[0]
    dates = sorted({r.snapshot_date for r in s.execute(
        f"SELECT snapshot_date FROM {KEYSPACE}.stock_quotes_history")})
    return {
        "rows": int(n),
        "distinct_dates": len(dates),
        "min_snapshot_date": str(dates[0]) if dates else None,
        "max_snapshot_date": str(dates[-1]) if dates else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--print", dest="show", action="store_true",
                    help="dump the payload to stdout as well")
    a = ap.parse_args()

    sys.path.insert(0, str(BACKEND))
    payload: dict = {"captured_at": datetime.now(timezone.utc).isoformat()}

    # Nothing below works without an explicit connect() — the module-level session
    # is None until FastAPI's lifespan calls it, and this runs outside the app.
    # Bail rather than write a file of two identical "no session" errors: the
    # caller is about to stop Cassandra anyway, and a MISSING snapshot is honest
    # where a snapshot full of errors looks like the backend is broken.
    from db.cassandra_client import connect
    if not connect():
        print("  backend snapshot: Cassandra unreachable — nothing captured")
        return 1

    # Each half is guarded separately: a broken scanner must still let the cheap
    # row count through, and vice versa. A half that fails records WHY, so the
    # audit reads a reason instead of a missing key.
    for key, fn in (("darvas", _darvas), ("stock_quotes_history", _history)):
        try:
            payload[key] = fn()
        except Exception as exc:
            payload[key] = {"error": f"{type(exc).__name__}: {exc}"[:300]}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(OUT)          # atomic: the audit never reads a half-written file

    d, h = payload.get("darvas", {}), payload.get("stock_quotes_history", {})
    print(f"  backend snapshot -> {OUT.name}: "
          f"darvas BUY {d.get('BUY', '?')}/{d.get('universe', '?')} "
          f"({d.get('buy_pct', '?')}%) · history {h.get('rows', '?')} rows "
          f"through {h.get('max_snapshot_date', '?')}")
    if a.show:
        print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
