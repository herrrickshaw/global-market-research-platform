# Global Data Library — Extraction Strategy (Updated)

**Report Date:** 2026-07-29
**Current Completeness:** 6.2% (1,246/20,129)
**Target:** 50%+ (10,065 symbols)

## API Assessment Results

### ✅ VIABLE SOURCES

| Source | Market | Status | Time | Notes |
|--------|--------|--------|------|-------|
| **J-Quants** | Japan | ⚠️ Needs fix | 1-2h | API key valid, response parsing issue |
| **AlphaVantage** | US | ✅ Ready | 7-8h | Free tier (5 calls/min), overnight batch |
| **yfinance** | Korea/EU | ✅ Works | 5-7h | Manual throttling required |

### 🔴 BLOCKED SOURCES

| Source | Reason | Impact | Alternative |
|--------|--------|--------|-------------|
| screener.in | API 404 endpoint | India 0% | yfinance overnight |
| EODHD | 403 Forbidden (key expired?) | US backup | Use AlphaVantage + yfinance |
| MarketAux | 404 endpoint | Minor | Not critical |

## Realistic Path to 50%+

### Phase 1: Quick Wins (Parallel, ~2-3 hours)

**1. Japan: J-Quants Full Extraction (3,709 symbols)**
```bash
# Fix: Debug API response structure
# Expected: 27% → 27% (already 1,000 extracted)
python3 edgar_jquants_full_debug.py  # TBD
```

**2. Europe: yfinance Batch (966 symbols)**
```bash
# Start immediately (lowest risk)
# Rate limit: 1 req/2sec = 30 min baseline
python3 edgar_europe_full.py
```

**3. Korea: yfinance Batch (2,768 symbols)**
```bash
# Rate limit: 1 req/2sec = 90 min baseline
python3 edgar_korea_full.py
```

**Total Phase 1 gain: +3,734 symbols → 6.2% → 24.8%**

### Phase 2: Overnight Batch (7-8 hours)

**1. US: AlphaVantage Overnight (7,442 symbols)**
```bash
# Run during off-hours (8pm - 4am)
# Uses free tier (5 calls/min) efficiently
python3 edgar_alphavantage_overnight.py  # TBD
```

**Total Phase 2 gain: +7,442 symbols → 24.8% → 61.8%**
*Target exceeded by 24%+ margin*

### Phase 3: Cleanup (1-2 hours)

**1. India: yfinance Batch (5,244 symbols)**
```bash
# Fallback after screener.in broken
# Rate limit same as Europe
python3 edgar_india_yfinance.py  # TBD
```

**Total Phase 3: +5,244 symbols (optional, already at 50%+)**

## Implementation Plan

### IMMEDIATE (Next 2-3 hours)
1. Create `edgar_europe_full.py` with throttle config (1 req/2sec)
2. Create `edgar_korea_full.py` with throttle config (1 req/2sec)
3. Run both in parallel via tmux/background
4. Monitor progress in logs

### TONIGHT (7-8 hours)
1. Queue `edgar_alphavantage_overnight.py` to start at 8pm
2. This uses commercial API key (valid) with 5 calls/min
3. Results will be ready by 4am

### TOMORROW (Optional)
1. If needed, extract India via yfinance
2. Load all results to Cassandra
3. Update PR #24 with final numbers

## Expected Timeline

| Phase | Start | End | Duration | Gain | Total |
|-------|-------|-----|----------|------|-------|
| 1 (Europe/Korea) | Now | 3h | 3h | +24.6% | 30.8% |
| 2 (US overnight) | 8pm | 4am | 8h | +36.9% | 67.7% |
| **TARGET HIT** | — | — | — | **+50%** | **56.2%** |
| 3 (India optional) | 8am | 10am | 2h | +26% | 82.2% |

## File Generation

All extractors will generate:
- `edgar_*.json` — Extraction metadata + results
- `edgar_*_cassandra.cql` — Bulk load statements
- Logs to `/Users/umashankar/market-pipeline/logs/`

## Risk Mitigation

- **Throttling:** 1 req/2sec (proven safe for yfinance)
- **API Rate Limits:** AlphaVantage 5 calls/min enforced in code
- **Fallbacks:** Each extractor logs failures separately
- **Monitoring:** Real-time progress in logs

## Success Criteria

✅ 50%+ = 10,065 symbols extracted
✅ All data loaded to Cassandra
✅ PR #24 updated with final report
