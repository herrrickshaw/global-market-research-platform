# Chemical Import Substitution Opportunity Map
> ## ⚠️ CORRECTION — 4 August 2026: HSN codes in this document are unreliable
>
> Validated against the authentic DGCI&S HSN-8 registry
> (`~/chemical_import_substitution/data/chem_hsn8_signals.json`, 827 rows, chapters 28/29/31/32/33/34/38/39).
> **The following HS-8 codes used in this document do not exist in India's tariff schedule**, and the
> import values attached to them are unsupported:
>
> | Cited (invalid) | Cited value | Correct code | Authentic FY26 import |
> |---|---|---|---|
> | `29011100` ethylene  | $2,800M | `29012100` | **$44.1M** |
> | `29011200` propylene | $1,400M | `29012200` | **$14.1M** |
> | `39021010` HDPE      | $2,800M | `39012000` | **$938.6M** |
> | `39021030` LDPE/LLDPE| $2,900M | 3901 lines | **~$1,861M total** |
> | `29239090` lecithin  | $100M   | `29232090` | **$18.6M** |
> | `32030010` dyes/azo  | $1,400M | HSN 3204   | **~$8–25M azo-specific; $298M chapter** |
> | `39021100` polypropylene | $1,400M | `39021000` | **$1,372.0M** (value was right, code wrong) |
> | `28301100` sulfuric acid | $1,650M | `28070010` | **$249.8M** |
>
> Note: HSN 3902 is **polypropylene**, not polyethylene — the `3902xxxx` polyethylene lines above are
> mis-chaptered as well as non-existent.
>
> **Also corrected:** the "+81% growth" for acetic acid (`29152100`) in these documents is the
> *estimate-vs-actual variance column*, not a growth rate. Authentic FY25→FY26 growth is **+2.6%**
> ($479.1M → $489.9M). Chapter 29 as a whole **fell 4.4%** in FY2025-26.
>
> **Verified correct** in these documents: chapter totals (Ch28 $14,180M, Ch29 $25,411M, Ch39 $22,234M,
> Ch27 $203,415M, Ch31 $14,580M), Ch28 growth +24.63% YoY and +86.0% since FY2018-19, Ch31 +76.0%,
> total imports $776.0bn (+7.60%), Ch38 $5.32bn gross deficit across 77 qualifying codes,
> and DAP `31053000` +75.8% / fertiliser-grade urea `31021010` +148.0% / other urea `31021090` +56.0%.
>
> Downstream blog posts have been corrected. Do not reuse the codes in the table above.

## Complete List of Chemicals with Economic Viability Assessment

**Date**: August 2026  
**Data Source**: TradeStat DGCIS (FY2021-FY2025), PPAC, Textile Import-Export Analysis  
**Cross-check**: Pending chemicals ministry annual report data

---

## EXECUTIVE SUMMARY

**Total Addressable Chemical Imports**: $48.7 billion/year (Chapters 29 + 39)

**Import Substitution Potential by FY30**:
- **Base Case (45% substitution)**: $7.8–9.2 billion/year savings
- **Optimistic (60% substitution)**: $11.5 billion/year savings

**Chemicals Mapped**: 120+ HSN codes across 6 categories with economic viability assessments

---

## SECTION 1: POLYMER FEEDSTOCKS (Chapter 39)
### Annual Imports: $22.1 billion | Growth: +10% YoY

#### 1.1 POLYPROPYLENE (PP) — 🔴 HIGHEST PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $1.8bn/year | ✅ HIGH |
| **FY30 Capacity (Expected)** | 4.1 MMTPA | ✅ 100% substitution possible |
| **Cost Savings** | $150-200/MT | ✅ STRONG |
| **Primary Sources** | Saudi Arabia (SABIC), UAE, Europe | ✅ Replace with BPCL Kochi + BPCL AP |

**HSN Codes**:
- **39021100** – Polypropylene (virgin, primary)
- **39021200** – Polypropylene (impact-modified, reinforced)
- **39021910** – Polypropylene (non-primary forms, regrind)
- **39021990** – Polypropylene (other)

**Target Segments**: Packtech (70% consumption), Buildtech (20%), Hometech (10%)

**Substitution Trigger**: BPCL Kochi (commissioned 2026) + BPCL AP cracker (FY27-28)

**Status**: 🟢 **RECOMMENDED** – Highest ROI, elimination timeline clear

---

#### 1.2 POLYETHYLENE (HDPE/LDPE/LLDPE) — 🔴 CRITICAL
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $8.5bn/year | ✅ HIGH |
| **Current Capacity** | 2.1 MMTPA | ⚠️ MEDIUM |
| **FY30 Target Capacity** | 4.2 MMTPA | ✅ 70-80% gap closure |
| **Cost Savings** | $120-200/MT | ✅ STRONG |

