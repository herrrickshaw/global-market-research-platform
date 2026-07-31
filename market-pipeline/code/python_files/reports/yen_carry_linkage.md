# The yen carry channel — testing what the domestic-funding proxy missed

USD/JPY, Nikkei 225 and S&P 500, 1996-11-01 .. 2026-08-01 (7,703 aligned sessions).


**Sign convention:** positive yen move = yen APPRECIATION = the carry-unwind direction. USD/JPY is quoted yen-per-dollar, so the raw series moves the other way; it is flipped here.


## 1. Sharp yen appreciation → what happens to equities

Event = 5-session yen appreciation above its 95th percentile (**> 2.30%**), crossings clustered at 30 days → **84 episodes** over 1996-11-01 .. 2026-08-01.

Each episode is dated **two ways**, because they answer different questions: **onset** = first crossing, so the unwind itself falls inside the forward window; **peak** = largest 5-day move in the episode, so forward returns measure what happens AFTER the worst of it. August 2024 makes the difference concrete — onset 18 Jul, peak 5 Aug.


**onset-dated**

| horizon | mkt | mean fwd | median | hit rate >0 | unconditional | edge |
|---|---|---|---|---|---|---|
| 5d | S&P 500 | +0.45% | +0.70% | 58% | +0.15% | **+0.30pp** |
| 5d | Nikkei | +0.12% | +0.42% | 58% | +0.07% | **+0.04pp** |
| 21d | S&P 500 | +0.72% | +1.38% | 63% | +0.63% | **+0.08pp** |
| 21d | Nikkei | +0.18% | +1.28% | 59% | +0.31% | **-0.13pp** |
| 63d | S&P 500 | +1.91% | +2.33% | 63% | +1.89% | **+0.02pp** |
| 63d | Nikkei | -0.48% | +0.60% | 51% | +1.00% | **-1.49pp** |

**peak-dated**

| horizon | mkt | mean fwd | median | hit rate >0 | unconditional | edge |
|---|---|---|---|---|---|---|
| 5d | S&P 500 | +0.65% | +0.57% | 64% | +0.15% | **+0.50pp** |
| 5d | Nikkei | +0.52% | +0.42% | 60% | +0.07% | **+0.45pp** |
| 21d | S&P 500 | +1.93% | +1.64% | 67% | +0.63% | **+1.30pp** |
| 21d | Nikkei | +1.95% | +1.78% | 66% | +0.31% | **+1.64pp** |
| 63d | S&P 500 | +2.68% | +3.18% | 66% | +1.89% | **+0.79pp** |
| 63d | Nikkei | +0.53% | +0.85% | 55% | +1.00% | **-0.47pp** |

**Contemporaneous — the unwind window itself**

| mkt | mean over episode | median | worst episode |
|---|---|---|---|
| S&P 500 | -0.71% | +0.11% | -42.69% |
| Nikkei | -2.10% | -0.46% | -49.37% |

Compare the bond-selloff study in `bond_equity_linkage.md`: edges of +0.24pp (21d) and NEGATIVE beyond — i.e. nothing.

## 0. Validation — does the rule flag August 2024?

A method that misses the canonical carry unwind is not measuring what it claims to, so this is checked before anything is concluded. The test is whether the EPISODE covers it — not whether a single chosen date lands in an arbitrary window, which is what first made this look like a miss.

- yen move 29 Jul – 6 Aug 2024: **+5.28%** (positive = appreciation)
- Nikkei over that span **-8.28%**, S&P 500 **-4.10%**
- 5 Aug 2024 alone: Nikkei **-13.23%**, S&P -3.04%
- **flagged: YES** — episode spans 2024-07-18 .. 2024-09-10 (10 crossings), onset 2024-07-18, peak **2024-08-05** (+5.71%)
- the 5 Aug crossing was 18 days after onset, which is why onset- and peak-dating diverge so sharply for this episode

## 2. Convexity — is the response asymmetric?

The specific reason a linear correlation would miss a carry channel: if equities fall hard on yen appreciation but do not rise equally on depreciation, averaging the two gives ~zero. Deciles of the 5-session yen move, against the NEXT 5 sessions of equity returns.


