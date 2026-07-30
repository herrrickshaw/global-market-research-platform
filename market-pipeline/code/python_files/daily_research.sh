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
# the schedule within a run can be whatever suits the work: correlations and
# indices weekly, backtests monthly, collectors on their own cadence.
#
# 🔴 THIS IS A PARTITION OF THE DAILY RUN, NOT AN INDEPENDENTLY-SCHEDULED JOB.
# It was first given its own fixed-clock cron (08:30 IST), on the assumption
# that daily_mailer.sh --send would always be done by then. That is a guess, not
# a dependency — if --send overran, research started on top of it and
# immediately exited on the lock (a skipped day, not a delayed one); if --send
# finished early, research sat idle for no reason. daily_mailer.sh now launches
# this script itself, in the background, the moment --send actually completes
# (see the bottom of daily_mailer.sh) — so this is chained, not clocked. The
# lock-wait logic below still matters for a manual/ad-hoc invocation of this
# script on its own.
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
  # 🔴 PARALLELIZED 2026-07-30, WITH THE WORKER COUNTS DELIBERATELY SPLIT DOWN.
  # These three ran serially, one after another, each internally threaded
  # (Europe/Japan 10 workers, Korea 10 — daily_research.sh's own invocation
  # overrode Korea's 8 default). Serial execution meant only ONE market's
  # threads ever hit yfinance at once, so peak concurrent connections were ~10
  # regardless of how many markets there were.
  #
  # Running all three markets at once is safe (each writes its own
  # timestamped .xlsx, and ohlcv_cache keys by market — ohlcv_EUROPE.parquet,
  # ohlcv_JAPAN.parquet, ohlcv_KOREA.parquet never touch each other), but
  # simply backgrounding them at their EXISTING worker counts would raise peak
  # concurrent yfinance connections to 10+10+10=30 — three times today's peak,
  # against a data source this repo has already hit real rate-limit failures
  # on (see india_split_adjust.py's fetch_splits retry logic, and the
  # yfinance-collector work earlier today). More parallel HTTP connections to
  # the same throttled endpoint does not reliably mean more throughput.
  #
  # So each market's own thread count is cut roughly in proportion to how many
  # markets now run at once (10/3 ≈ 3-4), holding TOTAL concurrent connections
  # near the old serial peak while trading THREAD parallelism for MARKET
  # parallelism — the actual wall-clock win, without more simultaneous load on
  # yfinance than before. europe's --workers is new this same day (see
  # full_european_market_scan.py): it had no CLI override, the only one of the
  # three that could not be dialed down for this.
  step "[R1-R3] parallel market scans (Europe · Japan · Korea)"
  $PY full_european_market_scan.py --universe data/europe_broad_list.csv \
    --label broad --workers 4 &
  PID_EU=$!
  $PY full_japan_market_scan.py --workers 3 &
  PID_JP=$!
  $PY full_korea_market_scan.py --workers 3 &
  PID_KR=$!
  wait $PID_EU || NOTES+=("Europe: full market scan")
  wait $PID_JP || NOTES+=("Japan: full market scan")
  wait $PID_KR || NOTES+=("Korea: full market scan")

  # ── correlation scans ─────────────────────────────────────────────────────
  # US is weekly by design: its matrix is the largest and changes slowly.
  #
  # 🔴 UPPERCASE, and --output-dir is required. The first version passed lowercase
  # codes and omitted the output dir; argparse rejected all four with a usage
  # message and the run recorded them as failures. The choices are
  # {NSE,US,BSE,JAPAN,KOREA,CHINA,HK,EUROPE} — copied from daily_pipeline.sh
  # rather than guessed, which is what I should have done first.
  #
  # Parallelized alongside the fix, not just after it: market_correlation_scan
  # has no internal worker-thread pool of its own (no --workers flag exists),
  # and by this point in the run each market's ohlcv_cache is warm from the
  # scans above, so this step is mostly local cache reads plus a small re-seed
  # for symbols still lagging — not four markets' worth of fresh yfinance load.
  step "[R4] correlation scans (NSE · Europe · Japan · Korea, parallel)"
  for M in NSE EUROPE JAPAN KOREA; do
    $PY market_correlation_scan.py --market "$M" --output-dir correlation_scan &
    eval "PID_CORR_$M=\$!"
  done
  for M in NSE EUROPE JAPAN KOREA; do
    eval "_pid=\$PID_CORR_$M"
    wait "$_pid" || NOTES+=("correlation: $M")
  done
  if [ "$DOW" = "1" ] || [ "$FORCE_WEEKLY" = "1" ]; then
    step "[R5] correlation scan — US (weekly, Mondays)"
    $PY market_correlation_scan.py --market US --output-dir correlation_scan \
      || NOTES+=("correlation: US")
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

  # ── ops: warehouse + backup ───────────────────────────────────────────────
  # Moved here from daily_pipeline [15]/[16]. The backup is what made that job
  # 9 hours — it has nothing to do with the email and must never be able to
  # delay it. nse_xbrl/xml (98,289 files) is now excluded and carried as a
  # single tar.zst, and the rclone account lock serialises against the other
  # backup script.
  step "[R13] warehouse ingest + ticker freshness ledger"
  $PY bhavcopy_raw_archive.py || NOTES+=("ingest: raw bhavcopy archive")
  /usr/bin/python3 /Users/umashankar/scripts/bhavcopy_to_db.py --incremental \
    || NOTES+=("ingest: bhavcopy incremental")
  /usr/bin/python3 /Users/umashankar/scripts/bhavcopy_to_db.py \
    --to-postgres "dbname=market_data host=/tmp user=umashankar" \
    || NOTES+=("ingest: bhavcopy -> postgres")
  /usr/bin/python3 /Users/umashankar/scripts/warehouse_ohlcv_sync.py --apply \
    || NOTES+=("ingest: warehouse ohlcv parquet sync")
  /usr/bin/python3 /Users/umashankar/scripts/market_ingest.py \
    || NOTES+=("ingest: market snapshots")
  mkdir -p reports
  /usr/bin/python3 /Users/umashankar/scripts/market_ingest.py \
    --csv "$PWD/reports/ticker_freshness.csv" || NOTES+=("ingest: freshness csv")

  step "[R14] cloud backup (rclone -> Dropbox)"
  /Users/umashankar/scripts/cloud_backup.sh || NOTES+=("cloud: rclone backup")

  if [ ${#NOTES[@]} -gt 0 ]; then
    # A NOTE, not an alert. Nothing here gates an email, and mixing these into
    # the brief's alert is what made "the daily brief failed" mean a rainfall
    # refresh had errored.
    echo "[NOTES] ${#NOTES[@]} research step(s) had issues: ${NOTES[*]}"
  fi
  echo "=== done $(date) ==="
} 2>&1 | tee -a "$LOG"