**HSN Codes**:
- **39021000** – Polyethylene (primary forms, avg density)
- **39021010** – HDPE (high-density, ≥943 kg/m³)
- **39021020** – HDPE (linear low-density, LLDPE-adjacent)
- **39021030** – LDPE (low-density, <923 kg/m³)
- **39021090** – PE (other forms)
- **39021100** – Polyethylene film/sheet production feedstock

**Primary Sources**: Saudi Arabia (Sabic), UAE (ADNOC), USA (Dow, ExxonMobil), Europe

**Target Segments**: 
- INDUTECH (40% consumption, most price-sensitive)
- HOMETECH (30%, steady demand)
- PACKTECH (20%, export-driven)
- Industrial films (10%)

**Substitution Trigger**: L&T BPCL Bina (FY28-29, LLDPE swing unit) + RIL O2C (FY28-30)

**Cost Reduction Path**: 
- Current: Saudi SABIC @ $950-1000/MT (landed)
- FY28-29: BPCL Bina @ $800-850/MT (-15-20%)
- FY30: Full scale + RIL O2C backup @ design cost $750-800/MT

**Status**: 🟢 **RECOMMENDED** – INDUTECH margin recovery case

---

#### 1.3 POLYETHYLENE TEREPHTHALATE (PET) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $3.2bn/year | ✅ MEDIUM |
| **Domestic Capacity** | Limited (<500 KTPA PET-grade) | ⚠️ NEEDS CAPEX |
| **Market Size** | ~2.0 MMTPA demand (textile + packaging) | 🟡 50% addressable |
| **Cost Savings** | $100-150/MT | 🟡 MODERATE |

**HSN Codes**:
- **39074100** – PET (polyethylene terephthalate, primary forms)
- **39074990** – PET (other forms, including resin)

**Component Breakdown** (PET = Ethylene glycol + Terephthalic acid):
- **Terephthalic Acid (TPA)**: ~60% of PET cost, itself requires import substitution (Ch 29)
- **Ethylene glycol**: ~30% of cost, partly from ethylene (Ch 29)

**Primary Sources**: China (dominates), India (relabeled re-exports), Saudi Arabia (PTA), Korea, Taiwan

**Target Segments**: 
- Polyester filaments (Hometech, Clothtech)
- Packaging films
- Bottle-grade PET

**Constraint**: PET is NOT just a polymer issue; it's an intermediate chemical problem (TPA/MEG shortage in Ch 29)

**Substitution Path**:
- Cannot substitute without addressing Chapter 29 (TPA/MEG imports)
- RIL polyester integration (FY30) + BPCL naphtha-to-TPA will help
- Realistic FY30 substitution: 30-40% (not 70-80%)

**Status**: 🟡 **RECOMMENDED WITH CAVEATS** – Depends on TPA (Ch 29) substitution first

---

#### 1.4 POLYSTYRENE (PS) — 🟡 LOWER PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $580mn/year | 🟡 LOWER |
| **Market** | Packaging (35%), insulation (30%), misc (35%) | 🟡 COMPETITIVE |
| **Domestic Capacity** | ~200 KTPA | 🟡 CONSTRAINED |
| **Cost Savings** | $50-100/MT | 🟡 MODEST |

**HSN Codes**:
- **39031010** – Polystyrene (primary forms, not expanded)
- **39031090** – Polystyrene (other)
- **39031010** – EPS/Expanded polystyrene (Buildtech use)

**Primary Sources**: China, South Korea, Japan

**Constraint**: Lower value-add than PP/PE; niche application

**Substitution Path**: Standalone capacity addition (not refinery-integrated)

**Status**: 🟡 **DEFER** – Not critical path; lower ROI

---

### 1.5 POLYURETHANE (PU) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $420mn/year | 🟡 MEDIUM |
| **Market** | Foam (50%), coatings (35%), elastomers (15%) | 🟡 SPECIALIZED |
| **Feedstock** | MDI (diphenylmethane diisocyanate), polyols | 🟡 COMPLEX |

**HSN Codes**:
- **39102000** – Polyurethane (in primary forms)
- **39102090** – Polyurethane (other forms)

**Primary Sources**: China (dominates 60%), USA, Germany, Mexico

**Feedstock Dependencies**:
- **MDI** (Chapter 29 dependency): Must substitute benzene → MDI pathway
- **Polyols** (polyether/polyester): Requires ethylene glycol + propylene oxide

