#!/bin/bash
# cassandra_window.sh — take Cassandra down for the nightly pipeline window.
#
# WHY
# ---
# This is an 8GB M1. Cassandra runs with a fixed heap of -Xms4096M -Xmx4096M.
#
# 🔴 THAT 4GB IS NOT WHAT YOU GET BACK. -Xms reserves address space; macOS only
# backs the pages the JVM actually touches, and an idle Cassandra touches a small
# fraction. MEASURED on 2026-08-02, stopping it moved:
#
#     swap        2876 MB -> 2716 MB     (-160 MB)
#     compressed  2.10 GB -> 1.93 GB     (-170 MB)
#     free RAM    0.05 GB -> 0.06 GB     (unchanged)
#
# and restarting it put ~700MB of compressed memory back. So the honest figure is
# roughly 0.3-0.7GB of relieved pressure, NOT 4GB. Worth having on a box that was
# sitting at 50MB free — it is headroom bought for nothing, since nobody queries
# Cassandra overnight — but it is not the main lever. The warehouse_update
# pushdown (1.63GB -> 433MB) was four times larger.
#
# Nothing in the nightly chain needs it: ingest.sh, daily_mailer.sh and
# daily_research.sh never touch Cassandra. The only nightly reference is
# system_state.py's health check, which merely reports reachability.
#
# Meanwhile the pipeline was losing to jetsam. From the 2026-08-02 08:54 report:
#
#     "largestProcess" : "claude"
#     "free" : 7213 pages            (~118 MB)
#     "compressorSize" : 224414      (~3.6 GB compressed)
#
# Cassandra's RSS reads ~30MB at such moments, which looks harmless and is not:
# that is the JVM almost entirely PAGED OUT. Its heap did not disappear, it moved
# to swap (2.87GB of 4GB committed), and it pages back in the moment it is
# touched. Reading RSS alone would have cleared it of a cost it is very much
# incurring.
#
# 🔴 MUST GO THROUGH brew services. The plist sets KeepAlive=true, so killing the
# process just makes launchd start it again seconds later. `brew services stop`
# unloads the job, which is the only thing that actually keeps it down.
#
# 🔴 THE START SIDE IS THE SAFETY-CRITICAL HALF. The web app (run_app.sh, the
# FastAPI backend, the whole herrrickshaw keyspace) needs Cassandra. Leaving it
# down after the window breaks the app silently — it would look like a data bug,
# not a service that was never restarted. The start job is therefore scheduled on
# the CLOCK, not chained to the pipeline: if the pipeline crashes, hangs, or
# never runs, Cassandra still comes back.
#
#   cassandra_window.sh stop     # before the nightly chain
#   cassandra_window.sh start    # after it, and as an unconditional safety net
#   cassandra_window.sh status
set -uo pipefail

LOG="$HOME/market-pipeline/code/python_files/cassandra_window.log"
BREW=/opt/homebrew/bin/brew
PORT=9042

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"; }

# Liveness by PORT, not by process table. `brew services list` reports the
# launchd job's intent; a JVM can be up but not yet accepting CQL, and during
# startup those two disagree for ~30s.
listening() { /usr/sbin/lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; }

case "${1:-}" in
  stop)
    if ! listening; then log "stop: already down"; exit 0; fi
    log "stop: taking Cassandra down for the nightly window"
    "$BREW" services stop cassandra >>"$LOG" 2>&1
    for _ in $(seq 1 20); do
      listening || break
      sleep 3
    done
    if listening; then
      log "🔴 stop: STILL listening on $PORT after 60s — did not go down"
      exit 1
    fi
    log "stop: down (relieves ~0.3-0.7GB of swap/compressor pressure — measured, not the nominal 4GB heap)"
    ;;

  start)
    if listening; then log "start: already up"; exit 0; fi
    log "start: bringing Cassandra back"
    "$BREW" services start cassandra >>"$LOG" 2>&1
    # Cassandra takes tens of seconds to accept CQL. Report the REAL state rather
    # than brew's exit code, which returns as soon as launchd accepts the job.
    for _ in $(seq 1 40); do
      listening && break
      sleep 3
    done
    if listening; then
      log "start: up and accepting CQL on $PORT"
    else
      log "🔴 start: NOT listening on $PORT after 120s — the web app will fail"
      exit 1
    fi
    ;;

  status)
    if listening; then echo "cassandra: UP (listening on $PORT)"
    else echo "cassandra: DOWN"; fi
    ;;

  *)
    echo "usage: $(basename "$0") {stop|start|status}" >&2
    exit 2
    ;;
esac
