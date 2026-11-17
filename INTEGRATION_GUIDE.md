# 🚀 Quick Integration Guide: US Trade Export Analysis

## Step 1: Add FastAPI Router to Your Backend

In your **main FastAPI app** (e.g., `backend/main.py`):

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the new US Trade router
from routers.us_trade_export_router import router as us_trade_router

app = FastAPI()

# Add CORS if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include existing routers
# ... your current routers ...

# Add the new US Trade Export router
app.include_router(us_trade_router)  # ← Add this line

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
```

---

## Step 2: Verify Installation

Start your backend:
```bash
cd /Users/umashankar
python backend/main.py
# or
uvicorn backend.main:app --reload --port 8000
```

Test the new endpoints:
```bash
# Test 1: Top export opportunities
curl http://localhost:8000/api/us-trade/opportunities | jq

# Test 2: Commodity trade balance
curl http://localhost:8000/api/us-trade/commodities | jq

# Test 3: Port specialization
curl http://localhost:8000/api/us-trade/ports | jq

# Test 4: Refined petroleum margins to Asia
curl "http://localhost:8000/api/us-trade/margins?commodity=2710" | jq

# Test 5: Refined product breakdown (HS codes)
curl http://localhost:8000/api/us-trade/refined-products | jq

# Test 6: HS code tariff reference
curl http://localhost:8000/api/us-trade/tariff-reference | jq

# Test 7: Executive summary
curl http://localhost:8000/api/us-trade/summary | jq
```

**Expected Response (Test 1):**
```json
{
  "timestamp": "2026-08-10T12:00:00",
  "opportunities": [
    {
      "rank": 1,
      "commodity": "Refined Petroleum (HS 2710)",
      "export_score": 88,
      "current_exports": "3.5M bbl/day",
      "export_potential": "4.0M bbl/day (+500K capacity)",
      "margin_net_per_unit": "$12-15/bbl",
      "annual_opportunity_usd": "$2.2B - $2.7B",
      "best_ports": ["Port of Houston", "Port of Beaumont"]
    }
  ]
}
```

---

## Step 3: Display in Your React Frontend

Add a new view in your React app (`frontend/src/USTradeExportAnalysis.jsx`):

```jsx
import React, { useState, useEffect } from 'react';

