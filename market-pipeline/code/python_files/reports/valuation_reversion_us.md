# Valuation reversion — does over/under-pricing correct? (US, PIT 2017→2026)

109 monthly formations. Quintile 1 = cheapest vs market PE, 5 = richest. Market-relative (no historical US sectors); India's sector-relative version is in `pe_anomaly_backtest.md` (+5.3%/6M, t 2.5). Survivorship-biased → read spreads.

## 1. Forward return by PE quintile

| horizon | Q1 cheap | Q2 | Q3 | Q4 | Q5 rich | Q1−Q5 | t |
|---|--:|--:|--:|--:|--:|--:|--:|
| 3M | +4.44% | +2.81% | +2.86% | +2.78% | +2.72% | **+1.72%** | 2.32 |
| 6M | +8.72% | +5.74% | +5.44% | +5.73% | +5.54% | **+3.18%** | 1.16 |

## 2. Convergence — does relative PE move toward the market median (1.0)?

| bucket | rel-PE at formation | rel-PE +6M | moved toward 1.0? |
|---|--:|--:|---|
| cheap | 0.32× | 0.36× | ✅ yes |
| rich | 4.63× | 3.83× | ✅ yes |

> Read: if Q1−Q5 spread > 0 with t≳2, cheap-vs-market corrects UP / rich corrects DOWN in RETURNS. If rich rel-PE falls toward 1.0 and cheap rises toward 1.0, the multiple itself converges. Both together = the mean-reversion the clustering screen bets on. Not investment advice.