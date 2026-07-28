# Birds of a feather — does NSE's sector taxonomy capture co-movement?

- 35 quarterly formations, 2017-02-09 → 2025-10-14
- universe: top 300 by trailing turnover with an NSE Industry label (~231 usable)
- groups: 11 data clusters vs 16 official industries · forward window 126 bars
- metric: **mean within-group pairwise correlation in the FORWARD window** (never seen by the grouping)

| grouping | mean within-group fwd corr | vs random | t vs random |
|---|--:|--:|--:|
| RANDOM (the null) | 0.2412 | — | — |
| **OFFICIAL NSE Industry** | 0.3258 | **+0.0846** | 23.86 |
| **DATA clusters (trailing corr)** | 0.4010 | **+0.1598** | 39.16 |

- **DATA minus OFFICIAL: +0.0752  (t = 17.62)** — data clusters beat the taxonomy in 100% of formations

## by sub-period

| period | n | random | official | data |
|---|--:|--:|--:|--:|
| 2017-2020 | 16 | 0.2338 | 0.3024 | 0.3828 |
| 2021-2026 | 19 | 0.2474 | 0.3454 | 0.4164 |

> RANDOM is the floor, not zero: any basket inherits market beta, so even shuffled groups co-move. A taxonomy earns its status only by beating it. Clusters are rebuilt from trailing returns at every formation, so membership is point-in-time — unlike a named thematic list, which every surviving member was chosen to be in.
