# Global Fundamentals Collection Strategy

**Goal:** Collect PE/PB/ROE for ALL 25,335 symbols (100% coverage)  
**Timeline:** 6-8 hours parallel on AWS EC2  
**Target:** Transform from 22% (US only) → 100% real fundamentals across all markets

---

## Current State (Before Collection)

| Market | Symbols | Coverage | Type |
|--------|---------|----------|------|
| US | 9,278 | 22% (1,995) | Real Piotroski |
| India | 3,480 | 100% (3,480) | Real ROE |
| Europe | 1,709 | 0% | Liquidity proxy |
| Japan | 3,083 | 0% | Liquidity proxy |
| Korea | 2,597 | 0% | Liquidity proxy |
| China | 5,188 | 0% | Liquidity proxy |
| **TOTAL** | **25,335** | **22%** | Mixed |

---

## Collection Strategy by Market

### Phase 1: US Fundamentals (7,283 missing)
**Source:** AlphaVantage + EODHD  
**Metrics:** PE, PB, ROE, EPS, Market Cap  
**Rate Limit:** 5 calls/min (AlphaVantage), 2 calls/sec (EODHD)  
**Parallelization:** 3 workers (batch mode)  
**Estimated Time:** 4-6 hours  

```python
# Strategy:
1. Collect 7,283 missing US symbols via AlphaVantage
2. Fallback to EODHD for symbols AV can't fetch
3. Generate CQL UPDATE statements
4. Bulk load to Cassandra
```

### Phase 2: India Fundamentals (Complete)
**Current:** 3,480/3,480 (100%)  
**Action:** Collect historical PE/PB from screener.in (optional enhancement)  
**Estimated Time:** 0.5 hour  

### Phase 3: Europe Fundamentals (1,709)
**Source:** EODHD (comprehensive 17-exchange coverage)  
**Metrics:** PE, PB, ROE, Dividend Yield  
**Rate Limit:** 2 calls/sec  
**Parallelization:** 4 workers  
**Estimated Time:** 2 hours  

```
Exchanges:
  • London Stock Exchange (436 symbols)
  • Deutsche Boerse Frankfurt (142 symbols)
  • Euronext (208 symbols)
  • Nasdaq Nordic (80 symbols)
  • BME Madrid (35 symbols)
  • SIX Swiss (20 symbols)
  • Vienna ATX (20 symbols)
  • Others (768 symbols)
```

### Phase 4: Japan Fundamentals (3,083)
**Source:** EODHD + J-Quants (optional corporate filings)  
**Metrics:** PE, PB, ROE, EPS  
**Rate Limit:** 2 calls/sec  
**Parallelization:** 4 workers  
**Estimated Time:** 3 hours  

### Phase 5: Korea Fundamentals (2,597)
**Source:** EODHD + DART (Korean exchange data)  
**Metrics:** PE, PB, ROE, Market Cap  
**Rate Limit:** 2 calls/sec  
**Parallelization:** 4 workers  
**Estimated Time:** 2 hours  

### Phase 6: China Fundamentals (5,188)
**Source:** EODHD + Eastmoney (fallback)  
**Metrics:** PE, PB, ROE  
**Rate Limit:** 2 calls/sec  
**Parallelization:** 4 workers  
**Estimated Time:** 3 hours  

---

## Deployment Architecture

### Local Execution (Immediate)
```bash
# 1. Deploy collector
python3 /tmp/fundamentals_collector_production.py

# 2. Output: FUNDAMENTALS_API_COLLECTED_*.cql
#    └── One file per market with UPDATE statements

# 3. Load to Cassandra
for file in market-pipeline/code/python_files/reports/FUNDAMENTALS_API_COLLECTED_*.cql
do
  cqlsh localhost -f "$file"
done

# 4. Verify
cqlsh -e "SELECT COUNT(*) FROM herrrickshaw.stock_quotes WHERE pe > 0 ALLOW FILTERING;"
```

### AWS EC2 Deployment (Parallel, 6-8h)
```bash
# 1. Copy to EC2
scp -r market-pipeline ec2-user@13.218.137.191:/tmp/

# 2. SSH to EC2
ssh ec2-user@13.218.137.191

# 3. Run on EC2 with screen/tmux
cd /tmp/market-pipeline
export $(cat ~/.config/market-secrets/credentials.env | xargs)
python3 fundamentals_collector_production.py

# 4. Monitor progress
tail -f /tmp/collector.log

# 5. Load results back to local Cassandra
scp ec2-user@13.218.137.191:/tmp/reports/FUNDAMENTALS_API_COLLECTED_*.cql \
    market-pipeline/code/python_files/reports/
```

---

## API Configuration

