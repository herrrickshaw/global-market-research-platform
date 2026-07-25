# Valuation reversion — does over/under-pricing correct? (CN, PIT 2017→2026)

109 monthly formations. Quintile 1 = cheapest vs market PE, 5 = richest. Market-relative (no historical sectors); India's sector-relative version is in `pe_anomaly_backtest.md` (+5.3%/6M, t 2.5). Survivorship-biased → read spreads.

## 1. Forward return by PE quintile

| horizon | Q1 cheap | Q2 | Q3 | Q4 | Q5 rich | Q1−Q5 | t |
|---|--:|--:|--:|--:|--:|--:|--:|
| 3M | +4.04% | +4.21% | +4.31% | +3.97% | +3.66% | **+0.38%** | 0.30 |
| 6M | +8.61% | +8.00% | +8.34% | +7.81% | +7.04% | **+1.57%** | 0.33 |

## 2. Convergence — does relative PE move toward the market median (1.0)?

| bucket | rel-PE at formation | rel-PE +6M | moved toward 1.0? |
|---|--:|--:|---|
| cheap | 0.32× | 0.35× | ✅ yes |
| rich | 4.22× | 3.48× | ✅ yes |

> Read: if Q1−Q5 spread > 0 with t≳2, cheap-vs-market corrects UP / rich corrects DOWN in RETURNS. If rich rel-PE falls toward 1.0 and cheap rises toward 1.0, the multiple itself converges. Both together = the mean-reversion the clustering screen bets on. Not investment advice.