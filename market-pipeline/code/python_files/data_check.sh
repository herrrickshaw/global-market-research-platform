#!/bin/bash
# data_check.sh — every-3-days data sufficiency + quality check.
# Refreshes derived ratios, runs the GE/dbt quality gate, the anti-false-outcome
# sufficiency guard (with trend history + flip detection), and the freshness ledger.
# Writes a dated consolidated summary and appends a one-line status to a running log.
# Scheduled via cron: 0 9 */3 * * (09:00 every 3rd day of the month).
set -uo pipefail
cd /Users/umashankar/market-pipeline/code/python_files || exit 1
PY=/Users/umashankar/market-pipeline/code/python_files/.venv/bin/python3
DATE=$(date +%F)
LOG=reports/data_check.log
OUT=reports/data_check_${DATE}.md

echo "[$(date '+%F %T')] data-check start" >> "$LOG"
fail=()

run() {  # run <label> <script>
  if $PY "$2" >> "$LOG" 2>&1; then echo "  ✅ $1" ; else echo "  ❌ $1" ; fail+=("$1"); fi
}

{
  echo "# Data check — $DATE"
  echo
  echo "Every-3-days sufficiency + quality sweep. Sources: \`data_check.sh\`."
  echo
  echo '```'
  run "ratios rebuilt (6 markets)" build_all_ratios.py
  run "quality gate (GE/dbt expectations)" data_quality.py
  run "sufficiency guard (+ trend history + flips)" data_sufficiency.py
  run "freshness ledger" data_ledger.py
  run "source registry (+ reachability)" source_registry.py
  echo '```'
  echo
  echo "## Current sufficiency verdict"
  echo
  # pull the derived verdict table straight from the freshly-written report
  sed -n '/^| market | fund tickers/,/^$/p' reports/data_sufficiency.md | head -12
  echo
  echo "See \`reports/data_sufficiency.md\`, \`reports/data_quality.md\`, \`reports/data_ledger.md\`"
  echo "for full detail; \`cache_seed/data_sufficiency_history.parquet\` for the coverage trend."
} > "$OUT"

if [ ${#fail[@]} -eq 0 ]; then
  echo "[$(date '+%F %T')] data-check OK -> $OUT" >> "$LOG"
else
  echo "[$(date '+%F %T')] data-check FAILURES: ${fail[*]} -> $OUT" >> "$LOG"
fi
