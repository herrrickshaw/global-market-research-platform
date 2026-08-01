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

Cited with quotes in code comments but **no full reference anywhere in market-pipeline**
(BazaarTalks' reference sections partially cover them — copy those entries over if these
files are ever published):

- **Preet et al. (2021)** Magic Formula India — BazaarTalks has it as SSRN 3945468, SGGSCC/University of Delhi, but **undated** there
- **Bhute et al. (2024) "JIER"** — BazaarTalks' matching entry ("Backtesting Brilliance…", *JIER* 4(3), 2024) has **no authors**; the two repos disagree on whether "Bhute" is an author
- **Dhanus & Amutha (2025)** — *IJARCMSS* 8(2-II), 10–14 per BazaarTalks
- **AlQahtani et al. (2025)** Ridge regression — no title, venue, or ID anywhere
- **Walkshäusl et al.** F-score critique — "EconStor", no year, no journal; the in-text quote in `cost_vs_edge.py` is not traceable to a specific paper
- **"Chaudhuri/Wu"** and **"the TEDE emerging-vs-developed study"** (`backtest_zone_rules.py`) — topic labels, not citations
- **Gomber et al., *High-Frequency Trading*** — no year (the 2011 working paper exists)

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
