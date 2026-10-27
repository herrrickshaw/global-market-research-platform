# agents/pipeline_triage/scripted.py
# ==================================
# A stand-in for anthropic.Anthropic used by --dry-run and the tests. It plays
# each agent's part with fixed, mechanical rules, so the whole topology —
# coordinator fan-out, real read-only tools, subagent loops, error propagation,
# terminal tools — runs end to end with no API key and no spend. Its verdicts
# are rule-of-thumb, not judgement; only the live model triages.
#
# Turn number is derived from the history (count of assistant messages), so the
# client is stateless and safe to share across the coordinator's threads.
from __future__ import annotations

import itertools
import json
from types import SimpleNamespace as NS
from typing import Any, Callable, Dict, List

_ids = itertools.count(1)


def _use(name: str, inp: Dict[str, Any]) -> NS:
    return NS(type="tool_use", id=f"toolu_{next(_ids)}", name=name, input=inp)


def _reply(blocks: List[NS], stop: str = "tool_use") -> NS:
    return NS(content=blocks, stop_reason=stop, stop_details=None,
              usage=NS(input_tokens=0, output_tokens=0, cache_read_input_tokens=0))


def _last_results(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    last = messages[-1]["content"]
    return last if isinstance(last, list) else []


def _agent_of(system: str) -> str:
    for area, marker in (("freshness", "DATA FRESHNESS"), ("run_logs", "RUN HISTORY"),
                         ("send_gate", "THE SEND GATE")):
        if marker in system:
            return area
    return "coordinator"


# ── per-agent scripts: (turn, history) -> response ───────────────────────────
def _freshness(turn: int, messages) -> NS:
    if turn == 0:
        return _reply([_use("data_index", {"section": "all", "only_problems": True})])
    rows = json.loads(_last_results(messages)[0]["content"])["datasets"]
    blocking = [r for r in rows if r["section"] == "ingest"]
    return _reply([_use("submit_finding", {
        "status": "blocking" if blocking else ("degraded" if rows else "ok"),
        "summary": f"{len(rows)} dataset(s) not OK; {len(blocking)} in ingest.",
        "evidence": [{"source": f"data_index:{r['key']}", "observation": f"{r['status']} {r['detail']}"}
                     for r in rows[:8]],
        "suspected_root_causes": sorted({f"{r['writer']} did not refresh" for r in blocking}),
        "confidence": "medium"})])


def _run_logs(turn: int, messages) -> NS:
    if turn == 0:
        return _reply([_use("section_runs", {"section": s, "history": 3}) for s in ("ingest", "mailer")])
    obs, broken = [], []
    for res in _last_results(messages):
        body = json.loads(res["content"])
        if not body["runs"]:
            obs.append({"source": f"section_runs:{body['section']}", "observation": "no runs logged"})
        for r in body["runs"]:
            obs.append({"source": f"section_runs:{r['log']}", "observation": f"complete={r['complete']}"})
            if not r["complete"]:
                broken.append(r["log"])
    return _reply([_use("submit_finding", {
        "status": "degraded" if broken else "ok",
        "summary": f"{len(broken)} incomplete run(s) in the last 3 per section.",
        "evidence": obs, "suspected_root_causes": [f"{b} never reached __end__" for b in broken],
        "confidence": "medium"})])


def _send_gate(turn: int, messages) -> NS:
    if turn == 0:
        return _reply([_use("gate_state", {})])
    state = json.loads(_last_results(messages)[0]["content"])
    reason = state["price_gate_reason.txt"]
    blocked = bool(reason.get("content", "").strip())
    return _reply([_use("submit_finding", {
        "status": "blocking" if blocked else "ok",
        "summary": ("last gate run blocked: " + reason["content"][:150]) if blocked
                   else "last gate run passed (reason file empty).",
        "evidence": [{"source": f"gate_state:{k}", "observation": json.dumps(v)[:200]}
                     for k, v in state.items() if not k.startswith("_")],
        "suspected_root_causes": [], "confidence": "medium"})])


def _coordinator(turn: int, messages) -> NS:
    if turn == 0:
        return _reply([_use(f"investigate_{a}", {"brief": f"Investigate {a} for this morning's run."})
                       for a in ("freshness", "run_logs", "send_gate")])
    results = _last_results(messages)
    unverified, statuses = [], []
    for r in results:
        body = json.loads(r["content"])
        if r.get("is_error"):
            unverified.append(body["agent"])
        else:
            statuses.append(body["finding"]["status"])
    verdict = ("NEEDS_HUMAN" if unverified or "inconclusive" in statuses
               else "NO_GO" if "blocking" in statuses else "GO")
    return _reply([_use("submit_verdict", {
        "verdict": verdict, "headline": f"[dry-run rules] areas: {statuses}",
        "root_causes": [], "recommended_actions": ["run live (without --dry-run) for a reasoned triage"],
        "unverified": unverified})])


SCRIPTS: Dict[str, Callable[[int, list], NS]] = {
    "coordinator": _coordinator, "freshness": _freshness, "run_logs": _run_logs, "send_gate": _send_gate}


class ScriptedClient:
    def __init__(self, scripts: Dict[str, Callable[[int, list], NS]]):
        self.scripts = scripts
        self.beta = NS(messages=NS(create=self._create))
        self.calls: List[str] = []

    @classmethod
    def demo(cls) -> "ScriptedClient":
        return cls(dict(SCRIPTS))

    def _create(self, *, system: str, messages: list, **_kw) -> NS:
        agent = _agent_of(system)
        self.calls.append(agent)
        turn = sum(1 for m in messages if m["role"] == "assistant")
        return self.scripts[agent](turn, messages)
