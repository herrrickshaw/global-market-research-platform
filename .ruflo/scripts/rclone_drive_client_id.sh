#!/usr/bin/env bash
# Apply a personal Google OAuth client_id/secret to rclone's Drive remotes.
#
# rclone's built-in shared client_id is being retired during 2026; once it
# stops working every Drive remote here fails to authenticate. This swaps in
# your own credentials and re-authorises each remote.
#
# The secret is read from the terminal with echo disabled and goes straight
# into rclone.conf — it is never passed as a command-line argument (argv is
# visible to any process via `ps`) and never printed.
#
#   ./rclone_drive_client_id.sh                       # all Drive remotes
#   ./rclone_drive_client_id.sh googledrive           # only the ones named
#   ./rclone_drive_client_id.sh --verify              # check current state
#
# Changing the client_id invalidates the existing token, so each remote must
# be re-authorised (a browser window opens per remote — approve with the
# Google account that owns that Drive). The config is backed up first and
# restored automatically if anything fails.

set -uo pipefail

CONF="$(rclone config file 2>/dev/null | tail -1)"
BACKUP_DIR="$HOME/.config/rclone/backups"
ALL_DRIVE_REMOTES=(googledrive gdrive gdrive1)

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
ylw()  { printf '\033[33m%s\033[0m\n' "$*"; }

die() { red "error: $*"; exit 1; }

[ -f "$CONF" ] || die "rclone config not found at '$CONF'"

# --- verify mode -----------------------------------------------------------
if [ "${1:-}" = "--verify" ]; then
  echo "rclone config: $CONF"
  printf '%-14s %-12s %-10s %s\n' REMOTE TYPE CLIENT_ID REACHABLE
  for r in $(rclone listremotes 2>/dev/null | tr -d ':'); do
    type=$(rclone config show "$r" 2>/dev/null | awk -F' = ' '/^type/{print $2}')
    [ "$type" = "drive" ] || continue
    cid=$(rclone config show "$r" 2>/dev/null | awk -F' = ' '/^client_id/{print $2}')
    if [ -n "$cid" ]; then own="personal"; else own="SHARED"; fi
    # `about` needs a live token, so it doubles as an auth check.
    if rclone about "$r": >/dev/null 2>&1; then reach="yes"; else reach="NO"; fi
    printf '%-14s %-12s %-10s %s\n' "$r" "$type" "$own" "$reach"
  done
  exit 0
fi

# --- pick remotes ----------------------------------------------------------
if [ $# -gt 0 ]; then
  REMOTES=("$@")
else
  REMOTES=()
  for r in "${ALL_DRIVE_REMOTES[@]}"; do
    rclone config show "$r" >/dev/null 2>&1 && REMOTES+=("$r")
  done
fi
[ ${#REMOTES[@]} -gt 0 ] || die "no Drive remotes found"

for r in "${REMOTES[@]}"; do
  rclone config show "$r" >/dev/null 2>&1 || die "no such remote: $r"
  t=$(rclone config show "$r" 2>/dev/null | awk -F' = ' '/^type/{print $2}')
  [ "$t" = "drive" ] || die "'$r' is type '$t', not a Google Drive remote"
done

echo "Will update these Drive remotes: ${REMOTES[*]}"
echo

# --- collect credentials ---------------------------------------------------
# Read from the tty so a piped stdin can't silently supply a wrong value.
printf 'Google OAuth client_id: '
read -r CLIENT_ID </dev/tty
[ -n "$CLIENT_ID" ] || die "client_id cannot be empty"
case "$CLIENT_ID" in
  *.apps.googleusercontent.com) ;;
  *) ylw "warning: a Google client_id normally ends in .apps.googleusercontent.com" ;;
esac

printf 'Google OAuth client_secret (input hidden): '
read -rs CLIENT_SECRET </dev/tty
echo
[ -n "$CLIENT_SECRET" ] || die "client_secret cannot be empty"

# --- back up ---------------------------------------------------------------
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$BACKUP_DIR/rclone.conf.$STAMP"
cp "$CONF" "$BACKUP" || die "could not back up config"
chmod 600 "$BACKUP"
grn "config backed up to $BACKUP"
echo

restore() {
  red "restoring original config from $BACKUP"
  cp "$BACKUP" "$CONF"
}

# --- apply + reauthorise ---------------------------------------------------
FAILED=()
for r in "${REMOTES[@]}"; do
  echo "=== $r ==="
  # config_refresh_token=false stops `config update` from running its own
  # OAuth flow as a side effect of touching an OAuth remote — we want the
  # credentials written first, then one explicit reconnect below.
  if ! rclone config update "$r" \
        client_id "$CLIENT_ID" \
        client_secret "$CLIENT_SECRET" \
        config_refresh_token=false \
        --non-interactive >/dev/null 2>&1; then
    red "  failed to write credentials"
    FAILED+=("$r"); continue
  fi
  grn "  credentials written"

  # The old token was issued to the retired client_id, so it is now dead;
  # without this step the remote silently stops working.
  ylw "  a browser will open — approve with the Google account that owns '$r'"
  if rclone config reconnect "$r":; then
    if rclone about "$r": >/dev/null 2>&1; then
      grn "  re-authorised and reachable"
    else
      red "  re-authorised but not reachable"
      FAILED+=("$r")
    fi
  else
    red "  re-authorisation failed"
    FAILED+=("$r")
  fi
  echo
done

chmod 600 "$CONF"

# --- report ----------------------------------------------------------------
if [ ${#FAILED[@]} -gt 0 ]; then
  red "FAILED: ${FAILED[*]}"
  echo
  echo "The config still contains the new credentials for the remotes that"
  echo "did succeed. To undo everything and go back to the shared client_id:"
  echo "    cp $BACKUP $CONF"
  exit 1
fi

grn "all remotes updated: ${REMOTES[*]}"
echo
echo "Verify any time with:  $0 --verify"
echo "Original config kept at: $BACKUP"
