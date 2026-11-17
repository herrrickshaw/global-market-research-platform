#!/usr/bin/env python3
"""Search OpenAlex for literature. Key read from OPENALEX_API_KEY (credentials.env).

  python3 scripts/lit_search.py "overnight intraday returns" [-n 15] [--since 2015] [--oa]
Prints year | cites | title | DOI | legal open-access URL (if any).
"""
import argparse, os, sys, requests

p = argparse.ArgumentParser()
p.add_argument("query")
p.add_argument("-n", type=int, default=15)
p.add_argument("--since", type=int)
p.add_argument("--oa", action="store_true", help="only works with a free legal copy")
a = p.parse_args()

key = os.environ.get("OPENALEX_API_KEY")
if not key:
    sys.exit("OPENALEX_API_KEY not set: set -a; . ~/.config/market-secrets/credentials.env")

flt = [f"from_publication_date:{a.since}-01-01"] if a.since else []
if a.oa:
    flt.append("is_oa:true")
r = requests.get(
    "https://api.openalex.org/works",
    params={"search": a.query, "per-page": a.n, "sort": "relevance_score:desc",
            "filter": ",".join(flt) or None,
            "select": "title,publication_year,cited_by_count,doi,best_oa_location"},
    headers={"Authorization": f"Bearer {key}"}, timeout=30)
r.raise_for_status()
for w in r.json()["results"]:
    oa = ((w.get("best_oa_location") or {}).get("pdf_url")
          or (w.get("best_oa_location") or {}).get("landing_page_url") or "-")
    print(f"{w['publication_year']} | {w['cited_by_count']:>5} | {w['title']} | {w['doi'] or '-'} | {oa}")
