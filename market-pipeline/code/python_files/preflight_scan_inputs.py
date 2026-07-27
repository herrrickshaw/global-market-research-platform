#!/usr/bin/env python3
"""
preflight_scan_inputs.py — fail BEFORE compute, not downstream in the mailer.

Pipeline step [0b]. Applies the ETL quality-gate pattern to every scan input:
each check asserts an input exists / is non-empty / is fresh enough, and a
failure is reported per-market so daily_pipeline.sh can flag it loudly while
the unaffected markets still run (same guarded-step philosophy as the rest of
the pipeline).

Checks (per docs/SCREENER_SMOOTHNESS_STRATEGIES.md quick-win #4→1):
  1. cache dirs exist AND are writable (the sentiment-cache class of crash)
  2. universe lists exist with a sane row count (scan of 12 rows = wiped list)
  3. bhavcopy store freshness: max TradDt within N calendar days (India)
  4. Postgres reachable (warehouse ingest + fundamentals joins depend on it)

Exit code = number of failed checks (0 = all green).
"""
from __future__ import annotations
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data_registry as REG

FAILS: list[str] = []
WARNS: list[str] = []


def check(name: str, ok: bool, detail: str = "", warn_only: bool = False):
    tag = "ok " if ok else ("WARN" if warn_only else "FAIL")
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        (WARNS if warn_only else FAILS).append(f"{name}: {detail}")


def main() -> int:
    print("[0b] pre-flight: scan inputs")

    # 1 — cache dirs exist + writable
    for name, p in [("MARKET_CACHE", REG.MARKET_CACHE),
                    ("sentiment cache dir", HERE / "market_cache")]:
        p = Path(p)
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".preflight_probe"
        try:
            probe.write_text("x"); probe.unlink()
            check(f"dir writable: {name}", True)
        except OSError as e:
            check(f"dir writable: {name}", False, f"{p}: {e}")

    # 2 — universe lists non-trivial (a wiped/truncated list = half-empty scan)
    UNIVERSES = {  # file → minimum sane rows
        HERE / "data" / "us_list.csv": 3000,
        HERE / "data" / "japan_list.csv": 2000,
        HERE / "data" / "korea_list.csv": 1500,
        HERE / "data" / "nse_equity_list.csv": 1500,
        HERE / "data" / "europe_broad_list.csv": 500,
    }
    for f, min_rows in UNIVERSES.items():
        if not f.exists():
            check(f"universe: {f.name}", False, "missing", warn_only=True)
            continue
        try:
            n = sum(1 for _ in open(f, "rb")) - 1
            check(f"universe: {f.name}", n >= min_rows, f"{n} rows (min {min_rows})",
                  warn_only=n > 0)   # tiny-but-present = warn; empty = fail
        except OSError as e:
            check(f"universe: {f.name}", False, str(e))

    # 3 — bhavcopy store freshness (India scans read it directly)
    try:
        nse = Path(REG.BHAV_CACHE) / "nse.parquet" if hasattr(REG, "BHAV_CACHE") else None
        cands = [p for p in [nse, HERE / "bhavcopy_store" / "nse.parquet"]
                 if p and p.exists()]
        if cands:
            d = pd.read_parquet(cands[0], columns=["TradDt"])
            mx = pd.to_datetime(d["TradDt"]).max().date()
            stale = (date.today() - mx).days
            check("bhavcopy freshness", stale <= 5, f"max TradDt {mx} ({stale}d old)",
                  warn_only=stale <= 10)
        else:
            check("bhavcopy freshness", False, "nse.parquet not found", warn_only=True)
    except Exception as e:
        check("bhavcopy freshness", False, str(e), warn_only=True)

    # 4 — Postgres reachable (warehouse ingest + fundamentals joins)
    r = subprocess.run(["psql", "-d", "market_data", "-t", "-c", "SELECT 1"],
                       capture_output=True, text=True, timeout=15)
    check("postgres market_data", r.returncode == 0,
          (r.stderr or "").strip()[:80], warn_only=True)

    print(f"  pre-flight: {len(FAILS)} fail, {len(WARNS)} warn")
    return len(FAILS)


if __name__ == "__main__":
    sys.exit(main())
