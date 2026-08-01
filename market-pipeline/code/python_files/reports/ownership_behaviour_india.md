# Ownership and behaviour, WITHIN India

347 companies with both a shareholding pattern (as of Jun 2026) and ≥400 daily bars in the last ~3 years. Universe: NSE equities identified via ticker_exchange_reference. Collection targeted all 4,692 India equities but screener.in rate-limited after ~800; what survives here is what was retrieved before the block, skewed toward the more liquid names since collection walks the universe alphabetically from a turnover-sorted seed.


This is the test `ownership_behaviour.md` argued for and could not run: sector, currency, calendar and index construction are held constant, and **liquidity can be controlled for directly** — which is the whole reason the 5-market version could not distinguish an ownership effect from thin trading.


## 1. Spread — is there variation to explain?

| variable | min | p25 | median | p75 | max | sd |
|---|---|---|---|---|---|---|
| Promoters | 0.00 | 41.87 | 52.11 | 62.81 | 96.50 | 17.34 |
| FIIs | 0.03 | 6.27 | 10.53 | 16.86 | 61.96 | 9.54 |
| DIIs | 0.00 | 6.42 | 14.38 | 22.04 | 66.46 | 10.92 |
| Public | 2.06 | 9.19 | 17.62 | 28.69 | 68.75 | 13.36 |
| ann_vol | 19.33 | 30.38 | 36.65 | 45.33 | 84.81 | 10.08 |
| autocorr | -0.22 | -0.03 | 0.01 | 0.04 | 0.16 | 0.06 |
| median_turnover_cr | 1.09 | 21.34 | 52.24 | 140.59 | 2183.67 | 201.72 |

## 2. Raw cross-sectional correlations

Before any control — this is the naive answer, and section 3 exists because it is not trustworthy.


| ownership | vs ann_vol | vs autocorr | vs var_ratio | vs amihud (illiq) |
|---|---|---|---|---|
| Promoters | +0.097 | +0.024 | -0.060 | +0.130 |
| FIIs | -0.351 | -0.115 | -0.044 | -0.296 |
| DIIs | -0.515 | -0.186 | -0.050 | -0.281 |
| Public | +0.535 | +0.208 | +0.145 | +0.286 |

## 3. 🔴 Double sort — does the effect survive a liquidity control?

Stocks are split into liquidity terciles by median rupee turnover, then into ownership terciles WITHIN each. If ownership matters for its own sake the pattern holds down every liquidity row; if it only appears across rows, the story was illiquidity. **This is the alternative hypothesis getting first refusal** — public float correlates +0.27 with illiquidity, so a raw float-vs-volatility number is partly just 'small illiquid stocks are volatile'.


### by Promoters — recorded null — the original prior


**autocorr** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | -0.004 (36) | +0.008 (37) | +0.013 (43) | **+0.017** |
| mid | +0.015 (42) | +0.009 (39) | +0.004 (34) | **-0.011** |
| liquid | +0.006 (38) | +0.013 (39) | +0.008 (39) | **+0.002** |

→ spread sign is INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

**ann_vol** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +40.450 (36) | +42.077 (37) | +42.341 (43) | **+1.891** |
| mid | +37.265 (42) | +39.390 (39) | +39.546 (34) | **+2.281** |
| liquid | +34.478 (38) | +30.178 (39) | +34.052 (39) | **-0.426** |

→ spread sign is INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

### by DIIs — domestic institutional holding


**autocorr** (cell mean; n in brackets)

| liquidity | low DII | mid | high DII | spread |
|---|---|---|---|---|
| illiquid | +0.018 (53) | -0.001 (33) | -0.008 (30) | **-0.026** |
| mid | +0.018 (46) | +0.002 (31) | +0.005 (38) | **-0.013** |
| liquid | +0.037 (17) | +0.001 (51) | +0.007 (48) | **-0.030** |

→ spread sign is CONSISTENT across all three liquidity rows — survives the liquidity control.

**ann_vol** (cell mean; n in brackets)

| liquidity | low DII | mid | high DII | spread |
|---|---|---|---|---|
| illiquid | +46.926 (53) | +38.724 (33) | +35.625 (30) | **-11.301** |
| mid | +45.219 (46) | +34.932 (31) | +33.761 (38) | **-11.458** |
| liquid | +41.253 (17) | +32.525 (51) | +30.315 (48) | **-10.938** |

