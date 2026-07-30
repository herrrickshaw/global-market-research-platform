#!/bin/bash
# run_weekly_extended_scan.sh — Tier 3 markets (market_tiers.py): weekly
# OHLCV refresh + Darvas screen + freshness ledger, then rebuild the
# consolidated ticker_reference dictionary and liquidity index so the
# mailer's technical-only section (send_mailer.py::_technical_section)
# and market_daily.ticker_reference both reflect the new week's data.
#
# Resolves its own venv, same reasoning as run_fundamentals_offhours.sh —
# never inherit `python3` from the caller's PATH under launchd.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
export MARKET_CACHE="/Users/umashankar/market-pipeline/market_cache"
export BHAV_CACHE="/Users/umashankar/market-pipeline/data/bhavcopy_cache"
PY="$HERE/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
echo "=== weekly extended scan (Tier 3) $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
"$PY" weekly_extended_scan.py
RC=$?
"$PY" build_ticker_reference.py --build || echo "ticker_reference rebuild failed (continuing)"
echo "=== done $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
exit $RC
