#!/bin/bash
# RUFLO Token Usage Dashboard
# Real-time view of token consumption across tasks

DB="${RUFLO_MONITOR_DB:-.ruflo/data/token_usage.db}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_subscription_reality() {
    SUB_PLAN="Claude Max 5x"
    SUB_USD=120
    echo -e "\n${BLUE}=== SUBSCRIPTION REALITY (what you ACTUALLY pay) ===${NC}\n"
    # API-equivalent value extracted (the 'cost' column is notional, NOT billed)
    VAL_30=$(sqlite3 "$DB" "SELECT COALESCE(ROUND(SUM(cost),0),0) FROM token_usage WHERE task_id LIKE 'claude_code%' AND timestamp >= datetime('now','-30 days');")
    VAL_30=${VAL_30:-0}
    LEVERAGE=$(python3 -c "print(f'{${VAL_30:-0}/${SUB_USD}:.0f}')" 2>/dev/null || echo "?")
    # quota draw: Opus-tier tokens weigh ~5x Sonnet in Max metering
    OPUS_TOK=$(sqlite3 "$DB" "SELECT COALESCE(SUM(total_tokens),0) FROM token_usage WHERE task_id LIKE 'claude_code%' AND (model LIKE '%opus%' OR model LIKE '%fable%') AND timestamp >= datetime('now','-30 days');")
    OTHER_TOK=$(sqlite3 "$DB" "SELECT COALESCE(SUM(total_tokens),0) FROM token_usage WHERE task_id LIKE 'claude_code%' AND model NOT LIKE '%opus%' AND model NOT LIKE '%fable%' AND timestamp >= datetime('now','-30 days');")
    echo -e "Plan:                    ${GREEN}${SUB_PLAN}  \$${SUB_USD}/mo (FLAT)${NC}"
    echo -e "API-equiv value (30d):   ${BLUE}\$${VAL_30}${NC}  (notional — what pay-per-token WOULD cost)"
    echo -e "Subscription leverage:   ${GREEN}~${LEVERAGE}x${NC}  (value extracted ÷ flat fee)"
    echo -e "Quota draw (30d):        Opus/Fable-tier ${YELLOW}${OPUS_TOK}${NC} tok  vs  Sonnet/Haiku ${GREEN}${OTHER_TOK}${NC} tok"
    echo -e "${YELLOW}Rerouting saves \$0 (flat fee) — it buys RATE-LIMIT HEADROOM: Opus draws the${NC}"
    echo -e "${YELLOW}Max allowance ~5x faster than Sonnet, so you hit usage caps far less often.${NC}"
}

show_today_summary() {
    echo -e "\n${BLUE}=== TODAY'S USAGE (cost = API-equivalent value, NOT billed) ===${NC}\n"
    sqlite3 "$DB" <<EOF
.mode column
.headers on
SELECT
  DATE(timestamp) as Date,
  COUNT(*) as Tasks,
  SUM(total_tokens) as Total_Tokens,
  SUM(cost) as Est_Cost_USD,
  MIN(timestamp) as First_Task,
  MAX(timestamp) as Last_Task
FROM token_usage
WHERE DATE(timestamp) = DATE('now')
GROUP BY DATE(timestamp);
EOF
}

show_by_task() {
    echo -e "\n${BLUE}=== TOKENS BY TASK (Last 7 Days) ===${NC}\n"
    sqlite3 "$DB" <<EOF
.mode column
.headers on
SELECT
  task_id,
  COUNT(*) as Runs,
  SUM(total_tokens) as Total_Tokens,
  AVG(total_tokens) as Avg_Per_Run,
  MAX(total_tokens) as Peak,
  ROUND(SUM(cost), 4) as Est_Cost_USD
FROM token_usage
WHERE timestamp >= datetime('now', '-7 days')
GROUP BY task_id
ORDER BY SUM(total_tokens) DESC;
EOF
}

