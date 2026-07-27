# Valuation reversion — does over/under-pricing correct? (JP, PIT 2016→2026)

116 monthly formations. Quintile 1 = cheapest vs market PE, 5 = richest. Market-relative (no historical sectors); India's sector-relative version is in `pe_anomaly_backtest.md` (+5.3%/6M, t 2.5). Survivorship-biased → read spreads.

## 1. Forward return by PE quintile

| horizon | Q1 cheap | Q2 | Q3 | Q4 | Q5 rich | Q1−Q5 | t |
|---|--:|--:|--:|--:|--:|--:|--:|
| 3M | +5.38% | +4.12% | +3.51% | +2.97% | +2.33% | **+3.05%** | 5.30 |
| 6M | +11.00% | +8.16% | +7.05% | +5.83% | +4.40% | **+6.60%** | 4.84 |

## 2. Convergence — does relative PE move toward the market median (1.0)?

| bucket | rel-PE at formation | rel-PE +6M | moved toward 1.0? |
|---|--:|--:|---|
| cheap | 0.33× | 0.34× | ✅ yes |
| rich | 4.72× | 4.50× | ✅ yes |

> Read: if Q1−Q5 spread > 0 with t≳2, cheap-vs-market corrects UP / rich corrects DOWN in RETURNS. If rich rel-PE falls toward 1.0 and cheap rises toward 1.0, the multiple itself converges. Both together = the mean-reversion the clustering screen bets on. Not investment advice.