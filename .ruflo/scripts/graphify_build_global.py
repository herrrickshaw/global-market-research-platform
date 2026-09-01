#!/usr/bin/env python3
"""Build the persistent Graphify global cross-repo graph from every per-repo graph.json.
Incremental `global add` (union + per-repo tag) — fast, no O(n^2) fuzzy merge, 0 tokens."""
import glob, os, subprocess, time, json, collections

G = os.path.expanduser("~/.venvs/graphifyy/bin/graphify")
GLOBAL = os.path.expanduser("~/.graphify/global-graph.json")

if os.path.exists(GLOBAL):
    os.remove(GLOBAL)

graphs = sorted(
    p for p in glob.glob(os.path.expanduser("~/**/graphify-out/graph.json"), recursive=True)
    if "worktrees" not in p and "/.ruflo/" not in p and "/.graphify/" not in p
)
t0 = time.time()
for gj in graphs:
    tag = os.path.basename(os.path.dirname(os.path.dirname(gj)))
    try:
        r = subprocess.run([G, "global", "add", gj, "--as", tag],
                           capture_output=True, text=True, timeout=90)
        out = (r.stdout or r.stderr).strip().splitlines()
        last = out[-1] if out else "(no output)"
        print(f"  +{tag:<44} {last.split(':',1)[-1].strip()[:44]}", flush=True)
    except subprocess.TimeoutExpired:
        print(f"  !{tag:<44} TIMEOUT >90s — skipped", flush=True)

print(f"\nadded {len(graphs)} repos in {time.time()-t0:.1f}s")
if os.path.exists(GLOBAL):
    d = json.load(open(GLOBAL))
    nodes = d.get("nodes", [])
    by = collections.Counter(n.get("repo", "?") for n in nodes if isinstance(n, dict))
    print(f"GLOBAL: {len(nodes)} nodes · {len(d.get('edges', d.get('links', [])))} edges · "
          f"{len(by)} repos · {round(os.path.getsize(GLOBAL)/1e6,1)} MB")
    print("path:", GLOBAL)
else:
    print("ERROR: global graph not created")