| decile | mean 5d yen move | fwd 5d S&P | fwd 5d Nikkei | n |
|---|---|---|---|---|
| D1 ← strongest yen DEPRECIATION | -2.40% | -0.10% | +0.47% | 770 |
| D2 | -1.33% | +0.08% | +0.12% | 769 |
| D3 | -0.88% | +0.11% | +0.08% | 769 |
| D4 | -0.54% | +0.09% | -0.16% | 770 |
| D5 | -0.23% | +0.32% | +0.21% | 769 |
| D6 | +0.06% | +0.19% | +0.02% | 769 |
| D7 | +0.36% | +0.08% | +0.04% | 770 |
| D8 | +0.74% | +0.16% | -0.01% | 769 |
| D9 | +1.29% | +0.07% | -0.21% | 769 |
| D10 ← strongest yen APPRECIATION | +2.69% | +0.51% | +0.12% | 770 |

- S&P: appreciation decile +0.51% vs depreciation decile -0.10% → **spread +0.61pp**
- Nikkei: +0.12% vs +0.47% → **spread -0.35pp**

- **linear corr(5d yen move, next 5d S&P) = +0.069** — this is the number a linear test reports, and it is what the deciles above are testing for adequacy.

## 3. The real funding differential (US 3m − JP 3m)

Carry incentive, 2002-04-01 .. 2026-08-01: median **0.92pp**, range -0.88 .. 5.61pp. This is the spread a yen-funded position actually earns — the variable the domestic-only proxy could not see.

| carry differential | mean fwd 1y S&P | median | n days |
|---|---|---|---|
| Q1 narrowest | +12.88% | +12.36% | 1,521 |
| Q2 | +6.72% | +10.67% | 1,516 |
| Q3 | +4.27% | +7.68% | 1,505 |
| Q4 widest | +9.59% | +12.13% | 1,514 |

- corr(carry differential, forward 1y S&P) = **+0.009**
- after a top-decile COMPRESSION of the differential (<-0.42pp/63d — the unwind trigger): mean fwd 63d S&P **-1.07%** vs unconditional +1.96%

## 4. What this establishes

**1. The damage is CONTEMPORANEOUS, not forward — which is why every forward-looking test missed it.** Over the unwind window itself the Nikkei averages **−2.10%** (worst episode −49.37%) and the S&P **−0.71%** (worst −42.69%). But forward returns from either dating are flat-to-positive, and peak-dated they are clearly positive (+1.30pp edge, S&P 21d). Equities fall DURING a carry unwind and rebound after it. An event study that only looks forward from a date will therefore find nothing — which is exactly what the bond-selloff study did, and possibly for the same reason.

**2. My convexity hypothesis was WRONG.** I predicted equities would fall hard on yen appreciation and not rise equally on depreciation, and that averaging the two was why a linear test saw nothing. The deciles reject this: the strongest-appreciation decile (D10) has the BEST forward 5-day S&P return (+0.51%) and the depreciation decile (D1) the worst (−0.10%) — a +0.61pp spread pointing the opposite way to the prediction. The Nikkei spread (−0.35pp) has the predicted sign but is negligible. There is no forward asymmetry to find; the linear correlation of +0.069 was not hiding one.

**3. The carry LEVEL predicts nothing; the carry COMPRESSION does.** The differential's level is useless (corr +0.009 with forward 1y S&P, non-monotonic quintiles). But after a top-decile 63-day COMPRESSION of the US−JP differential — the actual unwind trigger — forward 63-day S&P is **−1.07% against +1.96% unconditional, a −3.03pp edge**. That is the single largest effect found across this study and the bond one, and it is the only result here consistent with the mechanism the literature describes.

🔴 **But do not over-read it.** Differential compression happens when the Fed cuts relative to the BoJ, and the Fed cuts when the US economy is deteriorating. So this may be measuring 'the Fed eases into trouble' rather than 'carry unwinds hurt equities' — the two are nearly collinear over 2002–2026 and this design cannot separate them. Distinguishing them needs a control for the growth outlook, which is not in this dataset.

**4. Sample limits.** 7,703 sessions over 30 years, but the funding-differential section starts only in 2002 (FRED JP 3-month coverage) and uses overlapping 252-day windows — roughly **24 independent years**, so quintile means separated by a few pp are noise. 84 episodes is a reasonable event count; the 24 years behind the carry differential is not.


---
*Descriptive analysis of historical relationships. Not investment advice. An event study shows association; yen and equity moves share drivers, so this cannot isolate the carry mechanism from common causation.*