export default function USTradeExportAnalysis() {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/us-trade/opportunities')
      .then(r => r.json())
      .then(data => {
        setOpportunities(data.opportunities);
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold mb-6">🚢 US Commodity Export Opportunities</h1>

      <div className="grid grid-cols-1 gap-4">
        {opportunities.map((opp, idx) => (
          <div key={idx} className="border rounded-lg p-4 bg-white shadow">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-xl font-semibold">
                  {opp.rank}. {opp.commodity}
                </h2>
                <p className="text-gray-600 text-sm mt-1">
                  Score: {opp.export_score}/100
                </p>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-green-600">
                  {opp.annual_opportunity_usd}
                </div>
                <p className="text-gray-600 text-xs">Annual Opportunity</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mt-4">
              <div>
                <p className="text-gray-600 text-xs uppercase">Current Exports</p>
                <p className="font-semibold">{opp.current_exports}</p>
              </div>
              <div>
                <p className="text-gray-600 text-xs uppercase">Potential</p>
                <p className="font-semibold">{opp.export_potential}</p>
              </div>
              <div>
                <p className="text-gray-600 text-xs uppercase">Net Margin</p>
                <p className="font-semibold">{opp.margin_net_per_unit}</p>
              </div>
              <div>
                <p className="text-gray-600 text-xs uppercase">Best Ports</p>
                <p className="font-semibold text-sm">{opp.best_ports.join(", ")}</p>
              </div>
            </div>

            <div className="mt-4">
              <p className="text-gray-600 text-xs uppercase font-semibold mb-2">Key Markets</p>
              <div className="flex flex-wrap gap-2">
                {opp.key_markets.map((market, i) => (
                  <span key={i} className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">
                    {market}
                  </span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

Add to your main navigation:
```jsx
import USTradeExportAnalysis from './USTradeExportAnalysis';

<Route path="/us-trade" element={<USTradeExportAnalysis />} />
```

---

## Step 4: Add to Your Dashboard

Add tabs to your existing dashboard:

```jsx
// In your DailyReport.jsx or main dashboard
const [activeTab, setActiveTab] = useState('daily-report');

return (
  <div>
    <div className="flex space-x-2 border-b mb-4">
      <button
        onClick={() => setActiveTab('daily-report')}
        className={`px-4 py-2 ${activeTab === 'daily-report' ? 'border-b-2 border-blue-500' : ''}`}
      >
        ⚡ Daily Report
      </button>
      <button
        onClick={() => setActiveTab('us-trade')}
        className={`px-4 py-2 ${activeTab === 'us-trade' ? 'border-b-2 border-blue-500' : ''}`}
      >
        🚢 US Trade Export
      </button>
    </div>

    {activeTab === 'daily-report' && <DailyReportContent />}
    {activeTab === 'us-trade' && <USTradeExportAnalysis />}
  </div>
);
```

---

## Step 5: Optional - Schedule Daily Updates

Add to your scheduler (`backend/db/scheduler.py`):

```python
from apscheduler.schedulers.background import BackgroundScheduler
import subprocess

def update_us_trade_analysis():
    """Update US trade analysis daily at 6 AM."""
    try:
        result = subprocess.run(
            ['python3', 'us_commodity_trade_balance.py'],
            capture_output=True,
            timeout=300
        )
        if result.returncode == 0:
            logger.info("✅ US Trade analysis updated")
        else:
            logger.error(f"❌ US Trade analysis failed: {result.stderr}")
    except Exception as e:
        logger.error(f"US Trade analysis error: {e}")

scheduler = BackgroundScheduler()
scheduler.add_job(update_us_trade_analysis, 'cron', hour=6, minute=0)
scheduler.start()
```

---

## Step 6: View in Browser

Open your frontend:
```
http://localhost:5173/us-trade
```

You should see:
- ✅ Top 3-4 export opportunities with scores
- ✅ Current vs potential export volumes
- ✅ Net margin per unit
- ✅ Annual opportunity in USD
- ✅ Best ports for each commodity
- ✅ Key markets by region

---

## 📊 Real-Time Data Flow

```
┌─────────────────────────────────────────────────────────┐
│ EIA API / FRED API / Market Data (Fallback)            │
│ • Crude Oil (WTI)                                       │
│ • Refined Petroleum (Gasoline, Diesel)                 │
│ • Natural Gas & LNG                                     │
│ • Thermal Coal                                          │
└────────────┬────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────┐
│ us_trade_export_analyzer.py                             │
│ • Scoring (100-point suitability model)                 │
│ • Export margins by region                              │
│ • Port allocation                                       │
└────────────┬────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────┐
│ data/market_data.duckdb (Cached)                        │
│ • us_export_opportunities table                         │
│ • Port allocation matrix                                │
│ • Margin data by region                                 │
└────────────┬────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────┐
│ FastAPI Routes (routers/us_trade_export_router.py)      │
│ GET /api/us-trade/opportunities                         │
│ GET /api/us-trade/commodities                           │
│ GET /api/us-trade/ports                                 │
│ GET /api/us-trade/margins                               │
│ GET /api/us-trade/refined-products                      │
│ GET /api/us-trade/tariff-reference                      │
│ GET /api/us-trade/summary                               │
└────────────┬────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────┐
│ React Frontend (USTradeExportAnalysis.jsx)              │
│ • Display opportunities with cards                      │
│ • Interactive port selector                             │
│ • Margin breakdowns by region                           │
│ • HS code reference tables                              │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ Validation Checklist

- [ ] FastAPI router imported in `main.py`
- [ ] All 7 endpoints responding with data
- [ ] React component displaying opportunities
- [ ] Dashboard tab added
- [ ] Margins correctly calculated (gross - logistics = net)
- [ ] Port specialization scores ranking correctly
- [ ] HS codes mapping correctly (2710 → Refined Petroleum)

---

## 🎯 Key Metrics to Monitor

1. **Refined Petroleum (HS 2710) exports** → Target: +500K bbl/day by Q4 2026
2. **LNG terminal utilization** → Target: 13-15 BCF/day (Freeport expansion)
3. **Coal exports to India** → Target: +25M tons/year
4. **Port of Houston throughput** → Track capacity utilization
5. **Margins by destination** → Monitor Asia vs Europe spreads

---

## 📞 Questions?

Refer to:
- `US_TRADE_EXPORT_README.md` — Full documentation
- `us_trade_export_analyzer.py` — EIA API integration
- `us_commodity_trade_balance.py` — Trade balance data
- `routers/us_trade_export_router.py` — API endpoint definitions

---

**Ready to go live? Run this to verify:**

```bash
# Activate venv
source ~/.venvs/trade-analysis/bin/activate

# Run backend
cd /Users/umashankar && python backend/main.py &

# Test endpoints
sleep 2
curl http://localhost:8000/api/us-trade/summary | jq '.summary.top_ports_by_energy'

# Should show Port of Houston with score 98 ✅
```

**Happy exporting! 🚢📊**
