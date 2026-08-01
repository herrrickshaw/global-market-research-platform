# Ownership and behaviour, WITHIN India

738 companies with both a shareholding pattern (as of Mar 2026) and ≥400 daily bars in the last ~3 years. Source: **NSE corporate-share-holdings-master** — the exchange's own filing, covering the full equity universe. Carries promoter/public only, so this run says nothing about FII/DII holding; see ownership_behaviour_india.md for the screener.in run that does.


This is the test `ownership_behaviour.md` argued for and could not run: sector, currency, calendar and index construction are held constant, and **liquidity can be controlled for directly** — which is the whole reason the 5-market version could not distinguish an ownership effect from thin trading.


## 1. Spread — is there variation to explain?

| variable | min | p25 | median | p75 | max | sd |
|---|---|---|---|---|---|---|
| Promoters | 0.00 | 45.14 | 56.51 | 69.60 | 94.71 | 18.80 |
| Public | 5.29 | 30.36 | 43.31 | 54.73 | 100.00 | 18.75 |
| ann_vol | 18.61 | 34.71 | 41.54 | 48.61 | 96.80 | 10.17 |
| autocorr | -0.22 | -0.03 | 0.00 | 0.04 | 0.21 | 0.06 |
| median_turnover_cr | 0.02 | 1.37 | 7.82 | 28.86 | 2183.67 | 145.83 |

## 2. Raw cross-sectional correlations

Before any control — this is the naive answer, and section 3 exists because it is not trustworthy.


| ownership | vs ann_vol | vs autocorr | vs var_ratio | vs amihud (illiq) |
|---|---|---|---|---|
| Promoters | +0.038 | -0.001 | -0.050 | +0.031 |
| Public | -0.038 | +0.002 | +0.050 | -0.031 |

## 3. 🔴 Double sort — does the effect survive a liquidity control?

Stocks are split into liquidity terciles by median rupee turnover, then into ownership terciles WITHIN each. If ownership matters for its own sake the pattern holds down every liquidity row; if it only appears across rows, the story was illiquidity. **This is the alternative hypothesis getting first refusal** — public float correlates +0.27 with illiquidity, so a raw float-vs-volatility number is partly just 'small illiquid stocks are volatile'.


### by Promoters — recorded null — the original prior


**autocorr** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +0.011 (60) | -0.007 (79) | -0.001 (107) | **-0.012** |
| mid | +0.007 (78) | +0.005 (82) | +0.015 (86) | **+0.008** |
| liquid | +0.002 (108) | +0.015 (85) | +0.001 (53) | **-0.001** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

**ann_vol** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +48.068 (60) | +45.650 (79) | +44.282 (107) | **-3.786** |
| mid | +43.626 (78) | +42.143 (82) | +42.308 (86) | **-1.318** |
| liquid | +37.045 (108) | +36.671 (85) | +38.337 (53) | **+1.292** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

### by Public — retail / non-institutional float


**autocorr** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | -0.001 (107) | -0.008 (78) | +0.012 (61) | **+0.013** |
| mid | +0.015 (86) | +0.005 (82) | +0.007 (78) | **-0.008** |
| liquid | +0.001 (53) | +0.016 (86) | +0.001 (107) | **+0.000** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

**ann_vol** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | +44.282 (107) | +45.806 (78) | +47.828 (61) | **+3.546** |
| mid | +42.308 (86) | +42.143 (82) | +43.626 (78) | **+1.318** |
| liquid | +38.337 (53) | +36.737 (86) | +36.995 (107) | **-1.342** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

## 4. Regression — ownership beyond size and liquidity

| dependent | ownership var | spec | R² | coef | t-stat |
|---|---|---|---|---|---|
| autocorr | Promoters | alone | 0.000 | -0.00000 | -0.03 |
| autocorr | Promoters | + turn | 0.007 | +0.00006 | +0.47 |
| autocorr | Public | alone | 0.000 | +0.00001 | +0.05 |
| autocorr | Public | + turn | 0.007 | -0.00005 | -0.44 |
| ann_vol | Promoters | alone | 0.001 | +0.02044 | +1.03 |
| ann_vol | Promoters | + turn | 0.163 | -0.02844 | -1.52 |
| ann_vol | Public | alone | 0.001 | -0.02060 | -1.03 |
| ann_vol | Public | + turn | 0.163 | +0.02828 | +1.51 |

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

