#!/usr/bin/env python3
"""Unified knowledge lookup across the graphify+ruflo layer — token-efficient
retrieval BEFORE reading whole files.

  knowledge.py "<question or symbol>"

Federates:
  1. memory_store (SQLite cache)    -> instant cached queries (80% token reduction)
  2. graphify global graph          -> code structure + exact file:line (graphify CLI)
  3. graphify reuse index           -> which repos already implement a symbol (extract, don't rewrite)
  4. ruflo semantic memory (MCP)    -> insights/decisions (namespace=knowledge)

Zero AI tokens: pure local graph lookup. Use its output as targeted context instead of
opening files blindly.
"""
import json, os, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from memory_store import MemoryStore

GRAPHIFY = os.path.expanduser("~/.venvs/graphifyy/bin/graphify")
GRAPH = os.path.expanduser("~/.graphify/global-graph.json")
INDEX = os.path.expanduser("~/.graphify/global-index.json")


def reuse_lookup(terms):
    if not os.path.exists(INDEX):
        return {}
    idx = json.load(open(INDEX))
    shared = idx.get("shared_symbols", {})
    hits = {}
    for sym, repos in shared.items():
        low = sym.lower()
        if any(t in low for t in terms):
            hits[sym] = repos
    return dict(sorted(hits.items(), key=lambda kv: -len(kv[1]))[:12])


def graphify_query(q, store):
    """Query with memory store first, fall back to graphify CLI."""
    # Try cache first (instant, ~0 tokens)
    mode, out = store.query(q, mode="query", use_cache=True)
    if out and "not found" not in out.lower() and "no node" not in out.lower():
        return mode, out, True  # (mode, result, from_cache)

    # Cache miss — explain variant
    mode, out = store.query(q, mode="explain", use_cache=True)
    if out and "not found" not in out.lower() and "no node" not in out.lower():
        return mode, out, False

    return None, None, False


def main():
    if len(sys.argv) < 2:
        print("usage: knowledge.py \"<question or symbol>\"")
        sys.exit(1)
    q = " ".join(sys.argv[1:])
    terms = [t.strip("()\"'.,").lower() for t in q.split() if len(t) > 3]

    # Initialize memory store (creates DB, loads cache)
    store = MemoryStore()

    print(f"# KNOWLEDGE LOOKUP: {q}\n")

    mode, out, from_cache = graphify_query(q, store)
    if out:
        cache_tag = "📦 (cached)" if from_cache else "🔍 (fresh)"
        print(f"## graphify {mode} {cache_tag}")
        print(out[:1600])
        print()
    else:
        print("## graphify: no direct node — try a specific symbol/file name\n")

    hits = reuse_lookup(terms)
    if hits:
        print("## reuse points (extract instead of rewrite):")
        for sym, repos in hits.items():
            print(f"  {sym:<26} in {len(repos)} repos: {', '.join(repos[:5])}"
                  f"{'…' if len(repos) > 5 else ''}")
        print()

    print("## ruflo semantic memory (insights/decisions) — query in-session with:")
    print(f'   mcp__ruflo__memory_search  query="{q}"  namespace="knowledge"  smart=true')

    # Show cache statistics
    stats = store.get_stats()
    print(f"\n## cache stats (memory store)")
    print(f"  Cached queries: {stats['query_cache_size']}")
    print(f"  Index nodes: {stats['node_index_size']}")
    print(f"  Dependencies: {stats['edge_count']}")
    print(f"  God nodes: {stats['god_nodes']}")
    print(f"  DB size: {stats['db_size_mb']} MB")

    print("\n(token-efficient: use the above as targeted context; open only the files cited.)")


if __name__ == "__main__":
    main()
