#!/bin/bash
# RUFLO Token Monitoring Bootstrap
# Tracks token usage across n8n workflows and market-pipeline tasks

set -e

RUFLO_HOME="${RUFLO_HOME:-.ruflo}"
CONFIG_FILE="$RUFLO_HOME/config/token-monitor.json"
LOG_DIR="$RUFLO_HOME/logs"
DATA_DIR="$RUFLO_HOME/data"

# Create directories
mkdir -p "$LOG_DIR" "$DATA_DIR" "$RUFLO_HOME/config"

echo "[RUFLO] Token Monitoring Initialization ($(date '+%Y-%m-%d %H:%M:%S'))"
echo "========================================================================="

# Initialize SQLite database
if [ ! -f "$DATA_DIR/token_usage.db" ]; then
    echo "[RUFLO] Creating token usage database..."
    sqlite3 "$DATA_DIR/token_usage.db" <<EOF
CREATE TABLE IF NOT EXISTS token_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  task_id TEXT NOT NULL,
  task_name TEXT,
  model TEXT,
  input_tokens INTEGER,
  output_tokens INTEGER,
  total_tokens INTEGER,
  cost REAL,
  market TEXT,
  status TEXT,
  duration_seconds REAL,
  error_msg TEXT
);

CREATE TABLE IF NOT EXISTS task_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  task_id TEXT NOT NULL,
  metric_name TEXT,
  metric_value REAL,
  unit TEXT
);

CREATE TABLE IF NOT EXISTS daily_budgets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date DATE UNIQUE,
  limit_tokens INTEGER,
  used_tokens INTEGER,
  remaining_tokens INTEGER,
  warning_triggered BOOLEAN
);

CREATE TABLE IF NOT EXISTS hourly_usage (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  hour_start DATETIME,
  hour_end DATETIME,
  task_id TEXT,
  tokens_used INTEGER,
  cost REAL
);

CREATE INDEX idx_timestamp ON token_usage(timestamp);
CREATE INDEX idx_task_id ON token_usage(task_id);
CREATE INDEX idx_date ON daily_budgets(date);
EOF
    echo "[RUFLO] ✓ Database initialized"
fi

# Start RUFLO with cost-tracker plugin
echo "[RUFLO] Starting token monitoring daemon..."
echo "[RUFLO] Config: $CONFIG_FILE"
echo "[RUFLO] Database: $DATA_DIR/token_usage.db"
echo "[RUFLO] Logs: $LOG_DIR/token_alerts.log"
echo ""

# Export monitoring config
export RUFLO_MONITOR_CONFIG="$CONFIG_FILE"
export RUFLO_MONITOR_DB="$DATA_DIR/token_usage.db"
export RUFLO_ALERT_LOG="$LOG_DIR/token_alerts.log"

# Run RUFLO cost-tracker
echo "[RUFLO] Activating cost-tracker plugin..."

# Check if ruflo is available
if command -v ruflo &> /dev/null; then
    ruflo plugins enable cost-tracker
    ruflo plugins configure cost-tracker --config "$CONFIG_FILE" 2>&1 | tee -a "$LOG_DIR/ruflo-init.log"
    echo "[RUFLO] ✓ Cost-tracker plugin enabled"
elif command -v claude-flow &> /dev/null; then
    claude-flow plugins enable cost-tracker
    claude-flow plugins configure cost-tracker --config "$CONFIG_FILE" 2>&1 | tee -a "$LOG_DIR/ruflo-init.log"
    echo "[RUFLO] ✓ Cost-tracker plugin enabled via claude-flow"
else
    echo "[RUFLO] Installing RUFLO from npm..."
    npx --prefer-offline --yes ruflo@latest plugins enable cost-tracker 2>&1 | tee -a "$LOG_DIR/ruflo-init.log"
fi

# Verify database
RECORD_COUNT=$(sqlite3 "$DATA_DIR/token_usage.db" "SELECT COUNT(*) FROM token_usage;")
echo "[RUFLO] ✓ Monitoring database ready (records: $RECORD_COUNT)"

# Create n8n webhook integration file
echo "[RUFLO] Setting up n8n webhook integration..."
mkdir -p "$RUFLO_HOME/integrations"

cat > "$RUFLO_HOME/integrations/n8n-token-webhook.json" <<'EOF'
{
  "webhook_path": "/webhook/token-alerts",
  "methods": ["POST"],
  "auth": "none",
  "description": "Receive token usage alerts from RUFLO and log to n8n",
  "mapping": {
    "task_id": "$.task_id",
    "tokens_used": "$.tokens_used",
    "budget_remaining": "$.budget_remaining",
    "warning_level": "$.warning_level",
    "timestamp": "$.timestamp"
  }
}
EOF

echo "[RUFLO] ✓ n8n webhook integration file created"

# Display monitoring status
echo ""
echo "========================================================================="
echo "[RUFLO] ✓ Token Monitoring Initialized Successfully"
echo ""
echo "Next steps:"
echo "1. Monitor token usage: ruflo monitor --dashboard"
echo "2. View alerts: tail -f $LOG_DIR/token_alerts.log"
echo "3. Query database: sqlite3 $DATA_DIR/token_usage.db"
echo "4. Setup n8n webhook at: http://localhost:5678/webhook/token-alerts"
echo "========================================================================="
echo ""
