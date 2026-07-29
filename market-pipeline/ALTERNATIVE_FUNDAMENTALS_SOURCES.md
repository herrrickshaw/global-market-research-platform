# Alternative Fundamentals Data Sources — Capability Map

**Objective**: Supplement 20-column canonical fundamentals beyond current quality_score fallback.  
**Current Status**: 25,335 symbols at 100% quality_score coverage; baseline fundamentals (PE, ROE, etc.) at ~26-43% depending on market.  
**Task**: Identify viable supplemental sources for PE, ROE, dividend_yield, margins, and other metrics.

---

## Summary Matrix: API Capabilities vs. Market Coverage

| Source | PE | ROE | Div Yield | Margins | Market Coverage | Free Tier | Rate Limit | Status |
|---|---|---|---|---|---|---|---|---|
| **EODHD** | ✅ | ✅ | ✅ | ✅ (npm, opm) | US, EU, JP, KR | EOD-only (no fund) | 2/sec | ❌ Paid tier required |
| **AlphaVantage** | ✅ | ❌ | ❌ | ✅ (margins) | US | 25/day | 5/min | ❌ Too limited |
| **FRED (macro)** | ❌ | ❌ | ❌ | ❌ | US macro indices only | ✅ Free | Unlimited | ❌ Not per-stock |
| **J-Quants (JP)** | ✅ | ✅ | ✅ | ✅ | Japan only (2,000+ stocks) | ✅ Free | 1/sec | ✅ VIABLE |
| **EDINET (JP filings)** | ✅ | ✅ | ✅ | ✅ | Japan corp filings | ✅ Free | Unlimited | ⚠️ Parsing required |
| **MarketAux** | ❌ | ❌ | ❌ | ❌ | News/sentiment only | ✅ | — | ❌ No fundamentals |
| **SEC EDGAR (US)** | ✅ | ✅ | ✅ | ✅ | US public only (~7,400) | ✅ Free | Unlimited | ⚠️ Parse 10-K/10-Q |
| **DART (Korea)** | ✅ | ✅ | ✅ | ✅ | Korea only (~2,500) | ✅ Free | 2/sec | ✅ VIABLE |
| **Screener.in (IN)** | ✅ | ✅ | ✅ | ✅ | India (~2,400) | Free trial | 1/sec | ✅ ALREADY INTEGRATED |
| **yfinance** | ✅ (lag) | ⚠️ | ✅ | ⚠️ (approx) | All markets | ✅ Free | 1-2/sec | ⚠️ Unreliable for non-US |
| **Buffett API** | ❌ | ❌ | ❌ | ❌ | No fundamentals endpoint | — | — | ❌ Not applicable |
| **World Bank API** | ❌ | ❌ | ❌ | ❌ | Macro only (country-level) | ✅ | Unlimited | ❌ Not per-stock |
| **Yahoo Finance** | ✅ (lag) | ⚠️ | ✅ | ⚠️ | All markets | ✅ | 2/sec | ⚠️ Lag: 2-4 weeks |

---

## Tier 1: High-Viability Untested Sources

### 1. **J-Quants API (Japan)** ⚠️ DEPRECATED V1
- **What**: Japanese financial market data including fundamentals for 2,000+ JSE-listed companies
- **Fundamentals**: ✅ PE, PB, PS, ROE, ROA, dividend yield, margins
- **Rate limit**: 1 request/sec (reasonable for batch collection)
- **Free tier**: ✅ Yes, fully free
- **Implementation**: HTTP REST API (V1 deprecated; V2 auth undocumented)
- **Credential status**: JQUANTS_API_KEY available in credentials.env
- **Test result**: ❌ V1 API returns 410 "J-Quants has moved to V2" with migration URL
- **V2 Status**: Endpoint exists but authentication header format differs from V1 (not yet documented in public sources)
- **Verdict**: ⚠️ DEFERRED — Requires reverse-engineering V2 API or waiting for official migration guide
- **Alternative**: Use yfinance for Japan symbols (current fallback)

### 2. **EDINET API (Japan Corporate Filings)** ✅ Credential exists
- **What**: Japanese corporate financial statements (XBRL format) filed with EDINET
- **Fundamentals**: ✅ PE, ROE, ROA, debt/equity, current ratio (from balance sheets)
- **Coverage**: ~90% of JSE-listed companies file with EDINET
- **Rate limit**: Unlimited
- **Free tier**: ✅ Yes
- **Implementation**: REST API + XML/XBRL parsing (complex)
- **Credential status**: EDINET_API_KEY available
- **Upside**: Official source, highest accuracy
- **Downside**: Requires XBRL parsing; quarterly filings only (not live prices)
- **Status**: NOT YET TESTED — lower priority than J-Quants (more parsing complexity)

