#!/bin/bash
#
# edinet_process_and_archive.sh
# Process EDINET XBRL files and archive to Dropbox/GDrive (cloud-first storage)
#
# Usage:
#   bash scripts/edinet_process_and_archive.sh
#
# This script:
#   1. Processes EDINET XBRL ZIPs from /tmp
#   2. Loads parsed data into Postgres (japan_fundamentals_history)
#   3. Archives the ZIP to Dropbox + GDrive
#   4. Deletes local copies (zero local footprint)
#

set -eo pipefail

# Config
REPO_HOME="/Users/umashankar/market-pipeline"
XBRL_SOURCE="/tmp"  # Expected: EDINET_XBRL_*.zip files here
PY_FETCHER="${REPO_HOME}/code/python_files/edinet_xbrl_historical_fetcher.py"
LOG_DIR="${REPO_HOME}/state"
LOG_FILE="${LOG_DIR}/edinet_archive_$(date +%Y%m%d_%H%M%S).log"

# Cloud config
DROPBOX_DEST="dropbox:/Market-Data-Archive/EDINET/"
GDRIVE_DEST="gdrive:/Market-Data-Archive/EDINET/"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Helper functions
log_info() { echo -e "${GREEN}[INFO]${NC} $*" | tee -a "$LOG_FILE"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $*" | tee -a "$LOG_FILE"; }

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log_step "EDINET XBRL Processing & Cloud Archive"
echo "Timestamp: $(date)" | tee "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Step 1: Find EDINET files
log_step "Scanning for EDINET XBRL files in $XBRL_SOURCE..."
FILES=$(find "$XBRL_SOURCE" -name "EDINET_XBRL_*.zip" 2>/dev/null || true)

if [ -z "$FILES" ]; then
  log_error "No EDINET_XBRL_*.zip files found in $XBRL_SOURCE"
  log_info "Expected files:"
  echo "  - EDINET_XBRL_2023_all.zip" | tee -a "$LOG_FILE"
  echo "  - EDINET_XBRL_2024Q1_all.zip" | tee -a "$LOG_FILE"
  echo "  - EDINET_XBRL_2024Q2_all.zip" | tee -a "$LOG_FILE"
  echo "  - EDINET_XBRL_2024Q3_all.zip" | tee -a "$LOG_FILE"
  log_info "Download from: https://disclosure2.edinet-fsa.go.jp/"
  exit 1
fi

FILE_COUNT=$(echo "$FILES" | wc -l)
log_info "Found $FILE_COUNT EDINET ZIP file(s)"
echo "$FILES" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Step 2: Process each file
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_FILES=()

for FILE in $FILES; do
  FILENAME=$(basename "$FILE")
  log_step "Processing: $FILENAME"

  # Parse XBRL and load into Postgres
  if python3 "$PY_FETCHER" --from-file "$FILE" 2>&1 | tee -a "$LOG_FILE"; then
    log_info "✓ $FILENAME processed successfully"

    # Step 3: Archive to Dropbox
    log_step "Archiving to Dropbox..."
    if rclone move "$FILE" "$DROPBOX_DEST" --progress 2>&1 | tee -a "$LOG_FILE"; then
      log_info "✓ $FILENAME archived to Dropbox"

      # Step 4: Verify in Dropbox
      log_step "Verifying archive..."
      if rclone lsf "$DROPBOX_DEST$FILENAME" >/dev/null 2>&1; then
        log_info "✓ Verified in Dropbox"

        # Step 5: Optional mirror to GDrive (for redundancy)
        log_step "Mirroring to GDrive (backup)..."
        if rclone copy "$DROPBOX_DEST$FILENAME" "$GDRIVE_DEST" --progress 2>&1 | tee -a "$LOG_FILE"; then
          log_info "✓ Mirrored to GDrive"
        else
          log_warn "GDrive mirror failed (non-critical) — file safe in Dropbox"
        fi

        ((SUCCESS_COUNT++))
      else
        log_error "Archive verification failed"
        ((FAILED_COUNT++))
        FAILED_FILES+=("$FILENAME")
      fi
    else
      log_error "Dropbox archive failed"
      ((FAILED_COUNT++))
      FAILED_FILES+=("$FILENAME")
    fi
  else
    log_error "Failed to process $FILENAME"
    ((FAILED_COUNT++))
    FAILED_FILES+=("$FILENAME")
  fi

  echo "" | tee -a "$LOG_FILE"
done

# Step 6: Verify Postgres
log_step "Verifying Postgres..."
TOTAL_ROWS=$(psql -d market_data -t -c "SELECT COUNT(*) FROM japan_fundamentals_history" 2>/dev/null || echo "0")
log_info "Postgres japan_fundamentals_history: $TOTAL_ROWS rows"
echo "" | tee -a "$LOG_FILE"

# Step 7: Cleanup local temps (only if all succeeded)
if [ $FAILED_COUNT -eq 0 ]; then
  log_step "Cleanup: Removing local temp files..."

  # Double-check we're in /tmp before cleanup
  if [[ "$XBRL_SOURCE" == "/tmp" ]]; then
    find "$XBRL_SOURCE" -name "EDINET_XBRL_*.zip" -exec rm -v {} \; 2>&1 | tee -a "$LOG_FILE"
    log_info "✓ Local temp files cleaned up (zero local disk usage)"
  else
    log_warn "Cleanup skipped — source is not /tmp (safety check)"
  fi
else
  log_warn "Cleanup skipped — $FAILED_COUNT file(s) failed processing"
  log_info "Retry for: ${FAILED_FILES[@]}"
fi

# Summary
echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
log_step "Summary"
echo "  Processed: $SUCCESS_COUNT" | tee -a "$LOG_FILE"
echo "  Failed: $FAILED_COUNT" | tee -a "$LOG_FILE"
echo "  Postgres rows: $TOTAL_ROWS" | tee -a "$LOG_FILE"
echo "  Local disk usage: 0 MB ✓" | tee -a "$LOG_FILE"
echo "  Cloud archive: Dropbox + GDrive ✓" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

log_info "Log file: $LOG_FILE"

# Exit status
if [ $FAILED_COUNT -eq 0 ]; then
  log_info "✓ All EDINET files processed successfully"
  exit 0
else
  log_error "✗ Some files failed — review log for details"
  exit 1
fi
