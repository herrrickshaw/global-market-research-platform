#!/usr/bin/env python3
"""
market_paths.py — one place that answers "where is this dataset?".

WHY THIS EXISTS. On 2026-08-14 the repo-local warehouse was cleaned and migrated
to Dropbox. Four consumers broke, each with its own hardcoded path and its own
unhelpful failure, and every one of them failed SILENTLY behind the mailer's
`|| continuing`:

    strategy_regime_survival.py   max() on an empty glob
    backtest_pe_anomalies.py      pd.concat "No objects to concatenate"
    india_split_adjust.py         the same, one layer down, killing small-cap
    playbook_screener.py          KeyError, downstream of the above

They were found a day later, one at a time, by reading tracebacks. The fix each
time was identical: point at a local cache, fall back loudly. That is a resolver,
and it belongs in one file rather than four.

THE MODEL. Cloud is the record; local is a cache.
  - resolve() returns a local path, materialising it from the cloud if absent.
  - Nothing here deletes. Cleanup is a separate, explicit call (see prune()),
    and it refuses to remove anything it has not verified in the cloud first.
  - A dataset that cannot be resolved raises with the exact rclone command that
    would fix it. Never returns a path that is not there — that is what turned a
    missing directory into "No objects to concatenate" four times over.

Usage:
    from market_paths import resolve
    wh = resolve("ohlcv_in")            # -> Path, guaranteed to exist
    px = sorted(wh.glob("year=*.parquet"))
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

CACHE = Path(os.environ.get(
    "MARKET_CACHE_ROOT", os.path.expanduser("~/.cache/market-warehouse")))

RCLONE = shutil.which("rclone") or "/opt/homebrew/bin/rclone"

# dataset key -> (local subpath under CACHE, cloud source, env override)
#
# Cloud paths are the market-data-archive layout confirmed 2026-08-15. The env
# override is kept per-dataset because the existing consumers already read those
# names — this file is meant to absorb them, not to force a flag-day rename.
DATASETS: dict[str, tuple[str, str, str]] = {
    "ohlcv_in":     ("ohlcv/IN",
                     "dropbox:market-data-archive/current/gmd_warehouse/ohlcv/IN",
                     "MARKET_WH_IN"),
    "ohlcv_adj_in": ("ohlcv_adj/IN",
                     "dropbox:market-data-archive/current/gmd_warehouse/ohlcv_adj/IN",
                     "MARKET_WH_ADJ_IN"),
    "ohlcv":        ("ohlcv",
                     "dropbox:market-data-archive/current/gmd_warehouse/ohlcv",
                     "MARKET_WH"),
}


def _rclone(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([RCLONE, *args], capture_output=True, text=True)


def in_cloud(key: str) -> bool:
    """True if the dataset has objects in the cloud. Listing only — no download."""
    _, remote, _ = DATASETS[key]
    r = _rclone("lsf", remote, "--max-depth", "1")
    return r.returncode == 0 and bool(r.stdout.strip())


def resolve(key: str, fetch: bool = True) -> Path:
    """
    Return a local path for `key`, guaranteed non-empty.

    Materialises from the cloud when the cache is cold. Raises with the fixing
    command rather than returning an empty directory — an empty glob is how all
    four of the 2026-08-14 failures presented, and none of them said why.
    """
    if key not in DATASETS:
        raise KeyError(f"unknown dataset {key!r}; known: {sorted(DATASETS)}")
    sub, remote, env = DATASETS[key]

    override = os.environ.get(env)
    if override:
        p = Path(os.path.expanduser(override))
        if any(p.glob("*")):
            return p
        raise FileNotFoundError(f"{env}={p} is empty or missing")

    local = CACHE / sub
    if local.is_dir() and any(local.iterdir()):
        return local

    if not fetch:
        raise FileNotFoundError(
            f"{key}: nothing at {local} and fetch=False.\n"
            f"  {RCLONE} copy {remote} {local}")

    local.mkdir(parents=True, exist_ok=True)
    r = _rclone("copy", remote, str(local))
    if r.returncode != 0 or not any(local.iterdir()):
        raise FileNotFoundError(
            f"{key}: could not materialise {local} from {remote}.\n"
            f"  rclone said: {(r.stderr or '').strip()[:200]}\n"
            f"  fix with:    {RCLONE} copy {remote} {local}")
    return local


def prune(key: str, keep_years: int = 2) -> list[str]:
    """
    Drop cached year partitions older than `keep_years`, but ONLY after
    confirming the cloud still holds them.

    🔴 VERIFY BEFORE DELETE, ALWAYS. The 2026-08-14 cleanup removed local data
    whose only other copy was a git LFS pointer, and
    IN_screener_only_backup.parquet is gone for good as a result — absent from
    both clouds. Nothing here deletes on the assumption that a backup exists;
    it checks, per file, and skips anything it cannot see in the cloud.
    """
    _, remote, _ = DATASETS[key]
    local = CACHE / DATASETS[key][0]
    if not local.is_dir():
        return []

    listed = _rclone("lsf", remote)
    if listed.returncode != 0:
        raise RuntimeError(f"prune({key}): cannot list {remote} — refusing to delete "
                           f"anything without confirming the cloud copy first")
    remote_files = {ln.strip() for ln in listed.stdout.splitlines() if ln.strip()}

    years = sorted(int(p.stem.split("=")[1]) for p in local.glob("year=*.parquet"))
    doomed = years[:-keep_years] if len(years) > keep_years else []
    removed = []
    for y in doomed:
        name = f"year={y}.parquet"
        if name not in remote_files:
            print(f"  prune({key}): {name} NOT in {remote} — keeping it")
            continue
        (local / name).unlink()
        removed.append(name)
    return removed


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--status":
        print(f"cache root: {CACHE}")
        for k, (sub, remote, env) in DATASETS.items():
            p = CACHE / sub
            n = len(list(p.glob("*"))) if p.is_dir() else 0
            size = sum(f.stat().st_size for f in p.glob("*") if f.is_file()) / 1e6 if n else 0
            print(f"  {k:14} local {n:>3} file(s) {size:>7.0f} MB   cloud: "
                  f"{'present' if in_cloud(k) else 'MISSING'}   env: {env}")
    else:
        print(__doc__)
