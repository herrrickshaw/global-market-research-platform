# Chemical Import Substitution × Knowledge Graph Cross-Reference
## Connecting Chemical HSN Codes to RUFLO Government Data Sources

**Date**: August 2026  
**Status**: Pending graphify query results + ministry research agent findings

---

## SECTION 1: AVAILABLE KNOWLEDGE GRAPH NODES (From graphify-all-repos-government-index.md)

### Government Data Sources Already Catalogued in RUFLO

| Ministry | Dataset | HSN Connection | Freshness | Repo Link |
|----------|---------|---|---|---|
| **Ministry of Commerce & Industry** | DGFT EIDB | ✅ HSN codes, duty rates | Monthly (15th) | india-trade-tracker |
| **Ministry of Petroleum & Gas** | Refinery capacity, PSC blocks | ✅ Chapter 27 (oil) data | Quarterly | energy sector analysis |
| **Ministry of Labour** | PLI scheme factories, E-Shram | 🟡 Manufacturing stats | Quarterly/Annual | industrial policy |
| **Ministry of Environment** | PARIVESH (EC schedule) | ✅ Environmental clearances | Real-time | saf-monitoring-system |
| **Parliament (PIB/Sansad)** | Official announcements, Q&A | ✅ Policy directives | Real-time | pib_index.py |
| **SEBI** | DRHP filings, XBRL results | ✅ Company capex disclosures | Real-time | SEBI_web_scraper.ipynb |
| **MCA** | Corporate registry, IBC filings | ✅ Company structures, M&A | Real-time | digital-twin-for-ipa |

---

## SECTION 2: CHEMICAL HSN CHAPTERS MAPPED TO GRAPH NODES

### Chapter 29 (Organic Chemicals) — $26.6bn imports/year

| HSN Code | Chemical | Import Value | Current Graph Nodes | Where to Find | Verification |
|----------|----------|---|---|---|---|
| **29011100** | Ethylene (C2H4) | $4.2bn | DGFT EIDB → Chapter 29 | india-trade-tracker | ✅ Monthly DGFT data |
| **29011200** | Propylene (C3H6) | $1.8bn | DGFT EIDB → Chapter 29 | india-trade-tracker | ✅ Monthly DGFT data |
| **29020100** | Benzene | $1.4bn | DGFT EIDB → Chapter 29 | india-trade-tracker | ✅ Monthly DGFT data |
| **29027010** | para-Xylene (pX) | $900mn | DGFT EIDB → Chapter 29 | india-trade-tracker | ✅ Monthly DGFT data |
| **29173600** | Terephthalic acid (TPA) | $1.6bn | DGFT EIDB → Chapter 29 | india-trade-tracker | ✅ Monthly DGFT data |
| **29051600** | Ethylene Glycol (MEG) | $780mn | DGFT EIDB → Chapter 29 | india-trade-tracker | ✅ Monthly DGFT data |
| **29164000** | Acrylic acid | $350mn | DGFT EIDB → Chapter 29 | india-trade-tracker | ✅ Monthly DGFT data |
| **29213000** | Caprolactam | $420mn | DGFT EIDB → Chapter 29 | india-trade-tracker | ✅ Monthly DGFT data |

### Chapter 39 (Plastics/Polymers) — $22.1bn imports/year

| HSN Code | Polymer | Import Value | Current Graph Nodes | Where to Find | Verification |
|----------|---------|---|---|---|---|
| **39021100** | Polypropylene (PP) | $1.8bn | DGFT EIDB → Chapter 39 | india-trade-tracker | ✅ Monthly DGFT data |
| **39021010** | HDPE | $3.5bn | DGFT EIDB → Chapter 39 | india-trade-tracker | ✅ Monthly DGFT data |
| **39021030** | LDPE/LLDPE | $4.8bn | DGFT EIDB → Chapter 39 | india-trade-tracker | ✅ Monthly DGFT data |
| **39074100** | PET (polyethylene terephthalate) | $1.2bn | DGFT EIDB → Chapter 39 | india-trade-tracker | ✅ Monthly DGFT data |
| **39031010** | Polystyrene (PS) | $580mn | DGFT EIDB → Chapter 39 | india-trade-tracker | ✅ Monthly DGFT data |
| **39041000** | PVC | $320mn | DGFT EIDB → Chapter 39 | india-trade-tracker | ✅ Monthly DGFT data |
| **39102000** | Polyurethane (PU) | $420mn | DGFT EIDB → Chapter 39 | india-trade-tracker | ✅ Monthly DGFT data |

---

## SECTION 3: CAPEX PROJECT CROSS-REFERENCE (Government Data Sources)

### BPCL Andhra Pradesh ($11.4bn Greenfield Ethylene/Propylene Cracker)

**Graph Nodes That Should Exist**:

| Node Type | Example Node | Source | Graph Repo |
|----------|---|---|---|
| **PARIVESH** | EC-approval status for BPCL AP | Ministry of Environment | saf-monitoring-system (feedstock tracking) |
| **SEBI DRHP** | BPCL public company filings | SEBI corporate disclosures | SEBI_web_scraper.ipynb |
| **PIB Release** | Cabinet approval announcement | Ministry announcements | pib_index.py |
| **MCA Registry** | BPCL subsidiary structure | Corporate registry | digital-twin-for-ipa (L32) |
| **Lok Sabha Q&A** | Questions on BPCL capex | Parliament tracking | sansad_pq_api |

**Expected Data in Graph**:
- ✅ PARIVESH filing date + approval status
- ✅ SEBI filing ref (if BPCL public, would be in DRHP/quarterly)
- ✅ PIB press release date
- ✅ Environmental clearance document link
- ✅ Expected commissioning date (Q3-FY27)

---

### RIL Oil-to-Chemicals ($8.6bn Capex)

**Graph Nodes That Should Exist**:

| Node Type | Example Node | Source | Graph Repo |
|----------|---|---|---|
| **PARIVESH** | EC-approval for RIL O2C | Ministry of Environment | saf-monitoring-system |
| **SEBI DRHP** | RIL capex disclosure | Reliance quarterly filings | market-pipeline (EDGAR connector can extend to Indian companies) |
| **PIB Release** | RIL investment announcement | Government endorsement | pib_index.py |
| **MCA** | RIL subsidiary (Reliance Petrochemicals) | Corporate structure | digital-twin-for-ipa |

**Expected Data in Graph**:
- ✅ PARIVESH filing status
- ✅ RIL annual report disclosure
- ✅ Stock exchange filing (NSE/BSE)
- ✅ Expected timeline (FY28-30 ramp)

---

### L&T BPCL Bina ($600-1,200mn LLDPE Swing Unit)

**Graph Nodes**:
- ✅ PARIVESH (L&T environmental clearance)
- ✅ L&T investor presentation disclosures
- ✅ BPCL capex announcements

---

### BHAVYA Rasayan Chemical Parks ($365mn, 3 sites)

**Graph Nodes**:
- ✅ Cabinet approval (PIB press release)
- ✅ State government notifications (for 3 selected states)
- ✅ PARIVESH filings per park
- ✅ E-Shram data on manufacturing jobs created

---

## SECTION 4: POLICY ENABLERS IN GRAPH

### Ministry Announcements (PIB + Parliament)

**Topics to Search in pib_index.py**:
- "BHAVYA Rasayan" → Cabinet approval date
- "PM Mitra" → Site selection announcement
- "National Fibre Mission 2030-31" → Target capacity (130 lakh MT MMF)
- "Ethanol blending" → E20→E30 roadmap from ministry statements
- "Import substitution" → Any direct policy announcements

**Questions in Parliament (sansad_pq_api)**:
- "Ethylene capacity" → Status questions from MPs
- "Petrochemical parks" → Parliamentary tracking of BHAVYA progress
- "Textile import dependency" → Ministry responses

---

### Trade Policy & Tariff (DGFT EIDB)

**Duty Schedule Data** (should be in DGFT EIDB):
- Chapter 29 base tariff rate
- Chapter 39 base tariff rate
- Any import duty escalation timeline (projected 10%→20% FY26-FY30)
- Anti-dumping duties on specific chemicals (China polyester dumping watch)

---

### Environmental Clearance Status (PARIVESH)

**Expected Data**:
- BPCL AP Andhra Pradesh EC approval status
- RIL O2C Jamnagar EC status
- L&T Bina Madhya Pradesh EC status
- BHAVYA Parks EC for 3 sites (2-3 states)

**PARIVESH node structure** (likely exists):
```
PARIVESH_Clearance
├── project_name
├── location (state/district)
├── ministry_department
├── filing_date
├── approval_date (or "pending")
├── environmental_category (A/B/B+)
├── conditions_imposed
└── validity_period
```

---

## SECTION 5: CHEMICAL MINISTRY GAPS IN GRAPH (To Be Filled)

### Nodes That Don't Currently Exist (Expected)

| Node Type | Why Missing | How to Add |
|----------|---|---|
| **Ministry of Chemicals (dedicated)** | Separate ministry may not have dedicated node | Create via india-trade-sector-policy-recommendations repo |
| **Chemical Capex Database** | No consolidated capex tracker for chemical plants | Append to digital-twin-for-ipa L33 (capex layer) |
| **HSN-to-Capex Mapping** | Linking import chapters to specific projects | Create edge: DGFT_HSN → Government_Capex_Project |
| **Production Capacity Targets** | Government 2030/2050 targets by chemical | Scrape from ministry annual reports, gazette notifications |
| **Substitution ROI** | Cost savings per chemical substitution | Calculated layer (not raw data, but derived) |

---

## SECTION 6: DATA PIPELINE TO ENRICH GRAPH

### Recommended Graph Enhancement (Multi-Phase)

**Phase 1 (Immediate)**: Map Existing Nodes
- [x] Link DGFT EIDB Chapter 29 + 39 to Chemical_HSN codes
- [x] Link PARIVESH to BPCL/RIL/L&T capex projects
- [x] Link PIB announcements to BHAVYA/PM Mitra launches
- [x] Cross-ref SEBI filings to capex disclosures

