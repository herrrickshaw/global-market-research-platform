#!/usr/bin/env python3
"""
Every judgement parameter in this directory, and what the literature says about it.

The modules here separate sourced figures from judgement parameters and sweep
the latter. That is better than hiding them, but a swept parameter is still a
guess with error bars. This checks the guesses against published research and
records the verdict — including where the verdict is "still unsupported".

WHAT A VERDICT MEANS
--------------------
  SUPPORTED    Published work bears directly on the parameter and agrees with
               the value or band used.
  DIRECTIONAL  The literature supports the SIGN or the mechanism but not the
               magnitude. The parameter's direction is safe; its number is not.
  STRUCTURAL   Not a statistical claim at all — it follows from law or
               institutional design, so no empirical validation applies.
  UNSUPPORTED  Nothing found. Stated so it can be found later, not buried.

Usage:
    python3 research/diaspora/literature_validation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from india_remittance_estimator import BASE_PARAMS, PLAUSIBLE_REMIT_RATE  # noqa: E402
from real_savings_ranking import DEFAULT_BASKET_USD  # noqa: E402
from rent_vs_wages import DEFAULT_RENT_SHARE  # noqa: E402
from roi_foreign_life import HOST_WAGE_GROWTH_BAND  # noqa: E402

# ===========================================================================
# LITERATURE
# ===========================================================================
LIT = {
    "iom_15pct": ("IOM, COVID-19 Analytical Snapshot #16 / World Migration Report; "
                  "corroborated by UN data via Our World in Data — migrants send home "
                  "an average of 15% of their earnings."),
    "lucas_stark": ("Lucas & Stark (1985), the remittance decay hypothesis — migrants "
                    "remit less the longer they live abroad, as attachment to the "
                    "household of origin weakens. Repeatedly tested since; confirmed for "
                    "the Turkish corridor and consistent with repeat-migrant evidence."),
    "family_reunion": ("Remittance-behaviour literature — migrants remit materially less "
                       "once joined by immediate family in the country of residence."),
    "gender": ("Migrant women remit a larger share of earnings than men (multiple "
               "studies; reported via World Bank / IOM syntheses)."),
    "eurostat_housing": ("Eurostat, housing cost overburden — the overburden threshold is "
                         "40% of disposable income, and 19.2% of EU tenants at market "
                         "price exceeded it (Dec-2024). Netherlands is the EU's highest "
                         "at 43.9%; Germany 13.8%."),
    "own_panel": ("This repo's own rent_vs_wages.PANEL — measured nominal wage growth "
                  "for each destination."),
}


def rows() -> list[dict]:
    ae_lo, ae_hi = (v * 100 for v in PLAUSIBLE_REMIT_RATE["Advanced"])
    gcc_lo, gcc_hi = (v * 100 for v in PLAUSIBLE_REMIT_RATE["GCC"])
    ae = BASE_PARAMS["Advanced"]
    gcc = BASE_PARAMS["GCC"]

    return [
        {
            "parameter": "Advanced-economy remittance rate band",
            "value": f"{ae_lo:.0f}-{ae_hi:.0f}% of net income",
            "verdict": "SUPPORTED",
            "evidence": LIT["iom_15pct"],
            "reading": ("The global mean is 15%, and that mean is dominated by low-income "
                        "corridors which remit far above it. An advanced-economy band "
                        "topping out AT the global mean is therefore the right side of it."),
        },
        {
            "parameter": "Gulf remittance rate band",
            "value": f"{gcc_lo:.0f}-{gcc_hi:.0f}% of net income",
            "verdict": "DIRECTIONAL",
            "evidence": LIT["iom_15pct"],
            "reading": ("Sits well above the 15% global mean, which is where Gulf labour "
                        "migration should sit — employer-provided housing and food, "
                        "suppressed consumption, remitting as the purpose of the move. "
                        "The direction is safe. The 25-55% width is not pinned by any "
                        "study found here."),
        },
        {
            "parameter": "Remit propensity falls with tenure abroad",
            "value": "implicit in the low AE propensity vs high Gulf propensity",
            "verdict": "SUPPORTED",
            "evidence": LIT["lucas_stark"],
            "reading": ("This is the canonical result in the field and it is exactly the "
                        "mechanism the remitter-base model assumes. Gulf migration is "
                        "short-tenure and circular; advanced-economy migration is not."),
        },
        {
            "parameter": "AE remit propensity lower than Gulf",
            "value": f"AE {ae['remit_propensity'][1]:.2f} vs Gulf {gcc['remit_propensity'][1]:.2f} (central)",
            "verdict": "SUPPORTED",
            "evidence": LIT["family_reunion"],
            "reading": ("Previously asserted here on structural grounds — Gulf family "
                        "sponsorship carries salary floors, so most migrants are "
                        "single-status, while advanced-economy migrants bring families. "
                        "The literature confirms family reunification depresses remitting, "
                        "so the mechanism is no longer just an assertion."),
        },
        {
            "parameter": "PIO (naturalised) remit propensity, advanced economies",
            "value": f"{ae['pio_propensity'][0]:.2f}-{ae['pio_propensity'][2]:.2f}",
            "verdict": "DIRECTIONAL",
            "evidence": LIT["lucas_stark"],
            "reading": ("Naturalisation implies long tenure, and decay says long tenure "
                        "means less remitting — so a low propensity is right in sign. The "
                        "0.08-0.25 range is not pinned by any measurement found."),
        },
        {
            "parameter": "Gulf PIO propensity = 0",
            "value": "0.00 fixed",
            "verdict": "STRUCTURAL",
            "evidence": "Gulf states have no general naturalisation path.",
            "reading": ("Not an empirical claim. There is no meaningful naturalised Indian "
                        "population in the Gulf to remit, so the parameter is a fact about "
                        "immigration law rather than about behaviour."),
        },
        {
            "parameter": "Rent share of the living-cost basket",
            "value": f"{DEFAULT_RENT_SHARE:.0%} of US${DEFAULT_BASKET_USD:,}",
            "verdict": "DIRECTIONAL",
            "evidence": LIT["eurostat_housing"],
            "reading": ("35% sits just under Eurostat's 40% overburden threshold, and "
                        "roughly a fifth of EU market-rate tenants are above that line. So "
                        "it is a high-but-defensible share for a new arrival renting at "
                        "market in a major city — and it errs toward LESS surplus, not "
                        "more. Worth noting against the ranking: the Netherlands finishes "
                        "first here and has the EU's highest housing overburden rate."),
        },
        {
            "parameter": "Advanced-economy nominal wage growth band",
            "value": f"{HOST_WAGE_GROWTH_BAND[0]:.1f}-{HOST_WAGE_GROWTH_BAND[1]:.1f}%",
            "verdict": "SUPPORTED",
            "evidence": LIT["own_panel"],
            "reading": ("Now derived from the measured panel rather than asserted. An "
                        "earlier version hardcoded 2.0-4.0%, which excluded the "
                        "Netherlands at 4.50% — the band contradicted data in the next "
                        "module along. Found by this exercise and fixed; a test pins them "
                        "together."),
        },
        {
            "parameter": "Hub-routing exposure weights (h)",
            "value": "US/UK/Singapore 1.0, UAE 0.5, else 0",
            "verdict": "UNSUPPORTED",
            "evidence": "No study found that decomposes remittance attribution by "
                        "booking entity versus remitter residence.",
            "reading": ("The mechanism is documented — correspondent banking and MTO "
                        "booking entities concentrate in these countries — but the "
                        "WEIGHTS are mine. This is why h is swept end-to-end and the "
                        "E1/E2 band is reported rather than a point estimate."),
        },
        {
            "parameter": "Advanced-economy migration cost",
            "value": "US$15,000 base case, swept",
            "verdict": "UNSUPPORTED",
            "evidence": "Gulf recruitment cost is measured (KNOMAD/ILO, 1-9 months of "
                        "earnings). No equivalent for skilled migration to the West.",
            "reading": "Swept 5k-40k precisely because nothing pins it.",
        },
    ]


def main() -> int:
    df = pd.DataFrame(rows())
    order = {"SUPPORTED": 0, "DIRECTIONAL": 1, "STRUCTURAL": 2, "UNSUPPORTED": 3}
    df = df.sort_values("verdict", key=lambda s: s.map(order))

    print("=== ASSUMPTIONS AGAINST THE LITERATURE ===\n")
    print(df[["parameter", "value", "verdict"]].to_string(index=False))

    counts = df.verdict.value_counts()
    print(f"\n  {counts.get('SUPPORTED', 0)} supported · {counts.get('DIRECTIONAL', 0)} directional · "
          f"{counts.get('STRUCTURAL', 0)} structural · {counts.get('UNSUPPORTED', 0)} unsupported")

    for v in ("SUPPORTED", "DIRECTIONAL", "STRUCTURAL", "UNSUPPORTED"):
        sub = df[df.verdict == v]
        if sub.empty:
            continue
        print(f"\n{'=' * 74}\n{v}\n{'=' * 74}")
        for _, r in sub.iterrows():
            print(f"\n  {r.parameter}  [{r.value}]")
            print(f"    evidence : {r.evidence}")
            print(f"    reading  : {r.reading}")

    print(f"\n{'=' * 74}\nWHAT THIS EXERCISE CHANGED\n{'=' * 74}")
    print("  1. The wage-growth band was hardcoded at 2.0-4.0% and contradicted this")
    print("     repo's own measured panel, where the Netherlands runs at 4.50%. It now")
    print("     derives from that panel. The crossover finding survives — Indian wage")
    print("     growth of 5.39% still clears the widened top of the band.")
    print("  2. The claim that advanced-economy migrants remit less because families")
    print("     join them was a structural assertion here. It is a documented finding.")
    print("  3. The Netherlands ranks first on savings and has the EU's highest housing")
    print("     cost overburden rate. Those two facts belong next to each other.")
    print("\n  Two parameters remain unsupported, and both are load-bearing: the")
    print("  hub-routing weights and the advanced-economy migration cost. Both are")
    print("  swept end to end rather than reported as points, which is the correct")
    print("  handling of a number nobody has measured — but it is not the same as")
    print("  knowing it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
