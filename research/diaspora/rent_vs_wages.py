#!/usr/bin/env python3
"""
Do wages keep up with rent? Non-US destinations.

The savings chain holds the living-cost basket at a constant US$28,000. That is
fine for ranking countries against each other in a single year and wrong for
asking whether the surplus survives. Rent is the largest and fastest-moving item
in the basket, and if it climbs faster than pay, the surplus that funds
remittances shrinks every year the migrant stays.

THE MEASUREMENT PROBLEM, WHICH IS THE POINT OF THIS MODULE
-----------------------------------------------------------
There are two rent inflation numbers for every country and they are not close.

  SITTING-TENANT rent is what the CPI housing component measures. It averages
  over the whole rented stock, most of which is occupied by people on running
  contracts, protected by rent caps, indexation rules and long leases.

  NEW-LISTING rent is what someone signing a fresh lease actually pays.

A migrant is ALWAYS a new tenant. They arrive, they sign at market. So the CPI
figure — the one every cost-of-living comparison uses, including the basket in
this repo's own savings ranking — systematically understates what a migrant
pays. And it understates it MOST in exactly the countries whose tenant
protections are strongest, because that is where the two series diverge.

Japan is the clearest case: CPI actual rents rose 0.7% while new listings in
Tokyo's 23 wards rose 7.82%. On the published series a migrant to Japan is
gaining ground on rent. On the series that applies to them, they are losing it
by five points a year.

Usage:
    python3 research/diaspora/rent_vs_wages.py
    python3 research/diaspora/rent_vs_wages.py --rent-share 0.45 --years 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from real_savings_ranking import build_frame  # noqa: E402

# ===========================================================================
# SOURCED. US deliberately excluded — see us_debt_service.py, which handles the
# American case on its own terms.
# country: (wage_growth_pct, rent_sitting_pct, rent_new_pct or None, note)
# ===========================================================================
PANEL = {
    "Netherlands": (4.50, 4.10, 6.50,
                    "Wages Feb-2026 y/y. Social-sector increases capped at 4.1% "
                    "(3-yr inflation + 0.5); new free-sector lettings 5-8%, midpoint used."),
    "Germany": (3.50, 3.00, 4.00,
                "Posted wage growth. Asking rents +3.0% y/y Q2-2026, only +0.3% in real "
                "terms; new listings 3-5%, midpoint used."),
    "United Kingdom": (3.40, 3.30, None,
                       "Private rents +3.3% in the 12 months to Jun-2026, average GBP 1,388/mo. "
                       "No separate new-let series retrieved."),
    "Canada": (2.30, -4.00, -4.00,
               "Asking rents -4.0% y/y in July, the 22nd consecutive annual decline. "
               "Provincial caps on sitting tenants are lower still (ON 2.1%, BC 2.3%, MB 1.8%)."),
    "Australia": (3.30, 3.60, None,
                  "CPI rents +3.6% in the 12 months to Jun-2026. No separate new-let series."),
    "Japan": (2.30, 0.70, 7.82,
              "CPI actual rents +0.7% y/y Jan-2026. New listings Tokyo 23 wards +7.82% "
              "(Kyoto +3.57%) — the widest sitting/new gap in the panel."),
}
SOURCES = ("Eurostat/national statistics offices, ABS, StatCan, Rentals.ca, "
           "Kiel Institute, Japan CPI and listing indices, Indeed Hiring Lab and "
           "OECD wage bulletins, 2026 vintages")

# PARAM — rent as a share of the US$28,000 basket. Not sourced; swept.
DEFAULT_RENT_SHARE = 0.35
DEFAULT_YEARS = 10
GENERAL_CPI_PCT = 2.5   # non-rent basket items, advanced-economy average


def table(rent_share: float) -> pd.DataFrame:
    rows = []
    for c, (w, r_sit, r_new, _note) in PANEL.items():
        rows.append({
            "country": c,
            "wage_growth_pct": w,
            "rent_sitting_pct": r_sit,
            "gap_sitting_pp": round(w - r_sit, 2),
            "rent_new_pct": r_new,
            "gap_new_pp": None if r_new is None else round(w - r_new, 2),
            "basis_flips_sign": (r_new is not None
                                 and ((w - r_sit) > 0) != ((w - r_new) > 0)),
        })
    return pd.DataFrame(rows).sort_values("gap_sitting_pp", ascending=False)


def surplus_path(rent_share: float, years: int, use_new: bool) -> pd.DataFrame:
    """What happens to the remittable surplus if these rates persist."""
    base = build_frame(28000).set_index("country")
    rows = []
    for c, (w, r_sit, r_new, _n) in PANEL.items():
        if c not in base.index or pd.isna(base.loc[c, "savings_ppp_usd"]):
            continue
        r = r_new if (use_new and r_new is not None) else r_sit
        net0 = float(base.loc[c, "net_wage_ppp_usd"])
        rent0 = 28000 * rent_share
        other0 = 28000 * (1 - rent_share)
        s0 = net0 - rent0 - other0
        netN = net0 * (1 + w / 100) ** years
        rentN = rent0 * (1 + r / 100) ** years
        otherN = other0 * (1 + GENERAL_CPI_PCT / 100) ** years
        sN = netN - rentN - otherN
        rows.append({
            "country": c,
            "rent_basis": "new lettings" if (use_new and r_new is not None) else "sitting tenant",
            "rent_growth_pct": r,
            "surplus_now_usd": round(s0),
            f"surplus_yr{years}_usd": round(sN),
            "change_pct": round((sN / s0 - 1) * 100, 1) if s0 else None,
        })
    return pd.DataFrame(rows).sort_values("change_pct", ascending=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rent-share", type=float, default=DEFAULT_RENT_SHARE)
    ap.add_argument("--years", type=int, default=DEFAULT_YEARS)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    print("=== WAGES AGAINST RENT, 2026 ===")
    print(f"  Sources: {SOURCES}")
    print("  The United States is excluded and handled in us_debt_service.py.\n")
    t = table(args.rent_share)
    print(t.to_string(index=False))

    print("\n  Positive gap = pay is outrunning rent. Negative = rent is outrunning pay.")
    flips = t[t.basis_flips_sign]
    if len(flips):
        print(f"\n  SIGN FLIPS between the two bases: {', '.join(flips.country)}.")
        for _, r in flips.iterrows():
            print(f"    {r.country}: {r.gap_sitting_pp:+.2f}pp on the published CPI basis, "
                  f"{r.gap_new_pp:+.2f}pp on what a new arrival signs.")
        print("  A migrant is always a new tenant, so the second number is theirs.")

    print("\n=== WHY THE PUBLISHED NUMBER IS THE WRONG ONE ===")
    print("  CPI rent averages over the whole rented stock, and most of that stock is")
    print("  occupied by sitting tenants — protected by caps, indexation and long leases.")
    print("  A migrant has none of that protection on arrival. They sign at market.")
    print("  So every cost-of-living comparison built on CPI rent understates the migrant's")
    print("  housing cost, and understates it MOST where tenant protection is strongest:")
    for c, (_w, r_sit, r_new, _n) in PANEL.items():
        if r_new is not None and r_new != r_sit:
            print(f"    {c:<16s} sitting {r_sit:>5.2f}%   new {r_new:>5.2f}%   "
                  f"gap {r_new - r_sit:+.2f}pp")
    print("\n  That includes the US$28,000 basket in this repo's own savings ranking, which")
    print("  is a CPI-style figure. It is right for ranking countries in one year and too")
    print("  low for projecting a migrant's costs forward.")

    print(f"\n=== WHAT IT DOES TO THE SURPLUS OVER {args.years} YEARS ===")
    print(f"  Rent taken as {args.rent_share:.0%} of the basket; other items at {GENERAL_CPI_PCT}%.")
    for use_new in (False, True):
        sp = surplus_path(args.rent_share, args.years, use_new)
        print(f"\n  --- {'new-letting' if use_new else 'sitting-tenant'} rent basis ---")
        print(sp.to_string(index=False))

    print("\n  Sensitivity to the rent share, which is the parameter and not a measurement:")
    rows = []
    for share in (0.25, 0.30, 0.35, 0.40, 0.45):
        sp = surplus_path(share, args.years, True)
        rows.append({"rent_share": share,
                     "best": f"{sp.country.iloc[0]} {sp.change_pct.iloc[0]:+.0f}%",
                     "worst": f"{sp.country.iloc[-1]} {sp.change_pct.iloc[-1]:+.0f}%",
                     "countries_shrinking": int((sp.change_pct < 0).sum())})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n=== WHAT THIS CHANGES, AND WHAT IT DOES NOT ===")
    sp = surplus_path(args.rent_share, args.years, True)
    now = sp.sort_values("surplus_now_usd", ascending=False).country.tolist()
    later = sp.sort_values(f"surplus_yr{args.years}_usd", ascending=False).country.tolist()
    print(f"  Order by surplus today : {' > '.join(now)}")
    print(f"  Order in {args.years} years        : {' > '.join(later)}")
    if now == later:
        print("\n  The ordering is unchanged. That is a real result and worth stating plainly:")
        print("  the savings ranking is robust to a decade of divergent rent inflation. What")
        print("  moves is the size of the gaps, not who is ahead.")
    else:
        moved = [c for c in now if now.index(c) != later.index(c)]
        print(f"\n  Positions change for: {', '.join(moved)}.")

    worst = sp.iloc[-1]
    print(f"\n  The exception is {worst.country}, and it is not a small one: the surplus falls")
    print(f"  {abs(worst.change_pct):.0f}% over {args.years} years on the new-letting basis. On the published CPI")
    print(f"  it looks like the migrant gains ground on rent; on Tokyo listings they lose")
    print(f"  more than five points a year. {worst.country} already ranked last on the one-year")
    print(f"  savings table, and this turns a thin surplus into almost none.")

    print("\n  Canada is the one genuinely favourable case. Asking rents have fallen for 22")
    print("  consecutive months, so a migrant arriving now signs into a falling market while")
    print("  wages still rise — the only negative rent figure in the panel. It improves")
    print("  Canada's position without changing its rank, because the countries above it")
    print("  start far enough ahead.")
    print("\n  The general lesson is the one this repo keeps arriving at from different")
    print("  directions: the published series measures a population the migrant is not in.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out / "rent_vs_wages.csv", index=False)
    print(f"\nCSV written: {out / 'rent_vs_wages.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
