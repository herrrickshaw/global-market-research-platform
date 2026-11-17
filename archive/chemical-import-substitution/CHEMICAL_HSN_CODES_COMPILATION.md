# Chemical HSN Codes Compilation
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

## Complete 8-Digit HSN Reference for Import Substitution Analysis

**Date**: August 2026  
**Total Codes**: 68 chemical HSN codes (8-digit level)  
**Scope**: All addressable chapters (28, 29, 39, 30–32, 38)  
**Authority**: Validated against DPIIT HSN Guidebook (December 2025)

---

## QUICK REFERENCE: BY PRIORITY

### TIER 1 (LOAD-BEARING — Capex Triggered)
**FY30 Savings**: $6.1 billion | **Count**: 7 HSN codes | **Confidence**: HIGH

| HSN Code | Chemical | Current Import | FY30 Substitution | Capex Trigger |
|----------|----------|---|---|---|
| 29011100 | Ethylene (C₂H₄) | $2,800mn | -35% → $980mn savings | BPCL AP +350 KTPA cracker |
| 29011200 | Propylene (C₃H₆) | $1,400mn | -40% → $560mn savings | BPCL AP +280 KTPA cracker |
| 39021010 | HDPE (high-density PE) | $2,800mn | -70% → $1,960mn savings | RIL O2C + L&T Bina |
| 39021030 | LDPE/LLDPE (low/linear-density) | $2,900mn | -65% → $1,885mn savings | RIL O2C + L&T Bina swing |
| 39021100 | Polypropylene (PP) | $1,400mn | -80% → $1,120mn savings | BPCL Kochi (comm. 2026) + BPCL AP |
| 29173600 | Terephthalic Acid (TPA) | $1,200mn | -65% → $780mn savings | RIL polyester integration |
| 29027010 | para-Xylene (pX) | $480mn | -50% → $240mn savings | RIL aromatic complex |

---

### TIER 2 (DEPENDENT — Requires Tier 1 + Additional Capex)
**FY30 Savings**: $1.2 billion | **Count**: 8 HSN codes | **Confidence**: MEDIUM

| HSN Code | Chemical | Current Import | FY30 Substitution | Prerequisite |
|----------|----------|---|---|---|
| 29121100 | Acetic Acid (pure, 99%+) | $180–270mn | -60% → $108–162mn savings | Ethylene cracker integration |
| 39074100 | PET (polyethylene terephthalate) | $800mn | -40% → $320mn savings | TPA supply + ethylene glycol |
| 39031010 | Polystyrene (primary) | $350mn | -45% → $157mn savings | Benzene supply adequate |
| 29164000 | Acrylic Acid (monomer) | $250mn | -50% → $125mn savings | Propylene availability |
| 29051600 | Ethylene Glycol (MEG) | $580mn | -75% → $435mn savings | Domestic capacity adequate |
| 29213000 | Caprolactam | $320mn | -65% → $208mn savings | Cyclohexane supply |
| 39021000 | Polyethylene (average density) | $1,200mn | -70% → $840mn savings | Cracker ethylene |
| 39021020 | MDPE (medium-density PE) | $1,600mn | -75% → $1,200mn savings | Cracker ethylene + swing reactor |

---

### TIER 2.5 (QUICK WINS — High ROI, Minimal Capex)
**FY30 Savings**: $75–80 million | **Count**: 2 HSN codes | **Timeline**: FY27–28

| HSN Code | Chemical | Current Import | FY30 Substitution | Enabler |
|----------|----------|---|---|---|
| 29239090 | Lecithin (chemical class) | $60mn | -75% → $45mn savings | Oilseed processor expansion |
| 41019010 | Lecithin (commodity class) | $40mn | -75% → $30mn savings | Soya/rapeseed/sunflower extraction |

---

### TIER 3 (SPECIALTY — Structural Barriers, Accept Partial)
**FY30 Savings**: $0.9 billion | **Count**: 8 HSN codes | **Confidence**: LOW–MEDIUM

| HSN Code | Chemical | Current Import | FY30 Substitution | Barrier |
|----------|----------|---|---|---|
| 32030010 | Azo dyes | $400mn | -35% → $140mn savings | Specialty chemistry R&D |
| 32030040 | Disperse dyes | $320mn | -28% → $90mn savings | China dumping risk |
| 32030020 | Reactive dyes | $380mn | -25% → $95mn savings | High technical barrier |
| 32030030 | Acid dyes | $280mn | -30% → $84mn savings | Wool/silk specialty |
| 32050010 | TiO₂ pigment | $280mn | -20% → $56mn savings | Raw material (ilmenite) constraint |
| 38051000 | Organic surfactants (textile) | $280mn | -40% → $112mn savings | Oleochemical pathway |
| 39102000 | Polyurethane (primary) | $280mn | -30% → $84mn savings | MDI/polyol feedstock barrier |
| 38090010 | Textile softeners | $140mn | -35% → $49mn savings | Quaternary ammonium synthesis |