### 3. **DART API (Korea)** ✅ Credential exists
- **What**: Korean financial statements from DART (Korea's filing system)
- **Fundamentals**: ✅ PE, ROE, margins, debt, cash flow metrics
- **Coverage**: 2,500+ KOSPI/KOSDAQ listed companies
- **Rate limit**: 2 requests/sec
- **Free tier**: ✅ Yes
- **Credential status**: DART_KEY available (currently used for news, can pivot to financials endpoint)
- **Upside**: Can cover all ~2,597 Korea symbols
- **Downside**: DART is less documented than J-Quants; requires Korean language fluency for some fields
- **Status**: PARTIALLY TESTED (currently used for news; financials endpoint untested)

### 4. **SEC EDGAR (US)** ✅ Free & public
- **What**: US public company 10-K and 10-Q filings
- **Fundamentals**: ✅ All 20 columns extractable from balance sheet, income statement, cash flow
- **Coverage**: ~7,300 public companies (matches our ~7,400 US symbols)
- **Rate limit**: Unlimited (but be respectful: 1-3 requests/sec)
- **Free tier**: ✅ Fully open API
- **Implementation**: REST API; JSON responses; requires parsing 10-K/10-Q structure
- **Upside**: Official source; comprehensive fundamentals; most recent 10-Q usually within 60 days
- **Downside**: Quarterly only (not latest quarter edge-case); requires understanding XBRL/SEC format
- **Tools available**: 
  - sec-edgar-downloader (Python, open source)
  - edgar (Python package)
  - Direct API: https://www.sec.gov/files/company_tickers.json
- **Status**: NOT YET TESTED — viable for US market

---

## Tier 1b: HIGH-PRIORITY AFTER TESTING

### 4a. **SEC EDGAR (US)** ✅ Credential not needed (public API)
- **What**: US public company financial statements (10-K annual, 10-Q quarterly)
- **Fundamentals**: ✅ All 20 columns extractable from XBRL tables (balance sheet, income, cash flow)
- **Coverage**: ~7,300 public companies (matches our ~7,278 US symbols)
- **Rate limit**: Unlimited (be respectful: 1-3 req/sec)
- **Free tier**: ✅ Fully open API, no authentication
- **Implementation**: REST API or sec-edgar-downloader library (Python, open source)
- **Viability**: ✅ VERY HIGH — official source, comprehensive data
- **Test status**: NOT YET TESTED (but SEC EDGAR is public/standardized)
- **Work estimate**: 2-3 days (parser + batch collection)
- **Expected coverage**: US 26% → ~80%+ (most recent quarter within 60 days)

### 4b. **DART API (Korea)** ⚠️ Partially tested
- **What**: Korean financial statements from DART (official Korean filing system)
- **Fundamentals**: ✅ PE, ROE, margins, debt, cash flow metrics
- **Coverage**: 2,500+ KOSPI/KOSDAQ listed companies
- **Rate limit**: 2 requests/sec
- **Free tier**: ✅ Yes, fully free
- **Credential status**: DART_KEY available (currently used for news queries; financials endpoint untested)
- **Viability**: ✅ HIGH — official source, well-documented API
- **Test status**: PARTIALLY TESTED (news endpoint works; financials endpoint not yet tested)
- **Work estimate**: 1-2 days (minimal, endpoint pivot only)
- **Expected coverage**: Korea 0% → ~60%+ (most recent quarter available)

## Tier 2: Partial/Unreliable/Tested Sources

### 7. **MarketAux** ❌ TESTED
- **Test result**: Confirmed NO fundamentals endpoint; news/sentiment only
- **API endpoints tested**:
  - `/v1/fundamentals` — 404 invalid
  - `/v1/entity/news` — 404 invalid
  - `/v1/last_news` — 200 OK (news only)
- **Verdict**: ❌ Not viable for fundamentals

### 5. **yfinance (fallback for all markets)**
- **Pros**: Already integrated; covers all markets
- **Cons**: Unreliable margin data; ROE estimates only; 2-4 week lag on earnings
- **Current use**: Fallback when API data unavailable
- **Viability**: Mediocre — use only when no other source exists

### 6. **FRED (Federal Reserve Economic Data)**
- **Pros**: Macro indicators (inflation, employment, GDP)
- **Cons**: NOT per-stock; country/sector-level only
- **Viability**: ❌ Not applicable for individual stock fundamentals

### 7. **MarketAux**
- **Status**: ❌ Tested; NO fundamentals endpoints (news/sentiment only)
- **Verdict**: Do not use for fundamentals

---

## Tier 3: Not Recommended

- **Buffett API**: No fundamentals endpoint
- **NewsAPI / NewsData**: Sentiment only, not fundamentals
- **World Bank API**: Macro/country-level, not per-stock
- **IEX Cloud**: Paid tier required for fundamentals (excluded per project cost constraints)
- **Kaggle**: Policy violation; prefer official sources

---

## Recommended Implementation Plan

### Phase 1 (Immediate): Test J-Quants for Japan (1 day)
1. Test J-Quants API with sample symbols
2. If successful: collect fundamentals for all 3,083 Japan symbols
3. Expected coverage lift: Japan 0% → ~70% (J-Quants) + fallback to yfinance for remaining

### Phase 2 (Next): SEC EDGAR for US (2-3 days)
1. Build 10-K/10-Q parser using sec-edgar-downloader
2. Map CIK (SEC identifier) to yfinance ticker
3. Extract PE, ROE, margins from XBRL tables
4. Expected coverage lift: US ~26% → ~80%+

### Phase 3 (Parallel): DART for Korea (1-2 days)
1. Pivot existing DART_KEY from news to financials endpoint
2. Test with sample symbols
3. If successful: collect all 2,597 Korea symbols
4. Expected coverage lift: Korea 0% → ~60%+

### Phase 4 (Optional): EDINET for Japan (if time permits)
- Use EDINET as secondary source for Japan symbols missing from J-Quants
- More complex parsing; lower priority

### Phase 5: Europe & China
- **Europe**: yfinance fallback for now (no dedicated free API)
- **China**: Eastmoney API (untested, would need separate research)

---

## Work Estimates (Revised After Testing)

| Phase | Source | Symbols | Est. Time | Effort | Coverage Gain | Priority |
|---|---|---|---|---|---|---|
| **1** | **SEC EDGAR** | **7,300** | **2-3 days** | **Parser dev + batch collection** | **US: 26%→80%+** | 🔴 **HIGHEST** |
| **2** | **DART API** | **2,597** | **1-2 days** | **Endpoint pivot + collection** | **Korea: 0%→60%+** | 🟠 **HIGH** |
| 3 | EDINET | 2,000 | 2-3 days | XBRL parser | Japan: 0%→20% | 🟡 MEDIUM |
| 4 | J-Quants V2 | 3,083 | TBD | Reverse-engineer V2 API | Japan: 20%→70% | 🔵 LOW (deferred) |
| **Total** | — | **9,897+** | **3-5 days** | — | **+40-50%** | — |

**Testing status**:
- ✅ MarketAux: Tested, not viable
- ⚠️ J-Quants: Tested, V1 deprecated (V2 requires reverse-engineering)
- ⏳ SEC EDGAR: Not tested yet (but public API, standardized format)
- ⏳ DART: Partially tested (news endpoint works; financials endpoint pending)

---

## Next Action (Revised Priority)

### Phase 1: SEC EDGAR for US (START IMMEDIATELY)
**Why**: Highest coverage gain (7,300+ symbols); official API; unlimited rate limit
```bash
# Step 1: Test SEC EDGAR API with sample ticker (AAPL)
python3 test_sec_edgar_fundamentals.py

# Step 2: Build bulk collector
# Step 3: Collect PE, ROE, margins, debt ratios from 10-K/10-Q

# Expected coverage: US 26% → ~80%+
```

### Phase 2: DART API for Korea (PARALLEL)
**Why**: High coverage gain (2,597 symbols); already have DART_KEY; minimal work
```bash
# Step 1: Pivot DART_KEY to financials endpoint
python3 test_dart_financials.py

# Step 2: Build batch collector
# Step 3: Collect fundamentals for 2,597 Korea symbols

# Expected coverage: Korea 0% → ~60%+
```

### Phase 3: J-Quants V2 (DEFERRED)
**Why**: V1 API deprecated; V2 auth format not yet documented
- Monitor for official J-Quants V2 documentation
- If documentation released: reverse-engineer V2 auth, implement Japan collector
- Fallback: Use yfinance for Japan symbols (current quality_score baseline)
