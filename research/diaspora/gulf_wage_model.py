#!/usr/bin/env python3
"""
What an Indian migrant in the Gulf actually earns — an ILO-anchored segment model.

WHY THIS EXISTS
---------------
The real-savings ranking carried Gulf wages at grade C and excluded them from
the like-for-like table. The figures available were recruitment-survey
*national* averages — UAE US$73,500, Qatar US$81,600, Saudi US$64,800 — which
describe a workforce that includes Emirati nationals, Western expatriate
executives and Gulf managers. Indian migrants are not that population.

This replaces the national average with a two-segment model of the Indian
migrant wage specifically, anchored at the bottom on statutory wage floors —
Qatar's being the only universal, non-discriminatory minimum wage in the GCC,
developed with the ILO — and at the top on published skilled-worker reference
levels.

The answer moves by roughly a factor of five, which is why it mattered.

THE SYMMETRY THAT MAKES THIS WORTH DOING PROPERLY
-------------------------------------------------
Indian migrants in the Gulf earn far BELOW their host country's national
average. Indian migrants in the US and UK earn ABOVE theirs — the population is
concentrated in technology, medicine and finance. So using national averages
everywhere does not merely add noise, it biases the two blocs in opposite
directions, flattering the Gulf and penalising the advanced economies. Fixing
only the Gulf half, as this module does, therefore makes the comparison *more*
conservative toward the Gulf, not less. The advanced-economy half is still
uncorrected because no migrant-specific wage series for them was reachable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ===========================================================================
# SOURCED — statutory wage floors, GCC. Note how few of these bind at all.
# ===========================================================================
QAR_PER_USD, KWD_PER_USD, AED_PER_USD, SAR_PER_USD = 3.64, 0.307, 3.6725, 3.75

WAGE_FLOORS = {
    # country: (monthly basic USD, monthly total package USD, covers migrants?, note)
    "Qatar": (1000 / QAR_PER_USD, 1800 / QAR_PER_USD, True,
              "QAR 1,000 basic + 500 accommodation + 300 food. Universal and "
              "non-discriminatory, all nationalities and sectors including domestic "
              "workers. Developed with the ILO, in force 20 Mar 2021. The only one "
              "of its kind in the region."),
    "Kuwait": (75 / KWD_PER_USD, 75 / KWD_PER_USD, True,
               "KWD 75/month private sector, applied to nationals and expatriates alike."),
    "UAE": (None, None, False,
            "No statutory minimum for expatriates. AED 6,000 applies to Emiratis only. "
            "Employers set expatriate pay without a binding floor."),
    "Saudi Arabia": (None, None, False,
                     "No statutory minimum for foreign workers. SAR 4,000 is a Saudization "
                     "(Nitaqat) threshold for nationals only."),
    "Oman": (None, None, False, "Nationals-only minimum; no binding expatriate floor retrieved."),
    "Bahrain": (None, None, False, "Nationals-only minimum; no binding expatriate floor retrieved."),
}

# UAE published reference levels used for Emiratisation classification. Not
# binding law, but they are the clearest published statement of what each skill
# tier is understood to pay in the Gulf's largest Indian-migrant market.
UAE_SKILL_REFERENCE_USD_MONTH = {
    "skilled labourer": 5000 / AED_PER_USD,     # ~USD 1,361
    "skilled technician": 7000 / AED_PER_USD,   # ~USD 1,906
    "university graduate": 12000 / AED_PER_USD,  # ~USD 3,267
}

# KNOMAD / ILO returnee survey (Martin), 2,000+ workers returning from GCC jobs,
# interviewed 2015. Median monthly earnings abroad, by origin nationality, in
# Qatar. The Indian median was not retrievable; these bracket it, since Indian
# pay in the Gulf sits between Filipino and Ethiopian on every account of the
# nationality wage hierarchy.
#
# VINTAGE MATTERS HERE: 2015 is six years before Qatar's minimum wage came into
# force, so these are pre-floor wages. The Ethiopian median of US$265 sits BELOW
# what became the statutory basic minimum of US$275 — which is not a
# contradiction but a corroboration. The ILO recorded that the new floor lifted
# more than 400,000 workers, 20% of Qatar's private sector, precisely because
# wages like these were common before it.
KNOMAD_QATAR_MEDIAN_USD_MONTH = {"Philippines": 435.0, "Ethiopia": 265.0}
KNOMAD_SURVEY_YEAR = 2015
QATAR_MIN_WAGE_IN_FORCE = "2021-03-20"

# Skill composition of the Indian population in the GCC.
#   STOCK is what we need — who is there now.
#   FLOW is who is arriving, from MEA emigration-clearance occupation tags, and
#   it is shifting hard toward skilled. The two must not be confused: the stock
#   still reflects decades of blue-collar arrivals.
COMPOSITION_STOCK = {"blue_collar": 0.70, "professional": 0.30}
COMPOSITION_FLOW_2014 = {"skilled": 0.38, "semi_skilled": 0.24, "unskilled": 0.38}
COMPOSITION_FLOW_2025 = {"skilled": 0.61, "semi_skilled": 0.26, "unskilled": 0.13}

# Recruitment-survey national averages — retained only to show the size of the
# error they introduce. Not used in the model.
NATIONAL_AVERAGE_USD_YEAR = {"Qatar": 81600, "UAE": 73500, "Saudi Arabia": 64800}

# ===========================================================================
# PARAMS — judgement, bounded by the sourced anchors above.
# ===========================================================================
# Blue-collar band: floor is Qatar's basic cash minimum; ceiling is Qatar's full
# package including accommodation and food in kind. The KNOMAD medians sit
# inside this band, which is the check that it is the right band.
BLUE_COLLAR_USD_YEAR = (
    12 * WAGE_FLOORS["Qatar"][0],   # ~3,297 — basic cash only
    12 * 400.0,                     # ~4,800 — between the two KNOMAD medians
    12 * WAGE_FLOORS["Qatar"][1],   # ~5,934 — full package
)
# Professional band: UAE skilled-technician reference at the bottom, graduate
# reference in the middle, and a senior level at the top.
PROFESSIONAL_USD_YEAR = (
    12 * UAE_SKILL_REFERENCE_USD_MONTH["skilled technician"],   # ~22,872
    12 * UAE_SKILL_REFERENCE_USD_MONTH["university graduate"],  # ~39,204
    65000.0,
)

# Documented Gulf remitting behaviour, share of net income. Same band the
# remittance estimator uses, so the two modules are testing each other on
# consistent terms.
GULF_REMIT_RATE_BAND = (0.25, 0.55)


def blended_wage() -> pd.DataFrame:
    """Stock-weighted Indian migrant wage in the Gulf, low/central/high."""
    rows = []
    for i, tag in enumerate(("low", "central", "high")):
        bc, pro = BLUE_COLLAR_USD_YEAR[i], PROFESSIONAL_USD_YEAR[i]
        blended = COMPOSITION_STOCK["blue_collar"] * bc + COMPOSITION_STOCK["professional"] * pro
        rows.append({"scenario": tag, "blue_collar_usd_yr": round(bc),
                     "professional_usd_yr": round(pro),
                     "blended_indian_migrant_usd_yr": round(blended)})
    return pd.DataFrame(rows)


def consistency_check(per_remitter_usd: float) -> pd.DataFrame:
    """Does the remittance estimate fit inside the wage the ILO anchors imply?

    The Gulf pays no income tax, so net income is gross income and the implied
    remittance rate is simply remittance over wage.
    """
    out = []
    for _, r in blended_wage().iterrows():
        w = r.blended_indian_migrant_usd_yr
        rate = per_remitter_usd / w * 100
        lo, hi = (b * 100 for b in GULF_REMIT_RATE_BAND)
        out.append({
            "wage scenario": r.scenario,
            "blended wage USD/yr": w,
            "remittance USD/yr": round(per_remitter_usd),
            "implied remit rate %": round(rate, 1),
            "documented band %": f"{lo:.0f}-{hi:.0f}",
            "verdict": ("fits" if lo <= rate <= hi else
                        ("ABOVE BAND — wage base cannot support this remittance"
                         if rate > hi else "below band")),
        })
    return pd.DataFrame(out)


def segment_decomposition(per_remitter_usd: float) -> pd.DataFrame:
    """If the bloc average is real, what must each segment be remitting?

    Solves the mixture: blue-collar remit at the top of the documented band,
    and the professional segment carries whatever remains.
    """
    out = []
    for _, r in blended_wage().iterrows():
        bc_remit = r.blue_collar_usd_yr * GULF_REMIT_RATE_BAND[1]
        share_bc, share_pro = COMPOSITION_STOCK["blue_collar"], COMPOSITION_STOCK["professional"]
        pro_remit = (per_remitter_usd - share_bc * bc_remit) / share_pro
        pro_rate = pro_remit / r.professional_usd_yr * 100
        out.append({
            "wage scenario": r.scenario,
            "blue-collar remits USD/yr (at band max)": round(bc_remit),
            "professional must remit USD/yr": round(pro_remit),
            "as % of professional wage": round(pro_rate, 1),
            "credible?": "yes" if pro_rate <= 55 else "NO — exceeds any documented rate",
        })
    return pd.DataFrame(out)


def main() -> int:
    print("=== GCC STATUTORY WAGE FLOORS — how few of them bind ===")
    rows = []
    for c, (basic, total, covers, note) in WAGE_FLOORS.items():
        rows.append({"country": c,
                     "binds on migrants": "yes" if covers else "NO",
                     "basic USD/mo": round(basic) if basic else None,
                     "package USD/mo": round(total) if total else None})
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n  Only Qatar and Kuwait have a floor that binds on migrant workers at all.")
    print("  Qatar's is the region's only universal, non-discriminatory minimum wage,")
    print("  developed with the ILO and in force since March 2021. In the UAE and Saudi")
    print("  Arabia — between them the destination of the majority of Indian migrants —")
    print("  expatriate pay has no statutory floor whatsoever.")

    print("\n=== CROSS-CHECK ON THE BLUE-COLLAR BAND ===")
    print("  KNOMAD/ILO returnee survey, median monthly earnings in Qatar:")
    for k, v in KNOMAD_QATAR_MEDIAN_USD_MONTH.items():
        print(f"    {k:<14s} US${v:>6.0f}/mo")
    lo_m, hi_m = BLUE_COLLAR_USD_YEAR[0] / 12, BLUE_COLLAR_USD_YEAR[2] / 12
    print(f"  Modelled blue-collar band: US${lo_m:.0f}-{hi_m:.0f}/mo.")
    for k, v in KNOMAD_QATAR_MEDIAN_USD_MONTH.items():
        where = ("inside the band" if lo_m <= v <= hi_m else
                 f"BELOW the post-2021 statutory basic floor of US${lo_m:.0f}")
        print(f"    {k:<14s} {where}")
    print(f"\n  The survey is {KNOMAD_SURVEY_YEAR}; Qatar's floor took effect {QATAR_MIN_WAGE_IN_FORCE}. So the")
    print("  Ethiopian median sitting under today's legal minimum is corroboration, not")
    print("  contradiction — the ILO recorded the new floor lifting over 400,000 workers,")
    print("  20% of Qatar's private sector, precisely because such wages were common.")
    print("  The Indian median was not retrievable, but Indian pay in the Gulf sits")
    print("  between Filipino and Ethiopian on every account of the nationality wage")
    print("  hierarchy, so it is bracketed either way.")

    print("\n=== BLENDED INDIAN MIGRANT WAGE (stock-weighted, 70% blue-collar) ===")
    bw = blended_wage()
    print(bw.to_string(index=False))
    central = bw.loc[bw.scenario == "central", "blended_indian_migrant_usd_yr"].iat[0]
    print(f"\n  Composition: stock is {COMPOSITION_STOCK['blue_collar']:.0%} blue-collar. The arrival FLOW has shifted")
    print(f"  hard the other way — MEA emigration-clearance tags went from "
          f"{COMPOSITION_FLOW_2014['skilled']:.0%} skilled in 2014")
    print(f"  to {COMPOSITION_FLOW_2025['skilled']:.0%} in 2025 — but the stock still reflects decades of blue-collar")
    print("  arrivals. Using the flow mix here would be the classic error.")
    print("\n  Against the recruitment-survey national averages previously carried:")
    for c, v in NATIONAL_AVERAGE_USD_YEAR.items():
        print(f"    {c:<14s} national avg US${v:,}  vs  Indian-migrant blended US${central:,}"
              f"   overstated {v / central:.1f}x")

    print("\n=== CONSISTENCY TEST AGAINST THE REMITTANCE ESTIMATE ===")
    per_remitter = 8659.0   # central Gulf per-remitter figure from the estimator
    print(f"  The remittance estimator puts Gulf flow at US${per_remitter:,.0f} per remitting")
    print("  migrant per year. The Gulf levies no income tax, so that must come out of")
    print("  the wage above.\n")
    print(consistency_check(per_remitter).to_string(index=False))

    print("\n  If the bloc average is real, the segments must decompose like this:")
    print(segment_decomposition(per_remitter).to_string(index=False))

    cc, sd = consistency_check(per_remitter), segment_decomposition(per_remitter)
    fits = cc.loc[cc.verdict == "fits", "wage scenario"].tolist()
    ok_seg = sd.loc[sd["credible?"] == "yes", "wage scenario"].tolist()
    print("\n=== WHAT THIS MEANS ===")
    print(f"  Of three wage scenarios the remittance figure fits "
          f"{len(fits)} ({', '.join(fits) or 'none'}), and the")
    print(f"  segment decomposition is credible in {len(ok_seg)} ({', '.join(ok_seg) or 'none'}).")
    print("  Both survive only at the high scenario — which requires assuming the top of")
    print("  every band at once: blue-collar workers on Qatar's full package including")
    print("  accommodation and food, and professionals at US$65,000. That is the most")
    print("  generous reading of the wage evidence available, and it is the only one under")
    print("  which US$8,659 per remitter works as wage remittance.")
    print("\n  So the Gulf's 'grade A, two independent methods agree' finding needs")
    print("  qualifying. The two methods agree on the FLOW, and the ILO data does not")
    print("  overturn that. What it overturns is the interpretation: Gulf remittances")
    print("  cannot be predominantly wage remittances sent by labour migrants out of")
    print("  salary. Something else is carrying much of the value — business and trade")
    print("  income repatriated by the Gulf's large Indian merchant community, NRI")
    print("  deposit flows, and gold and trade settlement routed through Dubai.")
    print("\n  Which is the same conclusion the advanced-economy analysis reached, from")
    print("  the opposite direction: in both blocs the remittance series is measuring")
    print("  considerably more than migrant workers sending wages home.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
