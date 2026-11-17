# agents/pipeline_triage/__main__.py
#
#   .venv/bin/python -m agents.pipeline_triage              # live triage (needs ANTHROPIC_API_KEY)
#   .venv/bin/python -m agents.pipeline_triage --dry-run    # scripted model, REAL tools, no API call
#   .venv/bin/python -m agents.pipeline_triage --json
#
# Exit code mirrors the verdict: 0 GO, 1 NO_GO, 2 NEEDS_HUMAN. Advisory only —
# mailer.sh does not call this, and nothing here can send.
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .agents import DEFAULT_MODEL, run_triage
from .tools import HERE

EXIT = {"GO": 0, "NO_GO": 1, "NEEDS_HUMAN": 2}


def _client(dry_run: bool):
    if dry_run:
        from .scripted import ScriptedClient
        return ScriptedClient.demo()
    sys.path.insert(0, str(HERE))
    import anthropic
    import env_loader                     # environ → credentials.env → .env
    key = env_loader.get("ANTHROPIC_API_KEY")
    if not key:
        sys.exit("ANTHROPIC_API_KEY not set — add it to ~/.config/market-secrets/credentials.env "
                 "(mode 600) or export it; use --dry-run to exercise the tools without the API.")
    return anthropic.Anthropic(api_key=key)


def _print(report: dict) -> None:
    v = report["verdict"] or {}
    print(f"\n== {v.get('verdict', '?')}: {v.get('headline', '')}")
    for c in v.get("root_causes", []):
        print(f"  cause: {c['cause']}  [{c['owner_script'] or '-'}]\n         {c['evidence']}")
    for a in v.get("recommended_actions", []):
        print(f"  do:    {a}")
    for u in v.get("unverified", []):
        print(f"  UNVERIFIED: {u}")
    print("\n-- investigations")
    for i in report["investigations"]:
        f = i["finding"] or {}
        print(f"  {i['agent']:<10} {i['outcome']:<10} {f.get('status', '-'):<12} {f.get('summary', '')[:110]}")
    u = report["usage"]
    print(f"\n-- tokens in={u['input']:,} out={u['output']:,} cache_read={u['cache_read']:,}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="scripted model; real read-only tools; no API")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--worker-model", default=None, help="subagent model (default: same as --model)")
    ap.add_argument("--max-turns", type=int, default=6, help="coordinator turn cap")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = HERE / "logs" / f"triage_{stamp}{'_dry' if args.dry_run else ''}.jsonl"
    trace_path.parent.mkdir(exist_ok=True)
    with trace_path.open("w") as fh:
        def trace(event: dict) -> None:
            fh.write(json.dumps(event, default=str) + "\n")
            fh.flush()
            if not args.json and "outcome" in event:
                print(f"[{event['agent']}] {event['outcome']} after {event['turns']} turn(s)", file=sys.stderr)

        report = run_triage(_client(args.dry_run), args.model, args.worker_model, trace, args.max_turns)

    report["trace"] = str(trace_path)
    (Path(trace_path).with_suffix(".report.json")).write_text(json.dumps(report, indent=2, default=str))
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print(report)
        print(f"-- trace {trace_path}")
    return EXIT.get((report["verdict"] or {}).get("verdict"), 2)


if __name__ == "__main__":
    sys.exit(main())
