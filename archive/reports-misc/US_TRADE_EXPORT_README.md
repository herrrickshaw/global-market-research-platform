# 🚢 US Commodity Export Analysis Platform

**Purpose**: Identify optimal US commodity export opportunities using EIA data, trade balance analysis, and port specialization scoring.

## 📊 Analysis Overview

This system analyzes **5 key US export commodities** across **7 major US ports** to identify highest-margin export opportunities.

### Top Export Opportunities (Ranked by Score)

| Rank | Commodity | Score | Current Exports | Export Potential | Net Margin | Annual Opportunity |
|------|-----------|-------|-----------------|------------------|------------|-------------------|
| 1️⃣ | **Refined Petroleum (HS 2710)** | 88/100 | 3.5M bbl/day | 4.0M bbl/day | $12-15/bbl | **$2.2B - $2.7B** |
| 2️⃣ | **LNG (HS 271121)** | 78/100 | 12 BCF/day | 15 BCF/day | $1.7-$2.7/MMBtu | **$8.5B - $12.0B** |
| 3️⃣ | **Thermal Coal (HS 2701)** | 77/100 | 50M tons/yr | 75M tons/yr | $17/ton | **$425M** |
| 4 | Crude Oil (HS 2709) | 98/100 | 500K bbl/day | 500K bbl/day | Limited | *Export restrictions* |

### Key Markets by Commodity

**Refined Petroleum → Asia**
- India: +4% YoY petroleum demand
- Southeast Asia: Refinery shortfalls, import-dependent
- Demand for gasoline (HS 271012), diesel (HS 271019)

**LNG → Asia Pacific**
- Japan: 20% of global LNG market
- South Korea: Growing demand
- India: Emerging importer (+8% YoY growth)

**Thermal Coal → South Asia**
- India: Imports 75% of coal needs, +3.2% YoY growth
- Coal is 70% of India's electricity generation
- Trade margins: $17/ton (after $28/ton freight)

---

## 🔧 Installation & Usage

### 1. **Standalone Analysis Scripts**

```bash
# Create virtual environment
python3.11 -m venv ~/.venvs/trade-analysis
source ~/.venvs/trade-analysis/bin/activate
pip install pandas requests duckdb -q

# Run main export analyzer (uses EIA API + fallback data)
python3 us_trade_export_analyzer.py

# Run trade balance & port allocation analysis
python3 us_commodity_trade_balance.py
```

### 2. **FastAPI Integration**

Add to your main FastAPI app (`main.py`):

```python
from routers.us_trade_export_router import router as us_trade_router

app.include_router(us_trade_router)
```

Then restart your backend and access:

```bash
# Test the endpoints
curl http://localhost:8000/api/us-trade/opportunities
curl http://localhost:8000/api/us-trade/commodities
curl http://localhost:8000/api/us-trade/ports
curl http://localhost:8000/api/us-trade/margins?commodity=2710
curl http://localhost:8000/api/us-trade/refined-products
curl http://localhost:8000/api/us-trade/tariff-reference
curl http://localhost:8000/api/us-trade/summary
```

---

## 📡 API Endpoints Reference

### **GET `/api/us-trade/opportunities`**
Get top US export opportunities ranked by suitability and margin.

