# Where's the edge? The fat-pitch grid (filter × market)

![edge matrix](../reports/edge_matrix.png)

Ted Williams mapped his batting average to every zone of the strike zone and only swung at
pitches in his .400 zone. Warren Buffett borrowed it for investing: **wait for the fat
pitch — you don't have to swing at everything.** This grid does the same for our strategies:
each cell is the backtested (or paper-track) edge for running that filter in that market.

- 🟩 **green = your .400 zone** — a validated edge; swing.
- 🟥 **red = the .230 corner** — tested and it fails or loses; take the pitch.
- ⬜ **grey = not enough data** — keep the bat on your shoulder until the data arrives.

Built by `edge_matrix.py` from this repo's committed backtests (value-reversion,
value+quality long/short, momentum via Deflated Sharpe) plus the paper-track
(darvas / golden-cross). Machine-readable in `reports/edge_matrix.csv`.

## The fat pitches (swing)

| market | pitch | edge |
|---|---|---|
| **Japan** | value-reversion | **+6.6%/6M, t 4.8** — the juiciest on the board |
| **Korea** | value+quality L/S · breakout | +4.8% t4.2 · DSR .99 |
| **India** | value-reversion · trend | +5.3% t2.5 · DSR .99 |
| **US** | value-reversion (≤3M) | +1.7%/3M t2.3 |
| **Europe** | momentum | DSR .98 |

## The cold corners (take the pitch)

- **China value-reversion** — tested, ≈0, *fails* (the multiple converges but doesn't pay).
- **India value+quality L/S** and **India darvas** — both lose (India punishes shorts/breakouts).
- **US Piotroski** — *inverted* (high-quality underperforms in the US).
- **Japan momentum** — no factor survives multiple-testing.

## The meta-lesson

The green clusters into **two rows**: **value-reversion** (green in IN/US/KR/JP — fails only
in China) and **momentum/trend** (green in IN/KR/EU). Everything else is mostly grey or red.
So the whole platform's edge reduces to a simple rule: **swing at value-reversion in
IN/US/KR/JP and momentum in IN/KR/EU; take every other pitch.** Value-reversion is the widest
fat zone — if you master one pitch, that's it.

## Caveats (compare within a row, not across)

- Value cells are **6-month spreads**; darvas/golden-cross cells are **short-horizon
  paper-track excess** — different pitch speeds, so read down a row, not across horizons.
- The **paper-track only ever swung at the technical pitches** — it never traded
  value-reversion, which is why India's live ledger looked weak. Wiring value-reversion into
  live signal generation is what would let the P&L swing at the fattest pitch.

> Every cell traces to a committed backtest or the paper-track. Not investment advice.
