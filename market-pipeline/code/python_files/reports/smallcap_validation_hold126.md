# Small-cap exclusion screen — validation

Generated 2026-07-28 by `smallcap_screener.py --validate --hold 126 --warmup 220`. Survivorship-free: the band is reconstructed point-in-time at each formation.

# Small-cap exclusion rules — survivorship-free validation

- 105 monthly formations, 2017-01-24 → 2025-12-31
- band = trailing turnover ranks 200-450 (~239 names), 126-bar hold, 100bp charged
- panel INCLUDES delisted names, so this has no survivorship lift

| leg | mean 63-bar return | ann. | vs full band |
|---|--:|--:|--:|
| full band (the index proxy) | +6.90% | +30.58% | +0.00pp |
| SCREENED (exclusions removed) | +9.96% | +46.22% | +3.07pp |
| the excluded names | +3.88% | +16.46% | -3.01pp |

## marginal effect of each exclusion (mean forward return of names it removes)

| rule | mean fwd | vs band | verdict |
|---|--:|--:|---|
| downtrend | +3.05% | -4.85pp | excluding helps |
| distress | -0.21% | -8.11pp | excluding helps |
| blowup | +5.53% | -2.37pp | excluding helps |
| untradeable | +1.78% | -6.12pp | excluding helps |

- screened-minus-band per period: **+3.07%**  (t = 8.75, n=105)

## by sub-period (does it work in the regime it was built for?)

| period | n | band | screened | edge | t |
|---|--:|--:|--:|--:|--:|
| 2016-2020 bear | 44 | +3.04% | +7.37% | **+4.33%** | 6.06 |
| 2020-2026 bull | 61 | +11.40% | +13.55% | **+2.15%** | 8.23 |
