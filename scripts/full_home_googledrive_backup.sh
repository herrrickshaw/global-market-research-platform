#!/bin/bash
# full_home_googledrive_backup.sh — ONE-TIME full copy of /Users/umashankar
# to Google Drive, requested 2026-09-23. NOT scheduled/recurring — run
# manually if you want another snapshot.
#
# `rclone copy`, not `move` and not `sync`: local files are left completely
# untouched (a `move` would delete them after upload — which would break
# every repo, script, cron job and this Claude Code session itself, all of
# which depend on files existing at their current local paths; a `sync`
# would let a later run delete the Drive copy of anything removed locally).
#
# Explicitly NO --exclude filters — user confirmed "literally all of
# /Users/umashankar, no exclusions" after being shown the risk. --links
# stores symlinks as .rclonelink placeholder files (safe: preserves them
# without following/dereferencing, so no risk of loops or escaping the tree).
#
# 79GB / Google Drive had 4.47TiB free as of 2026-09-23 — capacity is not a
# concern, but this WILL take a long time (many hours depending on upload
# bandwidth) and should run in the background.
set -uo pipefail

SRC="/Users/umashankar/"
DEST="googledrive:umashankar-home-backup-2026-09-23"
RCLONE=/opt/homebrew/bin/rclone
LOG="/Users/umashankar/scripts/full_home_googledrive_backup.log"

{
  echo "=== START $(date '+%Y-%m-%d %H:%M:%S') ==="
  "$RCLONE" copy "$SRC" "$DEST" \
    --links \
    --transfers 8 --checkers 8 \
    --stats 5m --stats-one-line \
    -v
  status=$?
  echo "=== END $(date '+%Y-%m-%d %H:%M:%S') — exit $status ==="
} >> "$LOG" 2>&1
