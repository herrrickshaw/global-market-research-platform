#!/bin/bash
# daily_mailer.sh — build and send the Daily Market Brief. Nothing else.
# India + US only (watchlist_markets.COVERED); the parked markets' scans and
# all research/ops work run in daily_research.sh, chained from the end of a
# real send. History and rationale: CHANGELOG.md, 2026-10-27 entry.
#
#   ./daily_mailer.sh            # data + send in one pass
#   ./daily_mailer.sh --data     # PHASE 1 only: refresh India + US market data
#   ./daily_mailer.sh --send     # PHASE 2 only: screen -> validate -> SEND
#   ./daily_mailer.sh --draft    # everything except the send
#
#   PHASE 1 (--data)  03:00 IST — after the US close in BOTH DST regimes.
#   PHASE 2 (--send)  06:30 IST — both markets shut, so a gate difference means
#                     staleness, not drift. (The old single 00:30 slot scanned
#                     the US mid-session every weekday.)
# Expected runtime ~15-40 min for phase 1, ~5-8 min for phase 2.
set -uo pipefail
cd "$(dirname "$0")"

# ── hold a power assertion for the whole run ──────────────────────────────────
# The pipeline is not slow, it is suspended: 2026-08-15's 262-min data phase
# held 37 sleep events around ~29 s of real work (CHANGELOG 2026-10-27). -w ties
# the assertion to this shell; -s/-i/-m block the sleeps that cost time on AC.
# ⚠️ On battery nothing blocks Maintenance Sleep — run the 03:00/06:30 slots on AC.
if command -v caffeinate >/dev/null 2>&1; then
  caffeinate -s -i -m -w "$$" &
  echo "  power assertion held for pid $$ (caffeinate -s -i -m)"
fi

# launchd's default soft fd limit is 256: the 2026-11-12 US scan died with
# "Errno 24 Too many open files" (and yfinance "unable to open database file")
# mid bulk download. Raise it for this run and every child.
ulimit -n 10240 2>/dev/null || ulimit -n "$(ulimit -Hn)" 2>/dev/null || true
echo "  fd limit: $(ulimit -n)"

# Never inherit python3 from the caller's PATH. A manual run from a plain shell
# resolved it to homebrew 3.14 on 2026-07-22: step [0] flagged missing deps,
# every scan died, and the validation gate correctly suppressed the send.
PY="$(dirname "$0")/.venv/bin/python3"
LOG="daily_mailer_$(date +%Y%m%d).log"
# No fallback to PATH python3. On 2026-09-15 the venv had been deleted, this
# line quietly picked homebrew 3.14, and all 13 steps "ran" with no deps —
# eight failures, a suppressed send, and no draft. A missing venv is a config
# fault: say so once, loudly, and stop. /usr/bin/python3 is enough for the
# alert (send_alert.py is stdlib + env_loader).
if [ ! -x "$PY" ]; then
  _msg="venv missing: $PY — rebuild with python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  echo "=== daily mailer $(date) · ABORTED ===" >> "$LOG"
  echo "  🔴 $_msg" | tee -a "$LOG" >&2
  /usr/bin/python3 send_alert.py --pipeline daily_mailer.sh --log "$LOG" \
      "STARTUP: $_msg" >/dev/null 2>&1 || echo "  (alert could not be sent either)" >&2
  exit 78   # EX_CONFIG
