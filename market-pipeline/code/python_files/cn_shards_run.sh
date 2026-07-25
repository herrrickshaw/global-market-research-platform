#!/bin/bash
# Launch N parallel CN shard workers, restart any that die, merge when all complete.
cd /Users/umashankar/market-pipeline/code/python_files || exit 1
PY=.venv/bin/python3
N=6
LOG=/private/tmp/claude-501/-Users-umashankar/38173149-3030-43dc-97c5-a0ced49bd927/scratchpad/cn_shards.log
: > "$LOG"
for round in $(seq 1 25); do
  pids=()
  for s in $(seq 0 $((N-1))); do
    $PY -u cn_shard_collect.py $N $s >> "$LOG" 2>&1 &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p"; done          # barrier: all shards this round
  # merge + check coverage
  $PY merge_cn_shards.py >> "$LOG" 2>&1
  n=$($PY -c "import pandas as pd;print(pd.read_parquet('/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/CN_deep.parquet').ticker.nunique())" 2>/dev/null || echo 0)
  echo "[$(date '+%T')] round $round -> $n tickers" >> "$LOG"
  [ "$n" -ge 550 ] && { echo "DONE $n" >> "$LOG"; break; }
done
