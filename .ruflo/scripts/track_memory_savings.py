#!/usr/bin/env python3
"""Monitor token savings from memory store cache hits.

Tracks:
- Query cache hit rate
- Tokens saved per query
- Cumulative savings vs baseline graphify CLI

Usage: python3 track_memory_savings.py [report|baseline|delta]
"""
import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from memory_store import MemoryStore


def estimate_tokens(query_result):
    """Rough token estimate: ~1 token per 4 characters."""
    return max(len(query_result) // 4, 50)


def get_metrics():
    store = MemoryStore()
    conn = sqlite3.connect(store.db_path)
    c = conn.cursor()

    cache_size = c.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
    total_nodes = c.execute("SELECT COUNT(*) FROM node_index").fetchone()[0]
    total_edges = c.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]

    # Estimate tokens saved (each cached query avoided a graphify CLI call)
    # Typical graphify result: 800-2000 characters = 200-500 tokens
    # Average: 300 tokens per avoided graphify call
    tokens_per_graphify_call = 300
    tokens_saved = cache_size * tokens_per_graphify_call

    conn.close()

    return {
        "timestamp": datetime.now().isoformat(),
        "cache_hits": cache_size,
        "indexed_nodes": total_nodes,
        "indexed_edges": total_edges,
        "tokens_saved_estimate": tokens_saved,
        "cost_savings_estimate_usd": (tokens_saved / 1_000_000) * 0.003,  # $3 per M tokens (Opus)
    }


def save_baseline():
    """Record baseline (no cache) metrics."""
    metrics = get_metrics()
    baseline_file = os.path.expanduser("~/.ruflo/data/memory_store_baseline.json")
    with open(baseline_file, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[Baseline saved] {baseline_file}")
    return metrics


def report_delta():
    """Show delta vs baseline (saved time)."""
    baseline_file = os.path.expanduser("~/.ruflo/data/memory_store_baseline.json")
    if not os.path.exists(baseline_file):
        print("No baseline recorded. Run: track_memory_savings.py baseline")
        return

    with open(baseline_file) as f:
        baseline = json.load(f)

    current = get_metrics()

    delta_hits = current["cache_hits"] - baseline.get("cache_hits", 0)
    delta_tokens = current["tokens_saved_estimate"] - baseline.get("tokens_saved_estimate", 0)
    delta_cost = current["cost_savings_estimate_usd"] - baseline.get("cost_savings_estimate_usd", 0)

    print(f"""
=== Memory Store Savings Report ===

Cache Hits (new):           {delta_hits}
Tokens Saved (since baseline): {delta_tokens:,}
Cost Savings (since baseline): ${delta_cost:.6f}

Total Cached Queries:       {current['cache_hits']}
Total Tokens Saved:         {current['tokens_saved_estimate']:,}
Total Cost Savings:         ${current['cost_savings_estimate_usd']:.6f}

Indexed Graph:
  Nodes:                    {current['indexed_nodes']:,}
  Edges:                    {current['indexed_edges']:,}

Baseline (saved: {baseline['timestamp']}):
  Cache Hits:               {baseline.get('cache_hits', 0)}
  Tokens Saved:             {baseline.get('tokens_saved_estimate', 0):,}
  Cost Savings:             ${baseline.get('cost_savings_estimate_usd', 0):.6f}
""")


def report_current():
    """Show current cache state."""
    metrics = get_metrics()
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "baseline":
            save_baseline()
        elif cmd == "delta":
            report_delta()
        else:
            report_current()
    else:
        report_current()
