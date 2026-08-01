# 🚀 MONDAY STARTUP CHECKLIST
## Week 1 Integration Kick-off (Aug 5, 2026)

---

## ⏰ TIMELINE: 8 hours (9 AM - 5 PM)

| Time | Task | Owner | Duration |
|------|------|-------|----------|
| 9:00 AM | Setup + Pull code | All | 15 min |
| 9:15 AM | Task 1.1: Verify score scale | Data Sci | 45 min |
| 10:00 AM | Team sync: Findings | Lead | 15 min |
| 10:15 AM | Task 1.2: Query markets | Data Sci | 45 min |
| 11:00 AM | **GO/NO-GO DECISION** | Lead | 15 min |
| 11:15 AM | If GO: Prep Task 2.1 | Backend | 3 hrs |
| 2:15 PM | Lunch | All | 45 min |
| 3:00 PM | If GO: Test DuckDB conn | Backend | 1 hr |
| 4:00 PM | Day 1 wrap + Plan Day 2 | Lead | 1 hr |

---

## 📋 TEAM ROLES & TASKS

### 👨‍💼 **TEAM LEAD** (Coordinator)
- [ ] Pull branch: `git pull origin claude/strategy-pipeline`
- [ ] Read: `NEXT_STEPS.md` (understand 6-task flow)
- [ ] Read: `WEEK1_INTEGRATION_PLAN.md` (understand blockers)
- [ ] Share with team (Slack + meeting)
- [ ] **9:15 AM**: Schedule standup at 10 AM
- [ ] **10 AM**: Collect Task 1.1 + 1.2 findings
- [ ] **11 AM**: Make GO/NO-GO decision (see Decision Gate below)
- [ ] **4 PM**: Document Day 1 status, plan Day 2 assignments

### 🔬 **DATA SCIENTIST** (Tasks 1.1 + 1.2)

#### Task 1.1: Verify Score Scale ⏰ 45 min
```bash
# Step 1: Install dependencies (5 min)
python3 -m pip install --user duckdb pandas

# Step 2: Run verification (5 min)
cd ~/market-pipeline/code/python_files/data_science_framework
python3 task_1_1_verification.py

# Step 3: Record findings (15 min)
# Document in shared doc:
```

**Record These 4 Numbers:**
- [ ] F-Score range: MIN _____ to MAX _____
- [ ] ROCE max value: _______ (RED FLAG if > 100%)
- [ ] India F-Score coverage: _______ % (target: >80%)
- [ ] US F-Score coverage: _______ % (target: >80%)

**Decision Gate - TASK 1.1 SUCCESS?**
```
✅ F-Score scale is 0-9 or 0-12?        YES / NO
✅ ROCE max < 100% (ex-cash valid)?     YES / NO
✅ India coverage > 80%?                YES / NO
✅ US coverage > 80%?                   YES / NO
```
⏸ **PAUSE** — Report to Team Lead at 10 AM standup

---

#### Task 1.2: Query All Markets ⏰ 45 min
**Only proceed if Task 1.1 = ALL YES**

```bash
# Run after Task 1.1 findings validated
python3 << 'EOF'
import duckdb
import pandas as pd

db_path = '/Users/umashankar/market-pipeline/reports_local/global_fundamentals.duckdb'
conn = duckdb.connect(db_path)

markets = conn.execute("""
    SELECT 
        market,
        COUNT(*) as total,
        COUNT(CASE WHEN piotroski IS NOT NULL THEN 1 END) as f_score_count,
        COUNT(CASE WHEN roce IS NOT NULL THEN 1 END) as roce_count,
        COUNT(CASE WHEN piotroski >= 7 THEN 1 END) as high_quality
    FROM fundamentals
    GROUP BY market
    ORDER BY total DESC
""").fetchall()

df = pd.DataFrame(markets, columns=['Market', 'Total', 'F-Score', 'ROCE', 'F≥7'])
for col in ['F-Score', 'ROCE']:
    df[col + ' %'] = (df[col] / df['Total'] * 100).round(0).astype(int)

print(df[['Market', 'Total', 'F-Score %', 'ROCE %', 'F≥7']].to_string(index=False))
conn.close()
EOF
```

**Record These Results:**
```
Market | Total | F-Score % | ROCE % | High Quality (F≥7)
-------|-------|-----------|--------|-------------------
  IN   | _____ |    ____   |  ___   |      _____
  US   | _____ |    ____   |  ___   |      _____
  JP   | _____ |    ____   |  ___   |      _____
  KR   | _____ |    ____   |  ___   |      _____
  EU   | _____ |    ____   |  ___   |      _____
```

**Decision Gate - TASK 1.2 SUCCESS?**
```
✅ IN coverage > 80%?                   YES / NO
✅ US coverage > 80%?                   YES / NO
✅ JP/KR/EU coverage > 50%?             YES / NO
```

---

### 💻 **BACKEND DEV** (Task 2.1 prep)

**During 9 AM - 11 AM (while Task 1.1 + 1.2 run):**

- [ ] Read: `FINANCIAL_METRICS_INTEGRATION.md` (understand Piotroski design)
- [ ] Read: `NEXT_STEPS.md` → Task 2.1 section (understand code)
- [ ] Test DuckDB connection (11:15 AM):

