# How the system evaluates metrics

Every number the platform screens on, with its **exact definition as implemented**,
where the inputs come from, and the source the definition is taken from.

This is the per-metric companion to [`METHODOLOGY.md`](METHODOLOGY.md), which covers
strategy-level inference — power, multiple-testing, coverage. Read that for *whether a
result is trustworthy*; read this for *what the number means*.

> ⚠️ Descriptive research and education only — **not investment advice.**

A definition here is only listed once it has been checked against the code that
computes it. Where implementation deviates from the canonical definition, the
deviation is stated rather than glossed — an undocumented deviation is how a
screen silently stops measuring what its name claims.

---

## 1. Earnings and valuation

### EPS — earnings per share

```
EPS = (net income − preferred dividends) / weighted-average common shares
```

- **Numerator** `net_income_to_common` = `us-gaap:NetIncomeLoss` (or IFRS `ProfitLoss`)
  minus `PreferredStockDividendsAndOtherAdjustments` /
  `PreferredStockDividendsIncomeStatementImpact` / `DividendsPreferredStock`.
  Absent any preferred tag the adjustment is **zero**, not unknown — most filers have
  no preferred stock, and treating "not reported" as "unknown" would null out earnings
  for all of them.
- **Denominator** `shares`, in priority order, with the winning tag recorded in
  `shares_basis`:

  | `shares_basis` | tag | note |
  |---|---|---|
  | `diluted` | `WeightedAverageNumberOfDilutedSharesOutstanding` | preferred; the EPS denominator proper |
  | `basic` | `WeightedAverageNumberOfSharesOutstandingBasic` | a *different statistic*, not a fallback of convenience |
  | `period_end` | `CommonStockSharesOutstanding` | an approximation — EPS is a weighted average |
  | `issued` | `CommonStockSharesIssued` | last resort |

  A cover-page `dei:EntityCommonStockSharesOutstanding` count is used only within
  **400 days** of the fiscal year end. Beyond that it is discarded and `shares` is
  `None`: a wrong EPS is acted on, a missing one is merely missing.

**Why preferred dividends matter.** Omitting them overstates earnings available to
common for every issuer with preferred stock — banks, insurers and REITs routinely —
and an overstated EPS *understates* PE, making exactly those names look cheaper than
they are. Measured on FY2025: WFC 6.58 → 6.26 (4.9% overstated), BAC 3.97 → 3.78 (4.8%).

**Validation.** Computed EPS is checked against each filer's **own reported**
`us-gaap:EarningsPerShareDiluted` for the same fiscal year. Agreement to within 0.7%
across WFC, BAC, AAPL, XOM, UNH, GOOGL, JPM. Agreement with the audited figure is the
strongest validation available, and before the preferred-dividend fix WFC was out by 5%.

