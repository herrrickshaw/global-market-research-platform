#!/bin/bash
# EDGAR Cassandra Bulk Loader
# Execute generated CQL batches and verify load

set -e

BATCH_DIR="/Users/umashankar/market-pipeline/code/python_files/reports"
LOG_FILE="/Users/umashankar/market-pipeline/code/python_files/reports/edgar_load_log_$(date +%Y-%m-%d_%H%M%S).txt"

echo "=========================================="
echo "EDGAR Fundamentals → Cassandra Loader"
echo "=========================================="
echo "Log: $LOG_FILE"
echo ""

# Step 1: Find all CQL batch files
echo "[1/4] Finding CQL batch files..."
BATCH_COUNT=$(find "$BATCH_DIR" -name "edgar_cassandra_batch_*.cql" | wc -l)
echo "  Found $BATCH_COUNT batch files"

if [ $BATCH_COUNT -eq 0 ]; then
    echo "❌ No CQL batch files found in $BATCH_DIR"
    echo "   Run edgar_production_run.py first to generate batches"
    exit 1
fi

# Step 2: Check Cassandra connectivity
echo "[2/4] Checking Cassandra connection..."
if ! command -v cqlsh &> /dev/null; then
    echo "⚠️  cqlsh not found. Install Cassandra client tools:"
    echo "   brew install cassandra"
    echo "   OR use docker: docker exec cassandra cqlsh <command>"
    exit 1
fi

# Try connection (non-fatal)
if cqlsh localhost -e "SELECT cluster_name FROM system.local;" &> /dev/null; then
    echo "  ✓ Cassandra connected (localhost:9042)"
    CASSANDRA_UP=1
else
    echo "  ⚠️  Cassandra connection failed (localhost:9042)"
    echo "    Start: docker-compose up -d cassandra"
    echo "    OR: cassandra -f (foreground)"
    CASSANDRA_UP=0
fi

# Step 3: Execute batches (if Cassandra is up)
if [ $CASSANDRA_UP -eq 1 ]; then
    echo "[3/4] Executing CQL batches..."
    
    BATCH_NUM=0
    TOTAL_RECORDS=0
    
    for batch_file in $(find "$BATCH_DIR" -name "edgar_cassandra_batch_*.cql" | sort); do
        BATCH_NUM=$((BATCH_NUM + 1))
        RECORD_COUNT=$(grep -c "UPDATE herrrickshaw" "$batch_file" || true)
        TOTAL_RECORDS=$((TOTAL_RECORDS + RECORD_COUNT))
        
        echo "  Batch $BATCH_NUM: $batch_file ($RECORD_COUNT records)"
        
        if cqlsh localhost -f "$batch_file" >> "$LOG_FILE" 2>&1; then
            echo "    ✓ Batch $BATCH_NUM loaded ($RECORD_COUNT records)"
        else
            echo "    ❌ Batch $BATCH_NUM failed (see $LOG_FILE)"
        fi
    done
    
    echo "  Total records: $TOTAL_RECORDS"
else
    echo "[3/4] Cassandra not available - skipping execution"
    echo "  Files ready at: $(find "$BATCH_DIR" -name "edgar_cassandra_batch_*.cql")"
    echo "  When Cassandra is ready, run:"
    echo "    for f in $BATCH_DIR/edgar_cassandra_batch_*.cql; do cqlsh -f \"\$f\"; done"
fi

# Step 4: Verify load
echo "[4/4] Verification..."

if [ $CASSANDRA_UP -eq 1 ]; then
    US_QUOTES=$(cqlsh localhost -e "SELECT COUNT(*) FROM herrrickshaw.stock_quotes WHERE market='us' AND pe IS NOT NULL ALLOW FILTERING;" 2>/dev/null | tail -1 | awk '{print $1}' || echo "unknown")
    echo "  US symbols with PE ratio: $US_QUOTES (after load)"
    echo "  Expected gain: +$TOTAL_RECORDS symbols"
else
    echo "  Verification skipped (Cassandra not available)"
fi

echo ""
echo "=========================================="
echo "✅ Load complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Check log: less $LOG_FILE"
echo "2. Query result: cqlsh -e \"SELECT COUNT(*) FROM herrrickshaw.stock_quotes WHERE market='us' AND pe IS NOT NULL ALLOW FILTERING;\""
echo "3. Run data audit: python3 data_completeness_audit.py"
echo ""

