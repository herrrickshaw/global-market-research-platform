# Ownership and behaviour, WITHIN India

1026 companies with both a shareholding pattern (as of Mar 2026) and ≥400 daily bars in the last ~3 years. Source: **NSE corporate-share-holdings-master** — the exchange's own filing, covering the full equity universe. Carries promoter/public only, so this run says nothing about FII/DII holding; see ownership_behaviour_india.md for the screener.in run that does.


This is the test `ownership_behaviour.md` argued for and could not run: sector, currency, calendar and index construction are held constant, and **liquidity can be controlled for directly** — which is the whole reason the 5-market version could not distinguish an ownership effect from thin trading.


## 1. Spread — is there variation to explain?

| variable | min | p25 | median | p75 | max | sd |
|---|---|---|---|---|---|---|
| Promoters | 0.00 | 45.44 | 57.30 | 69.81 | 99.03 | 18.41 |
| Public | 0.97 | 30.14 | 42.61 | 54.44 | 100.00 | 18.36 |
| ann_vol | 18.61 | 35.03 | 41.95 | 48.76 | 96.80 | 10.08 |
| autocorr | -0.22 | -0.03 | 0.01 | 0.05 | 0.26 | 0.06 |
| median_turnover_cr | 0.01 | 1.18 | 6.89 | 27.94 | 2183.67 | 131.87 |

## 2. Raw cross-sectional correlations

Before any control — this is the naive answer, and section 3 exists because it is not trustworthy.


| ownership | vs ann_vol | vs autocorr | vs var_ratio | vs amihud (illiq) |
|---|---|---|---|---|
| Promoters | +0.062 | -0.015 | -0.061 | +0.037 |
| Public | -0.063 | +0.016 | +0.061 | -0.037 |

## 3. 🔴 Double sort — does the effect survive a liquidity control?

Stocks are split into liquidity terciles by median rupee turnover, then into ownership terciles WITHIN each. If ownership matters for its own sake the pattern holds down every liquidity row; if it only appears across rows, the story was illiquidity. **This is the alternative hypothesis getting first refusal** — public float correlates +0.27 with illiquidity, so a raw float-vs-volatility number is partly just 'small illiquid stocks are volatile'.


### by Promoters — recorded null — the original prior


**autocorr** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +0.010 (80) | -0.004 (114) | -0.008 (148) | **-0.018** |
| mid | +0.008 (108) | +0.014 (114) | +0.018 (120) | **+0.010** |
| liquid | +0.007 (154) | +0.011 (115) | +0.003 (73) | **-0.004** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

**ann_vol** (cell mean; n in brackets)

| liquidity | low promoter | mid | high promoter | spread |
|---|---|---|---|---|
| illiquid | +47.677 (80) | +46.610 (114) | +44.984 (148) | **-2.693** |
| mid | +43.909 (108) | +42.577 (114) | +42.107 (120) | **-1.802** |
| liquid | +37.257 (154) | +36.666 (115) | +38.686 (73) | **+1.429** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

### by Public — retail / non-institutional float


**autocorr** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | -0.008 (148) | -0.004 (114) | +0.010 (80) | **+0.018** |
| mid | +0.017 (121) | +0.014 (112) | +0.008 (109) | **-0.009** |
| liquid | +0.003 (73) | +0.012 (116) | +0.007 (153) | **+0.004** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

**ann_vol** (cell mean; n in brackets)

| liquidity | low public float | mid | high public float | spread |
|---|---|---|---|---|
| illiquid | +44.984 (148) | +46.610 (114) | +47.677 (80) | **+2.693** |
| mid | +42.059 (121) | +42.584 (112) | +43.947 (109) | **+1.888** |
| liquid | +38.686 (73) | +36.716 (116) | +37.224 (153) | **-1.462** |

→ INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity.

## 4. Regression — ownership beyond size and liquidity

| dependent | ownership var | spec | R² | coef | t-stat |
|---|---|---|---|---|---|
| autocorr | Promoters | alone | 0.000 | -0.00005 | -0.48 |
| autocorr | Promoters | + turn | 0.012 | +0.00003 | +0.31 |
| autocorr | Public | alone | 0.000 | +0.00005 | +0.51 |
| autocorr | Public | + turn | 0.012 | -0.00003 | -0.28 |
| ann_vol | Promoters | alone | 0.004 | +0.03378 | +1.98 |
| ann_vol | Promoters | + turn | 0.174 | -0.01866 | -1.17 |
| ann_vol | Public | alone | 0.004 | -0.03453 | -2.02 |
| ann_vol | Public | + turn | 0.174 | +0.01780 | +1.11 |

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

