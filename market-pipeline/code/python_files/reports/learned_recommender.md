# Learned-model recommendations (shadow mode)

Lasso-weighted factor score applied to the live liquid universe; cached to `learned_recs.parquet` for the digest to join (sets `rec_learned`, does NOT replace the production `rec` until validated live). Active markets = those where Lasso kept factors.

| market | learned factors | names scored | BUY | HOLD | SELL |
|---|---|--:|--:|--:|--:|
| IN | trend | 1438 | 537 | 236 | 665 |
| US | (none — regime rule) | 0 | — | — | — |
| JP | (none — regime rule) | 0 | — | — | — |
| KR | trend, mom126, golden_cross, lowvol | 1725 | 655 | 529 | 541 |
| EU | (none — regime rule) | 0 | — | — | — |

> Shadow mode: `rec_learned` is recorded and comparable against the live `rec` but does not drive eviction or the mailer until it beats the regime rule on forward paper-track data. Not investment advice.