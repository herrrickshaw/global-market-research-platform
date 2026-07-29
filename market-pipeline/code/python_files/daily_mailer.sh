#!/bin/bash
# daily_mailer.sh — build and send the Daily Market Brief. Nothing else.
#
# WHY THIS EXISTS. daily_pipeline.sh had grown to 38 steps and ~9 hours, of which
# the mailer was one step. It also ran five market scans, five correlation scans,
# monthly backtests, warehouse ingest, an rclone cloud backup, an IUDX
# FLOOD-SENSOR collector and an annual IMD RAINFALL refresh. On 2026-07-29 the
# brief was ready at 22:55 and the job did not finish until 08:08 the next
# morning — every one of those 9h13m spent on work the email did not need, with
# the backup alone taking 4h19m.
#
# That coupling is not just slow, it is misleading: a failure in any of those 38
# steps lands in the same FAILURES array and the same alert, so "the daily brief
# failed" has meant a rainfall refresh erroring out. And the reverse — the brief
# being blocked by a stale scan of a market it no longer covers.
#
# So this script does exactly what the email needs, and the research and ops work
# moves to daily_research.sh / daily_ops.sh on their own schedules.
#
# SCOPE: India and US only, matching watchlist_markets.COVERED. Europe, Japan and
# Korea are parked because their fundamentals cannot support a per-name claim
# (quality scores in ratio-named columns — see watchlist_markets.PARKED), so
# scanning them for a brief that will not mention them is pure latency. Their
# scans still run in daily_research.sh, which is where a market gets rehabilitated.
#
#   ./daily_mailer.sh            # data + send in one pass
#   ./daily_mailer.sh --data     # PHASE 1 only: refresh India + US market data
#   ./daily_mailer.sh --send     # PHASE 2 only: screen -> validate -> SEND
#   ./daily_mailer.sh --draft    # everything except the send
#
# 🔴 WHY TWO PHASES, AND WHY THE OLD 00:30 SLOT WAS WRONG. US markets close at
# 16:00 ET = 01:30 IST under EDT, 02:30 IST under EST. The pipeline was scheduled
# at 00:30 IST, so it scanned the US MID-SESSION every single weekday, by
# construction. That is why [13d] kept flagging US drift and why its tolerance
# had to be loosened to 4% — the scan was capturing an intraday price and
# comparing it against a later one. The fix is not a wider tolerance, it is a
# later start.
#
#   PHASE 1 (--data)  03:00 IST — after the US close in BOTH DST regimes, so
#                     India's 15:30 close and the US 16:00 ET close are final.
#   PHASE 2 (--send)  06:30 IST — both markets shut, nothing moving. A reconcile
#                     here compares a settled scan against a settled quote, so a
#                     difference means STALENESS rather than drift, which is the
#                     only condition under which that gate means anything.
#
# Splitting them also means a slow scan cannot delay the brief: phase 1 has three
# and a half hours of slack before phase 2 needs its output.
#
# Expected runtime ~25-40 min for phase 1, ~5 min for phase 2.
set -uo pipefail
cd "$(dirname "$0")"

# Never inherit python3 from the caller's PATH. A manual run from a plain shell
# resolved it to homebrew 3.14 on 2026-07-22: step [0] flagged missing deps,
# every scan died, and the validation gate correctly suppressed the send.
PY="$(dirname "$0")/.venv/bin/python3"
[ -x "$PY" ] || PY=python3
LOG="daily_mailer_$(date +%Y%m%d).log"

# ── single-run lock ──────────────────────────────────────────────────────────
# Shared with daily_pipeline.sh deliberately: both write watchlist.csv, and that
# file is read-modify-write, so a collision does not merge — the second writer
# discards the first's rows entirely while both report success. macOS has no
# flock(1); mkdir is the race-free primitive. A lock whose owner is gone is
# cleared rather than wedging the job forever.
LOCKDIR="/tmp/daily_pipeline.lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  _owner="$(cat "$LOCKDIR/pid" 2>/dev/null || echo '')"
  if [ -n "$_owner" ] && kill -0 "$_owner" 2>/dev/null; then
    echo "daily_mailer: pipeline already running (pid $_owner) — exiting so the"
    echo "two runs do not interleave writes to watchlist.csv."
    exit 0
  fi
  rm -rf "$LOCKDIR"; mkdir "$LOCKDIR" || exit 1
