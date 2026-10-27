# pipeline_triage — coordinator + subagent triage of the morning run

Answers one question after `ingest.sh` → `mailer.sh`: **is this morning's brief fit to send,
and if not, why not?** It is advisory and read-only. The deterministic gates
(`data_index.py --require ingest`, `price_gate.py`) still decide SEND. This explains
what they found.

```bash
.venv/bin/python -m agents.pipeline_triage --dry-run   # scripted model, real tools, no API, no spend
.venv/bin/python -m agents.pipeline_triage             # live (ANTHROPIC_API_KEY via env_loader)
.venv/bin/python -m agents.pipeline_triage --json      # full report on stdout
.venv/bin/python -m pytest tests/test_pipeline_triage.py
```

Exit code: `0` GO · `1` NO_GO · `2` NEEDS_HUMAN. Each run writes `logs/triage_<stamp>.jsonl`
(one event per model turn: agent, stop_reason, tools called, seconds) and `.report.json`.

## Topology

```
coordinator  (Opus 5.5, effort high, ≤6 turns)
  tools: investigate_freshness · investigate_run_logs · investigate_send_gate · submit_verdict
    │  self-contained brief per call. Called in parallel and run on a thread pool
    ├── freshness   data_index · registry_entry · list_logs · read_log   → submit_finding
    ├── run_logs    section_runs · list_logs · read_log                  → submit_finding
    └── send_gate   gate_state · list_logs · read_log                    → submit_finding
       (each: fresh history, effort low, ≤8 turns)
```

| File | Role |
|---|---|
| `loop.py` | The one agent loop (manual `while`), its stop conditions, two-phase parallel tool execution |
| `tools.py` | Read-only tools, the path guard, output budgeting |
| `agents.py` | Agent specs, system prompts, terminal-tool schemas, the coordinator |
| `scripted.py` | Stateless fake client for `--dry-run` and tests |
| `__main__.py` | CLI, trace file, exit codes |

## Design decisions (and what was rejected)

**Manual loop instead of the SDK tool runner.** The stop conditions are the point of the
module, so they are explicit and tested: success only through the **terminal tool**,
plus `max_turns`, `refusal`, `max_tokens` (a cut-off `tool_use` is never executed),
no terminal call after one nudge, and an API error after the SDK's own retries. Each
one is returned as a `RunResult.outcome` and never raised.

**Terminal tools with strict schemas instead of parsing prose.** `submit_finding` and
`submit_verdict` are `strict: true` tools. The run ends when one is called, and its
input *is* the structured result. Forced `tool_choice` returns a 400 on Opus 5.5, so the prompt
asks for the call and the loop enforces it.

**Subagents instead of one agent with every tool.**
- *Context isolation:* a subagent sees only its brief, and the coordinator sees only a
  structured finding, not 135 KB of `run_monitor --json`.
- *Least privilege:* the coordinator holds no data tools at all.
- *Independent failure:* one stuck investigation doesn't stall the others.

Rejected: a single agent. It would have been simpler, but its context would hold every
log tail, and an exhausted turn budget would lose all three areas at once.

**Error propagation is the core rule.** A subagent that fails in any way (out of turns,
no verdict, refusal, API error, or a Python crash) comes back as an `is_error` tool result
saying *treat this area as UNKNOWN, not healthy*. The coordinator prompt forbids GO while
an area the send depends on is unverified. If the coordinator itself fails, the report is
forced to `NEEDS_HUMAN`. Three tests pin this
(`test_failed_subagent_forces_needs_human`, `test_crashed_subagent_is_reported_not_raised`,
`test_coordinator_failure_never_implies_a_verdict`).

**Guardrails live in code, not prompts.**
- `price_gate.py` is not a tool. It rewrites `state/price_gate_reason.txt`, so the gate
  agent reads that file instead.
- Logs are addressed by bare name and resolved only inside the known log directories.
- JSON tools shrink by dropping whole items (`fit_json`, with an `omitted` count) instead
  of cutting a string. The first dry run caught that bug.

**History is append-only.** `response.content` goes back verbatim, thinking blocks
included. This is required for preserved thinking on current models.

**Models.** Both tiers default to `claude-opus-5-5`, with `--worker-model` to put the
read-heavy subagents on a cheaper model. Requests opt into server-side refusal fallbacks
(`fallbacks: "default"`).

## Not done yet

- Live run is unverified: the machine has no `ANTHROPIC_API_KEY`. Add it to
  `~/.config/market-secrets/credentials.env` and run without `--dry-run`.
- No prompt caching. Each subagent prompt is under the minimum cacheable prefix, and the
  coordinator runs about 2 turns.
- Not scheduled. To run it after `mailer.sh`, add a step that runs it and attaches the
  report to the failure alert. Keep it off the send path.
