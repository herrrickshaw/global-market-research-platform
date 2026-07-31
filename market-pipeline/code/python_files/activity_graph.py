#!/usr/bin/env python3
"""
activity_graph.py — a LangGraph summary of what actually ran overnight, and
what the mailer needs done about it.

WHY THIS EXISTS. The nightly work is no longer one job. As of 2026-07-29 there
are five independent schedulers writing to the same tree:

    com.umashankar.ingest          00:20  ingest_pipeline_<date>.log
    com.umashankar.dailybrief      00:30  daily_pipeline_<date>.log
    com.market-research.daily-collection  03:11/08:00  logs/collection_*.log
    com.umashankar.basebrief       06:35  market-brief-base/run.log
    n8n "Watchlist Digest"         07:00  n8n_out.log

Reading them one at a time is how 2026-07-29 was initially misread as "the
pipeline did not run": the 00:30 job had in fact fired on time and exited on its
single-run lock, while THREE other jobs ran to completion and one of them
rebuilt brief_today.html at 03:36. No single log contains that story.

WHAT THIS ANSWERS. Two questions, which is why it is a graph and not a script:

  ACTIVITY   — for every scheduler, did it fire, when, how long, what failed?
               One run block per invocation; a single log file routinely holds
               several (2026-07-28 held three, two of them manual).

  MAILER     — the send is gated by [13b] validate_brief.py, which suppresses on
               EITHER a screener.in mismatch OR a price-reconcile failure. Those
               are different faults with different fixes and the log line for
               them reads almost identically, so they are separated here and
               each becomes its own task with its own severity.

WHY LANGGRAPH. `activity`, `gates` and `outputs` are three independent reads
over the same discovered run inventory; they fan out in parallel and join at
`synthesize`, which is the only node that ranks. Same shape and same reasoning
as completeness_graph.py: the nodes are deterministic Python, there is no LLM in
this graph and no reason for one. Every line below is parsed, not generated.

🔴 THIS SUMMARISES LOGS, NOT CORRECTNESS. A step that reports success is
recorded as success. The reconcile and validation results are read as the
pipeline stated them — this graph does not re-price anything.

Usage:
  python3 activity_graph.py
  python3 activity_graph.py --json
  python3 activity_graph.py --date 20260728
"""
from __future__ import annotations

import argparse
import json
import operator
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, TypedDict

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
OUT_MD = REPORTS / "activity_graph.md"

COLLECT_LOGS = Path("/Users/umashankar/market-pipeline/logs")
BASEBRIEF = Path("/Users/umashankar/market-brief-base/run.log")
N8N_LOG = HERE / "n8n_out.log"
BRIEF = HERE / "brief_today.html"
CORR = HERE / "correlation_scan"

# Genuine failures. Deliberately does NOT include yfinance rate-limit chatter,
# "possibly delisted; no price data found", or urllib3 NotOpenSSLWarning — those
# are daily background noise and matching them buries the real faults.
FAIL_PAT = re.compile(
    r"failed \(continuing\)|scan failed|ModuleNotFoundError|Traceback"
    r"|Operation not permitted|MISSING REQUIRED|cqlsh not found"
    r"|not configured|\bFAIL\b"
)
RUN_HDR = re.compile(r"^=== (Daily pipeline|done)\b(.*)$")
STEP = re.compile(r"^\[(\d+[a-z]?)/(\d+)\]\s+(.*)$")
ALERT = re.compile(r"^\[ALERT\] (\d+) step\(s\) failed[^:]*:\s*(.*)$")
SENT = re.compile(r"sent '([^']*)'")
SUPPRESS = re.compile(r"send SUPPRESSED|sending SUPPRESSED")
RECON_FAIL = re.compile(
    r"\[(\w+)\]\s+(\S+\.xlsx):\s+(\d+) checked · FAIL — (\d+)/(\d+) stale \(worst (\S+) ([\d.]+)%\)"
)
MODNOTFOUND = re.compile(r"ModuleNotFoundError: No module named '([^']+)'")