fi
echo $$ > "$LOCKDIR/pid"
trap 'rm -rf "$LOCKDIR"' EXIT INT TERM

step() {
  printf '[STEP] %s %s %s\n' "$(date +%s)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
  echo "$*"
}

# Phase selection. Neither flag = both phases, so a manual run still works.
RUN_DATA=1; RUN_SEND=1; IS_DRAFT=0
for a in "$@"; do
  [ "$a" = "--data" ] && RUN_SEND=0
  [ "$a" = "--send" ] && RUN_DATA=0
  [ "$a" = "--draft" ] && IS_DRAFT=1
done

FAILURES=()
{
  echo "=== daily mailer $(date) · data=$RUN_DATA send=$RUN_SEND ==="

  # ── 1. gates ───────────────────────────────────────────────────────────────
  step "[1/13] dependency check"
  $PY check_deps.py || FAILURES+=("STARTUP: missing required dependencies")

  step "[2/13] pre-flight: scan input gates"
  $PY preflight_scan_inputs.py || FAILURES+=("STARTUP: pre-flight input gate(s) failed")

  if [ "$RUN_DATA" = "1" ]; then
  # ── 2. India ───────────────────────────────────────────────────────────────
  step "[3/13] India EOD refresh (official bhavcopy, incremental)"
  $PY bhavcopy_history.py 400 \
    || { echo "  bhavcopy refresh failed (will use cache)"; FAILURES+=("India: bhavcopy refresh"); }

  step "[4/13] India full screener scan"
  $PY scan_bhavcopy.py \
    || { echo "  scan failed (will use latest cache)"; FAILURES+=("India: full screener scan"); }

  step "[5/13] India combined report (fundamentals + street talk)"
  $PY daily_combined_report.py --market IN --html \
    || { echo "  combined report failed"; FAILURES+=("India: combined report"); }

  step "[6/13] India CCC screen (screener.in) + scrape test"
  $PY -c "import screener_in as s; s.ccc_screen().to_parquet('cache_seed/india_ccc_screen.parquet', index=False)" \
    || { echo "  CCC refresh skipped"; FAILURES+=("India: CCC screen refresh"); }
  $PY test_screener_in.py \
    || { echo "  ⚠️  screener.in CCC test FAILED — CCC section will show n/a"; FAILURES+=("India: CCC scrape test"); }

  # ── 3. US ──────────────────────────────────────────────────────────────────
  step "[7/13] US full market scan (NASDAQ+NYSE, min-price \$2)"
  $PY full_us_market_scan.py --workers 10 --min-price 2 \
    || { echo "  US full market scan failed (continuing)"; FAILURES+=("US: full market scan"); }

  step "[8/13] US combined report (reuses the fresh US scan)"
  $PY daily_combined_report.py --market US --html \
    || { echo "  US combined report failed (continuing)"; FAILURES+=("US: combined report"); }
  fi   # end phase 1

  if [ "$RUN_SEND" = "1" ]; then

  # ── 4. watchlist + screens ─────────────────────────────────────────────────
  step "[9/13] watchlist repair (renames/delists/ETFs + coverage gate)"
  $PY watchlist_repair.py || FAILURES+=("watchlist: repair")

  step "[10/13] screens (value re-rating · playbook · small-cap)"
  $PY screen_value_rerating.py || FAILURES+=("screen: value re-rating")
  $PY playbook_screener.py     || FAILURES+=("screen: playbook")
  $PY smallcap_screener.py --screen || FAILURES+=("screen: small-cap")

  step "[11/13] prediction filter -> tiers -> re-entry ranking"
  $PY prediction_filter.py || FAILURES+=("prediction filter")
  $PY watchlist_tiers.py   || FAILURES+=("watchlist tiers")
  # NOTE: reentry_engine RANKS but no longer injects (--commit required). The
  # forward edge that justified auto-injection measured t=0.06 and was withdrawn
  # 2026-07-29; it stays in the mailer path only to keep the paper-track running.
  $PY reentry_engine.py || FAILURES+=("re-entry ranking")

  step "[12/13] refresh live market regime (zone_regime.json)"
  $PY strategy_regime_survival.py --refresh-regime \
    || echo "  regime refresh failed (continuing)"

  # ── 5. THE SEND GATES ──────────────────────────────────────────────────────
  # Both must pass. They catch different failures and neither subsumes the other:
  # reconcile catches a STALE SCAN (the 2026-07-29 case, where JP/KR carried the
  # previous day's closes on a day both fell 10-15%), while validate_brief checks
  # our numbers against an INDEPENDENT source (screener.in). A brief can be
  # internally consistent and a day old, or fresh and wrong.
  #
  # Only IN and US are reconciled — the parked markets are not scanned here, so
  # reconciling them would compare a stale file against a live quote and block
  # the send over a market the brief does not mention.
  RECONCILE_FAIL=0
  step "[13/13] send gates: price reconcile (IN, US) + brief validation"
  for MKT in IN US; do
    $PY scan_price_reconcile.py --market "$MKT" \
      || { RECONCILE_FAIL=$((RECONCILE_FAIL+1)); echo "  ⚠ $MKT failed price reconcile"; }
  done
  [ "$RECONCILE_FAIL" -gt 0 ] && FAILURES+=("reconcile: $RECONCILE_FAIL market(s) stale scan prices")

  VALIDATE_OK=1
  $PY validate_brief.py --sample 6 && VALIDATE_OK=0

  # ── 6. send ────────────────────────────────────────────────────────────────
  if [ "$VALIDATE_OK" -eq 0 ] && [ "$RECONCILE_FAIL" -eq 0 ]; then
      step "[SEND] build + send mailer"
      $PY send_mailer.py "$@" \
        || { echo "  mailer build/send failed"; FAILURES+=("mailer: build/send"); }
  else
      # Name the ACTUAL blocker. On 2026-07-28 the reconcile blocked the send and
      # the alert said "failed screener.in validation" — validation had PASSED 6/6.
      if [ "$VALIDATE_OK" -ne 0 ]; then WHY="brief failed screener.in validation"
      else WHY="price reconcile flagged $RECONCILE_FAIL market(s) (validation itself PASSED)"; fi
      echo "  ❌ send SUPPRESSED — $WHY; saving draft instead"
      FAILURES+=("mailer: NOT SENT — $WHY")
      $PY send_mailer.py --draft \
        || { echo "  draft save failed"; FAILURES+=("mailer: draft save"); }
  fi

  fi   # end phase 2

  if [ ${#FAILURES[@]} -gt 0 ]; then
    echo "[ALERT] ${#FAILURES[@]} step(s) failed: ${FAILURES[*]}"
    # send_alert re-checks any "NOT SENT" claim against state/last_brief_sent.json
    # before mailing, so a failure that was fixed mid-run does not contradict a
    # brief that actually went out.
    $PY send_alert.py "${FAILURES[@]}" || echo "  alert email itself failed to send"
  fi

  echo "=== done $(date) ==="
} 2>&1 | tee -a "$LOG"

# ── chain the research partition ────────────────────────────────────────────
# daily_research.sh used to run on its own fixed clock guess (08:30), independent
# of whether --send had actually finished by then. That is not a partition of
# THIS run, it is a second run that happens to be scheduled nearby — if --send
# overran, research would start on top of it and immediately exit on the lock
# (wasted cron cycle, research silently skipped for the day); if --send finished
# early, research sat idle for no reason.
#
# Launched here instead: the brief has already been sent (or the alert already
# fired) by this point, so nothing downstream is waiting on research, and
# daily_mailer.sh must not block for the ~2h research run before it can exit.
# Backgrounded and disowned so it does not.
#
# The EXIT trap above (line ~76) still holds /tmp/daily_pipeline.lock for the
# few remaining instructions of THIS script, so daily_research.sh's own mkdir
# will find it briefly occupied and fall into its wait loop — harmless, since
# that loop polls a live pid and the trap releases the lock within a second of
# this line running; worst case is one unneeded 60s poll interval on a ~2h run.
# It is not, and does not need to be, a hand-off synchronised any tighter than
# that.
#
# Only fires after a REAL send phase (RUN_SEND=1, IS_DRAFT=0), which is the
# actual end of "today's run" — not after --data alone, and not after --draft,
# which are partial/test invocations that should not also trigger 2 hours of
# research work. Checked across ALL args, not just $1: --draft can appear
# anywhere in "$@".
if [ "$RUN_SEND" = "1" ] && [ "$IS_DRAFT" = "0" ]; then
  nohup ./daily_research.sh > /dev/null 2>&1 &
  disown
  echo "  chained: daily_research.sh started in the background (pid $!)"
fi
