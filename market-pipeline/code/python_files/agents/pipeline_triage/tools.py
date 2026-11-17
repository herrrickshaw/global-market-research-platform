# agents/pipeline_triage/tools.py
# ===============================
# The read-only tools the triage subagents may call. Three rules, all enforced
# here rather than trusted to a prompt:
#
#   1. READ-ONLY. Nothing here sends, writes state/, or runs a pipeline step.
#      price_gate.py in particular is NOT exposed: it rewrites
#      state/price_gate_reason.txt, which mailer.sh reads to name the blocker.
#      The gate agent reads that file instead of re-running the gate.
#   2. NO PATHS FROM THE MODEL. Logs are addressed by bare file name and resolved
#      inside LOG_DIRS only; anything with a separator or "..", or that resolves
#      outside those dirs, is refused.
#   3. SMALL OUTPUTS. run_monitor --json is ~135 KB and data_index --json ~18 KB.
#      Each tool returns the slice a question needs, and every string is
#      clipped with a marker telling the agent to narrow the query — tool output
#      is the main thing that eats a subagent's context.
from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from .loop import Tool

HERE = Path(__file__).resolve().parents[2]            # code/python_files
LOG_DIRS = [HERE, HERE / "logs", HERE.parents[1] / "logs"]
STATE = HERE / "state"
SECTIONS = ["ingest", "mailer", "modelling", "factor_tests"]
MAX_CHARS = 6000


