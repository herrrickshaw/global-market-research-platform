#!/usr/bin/env node
/**
 * RUFLO Token Usage Logger Hook
 * Automatically logs token consumption from Claude Code operations
 *
 * Hooks into:
 * - Tool execution (input/output tokens)
 * - Agent spawning (initialization cost)
 * - API calls (requests/responses)
 * - Task completion (total usage)
 */

'use strict';

const fs = require('fs');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();

class TokenLogger {
  constructor() {
    this.dbPath = process.env.RUFLO_MONITOR_DB || '.ruflo/data/token_usage.db';
    this.alertLog = process.env.RUFLO_ALERT_LOG || '.ruflo/logs/token_alerts.log';
    this.db = null;
    this.dailyLimit = 200000;
    this.softLimit = 160000;
    this.init();
  }

  init() {
    this.ensureDirectories();
    this.db = new sqlite3.Database(this.dbPath, (err) => {
      if (err && err.code !== 'SQLITE_CANTOPEN') {
        this.log('ERROR', `Database connection failed: ${err.message}`);
      }
    });
  }

  ensureDirectories() {
    const dirs = [
      path.dirname(this.dbPath),
      path.dirname(this.alertLog)
    ];
    dirs.forEach(dir => {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    });
  }

  log(level, msg) {
    const timestamp = new Date().toISOString();
    const line = `[${timestamp}] [${level}] ${msg}`;
    console.error(line);
  }

  /**
   * Log token usage for a task
   */
  logTokenUsage(data) {
    if (!this.db) {
      this.log('WARN', 'Database not initialized, skipping token log');
      return;
    }

    const {
      taskId = 'unknown',
      taskName = '',
      model = 'claude',
      inputTokens = 0,
      outputTokens = 0,
      market = '',
      status = 'success',
      durationSeconds = 0,
      errorMsg = null
    } = data;

    const totalTokens = inputTokens + outputTokens;
    const cost = this.estimateCost(model, inputTokens, outputTokens);

    const sql = `
      INSERT INTO token_usage (
        task_id, task_name, model, input_tokens, output_tokens,
        total_tokens, cost, market, status, duration_seconds, error_msg
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `;

    this.db.run(sql, [
      taskId, taskName, model, inputTokens, outputTokens,
      totalTokens, cost, market, status, durationSeconds, errorMsg
    ], (err) => {
      if (err) {
        this.log('ERROR', `Failed to log usage: ${err.message}`);
        return;
      }

      this.checkBudgetStatus(totalTokens, taskId);
    });
  }

  /**
   * Estimate cost based on Claude pricing
   */
  estimateCost(model, inputTokens, outputTokens) {
    // Claude pricing (as of 2026)
    const prices = {
      'claude-3-5-haiku-20241022': { input: 0.00025, output: 0.00125 }, // Haiku 3.5 (newer, cheaper)
      'claude-3-haiku': { input: 0.00025, output: 0.00125 },
      'claude-3-5-sonnet': { input: 0.003, output: 0.015 },
      'claude-3-sonnet': { input: 0.003, output: 0.015 },
      'claude-3-5-opus': { input: 0.015, output: 0.075 },
      'claude-3-opus': { input: 0.015, output: 0.075 },
      'claude': { input: 0.00025, output: 0.00125 }, // default Haiku
    };

    const price = prices[model] || prices['claude'];
    return (inputTokens * price.input) + (outputTokens * price.output);
  }

  /**
   * Check if approaching budget limits
   */
  checkBudgetStatus(tokensJustUsed, taskId) {
    const checkSql = `
      SELECT COALESCE(SUM(total_tokens), 0) as used
      FROM token_usage
      WHERE DATE(timestamp) = DATE('now')
    `;

    this.db.get(checkSql, (err, row) => {
      if (err) {
        this.log('ERROR', `Budget check failed: ${err.message}`);
        return;
      }

      const used = row.used;
      const remaining = this.dailyLimit - used;
      const percentUsed = (used / this.dailyLimit) * 100;

      // Log alerts if approaching limits
      if (percentUsed >= 85) {
        this.writeAlert('CRITICAL', taskId, used, remaining, percentUsed);
      } else if (percentUsed >= 70) {
        this.writeAlert('WARNING', taskId, used, remaining, percentUsed);
      }

      // Soft limit check
      if (used >= this.softLimit && used - tokensJustUsed < this.softLimit) {
        this.writeAlert('SOFT_LIMIT', taskId, used, remaining, percentUsed);
      }
    });
  }

  /**
   * Write alert to log file and console
   */
  writeAlert(level, taskId, used, remaining, percentUsed) {
    const alert = {
      timestamp: new Date().toISOString(),
      level,
      task_id: taskId,
      tokens_used: used,
      tokens_remaining: remaining,
      percentage_used: Math.round(percentUsed),
      daily_limit: this.dailyLimit
    };

    const alertLine = JSON.stringify(alert);
    fs.appendFileSync(this.alertLog, alertLine + '\n');

    if (level === 'CRITICAL') {
      this.log('CRITICAL', `🔴 BUDGET CRITICAL: ${Math.round(percentUsed)}% used (${used}/${this.dailyLimit})`);
    } else if (level === 'WARNING') {
      this.log('WARN', `🟡 BUDGET WARNING: ${Math.round(percentUsed)}% used (${used}/${this.dailyLimit})`);
    } else if (level === 'SOFT_LIMIT') {
      this.log('INFO', `📊 Soft limit reached: ${used} tokens`);
    }

    // Optionally call n8n webhook
    this.notifyWebhook(alert);
  }

  /**
   * Send alert to n8n webhook
   */
  notifyWebhook(alert) {
    // This would be called if n8n webhook is configured
    // Left as placeholder for webhook POST implementation
    process.env.RUFLO_WEBHOOK_URL && this.log('DEBUG', `Webhook would send: ${JSON.stringify(alert)}`);
  }

  /**
   * Close database connection
   */
  close() {
    if (this.db) {
      this.db.close();
    }
  }
}

// Parse incoming token usage data from stdin
function main() {
  const logger = new TokenLogger();
  let inputData = '';

  process.stdin.on('data', (chunk) => {
    inputData += chunk;
  });

  process.stdin.on('end', () => {
    try {
      if (inputData.trim()) {
        const data = JSON.parse(inputData);
        logger.logTokenUsage(data);
      }
    } catch (err) {
      logger.log('ERROR', `Failed to parse input: ${err.message}`);
    } finally {
      // Keep alive briefly to ensure database write completes
      setTimeout(() => {
        logger.close();
        process.exit(0);
      }, 500);
    }
  });

  // Timeout after 5 seconds
  setTimeout(() => {
    logger.close();
    process.exit(0);
  }, 5000);
}

main();
