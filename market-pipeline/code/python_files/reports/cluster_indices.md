# Birds of a feather — does NSE's sector taxonomy capture co-movement?

- 35 quarterly formations, 2017-02-09 → 2025-10-14
- universe: top 300 by trailing turnover with an NSE Industry label (~231 usable)
- groups: 8 data clusters vs 16 official industries · forward window 126 bars
- metric: **mean within-group pairwise correlation in the FORWARD window** (never seen by the grouping)

| grouping | mean within-group fwd corr | vs random | t vs random |
|---|--:|--:|--:|
| RANDOM (the null) | 0.2412 | — | — |
| **OFFICIAL NSE Industry** | 0.3258 | **+0.0846** | 23.86 |
| **DATA clusters (trailing corr)** | 0.3530 | **+0.1118** | 20.85 |

- **DATA minus OFFICIAL: +0.0272  (t = 4.37)** — data clusters beat the taxonomy in 83% of formations

## by sub-period

| period | n | random | official | data |
|---|--:|--:|--:|--:|
| 2017-2020 | 16 | 0.2338 | 0.3024 | 0.3377 |
| 2021-2026 | 19 | 0.2474 | 0.3454 | 0.3659 |

## sensitivity to k — the whole result lives or dies here

This run used **k=45** (8 usable clusters). The comparison is only fair when the two groupings have comparable granularity, because smaller groups are mechanically more homogeneous — so k is not a free parameter to be tuned until the answer is nice. The recorded sweep (reproduce any row with `--k N`):

| k | data groups | vs random | vs OFFICIAL | t |
|--:|--:|--:|--:|--:|
| 15 | 4 | +0.0379 | -0.0467 | -7.77 |
| 30 | 6 | +0.0807 | -0.0039 | -0.55 |
| 45 ⬅ **shipped** | 8 | +0.1118 | +0.0272 | 4.37 |
| 60 | 10 | +0.1420 | +0.0574 | 13.27 |
| 80 | 11 | +0.1598 | +0.0752 | 17.62 |

> The sign FLIPS between k=30 and k=45, and the t-statistic rises monotonically with k. Any single-k claim is therefore an artefact of k, in either direction. k=45 is shipped as the closest fair match to the 16 official industries after MIN_GROUP filtering — not because it is the most flattering. It is not: k=80 reports +0.0752 (t 17.62), nearly three times larger, and a report built on it was in this repo until 2026-07-28. Higher k means smaller groups, which raises within-group correlation mechanically, so that number measures granularity as much as structure.

> RANDOM is the floor, not zero: any basket inherits market beta, so even shuffled groups co-move. A taxonomy earns its status only by beating it. Clusters are rebuilt from trailing returns at every formation, so membership is point-in-time — unlike a named thematic list, which every surviving member was chosen to be in.
