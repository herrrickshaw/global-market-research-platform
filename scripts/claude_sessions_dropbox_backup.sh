#!/bin/bash
# claude_sessions_dropbox_backup.sh — one-way copy of the REST of
# ~/.claude/projects/ (session transcripts, subagent logs — everything
# except memory/, which memory_dropbox_backup.sh already covers separately)
# to Dropbox. Written 2026-09-23, same day as the memory-dir backup, per
# explicit follow-up request to also cover this.
#
# Same rationale as memory_dropbox_backup.sh: `rclone copy`, never `sync` —
# a sync would propagate an accidental local delete (or this machine's own
# routine pruning of old session files) to the backup and destroy history
# there too. `copy` only adds/updates remotely, so pruned-locally files stay
# recoverable from Dropbox indefinitely. See feedback_memory_directory_unbacked_up
# memory for the fuller writeup (covers both scripts).
#
# ~1.9GB / ~10k files as of 2026-09-23 (mostly -Users-umashankar/*.jsonl
# session transcripts + subagents/ subfolders across ~8 project dirs). First
# run is the slow one; every run after only transfers deltas.
#
# memory/ is excluded here on purpose — it has its own script, its own
# destination (dropbox:claude-memory-backup/memory), and uploading it twice
# would just double the nightly transfer for identical content.
set -uo pipefail

SRC="/Users/umashankar/.claude/projects"
DEST="dropbox:claude-memory-backup/projects"
RCLONE=/opt/homebrew/bin/rclone
LOG="/Users/umashankar/scripts/claude_sessions_dropbox_backup.log"

ACCT_LOCK="/tmp/cloud_backup.rclone-dropbox.lock"
_waited=0
while [ -d "$ACCT_LOCK" ] && [ "$_waited" -lt 60 ]; do
  sleep 10; _waited=$((_waited + 10))
done

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') ==="
  "$RCLONE" copy "$SRC" "$DEST" \
    --exclude "-Users-umashankar/memory/**" \
    --exclude ".DS_Store" \
    --transfers 16 --checkers 16
  status=$?
  if [ "$status" -eq 0 ]; then
    echo "ok: $("$RCLONE" size "$DEST" --json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(f"{d[\"count\"]} files, {d[\"bytes\"]} bytes")' 2>/dev/null || echo 'copy succeeded')"
  else
    echo "FAILED: rclone copy exit $status"
  fi
} >> "$LOG" 2>&1
