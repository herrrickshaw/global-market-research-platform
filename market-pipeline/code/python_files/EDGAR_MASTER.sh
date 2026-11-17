#!/bin/bash
# EDGAR Master Orchestration Script
# Runs complete EDGAR extraction pipeline with logging, Cassandra load, and Dropbox sync.

set -e

echo "╔════════════════════════════════════════════════════════════════════════════════╗"
echo "║                     EDGAR MASTER ORCHESTRATION SCRIPT                          ║"
echo "║         Extract SEC fundamentals for 2,200+ US symbols to Cassandra            ║"
echo "╚════════════════════════════════════════════════════════════════════════════════╝"
echo ""

REPO_DIR="/Users/umashankar/market-pipeline"
PYTHON_DIR="$REPO_DIR/code/python_files"
REPORTS_DIR="$PYTHON_DIR/reports"
LOGFILE="$REPORTS_DIR/edgar_master_$(date +%Y-%m-%d_%H%M%S).log"

mkdir -p "$REPORTS_DIR"

echo "📋 Configuration"
echo "  Repository: $REPO_DIR"
echo "  Python scripts: $PYTHON_DIR"
echo "  Reports/Logs: $REPORTS_DIR"
echo "  Master log: $LOGFILE"
echo ""

# Check dependencies
echo "🔍 Checking dependencies..."
DEPS_OK=1

if ! command -v python3 &> /dev/null; then
    echo "  ❌ python3 not found"
    DEPS_OK=0
fi

if ! python3 -c "import yfinance" 2>/dev/null; then
    echo "  ⚠️  yfinance not installed (required for extraction)"
    echo "    Run: pip install yfinance"
fi

if ! command -v cqlsh &> /dev/null; then
    echo "  ⚠️  cqlsh not found (required for Cassandra load)"
    echo "    Run: brew install cassandra"
fi

if ! command -v rclone &> /dev/null; then
    echo "  ⚠️  rclone not found (required for Dropbox sync)"
    echo "    Run: brew install rclone"
fi

echo "  ✓ Python3: $(python3 --version)"

# Menu
echo ""
echo "╔════════════════════════════════════════════════════════════════════════════════╗"
echo "║                            EXECUTION MODES                                     ║"
echo "╠════════════════════════════════════════════════════════════════════════════════╣"
echo "║ 1) FULL        Extract 2,200+ US symbols (4-6 hours)                          ║"
echo "║ 2) FAST        Extract 500 symbols for testing (30-45 min)                     ║"
echo "║ 3) AWS         Run on AWS EC2 with data logger + Dropbox sync                  ║"
echo "║ 4) LOAD        Load generated CQL to Cassandra                                 ║"
echo "║ 5) VERIFY      Check completeness gains after load                             ║"
echo "║ 6) ALL         Run 1→4→5 (full pipeline)                                       ║"
echo "╚════════════════════════════════════════════════════════════════════════════════╝"
echo ""

read -p "Select mode [1-6]: " MODE

case $MODE in
    1)
        echo ""
        echo "🚀 Mode 1: FULL EXTRACTION (2,200+ symbols)"
        echo "  Starting extraction at $(date)"
        echo ""
        python3 "$PYTHON_DIR/edgar_production_full.py" \
            --batch-size 100 \
            --workers 4 \
            --symbols-limit 2200 \
            2>&1 | tee -a "$LOGFILE"
        ;;
    
    2)
        echo ""
        echo "🚀 Mode 2: FAST TEST (500 symbols)"
        echo "  Starting extraction at $(date)"
        echo ""
        python3 "$PYTHON_DIR/edgar_production_full.py" \
            --batch-size 100 \
            --workers 4 \
            --symbols-limit 500 \
            2>&1 | tee -a "$LOGFILE"
        ;;
    
    3)
        echo ""
        echo "🚀 Mode 3: AWS RUNNER WITH LOGGING + DROPBOX SYNC"
        echo "  Starting at $(date)"
        echo ""
        python3 "$PYTHON_DIR/edgar_aws_runner.py" \
            --profile default \
            --region us-east-1 \
            --symbols-limit 100 \
            2>&1 | tee -a "$LOGFILE"
        ;;
    
    4)
        echo ""
        echo "🚀 Mode 4: LOAD TO CASSANDRA"
        echo "  Starting load at $(date)"
        echo ""
        bash "$PYTHON_DIR/edgar_cassandra_loader.sh" 2>&1 | tee -a "$LOGFILE"
        ;;
    
    5)
        echo ""
        echo "🚀 Mode 5: VERIFY COMPLETENESS"
        echo "  Running audit at $(date)"
        echo ""
        python3 "$PYTHON_DIR/data_completeness_audit.py" 2>&1 | tee -a "$LOGFILE"
        ;;
    
    6)
        echo ""
        echo "🚀 Mode 6: FULL PIPELINE (Extract → Load → Verify)"
        echo "  Starting complete pipeline at $(date)"
        echo ""
        
        # Step 1: Extract
        echo "════════════════════════════════════════════════════════════"
        echo "Step 1/3: EDGAR Extraction (2,200+ symbols)"
        echo "════════════════════════════════════════════════════════════"
        python3 "$PYTHON_DIR/edgar_production_full.py" \
            --batch-size 100 \
            --workers 4 \
            --symbols-limit 2200 \
            2>&1 | tee -a "$LOGFILE"
        
        echo ""
        echo "════════════════════════════════════════════════════════════"
        echo "Step 2/3: Load to Cassandra"
        echo "════════════════════════════════════════════════════════════"
        bash "$PYTHON_DIR/edgar_cassandra_loader.sh" 2>&1 | tee -a "$LOGFILE"
        
        echo ""
        echo "════════════════════════════════════════════════════════════"
        echo "Step 3/3: Verify Completeness"
        echo "════════════════════════════════════════════════════════════"
        python3 "$PYTHON_DIR/data_completeness_audit.py" 2>&1 | tee -a "$LOGFILE"
        
        echo ""
        echo "✅ FULL PIPELINE COMPLETE"
        ;;
    
    *)
        echo "❌ Invalid mode. Exiting."
        exit 1
        ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════════╗"
echo "║                          EXECUTION COMPLETE                                    ║"
echo "╚════════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Results"
echo "  Master log: $LOGFILE"
echo "  CQL batches: $REPORTS_DIR/edgar_cassandra_batch_*.cql"
echo "  JSON export: $REPORTS_DIR/edgar_production_results_*.json"
echo ""
echo "Next steps:"
echo "  1. Review logs: less $LOGFILE"
echo "  2. Monitor progress: tail -f $LOGFILE"
echo "  3. Check Cassandra: cqlsh -e \"SELECT COUNT(*) FROM herrrickshaw.stock_quotes WHERE market='us' AND pe IS NOT NULL ALLOW FILTERING;\""
echo ""

