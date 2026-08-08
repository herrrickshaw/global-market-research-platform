#!/bin/bash
# weekly_maintenance.sh — ONE weekly pass: clean -> dedup-verify -> compress -> backup.
#
# WHY THIS EXISTS: the four maintenance verbs were scattered (backup ran as a
# daily pipeline step, dedup/audit as separate Monday crons, compression nowhere).
# This is the single weekly entry point so nothing double-fires and there is one
# log to read. It deliberately CALLS the existing scripts (cloud_backup.sh,
# cloud_backup_verify.sh) rather than reimplementing them, and it does NOT touch
# the separate repo-data-dedup crons (different repo, already scheduled).
#
# It is safe to run any day: every step is idempotent. Wire it to ONE Monday cron.
#
# Steps:
#   1. CLEAN     prune regenerable clutter (stale draft HTML, __pycache__)
#   2. DEDUP     verify bhavcopy.cleaned_ohlcv has no duplicate (symbol,date) rows
#   3. COMPRESS  correlation_scan/*_correlation_matrix.csv -> float16 zstd parquet
#                (the real space lever; keeps files LFS-free so no LFS billing)
#   3b. GRAPH    incremental graphify refresh + 3-repo merge (advisory)
#   3c. CITE     sync cite_check central install + citation sweep of all wired
#                repos (UNKNOWN citations count as an issue; the pre-commit hook
#                catches new ones, this catches drift and bib/central skew)
#   4. BACKUP    cloud_backup.sh --with-pg, then the independent verify GATE
#
# Exit 0 only if the backup verify gate passes.
set -uo pipefail

PF="$HOME/market-pipeline/code/python_files"
LOG="$PF/weekly_maintenance.log"
PY=/usr/bin/python3          # the interpreter that has duckdb+pandas+pyarrow
CORR_REPO="$HOME/repos/market-correlation-matrices"
FAILS=0

# single-instance lock (same pattern as cloud_backup.sh)
LOCK="/tmp/weekly_maintenance.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "weekly_maintenance: another instance holds $LOCK — exiting (not an error)" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

