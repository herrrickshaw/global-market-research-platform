# Impact-aware execution & capacity (Almgren-Chriss square-root model)

Replaces the flat-bps cost with `half_spread + η·σ·√(Q/ADV)` and a 15%-ADV participation cap. Book holds ~40 names/desk. `net_edge` = the bull-regime gross excess minus round-trip impact — where it crosses 0 is the desk's capacity (the AUM ceiling before impact eats the edge).

| market | AUM $M | $/pos | %ADV | impact bps | days to exit | net edge bps |
|---|--:|--:|--:|--:|--:|--:|
| IN | 1 | 0.03 | 0.4 | 40.3 | 1.0 | 3.7 |
| IN | 5 | 0.12 | 1.9 | 80.3 | 1.0 | -36.3 ❌ |
| IN | 10 | 0.25 | 3.8 | 110.2 | 1.0 | -66.2 ❌ |
| IN | 25 | 0.62 | 9.6 | 169.6 | 1.0 | -125.6 ❌ |
| IN | 50 | 1.25 | 19.1 | 236.5 | 1.3 | -192.5 ❌ |
| IN | 100 | 2.50 | 38.3 | 331.2 | 2.6 | -287.2 ❌ |
| IN | 250 | 6.25 | 95.7 | 519.0 | 6.4 | -475.0 ❌ |
| IN | 500 | 12.50 | 191.4 | 730.7 | 12.8 | -686.7 ❌ |
| US | 1 | 0.03 | 0.0 | 15.0 | 1.0 | 6.0 |
| US | 5 | 0.12 | 0.2 | 29.7 | 1.0 | -8.7 ❌ |
| US | 10 | 0.25 | 0.3 | 40.8 | 1.0 | -19.8 ❌ |
| US | 25 | 0.62 | 0.8 | 62.8 | 1.0 | -41.8 ❌ |
| US | 50 | 1.25 | 1.7 | 87.6 | 1.0 | -66.6 ❌ |
| US | 100 | 2.50 | 3.4 | 122.6 | 1.0 | -101.6 ❌ |
| US | 250 | 6.25 | 8.5 | 192.1 | 1.0 | -171.1 ❌ |
| US | 500 | 12.50 | 17.0 | 270.4 | 1.1 | -249.4 ❌ |
| JP | 1 | 0.03 | 0.2 | 21.5 | 1.0 | -6.5 ❌ |
| JP | 5 | 0.12 | 1.0 | 41.9 | 1.0 | -26.9 ❌ |
| JP | 10 | 0.25 | 2.0 | 57.2 | 1.0 | -42.2 ❌ |
| JP | 25 | 0.62 | 5.0 | 87.5 | 1.0 | -72.5 ❌ |
| JP | 50 | 1.25 | 10.0 | 121.7 | 1.0 | -106.7 ❌ |
| JP | 100 | 2.50 | 20.0 | 170.1 | 1.3 | -155.1 ❌ |
| JP | 250 | 6.25 | 49.9 | 266.0 | 3.3 | -251.0 ❌ |
| JP | 500 | 12.50 | 99.9 | 374.1 | 6.7 | -359.1 ❌ |
| KR | 1 | 0.03 | 0.5 | 60.1 | 1.0 | 5.9 |
| KR | 5 | 0.12 | 2.4 | 122.1 | 1.0 | -56.1 ❌ |
| KR | 10 | 0.25 | 4.9 | 168.5 | 1.0 | -102.5 ❌ |
| KR | 25 | 0.62 | 12.2 | 260.6 | 1.0 | -194.6 ❌ |
| KR | 50 | 1.25 | 24.4 | 364.4 | 1.6 | -298.4 ❌ |
| KR | 100 | 2.50 | 48.8 | 511.3 | 3.3 | -445.3 ❌ |
| KR | 250 | 6.25 | 122.1 | 802.6 | 8.1 | -736.6 ❌ |
| KR | 500 | 12.50 | 244.2 | 1130.8 | 16.3 | -1064.8 ❌ |
| EU | 1 | 0.03 | 0.0 | 9.1 | 1.0 | 5.9 |
| EU | 5 | 0.12 | 0.0 | 12.8 | 1.0 | 2.2 |
| EU | 10 | 0.25 | 0.1 | 15.6 | 1.0 | -0.6 ❌ |
| EU | 25 | 0.62 | 0.1 | 21.3 | 1.0 | -6.3 ❌ |
| EU | 50 | 1.25 | 0.3 | 27.6 | 1.0 | -12.6 ❌ |
| EU | 100 | 2.50 | 0.6 | 36.5 | 1.0 | -21.5 ❌ |
| EU | 250 | 6.25 | 1.4 | 54.2 | 1.0 | -39.2 ❌ |
| EU | 500 | 12.50 | 2.8 | 74.2 | 1.0 | -59.2 ❌ |

## Capacity per desk (AUM where net edge → 0)

| desk | gross edge bps/2wk | ~capacity ($M AUM) |
|---|--:|--:|
| IN | 44 | 1 |
| US | 21 | 1 |
| JP | 15 | 0 |
| KR | 66 | 1 |
| EU | 15 | 5 |

> The edge is a small-money edge: India's +44bps/2wk survives to a few tens of $M, then impact erases it. This is the hard ceiling on how much the JPY-carry leverage can deploy — leverage multiplies ROE only until AUM hits capacity, then impact dominates. Half-spread/σ are desk medians; illustrative. Not investment advice.