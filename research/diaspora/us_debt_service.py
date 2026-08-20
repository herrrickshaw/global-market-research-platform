#!/usr/bin/env python3
"""
What the American surplus is already promised to.

The savings chain assumes the surplus above the living-cost basket is free to
remit. For a US-based Indian professional it usually is not: a master's degree
was financed, a car was financed, and at some point a house is financed. Debt
service comes out of exactly the same surplus that funds remittances.

This matters most for the United States because the United States ranks first
on landed savings. It is also the one country where the arithmetic is clean:
PPP dollars ARE dollars there, since the US is the numeraire of the PPP
conversion. Every figure below can be subtracted from the US savings line with
no exchange-rate step at all. That is not true of any other destination, which
is why this module is US-only rather than a general debt model.

THREE DEBTS, THREE DIFFERENT ECONOMIC TREATMENTS
------------------------------------------------
Lumping them together is the mistake worth avoiding.

  STUDENT LOAN   A pure claim on the surplus. Nothing comes back.
                 Two financing routes, and they are not equivalent —
                 see the note on the Indian education loan below.

  AUTO LOAN      Also a pure cost. The asset depreciates, so the payment buys
                 transport, not wealth.

  MORTGAGE       NOT a simple deduction, and treating it as one is wrong. The
                 interest, tax and insurance are costs. The principal is
                 savings — redirected into American property instead of into
                 India. So a mortgage does not destroy the savings; it
                 relocates them, into a different currency and a different
                 property market. Early payments are overwhelmingly interest,
                 which is when the relocation is least efficient.

THE FINDING THAT CONNECTS BACK TO THE REMITTANCE WORK
-----------------------------------------------------
An Indian who financed a US master's with an INDIAN education loan services a
rupee debt out of dollar income. Those payments cross the border into India and
are recorded as remittances. They are not family support and they are not
savings — they are loan amortisation. Every module in this directory has been
circling the conclusion that India's remittance series measures more than
migrants sending wages home. This is one concrete channel by which that happens,
and it is large.

Usage:
    python3 research/diaspora/us_debt_service.py
    python3 research/diaspora/us_debt_service.py --inr-per-usd 90
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from real_savings_ranking import build_frame  # noqa: E402

# ===========================================================================
# SOURCED — US household debt.
# ===========================================================================
NYFED_Q1_2026_TRILLIONS = {"mortgage": 13.19, "auto": 1.69, "student": 1.66,
                           "credit_card": 1.25, "total_household": 18.80}
NYFED_SOURCE = "NY Fed Household Debt and Credit Report, Q1 2026 (Consumer Credit Panel / Equifax)"

# educationdata.org, 2026 series.
STUDENT_LOAN = {
    "monthly_masters_only": 640.0,
    "monthly_incl_undergrad": 925.0,
    "balance_masters_holder": 80550.0,
    "balance_graduate_degree_only": 64440.0,
}
STUDENT_SOURCE = "educationdata.org 2026 — average payment and balance for master's-degree borrowers"

# Experian State of the Automotive Finance Market, Q1 2026.
AUTO = {"monthly_new": 770.0, "monthly_used": 531.0, "monthly_lease": 619.0,
        "rate_new_pct": 6.39, "rate_used_pct": 11.43,
        "loan_amount_new": 43925.0, "term_months_new": 69.5}
AUTO_SOURCE = "Experian State of the Automotive Finance Market, Q1 2026"

# US average mortgage, 2026.
MORTGAGE = {"monthly_pi": 2317.0, "monthly_piti": 2883.0,
            "first_payment_principal": 260.0, "first_payment_interest": 1670.0}
MORTGAGE_SOURCE = "US average mortgage payment 2026 — P&I 2,317/mo, full PITI 2,883/mo"

# Indian education loan for a US master's.
INDIA_EDU_LOAN = {
    "cost_lakh_low": 70, "cost_lakh_high": 100,
    "rate_sbi_female_pct": 8.65, "rate_sbi_male_pct": 9.15,
    "rate_credila_pct": 9.95, "rate_prodigy_usd_pct": 9.66,
    "tenor_years_max": 15,
}
INDIA_EDU_SOURCE = ("SBI Global Ed-Vantage 8.65%/9.15%, HDFC Credila from 9%, Credila from 9.95%, "
                    "Prodigy Finance from 9.66% USD; US master's total cost Rs 70-100 lakh; "
                    "tenor up to 15 years")

# PARAM — market exchange rate. NOT sourced here; swept, because the rupee
# EMI has to be paid out of dollars and the rate decides how much that costs.
DEFAULT_INR_PER_USD = 87.0


def emi(principal: float, annual_rate_pct: float, years: int) -> float:
    """Standard amortising monthly payment."""
    r = annual_rate_pct / 100 / 12
    n = years * 12
    g = (1 + r) ** n
    return principal * r * g / (g - 1)


def india_loan_emi_usd(inr_per_usd: float) -> pd.DataFrame:
    rows = []
    for lakh in (INDIA_EDU_LOAN["cost_lakh_low"], 85, INDIA_EDU_LOAN["cost_lakh_high"]):
        for label, rate in (("SBI (female)", INDIA_EDU_LOAN["rate_sbi_female_pct"]),
                            ("SBI (male)", INDIA_EDU_LOAN["rate_sbi_male_pct"]),
                            ("Credila", INDIA_EDU_LOAN["rate_credila_pct"])):
            p = lakh * 100000
            m = emi(p, rate, INDIA_EDU_LOAN["tenor_years_max"])
            rows.append({"loan_rs_lakh": lakh, "lender": label, "rate_pct": rate,
                         "emi_inr_month": round(m),
                         "emi_usd_month": round(m / inr_per_usd),
                         "emi_usd_year": round(m * 12 / inr_per_usd)})
    return pd.DataFrame(rows)


def us_surplus() -> dict:
    d = build_frame(28000).set_index("country")
    r = d.loc["United States"]
    return {"gross": float(r.wage_ppp_usd), "net": float(r.net_wage_ppp_usd),
            "surplus": float(r.savings_ppp_usd), "landed": float(r.savings_landed_india_usd),
            "transfer_pct": float((1 - r.savings_landed_india_usd / r.savings_ppp_usd) * 100)}


def scenarios(inr_per_usd: float) -> pd.DataFrame:
    s = us_surplus()
    india_emi = emi(85 * 100000, INDIA_EDU_LOAN["rate_sbi_male_pct"],
                    INDIA_EDU_LOAN["tenor_years_max"]) * 12 / inr_per_usd
    rows = [
        ("No debt (the ranking's assumption)", 0.0, ""),
        ("US student loan, master's only", STUDENT_LOAN["monthly_masters_only"] * 12, "pure cost"),
        ("US student loan incl. undergrad", STUDENT_LOAN["monthly_incl_undergrad"] * 12, "pure cost"),
        ("Indian education loan, Rs 85L @ 9.15%", india_emi,
         "pure cost — and it is REMITTED, so it inflates the remittance series"),
        ("Used car only", AUTO["monthly_used"] * 12, "pure cost, depreciating asset"),
        ("New car", AUTO["monthly_new"] * 12, "pure cost, depreciating asset"),
        ("US student loan + used car", (STUDENT_LOAN["monthly_masters_only"] + AUTO["monthly_used"]) * 12,
         "the common early-career case"),
        ("Indian education loan + new car", india_emi + AUTO["monthly_new"] * 12,
         "the common Indian-financed case"),
    ]
    out = []
    for name, cost, note in rows:
        rem = s["surplus"] - cost
        out.append({
            "scenario": name,
            "debt_service_usd_yr": round(cost),
            "share_of_surplus_pct": round(cost / s["surplus"] * 100, 1),
            "remittable_usd_yr": round(rem),
            "lands_in_india_usd_yr": round(rem * (1 - s["transfer_pct"] / 100)),
            "note": note,
        })
    return pd.DataFrame(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inr-per-usd", type=float, default=DEFAULT_INR_PER_USD)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()
    s = us_surplus()

    print("=== THE STOCK: what Americans owe ===")
    print(f"  {NYFED_SOURCE}")
    for k, v in NYFED_Q1_2026_TRILLIONS.items():
        if k != "total_household":
            print(f"    {k:<14s} US${v:>6.2f}tn")
    print(f"    {'TOTAL':<14s} US${NYFED_Q1_2026_TRILLIONS['total_household']:>6.2f}tn")
    print("\n  Aggregate stocks say what is normal, not what any one person pays. The")
    print("  monthly figures below are what actually competes with the remittance.")

    print(f"\n=== THE US SURPLUS THE RANKING ASSUMED WAS FREE ===")
    print(f"  Gross US${s['gross']:,.0f}  ->  net US${s['net']:,.0f}  ->  after the "
          f"US$28,000 basket, US${s['surplus']:,.0f} of surplus.")
    print(f"  That is US${s['surplus'] / 12:,.0f} a month, and the ranking treated all of it as")
    print("  remittable. Now put the payments against it.")

    print("\n=== SCENARIOS ===")
    sc = scenarios(args.inr_per_usd)
    print(sc.drop(columns=["note"]).to_string(index=False))
    print("\n  Notes:")
    for _, r in sc.iterrows():
        if r["note"]:
            print(f"    {r['scenario']}: {r['note']}")

    print(f"\n=== THE INDIAN EDUCATION LOAN (at Rs {args.inr_per_usd:.0f}/US$) ===")
    print(f"  {INDIA_EDU_SOURCE}")
    print()
    print(india_loan_emi_usd(args.inr_per_usd).to_string(index=False))
    print("\n  Sensitivity to the rupee, Rs 85 lakh at 9.15% over 15 years:")
    rows = []
    for fx in (80, 85, 87, 90, 95):
        e = emi(85 * 100000, 9.15, 15) * 12 / fx
        rows.append({"inr_per_usd": fx, "emi_usd_yr": round(e),
                     "share_of_us_surplus_pct": round(e / s["surplus"] * 100, 1)})
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n  A weaker rupee makes the loan CHEAPER to service out of dollars. It is the")
    print("  one line in this whole analysis where rupee depreciation helps the migrant.")

    print("\n=== THE MORTGAGE, WHICH IS NOT A DEDUCTION ===")
    print(f"  {MORTGAGE_SOURCE}")
    pi, piti = MORTGAGE["monthly_pi"], MORTGAGE["monthly_piti"]
    prin, intr = MORTGAGE["first_payment_principal"], MORTGAGE["first_payment_interest"]
    print(f"  Treating US${piti:,.0f}/month as lost savings would be wrong twice over.")
    print(f"    1. It replaces rent, which the US$28,000 basket already contains — so only")
    print(f"       the excess over rent is new spending, and the basket's rent share is not")
    print(f"       separately sourced here. This module therefore does NOT net a mortgage")
    print(f"       against the surplus; doing so would double-count housing.")
    print(f"    2. The principal is not consumption. On an early payment US${prin:,.0f} of "
          f"US${prin + intr:,.0f} builds")
    print(f"       equity — that is saving, redirected into American property rather than")
    print(f"       sent to India. Only the US${intr:,.0f} of interest, plus tax and insurance, is cost.")
    print(f"\n  So a mortgage does not destroy the savings. It relocates them — out of rupees")
    print(f"  and into a dollar asset. Which is a real decision with a real answer, because")
    print(f"  Indian property is inflating at the 8.30% WPI rate that no advanced-economy")
    print(f"  wage clears. Against that hurdle, holding property in the US instead of India")
    print(f"  is not obviously the worse side of the trade.")

    print("\n=== WHAT THIS DOES TO THE HEADLINE ===")
    base = sc.iloc[0]["lands_in_india_usd_yr"]
    common = sc[sc.scenario == "US student loan + used car"].iloc[0]
    indian = sc[sc.scenario == "Indian education loan + new car"].iloc[0]
    print(f"  Debt-free, the US lands US${base:,.0f} a year and ranks first of seven.")
    print(f"  With a master's loan and a used car it lands US${common['lands_in_india_usd_yr']:,.0f} "
          f"— {common['share_of_surplus_pct']:.0f}% of the surplus gone.")
    print(f"  Indian-financed, with a new car, US${indian['lands_in_india_usd_yr']:,.0f} "
          f"— {indian['share_of_surplus_pct']:.0f}% gone.")
    d = build_frame(28000).set_index("country")
    for c in ("Netherlands", "Australia", "Canada", "United Kingdom", "Germany"):
        v = d.loc[c, "savings_landed_india_usd"]
        if v > indian["lands_in_india_usd_yr"]:
            print(f"    -> below {c} (US${v:,.0f}), which carries no such assumption either way.")
    print("\n  The ranking is not wrong; it answers a debt-free question. But the American")
    print("  first place is the most fragile of the seven, because the American route into")
    print("  that salary is the one most often bought on credit.")

    print("\n=== WHAT THIS COMPARISON IS NOT ===")
    print("  Those arrows compare a debt-laden American against six debt-FREE peers, and")
    print("  that is not a fair fight. Migrants to Germany, Canada and Australia also")
    print("  borrow. Read the arrows as 'this is how far the US position can move', not")
    print("  as 'Germany now beats the US'.")
    print("\n  What is genuinely US-specific, and why the module is US-only:")
    print("    - A US master's costs Rs 70-100 lakh. Public universities in Germany charge")
    print("      no tuition, so the same qualification carries no comparable debt.")
    print("    - US car dependence is structural in most metros, so the auto payment is")
    print("      closer to a fixed cost than a choice.")
    print("    - The Indian-education-loan route exists at scale precisely because US")
    print("      study is what it is most often taken out to fund.")
    print("  Doing this properly for the other six needs their own borrowing data, which")
    print("  was not gathered. Until it is, the honest statement is the conditional one:")
    print("  a debt-financed US route lands materially less than the headline, and the")
    print("  gap to the rest is smaller than the ranking implies.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sc.to_csv(out / "us_debt_service.csv", index=False)
    print(f"\nCSV written: {out / 'us_debt_service.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
