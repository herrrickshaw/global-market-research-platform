# Why these filters win — the economics behind the fat pitches

A backtest tells you *that* something worked; it doesn't tell you *why*, and a "why" you
can't explain is usually overfitting. This document gives the economic/behavioural mechanism
for each winning filter, why it wins **in the markets where it wins**, what data we actually
evaluated it on, and the literature the reasoning rests on. Read it with
[`EDGE_MATRIX.md`](EDGE_MATRIX.md) (the grid) and [`METHODOLOGY.md`](METHODOLOGY.md) (the stats).

---

## 1. Value-reversion (cheap-vs-peers) — the widest edge (IN, US, KR, JP)

**Background.** Buy stocks trading cheap relative to peers or the market (low P/E, low P/B),
betting the discount narrows. This is Graham-&-Dodd value, formalised as the HML factor by
Fama & French (1992) and the P/E effect by Basu (1977).

**Why it wins (mechanism).** The edge is **behavioural mispricing, not risk compensation.**
Investors *over-extrapolate*: they project recent bad news too far into the future and punish
cheap stocks below fair value; when fundamentals reassert, the multiple mean-reverts up.
Lakonishok, Shleifer & Vishny (1994) showed value stocks are **not** fundamentally riskier —
the market simply mis-extrapolates their growth. De Bondt & Thaler (1985) documented the
long-horizon overreaction that value exploits. Our own **convergence test corroborates the
mechanism directly**: rich P/Es fall toward the median and cheap P/Es rise toward it (not just
the returns — the *multiple itself* converges).

