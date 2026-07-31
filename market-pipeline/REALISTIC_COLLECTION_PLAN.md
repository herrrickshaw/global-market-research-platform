# Realistic Data Collection Plan (2026-07-29)

## Your Proposed Schedule vs. Realistic Feasibility

| Collector | Your Plan | Realistic Status | Issue | Revised ETA |
|-----------|-----------|------------------|-------|------------|
| US EDGAR (2,200) | Now | ❌ API unreliable | PE missing 85%+ | Never (use cached or commercial) |
| India screener | 2026-07-30 | 🔴 BROKEN | API 404 all symbols | Needs fix (1-2 days to debug) |
| China akshare | 2026-08-02 | ⏳ Not tested | Likely needs auth | TBD (needs testing) |
| Japan J-Quants | 2026-08-03 | ⚠️ Partial | 1,000 extracted, response parsing issue | 2026-07-30 (quick fix) |
| Korea KRX | 2026-08-09 | ⏳ yfinance unreliable | PE missing 85%+ | Alternative: FinanceDataReader (not yf) |
| Europe yfinance | 2026-08-13 | ⏳ yfinance unreliable | PE missing 85%+ | Alternative: EODHD if key fixed |

## Why 50%+ Target Unrealistic with Current Approach

**Expected results if we run all 6 collectors:**
- US EDGAR: 100 symbols (yfinance again)
- India screener: 0 symbols (API broken)
- China akshare: 500-1,000 symbols (if it works)
- Japan J-Quants: 2,000 symbols (if we fix parsing)
- Korea KRX: 100 symbols (yfinance PE issue)
- Europe yfinance: 100 symbols (yfinance PE issue)

**Total: 2,800 symbols = 14% completeness**

This falls SHORT of 50% by 36 percentage points.

## What Actually Works

### ✅ Proven Working
1. **J-Quants (Japan)** — 1,000 symbols extracted
   - Issue: Response parsing (fixable)
   - Fix time: 1 hour
   - Result: +1,000 symbols

2. **Cached Data (Global)** — ~/repos/global-market-data/ltm/
   - Status: Unknown coverage
   - Risk: Data 2-3 months old
   - Time to audit: 1 hour

### ⏳ Needs Verification
1. **China akshare** — Never tested
2. **Korea FinanceDataReader** — Alternative to yfinance
3. **Europe EODHD** — If we fix API key issue

### 🔴 Broken / Unreliable
1. **yfinance .info** — PE missing 85%+ of calls
2. **AlphaVantage** — PE missing 85%+ of calls
3. **screener.in** — API 404 endpoint
4. **EODHD** — 403 auth error

## Revised Collection Plan (Realistic)

### IMMEDIATE (Today, 2026-07-29)
- [ ] Fix J-Quants response parsing → +1,000 symbols
- [ ] Audit cached data in ~/repos/global-market-data → +???? symbols
- [ ] Debug screener.in API → See if fixable
- **Estimated gain: +2,000-3,000 symbols = 12-15%**

### SHORT-TERM (Next 2 weeks)
- [ ] Test China akshare
- [ ] Test Korea FinanceDataReader
- [ ] Fix EODHD API key or find alternative
- [ ] Set up automated daily refresh for top 500 symbols
- **Estimated gain: +1,000-2,000 symbols = 5-10%**

### LONG-TERM (Month 2)
- [ ] Evaluate commercial APIs (FinHub, Polygon)
- [ ] Implement gradual expansion (50-100/week)
- [ ] Target 30-40% by end of Aug
- **Realistic 50%+ achieved by: October 2026**

## Honest Assessment

**The 50%+ target in 2 weeks is unachievable with free APIs.**

Reasons:
1. Free APIs (yfinance, AlphaVantage) have missing data
2. Commercial APIs (EODHD) have auth issues
3. Regulatory APIs (screener.in, DART) require heavy lifting
4. Cached data may be stale but could bridge gap quickly

## Recommendation

**Choose One:**

### A. Commit to Current 6.2% + Automate (Safest)
- Accept 6.2% completeness
- Build daily refresh for existing data
- Add 50-100 new symbols/week
- **Outcome: Sustainable, predictable**

### B. Aggressive Hybrid (Recommended)
- Audit cached data TODAY (1 hour)
- If cached has 20-30%, load it immediately
- Fix J-Quants parser (1 hour) → +1,000
- Debug screener.in (2 hours) → +2,000-5,000
- **Outcome: May reach 20-25% by tomorrow**

### C. Plan for Commercial APIs (Best Long-term)
- Start with free tier (FinHub, Polygon)
- Build connector this week
- Launch next week
- **Outcome: 50%+ achievable by Aug 15**

**What should we do?**

