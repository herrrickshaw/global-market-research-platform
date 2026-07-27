# Value-reversion as a classifier — precision/recall/accuracy, gross vs net of the information-asymmetry tax

Cheapest-PE quintile = *predict up*, richest = *predict down*; outcome = 6M forward return. **Gross** counts any correct direction; **net** counts a buy as a win only if the move beats the round-trip cost (spread+slippage+impact) — the tax an informed/fast trader extracts first. The gap is what the data disadvantage costs a retail trader.

| market | cost bps | precision (gross→net) | accuracy (gross→net) | recall net | F1 net | precision tax |
|---|--:|--:|--:|--:|--:|--:|
| IN | 40 | 51%→**50%** | 51%→51% | 51% | 0.51 | −1pp |
| US | 15 | 59%→**58%** | 53%→53% | 52% | 0.55 | −0pp |
| KR | 30 | 50%→**49%** | 55%→55% | 55% | 0.52 | −1pp |
| JP | 25 | 65%→**64%** | 57%→57% | 56% | 0.60 | −0pp |
| CN | 35 | 53%→**53%** | 52%→52% | 52% | 0.52 | −1pp |

## Read

- **Precision** = of the cheap stocks we'd buy, how many actually rose. **Net** precision (after the buy has to clear its cost) is the honest hit-rate a retail trader gets.
- The **precision tax** (gross−net) is the information-asymmetry drag: markets with wider spreads/higher costs (IN, CN) lose more of their edge to the faster/informed counterparty.
- **The headline lesson:** net accuracy is only ~50–57% — barely better than a coin flip. Yet these strategies *make money* (value-reversion +5–6%/6M). **The edge is in the MAGNITUDE, not the hit rate** — the winners are bigger than the losers. A confusion matrix *understates* a magnitude strategy; win-rate is the wrong lens, which is why we size by conviction and read spreads, not levels.
- **JP has the best classifier structure** (precision 64%, most mass on the TP/TN diagonal) — consistent with its strongest reversion t-stat (4.84). KR/IN sit near 50% hit-rate despite working in returns — pure magnitude plays.
- **The info-asymmetry tax is horizon-dependent:** at 6M a 15–40bps round-trip is tiny next to a ±15% move, so the precision tax is ~0–1pp here. It would be **large** for short-horizon signals (PEAD, momentum, intraday) where the informed/fast trader eats the first move before a retail order fills — that's where this test bites hardest.

> Costs are retail-scale round-trip estimates; single-horizon (6M); survivorship-biased universe; no borrow cost on the short/avoid leg. Research, not investment advice.