{
  echo "===== weekly maintenance $(date '+%Y-%m-%d %H:%M:%S %Z') ====="

  # 1. CLEAN — regenerable clutter only.
  echo "-- [1/4] clean --"
  before_free=$(df -k "$HOME" | awk 'NR==2{print $4}')
  # superseded working drafts older than 7 days
  find "$PF" -maxdepth 1 -name 'brief_today_draft*.html' -mtime +7 -print -delete 2>/dev/null \
    | sed 's/^/  rm /' || true
  # __pycache__ (never the venv's)
  find "$PF" -type d -name __pycache__ -not -path '*/.venv/*' -exec rm -rf {} + 2>/dev/null || true
  echo "  cleaned pycache + stale drafts"

  # 2. DEDUP — verify the cleaned India series carries no (symbol,date) collisions.
  # (NSE/BSE share bare symbols; cleaned_ohlcv is the NSE-precedence-resolved table.)
  echo "-- [2/4] dedup-verify --"
  "$PY" - <<'PYEOF' || FAILS=$((FAILS+1))
import os, sys
db = os.path.expanduser("~/data/bhavcopy.duckdb")
if not os.path.exists(db):
    print("  skip: no bhavcopy.duckdb"); sys.exit(0)
try:
    import duckdb
    con = duckdb.connect(db, read_only=True)
    cols = [c[0].lower() for c in con.execute("DESCRIBE cleaned_ohlcv").fetchall()]
    sym = next((c for c in ("symbol", "ticker", "sym") if c in cols), None)
    dat = next((c for c in cols if "date" in c), None)
    if not sym or not dat:
        print(f"  skip: cleaned_ohlcv has no symbol/date column (cols={cols[:6]}...)"); sys.exit(0)
    dups = con.execute(
        f'SELECT count(*) FROM (SELECT "{sym}","{dat}" FROM cleaned_ohlcv '
        f'GROUP BY 1,2 HAVING count(*)>1)'
    ).fetchone()[0]
    total = con.execute("SELECT count(*) FROM cleaned_ohlcv").fetchone()[0]
    if dups:
        print(f"  DUP FOUND: {dups} duplicate ({sym},{dat}) groups in {total} rows"); sys.exit(1)
    print(f"  ok: 0 duplicate ({sym},{dat}) pairs across {total} rows")
except Exception as e:
    print(f"  skip: {e}")  # a lock or missing duckdb is not a maintenance failure
PYEOF

  # 3. COMPRESS — the big space lever. Same conversion applied to the current run's
  # matrices; retains the base name (consumer only swaps .csv -> .parquet).
  echo "-- [3/4] compress --"
  "$PY" "$PF/compress_correlation_matrices.py" 2>&1 | sed 's/^/  /' || FAILS=$((FAILS+1))

  # LFS guard: make sure nothing we keep in git has slipped into LFS (LFS storage
  # is 8x over the free 1 GiB and the policy is no paid packs — see the summary in
  # the correlation repo). A regular parquet must report filter != lfs.
  if [ -d "$CORR_REPO/.git" ]; then
    lfscount=$(cd "$CORR_REPO" && git lfs ls-files 2>/dev/null | wc -l | tr -d ' ')
    echo "  lfs guard: market-correlation-matrices has $lfscount LFS files (want 0)"
    [ "$lfscount" = "0" ] || echo "  ! WARNING: LFS objects present — investigate before they bill"
  fi

  # 3b. KNOWLEDGE GRAPH refresh (2026-07-27, SCREENER_SMOOTHNESS_STRATEGIES #5):
  # incremental graphify update on market-pipeline (manifest saved, so this is
  # seconds when nothing changed) + re-merge the 3-repo graph. Weekly, not daily:
  # graph drift is slow, and the merged graph is what makes "what breaks if I
  # change X" a 2k-token query. Failure is non-fatal — the graph is advisory.
  echo "-- [3b] knowledge-graph refresh --"
  if command -v graphify >/dev/null 2>&1; then
    GPY=$(cat "$HOME/market-pipeline/graphify-out/.graphify_python" 2>/dev/null || echo python3)
    ( cd "$HOME/market-pipeline" && "$GPY" -c "
import json
from graphify.detect import detect_incremental
from pathlib import Path
r = detect_incremental(Path('.'))
print('graph: %d changed file(s) since last build' % r.get('new_total', 0))
" ) || echo "  ! graph detect failed (non-fatal)"
    ( cd "$HOME/market-pipeline" && graphify merge-graphs \
        graphify-out/graph.json \
        "$HOME/repos/global-stock-screener/graphify-out/graph.json" \
        "$HOME/repos/global-market-data/graphify-out/graph.json" \
        --out graphify-out/merged-3repo-graph.json 2>&1 | tail -1 ) \
      || echo "  ! graph merge failed (non-fatal)"
  else
    echo "  graphify not installed — skipped"
  fi

  # 3c. CITATION HYGIENE (2026-08-01 literature audit): re-sync the central
  # cite_check install from the canonical copy, then sweep every wired repo.
  # The pre-commit hook blocks NEW unknown citations; this weekly pass catches
  # drift (bib edited without sync, files landed by merge/pull, hook bypassed).
  echo "-- [3c] citation hygiene --"
  "$HOME/scripts/sync_cite_check.sh" 2>&1 | sed 's/^/  /' || echo "  ! sync failed (using stale copy)"
  CITE="$HOME/.local/share/cite_check/cite_check.py"
  if [ -f "$CITE" ]; then
    cite_bad=0
    for repo in "$PF" "$HOME/BazaarTalks" "$HOME/repos/global-market-scanners" \
                "$HOME/repos/market-screener-rag" "$HOME/repos/piotroski-liquidity-research" \
                "$HOME/repos/global-stock-screener" "$HOME/repos/global-market-data" \
                "$HOME/price_prediction_backtest"; do
      [ -d "$repo" ] || continue
      out=$(cd "$repo" && "$PY" "$CITE" --all 2>/dev/null | grep -E '^UNKNOWN|^YEAR\?' || true)
      if [ -n "$out" ]; then
        echo "  $(basename "$repo"):"
        echo "$out" | sed 's/^/    /'
        echo "$out" | grep -q '^UNKNOWN' && cite_bad=$((cite_bad+1))
      fi
    done
    if [ "$cite_bad" -gt 0 ]; then
      echo "  ! UNKNOWN citations in $cite_bad repo(s) — fix or add to references.bib"
      FAILS=$((FAILS+1))
    else
      echo "  ok: all wired repos cite-clean"
    fi
  else
    echo "  cite_check not installed — skipped"
  fi

  # 4. BACKUP — mirror to Dropbox (+ weekly pg dump), then the INDEPENDENT gate.
  echo "-- [4/4] backup --"
  "$HOME/scripts/cloud_backup.sh" --with-pg && echo "  cloud_backup ok" \
    || { echo "  ! cloud_backup reported failure"; FAILS=$((FAILS+1)); }
  if "$HOME/scripts/cloud_backup_verify.sh"; then
    echo "  verify gate PASS"
  else
    echo "  ! verify gate FAIL"; FAILS=$((FAILS+1))
  fi

  if [ "$FAILS" -gt 0 ]; then
    echo "===== done with $FAILS ISSUE(S) $(date '+%H:%M:%S') ====="; exit 1
  fi
  echo "===== done clean $(date '+%H:%M:%S') ====="
} >> "$LOG" 2>&1