**Response:**
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
      "key_markets": ["India (+4% YoY demand)", "SE Asia (refinery shortfalls)"],
      "best_ports": ["Port of Houston", "Port of Beaumont"],
      "products": ["Gasoline (HS 271012)", "Diesel (HS 271019)"]
    }
  ]
}
```

---

### **GET `/api/us-trade/commodities`**
Get US trade balance and export potential by commodity.

**Query Params:**
- `commodity` (optional): Filter by commodity name (e.g., "Refined Petroleum (HS 2710)")

**Response:**
```json
{
  "commodities": [
    {
      "commodity": "Refined Petroleum (HS 2710)",
      "trade_position": "NET EXPORTER",
      "annual_trade_balance_usd": 75000000000,
      "margin_opportunity": "HIGH - Gasoline, Diesel, Jet Fuel",
      "details": { ... }
    }
  ]
}
```

---

### **GET `/api/us-trade/ports`**
Get US port specialization for energy commodity exports.

**Response:**
```json
{
  "ports": [
    {
      "port": "Port of Houston (TX)",
      "state": "TX",
      "specialization_score": 98,
      "primary_commodities": ["Crude Oil", "Refined Petroleum", "LNG", "Coke"],
      "export_capacity": {
        "crude_bpd": 500000,
        "refined_bpd": 3500000,
        "lng_bcf_day": 12,
        "coal_tons": 10000000
      },
      "key_terminals": ["Sabine Pass LNG", "Houston Ship Channel"]
    }
  ]
}
```

---

### **GET `/api/us-trade/margins?commodity=2710`**
Get export margins by destination region for a commodity.

**Query Params:**
- `commodity` (required): HS code or commodity name (2710, 271121, 2701)

**Response:**
```json
{
  "hs_code": "2710",
  "commodity": "Refined Petroleum",
  "margins_by_region": [
    {
      "destination": "Europe",
      "gross_margin": 18.0,
      "logistics_cost": 5.5,
      "net_margin": 12.5,
      "demand_forecast": "MEDIUM"
    },
    {
      "destination": "Asia",
      "gross_margin": 15.5,
      "logistics_cost": 3.2,
      "net_margin": 12.3,
      "demand_forecast": "HIGH (India, SE Asia)"
    }
  ]
}
```

---

### **GET `/api/us-trade/refined-products`**
Get HS code breakdown of US refined petroleum exports.

**Response:**
```json
{
  "hs_code_parent": "2710",
  "commodity": "Refined Petroleum",
  "total_export_bpd": 3500000,
  "products": [
    {
      "hs_code": "271012",
      "product_name": "Light oils & fractions (Gasoline/Naphtha)",
      "export_volume_bpd": 1225000,
      "percent_of_refined": "35%",
      "margin_rank": "#1",
      "key_markets": "Asia, Europe, Caribbean"
    },
    {
      "hs_code": "271019",
      "product_name": "Other petroleum oils (Diesel/Kerosene)",
      "export_volume_bpd": 875000,
      "percent_of_refined": "25%",
      "margin_rank": "#2",
      "key_markets": "Europe, Americas"
    }
  ]
}
```

---

### **GET `/api/us-trade/tariff-reference`**
Get HS codes and tariff duty information for energy commodities.

**Response:**
```json
{
  "system": "Harmonized System (HS) - Used for US imports/exports",
  "tariff_codes": {
    "2710": {
      "product": "Refined Petroleum",
      "duty_rate": "0%",
      "notes": "Highest export margin; gasoline/diesel prioritized"
    },
    "271012": {
      "product": "Light Oils (Gasoline)",
      "duty_rate": "0%",
      "notes": "Premium markets in Asia"
    },
    "271019": {
      "product": "Other Oils (Diesel/Kerosene)",
      "duty_rate": "0%",
      "notes": "Highest Asia demand"
    },
    "271121": {
      "product": "Liquefied Natural Gas (LNG)",
      "duty_rate": "0%",
      "notes": "5 operational terminals"
    }
  }
}
```

---

## 🎯 Strategic Recommendations

### **Refined Petroleum (HS 2710) Export Strategy**

**Current State:**
- 3.5M bbl/day exports (mostly to Caribbean, Mexico)
- 6-8% of global refined product market share
- $75B annual trade surplus

**Opportunity:**
- Shift 500K bbl/day additional exports to Asia (net +$2.7B/yr)
- Prioritize gasoline (HS 271012) & diesel (HS 271019) to India
- Target India's +4% YoY petroleum demand growth
- Use Port of Houston (capacity: 3.5M bbl/day) & Port of Beaumont (2M bbl/day)

**Margins:**
```
Asia:      $12-15/bbl net (after $3.20/bbl logistics)
Europe:    $12.50/bbl net (after $5.50/bbl logistics) - higher freight
Caribbean: $10.20/bbl net (after $1.80/bbl logistics) - existing strength
```

---

### **LNG (HS 271121) Export Strategy**

**Current State:**
- 12 BCF/day capacity (100% utilized)
- 15-20% of global LNG market
- 5 operational terminals (Sabine Pass, Freeport, Corpus Christi, Cameron, Brownsville)
- $50B annual trade surplus

**Opportunity:**
- Add 3 BCF/day capacity (15 BCF/day total) via Freeport expansion + new terminals
- Sell to Japan (20% of global demand), South Korea, India
- Freeport expansion (2.1 BCF/day additional) = +$4.8B/yr
- India LNG demand growing at +8% YoY (from coal-to-gas transition)

**Margins:**
```
Asia:      $1.70/MMBtu net (after $2.50/MMBtu shipping)
Europe:    $0.50/MMBtu net (after $3.00/MMBtu shipping) - long-haul penalty
Americas:  $1.30/MMBtu net (after $1.50/MMBtu shipping)
```

**Terminal Utilization:**
- Sabine Pass (Lamesa, LA): 3.8 BCF/day ✅ Full
- Freeport (TX): 2.1 BCF/day ✅ Full → Expansion underway (+1.5 BCF/day by 2027)
- Corpus Christi (TX): 1.4 BCF/day ✅ Full
- Cameron (LA): 2.2 BCF/day ✅ Full
- Brownsville (TX): 1.5 BCF/day ✅ Full

---

### **Thermal Coal (HS 2701) Export Strategy**

**Current State:**
- 50M tons/year exports (mostly to Asia)
- 2-3% of global coal market
- $8B annual trade surplus

**Opportunity:**
- Increase to 75M tons/year (+25M tons)
- India is largest opportunity (imports 75% of needs, +3.2% YoY growth)
- Coal = 70% of India electricity generation → structural demand
- Transition to Pacific ports (Los Angeles, Long Beach) for Asian markets

**Margins:**
```
Asia:      $17/ton net (after $28/ton shipping) ← Strong
Europe:    -$7/ton net (after $42/ton shipping) ← Loss on green transition
Americas:  $8/ton net (after $12/ton shipping) ← Weak domestic demand
```

**Port Strategy:**
- Port of Los Angeles: 15M tons/year coal capacity (Pacific advantage)
- Port of Long Beach: 12M tons/year coal capacity
- Coal export via Pacific cuts shipping time to India by 15-20 days vs Gulf ports

---

## 📈 Data Integration with Cassandra

Store export analytics in your existing Cassandra keyspace:

```sql
-- Add table to herrrickshaw keyspace
CREATE TABLE us_export_opportunities (
    commodity_name text,
    hs_code text,
    export_score int,
    current_exports float,
    export_potential float,
    margin_net float,
    annual_opportunity_usd bigint,
    analysis_date timestamp,
    PRIMARY KEY (commodity_name)
);