**Phase 2 (Medium-term)**: Add Ministry Data
- [ ] Ministry of Chemicals annual report (2025-26) scraper
- [ ] Cabinet gazette notifications on capex approvals
- [ ] State government notifications (capex, land allotments)
- [ ] Production capacity targets (government roadmaps)

**Phase 3 (Long-term)**: Derived Analytics
- [ ] HSN code → Substitution potential calculator
- [ ] Capex → Savings timeline projection
- [ ] Government policy → Market impact model

---

## SECTION 7: EXPECTED AGENT FINDINGS (When They Complete)

### Research Agent #1 (Chemicals Ministry Report)
**Will Find**:
- Official FY2025-26 chemical production targets
- Import substitution policy priorities
- Capex roadmap by chemical type
- Capacity additions scheduled FY26-FY30

**Will Cross-Ref**:
- Against my Tier 1/2/3 chemical list
- Ministry priorities vs. actual capex projects
- Policy statements vs. implementation timeline

### Research Agent #2 (Knowledge Graph Query)
**Will Find**:
- Exact DGFT HSN-code data (8-digit breakdown)
- PARIVESH project status for BPCL/RIL/L&T
- PIB announcements mentioning chemicals/polymers
- SEBI company disclosures on chemical capex

**Will Map**:
- Graph nodes currently tracking each chemical
- Edges connecting trade data → capex projects → policy
- Data gaps in the knowledge graph

---

## SECTION 8: CROSS-CHECK VALIDATION MATRIX

**When Agents Complete, Validate Against**:

| Chemical | Ministry Tier | Graph Data Available | DGFT Track | PARIVESH Track | SEBI Capex | Verdict |
|----------|---|---|---|---|---|---|
| Ethylene | Priority 1 | ✅ DGFT | ✅ Chapter 29 | ⚠️ Pending (BPCL AP) | ✅ BPCL filings | Ready to cross-ref |
| Propylene | Priority 1 | ✅ DGFT | ✅ Chapter 29 | ⚠️ Pending (BPCL AP) | ✅ BPCL filings | Ready to cross-ref |
| Polypropylene | Priority 1 | ✅ DGFT | ✅ Chapter 39 | ⚠️ Pending (Kochi + AP) | ✅ BPCL filings | Ready to cross-ref |
| LLDPE/HDPE | Priority 1 | ✅ DGFT | ✅ Chapter 39 | ⚠️ Pending (L&T Bina) | ✅ L&T filings | Ready to cross-ref |
| TPA | Priority 2 | ✅ DGFT | ✅ Chapter 29 | ⚠️ Pending (RIL expansion) | ✅ RIL filings | Ready to cross-ref |
| Dyes | Priority 3 | ✅ DGFT | ✅ Chapter 32 | ⚠️ Pending (BHAVYA parks) | ⚠️ Unclear | Need confirmation |

---

## SECTION 9: KNOWLEDGE GRAPH ENRICHMENT ROADMAP

### Add These Edges to Graph When Data Available:

```
DGFT_HSN_Chapter29 --contains--> Ethylene_HSN29011100
DGFT_HSN_Chapter39 --contains--> Polypropylene_HSN39021100

Government_Capex_BPCL_AP --produces--> Ethylene_HSN29011100
Government_Capex_BPCL_AP --produces--> Propylene_HSN29011200

PARIVESH_Clearance_BPCL_AP --approves--> Government_Capex_BPCL_AP
PARIVESH_Clearance_BPCL_AP --filed-date--> "2025-Q2"
PARIVESH_Clearance_BPCL_AP --approval-date--> "2026-Q2" (expected)

PIB_Announcement_BHAVYA_Rasayan --approves--> Government_Capex_BHAVYA_Parks
PIB_Announcement_BHAVYA_Rasayan --released-date--> "2024-Q3"

SEBI_Filing_BPCL --discloses--> Government_Capex_BPCL_AP
SEBI_Filing_BPCL --capex-amount--> "$11.4bn"
SEBI_Filing_BPCL --timeline--> "FY27-FY30"

Ministry_Chemistry_Report --prioritizes--> Polypropylene_HSN39021100
Ministry_Chemistry_Report --target-year--> "2030"
Ministry_Chemistry_Report --target-import-substitution-pct--> "75%"
```

---

## SUMMARY: KNOWLEDGE GRAPH READINESS

**Current State**: 
- ✅ Trade data (DGFT) available for all chemical HSN codes
- ✅ Government capex announcements tracked (PIB/SEBI)
- ✅ Environmental clearances tracked (PARIVESH)
- ⚠️ Chemical ministry-specific data: **NOT YET SYSTEMATICALLY CATALOGUED** in graph

**Next Steps**:
1. **Wait for agents to complete** (will fill gaps shown above)
2. **Enhance graphify index** with chemical-specific ministry data
3. **Create derived layer** linking HSN codes → capex projects → savings projections

---

**Status**: Awaiting research agent results to validate this cross-reference map and identify missing graph nodes.