class ActivityState(TypedDict):
    runs: Annotated[list, operator.add]
    steps: Annotated[list, operator.add]
    gates: Annotated[list, operator.add]
    outputs: Annotated[list, operator.add]
    tasks: Annotated[list, operator.add]
    notes: Annotated[list, operator.add]
    summary: str


def _read(p: Path) -> list[str]:
    try:
        return p.read_text(errors="replace").splitlines()
    except OSError:
        return []


def _mtime(p: Path):
    try:
        return datetime.fromtimestamp(p.stat().st_mtime)
    except OSError:
        return None


def _split_runs(lines: list[str]) -> list[dict]:
    """One log file holds N invocations. Split on the banner, not on the file."""
    runs, cur = [], None
    for i, ln in enumerate(lines):
        m = RUN_HDR.match(ln.strip())
        if m and m.group(1) == "Daily pipeline":
            if cur:
                runs.append(cur)
            cur = {"start": m.group(2).strip().rstrip("="), "lines": [], "end": None}
        elif m and m.group(1) == "done" and cur:
            cur["end"] = m.group(2).strip().rstrip("=")
        if cur is not None:
            cur["lines"].append(ln)
    if cur:
        runs.append(cur)
    return runs


# ── nodes ────────────────────────────────────────────────────────────────────

def discover(state: ActivityState, tag: str) -> dict:
    """Find every scheduler's most recent run. Shared inventory for the fan-out."""
    runs, notes = [], []

    dp = HERE / f"daily_pipeline_{tag}.log"
    if dp.exists():
        blocks = _split_runs(_read(dp))
        for n, b in enumerate(blocks, 1):
            runs.append({
                "job": "dailybrief", "label": f"daily_pipeline #{n}",
                "log": str(dp), "start": b["start"], "end": b["end"],
                "lines": b["lines"], "complete": b["end"] is not None,
            })
    else:
        # The single most important finding the 00:30 job can produce.
        notes.append(f"NO daily_pipeline_{tag}.log — the 00:30 scheduled run "
                     f"produced no log for {tag}")

    ing = HERE / f"ingest_pipeline_{tag}.log"
    if ing.exists():
        ln = _read(ing)
        end = next((x for x in reversed(ln) if x.startswith("=== done ingest")), None)
        runs.append({"job": "ingest", "label": "ingest_pipeline", "log": str(ing),
                     "start": None, "end": end, "lines": ln,
                     "complete": end is not None})
    else:
        notes.append(f"no ingest_pipeline_{tag}.log")

    if COLLECT_LOGS.is_dir():
        cl = sorted(COLLECT_LOGS.glob(f"collection_{tag[:4]}-{tag[4:6]}-{tag[6:]}_*.log"))
        for c in cl:
            runs.append({"job": "collection", "label": c.stem, "log": str(c),
                         "start": None, "end": None, "lines": _read(c),
                         "complete": True})
        if not cl:
            notes.append("no collection_*.log for this date")

    if BASEBRIEF.exists():
        mt = _mtime(BASEBRIEF)
        if mt and mt.date().strftime("%Y%m%d") == tag:
            runs.append({"job": "basebrief", "label": "market-brief-base",
                         "log": str(BASEBRIEF), "start": None, "end": None,
                         "lines": _read(BASEBRIEF)[-40:], "complete": True})
        else:
            notes.append(f"basebrief run.log last written {mt} — not {tag}")

    return {"runs": runs, "notes": notes}


