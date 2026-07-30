#!/usr/bin/env python3
"""
pg_client.py — shared Postgres connection + write-safety helpers.

WHY THIS EXISTS
No unified Postgres client existed anywhere in this repo: 21 scripts each
independently ran a `DuckDB ATTACH ... TYPE postgres` handshake (paying the
INSTALL/LOAD/ATTACH cost on every invocation) or a bare `psycopg2.connect(...)`
with hand-copied kwargs. Two of the worst offenders wrote with no transaction
at all — `financial_ratios.py` did `DROP TABLE`-then-`CREATE TABLE AS SELECT`
on `fundamentals.ratios`, a table 5+ other scripts read, and `custom_indices.py`
did `DELETE`-then-separate-`INSERT` on `indices.custom_daily` — so a crash
mid-sequence left either table missing or half-populated for the next reader.
This is the same fragmentation-causes-real-bugs pattern already found and
fixed on the Cassandra side (see cassandra_client.py and the
`fundamentals_source` mislabeling bug it traced back to).

WHERE THIS LIVES, AND WHY
Sibling to data_registry.py and warehouse_common.py in this same flat script
directory — every real consumer (financial_ratios.py, custom_indices.py,
load_ohlcv_to_warehouse.py, ...) already does a bare `import data_registry`/
`import warehouse_common` from here, no path plumbing needed. Putting this in
backend/ would be a genuinely NEW cross-repo import (verified by grep: zero
existing imports of backend/ from market-pipeline/ or scripts/) — reject that.

WHAT THIS MIRRORS
- The connection lifecycle (connect/get_connection/is_available/close, module
  globals + a lock, broad try/except that never raises, log.warning on
  failure) mirrors backend/db/cassandra_client.py's ACTUAL shape — that file
  is a module-level singleton, not a class, and this one is too.
- The bulk-write mechanics (psycopg2.extras.execute_values) reuse the idiom
  already established in warehouse_common.py's resolve_stock_ids()/
  copy_dataframe() rather than inventing a third one.
- ensure_schema() mirrors cassandra_client.py's per-statement DDL-bootstrap
  loop (each statement in its own try/except, "already exists" swallowed) —
  but does NOT centralize schema definitions; each migrated script keeps
  owning its own CREATE SCHEMA/CREATE TABLE strings.

WRITE-SAFETY PRIMITIVES
- replace_table_atomic(): create-into-a-new-name, bulk-load, then swap — all
  in one transaction. Postgres DDL is transactional, so CREATE+INSERT+DROP+
  RENAME committing together means a reader never sees the table missing or
  half-populated; a crash anywhere in the sequence rolls back to the
  untouched previous table. Fixes financial_ratios.py's DROP+CREATE race.
- delete_and_insert(): a DELETE (or TRUNCATE) and the following bulk INSERT
  in one transaction — a crash between the two rolls back the delete too,
  instead of leaving the table empty/partial. Fixes custom_indices.py's
  unguarded DELETE-then-INSERT and market_ingest.py's refresh_symbol_names()
  TRUNCATE-then-INSERT.
"""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import data_registry as _R
    DSN = _R.PG_DSN
except Exception:
    # Same fallback convention already used by financial_ratios.py/custom_indices.py.
    DSN = "dbname=market_data host=/tmp user=umashankar"

log = logging.getLogger(__name__)
_lock = threading.Lock()
_conn = None
_available = False


def connect(dsn: Optional[str] = None) -> bool:
    """Idempotent. Returns True on success, False on failure — never raises."""
    global _conn, _available
    with _lock:
        if _available:
            return True
        try:
            _conn = psycopg2.connect(dsn or DSN)
            with _conn.cursor() as cur:
                cur.execute("SELECT 1")
            _available = True
            log.info("pg_client: connected (%s)", dsn or DSN)
            return True
        except Exception as exc:
            log.warning("pg_client: unavailable (%s) — %s", dsn or DSN, exc)
            _conn = None
            _available = False
            return False


def get_connection():
    return _conn


def is_available() -> bool:
    return _available


def close() -> None:
    global _conn, _available
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
        _conn = None
        _available = False


