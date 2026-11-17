#!/bin/bash
#
# Extract stock data locally (memory-optimized, Colibri + streaming)
# Replaces AWS/Colab extraction with local duckdb streaming
#
# Usage:
#   ./extract.sh india              # Extract NSE only
#   ./extract.sh us                 # Extract US/NASDAQ only
#   ./extract.sh all                # All markets (sequential, safe for 8GB laptop)
#   ./extract.sh india us europe    # Multiple markets
#   ./extract.sh india --batch-size 30  # Override batch size
#

set -eu

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="${SCRIPT_DIR}/.venv"
PYTHON="${VENV_DIR}/bin/python3"

# Create venv if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "[*] Creating Python venv..."
    python3 -m venv "$VENV_DIR"
    "$PYTHON" -m pip install -q pip setuptools wheel
fi

# Install dependencies
echo "[*] Installing dependencies..."
"$PYTHON" -m pip install -q pandas duckdb requests yfinance 2>/dev/null || true

# Parse arguments
MARKETS=()
EXTRA_ARGS=()

for arg in "$@"; do
    if [[ "$arg" =~ ^(india|us|europe|japan|korea|all)$ ]]; then
        MARKETS+=("$arg")
    else
        EXTRA_ARGS+=("$arg")
    fi
done

# Default to india if no market specified
if [ ${#MARKETS[@]} -eq 0 ]; then
    MARKETS=("india")
fi

# Print config
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Optimized Stock Data Extraction (Colibri + Streaming)    ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Markets to extract: ${MARKETS[*]}"
echo "Extra args: ${EXTRA_ARGS[*]:-none}"
echo "Output: data/market_data.duckdb"
echo "Resume: enabled (use --no-resume to start fresh)"
echo ""

# Run extraction for each market
TOTAL_START=$(date +%s)

for market in "${MARKETS[@]}"; do
    if [ "$market" == "all" ]; then
        # All markets sequentially (safe)
        for m in india us europe japan korea; do
            echo ""
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            echo "Extracting $m..."
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            "$PYTHON" "${SCRIPT_DIR}/code/python_files/extract_optimized.py" \
                --market "$m" "${EXTRA_ARGS[@]}"
        done
    else
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Extracting $market..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        "$PYTHON" "${SCRIPT_DIR}/code/python_files/extract_optimized.py" \
            --market "$market" "${EXTRA_ARGS[@]}"
    fi
done

TOTAL_END=$(date +%s)
TOTAL_TIME=$((TOTAL_END - TOTAL_START))

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✓ Extraction Complete                                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Total time: ${TOTAL_TIME}s"
echo "Output database: ${SCRIPT_DIR}/data/market_data.duckdb"
echo ""
echo "Next steps:"
echo "  1. Verify data: duckdb data/market_data.duckdb"
echo "     > SELECT market, COUNT(*) FROM price_history_streaming GROUP BY market;"
echo ""
echo "  2. Backup: cp data/market_data.duckdb data/market_data.backup.duckdb"
echo ""
echo "  3. Load into other tools:"
echo "     - Cassandra: python scripts/duckdb_to_cassandra.py"
echo "     - Pandas: pd.read_csv('duckdb:data/market_data.duckdb|price_history_streaming')"
echo "     - Parquet: duckdb < convert_to_parquet.sql"
echo ""