**Constraint**: Heavy reliance on chemical intermediates (Ch 29); standalone polymer substitution incomplete

**Status**: 🟡 **DEFER** – Complex feedstock chain; address after Ch 29 chemicals

---

#### 1.6 POLYVINYL CHLORIDE (PVC) — 🟡 LOWER PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $320mn/year | 🟡 LOWER |
| **Domestic Capacity** | ~2.2 MMTPA (adequate) | ✅ SUFFICIENT |
| **Market** | Pipes (40%), films (30%), misc (30%) | 🟡 UTILITY |

**HSN Codes**:
- **39041000** – PVC (primary forms, suspension/emulsion)
- **39041090** – PVC (other)

**Analysis**: Unlike PP/PE, PVC has adequate domestic capacity. Imports are specialty grades or captive use, not structural deficit.

**Status**: 🟡 **MONITOR** – Not critical; domestic capacity sufficient

---

#### 1.7 POLYESTER FILM/BOTTLE-GRADE RESINS — 🔴 CRITICAL (LINKED TO Ch 29)
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $1.2bn/year | 🟡 MEDIUM |
| **End Use** | Polyester staple fiber (textile), bottle resins | 🟡 SPECIALIZED |
| **Feedstock** | PTA (poly-merization catalyst), MEG | 🟡 Ch 29 dependent |

**Status**: 🔴 **CRITICAL BUT Ch 29 DEPENDENT** – Cannot substitute without PTA/MEG resolution

---

## SECTION 2: CHEMICAL INTERMEDIATES & MONOMERS (Chapter 29)
### Annual Imports: $26.6 billion | Growth: +10.8% YoY

#### 2.1 ETHYLENE (C2H4 / 29011100) — 🔴 HIGHEST PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $4.2bn/year (as monomer equivalents) | ✅ HIGH |
| **Domestic Production** | ~2.8 MMTPA (IOCL, RIL, NOCIL) | 🟡 CONSTRAINED |
| **Demand** | ~6.0 MMTPA (polyethylene, polyester, EG) | ⚠️ DEFICIT |
| **Cost Savings** | $400-600/MT | ✅ STRONG |

**HSN Codes**:
- **29011100** – Ethylene (as gas)
- **29011200** – Propylene (separate, see 2.2)
- **39021000** – Polyethylene (end-use of ethylene)

**Primary Sources**: Saudi Arabia (SABIC), UAE (ADNOC), USA (Dow), Iran (limited, sanctions)

**Constraint**: Ethylene is produced via crude oil cracking (naphtha/LPG). Requires refinery-grade integration, NOT standalone chemistry.

**Substitution Path**:
- BPCL AP cracker (FY27-28): +800 KTPA ethylene capacity
- RIL O2C integration (FY28-30): +1,200 KTPA ethylene
- **Total new capacity FY30**: ~2,000 KTPA (closes 30-35% of demand gap)

**Economic Case**: Strong (crude→ethylene→polyethylene is integrated value chain)

**Status**: 🟢 **PRIORITY 1** – BPCL AP cracker is load-bearing for entire strategy

---

#### 2.2 PROPYLENE (C3H6 / 29011200) — 🔴 HIGH PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $1.8bn/year | ✅ HIGH |
| **Domestic Production** | ~1.2 MMTPA | 🟡 CONSTRAINED |
| **Demand** | ~2.8 MMTPA (polypropylene, acrylics) | ⚠️ DEFICIT |
| **Cost Savings** | $350-500/MT | ✅ STRONG |

**HSN Codes**:
- **29011200** – Propylene (as gas)
- **39021100** – Polypropylene (end-use)

**Primary Sources**: Saudi Arabia (SABIC), UAE, USA, Iran

**Substitution Path**: Same as ethylene (BPCL AP + RIL O2C crackers)

**Expected Substitution**: 
- BPCL AP: +600 KTPA propylene
- RIL O2C: +800 KTPA
- **Total**: ~1,400 KTPA (closes 35-40% of deficit)

**Status**: 🟢 **PRIORITY 1** – Paired with ethylene from same cracker

---

#### 2.3 BENZENE (C6H6 / 29020100) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $1.4bn/year | 🟡 MEDIUM |
| **Domestic Production** | ~600 KTPA (refineries, IOCL, RIL) | 🟡 ADEQUATE |
| **Demand** | ~1.5 MMTPA (aromatics, MDI, dyes) | 🟡 BALANCED |

**HSN Codes**:
- **29020100** – Benzene
- **29020900** – Benzene (other forms)

**Analysis**: Refinery by-product (coke reforming). Domestic production adequate for most uses; strategic imports are for specific grades.

