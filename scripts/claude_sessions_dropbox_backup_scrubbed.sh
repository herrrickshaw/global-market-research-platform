#!/bin/bash
# claude_sessions_dropbox_backup_scrubbed.sh — replaces the 22:20
# claude_sessions_dropbox_backup.sh cron entry: redact secrets in
# ~/.claude/projects BEFORE the nightly one-way rclone copy to Dropbox.
#
# Why: the 2026-10-26 audit found 11 live API keys in session transcripts that
# this backup had been copying to Dropbox nightly (copy never deletes, so a key
# uploaded once stays there). See scrub_transcript_secrets.py for the method.
#
# Fails CLOSED: if the scrub step errors, nothing is uploaded tonight. Files
# that were skipped (still being written by a live session) or could not be
# redacted safely are excluded from tonight's upload via --exclude-from and
# re-checked on the next run (pending list), so an unredacted transcript never
# reaches Dropbox just because it was open at 22:20.
#
# Installed 2026-10-26 in place of claude_sessions_dropbox_backup.sh (kept for
# rollback: swap the 22:20 crontab line's script path back), after a manual full
# scrub_transcript_secrets.py --apply run. First nightly run has no stamp yet,
# so it scans the whole tree (~5 min); later runs only scan changed files.
set -uo pipefail

SRC="/Users/umashankar/.claude/projects"
DEST="dropbox:claude-memory-backup/projects"
RCLONE=/opt/homebrew/bin/rclone
PY=/opt/homebrew/bin/python3   # explicit: cron's minimal PATH (feedback_launchd_minimal_path)
SCRUB=/Users/umashankar/scripts/scrub_transcript_secrets.py
STAMP=/Users/umashankar/.claude/.scrub_stamp
PENDING=/Users/umashankar/.claude/.scrub_pending.lst
LOG="/Users/umashankar/scripts/claude_sessions_dropbox_backup.log"
HELD=$(mktemp -t scrub-held) || exit 1
trap 'rm -f "$HELD"' EXIT

ACCT_LOCK="/tmp/cloud_backup.rclone-dropbox.lock"
_waited=0
while [ -d "$ACCT_LOCK" ] && [ "$_waited" -lt 60 ]; do
  sleep 10; _waited=$((_waited + 10))
done

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S') (scrubbed) ==="
  "$PY" "$SCRUB" --apply --local-only \
      --since-stamp "$STAMP" --pending "$PENDING" --skipped-out "$HELD"
  scrub=$?
  # 0 = clean, 2 = some files unsafe to rewrite (they are in $HELD and excluded below)
  if [ "$scrub" -ne 0 ] && [ "$scrub" -ne 2 ]; then
    echo "FAILED: scrub exit $scrub — upload skipped tonight"
    exit 1
  fi
  [ -s "$HELD" ] && echo "holding back $(wc -l < "$HELD" | tr -d ' ') file(s) until next run"

  "$RCLONE" copy "$SRC" "$DEST" \
    --exclude "-Users-umashankar/memory/**" \
    --exclude ".DS_Store" \
    --exclude ".scrub_*" \
    --exclude-from "$HELD" \
    --transfers 16 --checkers 16
  status=$?
  if [ "$status" -eq 0 ]; then
    echo "ok: $("$RCLONE" size "$DEST" --json 2>/dev/null | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(f"{d[\"count\"]} files, {d[\"bytes\"]} bytes")' 2>/dev/null || echo 'copy succeeded')"
  else
    echo "FAILED: rclone copy exit $status"
  fi
} >> "$LOG" 2>&1
