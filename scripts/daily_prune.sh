#!/bin/bash
# daily_prune.sh — reclaim the LOCAL bloat that regrows every day.
# Only removes regenerable / abandoned / already-backed-up artifacts. Never touches
# active data, the pipeline, or cloud placeholders. Logs to ~/scripts/daily_prune.log.
# Wired to launchd com.user.dailyprune (09:15 daily). Manual run: bash ~/scripts/daily_prune.sh
set -uo pipefail
LOG="$HOME/scripts/daily_prune.log"
LOCK="/tmp/daily_prune.lock"
if ! mkdir "$LOCK" 2>/dev/null; then echo "$(date '+%F %T') another instance running" >>"$LOG"; exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
{
echo "===== daily prune $(date '+%F %T') ====="
df -h "$HOME" | awk 'NR==2{print "  before: "$4" free ("$5")"}'

# 1. Abandoned git tmp_pack debris (OOM-gc leftovers, no .idx) — the recurring ~22G hazard.
#    Guard: skip if any gc/repack is running, and only files >60min old (never a live build).
if ! pgrep -f 'git.*(gc|repack|pack-objects)' >/dev/null 2>&1; then
  for repo in "$HOME/.git" "$HOME"/repos/*/.git "$HOME"/market-pipeline/.git; do
    [ -d "$repo/objects/pack" ] || continue
    find "$repo/objects/pack" -name 'tmp_pack_*' -type f -mmin +60 -print -delete 2>/dev/null \
      | sed 's#^#  rm git-debris: #'
  done
else
  echo "  (git maintenance running — skipped tmp_pack sweep)"
fi

# 2. Old pg_cloud_backup dumps — keep newest only (daily ~3G each, already on Dropbox pg/).
D="$HOME/.cache/pg_cloud_backup"
if [ -d "$D" ]; then
  ls -t "$D"/*.dump 2>/dev/null | tail -n +2 | while IFS= read -r f; do echo "  rm old pg-dump: $(basename "$f")"; rm -f "$f"; done
fi

# 3. Regenerable package caches.
npm cache clean --force >/dev/null 2>&1 && echo "  npm cache cleaned"
command -v uv >/dev/null 2>&1 && uv cache prune >/dev/null 2>&1 && echo "  uv cache pruned"

# 4. Stale rotated logs >30d (compress, don't delete — keep audit trail small).
find "$HOME/.local/state" "$HOME/scripts" -name '*.log' -type f -size +20M -mtime +14 2>/dev/null \
  | while IFS= read -r f; do gzip -f "$f" 2>/dev/null && echo "  gzipped log: $(basename "$f")"; done

df -h "$HOME" | awk 'NR==2{print "  after:  "$4" free ("$5")"}'
echo "===== done $(date '+%F %T') ====="
} >> "$LOG" 2>&1
