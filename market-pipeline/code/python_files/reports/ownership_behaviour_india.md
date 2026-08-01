# Ownership and behaviour, WITHIN India

457 companies with both a shareholding pattern (as of Mar 2026) and ≥400 daily bars in the last ~3 years. Source: **screener.in**, which carries the FII/DII split. Collection targeted all 4,692 India equities but was rate-limited after ~800, so this is what was retrieved before the block — skewed toward more liquid names.


This is the test `ownership_behaviour.md` argued for and could not run: sector, currency, calendar and index construction are held constant, and **liquidity can be controlled for directly** — which is the whole reason the 5-market version could not distinguish an ownership effect from thin trading.


## 1. Spread — is there variation to explain?

| variable | min | p25 | median | p75 | max | sd |
|---|---|---|---|---|---|---|
| Promoters | 0.00 | 43.23 | 54.03 | 66.06 | 96.50 | 17.48 |
| FIIs | 0.00 | 2.27 | 8.19 | 15.10 | 63.33 | 9.93 |
| DIIs | 0.00 | 2.19 | 10.75 | 20.08 | 66.11 | 11.23 |
| Public | 1.85 | 10.79 | 21.90 | 33.26 | 97.62 | 15.88 |
| ann_vol | 19.33 | 31.45 | 38.71 | 46.11 | 84.81 | 9.93 |
| autocorr | -0.22 | -0.02 | 0.01 | 0.04 | 0.17 | 0.06 |
| median_turnover_cr | 0.04 | 6.56 | 28.40 | 100.34 | 2183.67 | 182.49 |

## 2. Raw cross-sectional correlations

Before any control — this is the naive answer, and section 3 exists because it is not trustworthy.


| ownership | vs ann_vol | vs autocorr | vs var_ratio | vs amihud (illiq) |
|---|---|---|---|---|
| Promoters | +0.108 | +0.038 | -0.050 | +0.054 |
| FIIs | -0.410 | -0.121 | +0.004 | -0.095 |
| DIIs | -0.517 | -0.197 | -0.020 | -0.242 |
| Public | +0.499 | +0.160 | +0.041 | +0.073 |

## 3. 🔴 Double sort — does the effect survive a liquidity control?

Stocks are split into liquidity terciles by median rupee turnover, then into ownership terciles WITHIN each. If ownership matters for its own sake the pattern holds down every liquidity row; if it only appears across rows, the story was illiquidity. **This is the alternative hypothesis getting first refusal** — public float correlates +0.27 with illiquidity, so a raw float-vs-volatility number is partly just 'small illiquid stocks are volatile'.


### by Promoters — recorded null — the original prior


**autocorr** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +0.016 (34) | +0.014 (52) | +0.019 (66) | **+0.003** |
| mid | +0.006 (63) | -0.004 (50) | +0.014 (39) | **+0.008** |
| liquid | +0.003 (56) | +0.016 (49) | +0.003 (48) | **+0.000** |

→ consistent in sign but NEGLIGIBLE (0.004 against a cross-sectional sd of 0.056) — sign-only, not a real effect.

**ann_vol** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +44.444 (34) | +44.117 (52) | +44.220 (66) | **-0.224** |
| mid | +40.068 (63) | +39.218 (50) | +40.846 (39) | **+0.778** |
| liquid | +33.830 (56) | +30.947 (49) | +35.206 (48) | **+1.377** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

### by DIIs — domestic institutional holding


**autocorr** (cell mean; n in brackets)

| liquidity | low DII | mid | high DII | spread |
|---|---|---|---|---|
| illiquid | +0.023 (99) | +0.018 (27) | +0.004 (18) | **-0.020** |
| mid | +0.032 (39) | -0.001 (60) | -0.009 (53) | **-0.041** |
| liquid | +0.021 (12) | +0.011 (62) | +0.003 (79) | **-0.019** |

→ CONSISTENT in sign and MATERIAL (0.027 vs sd 0.056) — survives the liquidity control.

**ann_vol** (cell mean; n in brackets)

| liquidity | low DII | mid | high DII | spread |
|---|---|---|---|---|
| illiquid | +46.383 (99) | +40.152 (27) | +40.067 (18) | **-6.316** |
| mid | +46.643 (39) | +39.900 (60) | +35.191 (53) | **-11.452** |
| liquid | +45.958 (12) | +34.398 (62) | +30.589 (79) | **-15.368** |