fi

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
    # 🔴 A LOST SEND MUST NOT LOOK LIKE A SUCCESS. Exiting 0 here meant launchd
    # recorded success for a job that did nothing: on 2026-08-15 the data phase
    # overran to 07:27, the 06:30 send hit this branch, and no brief went out
    # with nothing anywhere reporting it. Only reading the log tail revealed it.
    #
    # A send that never happened is a failure of this job, so say so — both to
    # the operator and to launchd (exit 75, EX_TEMPFAIL: the run is legitimately
    # blocked by another, not broken). The data phase keeps exit 0 because being
    # pre-empted by a still-running peer is a real no-op, not a lost deliverable.
    # Read the flags off "$@" directly: RUN_DATA/RUN_SEND are not parsed until
    # well after this lock is taken, so testing them here would always be false.
    #
    # 🔴 BUT "this send did no work" IS NOT "no brief went out". The two are
    # different claims and only the second is a failure. On 2026-08-25 a send
    # started by hand at 05:59 delivered the brief at 06:12 and chained
    # daily_research.sh, which takes THIS SAME LOCK (daily_research.sh:61) and
    # held it until 06:37. The 06:30 job therefore hit this branch, announced
    # SEND LOST for a brief already sitting in the operator's inbox, mailed an
    # alert about it, and handed launchd exit 75 for a day that had succeeded.
    #
    # So check the evidence before crying. state/last_brief_sent.json is written
    # by send_mailer.py after a successful send and is the authoritative record
    # (send_alert.py:44 re-checks the same file for the same reason). A brief
    # dated today means this run is a redundant peer, not a lost deliverable:
    # say so, stay quiet, exit 0. Only a genuinely missing brief escalates.
    case " $* " in
      *" --send "*)
        # brief_state.py owns state/last_brief_sent.json; it prints
        # "<sent_at>|<subject>" when a brief went out today, else nothing.
        _sent_subject="$("$PY" brief_state.py --sent-today 2>/dev/null)"
        if [ -n "$_sent_subject" ]; then
          echo "  ✅ not a lost send — a brief for $(date +%F) already went out at"
          echo "     ${_sent_subject%%|*} ('${_sent_subject#*|}')."
          echo "     The lock is held by pid $_owner (the research chain that send"
          echo "     started). Nothing to re-run, no alert sent."
          exit 0
        fi
        echo "  🔴 SEND LOST — the brief for $(date +%F) did NOT go out. The lock"
        echo "     was held by pid $_owner, so this send did no work. Re-run once"
        echo "     that finishes:  ./daily_mailer.sh --send"
        # Failures are POSITIONAL — the trailer at the end of this script calls
        # `send_alert.py --pipeline ... --log ... "${FAILURES[@]}"`. Passing
        # --failures put the literal flag through as its own failed-step name,
        # which is what the 2026-08-15 alerts showed ("- --failures").
        $PY send_alert.py --pipeline daily_mailer.sh --log "$LOG" \
            "send lost: lock held by pid $_owner, no brief for $(date +%F)" \
            >/dev/null 2>&1 || echo "     (alert could not be sent either)"
        exit 75
        ;;
    esac
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

# ── per-step wall-clock ceiling ──────────────────────────────────────────────
#   cap <seconds> <label> <command...>
# No step may run forever: a hang holds the lock and loses the brief silently
# (2026-08-07, a 4h50m HTTPS socket at 0% CPU; CHANGELOG 2026-10-27). Returns
# the command's own status, or 124 on timeout so every `|| FAILURES+=(...)`
# handler fires unchanged plus an explicit TIMEOUT entry.
CAP_POLL=5

# Kill a process and all its descendants, deepest first — a bare `kill` on the
# parent orphans grandchildren to init, and several steps shell out (step [5/13]
# can spawn a full scan via subprocess, step [7/13] runs a worker pool).
_kill_tree() {
  local sig="$1" root="$2" child
  for child in $(pgrep -P "$root" 2>/dev/null); do
    _kill_tree "$sig" "$child"
  done
  kill "-$sig" "$root" 2>/dev/null || true
}

# Render a duration the way the reader needs it: minutes once there are minutes
# to speak of, seconds below that. CAP_DEPS is 120s, where "0m of 2m" is noise.
_dur() { if [ "$1" -ge 120 ]; then echo "$(( $1 / 60 ))m"; else echo "$1s"; fi; }