**Why IN/US/KR/JP but NOT China.** The correction needs a marginal trader who eventually
prices on fundamentals — institutions, analysts, arbitrageurs. India, US, Korea and Japan
have enough of that. **China is ~80% retail turnover, momentum/theme-driven**, with weaker
fundamental anchoring — so in China the multiple *converges* (rich de-rates) but prices
**don't reward** the cheap side (our tested result: cheap−rich ≈ 0, t 0.04). The anomaly is
an *institutional-correction* effect, and it fades where the marginal trader doesn't correct.
This matches evidence that emerging/retail-dominated markets show weaker fundamental anomalies
(Carpenter, Lu & Whitelaw, 2021, on China's evolving efficiency).

**Data evaluated / caveats.** Survivorship-biased universes → we read **spreads, not levels**;
fundamentals lagged to filing dates (point-in-time); 6-month, non-overlapping observations.
Coverage is 50–90% depending on market; **Japan's panel is the Sakana EDINET-Bench task-sample
(~1,437 names)** so its *magnitude* (t 4.84) may be biased even though direction/significance
are decisive. US value **fades from 3M (t 2.3) to 6M (t 1.2)** — short-horizon only.

**Literature.** Basu (1977); Fama & French (1992); De Bondt & Thaler (1985); Lakonishok,
Shleifer & Vishny (1994).

---

## 2. Value + Quality long/short — Korea's standout (+4.8%/6M, t 4.2)

**Background.** Long stocks that are **cheap *and* high-quality** (high ROE), short those that
are **expensive *and* low-quality** ("hollow" glamour). This is the quality-value combination:
Piotroski (2000), Novy-Marx (2013) gross profitability, Asness-Frazzini-Pedersen "Quality
Minus Junk" (2019).

**Why it wins (mechanism).** The market **underpays for quality** — durable high-ROE
franchises earn more than their price implies (Novy-Marx 2013; Fama-French 2015 RMW factor).
Combining it with cheapness ("quality at a reasonable price") stacks two independent
mispricings. The short leg — expensive companies with no earnings power to justify the price —
de-rates as the glamour fades. So the long and short both mean-revert, and the *spread*
captures both.

**Why Korea specifically.** Two reasons. (1) The **"Korea discount"**: Korean equities trade
at persistently low multiples (chaebol governance, low payout) — and *within* that compressed
range, high-ROE-yet-cheap names are especially mispriced. (2) Korea is a **mean-reverting**
market (our regime finding), so the full round-trip long/short works — unlike India, where
**momentum runs the short leg over** (India value+quality L/S = −1.0%, a red cell), because a
trending market keeps bidding up the "expensive" names you're short.

**Data evaluated / caveats.** DART XBRL fundamentals (~2016–2019 onward); **the short leg needs
a locate and pays borrow** (thin small-caps especially) — the +4.8% is gross of that. The
t 4.2 is on the recent window; the deeper window is weaker (t ~1.5), so some of the strength is
recent-regime-specific.

**Literature.** Piotroski (2000); Novy-Marx (2013); Fama & French (2015); Asness, Frazzini &
Pedersen (2019).

---

## 3. Momentum / trend — the universal survivor (IN, KR, EU)

**Background.** Buy recent winners (12-month momentum, 52-week-high breakouts, 50>200-day
golden cross). Jegadeesh & Titman (1993); it is the one factor that survives our Deflated-
Sharpe multiple-testing in three markets.

**Why it wins (mechanism).** **Under-reaction.** Investors update slowly to news, so prices
*drift* in the direction of information rather than jumping to fair value (Hong & Stein 1999,
gradual information diffusion). Herding and positive-feedback trading extend the drift.
Moskowitz, Ooi & Pedersen (2012) showed the same trend persistence across virtually every asset
class — a pervasive, robust effect, which is why it survives multiple-testing where fragile
factors don't.

**Why IN/KR/EU — and why it FAILS in Japan / for US-fragile.** Momentum needs a **trending**
market character. India is strongly trending (retail flow + structural growth) → trend is our
single most robust factor (DSR 0.994). Korea and Europe trend enough in the bull regime. **Japan
is mean-reverting, not trending** — so no momentum factor survives (DSR 0.86, fails); a
trend-follower gets whipsawed there. **US momentum is fragile** (DSR 0.90, below the 0.95 bar):
the US momentum premium has decayed and is prone to crashes (Daniel & Moskowitz 2016), and
crowding/publication has eroded it (McLean & Pontiff 2016).

**Data evaluated / caveats.** 6–10-year windows; Deflated Sharpe corrects for the 10 factor
variants tried (Bailey & López de Prado 2014); the paper-track darvas/golden-cross cells are
*short-horizon per-signal* excess, not 6-month spreads (compare within a row, not across).

**Literature.** Jegadeesh & Titman (1993); Hong & Stein (1999); Moskowitz, Ooi & Pedersen
(2012); Daniel & Moskowitz (2016); Asness, Moskowitz & Pedersen (2013), *Value and Momentum
Everywhere*.

---

## Why the losers lose (justifying the red cells)

- **China value fails** — retail/momentum market, weak fundamental anchoring: the multiple
  converges but prices don't reward it (tested null, t 0.04). Mechanism above.
- **US Piotroski is *inverted*** — the F-score premium lives in "small, illiquid, low-analyst-
  coverage value stocks" (Piotroski 2000). In the liquid US large-cap slice we tested it
  reverses, consistent with our own finding that **the edge is illiquidity, not size** — screen
  the liquid tail and the quality premium isn't there to harvest.
- **Japan momentum / India shorts fail** — *market character*. A factor run against a market's
  character (momentum in mean-reverting Japan, shorting in trending India) whipsaws.

---

## Overarching caveats (data + method)

1. **Survivorship bias** — dead names are gone; we read spreads, which cancel the market-wide
   bias, never absolute levels.
2. **Point-in-time, but restatement risk** — we lag to filing dates; the summary figures can be
   restated versions.
3. **Gross of costs, small capacity** — before impact (Almgren-Chriss) and borrow; the edge is
   illiquidity-driven (~$300–500k capacity, Amihud 2002), i.e. retail-scale.
4. **The factor zoo is real** — Harvey, Liu & Zhu (2016) show most *published* factors are
   false positives; we apply the Deflated Sharpe correction precisely because of this, which is
   why only three technical factors survive and most cells are grey or red.
5. **Coverage / sample selection** — per market, flagged in `data_sufficiency.md`; Japan is a
   task-sample, China is 12–18% covered (collection ongoing).
6. **Anomaly decay** — McLean & Pontiff (2016): edges shrink after publication; our estimates
   are historical, not guarantees.

---

## The honest meta-point (our data vs the literature)

Reassuringly, our results **replicate the canonical literature** — value, momentum and quality
all show up where theory says they should. That's a feature: an edge with no published
mechanism would more likely be overfitting. **Our contribution is not a new factor** — it is the
**cross-market *character* mapping** (which known factor fits which market) and the **honest
nulls** (China value, Japan momentum) where the market's character breaks the mechanism. The
literature is overwhelmingly US/developed-market; the value here is testing *where those
mechanisms travel and where they don't.* Sakana's EDINET-Bench provides external corroboration
from a different method entirely: their finding that a naive persistence (momentum) baseline is
hard for even frontier LLMs to beat echoes our "momentum is the universal survivor."

> Descriptive research and education only — not investment advice.
