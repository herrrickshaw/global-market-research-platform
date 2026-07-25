#!/usr/bin/env python3
"""
edinet_collect.py — deep Japan fundamentals from EDINET (FSA official filing system, free).

Each annual securities report (有価証券報告書, docTypeCode 120) contains a 5-YEAR
"Summary of Business Results" block, so a couple of recent filings per company yield ~10y
of NetSales / ProfitLoss / TotalAssets / NetAssets / EPS / shares — the depth that closes
Japan's underpower gap (J-Quants free is only ~2y). Standardised `SummaryOfBusinessResults`
element IDs are used, so it works across JGAAP and IFRS filers.

Auth: EDINET v2 needs a free Subscription-Key. Set EDINET_API_KEY in the env or in
~/.config/market-secrets/credentials.env (EDINET_API_KEY=...). Sent as ?Subscription-Key=.

Strategy: iterate annual-report filing seasons (June, Mar-FYE), list docTypeCode 120,
download the CSV (type=5), extract the 5y summary, map secCode→ticker. Resumable.

Usage: python edinet_collect.py [YYYY-MM-DD..YYYY-MM-DD ...]   (default: recent 3 June seasons)
Output: JP_edinet.parquet (ticker, fy_end, revenue, net_income, total_assets, equity, eps, shares)
"""
from __future__ import annotations
import os, sys, io, zipfile, time, datetime
from pathlib import Path
import requests, pandas as pd, numpy as np

OUT = Path(os.environ.get("EDINET_OUT",
    "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history/JP_edinet.parquet"))
BASE = "https://api.edinet-fsa.go.jp/api/v2"

# standardised 5-year "Summary of Business Results" element IDs (jpcrp taxonomy)
ELEM = {
 "revenue":      ["jpcrp_cor:NetSalesSummaryOfBusinessResults", "jpcrp_cor:RevenueIFRSSummaryOfBusinessResults",
                  "jpcrp_cor:OperatingRevenue1SummaryOfBusinessResults"],
 "net_income":   ["jpcrp_cor:ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults",
                  "jpcrp_cor:NetIncomeLossSummaryOfBusinessResults",
                  "jpcrp_cor:ProfitLossIFRSSummaryOfBusinessResults"],
 "total_assets": ["jpcrp_cor:TotalAssetsSummaryOfBusinessResults"],
 "equity":       ["jpcrp_cor:NetAssetsSummaryOfBusinessResults", "jpcrp_cor:EquityIFRSSummaryOfBusinessResults"],
 "eps":          ["jpcrp_cor:BasicEarningsLossPerShareSummaryOfBusinessResults",
                  "jpcrp_cor:BasicEarningsPerShareIFRSSummaryOfBusinessResults"],
 "shares":       ["jpcrp_cor:TotalNumberOfIssuedSharesSummaryOfBusinessResults"],
}


CODE_MAP = "/Users/umashankar/repos/global-market-data/reference/edinet_code_map.parquet"


def load_code_map() -> dict:
    """EDINET code / sec-code → (ticker, fye month.day) from the official EDINETCODE list
    (3,828 listed companies). Lets us validate the ticker and derive exact fy_end dates."""
    try:
        m = pd.read_parquet(CODE_MAP)
        return {str(r.sec_code)[:4]: (r.ticker, r.fye) for _, r in m.iterrows()}
    except Exception:
        return {}


def api_key() -> str:
    k = os.environ.get("EDINET_API_KEY")
    if not k:
        cred = Path.home() / ".config/market-secrets/credentials.env"
        if cred.exists():
            for l in cred.read_text().splitlines():
                if l.startswith("EDINET_API_KEY="):
                    k = l.split("=", 1)[1].strip().strip('"')
    if not k:
        sys.exit("no EDINET_API_KEY (env or ~/.config/market-secrets/credentials.env)")
    return k


def seasons() -> list[str]:
    """default filing dates to scan: late-June of the last 3 years (Mar-FYE annual reports)."""
    days = []
    for yr in (2023, 2024, 2025):
        for d in range(20, 30):
            days.append(f"{yr}-06-{d:02d}")
    return days


