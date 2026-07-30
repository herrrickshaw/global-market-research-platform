#!/bin/bash
# cloud_backup.sh — mirror the market-data trees to Dropbox via rclone.
#
# WHY CLOUD AND NOT GITHUB LFS: the account-wide LFS budget is exhausted, LFS
# stores every rewritten parquet as a new permanent blob (no delta compression,
# ~120 MB/day of churn), and only deleting a whole repo ever frees space. The
# Dropbox remote has 1.6 TiB free, uploads only changed files, and this script
# keeps explicit dated history instead of destructive overwrites.
# (2026-07-22: user chose dropbox over googledrive — also sidesteps rclone's
# shared Google client_id retiring during 2026.)
#
# LAYOUT on the remote (default dropbox:market-data-archive):
#   current/<tree>/...          exact mirror of each local tree
#   history/<YYYY-MM-DD>/<tree> files that were CHANGED or DELETED that day
#                               (moved there by --backup-dir, never destroyed)
#   pg/market_data_<date>.dump  weekly compressed Postgres dump (Mondays)
#
# Retrieval:
#   rclone copy dropbox:market-data-archive/current/market_cache ~/restore/
#   rclone ls   dropbox:market-data-archive/history/2026-07-22/
#
# History older than $KEEP_DAYS is pruned; the current/ mirror is never pruned.
#
# Usage:
#   cloud_backup.sh              # sync all trees; pg dump if Monday
#   cloud_backup.sh --with-pg    # force the Postgres dump too
#   CLOUD_REMOTE=googledrive:market-data-archive cloud_backup.sh  # other account
set -uo pipefail

REMOTE="${CLOUD_REMOTE:-dropbox:market-data-archive}"
TODAY="$(date +%Y-%m-%d)"
KEEP_DAYS=60
LOG="$HOME/market-pipeline/code/python_files/cloud_backup.log"
RCLONE=/opt/homebrew/bin/rclone
FAILS=0

# Single-instance lock. On 2026-07-22 two concurrent invocations (pipeline
# step 16 + a manual --with-pg) shared /tmp/market_data_<date>.dump: instance A
# finished and rm'd the file while B's rclone was mid-transfer -> hash mismatch
# -> rclone deleted the "corrupted" REMOTE copy too. The sync trees survive
# concurrency (rclone per-file), but the dump lifecycle does not.
LOCK="/tmp/cloud_backup.$(echo "$REMOTE" | tr ':/' '__').lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "cloud_backup: another instance holds $LOCK — exiting (not an error)" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# ── account-level serialisation (2026-07-29) ─────────────────────────────────
# rclone rate limits are per-ACCOUNT, not per-destination. Two backup scripts
# exist — this one and the other cloud_backup.sh — writing to different Dropbox
# paths (market-data-archive vs market-data-backup) from the SAME source trees
# and the same Dropbox account. Any lock keyed by remote therefore never
# excluded the other: on 2026-07-28 both ran together and pipeline step [16]
# took 4h19m instead of minutes, with two rclones fighting for one account's
# throughput.
#
# This lock WAITS instead of exiting, which is the opposite of the daily_pipeline
# lock and deliberately so: a duplicate pipeline run is redundant work, but a
# skipped backup is lost coverage, and these two write to different destinations
# so both genuinely have to run. After 90 minutes it gives up waiting and
# proceeds anyway — a slow backup beats no backup, and a wedged peer must not be
# able to suppress this one indefinitely.
ACCT_LOCK="/tmp/cloud_backup.rclone-dropbox.lock"
ACCT_OWNED=0
_acct_waited=0
while :; do
  if mkdir "$ACCT_LOCK" 2>/dev/null; then
    ACCT_OWNED=1; echo $$ > "$ACCT_LOCK/pid"; break
  fi
  _acct_peer="$(cat "$ACCT_LOCK/pid" 2>/dev/null || true)"
  if [ -z "${_acct_peer:-}" ] || ! kill -0 "$_acct_peer" 2>/dev/null; then
    rm -rf "$ACCT_LOCK" 2>/dev/null; continue          # stale: owner is gone
  fi
  if [ "$_acct_waited" -ge 5400 ]; then
    echo "cloud_backup: waited 90m on $ACCT_LOCK (pid $_acct_peer) — proceeding concurrently" >> "$LOG"
    break
  fi
  [ "$_acct_waited" = 0 ] && echo "cloud_backup: waiting for rclone account lock (pid $_acct_peer)" >> "$LOG"
  sleep 30; _acct_waited=$((_acct_waited + 30))
done

# one trap, both locks — a second `trap ... EXIT` REPLACES the first in bash
trap 'rmdir "$LOCK" 2>/dev/null; [ "$ACCT_OWNED" = 1 ] && rm -rf "$ACCT_LOCK" 2>/dev/null' EXIT


# name -> local path. lmdb dirs and tmp/bak files are excluded below: lmdb is a
# live-updated memory-mapped store (copying mid-write gives a corrupt snapshot,
# and it is rebuilt from the parquets anyway); .tmp/.bak are churn.
TREES=(
  "market_cache|$HOME/market-pipeline/market_cache"
  "bhavcopy_cache|$HOME/market-pipeline/data/bhavcopy_cache"
  "cache_seed|$HOME/market-pipeline/code/python_files/cache_seed"
  "gmd_cache_seed|$HOME/repos/global-market-data/cache_seed"
  "warehouse_duckdb|$HOME/data"
  # The tar.zst archives of many-small-file static subdirs (see below). Synced as
  # its own dataset so excluding the raw files does not lose the data.
  "backup_archives|$HOME/.backup-archives"
)

