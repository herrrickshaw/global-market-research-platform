#!/usr/bin/env python3
"""
cash_conversion_cycle.py — compute CCC from filings. screener.in is a FALLBACK.

WHY THIS EXISTS
───────────────
The Cash Conversion Cycle was not computed here at all. It was scraped, whole,
from one screener.in page — a single third-party HTML endpoint, for a number
that is four line items and a subtraction. That single point of failure took out
step [6/13] of the daily run twice in three days:

  * 2026-08-20 the refresh died on one 25s read timeout.
  * 2026-08-21 the refresh succeeded but the scrape TEST ran 29 minutes and was
    killed at its 600s cap, and the brief was told to render CCC as n/a even
    though 29 current rows were already sitting in the cache.

Both were the same fault: no local ability to produce the number. A source that
must be reachable at 03:00 for a section to render is a source that decides
whether the section renders.

THE FORMULA
───────────
    DSO = receivables / revenue          x 365   (days sales outstanding)
    DIO = inventory    / cost_of_revenue x 365   (days inventory outstanding)
    DPO = payables     / cost_of_revenue x 365   (days payables outstanding)

    CCC = DSO + DIO - DPO

Days between paying for inputs and collecting for output. NEGATIVE is strong:
the business is funded by its suppliers and customers rather than by capital.
Apple computes to -71.1 days on FY2025 filings, Walmart to +2.8 — both match
their well-known figures, which is the check that this implementation is right.

SOURCE PRECEDENCE, and why
──────────────────────────
    1. filings   US  — SEC EDGAR companyfacts (us-gaap / ifrs-full)
                 IN  — the yfinance fundamentals store
    2. screener  either market — the scraped screen, ONLY where 1 yields nothing

Primary is whatever we already hold and can recompute offline. screener.in is
kept because it genuinely covers names our stores miss, but it can no longer
decide whether the number exists, and every row carries the source that produced
it so a reader can tell them apart.

NaN IS A RESULT. Some filers have no conventional cost-of-goods line at all —
Exxon reports `CostsAndExpenses` and sector-specific `EnergyRelatedInventory*`,
with no generic inventory or COGS tag. Substituting total expenses would yield a
confidently wrong DIO/DPO. A missing CCC is visibly missing; an invented one is
not.

    cash_conversion_cycle.py --market IN
    cash_conversion_cycle.py --market US --top 15
    cash_conversion_cycle.py --market IN --compare   # filings vs screener.in
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

try:
    import data_registry as _R
    FUND_DIR = Path(_R.FUND_DIR)
except Exception:
    FUND_DIR = Path("/Users/umashankar/market-pipeline/market_cache/fundamentals")

STORE = {"IN": FUND_DIR / "IN_current.parquet",
         "US": FUND_DIR / "US_current.parquet",
         "KR": FUND_DIR / "KR_current.parquet"}
SCREENER_CACHE = HERE / "cache_seed" / "india_ccc_screen.parquet"

NEEDED = ["receivables", "inventory", "payables", "cost_of_revenue", "revenue"]


def from_filings(market: str) -> pd.DataFrame:
    """CCC per ticker from the latest complete fiscal year in the store."""
    p = STORE.get(market)
    if not p or not p.exists():
        return pd.DataFrame()
    f = pd.read_parquet(p)
    missing = [c for c in NEEDED if c not in f.columns]
    if missing:
        # The collector has not yet run since the CCC inputs were added.
        # Say so rather than returning an empty frame that reads as "no data".
        print(f"  {market}: store lacks {missing} — re-run the collector "
              f"({'us_fundamentals_edgar.py' if market == 'US' else 'fundamentals_offhours.py'})",
              file=sys.stderr)
        return pd.DataFrame()

    f = f[pd.to_datetime(f["fy_end"], errors="coerce") <= pd.Timestamp.today()]
    f = f.sort_values("fy_end").groupby("ticker", as_index=False).last()
    n = {c: pd.to_numeric(f[c], errors="coerce") for c in NEEDED}

    # Guard every denominator. A zero or negative revenue/COGS is a data error,
    # not a business with an infinite cycle.
    rev = n["revenue"].where(n["revenue"] > 0)
    cogs = n["cost_of_revenue"].where(n["cost_of_revenue"] > 0)

    out = pd.DataFrame({
        "ticker": f["ticker"],
        "fy_end": f["fy_end"],
        "dso": n["receivables"] / rev * 365,
        "dio": n["inventory"] / cogs * 365,
        "dpo": n["payables"] / cogs * 365,
    })
    out["ccc"] = out["dso"] + out["dio"] - out["dpo"]
    out["source"] = "filings"
    # A cycle beyond +/- 3 years is an accounting artefact (a stub year, a
    # part-period COGS), not a real operating cycle. Null it rather than let it
    # top a "best CCC" ranking.
    out.loc[out["ccc"].abs() > 1095, ["ccc", "dso", "dio", "dpo"]] = np.nan
    return out.dropna(subset=["ccc"])


def from_screener() -> pd.DataFrame:
    """The scraped screen — FALLBACK. India only, and pre-computed upstream."""
    if not SCREENER_CACHE.exists():
        return pd.DataFrame()
    d = pd.read_parquet(SCREENER_CACHE)
    if "Cash_Cycle" not in d.columns:
        return pd.DataFrame()
    return pd.DataFrame({
        "ticker": d["Symbol"].astype(str),
        "fy_end": pd.NaT,
        "dso": np.nan, "dio": np.nan, "dpo": np.nan,
        "ccc": pd.to_numeric(d["Cash_Cycle"], errors="coerce"),
        "source": "screener.in",
    }).dropna(subset=["ccc"])


def ccc(market: str, allow_fallback: bool = True) -> pd.DataFrame:
    """Filings first; screener.in only fills tickers filings could not."""
    primary = from_filings(market)
    if not allow_fallback or market != "IN":
        return primary
    fb = from_screener()
    if fb.empty:
        return primary
    if primary.empty:
        return fb
    gap = fb[~fb["ticker"].isin(set(primary["ticker"]))]
    return pd.concat([primary, gap], ignore_index=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="cash conversion cycle from filings")
    ap.add_argument("--market", default="IN", choices=sorted(STORE))
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--no-fallback", action="store_true",
                    help="filings only; never fall back to the scraped screen")
    ap.add_argument("--compare", action="store_true",
                    help="filings vs screener.in on the tickers both cover")
    a = ap.parse_args()

    if a.compare:
        f, s = from_filings(a.market), from_screener()
        if f.empty or s.empty:
            print("  need both sources to compare"); return 1
        m = f.merge(s, on="ticker", suffixes=("_filings", "_screener"))
        m["diff"] = m["ccc_filings"] - m["ccc_screener"]
        print(f"=== filings vs screener.in · {len(m)} tickers in both ===")
        print(f"  {'TICKER':14}{'FILINGS':>10}{'SCREENER':>10}{'DIFF':>9}")
        for _, r in m.reindex(m["diff"].abs().sort_values(ascending=False).index).head(a.top).iterrows():
            print(f"  {r.ticker:14}{r.ccc_filings:>9.1f}d{r.ccc_screener:>9.1f}d{r['diff']:>8.1f}d")
        print(f"\n  median |diff| {m['diff'].abs().median():.1f}d · "
              f"agree within 10d: {(m['diff'].abs() <= 10).mean():.0%}")
        return 0

    d = ccc(a.market, allow_fallback=not a.no_fallback)
    if d.empty:
        print(f"  no CCC available for {a.market}"); return 1
    d = d.sort_values("ccc")
    print(f"=== cash conversion cycle · {a.market} · {len(d)} tickers ===")
    print(f"  {'TICKER':14}{'CCC':>8}{'DSO':>8}{'DIO':>8}{'DPO':>8}  SOURCE")
    for _, r in d.head(a.top).iterrows():
        f = lambda v: f"{v:>7.1f}" if pd.notna(v) else "      —"
        print(f"  {str(r.ticker):14}{f(r.ccc)}d{f(r.dso)} {f(r.dio)} {f(r.dpo)}  {r.source}")
    by = d.groupby("source").size().to_dict()
    print(f"\n  negative CCC (supplier-funded): {(d['ccc'] < 0).sum()} · "
          f"sources: {', '.join(f'{k} {v}' for k, v in by.items())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
