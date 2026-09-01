#!/bin/zsh
# Weekly graphify global-graph refresh (token-free: local tree-sitter only).
# 1) re-extract all LOCAL repos  2) pull+re-extract gh-clones + clone any NEW repos
# 3) rebuild merged global graph  4) reload the launchd MCP server so it serves fresh data.
set -u
LOG=~/.ruflo/logs/graphify_refresh.log
GRAPHIFY=~/.venvs/graphifyy/bin/graphify
export GIT_LFS_SKIP_SMUDGE=1
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# single-instance lock (mkdir is atomic) — prevents concurrent runs racing on files
LOCK=~/.ruflo/logs/.graphify_refresh.lock
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') refresh already running — skipping this trigger" >> "$LOG"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT INT TERM
{
  echo "===== graphify refresh $(date '+%F %T') ====="

  echo "[1/4] re-extracting local repos..."
  /usr/bin/python3 ~/.ruflo/scripts/graphify_all_repos.py >/dev/null 2>&1 && echo "  local ok"

  echo "[2/4] pulling + re-graphing gh-clones + cloning new repos..."
  for d in ~/.graphify/gh-clones/*/; do
    [ -d "$d/.git" ] || continue
    git -C "$d" pull --ff-only --quiet 2>/dev/null
  done
  /usr/bin/python3 ~/.ruflo/scripts/graphify_clone_missing.py >/dev/null 2>&1 && echo "  clones ok"

  echo "[3/4] rebuilding merged global graph..."
  /usr/bin/python3 ~/.ruflo/scripts/graphify_merge_direct.py 2>&1 | tail -1

  echo "[4/4] reloading MCP server (picks up fresh graph)..."
  launchctl kickstart -k gui/$(id -u)/com.graphify.mcp 2>/dev/null && echo "  server reloaded"

  echo "===== done $(date '+%F %T') ====="
} >> "$LOG" 2>&1
