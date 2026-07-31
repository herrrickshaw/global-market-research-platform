# Global Data Library — Next Actions (2026-07-29 03:30 IST)

## 🚀 PHASE 1: Execute NOW (3-4 hours)

### Europe + Korea Batch Extraction
```bash
cd /Users/umashankar/market-pipeline/code/python_files

# Start extraction (runs in foreground with logging)
python3 edgar_europe_korea_batch.py | tee ../logs/phase1_extraction.log

# OR run in background
nohup python3 edgar_europe_korea_batch.py > ../logs/phase1_extraction.log 2>&1 &
```

**Expected Results:**
- ✅ 966 Europe symbols → ~98-300 with PE (baseline unknown)
- ✅ 2,768 Korea symbols → ~400-800 with PE
- **Gain: +24.6% → 30.8% completeness**

**Output Files:**
- `edgar_europe_batch_YYYY-MM-DD_HHMMSS.json`
- `edgar_korea_batch_YYYY-MM-DD_HHMMSS.json`
- `edgar_europe_batch_cassandra_*.cql`
- `edgar_korea_batch_cassandra_*.cql`

---

## 🌙 PHASE 2: Schedule for Tonight (8pm-4am)

### US AlphaVantage Overnight Batch
```bash
# Option A: Schedule for 8pm tonight
at 20:00 << 'CMD'
cd /Users/umashankar/market-pipeline/code/python_files
python3 edgar_alphavantage_overnight.py >> ../logs/phase2_overnight.log 2>&1
CMD

# Option B: Run now with time.sleep() to delay until 8pm
python3 -c "
import time
from datetime import datetime
target = datetime.strptime('20:00', '%H:%M').timestamp()
now = datetime.now().timestamp()
delay = target - now
if delay > 0:
    print(f'Sleeping {delay/3600:.1f}h until 8pm...')
    time.sleep(delay)
" && \
python3 edgar_alphavantage_overnight.py >> ../logs/phase2_overnight.log 2>&1

# Option C: Just run now (7-8 hour runtime)
python3 edgar_alphavantage_overnight.py | tee ../logs/phase2_overnight.log
```

**Expected Results:**
- ✅ 7,442 US symbols → 2,000-4,000 with PE (AlphaVantage coverage varies)
- **Gain: +36.9% → 67.7% completeness**
- **(TARGET 50%+ EXCEEDED)**

**Output Files:**
- `edgar_alphavantage_overnight_YYYY-MM-DD_HHMMSS.json`
- `edgar_us_alphavantage_cassandra_*.cql`

---

## 💾 LOAD TO CASSANDRA (After each phase)

### Cassandra Quick Start
```bash
# Check if running
docker ps | grep cassandra

# If not running, start it
docker start cassandra

# Load Phase 1 results
cqlsh -f /Users/umashankar/market-pipeline/code/python_files/reports/edgar_europe_batch_cassandra_*.cql
cqlsh -f /Users/umashankar/market-pipeline/code/python_files/reports/edgar_korea_batch_cassandra_*.cql

# Load Phase 2 results (after overnight completes)
cqlsh -f /Users/umashankar/market-pipeline/code/python_files/reports/edgar_us_alphavantage_cassandra_*.cql

# Verify
docker exec cassandra cqlsh -e "SELECT COUNT(*) FROM herrrickshaw.stock_quotes WHERE pe IS NOT NULL;"
```

---

## 📊 MONITORING

### Watch Phase 1 Progress
```bash
# In new terminal
tail -f /Users/umashankar/market-pipeline/logs/phase1_extraction.log
```

### Watch Phase 2 Progress (Tonight)
```bash
# In new terminal
tail -f /Users/umashankar/market-pipeline/logs/phase2_overnight.log
```

### Quick Status Check
```bash
# Count extracted symbols
cd /Users/umashankar/market-pipeline/code/python_files/reports
for f in edgar_*_batch_*.json; do
  python3 -c "import json; d=json.load(open('$f')); print(f'{f}: {d[\"metadata\"][\"symbols_extracted\"]}')"
done
```

---

## 🎯 SUCCESS CRITERIA

### Phase 1 (NOW)
- [ ] edgar_europe_batch_*.json generated
- [ ] edgar_korea_batch_*.json generated
- [ ] Both loaded to Cassandra
- [ ] Completeness increased to ~30%

### Phase 2 (TONIGHT)
- [ ] edgar_alphavantage_overnight_*.json generated
- [ ] US data loaded to Cassandra
- [ ] Completeness reaches 50%+ (TARGET)

### Post-Execution
- [ ] Update git with final results
- [ ] Update PR #24 with new completeness numbers
- [ ] Update launchd job to use proven extractors

---

## ⚠️ ROLLBACK / TROUBLESHOOTING

### If Phase 1 Fails
```bash
# Kill running process
pkill -f edgar_europe_korea_batch.py

# Check logs for specific error
tail -100 /Users/umashankar/market-pipeline/logs/phase1_extraction.log

# Common issues:
# - yfinance throttled after 50 symbols: Add backoff delay
# - No symbols loaded: Check CSV files exist
# - Network timeout: Check connectivity to yfinance
```

### If Cassandra Load Fails
```bash
# Verify Cassandra is running
docker exec cassandra cqlsh -e "SELECT * FROM system.peers;"

# Restart if needed
docker stop cassandra && docker start cassandra

# Check CQL syntax
head -20 edgar_europe_batch_cassandra_*.cql

# Try loading single file
cqlsh -f edgar_europe_batch_cassandra_*.cql
```

---

## 📝 EXPECTED TIMELINE

| Phase | Start | End | Duration | Symbols | Total % |
|-------|-------|-----|----------|---------|---------|
| 1 | NOW | +3h | 3h | +3,734 | 30.8% |
| 2 | 8pm | 4am | 8h | +7,442 | 67.7% |
| **TARGET HIT** | — | — | — | — | **50%+** ✅ |

---

## 📖 FILES GENERATED TODAY

```
/Users/umashankar/market-pipeline/
├── EXTRACTION_STRATEGY.md (this file's plan)
├── NEXT_ACTIONS.md (this file - execution guide)
├── code/python_files/
│   ├── comprehensive_extractor.py (API audit script)
│   ├── edgar_europe_korea_batch.py (Phase 1 executor)
│   ├── edgar_alphavantage_overnight.py (Phase 2 executor)
│   └── reports/
│       ├── edgar_europe_batch_*.json
│       ├── edgar_korea_batch_*.json
│       ├── edgar_alphavantage_overnight_*.json
│       ├── edgar_*_cassandra_*.cql (bulk loaders)
└── logs/
    ├── phase1_extraction.log
    └── phase2_overnight.log
```

