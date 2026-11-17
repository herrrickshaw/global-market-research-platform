# Bond–equity linkage — literature check, and what our measurement missed

Companion to `bond_equity_linkage.md` (the computed result). This records what the
literature says, why our one durable finding has a well-developed theory behind it,
and — importantly — **a channel our carry test could not have detected by construction.**

## 1. The correlation regime shift has a theory, and it matches our numbers

Our measurement found the stock–bond correlation flipping twice: +0.34 (1990s),
−0.23 to −0.41 (2000–2021), +0.05 (2022–2026). Campbell, Pflueger & Viceira supply
the mechanism, and it is not about bonds at all — it is about **which kind of shock
dominates**:

| shock regime | inflation vs output gap | what a downturn does | stock–bond corr |
|---|---|---|---|
| **Demand-shock world** (≈2001–2021) | move together | recession → disinflation → rate cuts → bonds rally as stocks fall | **negative** — bonds hedge |
| **Supply-shock world** (1980s–90s, 2022–) | move oppositely | inflation scare → higher yields *and* weaker growth; central bank tightens into weakness | **positive** — both fall |

Campbell et al. find the inflation/output-gap correlation was negative ~1979–2001,
then turned positive, and the stock–bond correlation changed sign alongside it. The
2008 and 2020 crises were growth shocks with disinflation, which permitted easing and
reinforced the hedge. 2022 was an inflation shock that forced tightening — a common
headwind to both assets, and the reason 60/40 failed that year.

**This is why our selloff event study found no era-independent answer.** "What happens
to equities in a bond selloff" is underdetermined until you know which shock regime
you are in. Our conditional split (selloffs under negative vs positive prevailing
correlation) was reaching for this, though at n=27/19 it could not resolve it.

## 2. 🔴 What our carry test could NOT detect

`bond_equity_entropy.py --carry` used the **US 3-month bill** as the funding-cost
proxy and found no borrow-and-trade channel — if anything the reverse (dearest funding
quintile had the highest forward returns, procyclical).

**That result is scoped to DOMESTIC USD funding, and does not rule out the carry trade
that actually moves equity markets, which is CROSS-CURRENCY.** A yen-funded trade
borrows at the BoJ's rate, not the Fed's. Our funding proxy moves with the wrong
central bank, so the test was structurally blind to it — this is a limitation of the
measurement, not evidence of absence.

### The mechanism, and the clearest recent evidence

Borrow in a low-rate currency (yen, historically also CHF), convert, buy higher-yielding
assets. Profit is the rate differential plus any carry-asset return; the risk is that
the funding currency appreciates. Leverage via FX forwards and futures amplifies both.

August 2024 is the cleanest natural experiment on record:

- **31 Jul 2024**: BoJ unexpectedly hiked 0.1% → 0.25%.
- **2 Aug**: weak US payrolls (114k vs 175k expected) raised Fed-cut odds, compressing
  the differential from the other side.
- **29 Jul – 5 Aug**: yen appreciated ~**6.15%**.
- **5 Aug**: Topix and Nikkei fell **>12%** — the steepest single day since 1987 — and
  the S&P 500 fell 3%.

The self-reinforcing part is the bit that matters for risk: margin calls force
position closure, closing means buying back yen, which appreciates the yen further,
which triggers more margin calls. Estimates of the trade's size ran as high as
**$4 trillion**, though such figures are inherently loose.

Note what this does to our framing: the equity drawdown was not caused by a *bond
selloff*. It was caused by a **funding-rate convergence** in a different currency.
That channel is invisible to a US-yield-based analysis.

## 3. Why the option re-emerged post-recovery — and where it stands

Carry is a function of **policy divergence**, and the post-pandemic normalisation
produced exactly that: the Fed hiked aggressively into the 2022 inflation shock while
the BoJ held ultra-easy policy far longer. The wider the differential, the larger the
carry incentive — so the trade was not a market quirk but a direct consequence of
central banks being in different places in their cycles.

State of play in reporting through 2025–2026 (secondary sources, not verified against
data here):

- The BoJ has ended 17 years of ultra-easy policy, but the yen has stayed weak enough
  to keep the trade viable.
- Dec 2025: the 10-year JGB yield reportedly reached a 25-year high with the curve
  steepening and the MoF verbally supporting the yen — pressure on the trade from the
  funding side.
- Mid-2026: carry reported as **regaining momentum** on renewed divergence, with a more
  hawkish Fed priced against a BoJ expected to hold.

**The structural point:** carry unwinds are not gradual. They are convex — quiet
accumulation punctuated by violent liquidation when the differential compresses or the
funding currency jumps. That asymmetry is exactly what a correlation or a linear
regression on daily data will understate, which is a second reason our section 4 found
nothing.

## 4. What this makes testable

The channel is measurable with data we can fetch (`USDJPY=X`, `^N225` via yfinance,
plus JGB yields):

1. **Funding differential**: US 3m minus JP 3m (or policy rates) as the true carry
   incentive, replacing our domestic-only proxy.
2. **Carry-unwind events**: sharp yen appreciation (e.g. weekly move beyond the 95th
   percentile) as the event, with forward global equity returns measured against an
   unconditional baseline — the same event-study frame as `--selloff`, pointed at the
   right variable.
3. **Convexity check**: whether equity responses to yen moves are asymmetric — muted on
   depreciation, severe on appreciation. A linear correlation would average these to
   roughly nothing, which may be precisely what our null result did.

Until that is run, the honest statement is: **we found no domestic-funding carry
channel, and we did not test the cross-currency one.**

## Sources

- [Campbell, Pflueger & Viceira, *Bond-Stock Comovements*](https://campbell.scholars.harvard.edu/sites/g/files/omnuum5881/files/2025-08/CampbellPfluegerViceira_ARFE_20250820.pdf) ([NBER w34323](https://www.hbs.edu/ris/Publication%20Files/w34323_82e235d8-99d9-4166-9081-b7e85ab53a76.pdf))
- [Pflueger, *Risk, Return, and the Term Premium in Treasury Bonds*](https://cpflueger.github.io/carolinpflueger_repository/Pflueger_NBERCorporateAssociates2026_v2.pdf)
- [Empirical Evidence on the Stock–Bond Correlation (FAJ)](https://www.tandfonline.com/doi/full/10.1080/0015198X.2024.2317333)
- [Econofact, *When Do Stocks and Bonds Move Together?*](https://econofact.org/when-do-stocks-and-bonds-move-together-and-why-does-it-matter)
- [BIS Bulletin 90, *The market turbulence and carry trade unwind of August 2024*](https://www.bis.org/publ/bisbull90.htm)
- [CNBC, *Carry trades: a major unwinding is underway amid a stock sell-off*](https://www.cnbc.com/2024/08/05/carry-trades-a-major-unwinding-is-underway-amid-a-stock-sell-off.html)
- [Consumption Growth Persistence and the Stock–Bond Correlation (JFQA)](https://www.cambridge.org/core/services/aop-cambridge-core/content/view/555E3CC9EB81295E1E68959559EBF15C/S002210902400019Xa.pdf/consumption_growth_persistence_and_the_stockbond_correlation.pdf)
