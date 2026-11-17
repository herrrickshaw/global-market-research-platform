#!/bin/bash
# snapshot_quotes_daily.sh — append today's serving row for every market to
# herrrickshaw.stock_quotes_history.
#
# WHY THIS MATTERS MORE THAN IT LOOKS. stock_quotes holds ONE row per ticker,
# overwritten in place. Every ratio the platform reasons about — pe, pb,
# debt_to_equity, roe, the new value/quality ranks — is therefore a spot reading
# with no yesterday. "Is this stock getting cheaper or has it always been cheap?"
# is currently unanswerable, and no amount of later work can backfill it: the
# previous value is simply gone the moment the next fetch lands.
#
# 🔴 SO THE COST OF NOT RUNNING THIS IS PERMANENT. fundamentals.india_pe_daily
# already proves the value of the pattern — 1.98M rows of P/E with z-scores back
# to 2019, which is what makes the sector-relative screen possible at all. This
# extends that to every ratio and every market.
#
# TIMING. 07:15 IST, after the 03:00 data phase and the ~06:39 mailer. Snapshot
# AFTER the collector writes, or the row captured is yesterday's — and
# snapshot_market's own max_age_days=2 guard would then start skipping rows,
# which reads as "no data" rather than "ran too early".
#
# Idempotent per (market, ticker, day): a re-run overwrites that day's row.
set -uo pipefail

PY="$HOME/market-pipeline/code/python_files/.venv/bin/python"
LOG="$HOME/repos/repo-data-dedup/state/snapshot_quotes.log"
mkdir -p "$(dirname "$LOG")"

# caffeinate: the 2026-08-15 incident (E-010) was a scheduled job sleeping, not
# failing — 37 sleep events inside one run window. -w waits on this shell's pid.
exec 1>>"$LOG" 2>&1
echo "=== snapshot $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
caffeinate -i -m -w "$$" &

"$PY" - <<'PYEOF'
import sys, os, datetime as dt
sys.path.insert(0, os.path.expanduser("~/backend"))
from db import cassandra_client as cass
from db.quote_updater import snapshot_market

if not cass.connect():
    print("  🔴 Cassandra unreachable — nothing snapshotted, and today is lost")
    raise SystemExit(1)

total, failed = 0, []
for m in ("india", "us", "europe", "japan", "korea"):
    try:
        n = snapshot_market(m)
        total += n
        print(f"  {m:<8} {n:>6} rows")
    except Exception as e:                                    # noqa: BLE001
        failed.append(m)
        print(f"  {m:<8} FAILED {type(e).__name__}: {str(e)[:120]}")

print(f"  total {total:,} rows for {dt.date.today()}")
# A partial snapshot is still worth keeping, but it must not read as a clean run.
raise SystemExit(0 if not failed else 1)
PYEOF
rc=$?
echo "done $(date '+%H:%M') rc=$rc"
exit $rc
