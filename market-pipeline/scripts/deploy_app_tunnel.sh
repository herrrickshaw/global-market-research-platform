#!/bin/bash
# deploy_app_tunnel.sh — expose the FastAPI+React app via a Cloudflare quick tunnel.
#
# The backend depends on LOCAL Cassandra (25k instruments), so the Mac stays the
# server; this tunnels it out rather than migrating it. Quick tunnels need no
# account but mint a NEW random URL each start — check the printed URL (or
# /tmp/tunnel.log). For a STABLE private URL, install the Tailscale app and
# `tailscale serve 5173` instead (needs one-time login).
#
# ⚠️ SECURITY: the app has NO auth. A quick-tunnel URL is unguessable but
# public — treat the link as a secret; do not post it anywhere.
set -uo pipefail

BACKEND_PY_UVICORN="$HOME/Library/Python/3.9/bin/uvicorn"   # py3.9 has fastapi+cassandra-driver

echo "==> backend :8000"
pkill -f "uvicorn main:app" 2>/dev/null; sleep 1
(cd "$HOME/backend" && nohup "$BACKEND_PY_UVICORN" main:app --port 8000 \
  > /tmp/backend_deploy.log 2>&1 &)

echo "==> frontend :5173"
pkill -f "vite" 2>/dev/null; sleep 1
(cd "$HOME/frontend" && nohup npm run dev > /tmp/frontend_deploy.log 2>&1 &)

echo "==> cloudflared tunnel"
pkill -f "cloudflared tunnel" 2>/dev/null; sleep 1
nohup cloudflared tunnel --url http://localhost:5173 > /tmp/tunnel.log 2>&1 &

sleep 10
URL=$(grep -oE "https://[a-z-]+\.trycloudflare\.com" /tmp/tunnel.log | head -1)
curl -s -o /dev/null -w "  frontend %{http_code}\n" http://localhost:5173/
curl -s -o /dev/null -w "  backend  %{http_code}\n" http://localhost:8000/api/db/status
echo ""
echo "  📱 App URL: ${URL:-<check /tmp/tunnel.log>}"
