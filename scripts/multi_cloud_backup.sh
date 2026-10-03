#!/bin/bash
# multi_cloud_backup.sh — encrypted, deduplicated backups of the market-data trees
# to BOTH Dropbox and Google Drive, via BOTH restic and kopia (4 recovery paths).
# Tree list is read from cloud_backup.sh (single source of truth).
# Passphrase file: ~/.config/market-secrets/backup_repo.pass (mode 600).
# Usage: multi_cloud_backup.sh [restic|kopia|all] [googledrive|dropbox|all]
set -uo pipefail
PASS="$HOME/.config/market-secrets/backup_repo.pass"
export RESTIC_PASSWORD_FILE="$PASS"
export KOPIA_PASSWORD="$(cat "$PASS")"
export RCLONE_CONFIG="$HOME/.config/rclone/rclone.conf"
LOG="$HOME/scripts/multi_cloud_backup.log"
TOOL="${1:-all}"; CLOUD="${2:-all}"
LOCK="/tmp/multi_cloud_backup.lock"
if ! mkdir "$LOCK" 2>/dev/null; then echo "another instance running — exit" >>"$LOG"; exit 0; fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# paths from cloud_backup.sh (existing only)
PATHS=$(grep -oE '\$HOME[^"]+' "$HOME/scripts/cloud_backup.sh" | sed "s#\\\$HOME#$HOME#" | sort -u)
EXIST=""; for p in $PATHS; do [ -e "$p" ] && EXIST="$EXIST $p"; done

restic_do() { local r="rclone:$1:restic-market-data"
  restic -r "$r" cat config >/dev/null 2>&1 || restic -r "$r" init 2>&1 | tail -1 | sed "s/^/  [restic $1 init] /"
  restic -r "$r" backup --tag market-data $EXIST 2>&1 | tail -6 | sed "s/^/  [restic $1] /"
  restic -r "$r" forget --keep-daily 7 --keep-weekly 4 --prune 2>&1 | tail -2 | sed "s/^/  [restic $1 prune] /"; }
kopia_do() {
  local RC="--rclone-exe=/opt/homebrew/bin/rclone --rclone-startup-timeout=120s"
  kopia repository connect rclone --remote-path="$1:kopia-market-data" $RC >/dev/null 2>&1 \
    || kopia repository create rclone --remote-path="$1:kopia-market-data" $RC 2>&1 | tail -1 | sed "s/^/  [kopia $1 init] /"
  kopia snapshot create $EXIST 2>&1 | tail -6 | sed "s/^/  [kopia $1] /"; }

{
echo "===== multi-cloud backup $(date '+%F %T') tool=$TOOL cloud=$CLOUD ====="
echo "trees: $(echo $EXIST | wc -w | tr -d ' ')"
for c in googledrive dropbox; do
  [ "$CLOUD" = "all" ] || [ "$CLOUD" = "$c" ] || continue
  if [ "$TOOL" = "all" ] || [ "$TOOL" = "restic" ]; then echo "-- restic -> $c --"; restic_do "$c"; fi
  if [ "$TOOL" = "all" ] || [ "$TOOL" = "kopia" ];  then echo "-- kopia -> $c --";  kopia_do "$c"; fi
done
echo "===== done $(date '+%F %T') ====="
} >> "$LOG" 2>&1
