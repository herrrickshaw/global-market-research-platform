#!/bin/bash
# watch_overnight_run.sh — one-shot watcher for the next mailer-send +
# chained daily_research.sh cycle, writing a summary report once both
# have completed (or a timeout is hit).
#
# Launched via nohup so it survives independent of any particular Claude
# session — this is a real background OS process, not a scheduled prompt.
#
# Usage: nohup ./watch_overnight_run.sh > /dev/null 2>&1 & disown
set -uo pipefail
cd /Users/umashankar/market-pipeline/code/python_files

TODAY=$(date +%Y%m%d)
REPORT="/Users/umashankar/scripts/overnight_watch_report_${TODAY}.md"
MAILER_LOG="daily_mailer_${TODAY}.log"
RESEARCH_LOG="daily_research_${TODAY}.log"
MAX_WAIT_S=$((10 * 3600))   # 10h ceiling — covers a very late/slow run without running forever
POLL_S=300                  # 5 min

# daily_mailer.sh's log is APPEND-mode and shared by BOTH the --data and
# --send phases (same date-based filename) — today's --data run already
# wrote its own "=== done" hours before --send even starts, so a naive
# `grep -q "=== done"` is a false positive the moment --data finishes.
# The real signal: a "=== done" line whose LINE NUMBER is after the most
# recent "send=1" phase header.
send_phase_done() {
  local hdr done
  hdr=$(grep -n "send=1" "$MAILER_LOG" 2>/dev/null | tail -1 | cut -d: -f1)
  [ -z "$hdr" ] && return 1
  done=$(grep -n "^=== done" "$MAILER_LOG" 2>/dev/null | tail -1 | cut -d: -f1)
  [ -n "$done" ] && [ "$done" -gt "$hdr" ]
}

waited=0
while [ "$waited" -lt "$MAX_WAIT_S" ]; do
  if [ -f "$MAILER_LOG" ] && send_phase_done; then
    # mailer --send done; give the chained daily_research.sh time to appear+finish
    for _ in $(seq 1 $((3 * 3600 / POLL_S))); do   # up to 3h more for research to finish
      if [ -f "$RESEARCH_LOG" ] && grep -q "^=== done" "$RESEARCH_LOG" 2>/dev/null; then
        break 2
      fi
      sleep "$POLL_S"; waited=$((waited + POLL_S))
    done
    break
  fi
  sleep "$POLL_S"; waited=$((waited + POLL_S))
done

{
  echo "# Overnight run watch — ${TODAY}"
  echo
  echo "Checked $(date)"
  echo
  echo "## daily_mailer.sh (--send)"
  if [ -f "$MAILER_LOG" ]; then
    if send_phase_done; then
      echo "Completed."
      grep -E "sent '|ERROR|Traceback|Exception" "$MAILER_LOG" | tail -20
    else
      echo "⚠️ Log exists but no completion marker found — may still be running or crashed."
    fi
  else
    echo "⚠️ No log found at $MAILER_LOG — send may not have fired yet."
  fi
  echo
  echo "## daily_research.sh (chained)"
  if [ -f "$RESEARCH_LOG" ]; then
    if grep -q "^=== done" "$RESEARCH_LOG"; then
      echo "Completed."
      if grep -q "^\[NOTES\]" "$RESEARCH_LOG"; then
        echo
        echo "Issues reported:"
        grep "^\[NOTES\]" "$RESEARCH_LOG"
      else
        echo "No [NOTES] failures reported."
      fi
    else
      echo "⚠️ Log exists but no completion marker found — may still be running or crashed."
    fi
  else
    echo "⚠️ No log found at $RESEARCH_LOG — research chain may not have fired/completed yet."
  fi
  echo
  echo "## Real errors/tracebacks across both logs"
  grep -hE "Traceback|Error:|ERROR|CRITICAL" "$MAILER_LOG" "$RESEARCH_LOG" 2>/dev/null \
    | grep -viE "YFRateLimitError|HTTP Error 404|HTTP Error 401" \
    | sort -u | head -40
  echo
  echo "## system_state snapshot (new [R15] step, if research completed)"
  ./.venv/bin/python3 -c "
import system_state as S
snaps = S.all_data_snapshots()
stale = [s for s in snaps if s['status'] in ('STALE','MISSING')]
print(f'{len(snaps)} datasets snapshotted, {len(stale)} stale/missing')
for s in stale[:10]:
    print(f\"  {s['status']:8s} {s['dataset_key']}\")
conns = S.connection_status()
for c in conns:
    print(f\"  connection {c['target']}: {'OK' if c['available'] else 'DOWN'} (checked {c['checked_at']})\")
" 2>&1
} > "$REPORT"

echo "Report written to $REPORT"