def to_rows(df, columns: Sequence[str]) -> list:
    """
    Convert a DataFrame's selected columns into row-tuples safe for
    psycopg2 (execute_values / cursor.execute).

    Two things psycopg2 cannot adapt on its own, both found live while
    migrating scripts onto this module:
      - numpy scalar types (numpy.int64, numpy.float64, numpy.bool_) —
        `execute_values` raises "can't adapt type 'numpy.int64'" even
        though the same value as a native Python int works fine. Any
        DataFrame column backed by a numpy integer/float dtype yields
        these via itertuples(), not just explicitly-numpy-typed data.
      - missing-value sentinels other than plain float NaN — pandas'
        nullable dtypes (Int64, string[python], ...) use `pd.NA`, and the
        common `v != v` NaN-detection trick throws `TypeError: boolean
        value of NA is ambiguous` when v is pd.NA instead of a float.
    `pd.isna(v)` handles NaN/None/pd.NA/NaT uniformly; the isinstance
    checks convert numpy's boxed scalars to native types Postgres/psycopg2
    already know how to bind.
    """
    def conv(v):
        if pd.isna(v):
            return None
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, np.floating):
            return float(v)
        if isinstance(v, np.bool_):
            return bool(v)
        return v
    return [tuple(conv(v) for v in r)
            for r in df[list(columns)].itertuples(index=False, name=None)]


def ensure_schema(statements: Sequence[str]) -> None:
    """Run each DDL statement in its own try/except, swallowing 'already
    exists'-type errors — same idempotent-bootstrap idiom as
    cassandra_client.py's per-statement DDL loop. No-op if not connected."""
    if _conn is None:
        return
    for stmt in statements:
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            with _conn.cursor() as cur:
                cur.execute(stmt)
            _conn.commit()
        except Exception:
            _conn.rollback()


def replace_table_atomic(schema: str, table: str, df, column_types: dict) -> int:
    """
    Atomic full-table rebuild: create `{table}__incoming`, bulk-insert `df`,
    then DROP the old table and RENAME the new one into place — one commit,
    so a reader never sees the table dropped-but-not-yet-recreated.

    column_types: {column_name: postgres_type}, in the exact column order to
    write. Returns the number of rows written (0 if df is empty — no-op).
    """
    if _conn is None or df is None or df.empty:
        return 0
    new_table = f"{table}__incoming"
    cols = list(column_types.keys())
    cols_ddl = ", ".join(f'"{c}" {t}' for c, t in column_types.items())
    try:
        with _conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            cur.execute(f'DROP TABLE IF EXISTS "{schema}"."{new_table}"')
            cur.execute(f'CREATE TABLE "{schema}"."{new_table}" ({cols_ddl})')
        with _conn.cursor() as cur:
            rows = to_rows(df, cols)
            psycopg2.extras.execute_values(
                cur,
                f'INSERT INTO "{schema}"."{new_table}" ({", ".join(cols)}) VALUES %s',
                rows,
            )
        with _conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{schema}"."{table}"')
            cur.execute(f'ALTER TABLE "{schema}"."{new_table}" RENAME TO "{table}"')
        _conn.commit()
        return len(rows)
    except Exception:
        _conn.rollback()
        raise


def delete_and_insert(
    schema: str,
    table: str,
    delete_sql: str,
    delete_params: Sequence,
    rows: Sequence[tuple],
    columns: Sequence[str],
    truncate: bool = False,
) -> int:
    """
    Single transaction wrapping a DELETE (or TRUNCATE) and the following bulk
    INSERT — a crash between the two rolls back the delete too, instead of
    leaving the table empty/partial.

    Pass truncate=True to TRUNCATE the whole table instead of a WHERE-scoped
    DELETE (delete_sql/delete_params are ignored in that case). Returns the
    number of rows inserted (0 if `rows` is empty — the delete still runs).
    """
    if _conn is None:
        return 0
    try:
        with _conn.cursor() as cur:
            if truncate:
                cur.execute(f'TRUNCATE "{schema}"."{table}"')
            else:
                cur.execute(f'DELETE FROM "{schema}"."{table}" WHERE {delete_sql}', delete_params)
        if rows:
            with _conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    f'INSERT INTO "{schema}"."{table}" ({", ".join(columns)}) VALUES %s',
                    rows,
                )
        _conn.commit()
        return len(rows)
    except Exception:
        _conn.rollback()
        raise


def append_rows(schema: str, table: str, columns: Sequence[str], rows: Sequence[tuple]) -> int:
    """
    Pure append — bulk INSERT only, no delete/truncate. For append-only
    tables (an ingest log, a snapshots history) where delete_and_insert's
    DELETE/TRUNCATE step would be actively wrong (it would erase history
    this table exists to keep). Same execute_values idiom as the other two
    primitives. Returns the number of rows inserted (0 if `rows` is empty).
    """
    if _conn is None or not rows:
        return 0
    try:
        with _conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                f'INSERT INTO "{schema}"."{table}" ({", ".join(columns)}) VALUES %s',
                rows,
            )
        _conn.commit()
        return len(rows)
    except Exception:
        _conn.rollback()
        raise
