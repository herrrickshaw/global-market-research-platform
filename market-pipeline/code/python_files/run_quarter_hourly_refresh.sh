#!/bin/bash
# run_quarter_hourly_refresh.sh — every-15-min refresh of the CONSOLIDATED
# views only, never the underlying external collectors.
#
# Deliberately scoped: build_ticker_reference.py --build is a pure
# Postgres-to-Postgres join (ticker_freshness + liquidity_index.parquet +
# the PIT tables), and system_state.py --check-connections is a couple of
# cheap pings — neither touches yfinance/SEC/NSE/any external API. Running
# the actual collectors (screener_kit.update(), yf_intl_pit_fundamentals.py,
# fundamentals_offhours.py) on a 15-min cadence would hit the exact
# YFRateLimitError already observed live this session from two much
# lighter-weight concurrent calls — that risk doesn't buy anything here
# since those sources don't move that fast anyway (EOD OHLCV, quarterly
# fundamentals). This job exists so a dashboard reader never sees numbers
# more than ~15 min older than whatever the last real collection cycle
# (daily/off-hours/weekly) already landed in Postgres.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY="$HERE/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
echo "=== quarter-hourly refresh $(date '+%Y-%m-%d %H:%M:%S %Z') ==="
"$PY" build_ticker_reference.py --build || echo "ticker_reference refresh failed (continuing)"
"$PY" system_state.py --check-connections || echo "connection check failed (continuing)"
echo "=== done ==="
