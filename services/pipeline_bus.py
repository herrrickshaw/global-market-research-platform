#!/usr/bin/env python3
"""
pipeline_bus.py — the handoff between collector, scoring and delivery.

THE PROBLEM THIS REPLACES. The stages were coupled by a mutex
(/tmp/daily_pipeline.lock). On 2026-08-15 the 03:00 data phase ran until 07:27,
the 06:30 send found the lock held, printed one line, and exited 0. launchd
recorded success. No brief went out and nothing said so.

A mutex says "wait for me". That is the wrong contract between a slow upstream
and a downstream with a hard deadline. What delivery actually needs to know is
"what is the newest scoring output that passed, and is it fresh enough for me to
send?" — a question it can answer alone, in milliseconds, whether or not the
collector is still running.

So: no stage ever blocks on another. Each publishes what it produced; each reads
the newest passing artifact from the stage above and decides for itself.

    publish("collector", run_id, "ok", asof=date.today(), artifact="stock_quotes", rows=21198)
    art = latest("scoring", max_age_days=1)     # None if nothing fresh enough

DEGRADED IS A FIRST-CLASS OUTCOME. Not every failure is binary. Delivery sending
yesterday's scores because today's collector is late is a real, useful outcome —
but only if it is recorded as `degraded` and reported, rather than passing as
`ok`. Today's session was mostly a hunt for failures that had been rounded to
success; this is the smallest structure that stops that happening again.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import socket
import subprocess
import uuid
from typing import Any, Optional

DSN = os.environ.get("PIPELINE_DSN", "dbname=market_data")

_OK, _FAILED, _DEGRADED = "ok", "failed", "degraded"
STAGES = ("collector", "scoring", "delivery", "serving")


def _psql(sql: str, *params: str) -> str:
    """
    One code path to the database, via psql.

    Deliberately not psycopg: `psycopg` is in the pipeline venv's
    "optional absent (guarded)" list, and this module has to work from any of
    the four services and from a bare cron shell. psql is present everywhere
    Postgres is, and this is a handful of tiny statements per run, not a hot
    path — the dependency saved is worth more than the microseconds lost.
    """
    cmd = ["psql", "-d", DSN, "-tAq", "-v", "ON_ERROR_STOP=1", "-c", sql]
    for i, p in enumerate(params, start=1):
        cmd[-1] = cmd[-1].replace(f"${i}", _quote(p))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(f"pipeline_bus: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def _quote(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def new_run_id() -> str:
    """A run id groups one logical pass. Time-ordered so logs sort naturally."""
    return f"{_dt.datetime.now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"


def publish(stage: str, run_id: str, status: str, asof: _dt.date,
            artifact: Optional[str] = None, rows: Optional[int] = None,
            **detail: Any) -> None:
    """Record what this stage produced. Never raises into the caller's control flow."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
    if status not in (_OK, _FAILED, _DEGRADED):
        raise ValueError(f"unknown status {status!r}")
    detail.setdefault("host", socket.gethostname())
    detail.setdefault("pid", os.getpid())
    _psql(
        "INSERT INTO pipeline.events (stage, run_id, status, artifact, rows, asof, detail) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)",
        # Pass None through, never the string "NULL": _quote() already emits a
        # bare NULL for None, whereas "NULL" would be quoted into the literal
        # text 'NULL' and rejected by a bigint column.
        stage, run_id, status, artifact, rows,
        asof.isoformat(), json.dumps(detail),
    )


def latest(stage: str, max_age_days: Optional[int] = None) -> Optional[dict]:
    """
    Newest artifact from `stage` that PASSED, or None.

    🔴 max_age_days is measured against `asof` — the DATA's date — not against
    when the row was written. A stage that reruns an old day writes a fresh row
    about stale data; judging by created_at would call that current. That exact
    conflation is what nearly let a 17-day-old serving table be snapshotted as
    today's observation (E-021), so freshness here always means the data's age.
    """
    where = "status = 'ok' AND stage = $1"
    if max_age_days is not None:
        where += f" AND asof >= current_date - {int(max_age_days)}"
    row = _psql(
        "SELECT row_to_json(t) FROM ("
        f"  SELECT stage, run_id, status, artifact, rows, asof, detail, created_at"
        f"  FROM pipeline.events WHERE {where}"
        "   ORDER BY asof DESC, created_at DESC LIMIT 1"
        ") t", stage)
    return json.loads(row) if row else None


def gate(stage: str, max_age_days: int = 1) -> tuple[Optional[dict], str]:
    """
    What a downstream stage should call.

    Returns (artifact, verdict) where verdict is one of:
        ok        — fresh upstream artifact, proceed normally
        degraded  — an older artifact exists; proceed but SAY SO
        blocked   — nothing usable at all

    The caller decides what to do. The point is that it gets to decide, with the
    facts, instead of discovering hours later that it silently did nothing.
    """
    fresh = latest(stage, max_age_days=max_age_days)
    if fresh:
        return fresh, _OK
    any_ok = latest(stage)
    if any_ok:
        return any_ok, _DEGRADED
    return None, "blocked"


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--status", action="store_true", help="show the latest event per stage")
    a = p.parse_args()
    if a.status:
        print(f"{'STAGE':<12}{'ASOF':<12}{'STATUS':<10}{'ROWS':>10}  ARTIFACT")
        for s in STAGES:
            e = latest(s)
            if e:
                print(f"{s:<12}{str(e['asof']):<12}{e['status']:<10}"
                      f"{str(e.get('rows') or '-'):>10}  {e.get('artifact') or '-'}")
            else:
                print(f"{s:<12}{'—':<12}{'no events':<10}{'-':>10}  -")
    else:
        print(__doc__)
