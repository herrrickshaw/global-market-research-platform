#!/bin/bash
# cloud_restore.sh — pull backed-up market data trees back from Dropbox.
#
# WHY THIS EXISTS
# ───────────────
# This is the WITHDRAWAL half of cloud_backup.sh, and until 2026-08-20 it lived
# only inside an n8n workflow ("Dropbox Market Data — Backup & Restore") reached
# through an HTTP webhook. That is the wrong home for a disaster-recovery path
# twice over:
#
#   * n8n's runtime was DELETED. `~/.nvm/versions/node/` is empty, so the plist's
#     interpreter no longer exists and the job has failed with EX_CONFIG on every
#     load since ~20 Jul — silently, for a month. The restore path was gone and
#     nothing said so.
#   * Restore is what you run when things are already broken. Putting it behind a
#     Node daemon, a SQLite database and an HTTP listener means the recovery tool
#     has more moving parts than the thing it recovers.
#
# So it is a shell script that calls rclone. Nothing runs in the background,
# nothing can die between now and the day it is needed.
#
# The allowlisting is ported verbatim from the n8n Code node, because it was
# right: the tree must be one of the five that are actually backed up, and the
# destination must be a plain absolute path. Neither ever reaches a shell
# unvalidated — a restore that can be talked into writing anywhere is a worse
# problem than the outage it is fixing.
#
#   cloud_restore.sh list                          # what is in the current mirror
#   cloud_restore.sh history                       # dated prior versions
#   cloud_restore.sh restore <tree> [dest] [date]  # pull a tree back
#
#   cloud_restore.sh restore warehouse_duckdb
#   cloud_restore.sh restore bhavcopy_cache /Users/umashankar/restore/bhav 2026-08-14
#
# Nothing here overwrites in place: the default destination is under
# ~/restore/<tree>, deliberately NOT the live path. Inspect what came back, then
# move it yourself. An automated restore straight over live data is how a bad
# backup becomes a bad production tree.
set -uo pipefail

RCLONE=/opt/homebrew/bin/rclone
REMOTE="dropbox:market-data-archive"
TREES=(market_cache bhavcopy_cache cache_seed gmd_cache_seed warehouse_duckdb)

die() { echo "cloud_restore: $*" >&2; exit 1; }

[ -x "$RCLONE" ] || die "rclone not found at $RCLONE"

action="${1:-list}"

case "$action" in
  list)
    echo "== current mirror: $REMOTE/current =="
    "$RCLONE" lsd "$REMOTE/current" --timeout 60s || die "lsd failed"
    "$RCLONE" size "$REMOTE/current" --json --timeout 60s
    ;;

  history)
    # dated version folders — where changed and deleted files are MOVED by
    # cloud_backup.sh rather than destroyed, so a bad sync is recoverable.
    echo "== dated versions: $REMOTE/history =="
    "$RCLONE" lsd "$REMOTE/history" --timeout 60s || die "lsd failed"
    ;;

  restore)
    tree="${2:-}"
    [ -n "$tree" ] || die "usage: cloud_restore.sh restore <tree> [dest] [YYYY-MM-DD]"
    ok=0; for t in "${TREES[@]}"; do [ "$t" = "$tree" ] && ok=1; done
    [ "$ok" = 1 ] || die "tree must be one of: ${TREES[*]}"

    dest="${3:-/Users/umashankar/restore/$tree}"
    case "$dest" in
      /*) ;;
      *)  die "dest must be an absolute path" ;;
    esac
    # Same character class as the n8n validator, and the same .. rejection.
    printf '%s' "$dest" | grep -qE '^/[A-Za-z0-9_/.-]+$' \
      || die "dest must be a plain absolute path (A-Za-z0-9_/.- only)"
    case "$dest" in *..*) die "dest must not contain .." ;; esac

    date_arg="${4:-}"
    if [ -n "$date_arg" ]; then
      printf '%s' "$date_arg" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' \
        || die "date must be YYYY-MM-DD"
      src="$REMOTE/history/$date_arg/$tree"
    else
      src="$REMOTE/current/$tree"
    fi

    echo "== restore =="
    echo "  from : $src"
    echo "  to   : $dest"
    mkdir -p "$dest" || die "cannot create $dest"
    "$RCLONE" copy "$src" "$dest" \
      --transfers 4 --retries 5 --low-level-retries 20 \
      --stats-one-line --timeout 10m || die "rclone copy failed"
    echo "  ✅ restored to $dest — inspect it before moving anything into place"
    du -sh "$dest" 2>/dev/null
    ;;

  *)
    die "action must be: list | history | restore"
    ;;
esac