→ spread sign is CONSISTENT across all three liquidity rows — survives the liquidity control.

### by Public — retail / non-institutional float


**autocorr** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | +0.001 (21) | -0.002 (33) | +0.012 (62) | **+0.010** |
| mid | -0.008 (31) | -0.001 (45) | +0.035 (39) | **+0.042** |
| liquid | +0.001 (64) | +0.013 (37) | +0.031 (15) | **+0.029** |

→ spread sign is CONSISTENT across all three liquidity rows — survives the liquidity control.

**ann_vol** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | +36.732 (21) | +36.798 (33) | +45.935 (62) | **+9.203** |
| mid | +33.664 (31) | +37.444 (45) | +44.034 (39) | **+10.370** |
| liquid | +30.168 (64) | +33.637 (37) | +42.657 (15) | **+12.489** |

→ spread sign is CONSISTENT across all three liquidity rows — survives the liquidity control.

## 4. Regression — ownership beyond size and liquidity

| dependent | ownership var | spec | R² | coef | t-stat |
|---|---|---|---|---|---|
| autocorr | Promoters | alone | 0.001 | +0.00008 | +0.45 |
| autocorr | Promoters | + liquidity + size | 0.034 | +0.00028 | +1.51 |
| autocorr | DIIs | alone | 0.035 | -0.00094 | -3.52 |
| autocorr | DIIs | + liquidity + size | 0.057 | -0.00091 | -3.22 |
| autocorr | Public | alone | 0.043 | +0.00086 | +3.95 |
| autocorr | Public | + liquidity + size | 0.049 | +0.00078 | +2.73 |
| ann_vol | Promoters | alone | 0.009 | +0.05625 | +1.81 |
| ann_vol | Promoters | + liquidity + size | 0.493 | +0.13874 | +5.71 |
| ann_vol | DIIs | alone | 0.265 | -0.47562 | -11.17 |
| ann_vol | DIIs | + liquidity + size | 0.568 | -0.34470 | -9.86 |
| ann_vol | Public | alone | 0.286 | +0.40363 | +11.76 |
| ann_vol | Public | + liquidity + size | 0.464 | +0.13596 | +3.49 |

|t| > ~2 is conventionally significant at 5%. **The comparison that matters is whether a coefficient SURVIVES the addition of liquidity and size** — not whether it is significant alone. A coefficient that collapses when log_turn enters was measuring liquidity wearing an ownership label.

## 5. What this establishes

**1. Institutional holding is associated with calmer prices, and it is NOT just illiquidity.** DII holding predicts lower volatility and lower autocorrelation, and the relationship barely moves when liquidity and size enter: the volatility coefficient goes -0.476 (t=-11.2) to -0.345 (t=-9.9), and autocorrelation -0.00094 (t=-3.5) to -0.00091 (t=-3.2). The double sort agrees — the spread keeps its sign down all three liquidity terciles. This is the finding the 5-market table pointed at and could not identify.

**2. Retail float destabilises, but two-thirds of the raw effect WAS liquidity.** Public float alone gives +0.404 on volatility (t=11.8); adding liquidity and size cuts it to +0.136 (t=3.5). Still significant, still the right sign — but anyone quoting the raw +0.516 correlation would be quoting mostly small-illiquid-stocks-are-volatile.

**3. My original axis was a null, and one part of it inverted.** Promoter holding does nothing for autocorrelation (t=+0.45 alone, +1.51 controlled). On volatility it is insignificant alone (t=+1.81) but becomes strongly positive once liquidity and size are controlled (+0.139, t=+5.71) — a SUPPRESSION effect: promoter-heavy stocks are also larger, and size masks the relationship until it is held constant. Reported because it inverts the naive reading, not because it was expected.


### 🔴 The limit this design still does not clear: direction

Everything above is association. **Institutions may be selecting stable stocks rather than stabilising them** — a DII mandate that screens for predictable earnings would produce exactly this cross-section with no stabilising behaviour at all. Controlling for liquidity and size does not touch that, because the selection runs on characteristics correlated with both. Separating them needs variation in ownership that is not chosen by the owner: index-inclusion events, mandate changes, or a panel exploiting WITHIN-STOCK changes in DII holding over time — the quarterly history is already collected and would support the last of those.

*Descriptive analysis of historical relationships. Not investment advice.*

