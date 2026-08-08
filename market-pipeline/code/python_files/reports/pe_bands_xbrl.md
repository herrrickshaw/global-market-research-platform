# India P/E panel — bands, tiers and accuracy

Generated 2026-07-30 by `pe_bands.py --build --source xbrl`.

- **1,979,108** daily observations · **1,776** symbols
- span **2019-01-17 → 2026-07-29**
- P/E is TTM: four consecutive quarters, each stamped at its FILING date, so a lookup on any bar uses only what the market could already see

## Band occupancy

Bands are ±σ on **log** P/E. A multiple is ratio-scale and right-skewed —
10→20 must count the same as 40→80 — and banding raw P/E produced
z-scores of +78/−38 before this was corrected. σ carries a floor of 0.15
log units, because a near-constant multiple otherwise divides by ~0 (one
symbol reached z = −45 that way).

| band | share |
|---|--:|
| normal | 44.6% |
| nan | 19.0% |
| +1..+2sd | 13.9% |
| -2..-1sd | 10.5% |
| >+2sd | 8.4% |
| <-2sd | 3.7% |

> `nan` at 19.0% is the honest coverage gap — symbols without enough consecutive quarters to form a TTM window, or without the 12-observation history a band needs. It is reported rather than dropped: a hidden gap reads as coverage.

## Accuracy vs `fundamentals.ratios`

Independent cross-check on the latest bar, 926 symbols present in both. `ratios` is built from a different source, so agreement is evidence and disagreement is a question, not proof either side is right.

| percentile | abs error |
|---|--:|
| p25 | 6.4% |
| p50 | 18.7% |
| p75 | 42.4% |
| p90 | 78.2% |

- **median 18.7%** · within 25%: 59% · within 50%: 80%

> This number is why `--source` defaults to `xbrl`: the screener path measures wider AND covers fewer symbols (1,301 vs 1,744). Recomputed on every build rather than quoted, so it cannot drift from the panel it describes.

## Cross-sectional tiers

`tier` is a per-DATE decile of P/E, so tier 1 is "cheapest tenth TODAY" rather than cheap against a fixed historical level. That keeps it invariant to market-wide re-rating: in a bull market every absolute P/E rises, and a fixed threshold would silently empty the cheap tier.

| tier (latest bar) | symbols |
|---|--:|
| 1 | 145 |
| 2 | 145 |
| 3 | 145 |
| 4 | 145 |
| 5 | 146 |
| 6 | 145 |
| 7 | 145 |
| 8 | 145 |
| 9 | 145 |
| 10 | 146 |

