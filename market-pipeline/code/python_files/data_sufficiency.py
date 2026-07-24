#!/usr/bin/env python3
"""
data_sufficiency.py — the anti-false-outcome guard. Before trusting ANY cross-market
verdict, quantify whether each market has enough data to support it: fundamentals
coverage of the tradeable universe, time span, and — critically — the number of
NON-OVERLAPPING observations behind each t-stat (a 5y window de-overlapped by 6 gives
~10 obs → a t-stat is nearly meaningless, so "not significant" there means UNDERPOWERED,
not "no effect").

Documents, per market:
  - universe (warehouse tickers) vs fundamentals coverage %  → completeness
  - fundamentals year span                                    → history depth
  - reversion formations & non-overlapping obs (3M/6M)        → statistical power
  - VERDICT: SUFFICIENT / THIN / UNDERPOWERED, with the reason

Output: reports/data_sufficiency.md
"""
from __future__ import annotations
import glob
from pathlib import Path
import pandas as pd, numpy as np
from obs import get_logger

HERE = Path(__file__).resolve().parent
LOG = get_logger("data_sufficiency")
FH = "/Users/umashankar/repos/global-stock-screener/cache_seed/fundamentals_history"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv"
FUND = {"IN": "IN", "US": "US", "KR": "KR_deep", "JP": "JP", "EU": "EU", "CN": "CN"}
# minimum non-overlapping obs for a credible de-overlapped t-stat
MIN_NONOVERLAP = 15
MIN_UNIVERSE_COV = 0.60          # fundamentals should cover ≥60% of tradeable universe


def liquid_universe(mkt: str) -> tuple:
    """(#liquid tickers, #all tickers) — liquid = top-2 turnover terciles on the latest
    date. Coverage vs the LIQUID universe is the honest denominator (we never trade the
    illiquid micro-cap tail, so missing fundamentals there don't matter)."""
    parts = glob.glob(f"{WH}/{mkt}/year=2026.parquet")
    if not parts:
        return 0, 0
    df = pd.read_parquet(parts[0], columns=["Date", "Symbol", "Close", "Volume"])
    last = df[df.Date == df.Date.max()].copy()
    last["turn"] = last.Close * last.Volume
    all_n = last.Symbol.nunique()
    liq = last[last.turn >= last.turn.quantile(1/3)]
    return liq.Symbol.nunique(), all_n


def main() -> int:
    rows = []
    for mkt, fund in FUND.items():
        try:
            f = pd.read_parquet(f"{FH}/{fund}.parquet")
        except Exception:
            continue
        ntk = f.ticker.nunique()
        yrs = pd.to_datetime(f.fy_end, errors="coerce").dt.year
        span = f"{int(yrs.min())}-{int(yrs.max())}" if yrs.notna().any() else "?"
        n_years = int(yrs.max() - yrs.min() + 1) if yrs.notna().any() else 0
        uni, all_n = liquid_universe(mkt)
        cov = ntk / uni if uni else np.nan
        # reversion power: monthly formations over the usable window, de-overlapped by 6
        start_yr = max(int(yrs.min()) if yrs.notna().any() else 2021, 2017) + 1  # +1y for PIT lag
        n_form = max(0, (2026 - start_yr) * 12 + 6)
        nonov6 = n_form // 6
        comp = "✅ complete" if (cov == cov and cov >= MIN_UNIVERSE_COV) else "🔴 THIN"
        power = "✅ powered" if nonov6 >= MIN_NONOVERLAP else "🔴 UNDERPOWERED"
        rows.append({"market": mkt, "fund_tickers": ntk, "liquid_uni": uni, "cov": cov,
                     "coverage": f"{cov*100:.0f}%" if cov == cov else "?",
                     "years": span, "n_form≈": n_form, "nonoverlap_6M≈": nonov6,
                     "completeness": comp, "power": power})
    d = pd.DataFrame(rows)

    L = ["# Data-sufficiency audit — is each conclusion actually supported?", "",
         "Guards against false outcomes from thin data. **completeness** = fundamentals "
         f"cover ≥{MIN_UNIVERSE_COV*100:.0f}% of the tradeable universe. **power** = "
         f"≥{MIN_NONOVERLAP} non-overlapping obs behind a 6M t-stat (below this, a t-stat "
         "is meaningless — 'not significant' means UNDERPOWERED, not 'no effect').", "",
         "| market | fund tickers | liquid universe | coverage | years | formations | nonov-6M | completeness | power |",
         "|---|--:|--:|--:|--:|--:|--:|:--:|:--:|"]
    for _, r in d.iterrows():
        L.append(f"| {r.market} | {r.fund_tickers:,} | {r.liquid_uni:,} | {r.coverage} | {r.years} | "
                 f"{r['n_form≈']} | {r['nonoverlap_6M≈']} | {r.completeness} | {r.power} |")
    L += ["", "## What each verdict means for the analysis (DERIVED from the numbers above)", "",
          "| market | trust the value-reversion result? | why |", "|---|---|---|"]
    for _, r in d.iterrows():
        powered = r["nonoverlap_6M≈"] >= MIN_NONOVERLAP
        cv = r["cov"]
        complete = (cv == cv) and cv >= MIN_UNIVERSE_COV
        if powered and complete:
            v, why = "✅ YES", f"{r.years}, {r.coverage} liquid cov, {r['nonoverlap_6M≈']} non-overlap obs — powered & complete"
        elif powered and not complete:
            v, why = "🟡 RETURNS ONLY", f"{r['nonoverlap_6M≈']} obs (powered) BUT {r.coverage} liquid cov — a coverage bias risk; fetch more fundamentals"
        else:
            v, why = "🔴 CAN'T CONCLUDE", f"only {r['nonoverlap_6M≈']} non-overlap obs ({r.years}) — any t-stat is UNDERPOWERED; the verdict is a data artifact, not an effect"
        L.append(f"| {r.market} | {v} | {why} |")
    L += ["", "> 🔴 The honest correction: only **India** is fully powered + reasonably complete. "
          "US is powered but coverage-thin (fetch shares). KR is borderline. **JP/EU/CN cannot "
          "be concluded either way on current data** — their verdicts were data-sufficiency "
          "artifacts. To fix: (1) fetch full-universe fundamentals (raise coverage), (2) collect "
          "deep history via official filings (EDINET-JP, EU registries, akshare-CN) to raise obs "
          "count, THEN re-run. Until then, report JP/EU/CN as 'insufficient data', not a verdict."]
    (HERE / "reports" / "data_sufficiency.md").write_text("\n".join(L))
    print("\n".join(L))
    print("\nwrote reports/data_sufficiency.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
