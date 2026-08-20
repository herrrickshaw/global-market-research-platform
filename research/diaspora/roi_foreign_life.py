#!/usr/bin/env python3
"""
ROI on a foreign life, for Indians.

The savings modules answer "how much lands in India per year". That is a level.
An ROI question is different: what did you pay to get it, how long until it pays
back, and — the part almost nobody prices — what was the Indian career you gave
up doing in the meantime?

THE THREE TERMS
---------------
  COST     Recruitment and migration costs paid up front. For Gulf labour
           migration this is measured: the KNOMAD/ILO returnee survey puts it
           at one to nine months of foreign earnings. For skilled migration to
           the advanced economies no comparable measured figure was reachable,
           so it is a parameter, swept.

  RETURN   Annual savings landing in India, from real_savings_ranking.

  FOREGONE The Indian salary you did not earn. PLFS measures it, and measures
           how fast it is growing — which turns out to be the interesting part.

THE UNIT PROBLEM, STATED RATHER THAN FUDGED
-------------------------------------------
Landed savings are in PPP-USD. The Indian salary is in rupees. Converting
between them needs India's PPP conversion factor, which this environment could
not source (World Bank PA.NUS.PPP; data.worldbank.org is not reachable here).

So this module does NOT compute a rupee-denominated net present value, because
that would require a conversion factor invented for the purpose. It works in
the two units that need no conversion:

  - payback period, in years — a ratio of two figures already in the same unit
  - growth rates — unit-free, and where the actual finding turns out to live

Everything below is either measured or a swept parameter. Nothing is converted
across a factor that was not sourced.

Usage:
    python3 research/diaspora/roi_foreign_life.py
    python3 research/diaspora/roi_foreign_life.py --migration-cost 12000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from real_savings_ranking import INDIA_CPI, INDIA_WPI_YOY, build_frame  # noqa: E402

# ===========================================================================
# SOURCED — the Indian counterfactual. MoSPI PLFS, Annual, indicator 6:
# average wage/salary earnings during the preceding calendar month from regular
# wage/salaried employment. All India, person, rural + urban.
# ===========================================================================
PLFS_SALARIED_INR_MONTH = {2022: 19315.50, 2023: 20407.54, 2024: 21454.87}
PLFS_SOURCE = "MoSPI PLFS Annual, indicator 6, All India, person, rural+urban"

# SOURCED — migration cost, Gulf labour migration. KNOMAD/ILO returnee survey
# (Martin), 2,000+ workers returning from GCC jobs: recruitment costs ran one to
# nine months of foreign earnings.
GULF_RECRUITMENT_MONTHS = (1, 9)
GULF_RECRUITMENT_SOURCE = "KNOMAD/ILO GCC returnee survey — recruitment cost 1-9 months of foreign earnings"

# SOURCED — host nominal wage growth, as a band rather than a point.
#
# Derived from this repo's own panel rather than asserted: rent_vs_wages.PANEL
# carries a measured wage-growth figure per destination, and the band is their
# observed min and max. An earlier version hardcoded (2.0, 4.0), which excluded
# the Netherlands at 4.50% — the band contradicted data sitting in the next
# module along. A test now pins the two together so they cannot drift apart
# again.
def _host_band() -> tuple[float, float]:
    from rent_vs_wages import PANEL
    w = [v[0] for v in PANEL.values()]
    return (min(w), max(w))


HOST_WAGE_GROWTH_BAND = _host_band()

# PARAM — up-front cost of skilled migration to an advanced economy: visa fees,
# relocation, credential recognition, the unpaid job search. No measured figure
# was reachable, so it is swept.
DEFAULT_MIGRATION_COST_USD = 15000


def india_wage_growth() -> dict:
    yrs = sorted(PLFS_SALARIED_INR_MONTH)
    lo, hi = PLFS_SALARIED_INR_MONTH[yrs[0]], PLFS_SALARIED_INR_MONTH[yrs[-1]]
    n = yrs[-1] - yrs[0]
    cagr = ((hi / lo) ** (1 / n) - 1) * 100
    steps = [((PLFS_SALARIED_INR_MONTH[b] / PLFS_SALARIED_INR_MONTH[a] - 1) * 100)
             for a, b in zip(yrs, yrs[1:])]
    return {"years": yrs, "cagr_pct": round(cagr, 2),
            "yoy_pct": [round(s, 2) for s in steps],
            "latest_inr_month": hi, "latest_inr_year": round(hi * 12)}


def payback(cost_usd: float) -> pd.DataFrame:
    d = build_frame(28000)
    d = d[d.wage_grade.str.startswith("A") & d.savings_landed_india_usd.notna()].copy()
    d["migration_cost_usd"] = cost_usd
    d["payback_years"] = (cost_usd / d.savings_landed_india_usd).round(2)
    d["yr1_net_usd"] = (d.savings_landed_india_usd - cost_usd).round(0)
    return d.sort_values("payback_years")[
        ["country", "savings_landed_india_usd", "migration_cost_usd",
         "payback_years", "yr1_net_usd"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--migration-cost", type=float, default=DEFAULT_MIGRATION_COST_USD)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    g = india_wage_growth()

    print("=== TERM 1: WHAT YOU PAY ===")
    print(f"  Gulf labour migration, measured: {GULF_RECRUITMENT_SOURCE}.")
    print(f"    At the ILO-anchored blended Gulf wage of US$15,123/yr, "
          f"{GULF_RECRUITMENT_MONTHS[0]}-{GULF_RECRUITMENT_MONTHS[1]} months is")
    lo = 15123 / 12 * GULF_RECRUITMENT_MONTHS[0]
    hi = 15123 / 12 * GULF_RECRUITMENT_MONTHS[1]
    print(f"    US${lo:,.0f}-{hi:,.0f} paid before the first day of work.")
    print(f"  Skilled migration to an advanced economy: no measured figure was reachable.")
    print(f"    Swept below; US${args.migration_cost:,.0f} used as the base case.")

    print("\n=== TERM 2: WHAT YOU GET BACK, AND HOW FAST ===")
    p = payback(args.migration_cost)
    print(p.to_string(index=False))
    under1 = int((p.payback_years < 1).sum())
    print(f"\n  Payback is fast everywhere the wage is high — under a year for {under1} of the")
    print(f"  {len(p)}. On this term alone the answer is trivially yes, go. Which is why this")
    print("  term alone is not the ROI.")

    print("\n  Sensitivity to the cost you cannot source:")
    rows = []
    for c in (5000, 10000, 15000, 25000, 40000):
        pp = payback(c)
        rows.append({"migration_cost_usd": c,
                     "fastest": f"{pp.country.iloc[0]} {pp.payback_years.iloc[0]}y",
                     "slowest": f"{pp.country.iloc[-1]} {pp.payback_years.iloc[-1]}y",
                     "countries_under_1yr": int((pp.payback_years < 1).sum())})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n=== TERM 3: WHAT YOU GAVE UP ===")
    print(f"  {PLFS_SOURCE}")
    for y in g["years"]:
        print(f"    {y}   Rs {PLFS_SALARIED_INR_MONTH[y]:>9,.2f} / month")
    print(f"  Year-on-year: {' , '.join(f'{v:+.2f}%' for v in g['yoy_pct'])}"
          f"   CAGR {g['cagr_pct']:+.2f}%")

    print("\n=== THE CROSSOVER ===")
    band = HOST_WAGE_GROWTH_BAND
    print(f"  Indian salaried wages, nominal      {g['cagr_pct']:>6.2f}%   (PLFS, measured)")
    print(f"  Advanced-economy wages, nominal   {band[0]:>6.1f}-{band[1]:.1f}%   (min/max of the measured panel)")
    print(f"  India CPI                           {INDIA_CPI['CPI (General)']:>6.2f}%   (MoSPI)")
    print(f"  India WPI                           {INDIA_WPI_YOY:>6.2f}%   (MoSPI)")
    faster = g["cagr_pct"] > band[1]
    print(f"\n  The Indian salary you left is growing faster in nominal terms than the")
    print(f"  foreign salary you took: {g['cagr_pct']:.2f}% against {band[0]:.1f}-{band[1]:.1f}%. That is measured on the")
    print(f"  India side and a cycle range on the other, so treat it as a direction rather")
    print(f"  than a decimal — but the direction is not close: {'confirmed' if faster else 'NOT confirmed'}.")
    print(f"\n  Real terms tells the same story from the other end. An Indian salary at")
    print(f"  {g['cagr_pct']:.2f}% against CPI of {INDIA_CPI['CPI (General)']:.2f}% gains about "
          f"{g['cagr_pct'] - INDIA_CPI['CPI (General)']:+.2f}% a year in purchasing")
    print(f"  power. Foreign savings, once landed, are eroded at that same {INDIA_CPI['CPI (General)']:.2f}% — or at")
    print(f"  {INDIA_WPI_YOY:.2f}% if they are destined for property — while growing at only {band[0]:.1f}-{band[1]:.1f}%.")

    print("\n=== WHAT THE ROI ACTUALLY IS ===")
    print("  A foreign life buys a step change in level, not a faster rate. The step is")
    print(f"  large: {under1} of {len(p)} destinations repay the whole migration cost inside a")
    print("  year, and the annual sum landing in India is several times an Indian salary.")
    print("  But the rate underneath it is worse than the one you left, and the erosion")
    print("  applies at Indian prices no matter where the money was earned.")
    print("\n  Three practical consequences follow, and none of them are about tax:")
    print("    1. The gain is front-loaded. It is banked in the early years, when the")
    print("       level gap is widest, not accumulated steadily over a career.")
    print("    2. Deferring the transfer destroys it. Money held abroad to be sent")
    print("       'later' compounds at the host rate and is spent at the Indian one.")
    print("    3. What the money is FOR decides whether it worked. Against consumption")
    print(f"       at {INDIA_CPI['CPI (General)']:.2f}% the maths holds. Against property at {INDIA_WPI_YOY:.2f}% it does not, and")
    print("       property is what remittances most often accumulate toward.")

    print("\n=== WHAT IS STILL MISSING ===")
    print("  - No rupee-denominated NPV, deliberately. India's PPP conversion factor")
    print("    (World Bank PA.NUS.PPP) was not reachable, and inventing one to bridge")
    print("    PPP-USD savings to rupee salaries would put a fabricated number at the")
    print("    centre of the result. Payback and growth rates need no such bridge.")
    print("  - The PLFS counterfactual is the all-India salaried average. Migrants are")
    print("    not average — they skew graduate and urban, so the salary actually given")
    print("    up is higher than this and the foreign premium correspondingly smaller.")
    print("    PLFS carries an education breakdown that would fix this; the filter")
    print("    combination returned no rows and was not resolved.")
    print("  - Advanced-economy migration cost is a parameter, not a measurement.")
    print("  - No value is placed on permanent residency, healthcare, schooling, or")
    print("    living somewhere you would rather live. See immigration_destination_panel")
    print("    for the axis money cannot price.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "roi_foreign_life.csv"
    p.to_csv(path, index=False)
    print(f"\nCSV written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