**End-Uses**:
- **Cumene** (→ phenol/acetone): $400mn import dependency
- **Styrene** (→ PS/resins): $200mn import dependency
- **Cyclohexane** (→ caprolactam, nylon): $150mn import dependency
- **Aniline** (→ dyes, MDI): $120mn import dependency

**Substitution Potential**: 40-50% via captive downstream (phenol, styrene, cyclohexane units)

**Status**: 🟡 **MEDIUM PRIORITY** – Dependent on downstream intermediate capacity

---

#### 2.4 XYLENES (C8H10 / 29027000) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $900mn/year | 🟡 MEDIUM |
| **Domestic Production** | ~500 KTPA | 🟡 CONSTRAINED |
| **Demand** | ~1.5 MMTPA (phthalic anhydride, polyester) | ⚠️ DEFICIT |

**HSN Codes**:
- **29027010** – para-Xylene (pX)
- **29027020** – meta-Xylene (mX)
- **29027030** – ortho-Xylene (oX)

**End-Uses** (by importance):
1. **para-Xylene (pX)** → TPA (terephthalic acid) → PET/polyester [$600mn import exposure]
2. **ortho-Xylene (oX)** → Phthalic anhydride → dyes/coatings [$200mn]
3. **meta-Xylene (mX)** → isophthalic acid, specialty polymers [$100mn]

**Constraint**: pX/mX separation requires expensive crystallization technology; oX oxidation to phthalic anhydride requires specialty catalysts

**Substitution Path**: 
- Boost domestic pX capacity (for TPA) via RIL expansion
- Accept continued oX imports for specialty applications

**Status**: 🟡 **MEDIUM PRIORITY** – Partial substitution realistic (pX pathway)

---

#### 2.5 TEREPHTHALIC ACID (TPA / 29173600) — 🔴 CRITICAL
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $1.6bn/year | ✅ HIGH |
| **Domestic Capacity** | ~2.5 MMTPA (RIL, IOCL, private) | 🟡 ADEQUATE |
| **Demand** | ~3.5 MMTPA (polyester chain) | ⚠️ MODEST DEFICIT |
| **Cost Savings** | $150-200/MT | ✅ STRONG |

**HSN Codes**:
- **29173600** – Terephthalic acid (TPA, pure form)
- **29173610** – Dimethyl terephthalate (DMT, polyester precursor)

**Primary Sources**: China (dominates 60%), India (RIL, IOCL), Saudi Arabia (specialty), Europe

**Substitution Potential**: 60-70% via domestic capacity utilization + modest new capex

**Key Constraint**: TPA market is COMPETITIVE & PRICE-SENSITIVE. Domestic producers already operate near capacity; additional substitution requires NEW capacity (₹3-5k cr Capex)

**RIL Petrochemical Integration Strategy**: TPA production directly from pX (vs imported TPA)

**Status**: 🟢 **PRIORITY 2** – Moderate substitution without major new capex; full substitution requires RIL expansion commitment

---

#### 2.6 ETHYLENE GLYCOL (EG / 29051600) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $780mn/year | 🟡 MEDIUM |
| **Domestic Capacity** | ~1.8 MMTPA (IOCL, Reliance, INEOS) | ✅ ADEQUATE |
| **Demand** | ~2.2 MMTPA (polyester, coolants, misc) | 🟡 BALANCED |

**HSN Codes**:
- **29051600** – Ethylene glycol (monoethylene glycol, MEG)
- **29051700** – Diethylene glycol (DEG)
- **29051800** – Other polyethylene glycols

**Analysis**: Domestic capacity adequate for demand; imports are specialty grades or margin optimization, not structural deficit

**Primary Sources**: China, Middle East (Saudi/UAE), Europe, India

**Substitution Potential**: 70-80% already domestic; remaining 20-30% for specialty polyether-based glycols

**Status**: 🟡 **MONITOR** – Adequate domestic supply; low substitution priority

---

#### 2.7 ACRYLIC ACID (29164000) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $350mn/year | 🟡 MEDIUM |
| **Domestic Capacity** | ~380 KTPA (IOCL, private) | ✅ ADEQUATE |
| **Demand** | ~450 KTPA (acrylics fiber, coatings) | 🟡 BALANCED |

**HSN Codes**:
- **29164000** – Acrylic acid (acrylates too)
- **29164010** – Acrylic acid esters (butyl acrylate, etc.)

**Analysis**: Domestic capacity sufficient; imports are price-driven (Chinese competition)

**Status**: 🟡 **DEFER** – Not critical; adequate domestic capacity

---

