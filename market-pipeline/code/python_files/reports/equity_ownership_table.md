# Who owns each equity market

**Read the evidence tags.** 🟢 = computed here from primary data and reproducible by re-running `equity_ownership.py`. 🟡 = cited from public reporting, not recomputed. The two are not interchangeable and the difference is the most important thing on this page.


## 🟢 United States — COMPUTED (Fed Z.1 via FRED, as of 2026-01-01)

Total corporate equity outstanding **$106.9 trillion**. Holders are DIRECT holders; the household line is a residual, which is how the Financial Accounts themselves derive that sector.


| holder | % of US corporate equity |
|---|---|
| Households (residual) | **46.1%** |
| Rest of world (foreign) | **18.2%** |
| Mutual funds | **15.4%** |
| ETFs | **10.1%** |
| Private pension funds | **4.8%** |
| State/local govt pensions | **3.4%** |
| Life insurance | **0.7%** |
| Federal govt retirement | **0.7%** |
| Property-casualty insurance | **0.6%** |

Sum 100.0%.

**Ten-year drift** (vs 2016-10-01):

| holder | then | now | change |
|---|---|---|---|
| Households (residual) | 43.6% | 46.1% | +2.5pp |
| Rest of world (foreign) | 14.3% | 18.2% | +3.9pp |
| Mutual funds | 22.5% | 15.4% | -7.1pp |
| ETFs | 5.0% | 10.1% | +5.0pp |
| Private pension funds | 5.8% | 4.8% | -0.9pp |
| State/local govt pensions | 5.8% | 3.4% | -2.4pp |
| Life insurance | 1.5% | 0.7% | -0.7pp |
| Federal govt retirement | 0.6% | 0.7% | +0.0pp |
| Property-casualty insurance | 0.9% | 0.6% | -0.3pp |

## 🟡 India — CITED, not computed

| holder | share | note |
|---|---|---|
| FII / FPI | ~17% | FII:DII ownership ratio fell below 1 to 0.98 at 31 Mar 2025; FII ownership reported at multi-year lows |
| DII (MF + insurance + pension) | ~17% | DII holdings ₹71.76 lakh crore, ~2% above FII |
| Promoters | ~50% | Promoter holding is the dominant Indian block; widely reported |
| Retail direct + others | balance | Residual of the above |

## 🟡 Japan — CITED, not computed

| holder | share | note |
|---|---|---|
| Foreign investors | ~30% owned | but ~60-70% of TURNOVER — the stock/flow gap |
| BoJ (via ETFs) | largest single owner | ¥45.1tn vs GPIF ¥44.8tn at the reported date |
| Individuals | ~17% | individual holdings ~¥170.5tn FY2023; ~25% of trading value FY2025 |
| Banks/insurers/corporates | balance | cross-shareholdings, long-term declining |

## 🟡 Korea — CITED, not computed

| holder | share | note |
|---|---|---|
| Retail | 64% of TRANSACTION VALUE | highest of any major market; vs ~30% US/Japan |
| NPS | ~8% of KOSPI | equities >50% of assets but 36.8% overseas vs 14.8% domestic |
| Foreign | ~30% | long-run range |

## 🟡 Europe — CITED, not computed

| holder | share | note |
|---|---|---|
| — | not established | no primary source reached; pension/insurance-led with low direct retail participation is the usual characterisation |

## 🟢 India FLOW — COMPUTED (NSE daily, append-only)

2 rows, 2026-07-31 .. 2026-07-31. Values ₹ crore. **This store cannot be backfilled** — NSE's endpoint serves the current day only — so it accumulates from first run.


| date | DII | FII/FPI |
|---|---|---|
| 2026-07-31 | +2,260 | +277 |

## Stock vs flow — why both are here

Japan is the clean illustration: foreigners own roughly 30% of the float but account for the majority of turnover, so they set the price while domestic institutions and the BoJ hold the shares. India ran the same divergence in reverse — DIIs became the marginal buyer well before they overtook FIIs on holdings. Reading an ownership table as if it described who moves the market is the standard error this page is arranged to prevent.

