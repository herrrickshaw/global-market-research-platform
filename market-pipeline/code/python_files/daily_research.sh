#!/bin/bash
# daily_research.sh — the work the daily brief does NOT need.
#
# Split out of daily_pipeline.sh on 2026-07-29. That script had grown to 38 steps
# and ~9 hours, of which sending the email was one. Everything here used to run
# between "the brief is ready" and "the job finished" — the brief was built at
# 22:55 and the run ended at 08:08 the next morning.
#
# Two things went wrong with that coupling, and both bit on the same night:
#
#   * A failure anywhere landed in one FAILURES array and one alert, so "the
#     daily brief failed" could mean an IUDX flood-sensor collector erroring, or
#     an annual IMD rainfall refresh. Signal buried in unrelated noise.
#   * The alert fires at the END. The brief's status was determined at 22:55 and
#     announced at 08:08, by which point it was wrong — a fixed problem was still
#     being reported as broken.
#
# Nothing here gates an email, so a failure is a note rather than an alarm, and
# the schedule can be whatever suits the work: correlations and indices weekly,
# backtests monthly, collectors on their own cadence.
#
# 🔴 SCANS FOR THE PARKED MARKETS LIVE HERE. Europe, Japan and Korea are out of
# the brief because their fundamentals cannot support a per-name claim, but they
# are NOT abandoned — the scans keep running so the data stays current and a
# market can be rehabilitated by flipping watchlist_markets.COVERED rather than
# by restarting collection from cold.
#
#   ./daily_research.sh            # everything due today
#   ./daily_research.sh --weekly   # force the weekly block
#   ./daily_research.sh --monthly  # force the monthly block
set -uo pipefail
cd "$(dirname "$0")"

PY="$(dirname "$0")/.venv/bin/python3"
[ -x "$PY" ] || PY=python3
LOG="daily_research_$(date +%Y%m%d).log"
DOW=$(date +%u)          # 1 = Monday
DOM=$(date +%d)

FORCE_WEEKLY=0; FORCE_MONTHLY=0
for a in "$@"; do
  [ "$a" = "--weekly" ]  && FORCE_WEEKLY=1
  [ "$a" = "--monthly" ] && FORCE_MONTHLY=1
done

# Shares the pipeline lock: this writes reports/ and the warehouse, and the
# mailer path reads them. Overlapping runs would have one reading a half-written
# file. Unlike the mailer it WAITS rather than exiting — research work skipped is
# research work lost, whereas a duplicate brief is merely redundant.
LOCKDIR="/tmp/daily_pipeline.lock"
_waited=0
while ! mkdir "$LOCKDIR" 2>/dev/null; do
  _owner="$(cat "$LOCKDIR/pid" 2>/dev/null || echo '')"
  if [ -z "${_owner:-}" ] || ! kill -0 "$_owner" 2>/dev/null; then
    rm -rf "$LOCKDIR"; continue
  fi
  if [ "$_waited" -ge 5400 ]; then
    echo "daily_research: waited 90m on the pipeline lock (pid $_owner) — proceeding"
    break
  fi
  [ "$_waited" = 0 ] && echo "daily_research: waiting for the pipeline lock (pid $_owner)"
  sleep 60; _waited=$((_waited + 60))
done
echo $$ > "$LOCKDIR/pid" 2>/dev/null
trap 'rm -rf "$LOCKDIR"' EXIT INT TERM

step() {
  printf '[STEP] %s %s %s\n' "$(date +%s)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
  echo "$*"
}
NOTES=()

{
  echo "=== daily research $(date) ==="

  # ── parked-market scans: kept current so a market can be re-admitted ───────
  step "[R1] Europe full market scan (17 exchanges)"
  $PY full_european_market_scan.py --universe data/europe_broad_list.csv --label broad \
    || NOTES+=("Europe: full market scan")
  step "[R2] Japan full market scan (TSE)"
  $PY full_japan_market_scan.py --workers 10 || NOTES+=("Japan: full market scan")
  step "[R3] Korea full market scan (KOSPI+KOSDAQ)"
  $PY full_korea_market_scan.py --workers 10 || NOTES+=("Korea: full market scan")

  # ── correlation scans ─────────────────────────────────────────────────────
  # US is weekly by design: its matrix is the largest and changes slowly.
  step "[R4] correlation scans (NSE · Europe · Japan · Korea)"
  for M in nse europe japan korea; do
    $PY market_correlation_scan.py --market "$M" || NOTES+=("correlation: $M")
  done
  if [ "$DOW" = "1" ] || [ "$FORCE_WEEKLY" = "1" ]; then
    step "[R5] correlation scan — US (weekly, Mondays)"
    $PY market_correlation_scan.py --market us || NOTES+=("correlation: us")
  fi

  # ── weekly research ───────────────────────────────────────────────────────
  if [ "$DOW" = "1" ] || [ "$FORCE_WEEKLY" = "1" ]; then
    step "[R6] custom + cluster index level series (weekly)"
    $PY custom_indices.py --build > /dev/null || NOTES+=("indices: custom build")
    step "[R7] paper-track scorecard (weekly)"
    $PY paper_track.py > /dev/null 2>&1 || NOTES+=("paper track")
  fi

  # ── audits ────────────────────────────────────────────────────────────────
  step "[R8] cross-market consistency audit"
  $PY consistency_audit.py || NOTES+=("consistency: cross-market anomaly")
  step "[R9] completeness audit (data · claims · gates · population)"
  $PY completeness_graph.py > /dev/null || NOTES+=("completeness audit")

  # ── monthly backtests ─────────────────────────────────────────────────────
  if [ "$DOM" = "01" ] || [ "$FORCE_MONTHLY" = "1" ]; then
    step "[R10] monthly zone-rule + regime-survival + PE-anomaly backtests"
    $PY backtest_zone_rules.py           > /dev/null || NOTES+=("backtest: zone rules")
    $PY strategy_regime_survival.py      > /dev/null || NOTES+=("backtest: regime survival")
    $PY backtest_pe_anomalies.py         > /dev/null || NOTES+=("backtest: PE anomaly")
    step "[R11] monthly sector-cache rebuild"
    $PY watchlist_digest.py --build-sectors --no-maintain --out /dev/null > /dev/null 2>&1 \
      || NOTES+=("sector cache rebuild")
    step "[R12] monthly bundle validation vs benchmarks"
    $PY bundle_validation.py > /dev/null || NOTES+=("bundle validation")
  fi

  if [ ${#NOTES[@]} -gt 0 ]; then
    # A NOTE, not an alert. Nothing here gates an email, and mixing these into
    # the brief's alert is what made "the daily brief failed" mean a rainfall
    # refresh had errored.
    echo "[NOTES] ${#NOTES[@]} research step(s) had issues: ${NOTES[*]}"
  fi
  echo "=== done $(date) ==="
} 2>&1 | tee -a "$LOG"