# Seconds of AWAKE time since boot. CLOCK_UPTIME_RAW does not advance while the
# system is suspended, so (wall delta - awake delta) is exactly how long the
# machine slept inside a step. Darwin has no shell primitive for this.
#
# Fallback is `date +%s`, which makes awake == wall and therefore slept == 0 —
# i.e. every timeout classifies as a real timeout, the pre-2026-08-29 behaviour.
# Degrading to the old, louder reading is the right failure mode here.
_awake_secs() {
  "$PY" -c 'import time; print(int(time.clock_gettime(time.CLOCK_UPTIME_RAW)))' \
    2>/dev/null || date +%s
}

TIMED_OUT=()
SUSPENDED=()
cap() {
  local secs="$1" label="$2"; shift 2
  "$@" &
  # Wall-clock, not an accumulator. The old form added CAP_POLL per iteration,
  # and `sleep 5` does not advance while the machine is suspended — so on
  # 2026-08-15, when the Mac slept 37 times mid-run, a 61-minute step [3/13]
  # never reached CAP_BHAVCOPY=2400 and no TIMEOUT was ever logged. Comparing
  # timestamps counts suspended time the way an observer does.
  local pid=$! started waited=0 awake_started
  started=$(date +%s)
  awake_started=$(_awake_secs)
  while kill -0 "$pid" 2>/dev/null; do
    waited=$(( $(date +%s) - started ))
    if [ "$waited" -ge "$secs" ]; then
      # Classify BEFORE killing. caffeinate -s -i -m cannot block Maintenance
      # Sleep on battery, so a step can burn its whole wall-clock budget while
      # getting almost no CPU: measured 2026-08-29, step [3/13] spent 3,649s of
      # its 3,662s suspended — about 13 seconds of wake time in 61 minutes, for
      # work profiled at ~29s. Calling that "India: bhavcopy refresh failed"
      # sends the operator hunting for an unbounded call that does not exist.
      #
      # The kill itself is unchanged and unconditional: a suspended step still
      # has to release $LOCKDIR, or the 06:30 send finds the lock held and
      # exits 0 with no brief (the 2026-08-07 silent failure).
      local awake slept
      awake=$(( $(_awake_secs) - awake_started ))
      slept=$(( waited - awake ))
      [ "$slept" -lt 0 ] && slept=0
      if [ "$slept" -ge $(( waited / 2 )) ]; then
        echo "  💤 SUSPENDED: '$label' hit the ${secs}s ceiling, but the machine slept"
        echo "     $(_dur "$slept") of $(_dur "$waited") — only ${awake}s of wake time. Not a code fault."
        SUSPENDED+=("$label (asleep $(_dur "$slept") of $(_dur "$waited"), ${awake}s awake)")
      else
        echo "  ⏱  TIMEOUT: '$label' exceeded ${secs}s — killing it and continuing"
        TIMED_OUT+=("$label (>${secs}s)")
      fi
      _kill_tree TERM "$pid"
      sleep 5
      if kill -0 "$pid" 2>/dev/null; then
        echo "  ⏱  still alive after SIGTERM — escalating to SIGKILL"
        _kill_tree KILL "$pid"
      fi
      wait "$pid" 2>/dev/null
      return 124
    fi
    sleep "$CAP_POLL"
  done
  wait "$pid"
}

