# Literature Reference Audit — 2026-08-01

Full audit of every academic citation across the repos that carry literature content:
**market-pipeline** (this repo), **BazaarTalks** ≡ **global-market-scanners** (byte-identical
literature files), **global-stock-screener**, **market-screener-rag**,
**piotroski-liquidity-research** (paper is a byte-identical copy of this repo's),
**price_prediction_backtest**, **us-stock-picks**. Extraction was exhaustive (4 parallel
sweeps over ~90 citation-bearing files); verification was against the actual papers, and
where a claim was checkable online (MIT course page, arXiv), it was fetched and checked.

## Verdict by tier

### Tier 1 — Verified correct (the core is solid)

The finance-literature backbone checks out: author, year, journal, volume/pages, and —
more importantly — **the claim attributed to each paper is what the paper actually says**.

Amihud (2002, *JFM* 5:31–56) · Corwin & Schultz (2012, *JF* 67(2)) — including the
floor-negative-spreads-at-zero detail, which really is the paper's recommendation ·
Fang, Noe & Tice (2009, *JFE* 94(1)) · Piotroski (2000, *JAR* 38) · Bailey & López de
Prado (2014, DSR, *JPM*) · Bailey et al. (2014, PBO) · Harvey, Liu & Zhu (2016, *RFS*) ·
Harvey & Liu (2015, *JPM*) · De Bondt & Thaler (1985) · Lakonishok, Shleifer & Vishny
(1994) · Basu (1977) · Jegadeesh & Titman (1993) · Moskowitz, Ooi & Pedersen (2012) ·
Hong & Stein (1999) · Daniel & Moskowitz (2016) · McLean & Pontiff (2016) · Novy-Marx
(2013) · Asness-Frazzini-Pedersen QMJ · Asness-Moskowitz-Pedersen (2013) · Tibshirani
(1996) · Almgren & Chriss (2000) / Almgren et al. (2005) · Fama-MacBeth (1973) ·
Carhart (1997) · Cochrane (2011) · Hou-Xue-Zhang (2020) · Bernard & Thomas (1989/90) ·
Chordia et al. (2009, *FAJ*) · Cohen & Frazzini (2008) · Loughran & McDonald (2011) ·
Amihud & Mendelson (1986) · Pástor & Stambaugh (2003) · Frazzini & Pedersen (2014) ·
Markowitz (1952) · Sharpe (1964) · Fama (1991) · Gu-Kelly-Xiu (2020) · Granville (1963) ·
Kaufman (1995) · Avellaneda-Stoikov (2008) · Ho-Stoll (1981) · Avellaneda-Lee (2010) ·
Altman (1968, formula and 1.81/2.99 zones exact) · Sugiura et al. (2025) EDINET-Bench
(arXiv:2506.08762 — ID matches the local PDF) · Robinson/van Greuning/Henry/Broihahn
CFA text (page-level citations, local PDF on disk) · the four framework books (Linoff,
McKinney, Han/Kamber/Pei, Knaflic — all real, correct editions/publishers).

**BazaarTalks / global-market-scanners have the best reference hygiene in the
portfolio** — two verbatim reference sections with correct journals, SSRN/arXiv IDs,
and an explicit "applied corpus consulted, not the source of any reported statistic"
disclaimer. `SCREENER_LITERATURE_LOG.md` (this repo) is the best *implementation*
audit — it verifies formulas field-by-field against the papers.

### Tier 2 — Errors found → **FIXED in this commit** (and sibling repos)

| # | Error | Where | Fix |
|---|---|---|---|
| 1 | Cash Conversion Cycle attributed to "Richard Lawrence" — a garbled merge of the real authors | `SCREENER_LITERATURE_LOG.md` §7 | → Richards & Laughlin (1980, *Financial Management* 9(1)) |
| 2 | "John Slatter / Michael O'Higgins, *Beating the Dow* (1991)" — Slatter didn't write that book (co-author: John Downes); Slatter's contribution is the 1988 WSJ column | `SCREENER_LITERATURE_LOG.md` §9 | → split the attribution correctly |
| 3 | Coffee Can origin (Kirby 1984, *JPM*) missing from the central log (other files had it right) | `SCREENER_LITERATURE_LOG.md` §2 | → Kirby (1984) added |
| 4 | Balvers & Wu dated 2005; published *J. Empirical Finance* 13 (2006), 24–48 | `backtest_zone_rules.py` | → 2006 + full cite |
| 5 | HML "formalised by Fama & French (1992)" — the factor construction is FF (1993); 1992 documented the cross-sectional effect | `docs/WHY_THESE_WIN.md` + market-screener-rag copy | → both years, correctly split |
| 6 | Paraphrase presented as a direct Piotroski (2000) quote — *"small, ILLIQUID, low-analyst-coverage value stocks"*; the paper's wording is "small and medium-sized firms, companies with low share turnover, and firms with no analyst following" | `size_vs_liquidity_us.py`, `reports/PIOTROSKI_LIQUIDITY_PAPER.md`, `docs/WHY_THESE_WIN.md` + piotroski-liquidity-research & market-screener-rag copies | → real wording quoted, paraphrase de-quoted |
| 7 | "applied from 7 papers" — only 5 distinct sources are named | `backtest_screeners.py` | → 5 |
| 8 | Deflated Sharpe used without its citation | `screener_evaluation.py` | → Bailey & López de Prado (2014) added |
| 9 | Data-ink ratio credited to Knaflic; the term is Tufte's (1983) | `data_science_framework/TOOLS_TECHNIQUES_ANALYSIS.md` | → Tufte credited |
| 10 | "Liu, B. (2024)" solo — arXiv 2404.16449 fetched: authors are **Beier Liu and Haiyun Zhu** (this repo's "Liu & Zhu" was right; BazaarTalks' was incomplete) | BazaarTalks + global-market-scanners RESEARCH_PAPER*.md | → Liu, B., & Zhu, H. |

### Tier 3 — Unverifiable offline / incomplete (left as-is, flagged)

Cited with quotes in code comments but originally **no full reference anywhere in
market-pipeline**. Two were **RESOLVED at source on 2026-08-01** (full citations now in
`backtest_screeners.py`'s source block and both twins' reference sections):

- ✅ **Preet et al. (2021)** — resolved via SSRN search: Preet, S., Gulati, A., Gupta, A.,
  & Aggarwal, A. (2021). *Back Testing Magic Formula on Indian Stock Markets: An Analysis
  of Magic Formula Strategy.* SGGSCC, University of Delhi. SSRN 3945468.
- ✅ **Bhute et al. (2024)** — resolved at jier.org: Bhute, A., Tripathi, M. M., Jadav, D.,
  Kasar, A., & Bathia, A. (2024). *Backtesting Brilliance: Leveraging Analytics for
  Comparing Buy & Hold Vs. Trading Strategies based on Technical Indicators.* *JIER* 4(3).
  doi:10.52783/jier.v4i3.1785 — the "Bhute et al." attribution was **correct**; it was
  BazaarTalks' anonymous entry that was incomplete.
- ✅ **Dhanus & Amutha (2025)** — verified real (2nd pass): Dhanus, S., & Amutha, G.
  (2025). *Back-Testing Super Trend in 15 Mins Time Frame among Top Five NIFTY-50
  Stocks.* *IJARCMSS* 8(2-II), Apr–Jun 2025 (inspirajournals.com, PDF 871152129).
  The Super-Trend/volume claims cited in `backtest_screeners.py` match the paper's
  actual topic.
- ✅ **AlQahtani et al. (2025)** — resolved: AlQahtani, H. S., Alhaddad, M. J., & Jarrah, M.
  (2025). *Comprehensive Analysis of Machine and Deep Learning Models for Stock Market
  Prediction.* *IJACSA* 16(8), 455–463 (same paper as BazaarTalks' anonymous IJACSA entry).
  🔴 **Claim-level erratum found and fixed:** `full_us_market_scan.py` credited the paper
  with recommending Ridge regression and a 5-year data window — the paper evaluates plain
  Linear Regression vs RNN vs LSTM (LR wins), mentions Ridge only in a taxonomy figure, and
  makes no window recommendation (its review notes ~2y sufficed; stresses retraining).
  Comments rewritten to credit the paper only for what it shows.
- ✅ **"Walkshäusl et al." F-score critique** — resolved at EconStor: the paper with that
  exact title is **Krauss, C., Krüger, T. & Beerstecher, D. (2015)**, IWQW Discussion Paper
  13/2015, FAU Erlangen-Nürnberg. 🔴 **Wrong-author citation, fixed** in `cost_vs_edge.py`
  and both copies of PIOTROSKI_LIQUIDITY_PAPER.md. (Walkshäusl's own F-score paper is
  *Piotroski's FSCORE: international evidence*, J. Asset Management 21, 2020 — the PDF in
  ~/Downloads — a different work.)
- ✅ **"Chaudhuri/Wu"** — resolved: Chaudhuri, K., & Wu, Y. (2003). *Random walk versus
  breaking trend in stock prices: Evidence from emerging markets.* *J. Banking & Finance*
  27(4), 575–592 (+ companion in *Managerial Finance* 2003). Full cite now in
  `backtest_zone_rules.py`.
- ⚠️ **"TEDE emerging-vs-developed study"** — best candidate located: Palwasha, R. I.,
  Ahmad, N., Ahmed, R. R., Vveinhardt, J., & Štreimikienė, D. (2018). *Speed of Mean
  Reversion: An Empirical Analysis of KSE, LSE and ISE Indices.* *TEDE* 24(4), 1435–1452.
  But it measures mean-reversion speed **across Pakistani indices only** — it does not
  compare emerging vs developed. `backtest_zone_rules.py` now says so and rests the
  emerging-markets-revert claim on Chaudhuri & Wu.
- ✅ **Gomber et al., *High-Frequency Trading*** — resolved: Gomber, P., Arndt, B., Lutat,
  M., & Uhle, T. (2011). SSRN 1858626, Goethe University Frankfurt / Deutsche Börse.

### Delta audit — 2026-08-01 second pass (files the first sweep did not cover)

- **`price_prediction_backtest/docs/ACCURACY_RELIABILITY_MATRIX.md`** — all 5 sources checked:
  - ✅ arXiv 2606.27100 *Pretrained Time-Series Foundation Models for Financial Return
    Forecasting* — real; authors Noguer i Alonso & Pereira Franklin (June 2026); the
    doc's "not universal engines of statistically reliable alpha" quote matches.
  - ✅ MDPI JRFM 19(3):203 (2026) *A Comparative Study of Transformer-Based and Classical
    Models…* — real; author Ting Liu; the doc's "ARIMA and Random Forest remain strong
    baselines" claim matches the paper's findings.
  - ✅ Gu–Kelly–Xiu SSRN 3159577 — correct ID.
  - ⚠️ Two ResearchGate links (394711257 systematic review, 403314395 DL review) —
    ResearchGate blocks fetching; titles are plausible but IDs not independently verified.
- **`literature_scout.py` (BazaarTalks ≡ global-market-scanners, byte-identical)** —
  "Jacob-Pradeep-Varma (IIMA 2022)" in the docstring = Jacob, J., Pradeep, K. P., &
  Varma, J. R. (2022), *Performance of quality factor in Indian equity market*, IIMA
  working paper / SSRN 4284686 — real. All other named papers already Tier-1 verified.
- **`ml_signal_engine.py`** — 🔴 claim-level erratum fixed: "Multivariate CNN-LSTM
  (RMSE 0.0162)" was presented as AlQahtani et al.'s finding, but AlQahtani only *cites*
  it in their review table — the result is Widiputra, H., Mailangkay, A., & Gautama, E.
  (2021), *Complexity*. Attribution corrected in the code header; full AlQahtani citation
  (IJACSA 16(8), doi:10.14569/IJACSA.2025.0160845) also added. Caution: IJACSA 16(11)
  carries a similar-sounding Saudi paper by Eissa Alreshidi (ARIMA/XGBoost, 7 models) —
  do not conflate the two.
- **`.lmstudio/extensions/backends`** (190 files with arXiv links) — vendored LM Studio
  third-party docs, out of audit scope.

### Tier 4 — Fabricated → **DELETED in this commit**

- **`data_science_framework/MIT_COURSES_ALIGNMENT.md`** — cited
  `openlearning.mit.edu/news/15-free-mit-data-science-courses` as its source; that page
  was fetched and lists 15 real courses — **none of the 8 course numbers/titles in the
  doc appear on it**. "18.050 Statistics for Applications" (real number: 18.650),
  "15.S12 Machine Learning, Marketplaces, and the Modern Economy" (15.S12 is
  *Blockchain and Money*), "16.622 Aerospace Software Engineering" (16.622 is
  *Experimental Projects II*), "6.420 Advanced Algorithms for Data Science" (no such
  subject) are invented.
- **`data_science_framework/GLOBAL_UNIVERSITY_COURSES.md`** — mixed real courses
  (Stanford CS229, CMU 36-402, Toronto CSC311/413, UW CSE547) with misattributions:
  "Berkeley STAT110" is Harvard's course; "UW CSE415 Introduction to Machine Learning"
  is actually *Introduction to Artificial Intelligence* (UW's intro ML is CSE446).
- References to both docs scrubbed from `FINAL_STATUS.md` and
  `DROPBOX_TESTING_GUIDE.md` (with an audit note left in place).

Both docs were AI-generated in an earlier session of this project and never verified —
this audit is the verification they should have had. The *techniques* they described
(SVM, LASSO, bootstrap, online learning, etc.) are standard and remain listed in
`FINAL_STATUS.md`; only the course-number scaffolding was fabricated.

## Repos touched by fixes

- **market-pipeline** — this commit
- **market-screener-rag**, **piotroski-liquidity-research**, **BazaarTalks**,
  **global-market-scanners** — same fixes committed locally in each repo (not pushed)

## Recommendations (not done)

1. Complete the Tier-3 references — BazaarTalks' reference-section format is the model;
   resolve the Preet year and the Bhute-vs-anonymous JIER authorship from SSRN 3945468
   and the JIER 4(3) issue page.
2. `roace_by_liquidity.py` scores 7 of 9 Piotroski tests (documented in its docstring) —
   any report citing its output as "Piotroski F-score" should carry that caveat.
3. The twins (BazaarTalks ≡ global-market-scanners) will drift; pick one as canonical.