*Source:* standard accounting definition of basic and diluted EPS — see
[Corporate Finance Institute](https://corporatefinanceinstitute.com/learn/resources/valuation/earnings-per-share-eps-formula)
and [Wall Street Prep](https://www.wallstreetprep.com/knowledge/earnings-per-share-eps/).
Empirically anchored to the filers' own XBRL.

### PE, PB, earnings yield

```
PE            = close / EPS
PB            = market cap / book equity          (book = stockholders' equity)
earnings yield = 1 / PE                            (build_all_ratios.py:81)
```

Prices come from the **live per-ticker OHLC tree** the scan writes, not from any
standing panel — until 2026-08-20 US ratios were priced off an orphan file four days
stale. Outliers are nulled rather than kept (`pe ≤ 0 or > 1000`, `pb ≤ 0 or > 200`,
`|roe| > 3`): a PE of 4,000 is a data error, and carrying it poisons any cross-sectional
percentile.

### ROE, ROCE

```
ROE  = net income / book equity
ROCE = EBIT / capital employed
```

**ROCE is India-only.** Only the screener.in feed carries EBIT *and* capital employed;
for US/KR it stays `NULL` rather than being approximated from total liabilities. An
approximated ROCE that looks like a real one is worse than a gap.

### Cash Conversion Cycle (CCC)

```
DSO = receivables / revenue          × 365     days sales outstanding
DIO = inventory   / cost_of_revenue  × 365     days inventory outstanding
DPO = payables    / cost_of_revenue  × 365     days payables outstanding

CCC = DSO + DIO − DPO
```

Days between paying for inputs and collecting for output. **Negative is strong** —
the business is funded by its suppliers and customers rather than by capital.

**Computed from filings**, not scraped ([`cash_conversion_cycle.py`](../cash_conversion_cycle.py)):

| precedence | source |
|---|---|
| 1 | **filings** — SEC EDGAR `companyfacts` (US), the yfinance fundamentals store (India) |
| 2 | screener.in screen `228040` — **fallback only**, and only for tickers filings cannot cover |

Every row carries the source that produced it, and the brief renders it, so a
scraped number is never indistinguishable from a computed one.

*Validation:* Apple computes to **−71.1 days** on FY2025 filings and Walmart to
**+2.8** — both match their well-known figures. The decomposition is reported too
(AAPL: DSO 34.9, DIO 9.4, DPO 115.4), which the scraped total never gave.

🔴 **NaN is a result.** Some filers have no conventional cost-of-goods line —
Exxon reports `CostsAndExpenses` and sector-specific `EnergyRelatedInventory*`,
with no generic inventory or COGS tag. Substituting total expenses would yield a
confidently wrong DIO and DPO. A missing CCC is visibly missing; an invented one
is not. Cycles beyond ±3 years are nulled as accounting artefacts.

*Why this changed (2026-08-21):* CCC was previously taken whole from a single
screener.in page, with a silent fallback to a cached parquet of unstated vintage.
That one endpoint broke step `[6/13]` of the daily run twice in three days — once
on a 25s timeout, once by running 29 minutes and hitting its cap. A source that
must answer at 03:00 for a section to render is a source that decides whether the
section renders.

---

## 2. Quality composite

### Piotroski F-Score (0–9)

Nine binary signals across profitability, leverage/liquidity and operating efficiency,
implemented in [`strategies/piotroski.py`](../strategies/piotroski.py):

| # | signal | implemented as |
|---|---|---|
| 1 | ROA positive | `roa > 0` |
| 2 | Operating cash flow positive | `cfo > 0` |
| 3 | ROA improving | `roa > roa_prev` |
| 4 | Accruals — cash beats profit | `cfo > net_income` |
| 5 | Leverage falling | `debt_to_assets < prev` |
| 6 | Current ratio rising | `current_ratio > prev` |
| 7 | No new equity issued | `shares <= shares_prev` |
| 8 | Gross margin rising | `gross_margin > prev` |
| 9 | Asset turnover rising | `asset_turnover > prev` |

Signal 4 is the paper's accrual test in level form: Piotroski defines it as
`CFO/assets − ROA > 0`, which reduces to `CFO > net income`.

**Documented deviation.** Signal 7 defaults to **true** when share-count history is
missing, rather than penalising absent data — kept consistent across every production
scan so one stock cannot score differently depending on which implementation saw it.
Measured 2026-08-20: this awards a free point to **12% of US tickers** (801 of 6,809).
Treat an F-Score of exactly 9 on a name with no share history as an 8.

*Source:* `piotroski2000` — Piotroski, J.D. (2000), *Value Investing: The Use of
Historical Financial Statement Information to Separate Winners from Losers*,
Journal of Accounting Research 38, 1–41. The paper's own finding — benefit concentrated
in small/medium firms with low share turnover and no analyst following — is why this
platform pairs the score with a liquidity tier rather than screening on it alone.

---

## 3. Price and trend

| metric | definition |
|---|---|
| `EMA50` | 50-period exponential moving average of close |
| `DMA50`, `DMA200` | 50- and 200-day *simple* moving averages |
| `GC_Signal` | golden cross — `DMA50` crossing above `DMA200` |
| `RSI` | Wilder 14-period relative strength index |
| `Above_EMA50` | `close > EMA50` |
| `Rel_Volume` | volume ÷ its own trailing average |

### Darvas Box

`box_top` is the highest high that has stood unbeaten for the confirmation window;
`box_bottom` is the lowest low *after* the index at which `box_top` was set — so the
box is anchored to the top, not fitted around the whole window. A breakout is a close
above `box_top`; `box_bottom` is the natural stop.

🔴 **The current bar is excluded from box formation.** Including it lets a stock break
out of a box its own breakout defined.

Reported alongside: `Upside_to_Top%`, `Position_in_Box%`, `Compression_Ratio`.

*Source:* Darvas, N. (1960), *How I Made $2,000,000 in the Stock Market* — the original
box method: track stocks making new highs, draw the box around the consolidation, buy
the breakout above the upper boundary, stop just below the lower.

---

## 4. Liquidity

Two different questions, deliberately answered differently:

```
FLOOR  = "is this tradeable at all?"   -> ABSOLUTE  (a currency amount)
TIERS  = "how liquid, relative to its
          own market?"                 -> PERCENTILE (within market)
```

- **Structural floor** — USD 10k median daily turnover, every market.
- **Policy floor** — ₹1 crore/day (~USD 120k) for **India only**.
- **Tiers** — percentile within the market's own distribution
  ([`adaptive_liquidity.py`](../adaptive_liquidity.py)).

A single USD constant used as a *tier* boundary is four different percentile filters
across five markets: USD 600k is US mid-cap but Indian large-cap. That is why the old
uniform USD 120k tiering put 94% of a US sample in one bucket, and why tiers are now
percentile-based while floors stay absolute.

*Source:* `amihud2002` — Amihud, Y. (2002), *Illiquidity and stock returns:
cross-section and time-series effects*, Journal of Financial Markets 5, 31–56.
Liquidity is treated as a conditioning variable, not a signal.

---

## 5. Data freshness — the metric behind every other metric

A price is only as good as the **session it belongs to**. The platform grades data by
the trading session it *contains*, never by file mtime, filename or row count — all
three of which were correct on 2026-08-19 while the brief quoted prices two days old.

```
expected_session(mkt, at) = newest session that has both CLOSED and been PUBLISHED as of `at`
```

- Each venue carries a close time **and a publication lag** (NSE bhavcopy +2h30;
  yfinance daily bar +1h30). Before the lag elapses the answer is the *previous*
  session — asking for a bar the source has not finished publishing is how a partial
  bar gets quoted as a close.
- Holidays come from `exchange_calendars` (XBOM, XNYS, XTKS, XKRX, XETR, XSHG),
  validated against the live NSE list — **0 disagreements across all weekdays of 2026**.
- Multi-unit stores are probed at the **median** symbol, never the maximum: max-like
  logic let 66% staleness read as "fresh, 0d".
- A scan's session is recovered from **its own prices**, matched against dated bars —
  filename and mtime agreed with each other and both were wrong.

Content checks that run beside freshness ([`price_quality.py`](../price_quality.py)):
flatline (carry-forward detection), coverage over the *active* universe, structural
range validity (`close ≤ 0`, `high < low`, close outside its own range), duplicate
`(symbol, session)`, nulls, and gaps against the real trading calendar.

---

## Sources

| ref | used for |
|---|---|
| Piotroski (2000), *J. Accounting Research* 38:1–41 | F-Score, and its small-cap/low-turnover conditioning |
| Darvas (1960), *How I Made $2,000,000 in the Stock Market* | box construction and breakout rule |
| Amihud (2002), *J. Financial Markets* 5:31–56 | illiquidity as a conditioning variable |
| Fama & French (1992, 1993, 2015) | value/size factor structure |
| Jegadeesh & Titman (1993) | momentum horizon selection |
| Bailey & López de Prado (2014) | Deflated Sharpe — the multiple-testing gate |
| Harvey, Liu & Zhu (2016) | why a t-stat of 2 is not enough |
| SEC XBRL `companyfacts` (`data.sec.gov`) | every US fundamental; tag names are exact, never fuzzy-matched |

Full BibTeX: [`references.bib`](../references.bib) (93 entries). Citations are gated in
CI by `cite_check.py` — an unknown citation fails the build, which is how two fabricated
references were caught and removed in the 2026-08 literature audit.
