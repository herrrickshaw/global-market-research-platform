#!/usr/bin/env python3
"""
system_state.py — last-known-state persistence layer.

WHY THIS EXISTS
───────────────
Nothing in this repo persists a queryable answer to "what do we last know
about X" across five things that matter — data freshness, analysis runs,
data sources, data locations, connection health. Pieces of each already
exist, scattered:

  * data_index.py's assess() computes live freshness over data_registry's
    Dataset list every run — and throws the answer away the moment the
    process exits. Nothing remembers yesterday's read.
  * completeness_graph.py's inventory() node already measures every source
    it can reach (row counts, spans, staleness) but only ever renders
    reports/completeness_graph.md — no persistence of the audit itself,
    and its own source list (PG_SOURCES, 13 hardcoded tuples) is exactly
    the kind of duplicated-list-goes-stale problem already fixed twice
    this session (Cassandra access via cassandra_client.py, cross-repo
    paths via repo_registry.py).
  * tool_registry.py's run_analysis()/run_screener()/run_all_screeners()
    execute and return a value with ZERO persistence anywhere — confirmed
    by direct read. Nothing records that an analysis ran, when, or what
    it found.
  * Nothing persists connection health at all — pg_client.is_available()
    and cassandra_client's equivalent are transient in-process booleans,
    gone when the process exits.

data_registry.py (local dataset paths) and repo_registry.py (cross-repo
paths) already ARE the authoritative location registries — this module
does not duplicate them, it reads them (see list_locations()).

WHERE THIS LIVES, AND WHY
─────────────────────────
Sibling to data_registry.py/repo_registry.py/pg_client.py in the same flat
script directory. Schema `system_state` in the same Postgres database
everything else in this repo already uses, bootstrapped via
pg_client.ensure_schema() — this module is a CONSUMER of pg_client's
connection singleton, never its own. A second parallel connection
singleton would be exactly the fragmentation pg_client.py itself exists
to undo.

CONTRACT
────────
  * Every write function degrades gracefully (never raises) if Postgres
    is unavailable — persistence must never break the analysis/audit/gate
    that would otherwise have succeeded, matching pg_client.py's and
    tool_registry.py's own defensive style.
  * Consumers that must stay stdlib-only (data_index.py explicitly says so
    in its own header, since it runs under two different interpreters)
    import this module LAZILY, inside the one optional code path that
    needs it — never at module load time.

Usage:
  python3 system_state.py --status
  python3 system_state.py --category data
  python3 system_state.py --check-connections
  python3 system_state.py --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pg_client

DDL = """
CREATE SCHEMA IF NOT EXISTS "system_state";
CREATE TABLE IF NOT EXISTS "system_state".data_sources (
  source_key   VARCHAR PRIMARY KEY,
  kind         VARCHAR NOT NULL,
  location     VARCHAR NOT NULL,
  date_column  VARCHAR,
  critical     BOOLEAN NOT NULL DEFAULT FALSE,
  cadence      VARCHAR,
  owner_script VARCHAR,
  notes        VARCHAR,
  added_at     TIMESTAMP NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS "system_state".data_snapshots (
  id           BIGSERIAL PRIMARY KEY,
  dataset_key  VARCHAR NOT NULL,
  run_at       TIMESTAMP NOT NULL DEFAULT now(),
  status       VARCHAR NOT NULL,
  rows         BIGINT,
  coverage_pct DOUBLE PRECISION,
  stale_days   INTEGER,
  detail       JSONB
);
CREATE INDEX IF NOT EXISTS ix_data_snapshots_key_time
  ON "system_state".data_snapshots(dataset_key, run_at DESC);
CREATE TABLE IF NOT EXISTS "system_state".analysis_runs (
  id           BIGSERIAL PRIMARY KEY,
  analysis_key VARCHAR NOT NULL,
  run_at       TIMESTAMP NOT NULL DEFAULT now(),
  status       VARCHAR NOT NULL,
  summary      JSONB,
  output_path  VARCHAR,
  duration_s   DOUBLE PRECISION,
  error        VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_analysis_runs_key_time
  ON "system_state".analysis_runs(analysis_key, run_at DESC);
CREATE TABLE IF NOT EXISTS "system_state".connection_health (
  id         BIGSERIAL PRIMARY KEY,
  target     VARCHAR NOT NULL,
  checked_at TIMESTAMP NOT NULL DEFAULT now(),
  available  BOOLEAN NOT NULL,
  latency_ms DOUBLE PRECISION,
  error      VARCHAR,
  checked_by VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_connection_health_target_time
  ON "system_state".connection_health(target, checked_at DESC);
"""

# Read-only view unifying the three per-domain ingest logs (each already
# owned/written by its own collector script — market_ingest.py,
# amfi_nav_collect.py, nse_index_history.py). Confirmed against live
# information_schema.columns before writing this — the three schemas are
# similar but not identical, so `scope` (the market/geography a row is
# about) only exists for market_daily; funds/indices ingest the whole
# domain per run, not a named sub-scope.
VIEW_DDL = """
CREATE OR REPLACE VIEW "system_state".v_ingest_log_unified AS
SELECT 'market_daily' AS domain, run_at, market AS scope,
       rows_appended, total_rows, status, detail
FROM market_daily.ingest_log
UNION ALL
SELECT 'funds' AS domain, run_at, NULL AS scope,
       rows_appended, total_rows, status, detail
FROM funds.ingest_log
UNION ALL
SELECT 'indices' AS domain, run_at, NULL AS scope,
       rows_appended, total_rows, status, detail
FROM indices.ingest_log;
"""


def _ensure() -> bool:
    """Idempotent connect + schema bootstrap. Never raises."""
    if not pg_client.connect():
        return False
    pg_client.ensure_schema([s.strip() for s in DDL.split(";") if s.strip()])
    pg_client.ensure_schema([VIEW_DDL.strip()])
    return True


# ── data sources ─────────────────────────────────────────────────────────────

def list_data_sources(kind: Optional[str] = None) -> list:
    if not _ensure():
        return []
    con = pg_client.get_connection()
    with con.cursor() as cur:
        if kind:
            cur.execute(
                'SELECT source_key, kind, location, date_column, critical, '
                'cadence, owner_script, notes FROM "system_state".data_sources '
                'WHERE kind = %s ORDER BY source_key', (kind,))
        else:
            cur.execute(
                'SELECT source_key, kind, location, date_column, critical, '
                'cadence, owner_script, notes FROM "system_state".data_sources '
                'ORDER BY source_key')
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def register_data_source(source_key: str, kind: str, location: str, *,
                         date_column: Optional[str] = None,
                         critical: bool = False, cadence: Optional[str] = None,
                         owner_script: Optional[str] = None,
                         notes: Optional[str] = None) -> None:
    """Insert or update one data-source registration. Never raises."""
    if not _ensure():
        return
    con = pg_client.get_connection()
    try:
        with con.cursor() as cur:
            cur.execute(
                'INSERT INTO "system_state".data_sources '
                '(source_key, kind, location, date_column, critical, cadence, '
                ' owner_script, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) '
                'ON CONFLICT (source_key) DO UPDATE SET '
                'kind = EXCLUDED.kind, location = EXCLUDED.location, '
                'date_column = EXCLUDED.date_column, critical = EXCLUDED.critical, '
                'cadence = EXCLUDED.cadence, owner_script = EXCLUDED.owner_script, '
                'notes = EXCLUDED.notes',
                (source_key, kind, location, date_column, critical, cadence,
                 owner_script, notes))
        con.commit()
    except Exception:
        con.rollback()


# ── data locations (no new table — merges the existing registries) ──────────

def list_locations() -> list:
    """Pure in-process merge of data_registry.DATASETS + repo_registry's
    cross-repo paths + any local_file/local_dir data_sources rows.
    Deliberately no new table — data_registry.py/repo_registry.py already
    are the authoritative registries."""
    out = []
    try:
        import data_registry as _DR
        for d in _DR.DATASETS:
            out.append({"key": d.key, "path": str(d.path), "kind": "local",
                        "writer": d.writer, "section": d.section})
    except Exception:
        pass
    try:
        import repo_registry as _RR
        out.append({"key": "repo.market_pipeline", "path": str(_RR.MARKET_PIPELINE),
                    "kind": "repo_root", "writer": "", "section": ""})
        out.append({"key": "repo.global_market_data", "path": str(_RR.GLOBAL_MARKET_DATA),
                    "kind": "repo_root", "writer": "", "section": ""})
        out.append({"key": "repo.global_stock_screener", "path": str(_RR.GLOBAL_STOCK_SCREENER),
                    "kind": "repo_root", "writer": "", "section": ""})
        out.append({"key": "repo.ohlcv_adj_in", "path": str(_RR.OHLCV_ADJ_IN),
                    "kind": "cross_repo_path", "writer": "price_adjuster.py", "section": ""})
    except Exception:
        pass
    for row in list_data_sources():
        if row["kind"] in ("local_file", "local_dir", "sibling_repo_sqlite"):
            out.append({"key": row["source_key"], "path": row["location"],
                        "kind": row["kind"], "writer": row.get("owner_script") or "",
                        "section": ""})
    return out


# ── data snapshots ────────────────────────────────────────────────────────────

def record_data_snapshot(dataset_key: str, status: str, *, rows: Optional[int] = None,
                         coverage_pct: Optional[float] = None,
                         stale_days: Optional[int] = None, detail=None) -> None:
    if not _ensure():
        return
    con = pg_client.get_connection()
    try:
        with con.cursor() as cur:
            cur.execute(
                'INSERT INTO "system_state".data_snapshots '
                '(dataset_key, status, rows, coverage_pct, stale_days, detail) '
                'VALUES (%s,%s,%s,%s,%s,%s)',
                (dataset_key, status, rows, coverage_pct, stale_days,
                 json.dumps(detail) if detail is not None else None))
        con.commit()
    except Exception:
        con.rollback()


def latest_data_snapshot(dataset_key: str) -> Optional[dict]:
    if not _ensure():
        return None
    con = pg_client.get_connection()
    with con.cursor() as cur:
        cur.execute(
            'SELECT dataset_key, run_at, status, rows, coverage_pct, stale_days, detail '
            'FROM "system_state".data_snapshots WHERE dataset_key = %s '
            'ORDER BY run_at DESC LIMIT 1', (dataset_key,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [c.name for c in cur.description]
        return dict(zip(cols, row))


def all_data_snapshots() -> list:
    """Latest row per dataset_key."""
    if not _ensure():
        return []
    con = pg_client.get_connection()
    with con.cursor() as cur:
        cur.execute(
            'SELECT DISTINCT ON (dataset_key) dataset_key, run_at, status, rows, '
            'coverage_pct, stale_days, detail FROM "system_state".data_snapshots '
            'ORDER BY dataset_key, run_at DESC')
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ── analysis runs ─────────────────────────────────────────────────────────────

def record_analysis_run(analysis_key: str, status: str, *, summary=None,
                        output_path: Optional[str] = None,
                        duration_s: Optional[float] = None,
                        error: Optional[str] = None) -> None:
    if not _ensure():
        return
    con = pg_client.get_connection()
    try:
        with con.cursor() as cur:
            cur.execute(
                'INSERT INTO "system_state".analysis_runs '
                '(analysis_key, status, summary, output_path, duration_s, error) '
                'VALUES (%s,%s,%s,%s,%s,%s)',
                (analysis_key, status,
                 json.dumps(summary, default=str) if summary is not None else None,
                 output_path, duration_s, error))
        con.commit()
    except Exception:
        con.rollback()


def latest_analysis_runs(key: Optional[str] = None, limit: int = 20) -> list:
    if not _ensure():
        return []
    con = pg_client.get_connection()
    with con.cursor() as cur:
        if key:
            cur.execute(
                'SELECT analysis_key, run_at, status, summary, output_path, '
                'duration_s, error FROM "system_state".analysis_runs '
                'WHERE analysis_key = %s ORDER BY run_at DESC LIMIT %s', (key, limit))
        else:
            cur.execute(
                'SELECT analysis_key, run_at, status, summary, output_path, '
                'duration_s, error FROM "system_state".analysis_runs '
                'ORDER BY run_at DESC LIMIT %s', (limit,))
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


# ── connection health ─────────────────────────────────────────────────────────

def record_connection_check(target: str, available: bool, *,
                            latency_ms: Optional[float] = None,
                            error: Optional[str] = None,
                            checked_by: Optional[str] = None) -> None:
    if not _ensure():
        return
    con = pg_client.get_connection()
    try:
        with con.cursor() as cur:
            cur.execute(
                'INSERT INTO "system_state".connection_health '
                '(target, available, latency_ms, error, checked_by) '
                'VALUES (%s,%s,%s,%s,%s)',
                (target, available, latency_ms, error, checked_by))
        con.commit()
    except Exception:
        con.rollback()


def connection_status(target: Optional[str] = None) -> list:
    """Latest row per target."""
    if not _ensure():
        return []
    con = pg_client.get_connection()
    with con.cursor() as cur:
        if target:
            cur.execute(
                'SELECT target, checked_at, available, latency_ms, error, checked_by '
                'FROM "system_state".connection_health WHERE target = %s '
                'ORDER BY checked_at DESC LIMIT 1', (target,))
            rows = cur.fetchall()
        else:
            cur.execute(
                'SELECT DISTINCT ON (target) target, checked_at, available, '
                'latency_ms, error, checked_by FROM "system_state".connection_health '
                'ORDER BY target, checked_at DESC')
            rows = cur.fetchall()
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]


def check_postgres() -> tuple:
    t0 = time.time()
    try:
        ok = pg_client.connect()
        latency = (time.time() - t0) * 1000
        record_connection_check("postgres", ok, latency_ms=latency,
                                checked_by="system_state.py")
        return ok, None
    except Exception as e:                                        # noqa: BLE001
        record_connection_check("postgres", False, error=str(e)[:200],
                                checked_by="system_state.py")
        return False, str(e)


def check_cassandra() -> tuple:
    t0 = time.time()
    try:
        from cassandra.cluster import Cluster
        cl = Cluster(["127.0.0.1"], connect_timeout=8)
        cl.connect("herrrickshaw")
        latency = (time.time() - t0) * 1000
        record_connection_check("cassandra", True, latency_ms=latency,
                                checked_by="system_state.py")
        return True, None
    except Exception as e:                                        # noqa: BLE001
        record_connection_check("cassandra", False, error=str(e)[:200],
                                checked_by="system_state.py")
        return False, str(e)


# ── etl_registry.py bridge (read-only, best-effort) ──────────────────────────

def etl_registry_summary() -> Optional[dict]:
    """Best-effort read of the sibling repo's own ETL/backup-replication
    SQLite store (~/repos/global-market-data/warehouse/etl_registry.sqlite).
    A bridge, not a migration — that store answers a different question
    (file/backup integrity for one repo) than this module does, and a live
    SQLite<->Postgres join would be exactly the cross-engine coupling this
    repo's conventions (one client module per backend) exist to avoid."""
    p = Path.home() / "repos" / "global-market-data" / "warehouse" / "etl_registry.sqlite"
    if not p.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        try:
            cur = con.execute(
                "SELECT run_at, files_checked, missing_local, sha_mismatch, "
                "cloud_missing, dupe_groups, wasted_bytes, stale_sources, result "
                "FROM audits ORDER BY run_at DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return None
            cols = [c[0] for c in cur.description]
            return dict(zip(cols, row))
        finally:
            con.close()
    except Exception:
        return None


# ── generic dispatcher ────────────────────────────────────────────────────────

def get_state(category: str, key: Optional[str] = None):
    if category == "data":
        return latest_data_snapshot(key) if key else all_data_snapshots()
    if category == "analysis":
        return latest_analysis_runs(key)
    if category == "sources":
        return list_data_sources(kind=key)
    if category == "locations":
        return list_locations()
    if category == "connections":
        return connection_status(target=key)
    raise ValueError(f"unknown category: {category}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_status(category: Optional[str], as_json: bool) -> int:
    cats = [category] if category else ["sources", "data", "analysis", "connections", "locations"]
    result = {c: get_state(c) for c in cats}
    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return 0
    for c in cats:
        rows = result[c]
        print(f"\n=== {c.upper()} ({len(rows)}) ===")
        for r in rows[:20]:
            print(f"  {r}")
        if len(rows) > 20:
            print(f"  … {len(rows) - 20} more")
    if not category:
        etl = etl_registry_summary()
        print(f"\n=== SIBLING ETL_REGISTRY (read-only bridge) ===")
        print(f"  {etl}" if etl else "  unavailable (file missing or unreadable)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--category", choices=["data", "analysis", "sources",
                                           "connections", "locations"])
    ap.add_argument("--check-connections", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.check_connections:
        pg_ok, pg_err = check_postgres()
        cass_ok, cass_err = check_cassandra()
        if a.json:
            print(json.dumps({"postgres": {"available": pg_ok, "error": pg_err},
                             "cassandra": {"available": cass_ok, "error": cass_err}}))
        else:
            print(f"  postgres:  {'OK' if pg_ok else 'UNAVAILABLE'}"
                  + (f" — {pg_err}" if pg_err else ""))
            print(f"  cassandra: {'OK' if cass_ok else 'UNAVAILABLE'}"
                  + (f" — {cass_err}" if cass_err else ""))
        return 0

    return _print_status(a.category, a.json)


if __name__ == "__main__":
    sys.exit(main())