# Budgets. Set from the worst case actually observed across every run in this
# directory (n shown), NOT guessed — a ceiling that clips a merely slow day would
# be worse than no ceiling, because it would fail runs that were going to succeed.
# Each is a wide multiple of its observed max, so only a genuine wedge trips it.
# Outer guard on [ENSURE-FRESH]. ensure_fresh has its own --max-minutes 35 budget and
# reports anything it did not attempt; this cap exists only for the case where
# a child hangs and the internal budget never gets to tick. 40min > 35min so the
# internal, self-reporting bound is the one that normally fires.
CAP_ENSURE_FRESH=2400
CAP_DEPS=120        # obs max     3s  (n=14)
CAP_PREFLIGHT=300   # obs max    21s  (n=18)
CAP_BHAVCOPY=2400   # obs max   956s  (n=11)  full EOD rebuild
CAP_SCAN_IN=3600    # obs max  1823s  (n=11)
CAP_REPORT_IN=1800  # obs max   907s  (n=10)  healthy path is ~7s
CAP_CCC=600         # obs max     4s  (n=10)  network scrape, kept generous
CAP_SCAN_US=5400    # obs max  2783s  (n=9)   longest step in the pipeline
CAP_REPORT_US=1800  # obs max    13s  (n=3)   can spawn a fresh scan like IN
CAP_WATCHLIST=600   # obs max     8s  (n=5)
CAP_SCREENS=900     # obs max    44s  (n=11)
CAP_PREDICT=900     # obs max    91s  (n=11)
CAP_REGIME=600      # obs max    17s  (n=11)
CAP_GATES=900       # obs max    12s  (n=9)   hits screener.in + yfinance
CAP_SEND=900        # obs      ~65s
CAP_ALERT=300       # an alert that hangs would hold the lock after all work is done

# Phase selection. Neither flag = both phases, so a manual run still works.
RUN_DATA=1; RUN_SEND=1; IS_DRAFT=0
for a in "$@"; do
  [ "$a" = "--data" ] && RUN_SEND=0
  [ "$a" = "--send" ] && RUN_DATA=0
  [ "$a" = "--draft" ] && IS_DRAFT=1
done

