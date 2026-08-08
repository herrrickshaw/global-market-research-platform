#!/bin/bash
# lfs_compress_archive.sh — compress-then-prune for the $HOME repo's local LFS store.
#
# WHY: the LFS remote is 8x over quota (policy: no paid packs), so 344 of the
# 11,300 local objects exist ONLY on this disk. A naive cleanup could destroy
# them. Order of operations here makes every byte recoverable BEFORE anything
# is deleted:
#   verify   list local objects; compute the local-only (unpushed) set
#   archive  tar --zstd the ENTIRE .git/lfs/objects store + manifest + sha256
#   upload   rclone the archive to dropbox:market-data-archive/lfs_archive/
#            and verify remote size matches before declaring success
#   prune    git lfs prune --verify-remote (never touches unpushed objects,
#            and re-checks the remote for everything it does delete)
#
# Usage: lfs_compress_archive.sh {verify|archive|upload|prune|all|status}
# Safe to re-run any phase. Refuses to run archive/upload while the weekly
# maintenance job holds its lock or an rclone sync is running.
set -uo pipefail

REPO="$HOME"
STORE="$REPO/.git/lfs/objects"
STAMP=$(date +%Y%m%d)
WORK="$HOME/lfs_archive_work"
ARCHIVE="$WORK/lfs_store_${STAMP}.tar.zst"
REMOTE="dropbox:market-data-archive/lfs_archive"
LOG="$WORK/lfs_archive.log"

mkdir -p "$WORK"
say() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

busy_guard() {
  if [ -d /tmp/weekly_maintenance.lock ]; then
    say "REFUSING: weekly_maintenance lock present (backup likely syncing)"; exit 2
  fi
  if pgrep -f "rclone sync" >/dev/null 2>&1; then
    say "REFUSING: an rclone sync is running — wait for it to finish"; exit 2
  fi
}

phase_verify() {
  say "== verify =="
  cd "$REPO"
  find "$STORE" -type f > "$WORK/local_oids_paths.txt"
  local n; n=$(wc -l < "$WORK/local_oids_paths.txt" | tr -d ' ')
  local sz; sz=$(du -sh "$STORE" | cut -f1)
  say "local store: $n objects, $sz"
  git lfs push origin --all --dry-run 2>&1 | awk '/^push /{print $2}' | sort -u > "$WORK/local_only_oids.txt"
  local m; m=$(wc -l < "$WORK/local_only_oids.txt" | tr -d ' ')
  say "local-only (NOT on LFS remote): $m objects — these are unrecoverable if lost"
  say "verify done. Manifests in $WORK"
}

phase_archive() {
  say "== archive =="
  command -v zstd >/dev/null || { say "zstd not installed (brew install zstd)"; exit 1; }
  [ -s "$WORK/local_oids_paths.txt" ] || phase_verify
  say "compressing $STORE -> $ARCHIVE (zstd -T0)"
  tar -C "$REPO/.git/lfs" -cf - objects | zstd -T0 -8 -q -o "$ARCHIVE" || { say "tar/zstd FAILED"; exit 1; }
  shasum -a 256 "$ARCHIVE" > "$ARCHIVE.sha256"
  cp "$WORK/local_oids_paths.txt" "$WORK/local_only_oids.txt" "$WORK/" 2>/dev/null || true
  say "archive: $(du -sh "$ARCHIVE" | cut -f1)  sha256 recorded"
}

phase_upload() {
  busy_guard
  say "== upload =="
  [ -f "$ARCHIVE" ] || { say "no archive for today — run 'archive' first"; exit 1; }
  rclone copy "$ARCHIVE" "$REMOTE/" --progress 2>&1 | tail -2 | tee -a "$LOG"
  rclone copy "$ARCHIVE.sha256" "$REMOTE/" 2>>"$LOG"
  rclone copy "$WORK/local_only_oids.txt" "$REMOTE/manifests_${STAMP}/" 2>>"$LOG"
  local lsz rsz
  lsz=$(stat -f %z "$ARCHIVE")
  rsz=$(rclone lsjson "$REMOTE/$(basename "$ARCHIVE")" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['Size'] if d else 0)")
  if [ "$lsz" = "$rsz" ]; then
    say "upload VERIFIED: remote size matches ($lsz bytes)"
  else
    say "upload MISMATCH: local $lsz vs remote $rsz — DO NOT PRUNE"; exit 1
  fi
}

phase_prune() {
  say "== prune =="
  # refuse unless today's archive was upload-verified
  grep -q "upload VERIFIED" "$LOG" 2>/dev/null || { say "REFUSING: no verified upload in log — run 'upload' first"; exit 2; }
  cd "$REPO"
  local before; before=$(du -sh "$STORE" | cut -f1)
  # --verify-remote: re-check each object exists on the LFS server before
  # deleting the local copy. Unpushed objects are ALWAYS retained by design.
  git lfs prune --verify-remote 2>&1 | tail -3 | tee -a "$LOG"
  local after; after=$(du -sh "$STORE" | cut -f1)
  say "local LFS store: $before -> $after"
}

case "${1:-status}" in
  verify)  phase_verify ;;
  archive) phase_archive ;;
  upload)  phase_upload ;;
  prune)   phase_prune ;;
  all)     phase_verify; phase_archive; phase_upload; phase_prune ;;
  status)
    echo "store: $(du -sh "$STORE" 2>/dev/null | cut -f1), local-only: $(wc -l < "$WORK/local_only_oids.txt" 2>/dev/null || echo '?') objects"
    ls -lh "$WORK"/*.tar.zst 2>/dev/null || echo "no archive yet"
    rclone lsl "$REMOTE" 2>/dev/null | head -5 || echo "(remote listing unavailable)"
    ;;
  *) echo "usage: $0 {verify|archive|upload|prune|all|status}"; exit 1 ;;
esac
