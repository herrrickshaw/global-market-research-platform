# Evaluating 70 trading strategies (strike.money) through this project's evidence

Two axes decide whether *you* can profit: **durability** (does the edge survive multiple-testing?) and **retail accessibility** (can you run it, or does it need the speed/data advantage we measured as the information-asymmetry tax?). Win-rate claims are ignored — our confusion-matrix test showed the edge is *magnitude*, not hit-rate.

## ✅ The harvestable set (durable AND retail-accessible)

| strategy | family | access | durability | why (our evidence) |
|---|---|--:|--:|---|
| Factor Investing (value/mom/quality) | systematic | 9 | 8 | our core: value-reversion + momentum survive DSR (IN/US/KR/JP) |
| Mean Reversion (value, monthly) | systematic | 9 | 8 | value-reversion +5-6%/6M where fundamentals rule; fails in China |
| Momentum / Trend-Following | systematic | 8 | 7 | survives DSR in TRENDING markets (IN/KR/EU); whipsaws in JP |
| Position Trading | systematic | 8 | 7 | long-horizon trend; capacity-friendly, low info-tax |
| Pairs / Stat-Arb / Cointegration | systematic | 6 | 6 | real mean-reversion of spreads but crowded + execution-sensitive |
| Dollar-Cost Averaging | passive | 10 | 6 | market beta not alpha, but robust + zero info-tax |
| Portfolio Rebalancing | passive | 9 | 6 | harvests mean-reversion; Sharpe +0.2-0.5 plausible |
| Risk Parity | passive | 8 | 6 | vol-weighted diversification; robust, not an alpha |
| Insider Sentiment | event | 7 | 6 | documented 6-12mo outperformance; retail-accessible via filings |

## 🔴 Real edge, but NOT for you (privileged — you're the counterparty)

| strategy | access | durability | why |
|---|--:|--:|---|
| HFT / Latency Arb | 1 | 8 | real but pure speed advantage — retail is the prey, not the hunter |
| Market Making | 1 | 7 | earns the spread — needs colocation + inventory tech |
| Basis / Funding-rate Arb | 3 | 6 | convergence is predictable; needs scale + low cost |
| Arbitrage (classic) | 3 | 6 | 0.1-0.5%/trade, 70-90% hit — but competed to zero without speed |
| Order Flow / Tape Reading | 2 | 5 | the informed side of our info-asymmetry tax |

## ⚠️ Retail-accessible but no durable edge (the win-rate traps)

| strategy | access | durability | why |
|---|--:|--:|---|
| Options Buying (OTM) | 6 | 1 | 80-90% of NSE OTM buyers lose — negative edge |
| Dividend Capture | 6 | 2 | price drops ~by the dividend; weak after tax |
| Price Action / Candlesticks | 7 | 2 | fails multiple-testing; VLM study: only short-horizon, regime-bound |
| Fibonacci Retracement | 7 | 2 | no robust out-of-sample edge; arbitrary levels |
| Smart Money Concepts | 7 | 2 | narrative, not a tested edge |
| Reversal Trading | 7 | 2 | 41% win-rate (their own number) — negative expectancy |
| Seasonal Trading | 8 | 2 | mostly data-mined; multiple-testing kills most |
| Social / Copy Trading | 8 | 2 | no durable edge; you copy the lag |
| Range Trading | 7 | 3 | high win-rate but negative skew (small wins, big losses) |
| Crypto / DeFi / Yield / Staking | 6 | 3 | different asset class; yield real but smart-contract + vol risk |

## The three lessons this project proves about that list

1. **Durable edge and retail access rarely coexist.** The top-right corner is nearly all *slow, systematic, magnitude* strategies (value-reversion, momentum, factor, position) — exactly what we validated. Everything fast and durable (HFT, market-making, arb) lives top-left: real, but it *is* the information-asymmetry tax being charged to retail.
2. **Win-rate is a marketing lens.** Range/gap/reversal advertise 41-80% win rates yet carry negative skew; our confusion matrix showed value-reversion wins only ~50% of the time and still profits — magnitude, not frequency.
3. **Speculation strategies work only where speculation rules.** Sentiment/news/technical patterns 'work' in retail-driven, high-uncertainty regimes (and are then arbitraged by the fast) — the same fundamentals-vs-speculation dial from the sector work.

> Scores are judgemental, grounded in this repo's backtests + the cited literature, not a fresh backtest of all 70. Research, not investment advice.