def list_annual(date: str, key: str) -> list[dict]:
    try:
        r = requests.get(f"{BASE}/documents.json",
                         params={"date": date, "type": 2, "Subscription-Key": key}, timeout=30)
        if r.status_code != 200:
            return []
        return [d for d in r.json().get("results", [])
                if d.get("docTypeCode") == "120" and d.get("secCode")]     # annual securities report
    except Exception:
        return []


def parse_csv(zip_bytes: bytes) -> pd.DataFrame | None:
    """extract the multi-year Summary-of-Business-Results rows from the EDINET CSV zip."""
    try:
        z = zipfile.ZipFile(io.BytesIO(zip_bytes))
        name = next((n for n in z.namelist() if n.endswith(".csv") and "jpcrp" in n.lower()), None) \
            or next((n for n in z.namelist() if n.endswith(".csv")), None)
        if not name:
            return None
        raw = z.read(name)
        for enc in ("utf-16", "utf-16-le", "cp932", "utf-8"):
            try:
                df = pd.read_csv(io.BytesIO(raw), sep="\t", encoding=enc, dtype=str)
                if "要素ID" in df.columns or "ElementID" in df.columns:
                    return df
            except Exception:
                continue
    except Exception:
        return None
    return None


def extract(df: pd.DataFrame) -> pd.DataFrame:
    """pull the 5-year summary: one row per (relative-year) with the mapped metrics."""
    eid = "要素ID" if "要素ID" in df.columns else "ElementID"
    ctx = "コンテキストID" if "コンテキストID" in df.columns else "ContextID"
    val = "値" if "値" in df.columns else "Value"
    if eid not in df.columns or val not in df.columns:
        return pd.DataFrame()
    out = {}
    for metric, ids in ELEM.items():
        sub = df[df[eid].isin(ids)]
        for _, r in sub.iterrows():
            c = str(r.get(ctx, ""))                       # ...Prior4Year / Prior1Year / CurrentYear
            out.setdefault(c, {})[metric] = pd.to_numeric(str(r[val]).replace(",", ""), errors="coerce")
    rows = [{"ctx": c, **m} for c, m in out.items() if any(pd.notna(v) for v in m.values())]
    return pd.DataFrame(rows)


def main() -> int:
    key = api_key()
    dates = sys.argv[1:] or seasons()
    dates = [d for spec in dates for d in ([spec] if ".." not in spec else
             pd.date_range(*spec.split(".."))[::1].strftime("%Y-%m-%d").tolist())]
    done = set()
    rows = []
    if OUT.exists():
        prev = pd.read_parquet(OUT); rows = prev.to_dict("records"); done = set(prev.get("docID", []))
    seen_docs = 0
    for date in dates:
        docs = list_annual(date, key)
        for d in docs:
            doc_id, sec = d["docID"], str(d["secCode"])[:4]
            if doc_id in done:
                continue
            ticker = f"{sec}.T"
            try:
                r = requests.get(f"{BASE}/documents/{doc_id}",
                                 params={"type": 5, "Subscription-Key": key}, timeout=60)
                if r.status_code != 200:
                    continue
                df = parse_csv(r.content)
                if df is None:
                    continue
                ex = extract(df)
                fy = d.get("periodEnd") or d.get("docDescription", "")
                for _, e in ex.iterrows():
                    rows.append({"ticker": ticker, "docID": doc_id, "ctx": e.get("ctx"),
                                 "fy_end_report": fy,
                                 **{k: e.get(k) for k in ELEM}})
                seen_docs += 1
            except Exception:
                pass
            time.sleep(0.2)
            if seen_docs and seen_docs % 100 == 0:
                pd.DataFrame(rows).to_parquet(OUT, index=False)
                print(f"  {seen_docs} filings, {len(rows)} rows", flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(OUT, index=False)
    print(f"EDINET: {len(df)} rows, {df.ticker.nunique() if len(df) else 0} tickers -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
