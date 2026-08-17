#!/usr/bin/env python3
"""
pg_to_parquet.py — a columnar, cloud-queryable mirror of the market_data warehouse.

WHY THIS EXISTS, GIVEN pg_cloud_backup.sh ALREADY RUNS NIGHTLY.
Those are different jobs and neither replaces the other:

    pg_cloud_backup.sh  ->  market_data_<date>.dump   1.87 GB   RESTORES the warehouse
    pg_to_parquet.py    ->  pg_parquet/<schema>/*.parquet       QUERIES the warehouse

A pg_dump is a recovery artifact. To answer one question from it — "what did
RELIANCE close at last Tuesday" — a consumer must install Postgres, restore 18 GB
and then run SQL. That is minutes of wall-clock and 18 GB of disk on every cold
consumer, which is exactly why the warehouse still pins the pipeline to this Mac
even though the dump has been on two clouds for weeks.

Parquet inverts that. DuckDB reads a single column of a single file in place, so
a GitHub runner needing India OHLCV pulls ~1 GB, not 18 GB, and needs no server
at all. That is the difference between "the data is backed up" and "the data is
reachable from anywhere", and only the second one gets the local machine out of
the loop.

🔴 THIS IS A MIRROR, NOT THE RECORD. Postgres stays authoritative. Parquet files
here are immutable per-run snapshots; nothing writes back through them. If the
two ever disagree, Postgres is right and this file is stale — which is why every
export records its source row count and refuses to publish on a mismatch.

VERIFY BEFORE PUBLISH, ALWAYS. Each table's row count is re-read FROM THE WRITTEN
PARQUET and compared against Postgres before anything is uploaded. A truncated
export that still parses is the failure mode that matters here: it would publish
a file that reads fine and silently answers questions wrong. Better to fail loud
and keep yesterday's copy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DB = "market_data"
RCLONE = "/opt/homebrew/bin/rclone"

# Both clouds, because one cloud is one point of failure. Same rationale as
# cloud_backup.sh: Dropbox is the working copy, gdrive the independent one.
REMOTES = (
    "dropbox:market-pipeline-cache/pg_parquet",
    "googledrive:market-data-backup/current/pg_parquet",
)

STAGE = Path(os.environ.get(
    "PG_PARQUET_STAGE",
    "/private/tmp/claude-501/-Users-umashankar/230a0ab3-5c83-49eb-90f4-324f13d9cbba/scratchpad/pgparquet",
))

# zstd over snappy: this is write-once/read-many cold data going over a network,
# so decode speed matters far less than bytes on the wire. Level 9 measured 6.6x
# on fact_screener_signal at 600k rows/s — the compression is not the bottleneck,
# the Postgres read is.
ZSTD_LEVEL = 9


def log(msg: str) -> None:
    print(f"{dt.datetime.now():%H:%M:%S}  {msg}", flush=True)


def psql(sql: str) -> str:
    r = subprocess.run(["psql", "-d", DB, "-tAq", "-v", "ON_ERROR_STOP=1", "-c", sql],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"psql: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def tables() -> list[tuple[str, str]]:
    """Every user table, smallest first.

    Smallest first is deliberate: a credentials/permissions/disk problem surfaces
    on a 1 MB table in two seconds rather than 20 minutes into ohlcv_history.
    """
    out = psql("""
        SELECT schemaname || '|' || relname
          FROM pg_catalog.pg_stat_user_tables
         ORDER BY pg_total_relation_size(relid) ASC""")
    return [tuple(line.split("|", 1)) for line in out.splitlines() if "|" in line]


def export_one(con, schema: str, table: str) -> dict:
    """Export one table and prove the file matches the source before returning."""
    dest = STAGE / schema
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{table}.parquet"

    src_rows = int(psql(f'SELECT count(*) FROM "{schema}"."{table}"'))

    # An empty table still gets a file. A consumer joining against a table that
    # simply is not there fails with a confusing missing-file error; one joining
    # against an empty table gets an empty result, which is the truth.
    t0 = time.time()
    con.execute(
        f"COPY (SELECT * FROM pg.\"{schema}\".\"{table}\") TO '{out}' "
        f"(FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL {ZSTD_LEVEL})")
    secs = time.time() - t0

    # 🔴 Read the count back out of the FILE, not out of the COPY statement's
    # return value. The point is to catch a short write, and a writer's own
    # opinion of how much it wrote cannot detect that.
    got = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    mb = out.stat().st_size / 1048576

    ok = got == src_rows
    log(f"  {schema}.{table:<28} {src_rows:>12,} rows  {mb:>8.1f} MB  {secs:>6.1f}s"
        + ("" if ok else f"  🔴 MISMATCH parquet={got:,}"))
    return {"schema": schema, "table": table, "rows": src_rows, "parquet_rows": got,
            "mb": round(mb, 2), "secs": round(secs, 1), "ok": ok, "path": str(out)}


def upload(results: list[dict]) -> list[dict]:
    """Push the staged tree to both remotes and verify each landed at full size."""
    verified = []
    for remote in REMOTES:
        log(f"uploading -> {remote}")
        r = subprocess.run(
            [RCLONE, "copy", str(STAGE), remote, "--transfers", "4",
             "--checkers", "8", "--stats", "30s", "--stats-one-line"],
            capture_output=True, text=True, timeout=7200)
        if r.returncode != 0:
            log(f"  🔴 rclone rc={r.returncode}: {r.stderr.strip()[-300:]}")
            verified.append({"remote": remote, "ok": False, "err": r.stderr.strip()[-200:]})
            continue

        # Verify by listing, not by trusting rc=0. rclone returns 0 for a
        # transfer it believes succeeded; the question here is whether the bytes
        # are actually on the far side.
        ls = subprocess.run([RCLONE, "lsl", remote], capture_output=True, text=True, timeout=600)
        remote_sizes = {}
        for line in ls.stdout.splitlines():
            parts = line.split(None, 3)
            if len(parts) == 4:
                remote_sizes[parts[3]] = int(parts[0])

        missing, short = [], []
        for res in results:
            rel = f"{res['schema']}/{res['table']}.parquet"
            local = Path(res["path"]).stat().st_size
            if rel not in remote_sizes:
                missing.append(rel)
            elif remote_sizes[rel] != local:
                short.append(f"{rel} ({remote_sizes[rel]} != {local})")
        ok = not missing and not short
        log(f"  {'OK' if ok else '🔴'} {len(results) - len(missing) - len(short)}/{len(results)} verified"
            + (f", missing={missing[:3]}" if missing else "")
            + (f", short={short[:3]}" if short else ""))
        verified.append({"remote": remote, "ok": ok, "missing": missing, "short": short})
    return verified


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", help="comma-separated schema.table list; default = all")
    p.add_argument("--no-upload", action="store_true", help="export and verify locally, skip clouds")
    p.add_argument("--keep-local", action="store_true",
                   help="keep the staged parquet after both clouds verify")
    a = p.parse_args()

    sys.path.insert(0, "")
    try:
        import duckdb
    except ImportError:
        print("duckdb missing — run with ~/market-pipeline/code/python_files/.venv/bin/python",
              file=sys.stderr)
        return 1

    want = set(a.only.split(",")) if a.only else None
    todo = [(s, t) for s, t in tables() if not want or f"{s}.{t}" in want]
    if not todo:
        log("nothing to export")
        return 1

    free_gb = shutil.disk_usage(STAGE.parent if STAGE.exists() else "/").free / 2**30
    log(f"{len(todo)} tables, {free_gb:.1f} GB free at stage")
    if free_gb < 8:
        log("🔴 under 8 GB free — refusing to start rather than fail mid-export")
        return 1

    STAGE.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres;")
    con.execute(f"ATTACH 'dbname={DB}' AS pg (TYPE postgres, READ_ONLY)")

    t0 = time.time()
    results = [export_one(con, s, t) for s, t in todo]
    bad = [r for r in results if not r["ok"]]
    total_mb = sum(r["mb"] for r in results)
    total_rows = sum(r["rows"] for r in results)
    log(f"exported {len(results)} tables, {total_rows:,} rows, {total_mb:.0f} MB "
        f"in {time.time() - t0:.0f}s")

    if bad:
        log(f"🔴 {len(bad)} table(s) failed row-count parity — NOT uploading:")
        for r in bad:
            log(f"    {r['schema']}.{r['table']}: pg={r['rows']:,} parquet={r['parquet_rows']:,}")
        return 1

    manifest = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
                "db": DB, "zstd_level": ZSTD_LEVEL,
                "total_rows": total_rows, "total_mb": round(total_mb, 1),
                "tables": [{k: r[k] for k in ("schema", "table", "rows", "mb")} for r in results]}
    (STAGE / "_manifest.json").write_text(json.dumps(manifest, indent=1))

    if a.no_upload:
        log(f"--no-upload: staged at {STAGE}")
        return 0

    ver = upload(results)
    both = all(v["ok"] for v in ver)
    if both and not a.keep_local:
        # Only after BOTH clouds verify. Deleting on one cloud's word would be
        # exactly the sole-copy hazard this whole migration exists to remove.
        shutil.rmtree(STAGE)
        log("both clouds verified — staged copy removed")
    elif not both:
        log(f"🔴 not verified on every remote — keeping {STAGE}")
    return 0 if both else 1


if __name__ == "__main__":
    sys.exit(main())