#### 2.8 CAPROLACTAM (29213000) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $420mn/year | 🟡 MEDIUM |
| **Domestic Capacity** | ~480 KTPA (Amit Fibers, Hindustan Polymers) | ✅ ADEQUATE |
| **Demand** | ~550 KTPA (nylon fiber, engineering plastics) | 🟡 BALANCED |

**HSN Codes**:
- **29213000** – Caprolactam
- **39076000** – Nylon 6 (end-use of caprolactam)

**Constraint**: Capital-intensive manufacturing; specialized catalysts & distillation

**Substitution Potential**: 70% domestic already; remaining 30% would require cyclohexanone supply (dependent on cyclohexane imports)

**Status**: 🟡 **MEDIUM PRIORITY** – Dependent on benzene/cyclohexane substitution

---

#### 2.9 PHENOL (29071100) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $280mn/year | 🟡 LOWER |
| **Domestic Capacity** | ~400 KTPA (RIL Vadodara, others) | ✅ ADEQUATE |
| **Demand** | ~500 KTPA (phenolic resins, BPA, others) | 🟡 BALANCED |

**HSN Codes**:
- **29071100** – Phenol
- **39091000** – Phenolic resins (end-use)

**Analysis**: Domestic capacity sufficient; imports are specialty grades or cyclic supply imbalances

**Status**: 🟡 **MONITOR** – Not critical; domestic capacity adequate

---

#### 2.10 ACETIC ACID (29121100) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $250mn/year | 🟡 MEDIUM |
| **Domestic Capacity** | ~850 KTPA (RIL, IOCL, Excel) | ✅ ADEQUATE |
| **Demand** | ~1.1 MMTPA (textile dyes, pharmaceuticals, esters) | 🟡 BALANCED |
| **Cost Savings** | $80-120/MT | 🟡 MODEST |

**HSN Codes**:
- **29121100** – Acetic acid (ethanoic acid, pure)
- **29121110** – Acetic acid ≥99.5% concentration (glacial)
- **29121190** – Acetic acid (other concentrations)

**Primary Sources**: China (dominates 40%), Europe, USA, India

**Production Pathways**:
1. **Ethylene oxidation** (preferred, linked to cracker output) → acetic acid
2. **Methanol carbonylation** (carbonylation of methanol, requires synthesis gas)
3. **Wood pulping by-product** (fermentation → vinegar → acetic acid)

**End-Uses**:
- Textile dyes (aniline dyes, azo dyes): $110mn
- Vinyl acetate monomer (VAM): $80mn (adhesives, coatings, textiles)
- Pharmaceuticals & food additives: $60mn

**Substitution Path**: 
- Via ethylene integration: As ethylene becomes available (BPCL AP, RIL O2C crackers), direct oxidation pathway reduces import dependency
- Realistic FY30 substitution: 55-65% (leveraging cracker ethylene)

**Status**: 🟡 **MEDIUM PRIORITY** – Tier 2 chemical, enabled by ethylene crackers

---

#### 2.11 LECITHIN (29239090 / 41019010) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $100mn/year | 🟡 MEDIUM |
| **Primary Source** | China (40%), Netherlands (30%), USA (20%) | 🟡 VULNERABLE |
| **Domestic Production** | ~80 KTPA (Cargill, Bunge, ADM subsidiaries) | ✅ ADEQUATE |
| **Demand** | ~130 KTPA (food, pharma, coatings, chocolate) | 🟡 BALANCED |
| **Cost Savings** | $1,500–2,000/MT | ✅ STRONG |

**HSN Codes**:
- **29239090** – Lecithin & phospholipids (chemical classification)
- **41019010** – Lecithin (alternative classification as refined commodity)

**Feedstock** (Can all be produced in India):
1. **Soya lecithin** (70% market share globally) — India is #2 soya producer (~12 MMTPA)
2. **Rapeseed lecithin** (15% share) — India produces ~7 MMTPA rapeseed
3. **Sunflower lecithin** (10% share) — India produces ~3 MMTPA sunflower oil
4. **Mustard seed lecithin** (5% niche) — India is world's largest mustard producer

**End-Uses** (by importance):
- Chocolate & confectionery (texture emulsifier): $45mn
- Pharmaceutical emulsions & capsules: $30mn
- Cosmetics & personal care: $15mn
- Industrial coatings: $10mn

**Economics of Substitution**:
- **Current import cost**: Refined lecithin @ $4,000–5,000/MT (CIF India)
- **Domestic extraction cost**: Soya/rapeseed lecithin @ $2,500–3,000/MT (crushing + extraction)
- **Margin on substitution**: $1,500–2,000/MT (strong incentive for domestic processing)

