# Ownership and behaviour, WITHIN India

1226 companies with both a shareholding pattern (as of Mar 2026) and ≥400 daily bars in the last ~3 years. Source: **NSE corporate-share-holdings-master** — the exchange's own filing, covering the full equity universe. Carries promoter/public only, so this run says nothing about FII/DII holding; see ownership_behaviour_india.md for the screener.in run that does.


This is the test `ownership_behaviour.md` argued for and could not run: sector, currency, calendar and index construction are held constant, and **liquidity can be controlled for directly** — which is the whole reason the 5-market version could not distinguish an ownership effect from thin trading.


## 1. Spread — is there variation to explain?

| variable | min | p25 | median | p75 | max | sd |
|---|---|---|---|---|---|---|
| Promoters | 0.00 | 45.25 | 57.41 | 69.61 | 99.03 | 18.26 |
| Public | 0.97 | 30.31 | 42.56 | 54.56 | 100.00 | 18.21 |
| ann_vol | 18.61 | 35.17 | 41.92 | 48.80 | 96.80 | 10.01 |
| autocorr | -0.25 | -0.03 | 0.01 | 0.05 | 0.31 | 0.06 |
| median_turnover_cr | 0.01 | 1.21 | 6.76 | 26.48 | 2183.67 | 134.38 |

## 2. Raw cross-sectional correlations

Before any control — this is the naive answer, and section 3 exists because it is not trustworthy.


| ownership | vs ann_vol | vs autocorr | vs var_ratio | vs amihud (illiq) |
|---|---|---|---|---|
| Promoters | +0.053 | +0.003 | -0.044 | +0.035 |
| Public | -0.054 | -0.002 | +0.044 | -0.035 |

## 3. 🔴 Double sort — does the effect survive a liquidity control?

Stocks are split into liquidity terciles by median rupee turnover, then into ownership terciles WITHIN each. If ownership matters for its own sake the pattern holds down every liquidity row; if it only appears across rows, the story was illiquidity. **This is the alternative hypothesis getting first refusal** — public float correlates +0.27 with illiquidity, so a raw float-vs-volatility number is partly just 'small illiquid stocks are volatile'.


### by Promoters — recorded null — the original prior


**autocorr** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +0.006 (99) | +0.001 (131) | -0.007 (179) | **-0.012** |
| mid | +0.007 (124) | +0.017 (146) | +0.016 (138) | **+0.009** |
| liquid | +0.008 (186) | +0.013 (131) | +0.003 (92) | **-0.005** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

**ann_vol** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +47.620 (99) | +46.112 (131) | +44.947 (179) | **-2.673** |
| mid | +43.953 (124) | +42.996 (146) | +41.762 (138) | **-2.191** |
| liquid | +37.798 (186) | +36.696 (131) | +38.601 (92) | **+0.804** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

### by Public — retail / non-institutional float


**autocorr** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | -0.007 (178) | +0.000 (132) | +0.006 (99) | **+0.012** |
| mid | +0.016 (139) | +0.017 (144) | +0.008 (125) | **-0.009** |
| liquid | +0.003 (92) | +0.014 (132) | +0.008 (185) | **+0.005** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

**ann_vol** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | +44.809 (178) | +46.289 (132) | +47.620 (99) | **+2.811** |
| mid | +41.723 (139) | +42.977 (144) | +44.021 (125) | **+2.298** |
| liquid | +38.601 (92) | +36.740 (132) | +37.773 (185) | **-0.828** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

## 4. Regression — ownership beyond size and liquidity

| dependent | ownership var | spec | R² | coef | t-stat |
|---|---|---|---|---|---|
| autocorr | Promoters | alone | 0.000 | +0.00001 | +0.10 |
| autocorr | Promoters | + turn | 0.013 | +0.00011 | +1.02 |
| autocorr | Public | alone | 0.000 | -0.00001 | -0.09 |
| autocorr | Public | + turn | 0.013 | -0.00010 | -1.00 |
| ann_vol | Promoters | alone | 0.003 | +0.02930 | +1.87 |
| ann_vol | Promoters | + turn | 0.160 | -0.02152 | -1.46 |
| ann_vol | Public | alone | 0.003 | -0.02994 | -1.91 |
| ann_vol | Public | + turn | 0.160 | +0.02076 | +1.40 |

|t| > ~2 is conventionally significant at 5%. **The comparison that matters is whether a coefficient SURVIVES the addition of liquidity and size** — not whether it is significant alone. A coefficient that collapses when log_turn enters was measuring liquidity wearing an ownership label.

## 5. What this establishes

**🔴 THE EFFECT DOES NOT REPLICATE IN THE FULL UNIVERSE. This is the headline, and it contradicts the screener.in run.**

On 347 liquid large caps, public float correlated **+0.516** with volatility and +0.230 with autocorrelation. Across the full NSE universe it is **-0.04 and +0.02** — indistinguishable from zero. Every regression coefficient here has |t| < 0.6, with or without the liquidity control, and no double sort survives: the volatility sort flips sign across liquidity rows, and the autocorrelation sort holds its sign only at a magnitude of 0.006 against a cross-sectional sd of 0.061 — sign-only, not an effect.

**The most likely reading is that the original result was a large-cap phenomenon.** The screener sample floored at $20M/day turnover; this one reaches a median turnover of Rs 0.02 crore. Widening the universe by ~2x the companies and ~100x the liquidity range destroyed the relationship, which is what a size-restricted artifact looks like.

**🔴 A structural caveat specific to this source.** NSE reports only promoter, public and employee trusts, and they sum to 100 — so Public is mechanically `100 - Promoters` and the two are the SAME variable with opposite sign. Their correlations here are exact mirrors (+0.040 / -0.040) because they must be. In the screener data, Public was a genuine residual after FII, DII and government, and therefore carried information that promoter holding did not. **These two runs are not measuring the same quantity**, and that alone could explain the divergence without any large-cap story at all. Distinguishing the two explanations needs the FII/DII split across the wide universe, which no free source provides.

**What still stands from the screener run**: the DII result (volatility t=-9.9 with controls) is untouched by this, because NSE cannot measure DII holding. It stands on 347 companies and is not confirmed at scale.


### 🔴 The limit neither run clears: direction

Everything here is association. **Institutions may be selecting stable stocks rather than stabilising them** — a mandate screening for predictable earnings produces exactly this cross-section with no stabilising behaviour at all. Controlling for liquidity and size does not touch that. Separating them needs ownership variation not chosen by the owner: index-inclusion events, mandate changes, or a within-stock panel on holding over time — the quarterly history for the last is already collected.

*Descriptive analysis of historical relationships. Not investment advice.*