def activity(state: ActivityState) -> dict:
    """Per-run: steps reached, genuine failures, alert trailer."""
    out = []
    for r in state["runs"]:
        lines = r["lines"]
        steps = [STEP.match(x.strip()) for x in lines]
        steps = [m.group(0) for m in steps if m]
        fails = sorted({x.strip() for x in lines if FAIL_PAT.search(x)})
        mods = sorted({m.group(1) for x in lines for m in [MODNOTFOUND.search(x)] if m})
        alert = next((ALERT.match(x.strip()) for x in reversed(lines)
                      if ALERT.match(x.strip())), None)
        out.append({
            "job": r["job"], "label": r["label"],
            "start": r["start"], "end": r["end"], "complete": r["complete"],
            "n_steps": len(steps), "last_step": steps[-1] if steps else None,
            "n_fail_lines": len(fails),
            "fails": fails[:12],
            "missing_modules": mods,
            "alert_count": int(alert.group(1)) if alert else 0,
            "alert_detail": alert.group(2).strip() if alert else None,
        })
    return {"steps": out}


def gates(state: ActivityState) -> dict:
    """The mailer gate: screener.in validation vs price reconcile. Different faults."""
    out = []
    for r in state["runs"]:
        if r["job"] not in ("dailybrief", "ingest"):
            continue
        lines = r["lines"]
        recon = [RECON_FAIL.search(x) for x in lines]
        recon = [{"market": m.group(1), "workbook": m.group(2),
                  "checked": int(m.group(3)), "stale": int(m.group(4)),
                  "of": int(m.group(5)), "worst_sym": m.group(6),
                  "worst_pct": float(m.group(7))}
                 for m in recon if m]
        validated = any("✓ validated" in x for x in lines)
        suppressed = next((x.strip() for x in lines if SUPPRESS.search(x)), None)
        sent = [SENT.search(x).group(1) for x in lines if SENT.search(x)]
        draft = any("draft saved" in x for x in lines)
        if not (recon or suppressed or sent or draft):
            continue
        # The reason string names the ACTUAL blocker; keep it verbatim.
        reason = None
        if suppressed:
            reason = suppressed.split("—", 1)[1].strip() if "—" in suppressed else suppressed
        out.append({
            "job": r["job"], "label": r["label"],
            "screener_validated": validated,
            "suppressed": suppressed is not None,
            "reason": reason,
            "reconcile_failures": recon,
            "sent_subjects": sent,
            "draft_saved": draft,
        })
    return {"gates": out}


def outputs(state: ActivityState) -> dict:
    """Artefacts the brief depends on: is each one actually from today?"""
    out = []
    today = date.today()

    mt = _mtime(BRIEF)
    out.append({"artefact": "brief_today.html",
                "mtime": str(mt) if mt else None,
                "fresh": bool(mt and mt.date() == today),
                "detail": f"{BRIEF.stat().st_size:,} bytes" if BRIEF.exists() else "absent"})

    if CORR.is_dir():
        for kind, pat in (("clusters", "*_correlation_clusters.txt"),
                          ("matrix", "*_correlation_matrix.csv*")):
            fs = sorted(CORR.glob(pat), key=lambda p: p.stat().st_mtime)
            newest = _mtime(fs[-1]) if fs else None
            out.append({"artefact": f"correlation {kind}",
                        "mtime": str(newest) if newest else None,
                        "fresh": bool(newest and (today - newest.date()).days <= 1),
                        "detail": f"{len(fs)} file(s)"
                                  + (f", newest {fs[-1].name}" if fs else " — NEVER PRODUCED")})

    # n8n reactivation is a send-path risk, not an output, but this is where the
    # send path is observable without touching n8n itself.
    for ln in reversed(_read(N8N_LOG)):
        if "Activated workflow" in ln and "Watchlist Digest" in ln:
            out.append({"artefact": "n8n Watchlist Digest 07:00",
                        "mtime": str(_mtime(N8N_LOG)), "fresh": True,
                        "detail": "ACTIVE — " + ln.strip()[:90]})
            break

    return {"outputs": out}


