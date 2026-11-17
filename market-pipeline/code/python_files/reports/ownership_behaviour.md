# Does ownership composition show up in market behaviour?

Companion to `equity_ownership_table.md` (who owns what) and `equity_capital_sources.md` (where the money comes from). This asks whether either is visible in the price series.


## 1. Behavioural signature, measured

Daily log returns per index, longest common history each. `var_ratio_5d` > 1 means trending, < 1 mean-reverting, = 1 a random walk — the cleanest single discriminator between a market that overshoots and corrects and one that trends.


| market | index | yrs | ann vol % | autocorr | VR(5d) | kurtosis | vol cluster | max DD % |
|---|---|---|---|---|---|---|---|---|
| US | S&P 500 | 31 | 19.0 | -0.088 | 0.84 | 10.1 | 0.27 | -57 |
| JP | Nikkei 225 | 31 | 23.4 | -0.044 | 0.90 | 6.3 | 0.22 | -69 |
| IN | Nifty 50 | 19 | 20.6 | +0.037 | 1.02 | 15.1 | 0.28 | -60 |
| KR | KOSPI | 30 | 27.3 | +0.038 | 1.00 | 7.6 | 0.29 | -65 |
| EU | Euro Stoxx 50 | 19 | 21.8 | -0.036 | 0.91 | 7.7 | 0.21 | -60 |

## 2. Ownership beside behaviour

| market | evidence | closely held % | retail % | foreign % | ann vol % | VR(5d) | autocorr |
|---|---|---|---|---|---|---|---|
| US | 🟢 | — | 46.1 | 18.2 | 19.0 | 0.84 | -0.088 |
| JP | 🟡 | — | 17.0 | 30.0 | 23.4 | 0.90 | -0.044 |
| IN | 🟢 | 47.2 | 11.4 | 20.0 | 20.6 | 1.02 | +0.037 |
| KR | 🟡 | — | 64.0 | 30.0 | 27.3 | 1.00 | +0.038 |
| EU | 🟡 | — | — | — | 21.8 | 0.91 | -0.036 |

Ownership notes (evidence grade carried from `equity_ownership.py`):

- **US** 🟢 — households 46.1% (Z.1 residual, largely intermediated); MF+ETF 25.5%
- **JP** 🟡 — BoJ is the largest single owner via ETFs; foreigners ~60-70% of turnover
- **IN** 🟢 — promoters 47.2%; FII 20.0 + DII 20.6 (screener.in, cap-weighted)
- **KR** 🟡 — retail = 64% of TRANSACTION VALUE (a flow share, not ownership)
- **EU** 🟡 — not established — no primary source reached

### 🔴 What these five rows can and cannot support

**n = 5.** Five points cannot establish a cross-sectional relationship. Any correlation computed across them is descriptive arithmetic, not evidence, and would not survive a standard error. The markets also differ in sector mix, currency regime, index construction and capital controls — none controlled here. Read the table as *whether the measured behaviour is consistent with the measured ownership*, and nothing stronger.

One comparability trap worth naming: **Korea's 64% is a share of TRANSACTION VALUE, not of ownership**, and India's 11.4% public float is an OWNERSHIP share. Putting them in one column is convenient and not quite legitimate — a market can be retail-dominated in flow while institutions hold the stock, which is precisely Korea. Turnover share is the better predictor of price behaviour; ownership share is what is actually measurable across markets.

## 3. What the numbers actually say

**The five markets split two-and-three, and the split is not random.**

| group | markets | autocorr | VR(5d) | reading |
|---|---|---|---|---|
| institution-intermediated | US, JP, EU | **negative** (−0.088 to −0.036) | **< 1** (0.84–0.91) | overshoots get corrected: mean-reverting |
| retail / closely-held | IN, KR | **positive** (+0.037, +0.038) | **≈ 1** (1.02, 1.00) | no correction: trending or random-walk |

**1. Volatility lines up with retail turnover.** Korea — 64% of transaction value from retail, the highest of any major market — has the highest volatility at **27.3%**. The US, with the deepest institutional intermediation (MF+ETF 25.5% of the float, households mostly holding *through* funds), has the lowest at **19.0%**. That ordering is what the inelastic-markets logic predicts.

**2. 🔴 My stated prediction was WRONG on direction.** The docstring predicted retail-heavy markets would show short-horizon REVERSAL — noise trading pushed prices away and arbitrage pulled them back. The data says the opposite: IN and KR show **positive** autocorrelation and VR ≈ 1, while the institution-heavy markets are the mean-reverting ones. Whatever produces reversal at a 5-day horizon, it is present where institutions dominate and absent where retail does.

**3. 🔴 And there is a microstructure explanation that has nothing to do with behaviour.** Positive daily autocorrelation in less liquid markets is classically produced by NON-SYNCHRONOUS TRADING and partial price adjustment: when index constituents do not all trade at the close, today's index partly reflects yesterday's information, which manufactures positive serial correlation mechanically. India's free float is only ~11.4% public with promoters holding 47.2%, so thin trading is exactly what one would expect. **This design cannot separate that from an ownership effect**, and the honest reading is that the IN/KR positive autocorrelation is at least partly an artifact.

**4. Kurtosis does not sort by ownership at all.** India is the fattest-tailed (15.1) and the US second (10.1), with Japan lowest (6.3) — no ordering that maps onto retail share, institutional share or float. Whatever drives tail risk here is not ownership composition.


### Where this leaves the question

Ownership composition is **consistent with** the volatility ordering and with a clean split in serial correlation. It is **not established as the cause** of either: n=5, no controls, and at least one competing mechanism (non-synchronous trading) that predicts the same serial-correlation pattern without invoking investor behaviour at all.

The way to actually test this is WITHIN a market rather than across five: rank stocks by promoter/institutional holding — data `equity_ownership.py` already collects per company for India — and compare behavioural metrics across those buckets, where sector, currency, calendar and index construction are held constant and n is in the hundreds rather than 5. That is the study this table argues for and does not itself deliver.


*Descriptive analysis of historical relationships. Not investment advice.*
