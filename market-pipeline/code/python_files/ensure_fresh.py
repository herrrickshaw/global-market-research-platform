#!/usr/bin/env python3
"""
ensure_fresh.py — bring the data up to NOW before a brief is built, whenever
that brief is asked for.

THE PROBLEM THIS SOLVES
───────────────────────
The pipeline was built around a fixed clock: collect at 03:00, send at 06:30.
Everything downstream assumes the 03:00 collection happened and succeeded, and
nothing re-asks. So the brief is only as good as one unrepeatable moment:

  * 2026-08-19. The 03:00 phase ran while the Mac was on battery and slept seven
    times; 3,872 US tickers failed their incremental refresh and kept 17 Aug
    closes. At 06:30 the send phase did not re-check the data — it reconciled,
    found the staleness, and had no move left except to suppress the brief.
  * 2026-08-15. The send lost the lock and never ran at all.
  * A brief requested at 11:00, or 16:00, or on a Sunday, gets whatever 03:00
    left behind, with no notion that a newer session has since closed.

The fix is to stop treating collection as a scheduled event and start treating
it as a PRECONDITION. `data_state.py` already says which datasets are behind the
session that has closed and published as of now; this module acts on that: plan
the minimum set of refreshes, run them in dependency order, and re-verify.

Called at the top of the send phase, the 03:00 job becomes an optimisation
rather than a single point of failure — if it worked there is nothing to do and
this exits in seconds; if it did not, the gap is closed before the brief is
built instead of being discovered by the gate afterwards.

WHAT IT DELIBERATELY DOES NOT DO
────────────────────────────────
It does not refresh everything, and it does not refresh what the brief does not
use. `--require` names the markets the deliverable actually quotes (IN and US
today), and only those can block. A stale Japan panel is worth reporting and
worth fixing on its own schedule; it is not worth delaying a brief that never
mentions Japan.

It also will not silently overrun. Refreshes here are minutes-to-an-hour (a full
US scan is ~90 min), so `--max-minutes` bounds the whole plan and anything not
attempted is REPORTED as not attempted. Silent truncation would recreate the
exact failure this file exists to prevent: a brief that looks complete and is
not.

    ensure_fresh.py --require IN US --dry-run     # what would run, and why
    ensure_fresh.py --require IN US --max-minutes 45
    ensure_fresh.py --markets EU                  # fix one market out of band
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shlex
import subprocess
import tempfile
import sys
import time
from pathlib import Path

import data_state as st
import market_sessions as ms

HERE = Path(__file__).resolve().parent
PY = str(HERE / ".venv" / "bin" / "python3")


def plan(state: dict, markets: list[str] | None, require: list[str] | None
         ) -> list[dict]:
    """Minimum ordered set of refreshes that would close the gaps in `state`.

    Ordering is by dependency depth: a scan re-run before its price store is
    refreshed just re-reads the stale store and produces an identically stale
    scan — which is what happened on 2026-08-19, where re-running the US scan at
    06:30 would have changed nothing at all.

    Commands are DEDUPED. Several datasets legitimately share one refresh (the
    US price store and the US scan are the same command, because the scan is
    what writes the store), and running it twice would double a 90-minute step.
    """
    rows = {r["id"]: r for r in state["datasets"]}
    behind = [r for r in rows.values() if r["verdict"] in st._BEHIND]
    if markets:
        behind = [r for r in behind if r["market"] in markets]

    def depth(r: dict, seen=frozenset()) -> int:
        if r["id"] in seen:
            return 0
        ds = [rows[d] for d in r.get("depends_on", []) if d in rows]
        return 1 + max([depth(d, seen | {r["id"]}) for d in ds], default=-1)

    steps: dict[str, dict] = {}
    for r in sorted(behind, key=depth):
        cmd = r.get("refresh")
        if not cmd:
            continue
        s = steps.setdefault(cmd, {
            "cmd": cmd, "depth": depth(r), "for": [], "markets": set(),
            "blocking": False,
        })
        s["for"].append(r["id"])
        s["markets"].add(r["market"])
        if require and r["market"] in require:
            s["blocking"] = True
    # Order: dependency depth first (a scan after its store), then BLOCKING
    # before optional, then the command for a stable tie-break.
    #
    # 🔴 2026-08-20: blocking-before-optional was missing, and the sort fell
    # through to alphabetical. The 06:30 plan that morning put
    # `refresh_panels.py --markets US` — the only step the brief actually needs —
    # LAST in its depth group, behind a full Korea scan and two panels for
    # markets the brief does not quote. `--max-minutes` is a hard budget, so the
    # one required step was the one most likely to be dropped. Ordering by need
    # costs nothing and makes the budget cut optional work first, which is the
    # only sensible thing for it to cut.
    out = sorted(steps.values(),
                 key=lambda s: (s["depth"], not s["blocking"], s["cmd"]))
    for s in out:
        s["markets"] = sorted(s["markets"])
    return out


def run_step(cmd: str, timeout_s: float) -> dict:
    """Run one refresh through the venv interpreter, capturing the outcome.

    🔴 2026-08-20: THE BUDGET MUST BE WALL-CLOCK, NOT MONOTONIC. This used
    `subprocess.run(timeout=...)`, whose timeout is measured with a monotonic
    clock — and on macOS that clock DOES NOT ADVANCE WHILE THE MACHINE IS
    SUSPENDED. On a laptop that sleeps 8 times inside a run, the internal budget
    silently under-counts and never fires: on 20 Aug this step ran 67 minutes of
    wall-clock against a 35-minute budget without tripping, and was eventually
    killed by daily_mailer's outer `cap` at 2400s.

    This is the SAME defect `cap()` was fixed for on 2026-08-15, reintroduced
    here in Python. Comparing `time.time()` stamps counts suspended time the way
    an observer does, so the bound now means what it says.
    """
    # 🔴 EXPAND `~` — THERE IS NO SHELL HERE. Popen takes an argv list, so a
    # tilde is a literal directory name and resolves against cwd=HERE. The
    # `pg.snapshots.*` datasets were registered with
    # `refresh="python3 ~/scripts/market_ingest.py"`, which every run since has
    # executed as `.../python_files/~/scripts/market_ingest.py` — Python's
    # "can't open file", exit 2, in 0.0 min. It has NEVER succeeded, and because
    # the planner only reports "ran: <cmd>" against a dataset that is still
    # behind, a command that could not start looked exactly like a refresh that
    # ran and did not help.
    argv = [os.path.expanduser(a) for a in shlex.split(cmd)]
    if argv and argv[0].endswith(".py"):
        argv = [PY, "-u"] + argv

    # And say so when the target does not exist, rather than letting the child
    # report it in an interpreter-specific way that gets truncated to one line
    # in the mailer log. A refresh command that cannot start is a BUG in the
    # catalog, not a slow dataset — it must not read as "tried, still behind".
    _script = next((a for a in argv if a.endswith(".py")), None)
    if _script and not Path(_script).exists():
        return {"cmd": cmd, "ok": False, "code": "NOCMD", "secs": 0.0,
                "tail": [f"refresh command cannot start: no such file: {_script}",
                         "  fix the `refresh=` string in data_catalog.py"]}
    t0 = time.time()

    # 🔴 STDOUT GOES TO A FILE, NOT A PIPE. The first version of this poll loop
    # used Popen(stdout=PIPE) and only called communicate() AFTER the loop — so
    # a child that writes more than the ~64KB pipe buffer blocks on write, never
    # exits, and is killed as a TIMEOUT it never earned. Every step this runs is
    # invoked with `-u` and prints per batch: `full_us_market_scan.py --workers 10`
    # emits far past 64KB, so the 06:30 refresh would have spent its entire
    # budget deadlocked and fetched nothing.
    #
    # A temp file has no such limit and needs no reader thread. `subprocess.run`
    # (which this replaced, for the wall-clock reasons above) did not have this
    # bug because it drains concurrently — the wall-clock fix was right and this
    # was the cost of hand-rolling the wait.
    timed_out = False
    try:
        with tempfile.TemporaryFile("w+", errors="replace") as fh:
            try:
                p = subprocess.Popen(argv, cwd=HERE, stdout=fh,
                                     stderr=subprocess.STDOUT, text=True)
            except Exception as e:
                return {"cmd": cmd, "ok": False, "code": "ERROR", "secs": 0.0,
                        "tail": [str(e)]}
            while p.poll() is None:
                if time.time() - t0 >= timeout_s:
                    timed_out = True
                    p.terminate()
                    try:
                        p.wait(timeout=10)
                    except Exception:
                        p.kill()
                        p.wait()
                    break
                time.sleep(1)
            fh.flush()
            fh.seek(0)
            out = fh.read()
    except Exception as e:
        return {"cmd": cmd, "ok": False, "code": "ERROR",
                "secs": round(time.time() - t0, 1), "tail": [str(e)]}
    if timed_out:
        ok, code = False, "TIMEOUT"
        tail = [f"exceeded {timeout_s/60:.0f} min wall-clock"] + \
               out.strip().splitlines()[-2:]
    else:
        ok, code = p.returncode == 0, p.returncode
        tail = out.strip().splitlines()[-3:]
    return {"cmd": cmd, "ok": ok, "code": code, "secs": round(time.time() - t0, 1),
            "tail": tail}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="refresh whatever is behind the session that has closed as of now")
    ap.add_argument("--require", nargs="*", default=["IN", "US"],
                    help="markets the deliverable quotes; only these can block")
    ap.add_argument("--markets", nargs="*", help="restrict the plan to these markets")
    ap.add_argument("--max-minutes", type=float, default=60.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--at", help="ISO instant to plan against (testing)")
    a = ap.parse_args()

    at = dt.datetime.fromisoformat(a.at) if a.at else dt.datetime.now(ms.UTC)
    if at.tzinfo is None:
        at = at.replace(tzinfo=ms.UTC)

    before = st.evaluate(at)
    steps = plan(before, a.markets, a.require)

    print(f"=== ENSURE FRESH · {at.astimezone():%Y-%m-%d %H:%M %Z} ===")
    for m in (a.markets or sorted(ms.MARKETS)):
        print(f"  expected session {m}: {ms.expected_session(m, at)}")
    if not steps:
        # "Nothing to run" is not the same as "nothing is wrong": an orphan with
        # no refresher produces no step precisely because nothing can fix it.
        stuck = [r for r in before["datasets"]
                 if r["verdict"] in st._BEHIND and not r.get("refresh")
                 and (not a.markets or r["market"] in a.markets)]
        if stuck:
            print(f"\n  ✅ nothing refreshable is behind.")
            print(f"  ⚠️  but {len(stuck)} dataset(s) are behind with NO refresher:")
            for r in stuck:
                print(f"     {r['id']} holds {r['session']}, expected {r['expected']}")
                print(f"       {r['location']}")
        else:
            print("\n  ✅ nothing behind — every dataset holds its expected session.")
        return 0

    print(f"\n  {len(steps)} refresh step(s) planned:")
    for s in steps:
        print(f"    [{s['depth']}] {'BLOCKING ' if s['blocking'] else '         '}"
              f"{s['cmd']}")
        print(f"          for: {', '.join(s['for'])}")

    if a.dry_run:
        print("\n  --dry-run: nothing executed.")
        return 0

    budget = a.max_minutes * 60
    results, skipped = [], []
    for s in steps:
        if budget <= 0:
            skipped.append(s)
            continue
        print(f"\n  ▶ {s['cmd']}")
        r = run_step(s["cmd"], budget)
        r["for"] = s["for"]
        results.append(r)
        budget -= r["secs"]
        print(f"    {'✅' if r['ok'] else '❌'} exit={r['code']} in {r['secs']/60:.1f} min")
        for l in r["tail"]:
            print(f"      {l[:110]}")

    after = st.evaluate(dt.datetime.now(ms.UTC))
    behind_after = [r for r in after["datasets"]
                    if r["verdict"] in st._BEHIND
                    and (not a.require or r["market"] in a.require)]
    # A dataset with NO refresh command cannot be fixed by anything this tool
    # does. Reporting one as "STILL behind" after five successful refreshes —
    # and exiting 1 on it — makes a clean run look failed, which is how an exit
    # code stops being read. Orphans are listed separately, as the standing
    # problems they are.
    #
    # The motivating case was `cache.ohlcv.US_legacy`, an orphan US panel no job
    # wrote. It was RETIRED from the catalog on 2026-08-25 once its last
    # scheduled reader was repointed, so this split currently matches nothing —
    # which is the intended end state, not a reason to delete the split. Any
    # future dataset registered without a writer lands here instead of
    # corrupting the exit code.
    still = [r for r in behind_after if r.get("refresh")]
    orphaned = [r for r in behind_after if not r.get("refresh")]

    print("\n=== RESULT ===")
    for r in results:
        print(f"  {'✅' if r['ok'] else '❌'} {r['cmd']}  ({r['secs']/60:.1f} min)")
    # Never let a bounded run read as a complete one.
    for s in skipped:
        print(f"  ⏭  NOT ATTEMPTED (budget exhausted): {s['cmd']}  for {', '.join(s['for'])}")
    if still:
        print(f"\n  🔴 {len(still)} required dataset(s) STILL behind after refresh:")
        for r in still:
            print(f"     {r['id']} holds {r['session']}, expected {r['expected']}")
            print(f"       ran: {r['refresh']}")
    else:
        print("\n  ✅ every refreshable dataset now holds its expected session.")
    if orphaned:
        print(f"\n  ⚠️  {len(orphaned)} dataset(s) behind with NO refresher — nothing "
              f"here can fix these; retire them or give them a writer:")
        for r in orphaned:
            print(f"     {r['id']} holds {r['session']}, expected {r['expected']}")
            print(f"       {r['location']}")

    if a.json:
        print(json.dumps({"steps": steps, "results": results,
                          "skipped": [s["cmd"] for s in skipped],
                          "still_behind": [r["id"] for r in still],
                          "orphaned": [r["id"] for r in orphaned]},
                         indent=2, default=str))
    # `orphaned` is deliberately NOT a failure: it is a standing structural
    # problem, not an outcome of this run, and a run that did everything it
    # could should say so.
    return 1 if (still or skipped or any(not r["ok"] for r in results)) else 0


if __name__ == "__main__":
    sys.exit(main())