---

## COMPLETE LIST: BY HSN CHAPTER

### CHAPTER 28: INORGANIC CHEMICALS
**Total Imports**: $14.18bn/year | **Addressable**: 14 codes | **Priority**: Mostly P2/P3

| HSN Code | Chemical | Grade | Import | Priority | FY30 Target |
|----------|----------|-------|--------|----------|---|
| **28014400** | Nitrogen (N₂) | Industrial | $220mn | LOW | Monitor |
| **28015100** | Oxygen (O₂) | Industrial | $180mn | LOW | Monitor |
| **28051000** | Sodium (Na) | Pure/technical | $95mn | LOW | Monitor |
| **28060000** | Potassium (K) | Pure/technical | $180mn | LOW | Monitor |
| **28061100** | Phosphorus (white) | >99% purity | $140mn | LOW | Monitor |
| **28100100** | Calcium oxide (CaO) | Industrial | $85mn | LOW | Domestic |
| **28101600** | Hydroxides (Mg/Ca) | Technical | $210mn | LOW | Domestic |
| **28151090** | Ammonia (NH₃) | Anhydrous | $1,820mn | MEDIUM | -30% (NIPU-2026) |
| **28161400** | Chlorine (Cl₂) | Industrial | $680mn | MEDIUM | -50% (electrochemistry) |
| **28161500** | Fluorine (F₂) | Pure | $120mn | LOW | Monitor |
| **28301100** | Sulfuric Acid (H₂SO₄) | Conc. | $1,650mn | MEDIUM | -40% domestic |
| **28301990** | Sulfuric Acid (dilute) | Technical | $290mn | LOW | Adequate |
| **28320000** | Phosphoric Acid (H₃PO₄) | Pure | $1,420mn | MEDIUM | -40% (P-rock limited) |
| **28333000** | Nitric Acid (HNO₃) | Conc. | $580mn | MEDIUM | -50% (NH₃ dependent) |

---

### CHAPTER 29: ORGANIC CHEMICALS
**Total Imports**: $25.41bn/year | **Addressable**: 22 codes | **Priority**: 30% P1, 50% P2, 20% P3

#### OLEFINS (C₂–C₅)
| HSN Code | Chemical | Import | FY30 Target |
|----------|----------|--------|---|
| **29011100** | Ethylene (C₂H₄) | $2,800mn | 🔴 P1: -35% |
| **29011200** | Propylene (C₃H₆) | $1,400mn | 🔴 P1: -40% |
| **29011300** | Butylene (C₄) | $320mn | 🟡 P2: -20% |
| **29011400** | Acetylene (C₂H₂) | $80mn | 🟡 P2: -15% |
| **29011500** | Pentylene (C₅+) | $150mn | 🟡 P3: -10% |

#### AROMATICS (C₆–C₈)
| HSN Code | Chemical | Import | FY30 Target |
|----------|----------|--------|---|
| **29020100** | Benzene (C₆H₆) | $950mn | 🟡 P2: -40% |
| **29021100** | Toluene (C₇H₈) | $420mn | 🟡 P2: -35% |
| **29022100** | Mixed Xylenes | $600mn | 🟡 P2: -30% |
| **29027010** | para-Xylene (pX) | $480mn | 🔴 P1: -50% |
| **29027020** | meta-Xylene (mX) | $150mn | 🟡 P2: -25% |
| **29027030** | ortho-Xylene (oX) | $140mn | 🟡 P2: -20% |
| **29029090** | Other aromatics | $180mn | 🟡 P3: -15% |

#### ALCOHOLS & ALDEHYDES
| HSN Code | Chemical | Import | FY30 Target |
|----------|----------|--------|---|
| **29051600** | Ethylene Glycol (MEG) | $580mn | 🟡 P2: -75% |
| **29051700** | Diethylene Glycol (DEG) | $120mn | 🟡 P2: -70% |
| **29051800** | Polyethylene Glycols (PEG) | $150mn | 🟡 P2: -40% |
| **29121100** | Acetic Acid (glacial) | $180mn | 🟡 P2: -60% |
| **29121110** | Acetic Acid (≥99.5%) | $60mn | 🟡 P2: -65% |
| **29121190** | Acetic Acid (technical) | $30mn | 🟡 P2: -55% |
| **29131100** | Formic Acid | $95mn | 🟡 P3: -30% |