def clip(text: str, limit: int = MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n[clipped {len(text) - limit} chars — narrow the query (grep / fewer lines)]"


def fit_json(obj: Dict[str, Any], list_key: str, limit: int = MAX_CHARS) -> str:
    """Serialise obj, dropping trailing items of obj[list_key] until it fits.

    JSON tools shrink by whole items instead of clip(): a half-cut string is
    unparseable, and an agent reading it cannot tell which fields were lost.
    """
    items = list(obj[list_key])
    total = len(items)
    while True:
        text = json.dumps({**obj, list_key: items, "omitted": total - len(items)}, default=str)
        if len(text) <= limit or not items:
            return text
        items.pop()


def _schema(props: Dict[str, Any]) -> Dict[str, Any]:
    # strict tools: every property required, no extras
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def _age(p: Path) -> str:
    return f"{(time.time() - p.stat().st_mtime) / 3600:.1f}h ago"


# ── freshness ────────────────────────────────────────────────────────────────
_KEEP = ("key", "status", "age_days", "detail", "section", "writer", "cadence", "max_age_days")


def _data_index() -> List[Dict[str, Any]]:
    out = subprocess.run([sys.executable, str(HERE / "data_index.py"), "--json"],
                         capture_output=True, text=True, timeout=120, cwd=HERE)
    if not out.stdout.strip():
        raise RuntimeError(f"data_index.py produced no JSON (exit {out.returncode}): {out.stderr[-500:]}")
    return json.loads(out.stdout)


def data_index(inp: Dict[str, Any]) -> str:
    rows = _data_index()
    if inp["section"] != "all":
        rows = [r for r in rows if r.get("section") == inp["section"]]
    if inp["only_problems"]:
        rows = [r for r in rows if r.get("status") != "OK"]
    slim = [{k: (round(r[k], 2) if isinstance(r.get(k), float) else r.get(k)) for k in _KEEP} for r in rows]
    return fit_json({"count": len(slim), "datasets": slim}, "datasets")


def registry_entry(inp: Dict[str, Any]) -> str:
    for r in _data_index():
        if r.get("key") == inp["key"]:
            return json.dumps(r, default=str)             # one registry row is always small
    raise KeyError(f"no dataset {inp['key']!r} in data_registry")


# ── run logs ─────────────────────────────────────────────────────────────────
def section_runs(inp: Dict[str, Any]) -> str:
    sys.path.insert(0, str(HERE))
    import run_monitor                                   # parse() only; no side effects
    logs = [p for p in run_monitor._logs() if p.name.startswith(inp["section"] + "_pipeline_")]
    n = max(1, min(int(inp["history"]), 5))
    logs.sort(key=lambda p: p.name)                       # name carries the date; dirs differ
    runs = [r for r in (run_monitor.parse(p) for p in logs[-n:]) if r]
    runs.reverse()                                        # newest first, so fit_json drops the oldest
    for r in runs:
        r["steps"] = [{"label": s["label"], "dur_s": s["dur"]} for s in r["steps"]]
    note = "" if runs else "no [STEP]-marked logs for this section"
    return fit_json({"section": inp["section"], "note": note, "runs": runs}, "runs")


def _resolve_log(name: str) -> Path:
    if not name or "/" in name or "\\" in name or ".." in name:
        raise ValueError("pass a bare log file name from list_logs, not a path")
    for d in LOG_DIRS:
        p = (d / name).resolve()
        if p.parent == d.resolve() and p.is_file():
            return p
    raise FileNotFoundError(f"{name!r} not found in the log directories")


def list_logs(inp: Dict[str, Any]) -> str:
    pat = inp["pattern"]
    if "/" in pat or ".." in pat:
        raise ValueError("pattern is a file-name glob, e.g. 'mailer_pipeline_*.log'")
    hits = []
    for d in LOG_DIRS:
        if d.is_dir():
            hits += [p for p in d.iterdir() if p.is_file() and p.suffix in (".log", ".jsonl", ".txt")
                     and fnmatch.fnmatch(p.name, pat)]
    hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return json.dumps([{"name": p.name, "modified": _age(p), "bytes": p.stat().st_size} for p in hits[:25]])


def read_log(inp: Dict[str, Any]) -> str:
    p = _resolve_log(inp["name"])
    lines = p.read_text(errors="replace").splitlines()
    if inp["grep"]:
        needle = inp["grep"].lower()
        lines = [f"{i + 1}: {l}" for i, l in enumerate(lines) if needle in l.lower()]
    n = max(1, min(int(inp["tail_lines"]), 200))
    return clip(f"{p.name} (modified {_age(p)}, {len(lines)} matching lines, showing last {n})\n"
                + "\n".join(lines[-n:]))


# ── send gate ────────────────────────────────────────────────────────────────
def gate_state(_inp: Dict[str, Any]) -> str:
    out = {}
    for name in ("price_gate_reason.txt", "last_brief_sent.json"):
        p = STATE / name
        if p.is_file():
            out[name] = {"modified": _age(p), "bytes": p.stat().st_size,
                         "content": clip(p.read_text(errors="replace"), 2000)}
        else:
            out[name] = {"missing": True}
    out["_meaning"] = ("price_gate_reason.txt is EMPTY when the last gate run passed and holds the "
                       "blocker text when it failed; last_brief_sent.json records the last real send.")
    return json.dumps(out)


# ── tool objects, grouped by the subagent allowed to use them ────────────────
LIST_LOGS = Tool("list_logs", "List pipeline log files (newest first, max 25) whose NAME matches a glob, "
                 "e.g. 'mailer_pipeline_*.log', '*error*'. Returns name, age, size.",
                 _schema({"pattern": {"type": "string", "description": "file-name glob"}}), list_logs)
READ_LOG = Tool("read_log", "Read the tail of one log file by its bare name (from list_logs). "
                "Set grep to a case-insensitive substring to keep only matching lines (with line numbers), "
                "or '' for all lines. tail_lines is capped at 200.",
                _schema({"name": {"type": "string"}, "grep": {"type": "string"},
                         "tail_lines": {"type": "integer"}}), read_log)

FRESHNESS_TOOLS = [
    Tool("data_index", "Freshness of every registered dataset (data_registry.py): status OK/STALE/MISSING, "
         "age in days vs allowed max age, the writer script and its cadence. section='all' or one section; "
         "only_problems=true hides OK rows.",
         _schema({"section": {"type": "string", "enum": ["all"] + SECTIONS},
                  "only_problems": {"type": "boolean"}}), data_index),
    Tool("registry_entry", "The full registry row for one dataset key: path, note (known hazards), consumers.",
         _schema({"key": {"type": "string"}}), registry_entry),
    LIST_LOGS, READ_LOG,
]
RUNLOG_TOOLS = [
    Tool("section_runs", "Step-by-step durations of the last N runs of a pipeline section, parsed from its "
         "[STEP] markers. complete=false means the run never reached its __end__ marker (it died or is "
         "still running); dur_s=null is the step it was in.",
         _schema({"section": {"type": "string", "enum": SECTIONS},
                  "history": {"type": "integer", "description": "1-5"}}), section_runs),
    LIST_LOGS, READ_LOG,
]
GATE_TOOLS = [
    Tool("gate_state", "Current send-gate state files: price_gate_reason.txt and last_brief_sent.json, "
         "with their ages.", _schema({}), gate_state),
    LIST_LOGS, READ_LOG,
]