show_hourly_trend() {
    echo -e "\n${BLUE}=== HOURLY TREND (Last 24 Hours) ===${NC}\n"
    sqlite3 "$DB" <<EOF
.mode column
.headers on
SELECT
  STRFTIME('%H:00', timestamp) as Hour,
  COUNT(*) as Tasks_Run,
  SUM(total_tokens) as Tokens,
  ROUND(AVG(total_tokens), 0) as Avg_Per_Task,
  ROUND(SUM(cost), 4) as Est_Cost_USD
FROM token_usage
WHERE timestamp >= datetime('now', '-1 day')
GROUP BY HOUR
ORDER BY Hour DESC;
EOF
}

show_budget_status() {
    echo -e "\n${BLUE}=== BUDGET STATUS ===${NC}\n"
    TODAY_TOKENS=$(sqlite3 "$DB" "SELECT COALESCE(SUM(total_tokens), 0) FROM token_usage WHERE DATE(timestamp) = DATE('now');")
    TODAY_TOKENS=${TODAY_TOKENS:-0}
    DAILY_LIMIT=200000
    REMAINING=$((DAILY_LIMIT - TODAY_TOKENS))
    PERCENT=$((TODAY_TOKENS * 100 / DAILY_LIMIT))
    # thousands-grouped display (portable; avoids bash ${var:,} which errors on macOS bash 3.2)
    FMT_LIMIT=$(printf "%'d" "$DAILY_LIMIT" 2>/dev/null || echo "$DAILY_LIMIT")
    FMT_TODAY=$(printf "%'d" "$TODAY_TOKENS" 2>/dev/null || echo "$TODAY_TOKENS")
    FMT_REMAIN=$(printf "%'d" "$REMAINING" 2>/dev/null || echo "$REMAINING")

    if [ $PERCENT -gt 85 ]; then
        STATUS_COLOR=$RED
    elif [ $PERCENT -gt 70 ]; then
        STATUS_COLOR=$YELLOW
    else
        STATUS_COLOR=$GREEN
    fi

    echo -e "Daily Budget Limit:      ${BLUE}${FMT_LIMIT}${NC} tokens"
    echo -e "Today's Usage:           ${STATUS_COLOR}${FMT_TODAY}${NC} tokens"
    echo -e "Remaining:               ${STATUS_COLOR}${FMT_REMAIN}${NC} tokens"
    echo -e "Usage %:                 ${STATUS_COLOR}${PERCENT}%${NC}"

    if [ $PERCENT -gt 85 ]; then
        echo -e "\n${RED}⚠️  WARNING: Approaching daily budget limit!${NC}"
    fi
}

show_model_distribution() {
    echo -e "\n${BLUE}=== MODEL DISTRIBUTION (Last 7 Days) ===${NC}\n"
    sqlite3 "$DB" <<EOF
.mode column
.headers on
SELECT
  COALESCE(model, 'unknown') as Model,
  COUNT(*) as Calls,
  SUM(input_tokens) as Input,
  SUM(output_tokens) as Output,
  SUM(total_tokens) as Total,
  ROUND(SUM(cost), 4) as Cost_USD
FROM token_usage
WHERE timestamp >= datetime('now', '-7 days')
GROUP BY model
ORDER BY SUM(total_tokens) DESC;
EOF
}

show_errors() {
    ERROR_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM token_usage WHERE error_msg IS NOT NULL AND timestamp >= datetime('now', '-1 day');")
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "\n${RED}=== ERRORS (Last 24 Hours) ===${NC}\n"
        sqlite3 "$DB" <<EOF
.mode column
.headers on
SELECT
  task_id,
  COUNT(*) as Errors,
  timestamp as Most_Recent
FROM token_usage
WHERE error_msg IS NOT NULL
  AND timestamp >= datetime('now', '-1 day')
GROUP BY task_id
ORDER BY timestamp DESC;
EOF
    fi
}

# Main dashboard
clear
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         RUFLO TOKEN USAGE MONITORING DASHBOARD             ║${NC}"
echo -e "${BLUE}║              Token Monitor v1.0 (Real-time)                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

if [ ! -f "$DB" ]; then
    echo -e "\n${RED}❌ Database not found at: $DB${NC}"
    echo "Initialize monitoring with: ./.ruflo/scripts/start-token-monitor.sh"
    exit 1
fi

show_subscription_reality
show_today_summary
show_by_task
show_model_distribution
show_errors

echo -e "\n${BLUE}Last updated: $(date '+%Y-%m-%d %H:%M:%S')${NC}\n"
