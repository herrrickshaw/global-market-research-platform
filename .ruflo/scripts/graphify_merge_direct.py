#!/usr/bin/env python3
"""Deterministic O(n) union of all per-repo Graphify graph.json into ONE cross-repo map.
- namespaces node ids as '<repo>::<id>' so ids never collide
- tags every node/edge with its source repo
- adds cheap cross-repo links: identical symbol *labels* across repos -> 'shared_symbol' edges
Output: ~/.graphify/global-graph.json  (+ a compact extraction index)
"""
import glob, json, os, re, subprocess, collections

OUT = os.path.expanduser("~/.graphify/global-graph.json")
IDX = os.path.expanduser("~/.graphify/global-index.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# Read exact repo lists from logs (NEVER recursive-glob ~ — it walks 107GB).
#
# Dedup key is the REMOTE URL, not the directory name. A local checkout always beats
# a shallow gh-clone of the same remote: the clones are `--depth 1
# GIT_LFS_SKIP_SMUDGE=1`, so when both exist the clone is a stub. market-pipeline
# exposed the first half of this — a 13-node clone shadowing the real 7,670-node
# local graph, so every file:line reference into it resolved to nothing.
#
# Keying on the directory basename does NOT fix it, because three local checkouts sit
# in directories named differently from their own remote, and were merged twice:
#     ~/BazaarTalks-cpp                 <-> clone Bazartalks_Py2Cplus
#     ~/masaladeutsch-archive           <-> clone blogger_writeups_code
#     ~/omc-retail-profitability-model  <-> clone india-omc-fuel-fleet-model
# Each pair is ONE GitHub repo counted as two, inflating the graph by ~3.7k nodes and
# manufacturing five "100% identical repo" pairs that are really three aliases plus
# two genuine duplicates. Normalising the remote collapses the aliases and leaves the
# genuine duplicates standing, which is the distinction that matters.
by_remote = {}   # canonical remote -> (priority, graph path, display name)


def remote_of(repo_dir):
    """Canonical <owner>/<name> for a checkout, or None if it has no origin."""
    try:
        url = subprocess.run(["git", "-C", repo_dir, "remote", "get-url", "origin"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return None
    if not url:
        return None
    url = re.sub(r'^git@([^:]+):', r'https://\1/', url)
    url = re.sub(r'\.git$', '', url).rstrip('/').lower()
    return "/".join(url.split("/")[-2:]) or None


def offer(name, repo_dir, gj, priority):
    if not os.path.exists(gj):
        return
    key = remote_of(repo_dir) or f"path::{os.path.realpath(repo_dir)}"
    cur = by_remote.get(key)
    if cur is None or priority < cur[0]:
        by_remote[key] = (priority, gj, name)


# 1. local git repos discovered by the batch driver
for row in json.load(open(os.path.expanduser("~/.ruflo/logs/graphify_batch.json"))):
    if row.get("status") == "ok":
        d = os.path.expanduser(f"~/{row['repo']}")
        offer(os.path.basename(row["repo"]), d,
              os.path.join(d, "graphify-out", "graph.json"), 0)

# 2. local trees that are NOT their own git repo, so the batch driver never sees them
#    (it finds .git dirs and skips $HOME). market-pipeline lives inside the $HOME repo,
#    so its remote resolves to the $HOME repo's — key it by path instead.
for extra in ("~/market-pipeline",):
    p = os.path.expanduser(extra)
    gj = os.path.join(p, "graphify-out", "graph.json")
    if os.path.exists(gj):
        by_remote[f"path::{os.path.realpath(p)}"] = (0, gj, os.path.basename(p))

# 3. cloned GitHub repos — only used where no local checkout of that remote exists
clones_log = os.path.expanduser("~/.ruflo/logs/graphify_clones.json")
if os.path.exists(clones_log):
    for row in json.load(open(clones_log)):
        if row.get("status") == "ok":
            offer(row["repo"], row.get("path", ""), row.get("graph", ""), 1)

graphs = sorted(gj for _, gj, _ in by_remote.values())

nodes, edges = [], []
per_repo = collections.Counter()
label_index = collections.defaultdict(list)   # label -> [(repo, nsid)]

def node_id(n, i):
    return n.get("id") or n.get("name") or n.get("label") or f"n{i}"

def node_label(n):
    return n.get("label") or n.get("name") or n.get("id") or ""

for gj in graphs:
    repo = os.path.basename(os.path.dirname(os.path.dirname(gj)))
    try:
        d = json.load(open(gj))
    except Exception as e:
        print(f"  skip {repo}: {e}"); continue
    g_nodes = d.get("nodes", [])
    g_edges = d.get("edges", d.get("links", []))
    idmap = {}
    for i, n in enumerate(g_nodes):
        if not isinstance(n, dict):
            continue
        oid = node_id(n, i)
        nsid = f"{repo}::{oid}"
        idmap[oid] = nsid
        m = dict(n)
        m["id"] = nsid
        m["repo"] = repo
        nodes.append(m)
        lbl = node_label(n)
        if lbl:
            label_index[lbl].append((repo, nsid))
    per_repo[repo] = len(g_nodes)
    for e in g_edges:
        if not isinstance(e, dict):
            continue
        s = e.get("source") or e.get("from")
        t = e.get("target") or e.get("to")
        me = dict(e)
        me["source"] = idmap.get(s, f"{repo}::{s}")
        me["target"] = idmap.get(t, f"{repo}::{t}")
        me["repo"] = repo
        edges.append(me)

# cross-repo REUSE INDEX (O(n)): symbols that appear in >1 repo = extraction/reuse points.
# We index them (symbol -> repos) instead of exploding O(occ^2) pairwise edges.
shared = {}
for lbl, occ in label_index.items():
    repos = sorted(set(r for r, _ in occ))
    if len(repos) < 2 or len(lbl) < 4:
        continue
    shared[lbl] = repos
cross = len(shared)

json.dump({"directed": True, "nodes": nodes, "edges": edges,
           "meta": {"repos": len(per_repo), "shared_symbols": cross}},
          open(OUT, "w"))

# compact extraction index: repo -> node count; shared symbols -> where to reuse
json.dump({
    "repos": dict(per_repo),
    "totals": {"nodes": len(nodes), "edges": len(edges), "cross_repo_links": cross},
    "shared_symbols": dict(sorted(shared.items(), key=lambda kv: -len(kv[1]))[:200]),
}, open(IDX, "w"), indent=2)

print(f"MERGED {len(per_repo)} repos -> {len(nodes)} nodes, {len(edges)} edges "
      f"({cross} cross-repo links)")
print(f"  graph: {OUT}  ({os.path.getsize(OUT)/1e6:.1f} MB)")
print(f"  index: {IDX}")
print("  top reused symbols across repos:")
for lbl, repos in sorted(shared.items(), key=lambda kv: -len(kv[1]))[:12]:
    print(f"    {lbl:<32} in {len(repos)} repos: {', '.join(repos[:4])}{'…' if len(repos)>4 else ''}")
