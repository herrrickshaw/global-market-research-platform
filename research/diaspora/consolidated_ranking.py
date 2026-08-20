#!/usr/bin/env python3
"""
The ranking, after everything.

Five modules in this directory each answer a piece of the question and each
produces its own ordering. This puts them side by side and reports where they
agree — which is the only place a ranking deserves confidence.

It does NOT produce a weighted composite score. Weighting savings against
residency against rent trajectory would require exchange rates between
incommensurable things, chosen by me, and the number that came out would look
more authoritative than any of its inputs. Three orderings shown honestly beat
one composite invented to avoid showing three.

THE THREE HORIZONS
------------------
  YEAR 1, DEBT-FREE     What real_savings_ranking computes. The headline, and
                        the assumption most likely to be wrong for any
                        individual.

  YEAR 1, DEBT-LOADED   The same, net of what debt already claims. Only the US
                        has borrowing data here, so this shifts one row and the
                        others are shown unchanged rather than assumed debt-free.

  YEAR 10, RENT-ADJUSTED  The surplus after a decade of each country's wage
                          growth against its NEW-LETTING rent inflation — the
                          rent a migrant actually signs, not the CPI series.

Usage:
    python3 research/diaspora/consolidated_ranking.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from immigration_destination_panel import PATHWAY  # noqa: E402
from real_savings_ranking import OECD_AVG_NPATR_2025_PCT, build_frame  # noqa: E402
from rent_vs_wages import PANEL as RENT_PANEL  # noqa: E402
from rent_vs_wages import surplus_path  # noqa: E402
from us_debt_service import scenarios as debt_scenarios  # noqa: E402

# The debt case applied to the US row. Chosen as the common early-career
# position rather than the worst one: a master's financed in the US, plus a
# used car. The Indian-education-loan case is harsher and is reported alongside.
US_DEBT_CASE = "US student loan + used car"
US_DEBT_CASE_HARSH = "Indian education loan + new car"


def assemble(years: int = 10, rent_share: float = 0.35) -> pd.DataFrame:
    base = build_frame(28000)
    base = base[base.wage_grade.str.startswith("A") & base.savings_landed_india_usd.notna()]
    d = base[["country", "wage_ppp_usd", "effective_tax_pct",
              "savings_landed_india_usd"]].copy()
    d = d.rename(columns={"savings_landed_india_usd": "yr1_debtfree_usd"})

    # debt-loaded: US only, everyone else unchanged and flagged as such
    ds = debt_scenarios(87.0).set_index("scenario")
    us_common = ds.loc[US_DEBT_CASE, "lands_in_india_usd_yr"]
    d["yr1_debtloaded_usd"] = [us_common if c == "United States" else v
                               for c, v in zip(d.country, d.yr1_debtfree_usd)]
    d["debt_data"] = ["measured" if c == "United States" else "none gathered" for c in d.country]

    # 10-year, new-letting rent basis
    sp = surplus_path(rent_share, years, True).set_index("country")
    d[f"yr{years}_rentadj_usd"] = d.country.map(sp[f"surplus_yr{years}_usd"])
    d["rent_basis"] = d.country.map(sp["rent_basis"])

    d["years_to_permanence"] = d.country.map(
        {k: v[3] for k, v in PATHWAY.items()})
    return d


def rank_of(d: pd.DataFrame, col: str) -> dict:
    s = d.dropna(subset=[col]).sort_values(col, ascending=False)
    return {c: i + 1 for i, c in enumerate(s.country)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", type=int, default=10)
    ap.add_argument("--rent-share", type=float, default=0.35)
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    d = assemble(args.years, args.rent_share)
    ycol = f"yr{args.years}_rentadj_usd"
    r1, r2, r3 = rank_of(d, "yr1_debtfree_usd"), rank_of(d, "yr1_debtloaded_usd"), rank_of(d, ycol)
    d["rank_yr1_debtfree"] = d.country.map(r1)
    d["rank_yr1_debtloaded"] = d.country.map(r2)
    d[f"rank_yr{args.years}_rentadj"] = d.country.map(r3)
    d = d.sort_values("rank_yr1_debtfree")

    print("=== THE THREE ORDERINGS ===")
    print(d[["country", "yr1_debtfree_usd", "rank_yr1_debtfree",
             "yr1_debtloaded_usd", "rank_yr1_debtloaded",
             ycol, f"rank_yr{args.years}_rentadj",
             "years_to_permanence"]].to_string(index=False))
    print("\n  Note: the US is the only row where debt is measured. The others are shown")
    print("  unchanged, which flatters them — migrants to Canada, Germany and Australia")
    print("  borrow too, their data simply was not gathered.")

    # The US has no rent series (rent_vs_wages is non-US by design), so it drops
    # out of the ten-year ordering and every other country's rank shifts up one.
    # That shift is an artefact of a missing row, not movement. Compare the
    # three orderings only over the countries present in all of them.
    common = [c for c in d.country if c in r3]
    missing = [c for c in d.country if c not in r3]
    c1 = {c: i + 1 for i, c in enumerate(sorted(common, key=lambda x: r1[x]))}
    c2 = {c: i + 1 for i, c in enumerate(sorted(common, key=lambda x: r2[x]))}
    c3 = {c: i + 1 for i, c in enumerate(sorted(common, key=lambda x: r3[x]))}

    print("\n=== WHERE THEY AGREE ===")
    if missing:
        print(f"  Excluded from this comparison for want of a rent series: {', '.join(missing)}.")
        print("  Ranks below are re-based over the countries present in all three.")
    stable = [c for c in common if c1[c] == c2[c] == c3[c]]
    moved = [c for c in common if not (c1[c] == c2[c] == c3[c])]
    print(f"\n  Same position on all three horizons: "
          f"{', '.join(sorted(stable, key=lambda x: c1[x])) if stable else 'none'}")
    for c in moved:
        print(f"  {c:<16s} yr1 debt-free #{c1[c]}  ->  debt-loaded #{c2[c]}  ->  "
              f"{args.years}-yr rent-adjusted #{c3[c]}")
    if not moved:
        print("  Nothing moves. Across a debt adjustment and a decade of divergent rent")
        print("  inflation, the ordering of these countries is unchanged — which is a")
        print("  stronger result than any single ordering on its own.")

    print("\n=== THE RANKING THIS SUPPORTS ===")
    consensus = sorted(common, key=lambda c: (c1[c] + c2[c] + c3[c]))
    for i, c in enumerate(consensus, 1):
        row = d[d.country == c].iloc[0]
        spread = max(c1[c], c2[c], c3[c]) - min(c1[c], c2[c], c3[c])
        conf = "firm" if spread == 0 else ("soft" if spread == 1 else "UNSTABLE")
        yrs = row.years_to_permanence
        print(f"  {i}. {c:<16s} lands US${row.yr1_debtfree_usd:>7,.0f}/yr   "
              f"permanence {('%.0f yr' % yrs) if pd.notna(yrs) else 'no route':<9s} "
              f"[{conf}]")
    for c in missing:
        row = d[d.country == c].iloc[0]
        print(f"  --. {c:<16s} lands US${row.yr1_debtfree_usd:>7,.0f}/yr debt-free, "
              f"US${row.yr1_debtloaded_usd:,.0f} debt-loaded")
        print("      NOT PLACED. It tops the one-year debt-free table and falls to fifth of")
        print("      seven once its own debt is netted; it has no rent series here, and its")
        print("      green-card queue is the longest of any destination in this set. Three")
        print("      reasons no single position would be honest.")

    print("\n=== WHAT WOULD CHANGE IT ===")
    print("  1. Borrowing data for the six non-US destinations. The US is the only row")
    print("     carrying a debt figure, and it is the row most exposed — an Indian-financed")
    us_h = debt_scenarios(87.0).set_index("scenario").loc[US_DEBT_CASE_HARSH,
                                                          "lands_in_india_usd_yr"]
    print(f"     master's plus a new car takes it to US${us_h:,.0f}, last of the seven. Give the")
    print("     others their real debt and that gap narrows, probably a lot.")
    print("  2. Country-level tax rates. These are the weakest inputs in the whole stack.")
    _b = build_frame(28000)
    _mean = _b[_b.wage_grade.str.startswith("A")].effective_tax_pct.mean()
    print(f"     The set averages {_mean:.1f}% against an OECD-wide "
          f"{OECD_AVG_NPATR_2025_PCT}% for a single worker at")
    print("     average earnings — the right neighbourhood, but that is an aggregate check,")
    print("     not a per-country one. OECD Taxing Wages would settle it; oecd.org is")
    print("     blocked here at 403 and its published net-income figures sit on a different")
    print("     conversion basis, so they cannot substitute.")
    print("  3. Migrant-specific wages outside the Gulf. Indian migrants to the US and UK")
    print("     earn above their national average, which these figures use. Correcting that")
    print("     would widen the lead of the countries already at the top.")

    print("\n=== WHAT THE RANKING STILL CANNOT SEE ===")
    print("  Permanence is in the table and deliberately not in the score. For an Indian")
    print("  national the US employment green-card queue runs 12-15+ years against about a")
    print("  year in Canada or Australia, and no savings figure prices that. Nor does any")
    print("  of this price healthcare, schooling, family proximity, or wanting to be there.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    d.to_csv(out / "consolidated_ranking.csv", index=False)
    print(f"\nCSV written: {out / 'consolidated_ranking.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
