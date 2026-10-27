"""Stop conditions, error propagation and tool guards of agents/pipeline_triage.

Hermetic: every model turn comes from ScriptedClient; no API call, no key.
Only the path-guard and fit_json tests touch tools.py, and neither reads data.
"""
from __future__ import annotations

import json

import anthropic
import httpx
import pytest

from agents.pipeline_triage import agents, tools
from agents.pipeline_triage.loop import AgentSpec, Tool, run_agent
from agents.pipeline_triage.scripted import SCRIPTS, ScriptedClient, _reply, _use
from types import SimpleNamespace as NS

DONE = Tool("done", "finish", tools._schema({"x": {"type": "string"}}))


def _spec(extra=(), max_turns=4):
    return AgentSpec(name="t", model="m", system="test agent", tools=[*extra, DONE],
                     terminal="done", max_turns=max_turns)


def _client(fn):
    return ScriptedClient({"coordinator": fn})          # "test agent" system -> coordinator slot


def test_terminal_tool_is_the_only_success():
    r = run_agent(_client(lambda t, m: _reply([_use("done", {"x": "hi"})])), _spec(), "go")
    assert r.ok and r.payload == {"x": "hi"} and r.turns == 1


def test_prose_ending_gets_one_nudge_then_no_verdict():
    text = lambda t, m: _reply([NS(type="text", text="all good")], stop="end_turn")
    r = run_agent(_client(text), _spec(), "go")
    assert r.outcome == "no_verdict" and r.turns == 2


def test_max_turns_caps_a_looping_agent():
    echo = Tool("echo", "e", tools._schema({}), lambda _i: "again")
    r = run_agent(_client(lambda t, m: _reply([_use("echo", {})])), _spec([echo], max_turns=3), "go")
    assert r.outcome == "max_turns" and r.turns == 3 and r.payload is None


def test_refusal_and_truncation_stop_without_running_tools():
    ran = []
    side = Tool("side", "s", tools._schema({}), lambda _i: ran.append(1) or "x")
    for stop, outcome in (("refusal", "refusal"), ("max_tokens", "truncated")):
        r = run_agent(_client(lambda t, m: _reply([_use("side", {})], stop=stop)), _spec([side]), "go")
        assert r.outcome == outcome
    assert ran == []


def test_tool_exception_goes_back_as_is_error_result():
    def boom(_i):
        raise FileNotFoundError("no such log")
    seen = {}

    def script(turn, messages):
        if turn == 0:
            return _reply([_use("boom", {})])
        seen.update(messages[-1]["content"][0])
        return _reply([_use("done", {"x": "saw it"})])
    r = run_agent(_client(script), _spec([Tool("boom", "b", tools._schema({}), boom)]), "go")
    assert r.ok and seen["is_error"] is True and "no such log" in seen["content"]


def test_api_error_is_an_outcome_not_an_exception():
    def fail(t, m):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    assert run_agent(_client(fail), _spec(), "go").outcome == "api_error"


def _no_tools(monkeypatch):
    """Subagents keep their tool NAMES but never touch real data."""
    for area, cfg in agents.SUBAGENTS.items():
        monkeypatch.setitem(cfg, "tools", [])


def test_failed_subagent_forces_needs_human(monkeypatch):
    _no_tools(monkeypatch)
    ok = lambda t, m: _reply([_use("submit_finding", {"status": "ok", "summary": "fine", "evidence": [],
                                                      "suspected_root_causes": [], "confidence": "high"})])
    silent = lambda t, m: _reply([NS(type="text", text="looks fine to me")], stop="end_turn")
    client = ScriptedClient({**SCRIPTS, "freshness": ok, "send_gate": ok, "run_logs": silent})
    report = agents.run_triage(client)
    v = report["verdict"]
    assert v["verdict"] == "NEEDS_HUMAN" and v["unverified"] == ["run_logs"]
    assert {i["agent"]: i["outcome"] for i in report["investigations"]}["run_logs"] == "no_verdict"


def test_crashed_subagent_is_reported_not_raised(monkeypatch):
    _no_tools(monkeypatch)
    ok = lambda t, m: _reply([_use("submit_finding", {"status": "ok", "summary": "fine", "evidence": [],
                                                      "suspected_root_causes": [], "confidence": "high"})])

    def crash(t, m):
        raise RuntimeError("bug in subagent")
    client = ScriptedClient({**SCRIPTS, "freshness": crash, "send_gate": ok, "run_logs": ok})
    report = agents.run_triage(client)
    assert report["verdict"]["verdict"] == "NEEDS_HUMAN"
    assert report["verdict"]["unverified"] == ["freshness"]


def test_coordinator_failure_never_implies_a_verdict(monkeypatch):
    _no_tools(monkeypatch)
    rambling = lambda t, m: _reply([NS(type="text", text="GO, probably")], stop="end_turn")
    report = agents.run_triage(ScriptedClient({**SCRIPTS, "coordinator": rambling}))
    assert report["outcome"] == "no_verdict" and report["verdict"]["verdict"] == "NEEDS_HUMAN"


@pytest.mark.parametrize("name", ["../state/last_brief_sent.json", "/etc/passwd", "..", "a/b.log", ""])
def test_read_log_refuses_paths(name):
    with pytest.raises(ValueError):
        tools.read_log({"name": name, "grep": "", "tail_lines": 5})


def test_fit_json_drops_whole_items_and_stays_valid():
    out = json.loads(tools.fit_json({"rows": [{"v": "x" * 100} for _ in range(50)]}, "rows", limit=1000))
    assert out["omitted"] > 0 and len(out["rows"]) + out["omitted"] == 50


def test_every_tool_schema_is_strict_compatible():
    every = tools.FRESHNESS_TOOLS + tools.RUNLOG_TOOLS + tools.GATE_TOOLS + [agents.FINDING, agents.VERDICT]

    def check(s):
        if s.get("type") == "object":
            assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
            for p in s["properties"].values():
                check(p)
        if s.get("type") == "array":
            check(s["items"])
    for t in every:
        check(t.input_schema)
