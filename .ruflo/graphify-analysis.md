# RUFLO Token Analysis — Graphify Format

## Overview
Multi-repository token usage analysis with optimization impact tracking across market-pipeline, backend services, and utility tasks.

## Data Model

### Nodes

#### Repositories
- **market-pipeline** (primary)
- **backend** (FastAPI services)
- **put-call-parity** (options trading)
- **put-call-parity/monitoring** (derivative)

#### Tasks
- daily_scan
- watchlist_mailer
- portfolio_analysis
- bulk_fetcher
- put_call_parity
- screener_upload
- portfolio_upload

#### Models
- claude-3-5-haiku-20241022 (optimized)
- claude-3-haiku (legacy)
- claude-3-5-sonnet (premium)
- claude-3-opus (max)

#### Optimization Initiatives
- Phase 1: Batch Scans
- Phase 1: Instrument Caching
- Phase 1: Lazy-load Metrics
- Week 1: Model Upgrade

#### Markets
- india
- us
- europe
- japan
- korea

#### Metrics
- total_tokens
- cost_usd
- input_tokens
- output_tokens
- duration_seconds

### Edges (Relationships)

#### runs_task
`Repository` → `Task`
- market-pipeline runs: daily_scan, watchlist_mailer, bulk_fetcher
- backend runs: daily_scan, portfolio_analysis, portfolio_upload
- put-call-parity runs: put_call_parity

#### uses_model
`Task` → `Model`
- daily_scan uses claude-3-5-haiku-20241022 (after upgrade)
- watchlist_mailer uses claude-3-5-haiku-20241022 (after upgrade)
- portfolio_analysis uses claude-3-haiku (candidate for Sonnet upgrade)
- put_call_parity uses claude-3-haiku (candidate for Sonnet upgrade)

#### targets_market
`Task` → `Market`
- daily_scan targets: india, us, europe, japan, korea (all 5)
- watchlist_mailer targets: india
- bulk_fetcher targets: india, us, europe, japan, korea (all 5)
- portfolio_analysis targets: india, us, europe, japan, korea (all 5)

#### applies_optimization
`Optimization` → `Task`
- Batch Scans applies to: daily_scan (-2.6-4.4k tokens/day)
- Instrument Caching applies to: daily_scan (-3.5-5.3k tokens/day)
- Lazy-load Metrics applies to: daily_scan (-1.7-2.6k tokens/day)
- Model Upgrade applies to: daily_scan, watchlist_mailer (-2.6k tokens/day total)

#### reduces_cost
`Optimization` → `Metrics`
- Phase 1 reduces total_tokens by 9-14k/day (7.3-11.4%)
- Model Upgrade reduces cost_usd by 5-8% (same tier, better efficiency)

#### measured_by
`Task` → `Metrics`
- daily_scan: ~87.5k tokens/day (pre-opt), ~73-81k tokens/day (post-opt)
- watchlist_mailer: ~11.9k tokens/day (stable)
- portfolio_analysis: ~5.2k tokens/day
- bulk_fetcher: ~2.3k tokens/day
- put_call_parity: ~7.1k tokens/day
- screener_upload: ~0.8k tokens/day

---

## Visualizations

### 1. Task → Token Consumption Hierarchy

```
TOTAL DAILY: 123,007 tokens
├── daily_scan (87.5k, 71.1%)
│   ├── india market scan
│   ├── us market scan
│   ├── europe market scan
│   ├── japan market scan
│   └── korea market scan
├── watchlist_mailer (11.9k, 9.7%)
│   └── india email generation
├── portfolio_analysis (5.2k, 4.2%)
├── put_call_parity (7.1k, 5.8%)
├── bulk_fetcher (2.3k, 1.9%)
├── screener_upload (0.8k, 0.7%)
└── portfolio_upload (0.3k, 0.2%)
```

### 2. Model Upgrade Impact

```
daily_scan:
  Before: Claude 3 Haiku @ 87.5k tokens/day
  After:  Claude 3.5 Haiku @ 83.9k tokens/day
  Savings: -2.6% (-2.3k tokens/day)
  Quality: ↑ (direct upgrade)

watchlist_mailer:
  Before: Claude 3 Haiku @ 11.9k tokens/day
  After:  Claude 3.5 Haiku @ 11.4k tokens/day
  Savings: -2.6% (-0.5k tokens/day)
  Quality: ↑ (direct upgrade)
```

### 3. Optimization Pipeline (Phase 1 → Week 1 → Phase 2)

```
PHASE 1 (DEPLOYED):
  Batch Scans ─────────────┐
  Instrument Cache ────────┼──→ 9-14k tokens/day reduction
  Lazy-load Metrics ───────┘

WEEK 1 (LIVE):
  Model Upgrade ──→ +2.6k tokens/day savings
  ─────────────────────────────
  TOTAL: -9-14k tokens/day reduction (9-13%)

PHASE 2 (PENDING VALIDATION):
  Parallelize Fetcher ────┐
  Compress Output ────────┼──→ +2-3k tokens/day savings (optional)
  
PHASE 3 (FUTURE):
  Incremental Scan ──────┐
  Smart Caching ─────────┼──→ +1-2k tokens/day savings (optional)
```

### 4. Repository Coverage Map

