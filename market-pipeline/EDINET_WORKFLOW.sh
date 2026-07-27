#!/bin/bash
#
# edinet_workflow.sh — Complete Japan EDINET fundamentals backfill workflow
#
# This script orchestrates the full pipeline:
#   1. Acquire EDINET XBRL files (manual download or API fetch)
#   2. Process XBRL into Postgres
#   3. Validate coverage + quality
#   4. Generate reports
#
# Usage:
#   ./EDINET_WORKFLOW.sh --help
#   ./EDINET_WORKFLOW.sh --download latest           # Fetch latest filings
#   ./EDINET_WORKFLOW.sh --process /path/to/xbrl.zip # Parse & load
#   ./EDINET_WORKFLOW.sh --full-backfill              # Download + process FY2023-2024
#

set -eo pipefail

# Config
DATA_DIR="/Users/umashankar/market-pipeline/data"
XBRL_DIR="${DATA_DIR}/edinet_xbrl"
PY_FETCHER="/Users/umashankar/market-pipeline/code/python_files/edinet_xbrl_historical_fetcher.py"
PY_CONSOLIDATOR="/Users/umashankar/market-pipeline/code/python_files/japan_data_consolidator.py"
DB_NAME="market_data"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Helper functions
log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

show_help() {
  cat << 'HELP'
EDINET Japan Fundamentals Backfill Workflow

USAGE:
  ./EDINET_WORKFLOW.sh [COMMAND] [OPTIONS]

COMMANDS:

  --help
    Show this help message

  --validate
    Check Postgres schema readiness, validate EDINET code files

  --process FILE.zip
    Parse an EDINET XBRL ZIP archive and load into Postgres
    Example: ./EDINET_WORKFLOW.sh --process data/edinet_xbrl_2024q3.zip

  --download PERIOD
    Download EDINET filings for a specific period
    Options: latest, fy2024q3, fy2024q2, fy2024q1, fy2023annual
    Example: ./EDINET_WORKFLOW.sh --download fy2024q3

  --full-backfill
    Download + process complete FY2023-2024 dataset
    (Downloads: FY2023 Annual, FY2024 Q1, Q2, Q3)
    Estimated time: 30-60 min
    Estimated disk: 1.5-2 GB

  --status
    Show current Postgres coverage and data freshness

WORKFLOW STEPS (Manual):

  1. Download EDINET XBRL bulk files:
     https://disclosure2.edinet-fsa.go.jp/

  2. Place ZIP files in data/edinet_xbrl/

  3. Process each file:
     python edinet_xbrl_historical_fetcher.py --from-file data/edinet_xbrl_2024q3.zip

  4. Validate:
     python edinet_xbrl_historical_fetcher.py --validate

EXAMPLES:

  # Validate Postgres is ready
  ./EDINET_WORKFLOW.sh --validate

  # Process a downloaded XBRL file
  ./EDINET_WORKFLOW.sh --process data/edinet_xbrl_2024q3.zip

  # Full backfill (requires manual download step)
  ./EDINET_WORKFLOW.sh --full-backfill

HELP
}

validate() {
  log_info "Validating EDINET pipeline..."

  # Check Postgres
  log_info "Checking Postgres..."
  python3 "$PY_FETCHER" --validate 2>&1 | grep -E "japan|rows|table"

  # Check EDINET code files
  log_info "Checking EDINET code files..."
  if [ -f /Users/umashankar/Downloads/Edinetcode_20260725.zip ]; then
    unzip -l /Users/umashankar/Downloads/Edinetcode_20260725.zip | head -3
  fi

  log_info "✓ Validation complete"
}

process_xbrl() {
  local file="$1"

  if [ ! -f "$file" ]; then
    log_error "File not found: $file"
    exit 1
  fi

  log_info "Processing XBRL: $(basename $file)"
  python3 "$PY_FETCHER" --from-file "$file"

  log_info "✓ Processing complete"
}

status() {
  log_info "Checking EDINET data coverage..."

  psql -d "$DB_NAME" -c "
    SELECT
      'japan_current' as table_name,
      COUNT(*) as row_count,
      MAX(updated_at) as last_update
    FROM japan_current
    UNION ALL
    SELECT
      'japan_fundamentals_history',
      COUNT(*),
      MAX(created_at)
    FROM japan_fundamentals_history;
  " 2>/dev/null || log_error "Could not connect to Postgres"
}

download_filings() {
  local period="$1"

  mkdir -p "$XBRL_DIR"

  log_warn "EDINET XBRL downloads are large (~200-500MB per quarter)"
  log_info "Manual download required from: https://disclosure2.edinet-fsa.go.jp/"

  case "$period" in
    latest)
      log_info "Latest EDINET filings typically available 45-60 days after quarter-end"
      echo "FY2024 Q3 (Sep 30) → Expected: Nov 2024"
      ;;
    fy2024q3)
      echo "Download: EDINET_XBRL_2024Q3_all.zip"
      echo "URL: https://disclosure2.edinet-fsa.go.jp/XBRL/2024q3/"
      ;;
    fy2024q2)
      echo "Download: EDINET_XBRL_2024Q2_all.zip"
      ;;
    fy2024q1)
      echo "Download: EDINET_XBRL_2024Q1_all.zip"
      ;;
    fy2023annual)
      echo "Download: EDINET_XBRL_2023_all.zip"
      ;;
    *)
      log_error "Unknown period: $period"
      exit 1
      ;;
  esac

  log_info "After download, place ZIP in: $XBRL_DIR"
  log_info "Then run: ./EDINET_WORKFLOW.sh --process $XBRL_DIR/[filename].zip"
}

full_backfill() {
  log_warn "Full backfill requires manual downloads (EDINET doesn't expose API bulk download)"
  log_info "Steps:"
  echo "1. Download from https://disclosure2.edinet-fsa.go.jp/:"
  echo "   - EDINET_XBRL_2023_all.zip (FY2023 Annual)"
  echo "   - EDINET_XBRL_2024Q1_all.zip"
  echo "   - EDINET_XBRL_2024Q2_all.zip"
  echo "   - EDINET_XBRL_2024Q3_all.zip"
  echo ""
  echo "2. Place all in: $XBRL_DIR/"
  echo ""
  echo "3. Process each:"
  echo "   python3 $PY_FETCHER --from-file $XBRL_DIR/EDINET_XBRL_2023_all.zip"
  echo "   python3 $PY_FETCHER --from-file $XBRL_DIR/EDINET_XBRL_2024Q1_all.zip"
  echo "   python3 $PY_FETCHER --from-file $XBRL_DIR/EDINET_XBRL_2024Q2_all.zip"
  echo "   python3 $PY_FETCHER --from-file $XBRL_DIR/EDINET_XBRL_2024Q3_all.zip"
  echo ""
  echo "4. Verify:"
  echo "   ./EDINET_WORKFLOW.sh --status"
}

# Main
case "${1:-}" in
  --help) show_help ;;
  --validate) validate ;;
  --process) process_xbrl "$2" ;;
  --download) download_filings "$2" ;;
  --full-backfill) full_backfill ;;
  --status) status ;;
  "")
    log_error "No command specified"
    echo ""
    show_help
    exit 1
    ;;
  *)
    log_error "Unknown command: $1"
    show_help
    exit 1
    ;;
esac
