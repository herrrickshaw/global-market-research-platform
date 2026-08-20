#!/usr/bin/env python3
"""
Occupation-controlled salaries — because national averages answer the wrong question.

THE PROBLEM WITH EVERY WAGE FIGURE USED SO FAR
-----------------------------------------------
The savings ranking runs on OECD average annual wages: one number per country,
averaged across every job in the economy. Indian migrants are not an
economy-wide sample. They concentrate in technology, medicine, engineering and
finance, so an economy-wide average describes a population they are not in —
the same failure this directory has found in the remittance shares, the CPI rent
series and the Gulf wage data.

This module fixes it by comparing like occupations across countries, and — the
part that matters most — including India on the same basis, which finally makes
the "should I go at all" comparison computable.

THE UNIT RULE, WHICH IS NOT NEGOTIABLE
---------------------------------------
OECD average wages are PPP-converted. The salaries here are market-rate. Those
are different units and dividing one by the other is meaningless. Two earlier
attempts in this project were wrecked by exactly that mistake, and one was
caught only because it implied a 0.19% tax rate in Switzerland.

So this module never compares an occupation salary to an OECD average. It only
ever compares occupation to occupation, at market rates, which is the
comparison a migrant actually faces: their salary abroad against their salary at
home, both converted at the rate their bank gives them.

Usage:
    python3 research/diaspora/occupation_wages.py
    python3 research/diaspora/occupation_wages.py --inr 92
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from real_savings_ranking import WAGE_PPP_USD_2024  # noqa: E402

# ===========================================================================
# SOURCED — market exchange rates, units of local currency per USD, Aug-2026.
# ===========================================================================
FX_PER_USD = {"USD": 1.0, "GBP": 0.73822, "EUR": 0.8641,
              "CAD": 1.38724, "AUD": 1.4111, "INR": 95.43}
FX_SOURCE = ("Federal Reserve H.10 / HMRC monthly rates / HDFC treasury card rates, "
             "August 2026. INR taken at 95.43, the mid of a 93.99/97.42 bid-ask.")

# SOURCED — advertised/reported salary by occupation, in LOCAL currency.
# occupation: {country: (amount, currency, note)}
SALARIES = {
    "software engineer": {
        "United States": (151136, "USD", "Glassdoor 2026 national average"),
        "Australia": (120000, "AUD", "Glassdoor 2026 national average"),
        "Canada": (104196, "CAD", "Glassdoor 2026 national average"),
        "United Kingdom": (56086, "GBP", "Glassdoor 2026 national average"),
        "India": (900000, "INR", "Glassdoor 2026 national average"),
    },
    "registered nurse": {
        "United States": (101420, "USD", "2026 national average"),
        "Canada": (90118, "CAD", "2026 national average"),
        "Australia": (88000, "AUD", "2026 national median"),
        "Germany": (37143, "EUR", "2026 national average"),
        "United Kingdom": (31273, "GBP", "2026 national average"),
        "India": (950000, "INR", "2026 national median"),
    },
}

# Deliberately excluded. The German software-engineer figure that surfaced was
# quoted in USD by an aggregator with no stated conversion basis — it cannot be
# placed on the same footing as the local-currency figures above, and guessing
# which basis it used is how the errors in this project have happened.
EXCLUDED = {("software engineer", "Germany"):
            "quoted in USD by an aggregator, conversion basis unstated"}

# Indian city and seniority variants, kept apart from the national figure
# because migrants are drawn disproportionately from the top of this range —
# which makes the counterfactual salary higher and the gain smaller.
INDIA_VARIANTS = {
    "software engineer, Bangalore": (1297600, "INR"),
    "senior software engineer, India": (1671574, "INR"),
}


def to_usd(amount: float, currency: str, fx: dict[str, float]) -> float:
    return amount / fx[currency]


def table(fx: dict[str, float]) -> pd.DataFrame:
    rows = []
    for occ, by_country in SALARIES.items():
        india = to_usd(*by_country["India"][:2], fx)
        for country, (amt, cur, note) in by_country.items():
            usd = to_usd(amt, cur, fx)
            rows.append({
                "occupation": occ,
                "country": country,
                "local_amount": amt,
                "currency": cur,
                "usd_market": round(usd),
                "multiple_of_india": round(usd / india, 1),
                "source_note": note,
            })
    return pd.DataFrame(rows)


def ordering(df: pd.DataFrame, occ: str) -> list[str]:
    d = df[(df.occupation == occ) & (df.country != "India")]
    return d.sort_values("usd_market", ascending=False).country.tolist()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inr", type=float, default=None, help="override INR per USD")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    fx = dict(FX_PER_USD)
    if args.inr:
        fx["INR"] = args.inr
    print("=== EXCHANGE RATES ===")
    print(f"  {FX_SOURCE}")
    print("  " + "  ".join(f"{k} {v:g}" for k, v in fx.items()))

    df = table(fx)

    for occ in SALARIES:
        print(f"\n=== {occ.upper()} ===")
        d = df[df.occupation == occ].sort_values("usd_market", ascending=False)
        print(d[["country", "local_amount", "currency", "usd_market",
                 "multiple_of_india"]].to_string(index=False))

    print("\n=== THE COUNTRY ORDERING DEPENDS ON THE OCCUPATION ===")
    orders = {occ: ordering(df, occ) for occ in SALARIES}
    for occ, o in orders.items():
        print(f"  {occ:<20s} {' > '.join(o)}")
    common = set.intersection(*(set(o) for o in orders.values()))
    pairs = {occ: [c for c in o if c in common] for occ, o in orders.items()}
    same = len({tuple(v) for v in pairs.values()}) == 1
    print(f"\n  Restricted to the {len(common)} countries present in both: ")
    for occ, o in pairs.items():
        print(f"    {occ:<20s} {' > '.join(o)}")
    print(f"  Same ordering across occupations: {same}")
    if not same:
        print("  So there is no single 'best country' — only a best country for a job.")

    print("\n=== HOW BIG IS THE GAIN, REALLY ===")
    for occ in SALARIES:
        d = df[(df.occupation == occ) & (df.country != "India")]
        print(f"  {occ:<20s} {d.multiple_of_india.min():.1f}x to "
              f"{d.multiple_of_india.max():.1f}x an Indian salary in the same job")
    print("\n  This is the comparison roi_foreign_life could not make. It needed the")
    print("  Indian salary and the foreign salary in one unit, and the PPP conversion")
    print("  factor was unreachable. Same occupation, same source, market rates on both")
    print("  sides — no conversion factor required.")

    print("\n=== WHAT WOULD SHRINK THESE MULTIPLES ===")
    india_swe = to_usd(*SALARIES["software engineer"]["India"][:2], fx)
    us_swe = to_usd(*SALARIES["software engineer"]["United States"][:2], fx)
    print(f"  The Indian figure is a NATIONAL average: US${india_swe:,.0f} for a software")
    print("  engineer. Migrants are not drawn from the national average — they come")
    print("  disproportionately from the top of it:")
    for label, (amt, cur) in INDIA_VARIANTS.items():
        v = to_usd(amt, cur, fx)
        print(f"    {label:<34s} US${v:>7,.0f}   US multiple falls to {us_swe / v:.1f}x")
    print("\n  So every multiple above is an UPPER bound on the gain. Against the salary")
    print("  a realistic candidate actually leaves behind, the US premium is closer to")
    print(f"  {us_swe / to_usd(*INDIA_VARIANTS['senior software engineer, India'], fx):.0f}x than to "
          f"{us_swe / india_swe:.0f}x.")

    print("\n=== WHAT THIS MODULE REFUSES TO DO ===")
    print("  It does not compare these figures to the OECD average wages used in the")
    print("  savings ranking. Those are PPP-converted and these are market-rate; the")
    print("  two are different units and dividing one by the other is meaningless.")
    print("  For reference only, and NOT as a comparison, the OECD figures are:")
    for c in ("United States", "United Kingdom", "Canada", "Australia"):
        print(f"    {c:<16s} US${WAGE_PPP_USD_2024[c]:,} (PPP)")
    if EXCLUDED:
        print("\n  Excluded for want of a stated basis:")
        for (occ, c), why in EXCLUDED.items():
            print(f"    {c} / {occ}: {why}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "occupation_wages.csv", index=False)
    print(f"\nCSV written: {out / 'occupation_wages.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
