#!/bin/bash
# Auto-restart wrapper: akshare collector keeps dying mid-run; resume until ~complete.
cd /Users/umashankar/market-pipeline/code/python_files || exit 1
PY=.venv/bin/python3
F=/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/CN_deep.parquet
LOG=/private/tmp/claude-501/-Users-umashankar/38173149-3030-43dc-97c5-a0ced49bd927/scratchpad/cn_loop.log
for i in $(seq 1 40); do
  $PY -u cn_akshare_collect.py 600 >> "$LOG" 2>&1
  n=$($PY -c "import pandas as pd;print(pd.read_parquet('$F').ticker.nunique())" 2>/dev/null || echo 0)
  echo "[$(date '+%T')] pass $i: $n tickers" >> "$LOG"
  [ "$n" -ge 550 ] && { echo "DONE at $n" >> "$LOG"; break; }
  sleep 3
done
