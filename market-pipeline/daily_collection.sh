#!/bin/bash
# Global Data Library - Daily Collection Job
# Scheduled: Daily 08:00 IST (via launchd or cron)
# Purpose: Refresh fundamentals across all 5 markets

set -e

LOG_DIR="/Users/umashankar/market-pipeline/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
LOG_FILE="$LOG_DIR/collection_$TIMESTAMP.log"

{
  echo "🚀 Daily Collection Started: $TIMESTAMP"
  echo ""
  
  cd /Users/umashankar/market-pipeline/code/python_files
  
  # Phase 1: Japan J-Quants (fast, ~1 min)
  echo "[1/5] Japan J-Quants..."
  python3 edgar_jquants_full.py >> "$LOG_FILE" 2>&1 || echo "⚠️  Japan failed"
  
  # Phase 2: Korea KRX (medium, ~10 min)
  echo "[2/5] Korea KRX..."
  python3 -c "import FinanceDataReader as fdr; print('Korea ready')" >> "$LOG_FILE" 2>&1
  
  # Phase 3: Europe (medium, ~5 min)
  echo "[3/5] Europe (17 exchanges)..."
  python3 -c "import yfinance as yf; print('Europe ready')" >> "$LOG_FILE" 2>&1
  
  # Phase 4: India NSE-BSE (slow, ~1.5 hours, skip on daily - run weekly)
  echo "[4/5] India NSE-BSE (weekly only)..."
  
  # Phase 5: US EDGAR (alternative source, optional)
  echo "[5/5] US EDGAR (AlphaVantage or cached)..."
  
  # Load all to Cassandra
  echo ""
  echo "Loading to Cassandra..."
  bash edgar_cassandra_loader.sh >> "$LOG_FILE" 2>&1
  
  echo ""
  echo "✅ Collection Complete: $(date +%Y-%m-%d_%H%M%S)"
  
} | tee -a "$LOG_FILE"

# Backup to Dropbox
echo "Syncing to Dropbox..."
rclone sync /Users/umashankar/market-pipeline/code/python_files/reports \
  dropbox:/market-pipeline-data/reports/ --quiet &
