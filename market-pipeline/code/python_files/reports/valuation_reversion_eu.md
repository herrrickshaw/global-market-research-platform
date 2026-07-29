# Valuation reversion — does over/under-pricing correct? (EU, PIT 2022→2026)

35 monthly formations. Quintile 1 = cheapest vs market PE, 5 = richest. Market-relative (no historical sectors); India's sector-relative version is in `pe_anomaly_backtest.md` (+5.3%/6M, t 2.5). Survivorship-biased → read spreads.

## 1. Forward return by PE quintile

| horizon | Q1 cheap | Q2 | Q3 | Q4 | Q5 rich | Q1−Q5 | t |
|---|--:|--:|--:|--:|--:|--:|--:|
| 3M | +18.10% | +3.01% | +2.85% | +2.53% | +1.59% | **+16.51%** | 1.54 |
| 6M | +39.07% | +6.14% | +5.20% | +5.38% | +3.20% | **+35.88%** | 1.57 |

## 2. Convergence — does relative PE move toward the market median (1.0)?

| bucket | rel-PE at formation | rel-PE +6M | moved toward 1.0? |
|---|--:|--:|---|
| cheap | 0.20× | 0.21× | ✅ yes |
| rich | 5.07× | 4.91× | ✅ yes |

> Read: if Q1−Q5 spread > 0 with t≳2, cheap-vs-market corrects UP / rich corrects DOWN in RETURNS. If rich rel-PE falls toward 1.0 and cheap rises toward 1.0, the multiple itself converges. Both together = the mean-reversion the clustering screen bets on. Not investment advice.