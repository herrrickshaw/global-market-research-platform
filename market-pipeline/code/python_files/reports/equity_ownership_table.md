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

## 🟢 India ownership — COMPUTED (screener.in, cap-weighted)

Market-cap-weighted shareholding across **52 liquid large caps** (>$20M/day turnover), 12 quarters. **This is the liquid large-cap segment, not the whole market** — excluding the long illiquid tail biases promoter share DOWN and institutional share UP versus a true all-market figure.


| quarter | n | Promoters | FIIs | DIIs | Government | Public |
|---|---|---|---|---|---|---|
| Jun 2024 | 49 | 54.0% | 19.4% | 15.3% | 0.4% | 10.9% |
| Sep 2024 | 49 | 53.8% | 19.5% | 15.6% | 0.4% | 10.7% |
| Dec 2024 | 49 | 53.6% | 18.8% | 16.3% | 0.4% | 10.9% |
| Mar 2025 | 51 | 48.1% | 21.5% | 18.7% | 0.4% | 11.3% |
| Jun 2025 | 49 | 53.1% | 18.6% | 17.1% | 0.7% | 10.5% |
| Sep 2025 | 49 | 52.9% | 18.5% | 17.4% | 0.7% | 10.4% |
| Dec 2025 | 50 | 52.5% | 18.4% | 17.4% | 0.7% | 10.8% |
| Mar 2026 | 52 | 47.2% | 20.6% | 20.2% | 0.7% | 11.2% |
| Jun 2026 | 52 | 47.2% | 20.0% | 20.6% | 0.7% | 11.4% |

**The FII→DII crossover, measured:** FIIs 19.2% → 20.0% (+0.8pp), DIIs 15.6% → 20.6% (+5.0pp) over Sep 2023 .. Jun 2026. The press figure this was meant to test is a ratio crossing 1.0; here the gap closes and reverses on a cap-weighted large-cap basis.

🔴 Quarter-to-quarter moves partly reflect a CHANGING company panel, not only ownership shifting. Quarters backed by fewer than 30 companies are dropped for that reason.

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

## 🟢 India SIP contribution — COMPUTED (AMFI monthly notes)

13 months parsed from AMFI Monthly Note PDFs, Jun 2024 .. Aug 2025. ₹ crore. This is the *household savings* leg of Indian equity demand — the sticky, payroll-linked flow that is NOT debt-financed.


| month | SIP ₹ crore | % of industry AUM |
|---|---|---|
| Jun 2024 | 21,000 | — |
| Jul 2024 | 23,000 | — |
| Aug 2024 | 23,547 | — |
| Sep 2024 | 24,509 | — |
| Oct 2024 | 25,323 | — |
| Dec 2024 | 26,459 | — |
| Jan 2025 | 26,400 | — |
| Mar 2025 | 24,113 | — |
| Apr 2025 | 26,632 | — |
| May 2025 | 26,688 | — |
| Jun 2025 | 27,269 | — |
| Jul 2025 | 28,464 | — |
| Aug 2025 | 28,265 | 20.2% |

+34.6% over the window. Two figures are independently cross-checked: Aug 2025 = 28,265 appears verbatim in that note, and Aug 2024 = 23,547 matches the year-ago base quoted in the Aug 2025 note.

🔴 Jun and Jul 2024 read as exactly 21,000 and 23,000 — those notes phrase the figure as a crossed THRESHOLD rather than an exact total, so treat them as approximate. Nov 2024 and Feb 2025 are absent: the parser returns nothing rather than guess when a note's wording is ambiguous.

## Stock vs flow — why both are here

Japan is the clean illustration: foreigners own roughly 30% of the float but account for the majority of turnover, so they set the price while domestic institutions and the BoJ hold the shares. India ran the same divergence in reverse — DIIs became the marginal buyer well before they overtook FIIs on holdings. Reading an ownership table as if it described who moves the market is the standard error this page is arranged to prevent.

