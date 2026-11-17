# Valuation reversion — does over/under-pricing correct? (KR, PIT 2022→2026)

35 monthly formations. Quintile 1 = cheapest vs market PE, 5 = richest. Market-relative (no historical sectors); India's sector-relative version is in `pe_anomaly_backtest.md` (+5.3%/6M, t 2.5). Survivorship-biased → read spreads.

## 1. Forward return by PE quintile

| horizon | Q1 cheap | Q2 | Q3 | Q4 | Q5 rich | Q1−Q5 | t |
|---|--:|--:|--:|--:|--:|--:|--:|
| 3M | +2.89% | +1.82% | +0.75% | +1.35% | -1.02% | **+3.91%** | 3.70 |
| 6M | +5.38% | +4.75% | +2.63% | +3.65% | -0.95% | **+6.33%** | 3.32 |

## 2. Convergence — does relative PE move toward the market median (1.0)?

| bucket | rel-PE at formation | rel-PE +6M | moved toward 1.0? |
|---|--:|--:|---|
| cheap | 0.32× | 0.36× | ✅ yes |
| rich | 5.94× | 4.14× | ✅ yes |

> Read: if Q1−Q5 spread > 0 with t≳2, cheap-vs-market corrects UP / rich corrects DOWN in RETURNS. If rich rel-PE falls toward 1.0 and cheap rises toward 1.0, the multiple itself converges. Both together = the mean-reversion the clustering screen bets on. Not investment advice.