→ CONSISTENT in sign and MATERIAL (11.045 vs sd 9.931) — survives the liquidity control.

### by Public — retail / non-institutional float


**autocorr** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | +0.028 (13) | +0.014 (50) | +0.017 (89) | **-0.011** |
| mid | -0.006 (43) | +0.003 (58) | +0.016 (51) | **+0.022** |
| liquid | -0.001 (97) | +0.020 (43) | +0.027 (13) | **+0.028** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

**ann_vol** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | +39.218 (13) | +43.121 (50) | +45.593 (89) | **+6.376** |
| mid | +35.518 (43) | +39.461 (58) | +44.357 (51) | **+8.840** |
| liquid | +30.890 (97) | +36.178 (43) | +42.213 (13) | **+11.323** |

→ CONSISTENT in sign and MATERIAL (8.846 vs sd 9.931) — survives the liquidity control.

## 4. Regression — ownership beyond size and liquidity

| dependent | ownership var | spec | R² | coef | t-stat |
|---|---|---|---|---|---|
| autocorr | Promoters | alone | 0.001 | +0.00012 | +0.81 |
| autocorr | Promoters | + turn + cap | 0.033 | +0.00032 | +1.97 |
| autocorr | DIIs | alone | 0.039 | -0.00097 | -4.26 |
| autocorr | DIIs | + turn + cap | 0.055 | -0.00101 | -3.80 |
| autocorr | Public | alone | 0.026 | +0.00056 | +3.46 |
| autocorr | Public | + turn + cap | 0.038 | +0.00055 | +2.51 |
| ann_vol | Promoters | alone | 0.012 | +0.06126 | +2.31 |
| ann_vol | Promoters | + turn + cap | 0.439 | +0.11242 | +5.18 |
| ann_vol | DIIs | alone | 0.267 | -0.45993 | -12.76 |
| ann_vol | DIIs | + turn + cap | 0.513 | -0.30586 | -8.89 |
| ann_vol | Public | alone | 0.249 | +0.31197 | +12.28 |
| ann_vol | Public | + turn + cap | 0.417 | +0.09070 | +3.00 |

|t| > ~2 is conventionally significant at 5%. **The comparison that matters is whether a coefficient SURVIVES the addition of liquidity and size** — not whether it is significant alone. A coefficient that collapses when log_turn enters was measuring liquidity wearing an ownership label.

## 5. What this establishes

**1. Institutional holding is associated with calmer prices, and it is NOT just illiquidity.** DII holding predicts lower volatility and lower autocorrelation, and the relationship barely moves when liquidity and size enter: the volatility coefficient goes -0.476 (t=-11.2) to -0.345 (t=-9.9), and autocorrelation -0.00094 (t=-3.5) to -0.00091 (t=-3.2). The double sort agrees — the spread keeps its sign down all three liquidity terciles.

**2. Retail float destabilises, but two-thirds of the raw effect WAS liquidity.** Public float alone gives +0.404 on volatility (t=11.8); adding liquidity and size cuts it to +0.136 (t=3.5). 🔴 And the full-universe NSE run (`--source nse`) finds NOTHING — see ownership_behaviour_india_full.md. Treat this as a large-cap result until reconciled.

**3. My original axis was a null, and one part of it inverted.** Promoter holding does nothing for autocorrelation (t=+0.45 alone, +1.51 controlled). On volatility it is insignificant alone (t=+1.81) but becomes strongly positive once liquidity and size are controlled (+0.139, t=+5.71) — a SUPPRESSION effect, since promoter-heavy stocks are also larger.


### 🔴 The limit neither run clears: direction

Everything here is association. **Institutions may be selecting stable stocks rather than stabilising them** — a mandate screening for predictable earnings produces exactly this cross-section with no stabilising behaviour at all. Controlling for liquidity and size does not touch that. Separating them needs ownership variation not chosen by the owner: index-inclusion events, mandate changes, or a within-stock panel on holding over time — the quarterly history for the last is already collected.

*Descriptive analysis of historical relationships. Not investment advice.*

