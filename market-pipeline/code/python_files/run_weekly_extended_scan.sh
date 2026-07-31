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
# PIT fundamentals trickle for the rest of Tier 3 (AU/CA/DE/HK/SA/TW use the
# rich local fundamentals_history/ files with only the fake filed-date fixed;
# BR/CH/SE/SG/UK/ZA fall back to pure yfinance quarterly_income_stmt — see
# yf_intl_pit_fundamentals.py's module docstring). SEQUENCED AFTER the OHLCV
# scan above, never concurrent with it — running both at once against
# yfinance produced real rate-limit collisions when tested together
# (2026-07-31). JP/KR/CN keep their own daily off-hours trickle
# (run_fundamentals_offhours.sh) — not repeated here.
for m in AU CA DE HK SA TW BR CH SE SG UK ZA; do
  "$PY" yf_intl_pit_fundamentals.py --collect --market "$m" --limit 120 \
    || echo "intl PIT collect ($m) failed (continuing)"
done
"$PY" yf_intl_pit_fundamentals.py --load || echo "intl PIT load failed (continuing)"
"$PY" build_ticker_reference.py --build || echo "ticker_reference rebuild failed (continuing)"
echo "=== done $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
exit $RC
