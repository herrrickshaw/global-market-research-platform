#!/usr/bin/env python3
"""
diagnose.py — ask the rebuilt cross-repo graph what is wrong with the OTHER repos.

The market-pipeline finding (a 13-node gh-clone stub shadowing a 3,223-node local
checkout) was found by comparing a repo's representation against its real size.
Generalise that, and add the other things a 69-repo AST graph can answer that
reading files cannot:

  1. STUB REPOS      — repos represented by a shallow gh-clone while a local
                       checkout exists, or clone-only repos so small they are
                       almost certainly LFS/depth artefacts rather than real code.
  2. DUPLICATED CODE — the same function/class label defined in N repos. Filters
                       out the noise the naive index is full of (README.md,
                       main(), __init__) and keeps real named symbols.
  3. GOD FILES       — files carrying far more definitions than their repo's norm.
  4. ORPHAN NODES    — definitions with no edge at all in their own repo graph.
  5. UNGRAPHED       — local repos that produced zero nodes.
"""
import json, os, collections, subprocess

G = json.load(open(os.path.expanduser("~/.graphify/global-graph.json")))
BATCH = json.load(open(os.path.expanduser("~/.ruflo/logs/graphify_batch.json")))
CLONES = json.load(open(os.path.expanduser("~/.ruflo/logs/graphify_clones.json")))
NODES, EDGES = G["nodes"], G["edges"]

per_repo = collections.Counter(n.get("repo") for n in NODES)
print(f"graph: {len(NODES):,} nodes / {len(EDGES):,} edges / {len(per_repo)} repos\n")

# ---------------------------------------------------------------- 1. stubs
print("=" * 72)
print("1. STUB / THIN REPRESENTATIONS")
print("=" * 72)
local_names = {os.path.basename(r["repo"]) for r in BATCH if r.get("status") == "ok"}
clone_names = {r["repo"] for r in CLONES if r.get("status") == "ok"}
clone_nodes = {r["repo"]: r.get("nodes", 0) for r in CLONES}

shadowed = sorted(local_names & clone_names)
print(f"repos with BOTH a local checkout and a gh-clone: {len(shadowed)}")
for r in shadowed:
    print(f"  {r:<42} graph={per_repo.get(r,0):<7} clone_had={clone_nodes.get(r,0)}")
print("  (merge now prefers local; listed so the preference can be spot-checked)")

thin = sorted([(n, r) for r, n in clone_nodes.items()
               if r not in local_names and n < 40 and n > 0])
print(f"\nclone-only repos under 40 nodes — likely --depth 1 / LFS artefacts, not real:")
for n, r in thin[:15]:
    print(f"  {n:>5} nodes  {r}")

# ---------------------------------------------------------------- 2. dup code
print("\n" + "=" * 72)
print("2. DUPLICATED SYMBOLS ACROSS REPOS (consolidation candidates)")
print("=" * 72)
NOISE = {"main()", "README.md", ".__init__()", "__init__()", "Path", "DataFrame",
         "Caveats", "Quick Links", "setup()", "run()", "test()", "np", "pd"}
lab = collections.defaultdict(set)
for n in NODES:
    l = (n.get("label") or "").strip()
    if (n.get("file_type") == "code" and l and l not in NOISE
            and l.endswith("()") and len(l) > 8):
        lab[l].add(n.get("repo"))
dups = sorted(((len(v), k, sorted(v)) for k, v in lab.items() if len(v) >= 3),
              reverse=True)
print(f"named functions defined in >=3 repos: {len(dups)}")
for c, l, rs in dups[:18]:
    print(f"  {c:>2} repos  {l:<34} {', '.join(rs[:4])}{' …' if len(rs) > 4 else ''}")

# ---------------------------------------------------------------- 3. god files
print("\n" + "=" * 72)
print("3. GOD FILES (definition count far above the repo's own norm)")
print("=" * 72)
byfile = collections.Counter()
for n in NODES:
    if n.get("file_type") == "code" and n.get("source_file"):
        byfile[(n.get("repo"), n["source_file"])] += 1
byrepo_files = collections.defaultdict(list)
for (r, f), c in byfile.items():
    byrepo_files[r].append((c, f))
god = []
for r, fs in byrepo_files.items():
    if len(fs) < 8:
        continue
    counts = sorted(c for c, _ in fs)
    med = counts[len(counts) // 2]
    for c, f in fs:
        if med and c >= max(40, med * 8):
            god.append((c, med, r, f))
for c, med, r, f in sorted(god, reverse=True)[:14]:
    print(f"  {c:>4} defs (repo median {med:>2})  {r}/{f}")
print(f"  total flagged: {len(god)}")

# ---------------------------------------------------------------- 4. orphans
print("\n" + "=" * 72)
print("4. ORPHAN DEFINITIONS (no edge in their own repo graph)")
print("=" * 72)
linked = set()
for e in EDGES:
    linked.add(e.get("source")); linked.add(e.get("target"))
orph = collections.Counter()
total_code = collections.Counter()
for n in NODES:
    if n.get("file_type") != "code":
        continue
    total_code[n.get("repo")] += 1
    if n["id"] not in linked:
        orph[n.get("repo")] += 1
rows = [(orph[r] / total_code[r], orph[r], total_code[r], r)
        for r in total_code if total_code[r] >= 60]
for pct, o, t, r in sorted(rows, reverse=True)[:12]:
    print(f"  {pct*100:5.1f}%  {o:>5}/{t:<6} unreferenced defs  {r}")

# ---------------------------------------------------------------- 5. ungraphed
print("\n" + "=" * 72)
print("5. LOCAL REPOS THAT PRODUCED ZERO NODES")
print("=" * 72)
for r in BATCH:
    if r.get("status") != "ok":
        print(f"  [{r.get('status'):>7}]  {r['repo']}")
