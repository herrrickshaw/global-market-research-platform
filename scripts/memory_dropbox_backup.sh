#!/bin/bash
# memory_dropbox_backup.sh — one-way copy of the Claude Code long-term memory
# directory to Dropbox. Written 2026-09-23 after discovering
# ~/.claude/projects/-Users-umashankar/memory/ (141+ curated markdown files,
# the whole long-term memory system) had zero backup anywhere: excluded from
# the home repo via .gitignore, not covered by any existing backup script, not
# in either rclone remote. See feedback_memory_directory_unbacked_up memory.
#
# DELIBERATELY `rclone copy`, NOT `sync`: this directory is the source of
# truth and the only thing this script's purpose is to protect against local
# loss (disk failure, accidental rm). A `sync` mirrors deletions too, so an
# accidental local `rm -rf` would propagate to the backup on the very next
# run and destroy it there as well — exactly the trap already documented in
# feedback_sync_mirror_archive_trap. `copy` only ever adds/updates remote
# files; it never deletes anything at the destination.
#
# Kept independent of ~/scripts/cloud_backup.sh on purpose: that script is
# market-pipeline's data-tree backup (parquet/cache trees, account-level
# rclone lock, --backup-dir dated history, pruning) invoked from the daily
# pipeline scripts. Coupling an unrelated Claude Code memory backup to that
# pipeline's health (it has a documented history of lock/concurrency
# incidents) would trade a two-line cron job for pipeline fragility. This
# script still waits briefly on the SAME shared account lock as a courtesy —
# rclone rate limits are per-Dropbox-account, not per-destination — but a
# copy of a few hundred KB of text is low-risk even if that wait times out.
set -uo pipefail

SRC="/Users/umashankar/.claude/projects/-Users-umashankar/memory"
DEST="dropbox:claude-memory-backup/memory"
RCLONE=/opt/homebrew/bin/rclone
LOG="/Users/umashankar/scripts/memory_dropbox_backup.log"

ACCT_LOCK="/tmp/cloud_backup.rclone-dropbox.lock"
_waited=0
while [ -d "$ACCT_LOCK" ] && [ "$_waited" -lt 60 ]; do
  sleep 10; _waited=$((_waited + 10))
done

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
  "$RCLONE" copy "$SRC" "$DEST" --create-empty-src-dirs
  status=$?
  if [ "$status" -eq 0 ]; then
    echo "ok: $("$RCLONE" size "$DEST" --json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"{d[\"count\"]} files, {d[\"bytes\"]} bytes")' 2>/dev/null || echo 'copy succeeded')"
  else
    echo "FAILED: rclone copy exit $status"
  fi
} >> "$LOG" 2>&1
