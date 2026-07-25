# Sakana AI's EDINET-Bench vs. our research

Both touch Japanese financial data, but they answer **different questions** and are
**complementary, not competing**.

## What each one is

| | **Sakana AI — EDINET-Bench** (Jun 2025) | **Our platform** |
|---|---|---|
| **Core question** | *Can LLMs do complex Japanese financial tasks?* | *What factors/strategies produce a validated, tradeable edge in each market?* |
| **Type** | An **AI-capability benchmark** (NLP/ML eval) | A **systematic equity-strategy platform** (quant alpha) |
| **Tasks / output** | Fraud detection, earnings-direction, industry prediction — classification accuracy | Winning strategy per market + backtested earnings + screener + income/balance sheet |
| **Headline finding** | Even SOTA LLMs barely beat logistic regression — LLMs *struggle* at real financial reasoning | Market character decides the playbook; momentum survives multiple-testing, value works only where powered |
| **Data** | **Deep JP-only**: `edinet2dataset` + EDINET-Corpus (≈40k reports, 4,000 cos × 10y, text+BS/PL/CF) | **6 markets** (prices+fundamentals) — but JP was **shallow** (the gap they fill) |
| **Method** | Zero-shot LLM vs logistic/naive baselines, train/test split | Factor backtests, non-overlapping t-stats, **Deflated Sharpe** (multiple-testing), **sufficiency gating**, PIT filing lags |

## Where they resonate (independent corroboration)

- **Simple persistence is hard to beat.** Their "naive_prediction" baseline (this year follows
  last year's earnings trend) is competitive with frontier LLMs on earnings forecasting. That is
  a **momentum/persistence** result — and *our* strongest, multiple-testing-survived finding is
  that **momentum/trend is the one factor that works in nearly every market**. Two very different
  methodologies land on the same place.
- **Complexity doesn't add much.** They show LLMs ≈ logistic regression; we show most elaborate
  factors are **fragile** once you correct for multiple testing. Both are cautionary tales against
  over-engineered signals.
- **Earnings direction is genuinely hard.** Their earnings-forecast task is near-coin-flip even
  for SOTA models; our value-reversion "corrects to the mean in the *multiple* but not always in
  *returns*" (China, Japan) is the same difficulty surfacing in a different frame.

## Where they differ (and why it's complementary)

| dimension | Sakana | Us |
|---|---|---|
| **Breadth** | Japan only | India, US, Korea, Japan, Europe, China |
| **Goal** | Measure AI capability | Find & validate tradeable edges |
| **Rigor axis** | ML train/test + baselines (capability) | False-discovery controls — DSR, sufficiency, non-overlap t (alpha) |
| **JP data depth** | **Deep** (their moat) | Was shallow — **their data closes our gap** |
| **Deliverable** | Open dataset + eval harness | Strategies + screener-RAG + statements |

## The synthesis — their data + our method finishes Japan

Their `edinet2dataset` / EDINET-Corpus (and the **HuggingFace EDINET-Bench parquets, which need
no API key**) carry the exact panel our sufficiency guard said Japan was missing: from the
`earnings_forecast` + `fraud_detection` splits we recover **1,478 JP tickers × 5-year summaries**
(Sales, net income, equity, total assets, EPS, BPS) — enough, once stitched across filing years,
to reach the ~8–10y depth that clears our power bar. So:

1. **Their data → our method:** run *our* value-reversion / Deflated-Sharpe / sufficiency pipeline
   on their EDINET panel → give Japan a **real** value verdict (not "underpowered").
2. **Their tasks → our screener:** their fraud-detection labels become a **risk filter** (avoid
   fraud-flagged names) and earnings-direction a **quality overlay** in our screener.
3. **Their finding validates our caution:** "LLMs don't beat logistic regression" is a strong
   external prior for our multiple-testing skepticism.

## Honest scorecard

- **They are ahead on:** deep JP data infrastructure, an open reproducible corpus, and LLM-eval
  methodology. Their tooling solved the JP-depth problem we hit a paywall on.
- **We are ahead on:** multi-market coverage, a tradeable-strategy focus, finance-specific
  false-discovery controls (DSR + sufficiency gating), and an end-to-end screener with
  income/balance-sheet and regime conditioning.
- **Not rivals — different layers of the stack:** they build the *data + AI-capability* layer;
  we build the *strategy + validation* layer. The best move is to **consume their JP data through
  our validation lens.**

> Research only, not investment advice.
