# agents/pipeline_triage/agents.py
# ================================
# Coordinator → subagent topology for morning pipeline triage.
#
#                         ┌──────────────── coordinator ────────────────┐
#                         │ tools: investigate_* (×3) + submit_verdict  │
#                         └──────┬──────────────┬──────────────┬────────┘
#                                │ brief        │ brief        │ brief      (parallel)
#                         freshness        run_logs        send_gate
#                     data_index,         section_runs,    gate_state,
#                     registry_entry,     list/read_log    list/read_log
#                     list/read_log
#                                │ submit_finding (structured, or an error outcome)
#                                └──────────────► back to coordinator ──► submit_verdict
#
# Why this split and not one agent with every tool:
#   - CONTEXT ISOLATION. Each subagent starts from an empty history plus the
#     coordinator's brief, and reads logs/registry rows the coordinator never
#     sees. The coordinator receives one structured finding per area — a few
#     hundred tokens instead of the raw tool output.
#   - LEAST PRIVILEGE. Each subagent holds only the tools its question needs;
#     the coordinator holds none that touch data at all.
#   - INDEPENDENT FAILURE. A subagent that runs out of turns comes back as an
#     explicit is_error result ("treat as UNKNOWN"), so one broken investigation
#     degrades the verdict instead of silently passing as "nothing found".
#
# The deterministic gates (data_index --require, price_gate.py) stay the
# authority on SEND. This agent explains a failure and recommends; it cannot
# send, re-run, or overwrite anything.
from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from .loop import AgentSpec, RunResult, Tool, as_tool_result, run_agent
from .tools import FRESHNESS_TOOLS, GATE_TOOLS, RUNLOG_TOOLS, _schema

DEFAULT_MODEL = "claude-opus-5-5"

FINDING = Tool(
    "submit_finding",
    "Finish the investigation. Call exactly once, with what the evidence shows. If you could not "
    "establish something, use status 'inconclusive' and say what is missing — never guess.",
    _schema({
        "status": {"type": "string", "enum": ["ok", "degraded", "blocking", "inconclusive"]},
        "summary": {"type": "string", "description": "2-3 sentences"},
        "evidence": {"type": "array", "items": _schema({
            "source": {"type": "string", "description": "tool + dataset key / log name:line"},
            "observation": {"type": "string"}})},
        "suspected_root_causes": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    }))

VERDICT = Tool(
    "submit_verdict",
    "Finish triage with the final verdict. Call exactly once, after the investigations you need.",
    _schema({
        "verdict": {"type": "string", "enum": ["GO", "NO_GO", "NEEDS_HUMAN"],
                    "description": "GO = brief may be sent as-is; NO_GO = a blocking defect is evidenced; "
                                   "NEEDS_HUMAN = evidence conflicts or an area is unknown"},
        "headline": {"type": "string"},
        "root_causes": {"type": "array", "items": _schema({
            "cause": {"type": "string"}, "evidence": {"type": "string"},
            "owner_script": {"type": "string", "description": "script that should have produced it, or ''"}})},
        "recommended_actions": {"type": "array", "items": {"type": "string"}},
        "unverified": {"type": "array", "items": {"type": "string"},
                       "description": "areas whose investigation failed or was inconclusive"},
    }))

_SHARED = """You are a read-only investigator for a market-data pipeline that builds and emails a
morning stock brief. Sections: ingest (weekdays 00:15, EOD prices) -> mailer (00:30, scans + send
gate), plus weekly modelling/factor_tests. Freshness is judged by trading SESSION, not file mtime:
a file written today can still hold yesterday's prices, and weekends/holidays legitimately age data.
Cite the tool and the dataset key or log line for every claim. Report what the evidence shows; do not
speculate past it. Finish by calling submit_finding."""

SUBAGENTS: Dict[str, Dict[str, Any]] = {
    "freshness": {
        "tools": FRESHNESS_TOOLS,
        "system": _SHARED + """

Your area: DATA FRESHNESS. Start with data_index(section='all', only_problems=true). For each
non-OK dataset, decide whether it blocks the brief (an ingest dataset the mailer consumes) or is
advisory (modelling/factor_tests). Use registry_entry for the writer, consumers, and known-hazard note,
and the writer's log to see whether it ran and failed or never ran.""",
    },
    "run_logs": {
        "tools": RUNLOG_TOOLS,
        "system": _SHARED + """

Your area: RUN HISTORY. Use section_runs for ingest and mailer (history 3) to find runs that did
not complete, steps that are missing, or a step that got much slower than its own recent runs. Then
read_log with grep='error' / 'Traceback' / 'ALERT' on the failing run's log to name the failing step
and its error.""",
    },
    "send_gate": {
        "tools": GATE_TOOLS,
        "system": _SHARED + """

Your area: THE SEND GATE. gate_state tells you whether the last price_gate run blocked and why, and
when the last brief actually went out. Correlate with the mailer log's '[13/13]' and '[SEND]' lines
(read_log with grep). Establish: did today's brief send, was it blocked, and on what reason.""",
    },
}

