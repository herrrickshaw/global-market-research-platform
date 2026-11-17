#!/usr/bin/env python3
"""Batch-build Graphify knowledge graphs across all real project repos (token-free,
local tree-sitter extraction, --no-cluster so no LLM). Writes a summary log."""
import json, os, subprocess, time, sys

GRAPHIFY = os.path.expanduser("~/.venvs/graphifyy/bin/graphify")
HOME = os.path.expanduser("~")
LOG = os.path.expanduser("~/.ruflo/logs/graphify_batch.log")
PER_REPO_TIMEOUT = 150  # seconds

# discover git repos, excluding the home-as-repo, worktrees, and vendored trees
def find_repos():
    out = subprocess.run(
        ["find", HOME, "-maxdepth", "3", "-name", ".git", "-type", "d"],
        capture_output=True, text=True).stdout.splitlines()
    repos = []
    for g in out:
        r = g[:-5]  # strip /.git
        if r == HOME:  # skip 107G home-as-repo
            continue
        if any(x in r for x in ("worktrees", "node_modules", "/.claude/", "/.cache/",
                                 "/.nvm", "/.nemoclaw", "/vcpkg")):
            continue
        repos.append(r)
    return sorted(set(repos))

def log(msg):
    with open(LOG, "a") as fh:
        fh.write(msg + "\n")
    print(msg, flush=True)

def main():
    open(LOG, "w").close()
    repos = find_repos()
    log(f"# Graphify batch — {len(repos)} repos — started {time.strftime('%Y-%m-%d %H:%M:%S')}")
    results = []
    for r in repos:
        t0 = time.time()
        try:
            p = subprocess.run(
                [GRAPHIFY, "update", r, "--no-cluster"],
                capture_output=True, text=True, timeout=PER_REPO_TIMEOUT,
                env={**os.environ, "GRAPHIFY_FORCE": "1"})
            dt = time.time() - t0
            gj = os.path.join(r, "graphify-out", "graph.json")
            n = e = 0
            if os.path.exists(gj):
                d = json.load(open(gj))
                n = len(d.get("nodes", []))
                e = len(d.get("edges", d.get("links", [])))
            status = "ok" if n else "empty"
            results.append((r, n, e, dt, status))
            log(f"[{status:5}] {os.path.relpath(r, HOME):<48} nodes={n:<6} edges={e:<6} {dt:5.1f}s")
        except subprocess.TimeoutExpired:
            results.append((r, 0, 0, PER_REPO_TIMEOUT, "timeout"))
            log(f"[timeout] {os.path.relpath(r, HOME):<48} (> {PER_REPO_TIMEOUT}s, skipped)")
        except Exception as exc:
            results.append((r, 0, 0, time.time()-t0, "error"))
            log(f"[error] {os.path.relpath(r, HOME):<48} {str(exc)[:60]}")

    ok = [x for x in results if x[4] == "ok"]
    tot_n = sum(x[1] for x in ok)
    tot_e = sum(x[2] for x in ok)
    log(f"\n# DONE: {len(ok)}/{len(repos)} built · {tot_n} nodes · {tot_e} edges total")
    # write machine-readable summary
    json.dump([{"repo": os.path.relpath(r, HOME), "nodes": n, "edges": e,
                "sec": round(dt, 1), "status": s} for r, n, e, dt, s in results],
              open(os.path.expanduser("~/.ruflo/logs/graphify_batch.json"), "w"), indent=2)

if __name__ == "__main__":
    main()