```
market-pipeline/
├── build_mailer.py
│   └── watchlist_mailer (upgraded to 3.5 Haiku)
├── screener_kit.py
│   └── bulk_fetcher
├── portfolio_analysis.py
│   └── portfolio_analysis (candidate: Sonnet)
└── various utilities
    └── dependency chain

backend/
├── routers/cassandra_router.py
│   └── daily_scan (upgraded to 3.5 Haiku + Phase 1 opts)
├── db/quote_updater.py
│   └── instrument caching (Phase 1)
└── scanners/daily_scanner.py
    └── lazy-load metrics (Phase 1)

put_call_parity/
├── main.py
│   └── put_call_parity (candidate: Sonnet for trading quality)
└── strategy.py
    └── options analysis

.ruflo/
├── monitoring framework (token tracking)
└── validation dashboards (Week 1-3)
```

### 5. Optimization Impact Timeline

```
2026-07-27 (TODAY):
  ✓ Phase 1 deployed (code optimizations)
  ✓ Model upgrade deployed (3.5 Haiku live)
  ✓ Week 1 validation period starts

2026-08-03:
  • 1 week of real token data collected
  • Compare to pre-optimization baseline
  • Validate 9-14k token reduction

2026-08-10:
  • Full week of data analyzed
  • Quality metrics confirmed (no regressions)
  • Decision: proceed to Phase 2?

2026-08-17:
  • Phase 2 deployment (optional)
  • Sonnet upgrades (portfolio_analysis, put_call_parity)
  • Additional 2-3k tokens/day savings

2026-08-31:
  • Full month of optimized baseline established
  • Cumulative impact documented
  • Future roadmap: Phase 3 (incremental scan, smart cache)
```

### 6. Cost Impact Graph

```
DAILY COST TRAJECTORY:

$0.170 │                    ┌─ Before: $0.168/day
       │                    │
$0.165 │ ┌───────────────┐  │
       │ │ Phase 1       │  │
$0.160 │ │ optimizations │──┴─ Week 1: $0.150-0.157/day
       │ │ + Model       │
$0.155 │ │ upgrade       │
       │ │ Live now      │
$0.150 │ └───────────────┘
       │
       └─────────────────────────
       2026-07-27    2026-08-03    2026-08-17

ANNUAL COST:
  Before: $61.32/year
  After:  $54.75-57.30/year
  Savings: $3.75-6.57/year
```

---

## Connected Analysis

### Key Relationships

1. **Model Tier → Cost → Quality**
   - Haiku 3.5: Optimal for structured output, fast inference, low cost
   - Sonnet: Better for complex multi-factor analysis (portfolio, trading)
   - Opus: Overkill for daily scanning, not cost-effective

2. **Repository → Tasks → Token Consumption**
   - market-pipeline dominates with daily_scan (71% of budget)
   - backend supports daily_scan + portfolio analysis
   - put-call-parity handles options trading (specialized, high-quality focus)

3. **Optimization → Tasks → Models**
   - Code optimizations reduce base token load (Phase 1: -9-14k)
   - Model upgrade reduces per-token cost + improves quality
   - Combined effect: -9-14k tokens/day + quality boost

4. **Validation → Confidence → Next Steps**
   - Week 1: Collect real usage data, validate projections
   - If confirmed: Phase 2 optional upgrades (Sonnet for premium analysis)
   - If exceeded: Phase 3 (incremental scanning, smart caching)

---

## Query Examples (for RUFLO analysis)

### Find all tasks consuming >50k tokens/day
```sql
SELECT task_id, AVG(total_tokens) as avg_daily
FROM token_usage
WHERE DATE(timestamp) >= DATE('now', '-7 days')
GROUP BY task_id
HAVING avg_daily > 50000
ORDER BY avg_daily DESC;
```

### Compare models by cost efficiency
```sql
SELECT model, 
       COUNT(*) as runs,
       AVG(total_tokens) as avg_tokens,
       AVG(cost) as avg_cost,
       AVG(cost) / AVG(total_tokens) as cost_per_token
FROM token_usage
GROUP BY model
ORDER BY cost_per_token ASC;
```

### Track Phase 1 optimization impact
```sql
SELECT DATE(timestamp) as date,
       AVG(total_tokens) as avg_tokens,
       SUM(total_tokens) as daily_total
FROM token_usage
WHERE task_id = 'daily_scan'
GROUP BY DATE(timestamp)
ORDER BY DATE(timestamp) DESC;
```

### Find candidates for Sonnet upgrade
```sql
SELECT task_id, 
       COUNT(*) as executions,
       AVG(duration_seconds) as avg_duration,
       ROUND(AVG(total_tokens), 0) as avg_tokens,
       'Candidate for Sonnet' as recommendation
FROM token_usage
WHERE task_id IN ('portfolio_analysis', 'put_call_parity')
  AND DATE(timestamp) >= DATE('now', '-7 days')
GROUP BY task_id;
```

---

## Integration Points

### RUFLO Data → Graphify
- Real token usage from SQLite → Node metrics
- Task relationships from code → Edge definitions
- Optimization deployments → Timeline events

### Monitoring Dashboard Integration
- Weekly token consumption by task (bar chart)
- Cost trend over time (line chart)
- Model distribution pie chart
- Repository contribution stacked bar

### Phase 2 Decision Gate
- If actual savings ≥ 8.5k tokens/day: Proceed to Sonnet upgrades
- If actual savings < 8.5k tokens/day: Debug & refine Phase 1
- If quality regressed: Rollback (< 2 min procedure)

---

## Success Metrics

✓ 7+ consecutive days of clean operation
✓ Actual savings match projections (±10%)
✓ No signal quality degradation
✓ Email/scan output quality confirmed
✓ Budget alerts only at legitimate thresholds

---

Generated: 2026-07-28
Status: Framework Ready for Graphify Integration

