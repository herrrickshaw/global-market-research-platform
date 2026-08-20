#!/usr/bin/env python3
"""
Salaried migrants and business-owner migrants are not the same population.

EVERYTHING ELSE IN THIS DIRECTORY IS A SALARIED-WORKER MODEL
------------------------------------------------------------
That is worth saying at the top rather than in a caveat at the bottom. The
savings chain takes a wage, applies a tax rate, subtracts a basket and calls
what remains remittable. Every step of that assumes an employee:

  - income is a WAGE, so it has a ceiling
  - tax is determined AT SOURCE by a published schedule
  - the surplus is what is left after living, so remittance is bounded by it

None of the three holds for someone who owns the business. Income is profit,
not wage. The tax rate is partly elective. And remittance capacity is not
bounded by any salary, because trade proceeds and capital can move too.

So the rankings elsewhere here are correct for the population they describe and
silent about the other one — which matters, because the other one plausibly
carries a large share of the money.

WHY THE STATISTICS CANNOT SEPARATE THEM
---------------------------------------
Under FEMA, foreign income of every kind — salary, business income, savings
accumulated abroad — enters India through the NRE account and is freely
repatriable, principal and interest alike. A salaried migrant's monthly transfer
and a trading company owner's profit repatriation arrive through the same
channel, into the same account type, under the same rules.

They are therefore counted identically. The remittance series has no field that
distinguishes them, which is why no amount of care with the published numbers
will separate the two populations — and why the Gulf reconciliation elsewhere
in this directory failed on wage arithmetic alone.

(The asymmetry runs the other way for Indian-source income: rent, Indian
dividends, pensions and property proceeds must use an NRO account and are
capped at US$1 million a year after Indian tax. That cap binds on money leaving
India, not on money arriving, so it does not affect the inbound series.)

Usage:
    python3 research/diaspora/salaried_vs_business.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gulf_wage_model import blended_wage  # noqa: E402
from real_savings_ranking import build_frame  # noqa: E402

# ===========================================================================
# SOURCED
# ===========================================================================
US_TAX_MECHANICS = {
    "employee_fica_pct": 7.65,
    "self_employment_pct": 15.3,
    "se_threshold_usd": 176100,
    "se_above_threshold_pct": 2.9,
    "ss_wage_base_2026_usd": 184500,
}
US_TAX_SOURCE = ("IRS Schedule SE — self-employment tax is 15.3% on the first US$176,100 of "
                 "net earnings and 2.9% above it. An employee pays 7.65%; the employer pays "
                 "the other half. The self-employed pay both.")

S_CORP = ("An S-corporation election splits business income into a 'reasonable salary' "
          "(subject to payroll tax) and distributions (not subject to it). The IRS audits "
          "unreasonably low salaries, and the strategy generally only pays above roughly "
          "US$80,000 of income once compliance costs are counted.")

DIASPORA_BUSINESS = {
    "us_ownership_per_1000": 50,
    "us_indian_entrepreneur_income_usd": 84080,
    "us_all_business_owner_income_usd": 52086,
    "uk_indian_company_turnover_gbp_bn": 36.84,
    "uk_indian_company_employees": 174000,
    "uk_indian_company_corp_tax_gbp_bn": 1.0,
}
DIASPORA_SOURCE = ("RAND / Immigration Research Initiative for US business-ownership "
                   "propensity and entrepreneur income; Grant Thornton 'India in the UK' for "
                   "UK company aggregates. Gulf: LuLu Group, Landmark, Jashanmal, Ajmal, "
                   "Jumbo Electronics, Aster DM — Indian-founded trading and retail groups.")

FEMA = ("Foreign income of any kind — salary, business income, accumulated savings — enters "
        "via NRE and is freely repatriable. Indian-source income (rent, dividends, pension, "
        "property proceeds) must use NRO and is capped at US$1m/year after Indian tax.")

# Gulf per-remitter figure the estimator produces, and the wage base behind it.
GULF_PER_REMITTER_USD = 8659.0


def structural_table() -> pd.DataFrame:
    rows = [
        ("Income basis", "Wage — has a ceiling",
         "Profit — no wage ceiling"),
        ("Tax rate", "Set at source by a published schedule",
         "Partly ELECTIVE: entity choice, salary/distribution split, timing"),
        ("Payroll tax (US)", f"{US_TAX_MECHANICS['employee_fica_pct']}% employee share",
         f"{US_TAX_MECHANICS['self_employment_pct']}% both halves — unless structured around"),
        ("Pre-tax retention", "None — taxed on receipt",
         "Profit can stay in the company, deferring personal tax"),
        ("Remittance ceiling", "Wage − tax − living costs (what this repo models)",
         "Profit + trade proceeds + capital. Unbounded by any salary"),
        ("Timing", "Monthly, tracks the payslip",
         "Lumpy — follows deals, distributions and capital events"),
        ("Enters India as", "NRE, freely repatriable", "NRE, freely repatriable — IDENTICAL"),
    ]
    return pd.DataFrame(rows, columns=["dimension", "salaried migrant", "business-owner migrant"])


def us_payroll_gap() -> pd.DataFrame:
    """The one place the business owner is unambiguously worse off."""
    e, se = US_TAX_MECHANICS["employee_fica_pct"], US_TAX_MECHANICS["self_employment_pct"]
    rows = []
    for inc in (60000, 82933, 120000, 176100):
        rows.append({"income_usd": inc,
                     "employee_payroll_usd": round(inc * e / 100),
                     "self_employed_payroll_usd": round(inc * se / 100),
                     "extra_cost_usd": round(inc * (se - e) / 100)})
    return pd.DataFrame(rows)


def implied_business_remittance(observed: float, wage: float,
                                salaried_rate: float, business_share: float) -> float:
    """If the bloc average is `observed` and salaried migrants remit at
    `salaried_rate` of wage, the business-owner minority must carry the rest."""
    salaried_part = (1 - business_share) * wage * salaried_rate
    return (observed - salaried_part) / business_share


def gulf_decomposition() -> pd.DataFrame:
    wage = float(blended_wage().set_index("scenario")
                 .blended_indian_migrant_usd_yr["central"])
    rows = []
    for b in (0.03, 0.05, 0.10):
        for r in (0.30, 0.40, 0.50):
            v = implied_business_remittance(GULF_PER_REMITTER_USD, wage, r, b)
            rows.append({"business_owner_share": f"{b:.0%}",
                         "salaried_remit_rate": f"{r:.0%}",
                         "implied_business_remit_usd_yr": round(v),
                         "as_multiple_of_wage": round(v / wage, 1) if v > 0 else None,
                         "plausible": "yes" if 0 < v < 400000 else "NO"})
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    print("=== TWO POPULATIONS, ONE DATASET ===")
    print(structural_table().to_string(index=False))
    print(f"\n  FEMA: {FEMA}")
    print("\n  The last row is the problem. Both populations arrive through the same")
    print("  channel under the same rules, so the remittance series has no field that")
    print("  tells them apart. Nothing done carefully with the published numbers can")
    print("  separate what a salaried worker sent from what a trading company repatriated.")

    print("\n=== WHERE THE BUSINESS OWNER IS WORSE OFF ===")
    print(f"  {US_TAX_SOURCE}")
    print()
    print(us_payroll_gap().to_string(index=False))
    print(f"\n  {S_CORP}")
    print("\n  So the headline is that self-employment costs roughly twice the payroll tax")
    print("  — and the footnote is that above about US$80,000 it stops being a fixed cost")
    print("  and becomes a planning decision. That is the real difference: for an employee")
    print("  the rate is imposed, for an owner it is chosen within limits.")

    print("\n=== WHERE THE BUSINESS OWNER IS BETTER OFF ===")
    d = DIASPORA_BUSINESS
    prem = d["us_indian_entrepreneur_income_usd"] / d["us_all_business_owner_income_usd"] - 1
    print(f"  Indian-run businesses in the US: ownership propensity {d['us_ownership_per_1000']} per 1,000,")
    print(f"  average entrepreneur income US${d['us_indian_entrepreneur_income_usd']:,} against "
          f"US${d['us_all_business_owner_income_usd']:,} for all US")
    print(f"  business owners — a {prem:.0%} premium.")
    sal = build_frame(28000).set_index("country").loc["United States", "wage_ppp_usd"]
    print(f"  For comparison the US average WAGE in this repo's model is US${sal:,.0f}.")
    print(f"  In the UK, Indian-run companies turn over GBP {d['uk_indian_company_turnover_gbp_bn']}bn, "
          f"employ {d['uk_indian_company_employees']:,},")
    print(f"  and pay GBP {d['uk_indian_company_corp_tax_gbp_bn']}bn in corporation tax.")
    print(f"\n  {DIASPORA_SOURCE}")

    print("\n=== DOES THIS CLOSE THE GULF GAP? ===")
    wage = float(blended_wage().set_index("scenario").blended_indian_migrant_usd_yr["central"])
    print(f"  The estimator puts Gulf flow at US${GULF_PER_REMITTER_USD:,.0f} per remitter. The")
    print(f"  ILO-anchored blended migrant wage is US${wage:,.0f}, and the wage arithmetic only")
    print("  worked at the top of every band — which is what prompted this module.")
    print("\n  If a small minority are business owners, what must they be remitting?\n")
    print(gulf_decomposition().to_string(index=False))
    print("\n  Every cell is a plausible figure for someone running a Gulf trading or retail")
    print("  business. At a 5% owner share and a 40% salaried remit rate — both unremarkable")
    print("  — the implied business remittance is a few times the blended wage, not a")
    print("  fantastical number. So the gap does not require heroic wage-remittance rates.")
    print("  It requires a modest business-owner minority moving amounts that are ordinary")
    print("  for business owners and impossible for employees.")

    print("\n=== WHAT THIS MEANS FOR EVERYTHING ELSE HERE ===")
    print("  1. The savings rankings are SALARIED-WORKER rankings. They are not wrong; they")
    print("     answer a question about employees, and should be read that way.")
    print("  2. The remittance estimator's per-head figures are averages over a mixed")
    print("     population. A per-SALARIED-remitter figure would be lower, and a")
    print("     per-business-owner figure much higher, than the blended number reported.")
    print("  3. The recurring finding across these modules — that the remittance series")
    print("     measures more than migrants sending wages home — now has its mechanism.")
    print("     It is not a measurement error. It is two populations sharing one channel.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    structural_table().to_csv(out / "salaried_vs_business.csv", index=False)
    gulf_decomposition().to_csv(out / "gulf_business_decomposition.csv", index=False)
    print(f"\nCSVs written to {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