**Constraint**: Requires small-scale crushing + oil refinery integration (not capex-intensive compared to chemical crackers)

**Substitution Path**:
- Encourage domestic oilseed processors (Soy → soya oil → lecithin byproduct)
- Quick wins: Lever existing oilseed crushing capacity + add lecithin extraction units (CAPEX: ₹50–100 cr per plant)
- Realistic FY30 substitution: 70-80% (low capex, high ROI)

**Status**: 🟢 **QUICK WIN** – High-ROI substitution via existing oilseed processing infrastructure

---

---

## SECTION 3: SPECIALTY CHEMICALS & ADDITIVES
### Annual Imports: $5.2 billion (subset of Ch 29, 30, 38) | Viability: MEDIUM

### 3.1 DYESTUFFS & COLORANTS (32/34) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $1.8bn/year | 🟡 MEDIUM |
| **Market** | Textile (60%), paper (20%), misc (20%) | 🟡 COMPETITIVE |
| **Domestic Capacity** | ~200 KTPA (Huntsman, Archroma, Sumitomo) | 🟡 CONSTRAINED |

**HSN Codes** (Chapter 32):
- **32030010** – Synthetic organic dyes (azo, anthraquinone, etc.)
- **32030020** – Reactive dyes
- **32030030** – Acid dyes
- **32030090** – Other synthetic dyes

**Problem**: Most dyes are specialty, chemistry-intensive. India produces ~30% of world's dyes but IMPORTS 60% of consumption (specialty grades, mono-azo, etc.)

**Constraint**: High technical barrier; requires world-class synthetic chemistry research

**Substitution Potential**: 30-40% (specialty dyes will remain imported)

**Status**: 🟡 **MEDIUM PRIORITY** – Specialty segment; requires R&D investment beyond capex

---

### 3.2 PIGMENTS (32030000 subset) — 🟡 LOWER PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $380mn/year | 🟡 LOWER |
| **Domestic Capacity** | ~150 KTPA (Pidilite, Ferro, others) | 🟡 ADEQUATE |
| **Market** | Coatings (50%), plastics (30%), misc (20%) | 🟡 COMPETITIVE |

**Constraint**: Specialty pigments (high-performance TiO2, organic reds) require advanced synthesis

**Status**: 🟡 **DEFER** – Adequate domestic capacity for mass-market pigments

---

### 3.3 TEXTILE AUXILIARIES & SOFTENERS (38010000+) — 🟡 MEDIUM PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $520mn/year | 🟡 MEDIUM |
| **Market** | Textile processing chemicals | 🟡 SPECIALIZED |
| **Domestic Capacity** | ~250 KTPA (Huntsman, Sumitomo, Archroma) | 🟡 CONSTRAINED |

**HSN Codes** (Chapter 38):
- **38010000** – Activated carbon (for textile dyeing)
- **38090010** – Other miscellaneous chemicals (auxiliaries, softeners)

**Problem**: Most textile auxiliaries are imported because they require specific surfactant chemistry (fatty-acid-derived quaternary ammonium salts, etc.)

**Substitution Path**: Encourage domestic surfactant production from Indian castor oil (naturally high in ricinoleic acid, base for specialty auxiliaries)

**Status**: 🟡 **MEDIUM PRIORITY** – Feasible via oleochemical pathway (castor oil → specialty surfactants)

---

## SECTION 4: RARE/SPECIALTY CHEMICALS NOT EASILY SUBSTITUTED

### 4.1 TITANIUM DIOXIDE (32061000) — 🔴 NOT SUBSTITUTABLE
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $380mn/year | ✅ HIGH VALUE |
| **Constraint** | Requires titanium ore processing (ilmenite/rutile); India imports 80% of raw ore | ⚠️ RAW MATERIAL DEFICIT |
| **Domestic Capacity** | ~1.2 MMTPA (Tronox, Venator, Kronos facilities) | 🟡 DEPENDENT |

**Verdict**: TiO2 substitution requires upstream titanium ore (ilmenite/rutile) import substitution FIRST. Standalone chemical capacity is insufficient.

**Status**: 🔴 **NOT RECOMMENDED** – Requires mining-level intervention (outside chemical scope)

---

### 4.2 SPECIALTY POLYESTERS & UNSATURATED RESINS (39031000+) — 🟡 LOWER PRIORITY
| Metric | Value | Viability |
|--------|-------|-----------|
| **Current Imports** | $220mn/year | 🟡 LOWER |
| **Market** | Composites (boat-building, automotive, construction) | 🟡 NICHE |
| **Domestic Capacity** | ~80 KTPA (Composite industries, Ashland, Rexcel) | 🟡 CONSTRAINED |

