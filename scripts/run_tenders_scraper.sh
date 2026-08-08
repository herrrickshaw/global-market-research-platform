#!/bin/bash
# Tender Scraper Daily Runner
# Runs tenders_scraper_v2.py and logs output to ~/logs/tenders_scraper.log

set -e

LOG_DIR="$HOME/logs"
LOG_FILE="$LOG_DIR/tenders_scraper.log"
VENV_PATH="$HOME/.venvs/tenders"
SCRAPER_PATH="$HOME/tenders_scraper_v2.py"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Activate venv and run scraper
{
    echo "════════════════════════════════════════════════════════════════"
    echo "Tender Scraper Run - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "════════════════════════════════════════════════════════════════"

    # Check if venv exists, create if needed
    if [ ! -d "$VENV_PATH" ]; then
        echo "Creating virtual environment at $VENV_PATH..."
        python3 -m venv "$VENV_PATH"
        "$VENV_PATH/bin/pip" install -q -r "$HOME/tenders_requirements.txt"
    fi

    # Run scraper
    "$VENV_PATH/bin/python3" "$SCRAPER_PATH"

    echo ""
    echo "✓ Scraper completed at $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Database: $HOME/tenders_data.duckdb"

} >> "$LOG_FILE" 2>&1

# Exit status
if [ $? -eq 0 ]; then
    echo "✓ Tender scraper succeeded" >&2
    exit 0
else
    echo "✗ Tender scraper failed - check $LOG_FILE" >&2
    exit 1
fi
