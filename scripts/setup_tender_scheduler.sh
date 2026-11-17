#!/bin/bash
# Setup script for Tender Scraper Daily Scheduler
# Installs launchd configuration and creates necessary directories

set -e

HOME_DIR="$HOME"
SCRIPTS_DIR="$HOME_DIR/scripts"
LAUNCHD_DIR="$HOME_DIR/Library/LaunchAgents"
LOGS_DIR="$HOME_DIR/logs"
PLIST_SRC="$SCRIPTS_DIR/launchd_templates/com.market.tenders.scraper.plist.template"
PLIST_DEST="$LAUNCHD_DIR/com.market.tenders.scraper.plist"

echo "════════════════════════════════════════════════════════════════"
echo "Tender Scraper Scheduler Setup"
echo "════════════════════════════════════════════════════════════════"

# Check if on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This setup script is for macOS only"
    echo "   For Linux, use cron instead: crontab -e"
    echo "   Add: 0 6 * * * $SCRIPTS_DIR/run_tenders_scraper.sh"
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p "$LOGS_DIR"
mkdir -p "$LAUNCHD_DIR"
echo "   ✓ $LOGS_DIR"
echo "   ✓ $LAUNCHD_DIR"

# Check if template exists
if [ ! -f "$PLIST_SRC" ]; then
    echo "❌ Template not found: $PLIST_SRC"
    exit 1
fi

# Copy template to LaunchAgents
echo ""
echo "📋 Installing LaunchD configuration..."
cp "$PLIST_SRC" "$PLIST_DEST"
echo "   ✓ Copied to $PLIST_DEST"

# Make script executable
echo ""
echo "🔧 Setting permissions..."
chmod +x "$SCRIPTS_DIR/run_tenders_scraper.sh"
echo "   ✓ Made run_tenders_scraper.sh executable"

# Load the LaunchD job
echo ""
echo "⚙️  Loading LaunchD job..."

# Unload if already loaded
if launchctl list | grep -q "com.market.tenders.scraper"; then
    echo "   ⚠️  Job already loaded, reloading..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Load the job
launchctl load "$PLIST_DEST"
echo "   ✓ LaunchD job loaded"

# Verify
echo ""
echo "✅ Verification:"
if launchctl list | grep -q "com.market.tenders.scraper"; then
    JOB_INFO=$(launchctl list | grep "com.market.tenders.scraper")
    echo "   ✓ Job is loaded and active"
    echo "   $JOB_INFO"
else
    echo "   ❌ Job failed to load"
    exit 1
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "Setup Complete! ✅"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "📅 Schedule: Daily at 6:00 AM"
echo "📝 Logs: $LOGS_DIR/tenders_scraper.log"
echo "💾 Database: $HOME_DIR/tenders_data.duckdb"
echo ""
echo "Useful Commands:"
echo "  View logs:    tail -f $LOGS_DIR/tenders_scraper.log"
echo "  Run now:      $SCRIPTS_DIR/run_tenders_scraper.sh"
echo "  Check status: launchctl list | grep tenders"
echo "  Disable:      launchctl unload $PLIST_DEST"
echo "  Docs:         open $HOME_DIR/TENDERS_SCHEDULER_SETUP.md"
echo ""
