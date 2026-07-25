# Local RAG — credit-free Q&A over the platform's outputs

`local_rag.py` answers natural-language questions about the platform with **no paid API
and no model download**: TF-IDF retrieval (sklearn) + deterministic structured extraction.

**Design rule: numbers come from the data, prose from retrieval.** Financial-statement
figures, stock picks and buy/sell signals are read straight from the parquet/CSV outputs —
never hallucinated. The retriever (over `reports/*.md` + `docs/*.md`) only supplies context.
A local LLM is **optional**: if LM Studio (`:1234`) or ollama (`:11434`) is up it phrases the
answer; otherwise the answer is extractive (table + top passages). Either way it's free.

## Usage
```bash
python local_rag.py "show the income statement"        # -> income_statement_by_geo.csv
python local_rag.py "balance sheet"                    # -> balance_sheet_by_geo.csv
python local_rag.py --refresh "income statement"       # rebuild statements first
python local_rag.py "korea buy signals"                # -> watchlist zones (KR)
python local_rag.py "underpriced stocks in india"      # -> valuation clustering (IN)
python local_rag.py "top stock picks for us"           # -> recs_US.csv
python local_rag.py "is china data sufficient"         # -> data_sufficiency
python local_rag.py "why does shorting fail in india"  # open Q -> retrieval (+LLM if up)
```

## Intents (deterministic, grounded)
income statement · balance sheet · picks/recommendations · buy/sell/hold signals ·
under/over-priced (valuation clustering) · data sufficiency · data sources. Anything else
falls through to TF-IDF retrieval over the reports.

> To upgrade retrieval quality (optional, still free/offline): `pip install sentence-transformers`
> for semantic embeddings, and run LM Studio/ollama for fluent synthesis. Not investment advice.

## New intents (this session's analysis)
```bash
python local_rag.py "what should I do in japan"       # -> per-market playbook (ranked edges)
python local_rag.py "where is the edge in korea"      # -> the fat-pitch grid (edge × market)
python local_rag.py "which sectors are speculation"   # -> fundamentals-vs-speculation (PB~ROE R²)
python local_rag.py "picks for korea"                 # -> LIVE playbook picks (validated filters, long/short)
```
`picks` now serves the live `playbook_picks.csv` (each market's validated edge, on the watchlist
for monitoring). The standalone `market_screener_rag` repo adds `screener_rag.py playbook <market>`
with the same ranked edges + the net-of-borrow and China corrections.