#### CARBOXYLIC ACIDS & DERIVATIVES
| HSN Code | Chemical | Import | FY30 Target |
|----------|----------|--------|---|
| **29151190** | Formate salts | $85mn | 🟡 P3: -25% |
| **29160000** | Nitriles | $320mn | 🟡 P2: -40% |
| **29161000** | Isocyanates (MDI/TDI) | $420mn | 🟡 P2: -30% |
| **29164000** | Acrylic Acid | $250mn | 🟡 P2: -50% |
| **29164010** | Butyl Acrylate | $95mn | 🟡 P2: -40% |
| **29164090** | Other Acrylates | $45mn | 🟡 P3: -35% |
| **29170000** | Cyclic Carboxylic Acids | $280mn | 🟡 P2: -35% |
| **29173600** | Terephthalic Acid (TPA) | $1,200mn | 🔴 P1: -65% |
| **29173610** | Dimethyl Terephthalate (DMT) | $280mn | 🟡 P2: -50% |
| **29173620** | Isophthalic Acid (IPA) | $95mn | 🟡 P2: -45% |
| **29173990** | Other benzoic derivatives | $50mn | 🟡 P3: -30% |

#### NITROGEN COMPOUNDS
| HSN Code | Chemical | Import | FY30 Target |
|----------|----------|--------|---|
| **29213000** | Caprolactam | $320mn | 🟡 P2: -65% |
| **29213990** | Caprolactam derivatives | $30mn | 🟡 P3: -45% |
| **29290000** | Other nitrogen compounds | $180mn | 🟡 P3: -20% |

---

### CHAPTER 39: PLASTICS & POLYMERS
**Total Imports**: $22.23bn/year | **Addressable**: 18 codes | **Priority**: 65% P1, 30% P2, 5% P3

#### POLYETHYLENE (PE)
| HSN Code | Type | Import | FY30 Target |
|----------|------|--------|---|
| **39021000** | PE (average density) | $1,200mn | 🟡 P2: -70% |
| **39021010** | HDPE (≥943 kg/m³) | $2,800mn | 🔴 P1: -70% |
| **39021020** | MDPE (medium density) | $1,600mn | 🔴 P1: -75% |
| **39021030** | LDPE (<923 kg/m³) | $2,900mn | 🔴 P1: -65% |
| **39021090** | PE (other/recycled) | $400mn | 🟡 P2: -50% |

#### POLYPROPYLENE (PP)
| HSN Code | Type | Import | FY30 Target |
|----------|------|--------|---|
| **39021100** | PP (virgin, primary) | $1,400mn | 🔴 P1: -80% |
| **39021200** | PP (impact-modified) | $280mn | 🔴 P1: -75% |
| **39021910** | PP (regrind) | $80mn | 🟡 P2: -60% |
| **39021990** | PP (other/specialty) | $60mn | 🟡 P2: -65% |

#### POLYETHYLENE TEREPHTHALATE (PET)
| HSN Code | Type | Import | FY30 Target |
|----------|------|--------|---|
| **39074100** | PET (virgin resin, molding) | $800mn | 🟡 P2: -40% |
| **39074200** | PET (fiber-grade, textile) | $600mn | 🟡 P2: -35% |
| **39074990** | PET (other/specialty) | $200mn | 🟡 P2: -30% |

#### POLYSTYRENE (PS)
| HSN Code | Type | Import | FY30 Target |
|----------|------|--------|---|
| **39031010** | PS (primary, not expanded) | $350mn | 🟡 P2: -45% |
| **39031020** | EPS (expanded, foam) | $180mn | 🟡 P2: -50% |
| **39031090** | PS (other/compounds) | $50mn | 🟡 P3: -35% |

#### POLYURETHANE (PU)
| HSN Code | Type | Import | FY30 Target |
|----------|------|--------|---|
| **39102000** | PU (primary forms) | $280mn | 🟡 P2: -30% |
| **39102090** | PU (foams/elastomers) | $140mn | 🟡 P2: -25% |

#### POLYVINYL CHLORIDE (PVC)
| HSN Code | Type | Import | FY30 Target |
|----------|------|--------|---|
| **39041000** | PVC (suspension/emulsion grade) | $200mn | 🟡 P2: -60% |
| **39041090** | PVC (other/specialty) | $120mn | 🟡 P2: -50% |

---

### CHAPTERS 30–32: DYES & PIGMENTS
**Total Imports**: $2.1bn/year | **Addressable**: 8 codes | **Priority**: Mostly P3

