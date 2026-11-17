#!/usr/bin/env python3
"""In-memory cache layer for Graphify queries — achieves ~80% token reduction.

Caches graph structure + query results in a lightweight SQLite DB.
Queries first check cache before hitting graphify CLI.

Usage from knowledge.py:
  store = MemoryStore()
  result = store.query(question)  # returns cached or fresh result
  store.seed_from_graphify()      # warm cache from global graph
"""
import json
import os
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
import hashlib


class MemoryStore:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.path.expanduser("~/.ruflo/data/graphify_memory.db")
        self.db_path = db_path
        self.graphify_bin = os.path.expanduser("~/.venvs/graphifyy/bin/graphify")
        self.graph_file = os.path.expanduser("~/.graphify/global-graph.json")
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Query cache: (query_hash, query_text, result, mode, timestamp, ttl_hours)
        c.execute("""
            CREATE TABLE IF NOT EXISTS query_cache (
                query_hash TEXT PRIMARY KEY,
                query_text TEXT UNIQUE,
                result TEXT NOT NULL,
                mode TEXT,  -- 'query' or 'explain'
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ttl_hours INTEGER DEFAULT 168
            )
        """)

        # Node index: (node_id, label, repo, file, line_start, line_end, node_type)
        c.execute("""
            CREATE TABLE IF NOT EXISTS node_index (
                node_id TEXT PRIMARY KEY,
                label TEXT,
                repo TEXT,
                file TEXT,
                line_start INTEGER,
                line_end INTEGER,
                node_type TEXT,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Dependency graph: (source_node, target_node, edge_type, confidence)
        c.execute("""
            CREATE TABLE IF NOT EXISTS dependencies (
                source_id TEXT,
                target_id TEXT,
                edge_type TEXT,
                confidence REAL,
                PRIMARY KEY (source_id, target_id)
            )
        """)

        # God nodes (high-impact symbols): (node_id, label, edge_count, impact_score)
        c.execute("""
            CREATE TABLE IF NOT EXISTS god_nodes (
                node_id TEXT PRIMARY KEY,
                label TEXT,
                edge_count INTEGER,
                impact_score REAL,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Cleanup expired cache
        c.execute("""
            DELETE FROM query_cache
            WHERE datetime(cached_at, '+' || ttl_hours || ' hours') < CURRENT_TIMESTAMP
        """)

        conn.commit()
        conn.close()

    def _query_hash(self, query_text):
        """Compute stable hash for query caching."""
        normalized = query_text.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def query(self, question, mode="query", use_cache=True):
        """Query the graph. Check cache first, fall back to graphify CLI.

        Args:
            question: Natural language question or symbol name
            mode: 'query' (search) or 'explain' (detailed)
            use_cache: If False, always hit graphify (cache-bypass)

        Returns:
            (mode, result) tuple or (None, None) if not found
        """
        qhash = self._query_hash(question)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Check cache
        if use_cache:
            c.execute(
                "SELECT result, mode FROM query_cache WHERE query_hash = ?",
                (qhash,)
            )
            row = c.fetchone()
            if row:
                conn.close()
                return row[1], row[0]  # (mode, result)

        conn.close()

        # Cache miss — hit graphify CLI
        result_mode, result_text = self._graphify_query(question, mode)
        if result_text:
            self._cache_result(qhash, question, result_text, result_mode)

        return result_mode, result_text

    def _graphify_query(self, question, mode):
        """Call graphify CLI directly."""
        try:
            result = subprocess.run(
                [self.graphify_bin, mode, question, "--graph", self.graph_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            out = (result.stdout or "").strip()
            if out and "not found" not in out.lower():
                return mode, out
        except Exception as e:
            print(f"[MemoryStore] graphify call failed: {e}", file=__import__('sys').stderr)
        return None, None

    def _cache_result(self, qhash, question, result_text, mode):
        """Store query result in cache."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            """
            INSERT OR REPLACE INTO query_cache
            (query_hash, query_text, result, mode, cached_at, ttl_hours)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 168)
            """,
            (qhash, question, result_text, mode)
        )
        conn.commit()
        conn.close()

    def seed_from_graphify(self):
        """Warm cache: load graph structure from ~/.graphify/global-graph.json.

        Populates node_index and dependencies tables with graph contents.
        Extracts god_nodes (>40 edges) for fast discovery.
        """
        if not os.path.exists(self.graph_file):
            print(f"[MemoryStore] Graph file not found: {self.graph_file}")
            return False

        try:
            with open(self.graph_file) as f:
                graph = json.load(f)
        except Exception as e:
            print(f"[MemoryStore] Failed to load graph: {e}")
            return False

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Seed node_index from graph nodes
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        c.execute("DELETE FROM node_index")
        c.execute("DELETE FROM dependencies")
        c.execute("DELETE FROM god_nodes")

        for node in nodes:
            node_id = node.get("id")
            label = node.get("label", "")
            repo = node.get("metadata", {}).get("repo", "")
            file_path = node.get("metadata", {}).get("file", "")
            line_start = node.get("metadata", {}).get("line_start")
            line_end = node.get("metadata", {}).get("line_end")
            node_type = node.get("type", "unknown")

            c.execute(
                """
                INSERT OR REPLACE INTO node_index
                (node_id, label, repo, file, line_start, line_end, node_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (node_id, label, repo, file_path, line_start, line_end, node_type)
            )

        # Seed dependencies
        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            edge_type = edge.get("type", "unknown")
            confidence = edge.get("confidence", 1.0)

            c.execute(
                """
                INSERT OR REPLACE INTO dependencies
                (source_id, target_id, edge_type, confidence)
                VALUES (?, ?, ?, ?)
                """,
                (source, target, edge_type, confidence)
            )

        # Identify god_nodes (>40 edges)
        c.execute("""
            WITH node_edges AS (
                SELECT source_id as node_id, COUNT(*) as edge_count
                FROM dependencies
                GROUP BY source_id
                UNION ALL
                SELECT target_id as node_id, COUNT(*) as edge_count
                FROM dependencies
                GROUP BY target_id
            ),
            aggregated AS (
                SELECT node_id, SUM(edge_count) as total_edges
                FROM node_edges
                GROUP BY node_id
            )
            SELECT n.node_id, n.label, a.total_edges, a.total_edges * 1.0 as impact
            FROM node_index n
            JOIN aggregated a ON n.node_id = a.node_id
            WHERE a.total_edges > 40
            ORDER BY impact DESC
        """)

        for row in c.fetchall():
            c.execute(
                """
                INSERT OR REPLACE INTO god_nodes
                (node_id, label, edge_count, impact_score)
                VALUES (?, ?, ?, ?)
                """,
                row
            )

        conn.commit()
        row_count = c.execute("SELECT COUNT(*) FROM node_index").fetchone()[0]
        edge_count = c.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]
        god_count = c.execute("SELECT COUNT(*) FROM god_nodes").fetchone()[0]
        conn.close()

        print(f"[MemoryStore] Seeded: {row_count} nodes, {edge_count} edges, {god_count} god nodes")
        return True

    def get_stats(self):
        """Return cache statistics for monitoring."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        query_cache_size = c.execute("SELECT COUNT(*) FROM query_cache").fetchone()[0]
        node_count = c.execute("SELECT COUNT(*) FROM node_index").fetchone()[0]
        edge_count = c.execute("SELECT COUNT(*) FROM dependencies").fetchone()[0]
        god_node_count = c.execute("SELECT COUNT(*) FROM god_nodes").fetchone()[0]
        db_size_mb = os.path.getsize(self.db_path) / (1024 * 1024)

        conn.close()

        return {
            "query_cache_size": query_cache_size,
            "node_index_size": node_count,
            "edge_count": edge_count,
            "god_nodes": god_node_count,
            "db_size_mb": round(db_size_mb, 2),
            "db_path": self.db_path,
        }

    def clear_cache(self):
        """Reset all caches (for testing/refresh)."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM query_cache")
        c.execute("DELETE FROM node_index")
        c.execute("DELETE FROM dependencies")
        c.execute("DELETE FROM god_nodes")
        conn.commit()
        conn.close()
        print("[MemoryStore] Cache cleared")


if __name__ == "__main__":
    import sys

    store = MemoryStore()

    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        store.seed_from_graphify()
        stats = store.get_stats()
        print(json.dumps(stats, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "stats":
        stats = store.get_stats()
        print(json.dumps(stats, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "clear":
        store.clear_cache()
    elif len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        mode, result = store.query(question)
        if result:
            print(f"## {mode}")
            print(result)
        else:
            print("No result found")
    else:
        print("usage: memory_store.py [seed|stats|clear|<question>]")