| API | Key Status | Rate Limit | Coverage |
|-----|------------|-----------|----------|
| AlphaVantage | ✅ Valid | 5 calls/min | US only |
| EODHD | ✅ Valid | 2 calls/sec | Global (EU/JP/KR/CN) |
| J-Quants | ✅ Valid | Throttled | Japan corporate |
| EDINET | ✅ Valid | 100/day | Japan filings |
| screener.in | ✅ Valid | 3 calls/sec | India 10y history |
| DART | ✅ Valid | Throttled | Korea corporate |

---

## Parallel Execution Strategy

### Worker Distribution
```
AlphaVantage:  3 workers (rate-limited)
EODHD:         4 workers per market (EU/JP/KR/CN)
J-Quants:      2 workers (optional, Japan deep-dive)
screener.in:   1 worker (India optional)

Total parallel streams: 14 workers
```

### Timeline (Parallel)
| Phase | Market | Duration | Parallel |
|-------|--------|----------|----------|
| 1 | US (AlphaVantage) | 4-6h | ✓ Main |
| 2 | Europe (EODHD) | 2h | ✓ Parallel with US |
| 3 | Japan (EODHD) | 3h | ✓ Parallel with US |
| 4 | Korea (EODHD) | 2h | ✓ Parallel with US |
| 5 | China (EODHD) | 3h | ✓ Parallel with US |
| **Total** | | **6-8h** | ✓ All parallel |

---

## Expected Output (Post-Collection)

### Coverage Transformation
```
Before:  22% (5,475 with real fundamentals)
After:   100% (25,335 with PE/PB/ROE)

Symbols added:    19,860
Coverage gain:    78 percentage points
Improvement:      363% (19,860 / 5,475)
```

### Data Quality
- **PE Ratios:** 95%+ availability (most liquid markets)
- **PB Ratios:** 85%+ availability (less common in emerging markets)
- **ROE:** 70%+ availability (requires balance sheet data)
- **Fallback:** Quality score (1-100) for any missing fundamental

### CQL Output
```
FUNDAMENTALS_API_COLLECTED_US_2026-07-29_HHMMSS.cql
├─ 7,283 UPDATE statements
└─ ~2 MB file size

FUNDAMENTALS_API_COLLECTED_EUROPE_2026-07-29_HHMMSS.cql
├─ 1,709 UPDATE statements
└─ 0.5 MB file size

... (similar for JP/KR/CN)
```

---

## Success Criteria

✅ **Collection Success**
- [ ] US: 7,283/7,283 attempted (target: 90%+ success = 6,555)
- [ ] Europe: 1,709/1,709 (target: 85%+ = 1,452)
- [ ] Japan: 3,083/3,083 (target: 75%+ = 2,312)
- [ ] Korea: 2,597/2,597 (target: 80%+ = 2,078)
- [ ] China: 5,188/5,188 (target: 70%+ = 3,632)

✅ **Database Validation**
- [ ] All CQL loads without errors
- [ ] Query: `SELECT COUNT(*) FROM stock_quotes WHERE pe > 0` returns 20,000+
- [ ] Daily scan returns non-zero Darvas/Piotroski signals

---

## Deployment Checklist

- [ ] Verify API keys in credentials.env
- [ ] Clone collector to EC2: `/tmp/fundamentals_collector_production.py`
- [ ] Start EC2 t3.micro if stopped
- [ ] Run collector in tmux/screen session
- [ ] Monitor logs: `tail -f collector.log`
- [ ] Generate CQL files
- [ ] SCP CQL files back to local
- [ ] Load to Cassandra: `cqlsh -f FUNDAMENTALS_API_COLLECTED_*.cql`
- [ ] Run verification queries
- [ ] Commit results to git
- [ ] Notify team: "100% fundamentals coverage achieved"

---

## Rollback Plan

If collection encounters errors:
1. **Partial data:** Load only successful market CQL files
2. **API limits exceeded:** Pause, wait 24h, resume from last symbol
3. **Bad data:** DELETE problematic rows from stock_quotes, retry that market
4. **Cassandra timeout:** Increase batch size, reduce worker count

---

## Next Steps After Collection

1. **Daily Scan Re-run**
   ```bash
   curl -X POST http://localhost:8000/api/db/daily/scan?market=all
   ```

2. **Strategy Backtests**
   - Darvas with real PE/PB (vs proxies)
   - Piotroski scoring refinement
   - Value anomaly detection

3. **Portfolio Optimization**
   - Constraint: ROE > 10%
   - Constraint: PE < 20 (or market-relative)
   - Maximize Sharpe with fundamental filters

4. **Live Scanning**
   - Daily market-adjusted Darvas alerts
   - Real fundamentals in screener output

---

**Estimated completion:** 6-8 hours from EC2 launch  
**Result:** Global Data Library 100% coverage (25,335 symbols with PE/PB/ROE)  
**Next gate:** Strategy backtests + portfolio optimization
