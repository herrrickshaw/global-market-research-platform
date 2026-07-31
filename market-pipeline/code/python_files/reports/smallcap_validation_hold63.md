# Small-cap exclusion screen — validation

Generated 2026-07-28 by `smallcap_screener.py --validate --hold 63 --warmup 220`. Survivorship-free: the band is reconstructed point-in-time at each formation.

# Small-cap exclusion rules — survivorship-free validation

- 108 monthly formations, 2017-01-24 → 2026-04-07
- band = trailing turnover ranks 200-450 (~240 names), 63-bar hold, 100bp charged
- panel INCLUDES delisted names, so this has no survivorship lift

| leg | mean 63-bar return | ann. | vs full band |
|---|--:|--:|--:|
| full band (the index proxy) | +2.90% | +12.13% | +0.00pp |
| SCREENED (exclusions removed) | +4.66% | +19.98% | +1.76pp |
| the excluded names | +1.08% | +4.40% | -1.82pp |

## marginal effect of each exclusion (mean forward return of names it removes)

| rule | mean fwd | vs band | verdict |
|---|--:|--:|---|
| downtrend | +1.32% | -2.58pp | excluding helps |
| distress | -1.19% | -5.09pp | excluding helps |
| blowup | +2.11% | -1.79pp | excluding helps |
| untradeable | -4.42% | -8.33pp | excluding helps |

- screened-minus-band per period: **+1.76%**  (t = 6.09, n=108)

## by sub-period (does it work in the regime it was built for?)

| period | n | band | screened | edge | t |
|---|--:|--:|--:|--:|--:|
| 2016-2020 bear | 44 | +0.91% | +3.50% | **+2.59%** | 4.30 |
| 2020-2026 bull | 64 | +5.96% | +7.15% | **+1.18%** | 5.02 |
