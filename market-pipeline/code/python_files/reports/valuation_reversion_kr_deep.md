# Valuation reversion — does over/under-pricing correct? (KR_deep, PIT 2020→2026)

68 monthly formations. Quintile 1 = cheapest vs market PE, 5 = richest. Market-relative (no historical sectors); India's sector-relative version is in `pe_anomaly_backtest.md` (+5.3%/6M, t 2.5). Survivorship-biased → read spreads.

## 1. Forward return by PE quintile

| horizon | Q1 cheap | Q2 | Q3 | Q4 | Q5 rich | Q1−Q5 | t |
|---|--:|--:|--:|--:|--:|--:|--:|
| 3M | +3.50% | +3.13% | +1.19% | +2.57% | +1.33% | **+2.17%** | 1.84 |
| 6M | +7.31% | +6.19% | +2.86% | +5.91% | +3.46% | **+3.85%** | 1.51 |

## 2. Convergence — does relative PE move toward the market median (1.0)?

| bucket | rel-PE at formation | rel-PE +6M | moved toward 1.0? |
|---|--:|--:|---|
| cheap | 0.35× | 0.38× | ✅ yes |
| rich | 7.02× | 5.60× | ✅ yes |

> Read: if Q1−Q5 spread > 0 with t≳2, cheap-vs-market corrects UP / rich corrects DOWN in RETURNS. If rich rel-PE falls toward 1.0 and cheap rises toward 1.0, the multiple itself converges. Both together = the mean-reversion the clustering screen bets on. Not investment advice.