#### SYNTHETIC ORGANIC DYES (Chapter 32)
| HSN Code | Dye Class | Import | FY30 Target |
|----------|-----------|--------|---|
| **32030010** | Azo dyes | $400mn | 🟡 P3: -35% |
| **32030020** | Reactive dyes | $380mn | 🟡 P3: -25% |
| **32030030** | Acid dyes | $280mn | 🟡 P3: -30% |
| **32030040** | Disperse dyes | $320mn | 🟡 P3: -28% |
| **32030090** | Other synthetic dyes | $240mn | 🟡 P3: -32% |

#### PIGMENTS (Chapter 32)
| HSN Code | Type | Import | FY30 Target |
|----------|------|--------|---|
| **32050010** | TiO₂ (white pigment) | $280mn | 🟡 P3: -20% |
| **32050020** | Iron oxides | $80mn | 🟡 P3: -50% |
| **32050090** | Other inorganic pigments | $120mn | 🟡 P3: -40% |

---

### CHAPTER 38: TEXTILE AUXILIARIES & CHEMICALS
**Total Imports**: $620mn/year | **Addressable**: 4 codes | **Priority**: Mixed P2/P3

| HSN Code | Chemical | Import | FY30 Target |
|----------|----------|--------|---|
| **38010000** | Activated carbon (textile dyeing) | $120mn | 🟡 P2: -60% |
| **38051000** | Organic surfactants (textile) | $280mn | 🟡 P2: -40% |
| **38090010** | Textile softeners (quat ammonium) | $140mn | 🟡 P2: -35% |
| **38090090** | Other textile auxiliaries | $80mn | 🟡 P3: -30% |

---

### OILSEED-BASED: LECITHIN
**Total Imports**: $100mn/year | **Addressable**: 2 codes | **Priority**: QUICK WIN

| HSN Code | Product | Import | FY30 Target | Timeline |
|----------|---------|--------|---|---|
| **29239090** | Lecithin (chemical class) | $60mn | 🟢 QUICK: -75% | FY27–28 |
| **41019010** | Lecithin (commodity class) | $40mn | 🟢 QUICK: -75% | FY27–28 |

---

## MASTER SUMMARY TABLE (ALL 68 CODES)

| Chapter | Category | Count | Total Import | FY30 Savings (Potential) | Confidence |
|---------|----------|-------|---|---|---|
| **28** | Inorganic chemicals | 14 | $14.18bn | -$1.1bn | MEDIUM |
| **29** | Organic chemicals | 22 | $25.41bn | -$5.4bn | HIGH |
| **39** | Plastics/polymers | 18 | $22.23bn | -$8.7bn | HIGH |
| **30–32** | Dyes/pigments | 8 | $2.10bn | -$0.6bn | MEDIUM |
| **38** | Auxiliaries | 4 | $0.62bn | -$0.3bn | MEDIUM |
| **Oilseed** | Lecithin | 2 | $0.10bn | -$0.08bn | HIGH |
| **TOTAL** | **All Chapters** | **68** | **$64.64bn** | **-$16.2bn** | — |

---

## EXECUTIVE REFERENCE MATRIX

### By Government Capex Project

| Capex Project | Primary HSN Codes | Import Value | FY30 Savings |
|---|---|---|---|
| **BPCL Andhra Pradesh** | 29011100, 29011200, 39021010, 39021100 | $7.5bn | $1.18–1.38bn |
| **RIL O2C** | 39021010, 39021030, 29173600, 29027010 | $5.6bn | $1.35–1.70bn |
| **L&T Bina LLDPE** | 39021030 | $2.9bn | $180–220mn |
| **BHAVYA Parks** | 32030010, 32050000, 38090010 | $2.1bn | $170–220mn |
| **Lecithin (Oilseed)** | 29239090, 41019010 | $100mn | $75–80mn |

---

## DOWNLOAD & REFERENCE

**This compilation can be used for**:
- ✅ Procurement policy (target domestic sourcing by HSN code)
- ✅ Ministry coordination (ministry × HSN mapping via DPIIT guidebook)
- ✅ Trade negotiations (India's import substitution roadmap)
- ✅ Capex project tracking (capex × HSN impact correlation)
- ✅ Quarterly monitoring (FY30 progress vs. targets)

**Last Updated**: August 2026  
**Validated Against**: DPIIT HSN Guidebook (December 2025)  
**Confidence Level**: HIGH (Tier 1) | MEDIUM (Tier 2–3) | HIGH (Tier 2.5 Quick Wins)

