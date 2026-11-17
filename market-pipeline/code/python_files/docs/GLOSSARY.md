# Plain-English glossary

Every technical term used in this project, explained the way you'd explain it to a friend
with no finance or stats background. Analogies in *italics*.

---

## The big ideas (what strategy are we even running?)

- **Stock / equity** — a tiny ownership slice of a company. Its price goes up and down daily.
- **Systematic strategy** — buying and selling by fixed *rules*, not gut feeling. *Like a recipe
  you follow exactly, instead of cooking by instinct.*
- **Factor** — one measurable trait of a stock we bet on. *Like judging used cars by mileage or
  age — each is a "factor."* Our main factors:
  - **Momentum / trend** — stocks that have been rising tend to keep rising. *Winners keep
    winning, for a while.*
  - **Value (mean-reversion)** — unusually cheap stocks tend to drift back up to normal, and
    unusually expensive ones drift down. *A rubber band snapping back to its resting length.*
  - **Quality** — companies that are genuinely profitable and financially healthy.
- **Market character** — the personality of a whole country's market: some *trend* (India), some
  *snap back* (Korea, Japan). Our core idea: **use the strategy that fits the market's personality.**

## Judging if a stock is cheap or expensive

- **Earnings / profit** — what the company actually made after costs.
- **PE ratio (price-to-earnings)** — the price you pay for ₹1 (or $1) of the company's yearly
  profit. *Like paying 15× a shop's annual profit to buy the shop — PE = 15.* Low PE = cheap.
- **PB ratio (price-to-book)** — price versus the company's net worth on paper. Low = cheap.
- **ROE (return on equity)** — profit as a % of the owners' money in the business. *How much
  the company earns on each ₹100 the shareholders put in.* High ROE = a good money-machine.
- **Cheap-for-quality** — cheap **and** a good money-machine at the same time (our favourite combo).
- **Cheap-vs-peers / sector-relative** — cheap compared to *similar* companies, not the whole
  market. *A ₹40 lakh flat is "cheap" only next to other flats in that neighbourhood.*

## How we bet (the mechanics)

- **Long** — you buy, betting the price goes **up**.
- **Short** — you borrow a stock, sell it, and hope to buy it back cheaper — betting it goes
  **down**. *Selling something you don't own yet, planning to buy it later for less.*
- **Book** — your whole set of bets. **Long-only** = only up-bets. **Long/short (L/S)** = up-bets
  on good stocks *and* down-bets on bad ones at the same time.
- **Breakout / 52-week high / Darvas** — buying when a stock pushes above its recent ceiling
  (a momentum signal). **Golden cross (50>200-day average)** — when the short-term average price
  crosses above the long-term one, often read as a trend turning up.

## Testing whether a strategy actually works

- **Backtest** — replaying a rule on years of past data to see if it *would* have made money.
  *Like practising a betting system on last season's matches before risking real cash.*
- **Spread / quintile** — sort all stocks into 5 equal buckets ("quintiles"); the **spread** is
  the top bucket's return minus the bottom bucket's. *The gap between the A-students and the
  D-students.* We report spreads because they cancel out market-wide noise.
- **t-stat (t-statistic)** — a number for "is this result real or just luck?" *Roughly:
  \|t\| above 2 means "probably real," near 0 means "could easily be chance."*
- **Sharpe ratio** — return earned per unit of nerve-wracking ups-and-downs (risk). Higher = a
  smoother ride for the same reward.
- **Deflated Sharpe Ratio (DSR) / multiple-testing** — if you try 100 strategies, a few will look
  great **by pure luck**. DSR discounts for how many you tried. *If 100 people flip coins, someone
  gets 10 heads in a row — that doesn't make them a genius.* We only trust a factor if DSR > 0.95.
- **Statistical power / "underpowered" / non-overlapping observations** — do we have *enough
  independent data points* to trust the t-stat? Overlapping 6-month bets share months and aren't
  truly independent, so we count non-overlapping ones. Fewer than ~15 → "**underpowered**," meaning
  **"we can't tell," NOT "it doesn't work."** *You can't judge a restaurant from one visit.*
- **Null result** — we tested properly and found **no effect**. *A real finding: "this door is
  locked," not "we forgot to check the door."*
