#!/usr/bin/env python3
"""Clone every LIVE GitHub repo not already local (code only, no LFS blobs, shallow),
graph each token-free, and record paths for the global-map merge."""
import json, os, subprocess, time

DEST = os.path.expanduser("~/.graphify/gh-clones")
os.makedirs(DEST, exist_ok=True)
G = os.path.expanduser("~/.venvs/graphifyy/bin/graphify")
LOG = os.path.expanduser("~/.ruflo/logs/graphify_clones.json")

# local repos already graphed
b = json.load(open(os.path.expanduser("~/.ruflo/logs/graphify_batch.json")))
local = set(os.path.basename(r["repo"]) for r in b)
skip = {"global-market-research-platform"}  # this IS $HOME

gh = json.loads(subprocess.run(
    ["gh", "repo", "list", "--limit", "200", "--json", "name,isArchived"],
    capture_output=True, text=True).stdout)
live = [r["name"] for r in gh
        if not r["isArchived"] and r["name"] not in local and r["name"] not in skip]

env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}
results = []
for name in sorted(live):
    dest = os.path.join(DEST, name)
    t0 = time.time()
    if not os.path.isdir(os.path.join(dest, ".git")):
        c = subprocess.run(["gh", "repo", "clone", f"herrrickshaw/{name}", dest,
                            "--", "--depth", "1"],
                           capture_output=True, text=True, env=env, timeout=180)
        if c.returncode != 0:
            print(f"  [clone-fail] {name}: {c.stderr.strip()[:70]}", flush=True)
            results.append({"repo": name, "status": "clone-fail", "nodes": 0})
            continue
    # graph it (token-free)
    gj = os.path.join(dest, "graphify-out", "graph.json")
    try:
        subprocess.run([G, "update", dest, "--no-cluster"],
                       capture_output=True, text=True, env={**env, "GRAPHIFY_FORCE": "1"},
                       timeout=150)
    except subprocess.TimeoutExpired:
        print(f"  [graph-timeout] {name}", flush=True)
    n = 0
    if os.path.exists(gj):
        try: n = len(json.load(open(gj)).get("nodes", []))
        except Exception: pass
    st = "ok" if n else "empty"
    results.append({"repo": name, "path": dest, "graph": gj, "nodes": n, "status": st})
    print(f"  [{st:5}] {name:<34} nodes={n:<5} {time.time()-t0:5.1f}s", flush=True)

json.dump(results, open(LOG, "w"), indent=2)
ok = [r for r in results if r["status"] == "ok"]
print(f"\nCLONED+GRAPHED {len(ok)}/{len(live)} · {sum(r['nodes'] for r in ok)} new nodes")
print("log:", LOG)