FAILURES=()
# Cause chain: when an upstream step failed, its dependents still run (on cached
# input, by design — the price gate is the single decider). stale_if records WHICH
# outputs rest on that cached input and what to do about it, so the alert names a
# cause instead of a bare list of failures. Never changes control flow.
STALE=()
stale_if() {   # stale_if "<upstream FAILURES entry>" "<dependents>" "<remedy>"
  local f
  for f in "${FAILURES[@]:-}"; do
    if [ "$f" = "$1" ]; then
      STALE+=("STALE INPUT: $2 ran on cached data because '$1' failed — remedy: $3")
      echo "  ↳ stale input: $2 (upstream '$1' failed)"
      return 0
    fi
  done
  return 0
}
{
  echo "=== daily mailer $(date) · data=$RUN_DATA send=$RUN_SEND ==="

  # ── 1. gates ───────────────────────────────────────────────────────────────
  step "[1/13] dependency check"
  cap $CAP_DEPS "[1/13] dependency check" \
    $PY check_deps.py || FAILURES+=("STARTUP: missing required dependencies")

  step "[2/13] pre-flight: scan input gates"
  cap $CAP_PREFLIGHT "[2/13] pre-flight gates" \
    $PY preflight_scan_inputs.py || FAILURES+=("STARTUP: pre-flight input gate(s) failed")

  # ── 1a. bring the data up to NOW before building anything ──────────────────
  # The pipeline was built around a fixed clock: collect at 03:00, send at 06:30,
  # nothing downstream re-asks. So the brief was only ever as good as one
  # unrepeatable moment — and on 2026-08-19 that moment ran on battery, slept
  # seven times, and left 77% of the US scan on the previous session. The send
  # phase then had no move left except to suppress.
  #
  # ensure_fresh re-asks. It compares every dataset against the session that has
  # actually closed AND published as of now, and refreshes the minimum set that
  # is behind, in dependency order — so a brief requested at 06:30, 11:00 or on
  # a Saturday collects up to that hour rather than inheriting 03:00's luck.
  #
  # 🔴 IT MUST REBUILD THE REPORTS, NOT JUST THE SCANS. The brief reads BOTH
  # `<market>_scan/*.xlsx` (prices) and `combined_report_results/*.json` (mood,
  # street talk, fundamentals picks). Refreshing a scan alone ships a brief whose
  # price sections and narrative sections describe different days — measured
  # live on 19 Aug, where scan.US reached 18 Aug while combined_US_20260819_0459
  # still carried 17 Aug prices under a 19 Aug filename. report.IN/report.US are
  # registered in data_catalog as dependents of their scans precisely so the
  # planner rebuilds them here.
  #
  # FAIL-SAFE BY CONSTRUCTION. This never blocks the send: whatever it cannot
  # fix falls through to the self-heal below, which runs the full data phase.
  # A non-zero exit is logged, not fatal — the gates at [13/13] remain the thing
  # that decides whether a brief is fit to send.
  if [ "$RUN_SEND" = "1" ] && [ "$RUN_DATA" = "0" ]; then
    step "[ENSURE-FRESH] bring data up to the latest published session before building"
    # -u because cap() kills with SIGTERM/SIGKILL. Block-buffered stdout dies in
    # the buffer, so a killed step logs its start line, then nothing, then the
    # TIMEOUT — with no record of what it was doing. Measured 2026-08-20: this
    # step was killed at 2400s having printed nothing at all, and the reason
    # (the Mac slept for 2,396 of those 2,400 seconds) had to be reconstructed
    # from pmset rather than read out of the log.
    cap $CAP_ENSURE_FRESH "[ENSURE-FRESH] refresh to current session" \
      $PY -u ensure_fresh.py --require IN US --max-minutes 35 \
      || echo "  ensure_fresh could not close every gap — self-heal below is the fallback"
  fi

  # ── 1b. self-heal a missed OR STALE data phase ─────────────────────────────
  # 2026-08-01: the Mac slept through mailer-data's 03:00 slot, so --send at
  # 06:30 gated Thursday's scan against Friday's closes and correctly refused to
  # send. The gate held; the brief still never arrived. So if the data phase did
  # not deliver, run it inline (~12 min) rather than walking into a guaranteed
  # reconcile failure and an alert email.
  #
  # 🔴 2026-08-19: THE FILE-EXISTENCE TEST WAS NOT ENOUGH. The 03:00 phase DID
  # run and DID write `us_full_scan_20260819_0459.xlsx`, so this check passed —
  # but the Mac slept seven times mid-run, 3,872 tickers failed their refresh,
  # and 77% of that workbook's prices were the 17 Aug close. A file existing
  # under today's date says the job ran, never that it collected today's data.
  # That is the same mtime-for-content substitution that has caused every
  # staleness incident in this pipeline.
  #
  # The test is now the SESSION the scans actually hold, recovered from their
  # prices (data_state.py). `--require-current` fails on a one-session gap too,
  # which is precisely the case that shipped: every US row graded one behind.
  if [ "$RUN_SEND" = "1" ] && [ "$RUN_DATA" = "0" ]; then
    TODAY_TAG="$(date +%Y%m%d)"
    if ! ls indian_full_scan/indian_full_scan_"${TODAY_TAG}"_*.xlsx >/dev/null 2>&1 \
       || ! ls us_full_scan/us_full_scan_"${TODAY_TAG}"_*.xlsx >/dev/null 2>&1; then
      step "[SELF-HEAL] today's scan workbooks missing — running the data phase inline"
      RUN_DATA=1
    else
      # NOT `cmd | tail` — a pipeline's status is the LAST command's, so piping
      # into tail would discard the gate's verdict and always look like a pass.
      SESSION_CHECK="$($PY data_state.py --markets IN US \
                          --require-current scan.IN scan.US 2>&1)"
      SESSION_RC=$?
      echo "$SESSION_CHECK" | tail -20
      if [ "$SESSION_RC" -ne 0 ]; then
        step "[SELF-HEAL] scans hold a stale SESSION (files exist but prices are old) — rerunning data phase inline"
        RUN_DATA=1
      fi
    fi
  fi

  if [ "$RUN_DATA" = "1" ]; then
  # ── 2. India ───────────────────────────────────────────────────────────────
  # -u on the three long steps for the same reason as [ENSURE-FRESH] above:
  # cap() kills with SIGTERM/SIGKILL and block-buffered stdout dies unflushed,
  # so a timeout leaves no record of how far the step got. These three carry the
  # most wall-clock and so the most exposure — and their caps are calibrated
  # against observed maxima that assume an awake machine, which this one is not.
  step "[3/13] India EOD refresh (official bhavcopy, incremental)"
  cap $CAP_BHAVCOPY "[3/13] India EOD refresh" \
    $PY -u bhavcopy_history.py 400 \
    || { echo "  bhavcopy refresh failed (will use cache)"; FAILURES+=("India: bhavcopy refresh"); }

  step "[4/13] India full screener scan"
  cap $CAP_SCAN_IN "[4/13] India full screener scan" \
    $PY -u scan_bhavcopy.py \
    || { echo "  scan failed (will use latest cache)"; FAILURES+=("India: full screener scan"); }

  stale_if "India: bhavcopy refresh" "India scan [4/13] and report [5/13]" \
    "fix the bhavcopy source, then run ./daily_mailer.sh --data before --send"

  step "[5/13] India combined report (fundamentals + street talk)"
  cap $CAP_REPORT_IN "[5/13] India combined report" \
    $PY daily_combined_report.py --market IN --html \
    || { echo "  combined report failed"; FAILURES+=("India: combined report"); }

  step "[6/13] India CCC screen (screener.in) + scrape test"
  cap $CAP_CCC "[6/13] India CCC screen refresh" \
    $PY -c "import screener_in as s; s.ccc_screen().to_parquet('cache_seed/india_ccc_screen.parquet', index=False)" \
    || { echo "  CCC refresh skipped"; FAILURES+=("India: CCC screen refresh"); }
  cap $CAP_CCC "[6/13] screener.in scrape test" \
    $PY test_screener_in.py \
    || { echo "  ⚠️  screener.in CCC test FAILED — CCC section will show n/a"; FAILURES+=("India: CCC scrape test"); }

  # ── 3. US ──────────────────────────────────────────────────────────────────
  step "[7/13] US full market scan (NASDAQ+NYSE, min-price \$2)"
  cap $CAP_SCAN_US "[7/13] US full market scan" \
    $PY -u full_us_market_scan.py --workers 10 --min-price 2 \
    || { echo "  US full market scan failed (continuing)"; FAILURES+=("US: full market scan"); }

  stale_if "US: full market scan" "US combined report [8/13]" \
    "rerun ./daily_mailer.sh --data (the scan needs ~45 min, Mac on AC)"

  step "[8/13] US combined report (reuses the fresh US scan)"
  cap $CAP_REPORT_US "[8/13] US combined report" \
    $PY daily_combined_report.py --market US --html \
    || { echo "  US combined report failed (continuing)"; FAILURES+=("US: combined report"); }
  fi   # end phase 1

  if [ "$RUN_SEND" = "1" ]; then

  # ── 4. screens, then watchlist repair ──────────────────────────────────────
  step "[9/13] screens (value re-rating · playbook · small-cap)"
  cap $CAP_SCREENS "[9/13] value re-rating screen" \
    $PY screen_value_rerating.py || FAILURES+=("screen: value re-rating")
  cap $CAP_SCREENS "[9/13] playbook screen" \
    $PY playbook_screener.py     || FAILURES+=("screen: playbook")
  cap $CAP_SCREENS "[9/13] small-cap screen" \
    $PY smallcap_screener.py --screen || FAILURES+=("screen: small-cap")

  # Repair runs AFTER the screens, once. It used to run before them too, but
  # the screens add rows (a screen matching a stale JP/KR/EU scan file left on
  # disk by daily_research.sh re-introduced 31 parked rows in one run), so the
  # post-screen pass is the one that decides what watchlist_tiers syncs below;
  # the pre-screen pass only ever repaired rows this pass repairs again.
  step "[10/13] watchlist repair (renames/delists/ETFs + coverage gate)"
  cap $CAP_WATCHLIST "[10/13] watchlist repair" \
    $PY watchlist_repair.py || FAILURES+=("watchlist: repair")

  step "[11/13] prediction filter -> tiers -> re-entry ranking"
  cap $CAP_PREDICT "[11/13] prediction filter" \
    $PY prediction_filter.py || FAILURES+=("prediction filter")
  cap $CAP_PREDICT "[11/13] watchlist tiers" \
    $PY watchlist_tiers.py   || FAILURES+=("watchlist tiers")
  # NOTE: reentry_engine RANKS but no longer injects (--commit required). The
  # forward edge that justified auto-injection measured t=0.06 and was withdrawn
  # 2026-07-29; it stays in the mailer path only to keep the paper-track running.
  cap $CAP_PREDICT "[11/13] re-entry ranking" \
    $PY reentry_engine.py || FAILURES+=("re-entry ranking")

  # MARKET_WH is set HERE and nowhere else. The local warehouse tree was cleaned
  # and migrated to Dropbox on 2026-08-14, which broke this step (it globbed
  # year=*.parquet under the deleted path and died on max() of an empty
  # sequence — silently, behind "|| continuing", every run since).
  #
  # The Dropbox copy is synced but ONLINE-ONLY: 886 MB of placeholders, 0 bytes
  # resident, so pointing this at ~/Dropbox would re-download the whole tree on
  # first read and again after every eviction. Instead a small local cache holds
  # just the two years --refresh-regime actually loads (~119 MB):
  #   rclone copy dropbox:market-data-archive/current/gmd_warehouse/ohlcv/$M \
  #     ~/.cache/market-warehouse/ohlcv/$M --include "year=202[56].parquet"
  #
  # Scoped to this one command deliberately: the MONTHLY backtests
  # (strategy_regime_survival without --refresh-regime, START=2016;
  # backtest_zone_rules.py, START=2018) glob EVERY year, and against this 2-year
  # cache they would report a 2-year result as a 10-year one. They keep the
  # default path; load_panel() now raises on missing years rather than
  # truncating, so if that assumption ever breaks it breaks loudly.
  step "[12/13] refresh live market regime (zone_regime.json)"
  MARKET_WH="${MARKET_WH_DAILY:-$HOME/.cache/market-warehouse/ohlcv}" \
  cap $CAP_REGIME "[12/13] regime refresh" \
    $PY strategy_regime_survival.py --refresh-regime \
    || echo "  regime refresh failed (continuing)"

  # ── 5. THE SEND GATE ───────────────────────────────────────────────────────
  # price_gate.py: workbook age + warehouse signature for IN and US, a live
  # Yahoo spot-check for US (Yahoo is the only US source), and the witness
  # jury for IN. A brief can be internally consistent and a day old, or fresh
  # and wrong; the gate checks both. Only IN and US — the parked markets are
  # not scanned here, and gating on a stale JP file would block the send over
  # a market the brief does not mention.
  #
  # FAILS SAFE under the ceiling: cap returns 124, non-zero, so a gate that
  # cannot finish is never read as a gate that passed.
  step "[13/13] send gate: scan staleness (IN, US) + witness jury (IN)"
  GATE_OK=1
  rm -f state/price_gate_reason.txt
  cap $CAP_GATES "[13/13] price gate" \
    $PY price_gate.py --markets IN US --sample 6 && GATE_OK=0

  # Lineage: which scans/prices/gate verdict this run's brief rests on. Never fatal.
  $PY run_manifest.py || true

  # ── 6. send ────────────────────────────────────────────────────────────────
  if [ "$GATE_OK" -eq 0 ]; then
      step "[SEND] build + send mailer"
      # ⚠️ The one ceiling with a real downside. send_mailer has no already-sent
      # guard, so killing it mid-SMTP could in principle leave the brief half
      # delivered and a retry would send twice. Capped anyway, at ~14x the ~65s
      # it actually takes: a send that has not returned in 15 minutes is wedged,
      # not slow, and an unbounded hang here holds the lock and silently kills
      # the brief — the exact failure this whole guard exists to prevent. If it
      # ever trips, check state/last_brief_sent.json before re-running.
      cap $CAP_SEND "[SEND] build + send mailer" \
        $PY send_mailer.py "$@" \
        || { echo "  mailer build/send failed"; FAILURES+=("mailer: build/send"); }
  else
      # Name the ACTUAL blocker, in the gate's own words. The gate writes its
      # reason to a file rather than this script parsing stdout, and the text
      # names no source by hand: hardcoded labels went stale twice (2026-07-28
      # blamed validation for a reconcile failure; 2026-08-29 blamed screener.in
      # eleven days after it stopped being a witness).
      WHY="$(cat state/price_gate_reason.txt 2>/dev/null)"
      [ -z "$WHY" ] && WHY="price gate failed without a reason (see [13/13] above)"
      echo "  ❌ send SUPPRESSED — price gate: $WHY; saving draft instead"
      FAILURES+=("mailer: NOT SENT — price gate: $WHY")
      cap $CAP_SEND "[SEND] draft save" \
        $PY send_mailer.py --draft \
        || { echo "  draft save failed"; FAILURES+=("mailer: draft save"); }
  fi

  fi   # end phase 2

  # Name timed-out steps explicitly. Their `|| FAILURES+=(...)` handler above has
  # already recorded a generic failure, but "India: combined report" in an alert
  # reads as a crash — the operator needs to know it hung, because a hang points
  # at an unbounded call rather than a bug in the report itself.
  if [ ${#TIMED_OUT[@]} -gt 0 ]; then
    FAILURES+=("TIMEOUT: ${TIMED_OUT[*]}")
  fi

  # A suspended step is still a failure — the pipeline fell back to cached data
  # and the operator must know the day is stale — but it is not a BROKEN step,
  # and the distinction changes what they should do about it. The fix for this
  # class is AC power for the 03:00/06:30 slots; nothing caffeinate offers
  # blocks Maintenance Sleep on battery, so there is no code change to hunt for.
  if [ ${#SUSPENDED[@]} -gt 0 ]; then
    FAILURES+=("SUSPENDED — machine asleep, not a code fault (run on AC): ${SUSPENDED[*]}")
  fi

  if [ ${#FAILURES[@]} -gt 0 ]; then
    echo "[ALERT] ${#FAILURES[@]} step(s) failed: ${FAILURES[*]}"
    # send_alert re-checks any "NOT SENT" claim against state/last_brief_sent.json
    # before mailing, so a failure that was fixed mid-run does not contradict a
    # brief that actually went out.
    cap $CAP_ALERT "[ALERT] send_alert" \
      $PY send_alert.py --pipeline daily_mailer.sh --log "$LOG" \
      "${FAILURES[@]}" ${STALE[@]+"${STALE[@]}"} || echo "  alert email itself failed to send"
  fi

  echo "=== done $(date) ==="
} 2>&1 | tee -a "$LOG"

# ── chain the research partition ────────────────────────────────────────────
# Research starts when the send ends, not on its own clock (a fixed 08:30 slot
# either collided with an overrunning send or sat idle). Only after a REAL send
# phase — never --data or --draft. Backgrounded and disowned; the lock hand-off
# is one 60 s poll at worst. Its launch output goes to its own file, never
# /dev/null, and the plists set AbandonProcessGroup so launchd does not kill
# it with the parent (2026-07-30). CHANGELOG 2026-10-27.
if [ "$RUN_SEND" = "1" ] && [ "$IS_DRAFT" = "0" ]; then
  nohup ./daily_research.sh > "daily_research_chain_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
  disown
  echo "  chained: daily_research.sh started in the background (pid $!)"
fi
