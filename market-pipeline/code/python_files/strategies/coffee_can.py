#!/usr/bin/env python3
# Coffee Can Portfolio — Saurabh Mukherjea: long-term consistency, high ROE,
# steady revenue growth, low leverage. "Buy and forget" quality compounders.
from __future__ import annotations
from .base import StockData, Result, safe, cagr

META = {"name": "Coffee Can Portfolio", "slug": "coffee_can", "category": "fundamental",
        "description": "Consistent high-ROE compounders with steady revenue growth and "
                       "low debt (Saurabh Mukherjea philosophy).",
        "needs": "fundamentals"}
ROE_MIN = 15.0          # %
REV_GROWTH_MIN = 10.0   # % CAGR
DE_MAX = 1.0


def screen(s: StockData) -> Result | None:
    g = s.f
    roe = safe(g("roe"))
    roe_hist = g("roe_history") or []        # list of yearly ROE, newest-first
    rev, rev_old = safe(g("revenue")), safe(g("revenue_5y_ago"))
    de = safe(g("debt_to_equity"))
    if roe is None and not roe_hist:
        return None
    roe_vals = [safe(x) for x in roe_hist if safe(x) is not None]
    # Current ROE falls back to the newest history year, so a stock that only
    # carries roe_history is not failed by `(roe or 0)`.
    roe_now = roe if roe is not None else (roe_vals[0] if roe_vals else None)
    # Year-after-year ROE is the core of Coffee Can, but it was computed and then
    # left out of `passed` — one good year passed. It now gates the pass whenever
    # history exists. None = no history to judge (no caller supplies roe_history
    # today), which is reported as unverified rather than failed.
    consistent = all(v >= ROE_MIN for v in roe_vals) if roe_vals else None
    rev_cagr = cagr(rev, rev_old, 5) if rev and rev_old else None
    checks = {
        "ROE>=15": int(roe_now is not None and roe_now >= ROE_MIN),
        "ROE_consistent": None if consistent is None else int(consistent),
        "RevCAGR>=10": int(rev_cagr is not None and rev_cagr >= REV_GROWTH_MIN),
        "DE<=1": int(de is not None and de <= DE_MAX),
    }
    passed = (checks["ROE>=15"] and checks["RevCAGR>=10"] and checks["DE<=1"]
              and consistent is not False)
    note = ""
    if passed:
        note = "quality compounder" + (" (ROE consistency unverified)" if consistent is None else "")
    return Result(s.symbol, META["slug"], passed=bool(passed),
                  score=round(roe_now, 2) if roe_now is not None else 0.0,
                  metrics={"ROE": roe_now,
                           "RevCAGR5y": round(rev_cagr, 1) if rev_cagr is not None else None,
                           "DE": de, **checks},
                  note=note)
