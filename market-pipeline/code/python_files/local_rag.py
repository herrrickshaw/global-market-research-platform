#!/usr/bin/env python3
"""
local_rag.py — a CREDIT-FREE, fully-offline RAG over the platform's own outputs.

No paid API, no model download: TF-IDF retrieval (sklearn) + deterministic structured
extraction. The design rule is **numbers come from the data, prose from retrieval** —
financial-statement figures, picks and signals are read straight from the parquet/CSV
outputs (never hallucinated); the retriever only supplies explanatory context.

A local LLM is OPTIONAL: if an OpenAI-compatible server is up (LM Studio :1234 or
ollama :11434) it's used to phrase the final answer; otherwise the answer is extractive
(structured table + top retrieved passages). Either way it runs on your machine for free.

Usage:
  python local_rag.py "korea buy signals"
  python local_rag.py "show the income statement"
  python local_rag.py --refresh "balance sheet"     # rebuild statements first
  python local_rag.py "why does shorting fail in india"   # open Q -> retrieval(+LLM)
"""
from __future__ import annotations
import sys, re, glob, subprocess
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"


# ─────────────────────────── structured extractors (grounded) ───────────────────────────
def _md_table(df: pd.DataFrame, n: int | None = None) -> str:
    d = df.head(n) if n else df
    return d.to_markdown(index=False)


def income_statement(_q=""):
    p = REP / "income_statement_by_geo.csv"
    if not p.exists():
        return "income_statement_by_geo.csv not found — run `python trading_financials.py` (or --refresh)."
    return "**Income statement by geography** (from the paper-trade ledger):\n\n" + _md_table(pd.read_csv(p))


def balance_sheet(_q=""):
    p = REP / "balance_sheet_by_geo.csv"
    if not p.exists():
        return "balance_sheet_by_geo.csv not found — run `python trading_financials.py` (or --refresh)."
    return "**Balance sheet by geography:**\n\n" + _md_table(pd.read_csv(p))


def _market_from_q(q: str) -> str | None:
    for name, mk in {"india": "IN", "indian": "IN", " in ": "IN", "us": "US", "united states": "US",
                     "korea": "KR", "korean": "KR", "japan": "JP", "europe": "EU", "china": "CN"}.items():
        if name in f" {q.lower()} ":
            return mk
    return None


def picks(q=""):
    mk = _market_from_q(q) or "IN"
    p = REP / f"recs_{mk}.csv"
    if not p.exists():
        avail = [Path(x).stem.split("_")[1] for x in glob.glob(str(REP / "recs_*.csv"))]
        return f"No recs for {mk}. Available: {avail}. Run `python generate_recommendations.py`."
    d = pd.read_csv(p)
    d.columns = ["ticker", "pred_fwd_ret"] + list(d.columns[2:])
    d = d.sort_values("pred_fwd_ret", ascending=False).head(15)
    d["pred_fwd_ret"] = (d.pred_fwd_ret * 100).round(2).astype(str) + "%"
    return (f"**Top {mk} stock picks** (learned-model predicted forward return; research, not advice):\n\n"
            + _md_table(d[["ticker", "pred_fwd_ret"]]))


def signals(q=""):
    mk = _market_from_q(q)
    ql = q.lower()
    zone = "buy" if "buy" in ql else "sell" if "sell" in ql else "hold" if "hold" in ql else None
    w = pd.read_csv(HERE / "watchlist.csv")
    if mk:
        w = w[w.market == mk]
    # zone semantics: 'signal' rows are actionable; status carries the tier
    summ = w.groupby(["market", "status"]).size().reset_index(name="n")
    head = f"**Watchlist signals{' — ' + mk if mk else ''}:**\n\n" + _md_table(summ)
    names = w[w.status.str.contains("signal|held|value-hold", case=False, na=False)]
    if mk and len(names):
        head += f"\n\nActionable names ({mk}): " + ", ".join(names.symbol.head(25))
    head += ("\n\n> Zones are per-market (IN momentum/long-only; US/KR/JP/EU mean-revert). "
             "Buy/Hold/Sell come from the scan zones; validate before acting. Not investment advice.")
    return head


def valuation(q=""):
    mk = _market_from_q(q)
    p = REP / "valuation_clusters.csv"
    if not p.exists():
        return "valuation_clusters.csv not found — run `python valuation_clustering.py`."
    d = pd.read_csv(p)
    # normalize market naming: clusters use 'india'/'us'/'korea', codes elsewhere are IN/US/KR
    norm = {"india": "IN", "us": "US", "korea": "KR", "japan": "JP", "europe": "EU", "china": "CN"}
    d["market"] = d.market.astype(str).str.lower().map(norm).fillna(d.market.astype(str).str.upper())
    if mk:
        d = d[d.market == mk]
    side = "under" if re.search(r"under|cheap", q.lower()) else "over" if re.search(r"over|expensive|rich", q.lower()) else None
    cols = [c for c in ["market", "name", "pe", "pb", "roe", "valuation_z", "verdict"] if c in d.columns]
    if side == "under":
        d = d.sort_values("valuation_z").head(15)
        t = "UNDERPRICED vs same-profile peers (cheap for their economics)"
    elif side == "over":
        d = d.sort_values("valuation_z", ascending=False).head(15)
        t = "OVERPRICED vs same-profile peers"
    else:
        d = d.reindex(d.valuation_z.abs().sort_values(ascending=False).index).head(15)
        t = "most mispriced vs peers (both tails)"
    return f"**Valuation clustering — {t}{' · ' + mk if mk else ''}:**\n\n" + _md_table(d[cols])