# 🔴 THE MANY-SMALL-FILES PROBLEM, TWICE NOW. market_cache/nse_xbrl/xml (98,289
# XML files, 5.1 GB, static/append-only) was the first case: Dropbox rate-limits
# WRITE OPERATIONS per account, not bytes, so syncing files individually
# throttles no matter how fast the link is. On 2026-07-28 this step ran 9h20m
# and then died:
#
#   ERROR : ...: upload failed: too_many_write_operations
#   ERROR : Cancelling sync due to fatal error: upload failed: batcher is shutting down
#     ! market_cache: sync FAILED
#
# market_cache/ohlc (7,682 parquets, 334 MB) is the second case, found
# 2026-07-30 — same throttling shape (2,705 too_many_write_operations errors,
# 4h for a sync that should take minutes) despite being the OPPOSITE of static:
# 98.6% of its files are rewritten daily (fresh price bar per ticker). Dropbox's
# per-request throttling does not care whether the file set is static or
# live-updated, only how many of them there are.
#
# repo-data-dedup/scripts/cloud_backup.sh's "static-subdir archive pattern
# (standard 2026-07-23)" tar.zst's such subdirs into ~/.backup-archives and
# excludes them from the raw sync. Its rebuild gate was originally
# file-count:size-KB, which is fine for genuinely-static XBRL filings but was
# widened to also track max-mtime before ohlc was added — a daily rewrite that
# keeps roughly the same file count and a du-rounded size could otherwise leave
# a live-updated directory's archive frozen on day one. That script builds the
# archive; this one consumes it, so the exclusion below is safe only because
# backup_archives is in TREES above.
EXTRA_EXCLUDES=(--exclude "nse_xbrl/xml/**" --exclude "ohlc/**")

{
  echo "=== cloud backup $(date '+%Y-%m-%d %H:%M:%S %Z') -> $REMOTE ==="

  for entry in "${TREES[@]}"; do
    name="${entry%%|*}"; src="${entry#*|}"
    if [ ! -e "$src" ]; then
      echo "  ! $name: $src missing — skipped"; FAILS=$((FAILS+1)); continue
    fi
    "$RCLONE" sync "$src" "$REMOTE/current/$name" \
      --backup-dir "$REMOTE/history/$TODAY/$name" \
      --exclude "*.tmp" --exclude "*.bak" --exclude "*.parquet.bak" \
      --exclude "ohlcv.lmdb/**" --exclude ".DS_Store" \
      "${EXTRA_EXCLUDES[@]}" \
      --transfers 4 --checkers 8 --dropbox-chunk-size 96M \
      --stats-one-line --stats 0 --log-level NOTICE \
      && echo "  ok $name" \
      || { echo "  ! $name: sync FAILED"; FAILS=$((FAILS+1)); }
  done

  # Weekly Postgres dump (Mondays, or --with-pg). Custom format = compressed +
  # selective restore (pg_restore -t). The warehouse IS rebuildable from the
  # caches, but a direct dump makes retrieval one step instead of a pipeline.
  if [ "$(date +%u)" = "1" ] || [ "${1:-}" = "--with-pg" ]; then
    # $$ in the LOCAL name: even with the lock, a unique path means an aborted
    # instance can never collide with a later one. The REMOTE name stays dated.
    DUMP="/tmp/market_data_$(date +%Y%m%d).$$.dump"
    if /opt/homebrew/bin/pg_dump -d market_data -Fc -f "$DUMP" 2>/dev/null \
       || pg_dump -d market_data -Fc -f "$DUMP"; then
      "$RCLONE" copyto "$DUMP" "$REMOTE/pg/market_data_$(date +%Y%m%d).dump" --stats-one-line --stats 0 \
        && echo "  ok pg dump $(du -h "$DUMP" | cut -f1)" \
        || { echo "  ! pg dump upload FAILED"; FAILS=$((FAILS+1)); }
      rm -f "$DUMP"
      # keep the last 8 weekly dumps (sort -r|tail +9: macOS head has no -n -8)
      "$RCLONE" lsf "$REMOTE/pg/" 2>/dev/null | sort -r | tail -n +9 | while read -r old; do
        [ -n "$old" ] && "$RCLONE" deletefile "$REMOTE/pg/$old" \
          && echo "  pruned pg/$old"
      done
    else
      echo "  ! pg_dump FAILED"; FAILS=$((FAILS+1))
    fi
  fi

  # Prune history dirs older than KEEP_DAYS (current/ is never touched).
  CUTOFF=$(date -v-${KEEP_DAYS}d +%Y-%m-%d 2>/dev/null || date -d "-${KEEP_DAYS} days" +%Y-%m-%d)
  "$RCLONE" lsf --dirs-only "$REMOTE/history/" 2>/dev/null | tr -d '/' | while read -r d; do
    if [[ "$d" < "$CUTOFF" ]]; then
      "$RCLONE" purge "$REMOTE/history/$d" && echo "  pruned history/$d"
    fi
  done

  # One-line verification per tree: local vs remote file count + total size.
  for entry in "${TREES[@]}"; do
    name="${entry%%|*}"; src="${entry#*|}"
    [ -e "$src" ] || continue
    rsize=$("$RCLONE" size "$REMOTE/current/$name" --json 2>/dev/null)
    echo "  verify $name: remote $rsize"
  done

  if [ "$FAILS" -gt 0 ]; then
    echo "=== done with $FAILS FAILURE(S) $(date '+%H:%M:%S') ==="
    exit 1
  fi
  echo "=== done $(date '+%H:%M:%S') ==="
} >> "$LOG" 2>&1
