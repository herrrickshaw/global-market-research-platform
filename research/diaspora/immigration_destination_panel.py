#!/usr/bin/env python3
"""
The destination choice set an Indian migrant actually faces, and what is known
about each one.

WHERE THE COUNTRY LIST COMES FROM, AND WHAT THAT IS WORTH
---------------------------------------------------------
The candidate list is drawn from the "best countries to migrate from India"
genre — Global Citizen Solutions, CanApprove, Visa Library, Immigrant Invest,
Shiksha, UniAcco and similar. Those pages are published by immigration
consultancies and relocation agencies. They sell the visas they recommend, so
their rankings are advertising and their numbers are not usable.

They are used here for exactly one thing: to scope the choice set. Which
destinations do Indians actually consider? That question the marketing pages
answer honestly, because it reflects their own demand. Every number attached to
those countries comes from somewhere else — OECD for wages, Eurostat and MoSPI
for inflation, published immigration policy for pathways.

That split is the point. The pages define the rows; they do not fill the cells.

WHAT THIS ADDS OVER THE EXISTING RANKINGS
-----------------------------------------
Coverage goes from 16 countries to 30, and one dimension is added that the
savings modules could not see at all: how long it takes to become permanent,
and whether nationality changes the answer. For Indian nationals it changes the
answer enormously in one case, and that case is the single largest destination.

Usage:
    python3 research/diaspora/immigration_destination_panel.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from india_remittance_estimator import COUNTRIES, build  # noqa: E402
from real_savings_ranking import INDIA_CPI, INDIA_WPI_YOY, WAGE_PPP_USD_2024  # noqa: E402

CHOICE_SET_SOURCE = ("Immigration-consultancy 'best countries to migrate from India 2026' listings "
                     "(Global Citizen Solutions, CanApprove, Visa Library, Immigrant Invest, "
                     "Shiksha, UniAcco). Used to scope the row set only — these are marketing "
                     "pages published by firms selling the visas they recommend.")

# ===========================================================================
# SOURCED — OECD average annual wages 2024, USD PPP, for destinations the
# savings modules did not previously cover. Grade B: OECD figures reported by
# aggregators rather than read off the OECD tables directly, which this
# environment's egress policy blocks (oecd.org returns 403).
# ===========================================================================
WAGE_PPP_USD_2024_EXTENDED = {
    "Luxembourg": 90384, "Denmark": 88971, "Belgium": 86545, "Ireland": 86235,
    "Austria": 83716, "Norway": 82016, "South Korea": 60909, "Sweden": 60415,
    "Finland": 59597, "Spain": 54564, "Italy": 51019, "Poland": 44211,
    "Portugal": 40002, "Czechia": 38489,
}

# SOURCED — host inflation. Eurostat HICP, annual rate. Only the values the
# search channel returned specifically; the rest stay unknown rather than being
# filled from a euro-area aggregate that would misstate each member.
HOST_CPI_PCT = {
    "Sweden": 1.0, "Czechia": 1.1, "Denmark": 1.8,   # Eurostat, June 2026
}
EURO_AREA_CPI_PCT = 2.9      # Eurostat flash estimate, July 2026
HOST_CPI_NOTE = "Eurostat HICP annual rate, Jun-2026; euro-area flash Jul-2026 = 2.9%"

# SOURCED — the one immigration fact that dominates this decision for Indian
# nationals specifically, and which none of the savings modules can see.
US_BACKLOG = {
    "category": "EB-2 / EB-3 employment-based green card, India-born",
    "estimate": "12-15+ years on current Visa Bulletin movement",
    "status_aug_2026": "EB-2 India filing cut-off UNAVAILABLE — annual cap reached; "
                       "State Department announced India hit its yearly EB-2 cap on 21 May 2026",
    "cause": "the 7% per-country cap applies regardless of population, so India and China "
             "backlogs run dramatically longer than rest-of-world",
}

# INDICATIVE — published immigration policy, summarised. Route names and
# structures are stable and checkable; the time-to-permanence column is the
# statutory or typical residence requirement, not a queue estimate, EXCEPT
# where a numerical backlog is flagged. Verify against the authority before
# acting on any of it.
#   points   — selection is points-scored rather than employer-driven
#   offer    — a job offer is required to start the route
PATHWAY = {
    # country: (route, points?, job offer needed?, years to permanence, note)
    "Canada":         ("Express Entry (CRS)", True,  False, 1, "PR on grant; among the fastest"),
    "Australia":      ("General Skilled Migration 189/190", True, False, 1, "PR on grant"),
    "New Zealand":    ("Skilled Migrant Category / Green List", True, False, 2, ""),
    "Japan":          ("Highly Skilled Professional points system", True, True, 2,
                       "HSP fast-track can reach PR in 1-3 years"),
    "Germany":        ("EU Blue Card / Opportunity Card", True, False, 3,
                       "Opportunity Card is a points-based job-seeker route"),
    "Norway":         ("Skilled worker permit", False, True, 3, ""),
    "Sweden":         ("Work permit", False, True, 4, ""),
    "Finland":        ("Specialist residence permit", False, True, 4, ""),
    "Ireland":        ("Critical Skills Employment Permit", False, True, 2,
                       "Stamp 4 after 2 years"),
    "Netherlands":    ("Highly Skilled Migrant", False, True, 5, "salary-threshold route"),
    "United Kingdom": ("Skilled Worker (sponsored)", False, True, 5, "ILR at 5 years"),
    "Austria":        ("Red-White-Red Card", True, True, 5, ""),
    "Belgium":        ("Single permit / EU Blue Card", False, True, 5, ""),
    "Luxembourg":     ("EU Blue Card", False, True, 5, ""),
    "Denmark":        ("Positive List / Pay Limit Scheme", False, True, 8,
                       "long residence requirement relative to peers"),
    "Portugal":       ("D3 highly qualified / D8", False, False, 5, ""),
    "Spain":          ("Highly Qualified Professional (Startup Law)", False, True, 5, ""),
    "Italy":          ("Decreto Flussi quota / EU Blue Card", False, True, 5, ""),
    "Poland":         ("Work permit / EU Blue Card", False, True, 5, ""),
    "Czechia":        ("Employee Card / EU Blue Card", False, True, 5, ""),
    "South Korea":    ("E-7 skilled worker, F-2 points residence", True, True, 5, ""),
    "Singapore":      ("Employment Pass -> PR", False, True, None,
                       "PR is discretionary with no published timeline"),
    "Switzerland":    ("Work permit (quota)", False, True, 10, "C permit typically at 10 years"),
    "France":         ("Passeport Talent", False, True, 5, ""),
    "United States":  ("H-1B -> EB-2/EB-3", False, True, None,
                       "STATUTORY WAIT IS NOT THE BINDING CONSTRAINT — see US_BACKLOG"),
    "UAE":            ("Golden Visa (10-yr renewable)", False, False, None,
                       "long-term residency only; no citizenship route"),
    "Saudi Arabia":   ("Premium Residency", False, False, None,
                       "residency only; no citizenship route"),
    "Qatar":          ("Permanent residency permit (capped)", False, True, None,
                       "very limited; no citizenship route"),
    "Kuwait":         ("Employer-tied residence", False, True, None, "no route onward"),
    "Oman":           ("Employer-tied residence", False, True, None, "no route onward"),
    "Bahrain":        ("Employer-tied residence", False, True, None, "no route onward"),
    "Malaysia":       ("Employment Pass / MM2H", False, True, None, "residency only in practice"),
}


def panel() -> pd.DataFrame:
    base = build(COUNTRIES, 0.5).set_index("country")
    wages = {**WAGE_PPP_USD_2024, **WAGE_PPP_USD_2024_EXTENDED}
    rows = []
    for c in sorted(set(PATHWAY) | set(wages)):
        route, pts, offer, yrs, note = PATHWAY.get(c, ("not catalogued", None, None, None, ""))
        b = base.loc[c] if c in base.index else None
        rows.append({
            "country": c,
            "wage_ppp_usd": wages.get(c),
            "wage_source": ("OECD (extended set)" if c in WAGE_PPP_USD_2024_EXTENDED
                            else ("modelled/OECD (ranked set)" if c in WAGE_PPP_USD_2024 else None)),
            "tax_30k_pct": (b.tax_burden_30k_pct if b is not None else None),
            "tax_120k_pct": (b.tax_burden_120k_pct if b is not None else None),
            "host_cpi_pct": HOST_CPI_PCT.get(c),
            "route": route,
            "points_based": pts,
            "job_offer_required": offer,
            "years_to_permanence": yrs,
            "pathway_note": note,
        })
    d = pd.DataFrame(rows)
    d["has_savings_inputs"] = d.wage_ppp_usd.notna() & d.tax_120k_pct.notna() & d.tax_30k_pct.notna()
    d["blocked_by"] = [
        "" if r.has_savings_inputs else
        ", ".join(filter(None, [
            "no wage" if pd.isna(r.wage_ppp_usd) else "",
            "no tax schedule" if (pd.isna(r.tax_120k_pct) or pd.isna(r.tax_30k_pct)) else "",
        ]))
        for r in d.itertuples()
    ]
    return d


def main() -> int:
    d = panel()

    print("=== WHERE THE CHOICE SET COMES FROM ===")
    for line in (CHOICE_SET_SOURCE[i:i + 76] for i in range(0, len(CHOICE_SET_SOURCE), 76)):
        print(f"  {line}")
    print("\n  Those pages define the rows. Every number below comes from elsewhere.")

    print(f"\n=== THE PANEL: {len(d)} destinations ===")
    print(d[["country", "wage_ppp_usd", "tax_30k_pct", "tax_120k_pct", "host_cpi_pct",
             "route", "points_based", "job_offer_required", "years_to_permanence"]]
          .to_string(index=False))

    print("\n=== COVERAGE: which destinations have the inputs, and what blocks the rest ===")
    ok = d[d.has_savings_inputs]
    print(f"  Has wage + tax schedule: {len(ok)} of {len(d)} — {', '.join(sorted(ok.country))}")
    print("  (Having the inputs is not the same as being ranked: the six Gulf states hold")
    print("   wage and a zero tax schedule but are still excluded from the savings tables,")
    print("   because no migrant-specific living cost exists for them — see gulf_wage_model.)")
    blocked = d[~d.has_savings_inputs]
    for reason, grp in blocked.groupby("blocked_by"):
        print(f"\n  Blocked by {reason} ({len(grp)}):")
        print(f"    {', '.join(sorted(grp.country))}")
    print("\n  The binding constraint is no longer wages — it is the tax schedule. Adding")
    print("  14 OECD wages moved nothing into the ranked set, because a wage without a")
    print("  matching tax schedule cannot produce a savings figure. OECD Taxing Wages")
    print("  carries exactly the series needed (net personal average tax rate, single, no")
    print("  children, at 100% of the average wage) and oecd.org is blocked here at 403.")
    print("  That one table would move most of these 14 into the ranking at a stroke.")

    print("\n=== TIME TO PERMANENCE ===")
    t = d[d.years_to_permanence.notna()].sort_values("years_to_permanence")
    print(t[["country", "years_to_permanence", "route", "points_based",
             "job_offer_required"]].to_string(index=False))
    nop = d[d.years_to_permanence.isna()]
    print(f"\n  No published timeline or no route onward: {', '.join(sorted(nop.country))}")

    print("\n=== THE FACT THAT DOMINATES THIS DECISION FOR INDIAN NATIONALS ===")
    print(f"  {US_BACKLOG['category']}")
    print(f"    estimate : {US_BACKLOG['estimate']}")
    print(f"    status   : {US_BACKLOG['status_aug_2026']}")
    print(f"    cause    : {US_BACKLOG['cause']}")
    print("\n  Every other module in this directory ranks the United States on money, and")
    print("  the real-savings ranking puts it first. This is the column money cannot see:")
    print("  the same job in Canada or Australia converts to permanent residence in about")
    print("  a year, and in the United States an Indian national may wait over a decade for")
    print("  the same status — a wait that attaches to nationality, not to the person's")
    print("  skills or salary. A colleague born elsewhere, in the identical role, does not")
    print("  face it.")
    print("\n  That does not make the savings ranking wrong. It makes it one axis of two,")
    print("  and for many people the slower axis is the one that decides.")

    print("\n=== INFLATION CONTEXT ===")
    print(f"  Host: {HOST_CPI_NOTE}")
    for c, v in sorted(HOST_CPI_PCT.items(), key=lambda kv: kv[1]):
        print(f"    {c:<12s} {v:>5.1f}%")
    print(f"    {'euro area':<12s} {EURO_AREA_CPI_PCT:>5.1f}%")
    print(f"  India (MoSPI): CPI {INDIA_CPI['CPI (General)']:.2f}%, WPI {INDIA_WPI_YOY:.2f}%")
    print("\n  Every host rate here sits below India's. For anyone whose savings are a claim")
    print("  on Indian goods, that gap is the return — and it is why the destination's own")
    print("  inflation rate matters far less than the one at home.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