def sufficiency(_q=""):
    p = REP / "data_sufficiency.md"
    if not p.exists():
        return "run `python data_sufficiency.py`."
    txt = p.read_text()
    m = re.search(r"(\| market \| fund tickers.*?)(?=\n##|\Z)", txt, re.S)
    return "**Data sufficiency (can we trust each market?):**\n\n" + (m.group(1) if m else txt[:1500])


def sources(_q=""):
    p = HERE / "docs" / "DATA_SOURCES.md"
    return ("**Data sources registry:**\n\n" + p.read_text()[:2500]) if p.exists() else "run `python source_registry.py`."


INTENTS = [
 (r"income statement|p&?l|profit.*loss|revenue.*tax", income_statement),
 (r"balance sheet|assets?.*liabilit|equity position", balance_sheet),
 (r"pick|recommend|top stocks|what to buy", picks),
 (r"buy|sell|hold|signal|watchlist|zone", signals),
 (r"under\s?priced|over\s?priced|cheap|expensive|mispriced|valuation|cluster", valuation),
 (r"sufficien|coverage|enough data|reliable|trust", sufficiency),
 (r"data source|where.*data|provider|upstream", sources),
]


def route(q: str):
    for pat, fn in INTENTS:
        if re.search(pat, q.lower()):
            return fn
    return None


# ─────────────────────────── TF-IDF retriever (offline) ───────────────────────────
def build_corpus() -> list[dict]:
    docs = []
    for p in sorted(glob.glob(str(REP / "*.md"))) + sorted(glob.glob(str(HERE / "docs" / "*.md"))):
        txt = Path(p).read_text(errors="ignore")
        for chunk in re.split(r"\n(?=#{1,3} )", txt):          # split on headings
            chunk = chunk.strip()
            if len(chunk) > 80:
                docs.append({"source": Path(p).name, "text": chunk})
    return docs


def retrieve(q: str, k: int = 4):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    docs = build_corpus()
    if not docs:
        return []
    vec = TfidfVectorizer(stop_words="english", max_features=20000, ngram_range=(1, 2))
    M = vec.fit_transform([d["text"] for d in docs])
    sims = linear_kernel(vec.transform([q]), M).ravel()
    idx = sims.argsort()[::-1][:k]
    return [(docs[i], float(sims[i])) for i in idx if sims[i] > 0.02]


# ─────────────────────────── optional local LLM ───────────────────────────
def local_llm(prompt: str) -> str | None:
    try:
        import requests
    except Exception:
        return None
    for url, model in [("http://localhost:1234/v1/chat/completions", "local-model"),
                       ("http://localhost:11434/v1/chat/completions", "llama3")]:
        try:
            r = requests.post(url, json={"model": model, "temperature": 0.1,
                "messages": [{"role": "system", "content": "Answer ONLY from the provided context. "
                              "Never invent numbers. If the context lacks the answer, say so."},
                             {"role": "user", "content": prompt}]}, timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception:
            continue
    return None


def answer(q: str) -> str:
    fn = route(q)
    if fn:                                        # deterministic structured extraction
        out = fn(q)
        ctx = retrieve(q, 2)                      # add a little explanatory context
        if ctx:
            out += "\n\n---\n*Context:* " + ctx[0][0]["source"] + " — " + ctx[0][0]["text"][:300].replace("\n", " ")
        return out
    # open question -> retrieval, synthesized by local LLM if available, else extractive
    ctx = retrieve(q, 4)
    if not ctx:
        return "No relevant context found. Try: income statement · balance sheet · <market> buy signals · underpriced <market> · picks <market> · sufficiency."
    joined = "\n\n".join(f"[{d['source']}] {d['text']}" for d, _ in ctx)
    llm = local_llm(f"Context:\n{joined}\n\nQuestion: {q}\nAnswer concisely from the context:")
    if llm:
        return llm + f"\n\n*(sources: {', '.join(sorted({d['source'] for d, _ in ctx}))})*"
    return (f"**Retrieved (no local LLM running — extractive answer):**\n\n" +
            "\n\n".join(f"**{d['source']}** (score {s:.2f}):\n{d['text'][:700]}" for d, s in ctx))


def main() -> int:
    args = sys.argv[1:]
    if "--refresh" in args:
        args.remove("--refresh")
        print("refreshing financial statements…")
        subprocess.run([sys.executable, str(HERE / "trading_financials.py")], cwd=HERE)
    if not args:
        print(__doc__)
        return 0
    print(answer(" ".join(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