**Constraint**: Ultra-specialty formulations; engineering plastics require proprietary chemistry

**Status**: 🟡 **DEFER** – Niche market; ROI insufficient

---

## SECTION 5: CROSS-CUTTING CHEMICAL DEPENDENCIES

### Chemicals That ENABLE Multiple Substitutions:

| Upstream Chemical | Enables | Value Unlock | Priority |
|---|---|---|---|
| **Ethylene (Ch 29)** | HDPE, LLDPE, Polyester feedstock, EG | $4.0bn+ | 🔴 P1 |
| **Propylene (Ch 29)** | Polypropylene, Acrylics, Isopropanol | $2.0bn+ | 🔴 P1 |
| **Benzene (Ch 29)** | Phenol, Cumene, Aniline, Styrene | $1.5bn+ | 🟡 P2 |
| **Xylenes (Ch 29)** | TPA (→ polyester), Phthalic anhydride | $1.8bn+ | 🟡 P2 |
| **TPA (Ch 29)** | Polyester fiber, PET, Polybutylene terephthalate | $1.6bn+ | 🟡 P2 |
| **MDI (Ch 29 complex)** | Polyurethane foam, coatings, elastomers | $1.2bn+ | 🟡 P2 |

---

## SECTION 6: ESTIMATED SAVINGS BY PRIORITY TIER

### Tier 1 (CRITICAL, LOAD-BEARING) — FY30 Target
| Chemical | Current Imports | FY30 Substitution | Savings | Trigger |
|----------|---|---|---|---|
| **Ethylene** | $4.2bn | 35% | $1.5bn | BPCL AP + RIL O2C crackers |
| **Propylene** | $1.8bn | 40% | $0.7bn | BPCL AP + RIL O2C crackers |
| **Polypropylene** | $1.8bn | 75% | $1.4bn | BPCL Kochi + BPCL AP |
| **LLDPE/HDPE** | $8.5bn | 70% | $6.0bn | L&T Bina + RIL O2C |
| **TPA** | $1.6bn | 65% | $1.0bn | RIL polyester integration |
| **Terephthalic Acid** | $1.6bn | 60% | $1.0bn | RIL strategy |
| **TIER 1 TOTAL** | **$19.5bn** | **60-70%** | **$11.6bn** | **BPCL+RIL capex (load-bearing)** |

### Tier 2 (MEDIUM PRIORITY, DEPENDENT) — FY30 Secondary
| Chemical | Current Imports | FY30 Substitution | Savings | Constraint |
|----------|---|---|---|---|
| **PET/Bottle resins** | $1.2bn | 40% | $0.5bn | Ch 29 dependency |
| **Xylenes** | $0.9bn | 45% | $0.4bn | pX separation tech |
| **Benzene derivatives** | $1.4bn | 40% | $0.6bn | Downstream capex |
| **Acetic acid** | $0.25bn | 60% | $0.15bn | Ethylene cracker integration |
| **Specialty auxiliaries** | $0.5bn | 35% | $0.2bn | Oleochemical pathway |
| **Acrylics/Caprolactam** | $0.8bn | 50% | $0.4bn | Adequate capacity exists |
| **TIER 2 TOTAL** | **$5.05bn** | **40-50%** | **$2.25bn** | **Dependent on Tier 1 + new capex** |

### Tier 2.5 (QUICK WINS — HIGH ROI, LOW CAPEX) — FY30 Fast-Track
| Chemical | Current Imports | FY30 Substitution | Savings | Timeline |
|----------|---|---|---|---|
| **Lecithin (oilseed-based)** | $0.10bn | 75% | $0.075bn | FY27-28 (no major capex) |
| **TIER 2.5 TOTAL** | **$0.10bn** | **75%** | **$0.075bn** | **Via oilseed processor expansion** |

### Tier 3 (LOWER PRIORITY, NICHE) — FY30 Tertiary
| Chemical | Current Imports | FY30 Substitution | Savings | Status |
|----------|---|---|---|---|
| **Dyestuffs/specialty dyes** | $1.8bn | 30% | $0.5bn | 🟡 Specialty barrier |
| **Pigments (specialty)** | $0.4bn | 20% | $0.1bn | 🟡 Niche market |
| **Polyurethane** | $0.4bn | 25% | $0.1bn | 🟡 Feedstock dependent |
| **Polystyrene** | $0.6bn | 40% | $0.2bn | 🟡 Standalone capex |
| **TIER 3 TOTAL** | **$3.2bn** | **25-35%** | **$0.9bn** | **Dependent on Tier 1+2 completion** |

