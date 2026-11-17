#!/usr/bin/env python3
"""
mailer_roster.py — every daily brief run, as a table you can ask questions of.

WHY THIS EXISTS
───────────────
The pipeline's whole history sits in 22 (and growing) `daily_mailer_*.log` files
and one `state/last_brief_sent.json` that only ever holds the LAST send. So every
question about behaviour over time has had to be answered by grepping logs by
hand, which is how these went unnoticed:

  * 2026-08-15 the send was lost to the lock and NOTHING recorded it. It came to
    light days later because someone asked.
  * The 08-19 suppression looked like a one-off until the logs were read back and
    a pattern of stale-scan suppressions appeared.
  * Nobody could say how often a step fails, which step fails most, or whether
    the picks count is drifting — all of which are one query over this table.

A roster turns "did it work" into "how often does it work, and when it doesn't,
what breaks". `state/last_brief_sent.json` remains the authority for the LAST
send; this is the history around it.

WHAT A ROW IS
─────────────
One PHASE, not one day. `daily_mailer.sh` appends both the 03:00 data phase and
the 06:30 send phase to the same per-day file, and they fail in different ways —
collapsing them would hide which half broke. `data=1 send=0` and `data=0 send=1`
are therefore separate rows, joined by `log_date`.

OUTCOME is derived from what the log SAYS HAPPENED, in priority order, because
several markers can co-occur: a run that suppressed also wrote a draft, and a run
that sent may still have had failed steps.

    SENT        `sent '<subject>' -> <addr>` present
    SUPPRESSED  the send gate refused; a draft was written instead
    DRAFT       --draft was requested, no send attempted
    LOST        SEND LOST (lock held) — exit 75
    DATA_ONLY   a data phase, which never sends
    INCOMPLETE  no `=== done ===` trailer: the run was killed mid-flight

Storage is DuckDB per the repo convention ("tracked tabular data goes in DuckDB,
not loose CSVs"), rebuilt idempotently from the logs so it can always be thrown
away and regenerated.

    mailer_roster.py --rebuild        # parse every log into the table
    mailer_roster.py                  # the roster, newest first
    mailer_roster.py --failures       # which steps fail, how often
    mailer_roster.py --picks          # recommendation counts over time
    mailer_roster.py --json
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "data" / "mailer_roster.duckdb"

_HDR = re.compile(r"^=== daily mailer (.+?) · data=(\d) send=(\d) ===")
_DONE = re.compile(r"^=== done (.+?) ===")
_STEP = re.compile(r"^\[STEP\] (\d+) \S+ (.+)$")
_SENT = re.compile(r"sent '(.+?)'\s*(?:→|->)\s*(\S+)")
_DRAFT = re.compile(r"draft saved → \S+ \((.+?)\)\s*$")
_ALERT = re.compile(r"^\[ALERT\] (\d+) step\(s\) failed: (.*)$")
_TIMEOUT = re.compile(r"TIMEOUT: '(.+?)' exceeded (\d+)s")
# Subject encodes the recommendation counts:
#   "… + 📊 Picks (209 · 112 buy-zone · 8 bundles)"
_PICKS = re.compile(r"Picks \((\d+)\s*·\s*(\d+) buy-zone\s*·\s*(\d+) bundles\)")


@dataclass
class Run:
    log_date: str
    phase: str                 # data | send | both
    started: str
    finished: str = ""
    runtime_min: float | None = None
    outcome: str = "INCOMPLETE"
    subject: str = ""
    sent_to: str = ""
    picks: int | None = None
    buy_zone: int | None = None
    bundles: int | None = None
    n_failures: int = 0
    failures: str = ""
    timeouts: str = ""
    self_heal: bool = False
    ensure_fresh: bool = False
    suppressed_reason: str = ""
    steps: int = 0


def _parse_ts(s: str) -> dt.datetime | None:
    for fmt in ("%a %b %d %H:%M:%S %Z %Y", "%a %b %d %H:%M:%S IST %Y"):
        try:
            return dt.datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def parse_log(path: Path) -> list[Run]:
    """One log file → one Run per phase. Phases are delimited by the header."""
    date_tag = re.search(r"(\d{8})", path.name)
    log_date = (dt.datetime.strptime(date_tag.group(1), "%Y%m%d").date().isoformat()
                if date_tag else "")
    runs: list[Run] = []
    cur: Run | None = None
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.rstrip()
        m = _HDR.match(line)
        if m:
            when, data, send = m.group(1), m.group(2) == "1", m.group(3) == "1"
            phase = "both" if data and send else ("data" if data else "send")
            cur = Run(log_date=log_date, phase=phase, started=when)
            if phase == "data":
                cur.outcome = "DATA_ONLY"
            runs.append(cur)
            continue
        if cur is None:
            continue

        if _STEP.match(line):
            cur.steps += 1
        if "[SELF-HEAL]" in line:
            cur.self_heal = True
        if "[ENSURE-FRESH]" in line:
            cur.ensure_fresh = True

        m = _TIMEOUT.search(line)
        if m:
            cur.timeouts = ", ".join(filter(None, [cur.timeouts,
                                                   f"{m.group(1)} (>{m.group(2)}s)"]))
        m = _ALERT.match(line)
        if m:
            cur.n_failures = int(m.group(1))
            cur.failures = m.group(2).strip()

        if "SEND LOST" in line:
            cur.outcome = "LOST"
        if "send SUPPRESSED" in line:
            cur.outcome = "SUPPRESSED"
            r = line.split("—", 1)
            cur.suppressed_reason = r[1].strip() if len(r) > 1 else ""

        m = _SENT.search(line)
        if m and "alert" not in line.lower():
            # A run can send the BRIEF and also send an alert; the alert line
            # carries "[alert]" and must not be mistaken for the deliverable.
            cur.outcome = "SENT"
            cur.subject, cur.sent_to = m.group(1), m.group(2)
        m = _DRAFT.search(line)
        if m:
            if cur.outcome not in ("SENT", "SUPPRESSED", "LOST"):
                cur.outcome = "DRAFT"
            if not cur.subject:
                cur.subject = m.group(1)

        m = _DONE.match(line)
        if m:
            cur.finished = m.group(1)
            a, b = _parse_ts(cur.started), _parse_ts(cur.finished)
            if a and b:
                cur.runtime_min = round((b - a).total_seconds() / 60, 1)
            cur = None

    for r in runs:
        m = _PICKS.search(r.subject or "")
        if m:
            r.picks, r.buy_zone, r.bundles = (int(m.group(1)), int(m.group(2)),
                                              int(m.group(3)))
    return runs


def collect(pattern: str = "daily_mailer_2026*.log") -> list[Run]:
    out: list[Run] = []
    for p in sorted(HERE.glob(pattern)):
        try:
            out += parse_log(p)
        except Exception as e:                      # one bad log must not stop the rest
            print(f"  ! {p.name}: {type(e).__name__}: {e}", file=sys.stderr)
    return out


def rebuild(runs: list[Run]) -> None:
    import duckdb

    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("DROP TABLE IF EXISTS runs")
    con.execute("""CREATE TABLE runs (
        log_date DATE, phase VARCHAR, started VARCHAR, finished VARCHAR,
        runtime_min DOUBLE, outcome VARCHAR, subject VARCHAR, sent_to VARCHAR,
        picks INTEGER, buy_zone INTEGER, bundles INTEGER,
        n_failures INTEGER, failures VARCHAR, timeouts VARCHAR,
        self_heal BOOLEAN, ensure_fresh BOOLEAN, suppressed_reason VARCHAR,
        steps INTEGER)""")
    con.executemany(
        "INSERT INTO runs VALUES (" + ",".join(["?"] * 18) + ")",
        [tuple(asdict(r).values()) for r in runs])
    con.close()


def _q(sql: str):
    import duckdb

    if not DB.exists():
        print("roster not built — run: mailer_roster.py --rebuild", file=sys.stderr)
        sys.exit(1)
    return duckdb.connect(str(DB), read_only=True).execute(sql).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description="roster of every daily brief run")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--failures", action="store_true", help="which steps fail, how often")
    ap.add_argument("--picks", action="store_true", help="recommendation counts over time")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()

    if a.rebuild:
        runs = collect()
        rebuild(runs)
        print(f"roster rebuilt: {len(runs)} phase-runs from "
              f"{len({r.log_date for r in runs})} days → {DB.name}")
        return 0

    if a.json:
        rows = _q("SELECT * FROM runs ORDER BY log_date DESC, started")
        cols = [d[0] for d in
                __import__("duckdb").connect(str(DB), read_only=True)
                .execute("SELECT * FROM runs LIMIT 0").description]
        print(json.dumps([dict(zip(cols, r)) for r in rows], indent=2, default=str))
        return 0

    if a.failures:
        print("=== failures by step ===")
        rows = _q("SELECT failures, count(*) n, min(log_date), max(log_date) "
                  "FROM runs WHERE n_failures > 0 GROUP BY 1 ORDER BY n DESC")
        for f, n, lo, hi in rows:
            print(f"  {n:>2}x  {str(f)[:72]}")
            print(f"        first {lo} · last {hi}")
        tot = _q("SELECT count(*), sum(CASE WHEN n_failures>0 THEN 1 ELSE 0 END) FROM runs")[0]
        print(f"\n  {tot[1] or 0}/{tot[0]} phase-runs had at least one failed step")
        return 0

    if a.picks:
        print("=== recommendation counts (sent briefs) ===")
        print(f"  {'DATE':12} {'PICKS':>6} {'BUY-ZONE':>9} {'BUNDLES':>8}  SUBJECT")
        for d, p, b, bu, s in _q(
                "SELECT log_date, picks, buy_zone, bundles, subject FROM runs "
                "WHERE picks IS NOT NULL ORDER BY log_date"):
            print(f"  {str(d):12} {p:>6} {b:>9} {bu:>8}  {str(s)[:44]}")
        stats = _q("SELECT count(*), avg(picks), min(picks), max(picks), "
                   "avg(buy_zone) FROM runs WHERE picks IS NOT NULL")[0]
        if stats[0]:
            print(f"\n  n={stats[0]}  picks avg {stats[1]:.0f} "
                  f"(min {stats[2]}, max {stats[3]})  buy-zone avg {stats[4]:.0f}")
        return 0

    print("=== mailer roster ===")
    print(f"  {'DATE':11} {'PHASE':6} {'OUTCOME':11} {'MIN':>6} {'FAIL':>4}  NOTES")
    for (d, ph, oc, rt, nf, fl, sh, ef, to) in _q(
            f"SELECT log_date, phase, outcome, runtime_min, n_failures, failures, "
            f"self_heal, ensure_fresh, timeouts FROM runs "
            f"ORDER BY log_date DESC, started DESC LIMIT {a.limit}"):
        notes = []
        if sh:
            notes.append("self-heal")
        if ef:
            notes.append("ensure-fresh")
        if to:
            notes.append(f"TIMEOUT {to[:28]}")
        if nf:
            notes.append(str(fl)[:44])
        rts = f"{rt:.0f}" if rt is not None else "—"
        print(f"  {str(d):11} {ph:6} {oc:11} {rts:>6} {nf:>4}  {' · '.join(notes)[:60]}")

    summ = _q("SELECT outcome, count(*) FROM runs GROUP BY 1 ORDER BY 2 DESC")
    print("\n  " + " · ".join(f"{o} {n}" for o, n in summ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