COORDINATOR_SYSTEM = """You coordinate triage of this morning's market-brief pipeline run. You have no
data tools yourself: delegate to three investigators, each of which runs independently and returns a
structured finding — freshness (registered datasets vs allowed age), run_logs (did each section run
and finish), send_gate (did the brief send or get blocked, and why).

Write each brief as a self-contained instruction: the investigator sees only your brief, not this
conversation. Call the investigations you need in parallel in one turn. If findings conflict or
point at a specific step, you may send one follow-up investigation with a sharper brief.

An investigation that returns an error did NOT find the area healthy — list it under 'unverified'
and do not return GO while any area the send depends on is unverified. Prefer NEEDS_HUMAN over a
confident verdict the evidence does not support. Finish by calling submit_verdict."""


def subagent_spec(area: str, model: str) -> AgentSpec:
    cfg = SUBAGENTS[area]
    return AgentSpec(name=area, model=model, system=cfg["system"],
                     tools=cfg["tools"] + [FINDING], terminal=FINDING.name,
                     effort="low", max_turns=8)


def run_triage(client: Any, model: str = DEFAULT_MODEL, worker_model: Optional[str] = None,
               trace: Optional[Callable[[Dict[str, Any]], None]] = None,
               max_turns: int = 6) -> Dict[str, Any]:
    worker_model = worker_model or model
    subruns: list[RunResult] = []

    def delegate(area: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
        def fn(inp: Dict[str, Any]) -> Dict[str, Any]:
            try:
                r = run_agent(client, subagent_spec(area, worker_model), inp["brief"], trace)
            except Exception as e:          # a crashed subagent is an UNKNOWN area, same shape as any failure
                r = RunResult(agent=area, outcome="crashed", detail=f"{type(e).__name__}: {e}")
            subruns.append(r)
            return as_tool_result(r)
        return fn

    pool = ThreadPoolExecutor(max_workers=3)
    brief = _schema({"brief": {"type": "string", "description": "self-contained task for the investigator"}})
    tools = [Tool(f"investigate_{a}", f"Delegate the {a.replace('_', ' ')} investigation to a subagent.",
                  brief, _parallel(pool, delegate(a))) for a in SUBAGENTS] + [VERDICT]
    coord = AgentSpec(name="coordinator", model=model, system=COORDINATOR_SYSTEM, tools=tools,
                      terminal=VERDICT.name, effort="high", max_turns=max_turns)

    today = dt.datetime.now().strftime("%A %Y-%m-%d %H:%M")
    try:
        top = run_agent(client, coord, f"It is {today} local time. Triage this morning's pipeline run "
                                       "and decide whether the brief is fit to send.", trace)
    finally:
        pool.shutdown(wait=True)

    usage = {k: top.usage[k] + sum(r.usage[k] for r in subruns) for k in top.usage}
    report = {"outcome": top.outcome, "detail": top.detail, "verdict": top.payload,
              "investigations": [{"agent": r.agent, "outcome": r.outcome, "turns": r.turns,
                                  "finding": r.payload} for r in subruns],
              "usage": usage}
    if not top.ok:                     # the coordinator itself failed: never imply a verdict
        report["verdict"] = {"verdict": "NEEDS_HUMAN",
                             "headline": f"triage did not complete ({top.outcome}: {top.detail})",
                             "root_causes": [], "recommended_actions": [], "unverified": ["all"]}
    return report


def _parallel(pool: ThreadPoolExecutor, fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
    """Adapt a delegate to loop.Tool: submits to the pool and returns a lazy result the loop resolves.

    The loop calls tool fns one at a time, so to run sibling subagents concurrently each call is
    started here and joined by DelegateResult.resolve() in loop order.
    """
    def start(inp: Dict[str, Any]):
        return DelegateResult(pool.submit(fn, inp))
    return start


class DelegateResult:
    def __init__(self, future):
        self.future = future

    def resolve(self) -> Dict[str, Any]:
        return self.future.result()