```bash
python3 << 'EOF'
import duckdb
db_path = '/Users/umashankar/market-pipeline/reports_local/global_fundamentals.duckdb'
conn = duckdb.connect(db_path)

# Test 1: Can we query?
test = conn.execute("SELECT COUNT(*) FROM fundamentals").fetchall()
print(f"✅ DuckDB connected, {test[0][0]} total rows")

# Test 2: Sample data
sample = conn.execute("""
    SELECT ticker, piotroski, roce FROM fundamentals 
    WHERE market='US' AND piotroski >= 7 LIMIT 3
""").fetchall()
print(f"✅ US sample: {sample}")

conn.close()
EOF
```

**Prepare for Tuesday (if GO decision):**
- [ ] Create feature branch: `git checkout -b feature/quality-features`
- [ ] Stage Task 2.1 code structure
- [ ] Identify helper functions needed (list in team doc)

---

## 🎯 GO/NO-GO DECISION GATE (11 AM)

### GO Criteria (All must be YES)
```
[ ] Task 1.1: F-Score scale verified (0-9 or 0-12)
[ ] Task 1.1: ROCE max < 100% (ex-cash confirmed)
[ ] Task 1.2: IN + US coverage both > 80%
[ ] DuckDB connection test passed
[ ] Team alignment on 5-day plan
```

### Decision Outcomes

**✅ GO (Proceed to Day 2)**
- Task 2.1 + 2.3 scheduled for Tue-Wed
- Data Sci starts quality classification work
- Backend starts feature loading code
- Expected delivery: Wed EOD (ready for backtest Thu-Fri)

**🟨 CONDITIONAL GO (Proceed with scope reduction)**
- Example: JP/KR/EU < 50% coverage
- Action: Focus IN/US only for Week 1, JP/KR/EU defer to Week 2
- No impact on timeline (backtest still Thu-Fri)

**❌ NO-GO (Stop & debug)**
- Example: ROCE max > 100% or coverage < 50%
- Action: Spend Tue fixing data issues, push backtest to Week 2
- Communicate to stakeholders immediately

---

## 📊 END-OF-DAY SUMMARY (4 PM)

**Team Lead completes:**

### Findings Summary
```
Task 1.1 Results:
✅ F-Score scale: 0-? (standard Piotroski)
✅ ROCE max: __% (ex-cash confirmed / NOT confirmed)
✅ Data quality: ___ / 10

Task 1.2 Results:
✅ Markets queryable: IN, US, [JP, KR, EU]
✅ Coverage: IN __%, US __%, JP __%, KR __%, EU __%

Decision: ✅ GO / 🟨 CONDITIONAL / ❌ NO-GO
Reason: ___________________________________________
```

### Day 2 Assignments
```
Data Sci: Task 2.1 (load quality scores)
Backend:  Task 2.1 (DuckDB connection module)
QA:       Prepare test data for Task 3.2
Lead:     Daily standup + blocker tracking
```

### Blockers Identified
```
None / [list any issues found during Day 1]
```

### Slack Announcement
> **Week 1 Status: [GO/NO-GO]**
> 
> Day 1 findings: F-Score ✅, ROCE ✅, Coverage ✅
> 
> Tomorrow: Task 2.1 + 2.3 (Feature Engineering + Quality Classification)
> 
> Blockers: None / [list]

---

## 🔴 CRITICAL RED FLAGS (Stop & Investigate)

If ANY of these occur, escalate to Lead immediately:

- [ ] ROCE max > 100% → Cash inflation in large-caps
- [ ] F-Score coverage < 50% → Data loading issue
- [ ] DuckDB connection fails → Database path / permissions issue
- [ ] Score scale unknown (not 0-9, 0-12, 0-100) → Data corruption?

---

## 📞 TEAM CONTACTS

| Role | Name | Slack | Task |
|------|------|-------|------|
| Lead | _____ | @____ | Decision maker |
| Data Sci | _____ | @____ | Task 1.1 + 1.2 |
| Backend | _____ | @____ | Task 2.1 prep |
| QA | _____ | @____ | Validation |

---

## ✅ PRE-MEETING CHECKLIST (8:45 AM)

Before the 9 AM kickoff:

- [ ] All team members have access to `claude/strategy-pipeline` branch
- [ ] Everyone read `NEXT_STEPS.md` (executive summary, 2 min)
- [ ] Slack channel created or designated for daily updates
- [ ] Shared doc for recording Task 1.1 + 1.2 findings
- [ ] DuckDB database path confirmed: `/Users/umashankar/market-pipeline/reports_local/global_fundamentals.duckdb`
- [ ] Python 3.9+ available on all machines
- [ ] Network access to Dropbox/database confirmed

---

## 🎯 SUCCESS = Friday Celebration

**If all 6 tasks complete by Friday EOD:**

✅ Piotroski integration complete  
✅ 5-year backtest done (+400-600bps improvement expected)  
✅ Production deployment ready Week 2  
✅ Global markets (JP/KR/EU) queued for Week 3

**Print this checklist. Tape to monitors. Execute with precision. 🚀**

---

**Created:** 2026-08-01  
**Updated:** [date of execution]  
**Owner:** [Team Lead]  
**Status:** READY FOR MONDAY
