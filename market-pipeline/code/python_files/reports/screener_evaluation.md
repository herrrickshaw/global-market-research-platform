# Evaluating screener.in's popular Indian screens — effective or just popular?

Scored against this project's India backtests: **trend** (DSR 0.994, PRIMARY), **value-reversion** (+5.3%/6M, t2.5), **quality** (premium behind the liquidity gate), and the key finding that **the edge is illiquidity, not size** — so a market-cap floor fights the edge. India is long-only.

| screen | family | verdict | effectiveness | why |
|---|---|---|--:|---|
| Golden Crossover (50>200 DMA) | trend | 🟢 EFFECTIVE | 9.0/10 | our PRIMARY India edge — trend survives Deflated Sharpe (0.994); no size cap |
| Magic Formula (ROCE + earnings yield) | quality+value | 🟢 EFFECTIVE | 7.5/10 | combines the two validated factors; Greenblatt travels to India; no cap floor |
| Value Stocks (hi OPM/ROCE, low D/E) | quality+value | 🟢 EFFECTIVE | 7.5/10 | targets validated quality+value, keeps the illiquid tail where the edge lives |
| High Growth + High RoE + Low PE | quality+value+growth | 🟢 EFFECTIVE | 7.0/10 | multi-factor sweet spot; all three validated in India |
| The Bull Cartel (quarterly growth) | earnings momentum | 🟢 GOOD | 6.5/10 | earnings momentum aligns with India's momentum character; can be crowded/priced |
| Growth Stocks (GARP / G-Factor) | growth+quality | 🟢 GOOD | 6.0/10 | growth+quality tilt; India is momentum-friendly, but GARP crowds |
| Low on 10Y Avg Earnings (Graham) | deep value | 🟡 MODERATE | 6.0/10 | value reverts in India, but absolute deep-value catches value traps (use sector-relative) |
| Piotroski Scan (F = 9) | quality | 🟡 MODERATE | 5.5/10 | quality earns a premium BUT F-score alone is weak without the liquidity gate (US F is inverted) |
| FII Buying (institutional flow) | flow / sentiment | 🟡 MODERATE | 5.5/10 | FII flow chases momentum (some signal) but you follow the lag; short-lived, front-run-able |
| Benjamin Graham & Buffett (sales>₹250cr) | value + size floor | 🟡 MODERATE | 4.5/10 | value works, but the sales floor starts excluding the illiquid tail where the edge is strongest |
| Highest Dividend Yield | dividend / value | 🔴 WEAK | 4.5/10 | dividend-capture is weak; high-DY in India skews to low-growth PSU value traps |
| Bluest of the Blue Chips (mcap>₹3000cr) | large-cap value | 🔴 WEAK | 2.5/10 | the large-cap FLOOR kills the illiquidity edge — big Indian names are efficiently priced; popular but the worst place to find mispricing |

## The pattern — popularity ≠ effectiveness

- **Most effective:** *Golden Crossover* (our validated PRIMARY trend edge) and the multi-factor **quality+value screens without a size cap** (Magic Formula, Value Stocks, High-Growth-High-RoE-Low-PE). These target exactly the factors that survive our tests.
- **The big trap — blue-chip / size-floor screens.** *Bluest of the Blue Chips* (mcap>₹3000cr) and Graham-Buffett (sales>₹250cr) are hugely popular, but our cost/capacity research shows India's mispricing lives in the **small, illiquid** tail — large caps are efficiently priced. A size floor systematically removes the edge. **Popular, but structurally weak.**
- **Weak regardless of popularity:** *Highest Dividend Yield* (dividend-capture is weak; PSU value-trap skew), *FII Buying* (you follow the lag of a momentum chase).
- **Use with a fix:** *Piotroski F=9* and *Graham deep-value* work **only** when run behind the **liquidity gate** and made **sector-relative** — raw versions catch traps.

## How to actually use them (India playbook alignment)

1. **Base signal:** Golden Crossover (trend) — the PRIMARY India edge.
2. **Overlay:** one quality+value screen *without a market-cap floor* (Magic Formula or Value Stocks), run **behind the liquidity gate** (tradeable but not mega-cap).
3. **Confirm:** sector-relative cheapness (not absolute deep-value) to dodge value traps.
4. **Never** filter to blue-chips only, never short, size by inverse-vol, ~₹300–500k capacity before the edge decays.

> Verdicts are grounded in this repo's committed India backtests (`deflated_sharpe`, `valuation_reversion`, cost/capacity study), not a fresh backtest of each screen's exact query. Research, not investment advice.