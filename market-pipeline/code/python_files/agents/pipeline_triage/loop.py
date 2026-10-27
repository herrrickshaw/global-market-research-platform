# agents/pipeline_triage/loop.py
# ==============================
# The one agent loop every agent in this package runs — coordinator and
# subagents alike. Written by hand rather than with the SDK's tool runner
# because the stop conditions are the point of this module, and they need to
# be explicit and testable:
#
#   STOP 1  the agent calls its TERMINAL tool (submit_finding / submit_verdict).
#           That is the only "success". Ending the turn with prose is not.
#   STOP 2  max_turns reached          -> outcome "max_turns"
#   STOP 3  stop_reason == "refusal"   -> outcome "refusal"
#   STOP 4  stop_reason == "max_tokens" -> outcome "truncated" (a cut-off
#           tool_use block must never be executed)
#   STOP 5  the agent ends its turn without the terminal tool TWICE (one nudge
#           allowed)                   -> outcome "no_verdict"
#   STOP 6  the API itself fails after the SDK's own retries -> "api_error"
#
# Every non-success outcome is returned as data, never raised, so the caller
# (the coordinator) can tell "the investigation found nothing wrong" apart from
# "the investigation never finished". Treating the second as the first is the
# error-propagation bug this whole package exists to avoid.
#
# The history is append-only: response.content goes back verbatim (thinking
# blocks included) and nothing earlier is edited — required for preserved
# thinking on the current models.
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import anthropic

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    fn: Optional[Callable[[Dict[str, Any]], str]] = None   # None = terminal tool

    def schema(self) -> Dict[str, Any]:
        return {"name": self.name, "description": self.description,
                "input_schema": self.input_schema, "strict": True}


@dataclass
class AgentSpec:
    name: str
    model: str
    system: str
    tools: List[Tool]
    terminal: str                    # name of the tool that ends the run
    effort: str = "medium"
    max_turns: int = 8
    max_tokens: int = 16000


@dataclass
class RunResult:
    agent: str
    outcome: str                     # submitted | max_turns | refusal | truncated | no_verdict | api_error
    payload: Optional[Dict[str, Any]] = None
    detail: str = ""
    turns: int = 0
    usage: Dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0, "cache_read": 0})

    @property
    def ok(self) -> bool:
        return self.outcome == "submitted"


def _add_usage(acc: Dict[str, int], usage: Any) -> None:
    acc["input"] += getattr(usage, "input_tokens", 0) or 0
    acc["output"] += getattr(usage, "output_tokens", 0) or 0
    acc["cache_read"] += getattr(usage, "cache_read_input_tokens", 0) or 0


def run_agent(client: Any, spec: AgentSpec, task: str,
              trace: Optional[Callable[[Dict[str, Any]], None]] = None) -> RunResult:
    tools = {t.name: t for t in spec.tools}
    messages: List[Dict[str, Any]] = [{"role": "user", "content": task}]
    result = RunResult(agent=spec.name, outcome="max_turns")
    nudged = False
    emit = trace or (lambda _e: None)

    for turn in range(1, spec.max_turns + 1):
        result.turns = turn
        t0 = time.time()
        try:
            response = client.beta.messages.create(
                model=spec.model,
                max_tokens=spec.max_tokens,
                system=spec.system,
                tools=[t.schema() for t in spec.tools],
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": spec.effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIConnectionError as e:
            result.outcome, result.detail = "api_error", f"connection: {e}"
            break
        except anthropic.RateLimitError as e:
            result.outcome, result.detail = "api_error", f"rate limited after retries: {e}"
            break
        except anthropic.APIStatusError as e:
            result.outcome, result.detail = "api_error", f"HTTP {e.status_code}: {e.message}"
            break

        _add_usage(result.usage, response.usage)
        messages.append({"role": "assistant", "content": response.content})
        calls = [b for b in response.content if b.type == "tool_use"]
        emit({"agent": spec.name, "turn": turn, "stop_reason": response.stop_reason,
              "tools": [c.name for c in calls], "secs": round(time.time() - t0, 1)})

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            result.outcome = "refusal"
            result.detail = getattr(details, "category", None) or "refused"
            break
        if response.stop_reason == "max_tokens":
            result.outcome, result.detail = "truncated", "hit max_tokens mid-response"
            break

        if not calls:
            if nudged:
                result.outcome = "no_verdict"
                result.detail = "ended twice without calling " + spec.terminal
                break
            nudged = True
            messages.append({"role": "user", "content":
                             f"You have not finished. Call {spec.terminal} with your result now; "
                             "if the evidence is insufficient, say so in it rather than in prose."})
            continue

        # Two phases so parallel tool calls really run in parallel: start every call
        # (a tool fn may return a pending object with .resolve()), then collect in
        # order. All results for one assistant turn go back in ONE user message.
        started = []
        for call in calls:
            tool = tools.get(call.name)
            if tool is None:
                started.append((call, {"is_error": True, "content": f"unknown tool {call.name!r}"}))
            elif tool.fn is None:                      # terminal tool
                result.payload = dict(call.input)
                started.append((call, "recorded"))
            else:
                try:
                    started.append((call, tool.fn(dict(call.input))))
                except Exception as e:                  # a broken tool is evidence, not a crash
                    started.append((call, _error(e)))
        results = []
        for call, out in started:
            if hasattr(out, "resolve"):
                try:
                    out = out.resolve()
                except Exception as e:
                    out = _error(e)
            if isinstance(out, dict):
                results.append({"type": "tool_result", "tool_use_id": call.id, **out})
            else:
                results.append({"type": "tool_result", "tool_use_id": call.id, "content": out})
        if result.payload is not None:
            result.outcome = "submitted"
            break
        messages.append({"role": "user", "content": results})

    emit({"agent": spec.name, "outcome": result.outcome, "detail": result.detail,
          "turns": result.turns, "usage": result.usage})
    return result


def _error(e: Exception) -> Dict[str, Any]:
    return {"is_error": True, "content": f"{type(e).__name__}: {e}"}


def as_tool_result(r: RunResult) -> Dict[str, Any]:
    """How a subagent's run is reported back to the coordinator."""
    body = {"agent": r.agent, "outcome": r.outcome, "turns": r.turns}
    if r.ok:
        body["finding"] = r.payload
    else:
        body["error"] = (f"investigation did NOT complete ({r.outcome}: {r.detail}). "
                         "Treat this area as UNKNOWN, not as healthy.")
    return {"is_error": not r.ok, "content": json.dumps(body, default=str)}