- **Flip** — a verdict that changes when better data arrives (Japan went from "can't tell" to
  "works" once we had deep data). The world didn't change — our *evidence* did.

## Data honesty (how backtests fool you if you're careless)

- **Point-in-time (PIT) / look-ahead bias** — only using information you'd *actually* have known
  on that day. *Testing a horse-racing tip using only what was known before the race — not after.*
  Using future data secretly inflates results.
- **Survivorship bias** — the data often only includes companies that *survived*; the failures
  vanished. That flatters returns. We dodge it by reading **spreads** (top-vs-bottom), which cancel
  the bias. *Judging "how safe is skydiving?" by only interviewing people who landed fine.*
- **Coverage / liquid universe** — what fraction of the realistically-tradeable stocks we actually
  have data for. Below ~60% → we flag "coverage caveat" (our sample might be lopsided).
- **Sample selection** — when the data we have isn't a fair random slice (Japan's came from a
  research dataset built for other tasks), so we trust the *direction* but not the exact size.

## Costs, liquidity, and how much money it can hold

- **Liquidity / illiquidity** — how easily you can buy/sell without shoving the price. A big stock
  is liquid; a tiny one isn't. *Selling one house on your street barely moves prices; selling 50
  crashes them.*
- **Transaction costs** — fees, taxes, and the price you move against yourself when trading.
- **Market impact / Almgren-Chriss / square-root** — the bigger your order, the more you push the
  price against yourself; the pain grows roughly with the **square root** of order size.
- **Borrow / locate (for shorts)** — to short a stock you must borrow it and pay a fee; sometimes
  none is available ("no locate").
- **Capacity** — the most money a strategy can handle before it stops working. Ours is small
  (**~$300–500k**) because the edge lives in smaller, less-liquid stocks. *A great parking spot
  that fits one car, not a fleet.*

## Managing risk

- **Volatility** — how wildly a price swings. High volatility = a bumpy ride.
- **Inverse-vol sizing** — put *less* money in wilder stocks, more in calmer ones, so no single
  bet dominates.
- **Vol-target** — dial the whole portfolio's bumpiness to a chosen level.
- **Kill-switch** — an automatic "stop trading" trigger if losses breach a limit. *A circuit
  breaker that flips before the house burns down.*
- **Regime (bull / bear)** — the market's current mood: **bull** = broadly rising, **bear** =
  broadly falling. Some strategies only work in one mood.

## Quality & modelling tools

- **Piotroski F-score** — a 9-point health checklist for a company (profitable? less debt? etc.);
  more points = healthier. (Oddly, in the **US** it works *backwards* in our tests — a reminder
  that what works in one country can fail in another.)
- **Lasso regression** — a statistical method that automatically **keeps only the factors that
  matter** and zeroes out the rest. *A ruthless editor deleting every sentence that isn't pulling
  its weight.*
- **z-score / valuation-z** — how far from average something is, measured in "standard steps."
  *"You're two z-scores taller than average" = unusually tall.* Valuation-z > +1.5 = unusually
  expensive vs peers.
- **Peer clustering** — grouping companies by how their *business* actually behaves (margins,
  growth), instead of official industry labels, to find truer peers.
- **Convergence** — moving back toward the average. We check if an over-priced stock's PE actually
  *falls* toward normal over time.

## Where the data comes from

- **Fundamentals** — a company's financial statement numbers (sales, profit, assets).
- **OHLCV** — daily price data: **O**pen, **H**igh, **L**ow, **C**lose prices + **V**olume traded.
- **Data sources:** **NSE bhavcopy** (India official prices), **SEC EDGAR** (US filings),
  **DART** (Korea filings), **J-Quants** / **EDINET** (Japan filings), **akshare** (China),
  **yfinance** (free global prices). Each is a different "well" we draw from.

## The tools we built

- **RAG (retrieval-augmented generation)** — a question-answering assistant that looks up *our own
  results* and answers in plain language, instead of guessing. *A librarian who only quotes the
  books on the shelf, never makes things up.*
- **TF-IDF** — a simple, no-AI-cost way to find the most relevant paragraph for your question by
  matching important words.
- **Sufficiency gate / data ledger / source registry** — our bookkeeping: is there *enough good
  data* to trust a result, what's on disk, and where each source comes from.

---

*Descriptive research and education only — not investment advice.*