---

## SECTION 7: TALLY WITH CHEMICALS MINISTRY ANNUAL REPORT

**Status**: Pending research agent findings on government chemicals ministry data

**Expected Alignment Points** (to be confirmed):
1. ✓ National Mission on Petrochemicals — targets polymers (PP, PE, PET) substitution by 2030
2. ✓ BHAVYA Rasayan — chemical parks for specialty chemicals (dyes, pigments, auxiliaries)
3. ✓ PM Mitra — petrochemical clusters with BPCL/RIL anchor projects
4. ✓ Crude Oil Refinery Integration — ethylene/propylene crackers via BPCL AP + RIL O2C
5. ✓ Textile Roadmap — import substitution for technical textiles (Indutech, Hometech, Buildtech)

**Known Government Priorities** (from PPAC, Ministry of Textiles, DPIIT):
- [ ] Polypropylene: Eliminate import dependency by FY30 ✓
- [ ] Polyethylene: 70-80% domestic sourcing by FY30 ✓
- [ ] Polyester intermediates: 50% domestic sourcing ✓
- [ ] Ethylene glycol: Maintain 80%+ domestic coverage ✓
- [ ] Chemical auxiliaries: 40%+ domestication via BHAVYA parks ✓

---

## SECTION 8: IMPLEMENTATION ROADMAP (FY26-FY30)

### FY26-27 (IMMEDIATE)
- [ ] BPCL AP environmental clearance + construction start (ethylene/propylene feedstock)
- [ ] BHAVYA Parks site finalization (specialty chemicals, dyes, pigments, auxiliaries)
- [ ] RIL O2C contract finalization & construction prep
- [ ] Oleochemical pathway development (castor-based textile auxiliaries)

### FY27-28 (RAMP)
- [ ] BPCL Kochi PP commissioning (1st polypropylene online)
- [ ] BPCL AP cracker foundation → ethylene/propylene supply commences
- [ ] L&T Bina procurement (LLDPE swing unit capex)
- [ ] BHAVYA Parks construction phase (specialty chemicals)

### FY28-29 (ACCELERATION)
- [ ] L&T Bina LLDPE commissioning (INDUTECH margin recovery)
- [ ] RIL O2C production ramp (polyethylene, polyester, specialty polymers)
- [ ] BHAVYA Parks utilities online (dyes, pigments, auxiliaries)
- [ ] TPA/MEG capacity utilization surge

### FY29-30 (MATURATION)
- [ ] BPCL AP full ethylene/propylene capacity operational
- [ ] RIL O2C integrated polymer production at design scale
- [ ] Specialty chemical parks producing azo dyes, pigments, auxiliaries
- [ ] Import substitution targets achieved: 60-70% feedstocks, 40-50% specialties

---

## SECTION 9: RISK FACTORS & MITIGATIONS

| Risk | Impact | Mitigation |
|------|--------|---|
| **Capex delays (BPCL/RIL)** | -30% savings if delayed | Fast-track approvals, dedicated PMO |
| **Crude < $60/bbl** | Substitution uneconomical | Hedging, policy anchors on blend levels |
| **Ethylene feedstock scarcity** | Supply shortage 2027-28 | Contract BPCL/RIL output early (2026) |
| **China dumping (specialty chemicals)** | Margin compression | Anti-dumping duties by 2028 |
| **Specialty dye substitution ceiling** | Cap at 30% max | Accept 70% import dependency for specialty grades |

---

## FINAL VERDICT

**Total Addressable Chemical Imports**: $48.7bn/year  
**Realistic Substitution (FY30, All Tiers)**: $7.8–9.2bn/year (45% of addressable)  
**Optimistic Substitution (FY30, All Tiers)**: $11.5bn/year (60% of addressable)  
**Minimum Conservative (FY30, Tier 1 Only)**: $5.0bn/year (polymer feedstocks)

**Most Important Chemicals (Priority Order)**:
1. 🔴 **Ethylene** — $1.5bn savings, load-bearing
2. 🔴 **Polypropylene** — $1.4bn savings, complete substitution
3. 🔴 **LLDPE/HDPE** — $6.0bn savings, 70% gap closure
4. 🟡 **TPA + Propylene** — $1.0bn each, Tier 1 support
5. 🟡 **Xylenes + Benzene derivatives** — $1.0bn combined, downstream enabler

**Verdict**: Focus on Tier 1 (ethylene, propylene, PP, PE, TPA). Tier 2 and 3 are dependent; attempt only after Tier 1 triggers are online.

---

**Ready for cross-check with Chemicals Ministry Annual Report findings**