def synthesize(state: ActivityState) -> dict:
    """Rank everything into mailer tasks. The only node that decides priority."""
    tasks = []

    def add(sev, title, why, fix):
        tasks.append({"severity": sev, "title": title, "why": why, "fix": fix})

    for n in state["notes"]:
        if n.startswith("NO daily_pipeline"):
            add("BLOCKER", "Scheduled 00:30 run produced no log", n,
                "Check launchd_out.log for the single-run lock message and "
                "whether /tmp/daily_pipeline.lock is held by a live pid.")

    for g in state["gates"]:
        if g["suppressed"]:
            if g["screener_validated"]:
                add("HIGH", "Mailer send suppressed — validation PASSED",
                    f"{g['label']}: {g['reason']}",
                    "Fix the reconcile inputs; the screener.in check is not the "
                    "blocker and re-running validation will not clear it.")
            else:
                add("BLOCKER", "Mailer send suppressed — screener.in MISMATCH",
                    f"{g['label']}: {g['reason']}",
                    "Do not send. Reconcile the quoted prices against screener.in "
                    "before any manual re-send.")
        for rf in g["reconcile_failures"]:
            whole = rf["stale"] == rf["of"]
            add("HIGH" if whole else "MEDIUM",
                f"Price reconcile FAIL — {rf['market']} "
                f"({rf['stale']}/{rf['of']} stale)",
                f"worst {rf['worst_sym']} {rf['worst_pct']:.1f}% vs fresh quote"
                + (" — whole sample stale, not intraday drift" if whole else ""),
                "Whole-sample staleness points at the scan's price source "
                "(split/adjustment), not at individual names."
                if whole else "Spot-check the flagged names against the exchange close.")

    for s in state["steps"]:
        for mod in s["missing_modules"]:
            add("HIGH", f"Missing dependency: {mod}",
                f"{s['label']} hit ModuleNotFoundError for '{mod}'; every step is "
                f"guarded with '|| failed (continuing)' so this fails SILENTLY",
                f"Add {mod} to requirements.txt AND to check_deps.py so [0/14] "
                f"fails loudly instead of degrading.")
        if s["alert_count"]:
            add("MEDIUM", f"{s['label']}: {s['alert_count']} step(s) failed",
                s["alert_detail"] or "", "Triage each named step.")
        if not s["complete"] and s["job"] == "dailybrief":
            add("BLOCKER", f"{s['label']} never reached its done trailer",
                f"last step: {s['last_step']}",
                "A run still holding the lock blocks the next scheduled run.")

    for o in state["outputs"]:
        if o["artefact"] == "brief_today.html" and not o["fresh"]:
            add("BLOCKER", "brief_today.html is not from today",
                f"mtime {o['mtime']}",
                "The mailer would ship a stale brief. Do not send.")
        if "NEVER PRODUCED" in str(o["detail"]):
            add("MEDIUM", f"{o['artefact']} has never produced output",
                str(o["detail"]), "Confirm the dependency chain for that step.")
        if o["artefact"].startswith("n8n"):
            add("HIGH", "n8n 07:00 Watchlist Digest is ACTIVE",
                o["detail"],
                "This workflow was deactivated to stop double-sends. Confirm it "
                "is not sending alongside the pipeline mailer.")

    for r in state["runs"]:
        if r["job"] == "basebrief":
            if any("not configured" in x for x in r["lines"]):
                add("LOW", "basebrief cannot send (SMTP unset)",
                    "run.log: email: not configured (SMTP_USER, SMTP_PASS, SMTP_TO)",
                    "Either configure SMTP or drop --email from the plist so the "
                    "job stops reporting a send it never attempts.")
        if r["job"] == "collection":
            if any("cqlsh not found" in x for x in r["lines"]):
                add("LOW", "collection job cannot load Cassandra",
                    "cqlsh not found — the EDGAR→Cassandra load step is a no-op",
                    "brew install cassandra, or route the load through docker exec.")

    rank = {"BLOCKER": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    tasks.sort(key=lambda t: rank[t["severity"]])
    # Same fault seen in several run blocks is one task.
    seen, uniq = set(), []
    for t in tasks:
        k = (t["severity"], t["title"])
        if k not in seen:
            seen.add(k)
            uniq.append(t)

    n_run = len({r["label"] for r in state["runs"]})
    n_block = sum(1 for t in uniq if t["severity"] == "BLOCKER")
    summary = (f"{n_run} run(s) across {len({r['job'] for r in state['runs']})} scheduler(s); "
               f"{len(uniq)} task(s), {n_block} blocker(s)")
    return {"tasks": uniq, "summary": summary}


def build(tag: str):
    from langgraph.graph import END, START, StateGraph
    g = StateGraph(ActivityState)
    g.add_node("discover", lambda s: discover(s, tag))
    g.add_node("activity", activity)
    g.add_node("gates", gates)
    g.add_node("outputs", outputs)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "discover")
    # fan out — three independent reads of the same inventory
    g.add_edge("discover", "activity")
    g.add_edge("discover", "gates")
    g.add_edge("discover", "outputs")
    # join
    g.add_edge("activity", "synthesize")
    g.add_edge("gates", "synthesize")
    g.add_edge("outputs", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


def render(s: ActivityState, tag: str) -> str:
    L = [f"# Overnight activity — {tag}", "", s["summary"], ""]

    L += ["## Runs", "", "| job | run | complete | steps | fail lines | alert |",
          "|---|---|---|---|---|---|"]
    for st in s["steps"]:
        L.append(f"| {st['job']} | {st['label']} | "
                 f"{'yes' if st['complete'] else '**NO**'} | {st['n_steps']} | "
                 f"{st['n_fail_lines']} | {st['alert_count'] or '—'} |")
    L.append("")

    if s["gates"]:
        L += ["## Mailer gate", ""]
        for g in s["gates"]:
            L.append(f"**{g['label']}** — screener.in validated: "
                     f"{'yes' if g['screener_validated'] else 'NO'} · "
                     f"suppressed: {'yes' if g['suppressed'] else 'no'} · "
                     f"draft: {'yes' if g['draft_saved'] else 'no'}")
            if g["reason"]:
                L.append(f"  - blocker: {g['reason']}")
            for rf in g["reconcile_failures"]:
                L.append(f"  - [{rf['market']}] {rf['stale']}/{rf['of']} stale, "
                         f"worst {rf['worst_sym']} {rf['worst_pct']:.1f}%")
            for sub in g["sent_subjects"]:
                L.append(f"  - sent: {sub}")
            L.append("")

    L += ["## Outputs", "", "| artefact | fresh | mtime | detail |", "|---|---|---|---|"]
    for o in s["outputs"]:
        L.append(f"| {o['artefact']} | {'yes' if o['fresh'] else '**no**'} | "
                 f"{o['mtime']} | {o['detail']} |")
    L.append("")

    L += ["## Key tasks for the mailer", ""]
    if not s["tasks"]:
        L.append("None — nothing blocking the send.")
    for i, t in enumerate(s["tasks"], 1):
        L += [f"{i}. **[{t['severity']}] {t['title']}**",
              f"   - why: {t['why']}",
              f"   - fix: {t['fix']}"]
    L.append("")

    if s["notes"]:
        L += ["## Notes", ""] + [f"- {n}" for n in s["notes"]] + [""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--date", default=date.today().strftime("%Y%m%d"),
                    help="YYYYMMDD (default today)")
    a = ap.parse_args()

    app = build(a.date)
    s = app.invoke({"runs": [], "steps": [], "gates": [], "outputs": [],
                    "tasks": [], "notes": [], "summary": ""})
    if a.json:
        for r in s["runs"]:
            r.pop("lines", None)
        print(json.dumps(s, indent=2, default=str))
        return 0
    md = render(s, a.date)
    print(md)
    REPORTS.mkdir(exist_ok=True)
    OUT_MD.write_text(md)
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
