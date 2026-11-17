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
    #
    # 🔴 GATE ONLY WHAT THE SCANS ACTUALLY READ. This used to also gate
    # us_list.csv (min 3000), japan_list.csv (min 2000) and korea_list.csv
    # (min 1500) — three files the daily pipeline does not open:
    #
    #   US  → full_us_market_scan.py:136 pulls NASDAQ/NYSE from the NASDAQ
    #         trader FTP and caches it at us_full_scan/.symbols_cache.json
    #   JP  → full_japan_market_scan.py:207 build_ticker_universe() (JPX/kabupy)
    #   KR  → full_korea_market_scan.py:168 build_krx_universe() (FinanceDataReader)
    #
    # japan_list.csv and korea_list.csv do not exist on disk at all and
    # us_list.csv is a 221-byte stub, so all three WARNed on EVERY run while
    # the scans they supposedly guarded covered 5,852 / 2,930 / 2,537 names
    # normally. A gate that always fires is worse than no gate: it trains the
    # operator to skim past the pre-flight block, which is where a REAL input
    # failure would appear. (Those CSVs are written by run_app.sh for the web
    # app — a different consumer with its own lifecycle. Do not re-add them.)
    UNIVERSES = {  # file → minimum sane rows
        HERE / "data" / "nse_equity_list.csv": 1500,   # watchlist_repair.py:87
        HERE / "data" / "europe_broad_list.csv": 500,  # EU scan --universe arg
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

    # 2b — the US universe the scan DOES read. Absent is fine and not reported:
    # the scan refetches from the FTP on a miss or once SYMBOL_CACHE_TTL (24h)
    # expires. The failure this catches is the one the dead us_list.csv gate was
    # aiming at — a cache present but truncated, which silently scans a handful
    # of names and still writes a workbook that looks like a full run.
    import json
    uscache = HERE / "us_full_scan" / ".symbols_cache.json"
    if uscache.exists():
        try:
            d = json.loads(uscache.read_text())
            n = len(d.get("nasdaq", [])) + len(d.get("nyse", []))
            check("universe: US symbol cache", n >= 5000,
                  f"{n} symbols (min 5000)", warn_only=n > 0)
        except (OSError, ValueError) as e:
            # Unreadable is worth a warn: the scan will refetch, but a corrupt
            # cache means whatever wrote it failed halfway.
            check("universe: US symbol cache", False, f"unreadable: {e}",
                  warn_only=True)

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