-- Insert from analysis
INSERT INTO us_export_opportunities 
VALUES ('Refined Petroleum', '2710', 88, 3500000, 4000000, 13.5, 2450000000, now());
```

---

## 🔄 EIA API Configuration

The analyzer uses **EIA API** for live commodity data. Your API key is stored in:

```
~/.config/market-secrets/credentials.env
EIA_API_KEY=your_eia_api_key_here
```

**Note:** Store your actual EIA API key in `~/.config/market-secrets/credentials.env` (mode 600). Never commit credentials to git.

**Fallback Data:**
If EIA API is unavailable, the system uses hardcoded Aug 2026 market data:
- WTI Crude: ~$75.50/bbl
- Refined Petroleum: 3.5M bbl/day
- Henry Hub NG: ~$3.20/MMBtu
- Thermal Coal: ~$55/ton

---

## 📊 Scoring Model

Export suitability is scored on **5 dimensions** (100-point scale):

1. **Market Position (30 pts)**: Global market share & US competitiveness
   - Very High (13%+): 30 pts
   - Medium-High (6-8%): 20 pts
   - Low: 10 pts

2. **Price Level (25 pts)**: Commodity price level & margin opportunity
   - High ($50+/unit): 25 pts
   - Medium ($20-50): 15 pts
   - Low: 5 pts

3. **Port Infrastructure (20 pts)**: Dedicated port capacity & specialization
   - 3+ major ports: 20 pts
   - 1-2 ports: 15 pts
   - Limited: 5 pts

4. **Transport Mode (15 pts)**: Logistics efficiency (tanker, bulk, container)
   - Tanker/Bulk optimized: 15 pts
   - Bulk: 14 pts
   - Container: 10 pts

5. **Export Reach (10 pts)**: Multi-region demand & liquidity
   - Multi-region: 8-10 pts
   - Single region: 5 pts

**Score Interpretation:**
- 85+: **Excellent** (pursue aggressively)
- 70-84: **Good** (develop strategy)
- 50-69: **Fair** (tactical opportunities)
- <50: **Poor** (not recommended)

---

## 📂 File Structure

```
/Users/umashankar/
├── us_trade_export_analyzer.py        # Main EIA API analyzer
├── us_commodity_trade_balance.py      # Trade balance & port strategy
├── routers/
│   └── us_trade_export_router.py      # FastAPI endpoints
├── data/
│   └── market_data.duckdb             # Cached analysis results
└── US_TRADE_EXPORT_README.md          # This file
```

---

## 🚀 Next Steps

1. **Integrate FastAPI router** into your backend (`main.py`)
2. **Add to daily dashboard** export opportunities & margins
3. **Monitor port utilization** via `/api/us-trade/ports` endpoint
4. **Track refined petroleum** exports by HS code (271012 vs 271019)
5. **Forecast LNG terminal** capacity utilization
6. **Analyze coal demand** from India's power generation growth

---

## 📞 Support

For questions on:
- **HS Codes**: See `/api/us-trade/tariff-reference`
- **Port capacity**: See `/api/us-trade/ports`
- **Margins**: See `/api/us-trade/margins?commodity=2710`
- **Trade balance**: See `/api/us-trade/commodities`

---

**Last Updated**: 2026-08-10  
**Data Source**: EIA API, US Census Bureau, FRED, Market data (2024 YTD)
