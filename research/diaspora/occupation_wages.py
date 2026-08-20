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

SALARIES["accountant"] = {
    "United States": (89870, "USD", "BLS OEWS May-2025 mean, accountants and auditors"),
    "United Kingdom": (55000, "GBP", "chartered accountant, mid-level"),
    "India": (396000, "INR", "mid-level"),
}
SALARIES["civil engineer"] = {
    "United States": (80680, "USD", "2026 national average"),
    "Australia": (107215, "AUD", "2026 national average"),
}

# Deliberately excluded. The German software-engineer figure that surfaced was
# quoted in USD by an aggregator with no stated conversion basis — it cannot be
# placed on the same footing as the local-currency figures above, and guessing
# which basis it used is how the errors in this project have happened.
EXCLUDED = {
    ("software engineer", "Germany"):
        "quoted in USD by an aggregator, conversion basis unstated",
    ("data scientist", "*"):
        "every retrieved figure was either in USD with no stated basis, a wide "
        "range rather than a central estimate, or the country's ALL-OCCUPATION "
        "average mislabelled as the role's. Nothing comparable survived, so the "
        "role is absent rather than approximated",
    ("civil engineer", "Germany"):
        "EUR 119,000 is roughly twice Germany's all-occupation average wage and "
        "is not credible as a civil-engineer mean",
    ("civil engineer", "United Kingdom"):
        "entry-level band only, not comparable to the national averages here",
    ("civil engineer", "Canada"):
        "CAD 175,500 is an Alberta figure, a regional outlier",
}

# The panel thins fast past the first two roles. That is a property of the
# sources, not of the roles: past software engineering and nursing, the
# published figures stop sharing a basis. Rows are left incomplete rather than
# filled with numbers that cannot be compared.
ROLE_COVERAGE_NOTE = (
    "software engineer and registered nurse are complete enough to rank; "
    "accountant and civil engineer are partial; data scientist could not be "
    "assembled at all")

# Indian city and seniority variants, kept apart from the national figure
# because migrants are drawn disproportionately from the top of this range —
# which makes the counterfactual salary higher and the gain smaller.
INDIA_VARIANTS = {
    "software engineer, Bangalore": (1297600, "INR"),
    "senior software engineer, India": (1671574, "INR"),
}


# Which point of each country's distribution a figure describes. A multiple
# built from two different points is not a multiple of anything — the
# accountant row is the case: a US all-levels mean over an Indian mid-level
# figure produces a number larger than the software-engineer multiple, purely
# because the denominators sit at different seniorities.
def seniority_basis(note: str) -> str:
    n = note.lower()
    if "entry" in n:
        return "entry"
    if "mid-level" in n or "chartered" in n:
        return "mid-level"
    return "all-levels"


def to_usd(amount: float, currency: str, fx: dict[str, float]) -> float:
    return amount / fx[currency]


def table(fx: dict[str, float]) -> pd.DataFrame:
    rows = []
    for occ, by_country in SALARIES.items():
        # Not every role has an Indian comparator. Where it does not, the
        # multiple is absent rather than computed against some other base —
        # a role with no counterfactual cannot answer the migration question.
        india = (to_usd(*by_country["India"][:2], fx)
                 if "India" in by_country else None)
        for country, (amt, cur, note) in by_country.items():
            usd = to_usd(amt, cur, fx)
            rows.append({
                "occupation": occ,
                "country": country,
                "local_amount": amt,
                "currency": cur,
                "usd_market": round(usd),
                "multiple_of_india": round(usd / india, 1) if india else None,
                "seniority_basis": seniority_basis(note),
                "source_note": note,
            })
    return pd.DataFrame(rows)


def with_tax(df: pd.DataFrame) -> pd.DataFrame:
    """Apply each country's effective rate at the salary actually earned.

    The rate comes from the same interpolated schedule the savings ranking
    uses. It is applied to a MARKET-rate salary here, where the ranking applies
    it to a PPP one — the rate is a percentage so it travels, but the resulting
    net figures live in market dollars and must not be compared with the
    ranking's PPP nets.
    """
    from real_savings_ranking import build_frame, effective_tax_rate

    sched = build_frame(28000).set_index("country")[
        ["tax_burden_30k_pct", "tax_burden_120k_pct"]]
    d = df.copy()
    rates = []
    for _, r in d.iterrows():
        if r.country not in sched.index:
            rates.append(None)
            continue
        lo, hi = sched.loc[r.country]
        rates.append(float(effective_tax_rate(
            pd.Series([r.usd_market]), pd.Series([lo]), pd.Series([hi])).iloc[0]))
    d["effective_tax_pct"] = rates
    # pandas turns a None inside an assigned list into NaN, so the guard has to
    # be pd.isna and not `is None` — the identity check silently stops working
    # the moment the list touches a DataFrame.
    d["net_usd_market"] = [
        None if pd.isna(t) else round(u * (1 - t / 100))
        for u, t in zip(d.usd_market, d.effective_tax_pct)]
    return d


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

    # A multiple is only meaningful when both sides describe the same point of
    # their distribution. Where a role's rows disagree, say so instead of
    # printing a ratio that compares a mean to a median-of-mid-levels.
    mixed = {occ: sorted(set(g.seniority_basis))
             for occ, g in df.groupby("occupation")
             if g.seniority_basis.nunique() > 1}

    for occ in SALARIES:
        print(f"\n=== {occ.upper()} ===")
        d = df[df.occupation == occ].sort_values("usd_market", ascending=False)
        print(d[["country", "local_amount", "currency", "usd_market",
                 "multiple_of_india", "seniority_basis"]].to_string(index=False))
        if occ in mixed:
            print(f"    NOT COMPARABLE ACROSS COUNTRIES: this role mixes "
                  f"{' and '.join(mixed[occ])} figures.")
            print("    The multiple divides one seniority by another and means nothing.")

    print("\n=== AFTER TAX ===")
    t = with_tax(df)
    t = t[t.net_usd_market.notna()]
    for occ in SALARIES:
        sub = t[(t.occupation == occ)].sort_values("net_usd_market", ascending=False)
        if sub.empty:
            continue
        india = sub[sub.country == "India"]
        base = float(india.net_usd_market.iloc[0]) if len(india) else None
        print(f"\n  {occ}")
        for _, r in sub.iterrows():
            mult = f"{r.net_usd_market / base:5.1f}x" if base else "    -"
            print(f"    {r.country:<16s} gross US${r.usd_market:>7,.0f}  "
                  f"tax {r.effective_tax_pct:>5.2f}%  net US${r.net_usd_market:>7,.0f}  {mult}")
    print("\n  India has no net figure: this project carries no Indian tax schedule, so")
    print("  the post-tax multiple cannot be computed. The gross multiples above are")
    print("  the migration gain before either side is taxed.")

    print("\n  Does tax reorder the countries?")
    any_swap = False
    for occ in SALARIES:
        sub = t[t.occupation == occ]
        if len(sub) < 2:
            continue
        gross_order = sub.sort_values("usd_market", ascending=False).country.tolist()
        net_order = sub.sort_values("net_usd_market", ascending=False).country.tolist()
        if gross_order == net_order:
            print(f"    {occ:<20s} no — {' > '.join(gross_order)}")
        else:
            any_swap = True
            print(f"    {occ:<20s} YES")
            print(f"      gross: {' > '.join(gross_order)}")
            print(f"      net:   {' > '.join(net_order)}")
    if any_swap:
        print("\n  So the claim that tax is a second-order effect does not hold at the role")
        print("  level, even though it held for national averages. Nurses are the case:")
        print("  Australia overtakes Canada and the UK overtakes Germany once tax is")
        print("  applied, because the gross gaps between those pairs are small enough for")
        print("  a ten-point difference in burden to decide them. Where gross gaps are")
        print("  wide — anything against the United States — tax changes nothing.")

    print("\n=== THE SPENDS LEG IS MISSING, DELIBERATELY ===")
    print("  Savings = net income minus what living costs. These salaries are at MARKET")
    print("  rates, and the only living-cost figure in this project is a PPP basket.")
    print("  Subtracting one from the other would repeat the exact error that produced")
    print("  a 0.19% Swiss tax rate earlier in this work. Nominal per-country living")
    print("  costs were not sourced, so the chain stops at net income and says so.")
    print("  For savings after living costs, use the savings ranking, which is")
    print("  internally consistent in PPP throughout.")

    print("\n=== THE COUNTRY ORDERING DEPENDS ON THE OCCUPATION ===")
    orders = {occ: ordering(df, occ) for occ in SALARIES
              if len(ordering(df, occ)) >= 2}
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

    if mixed:
        print("\n=== ROLES WHOSE MULTIPLES MUST NOT BE COMPARED WITH EACH OTHER ===")
        for occ, bases in mixed.items():
            print(f"  {occ}: mixes {' and '.join(bases)}")
        print("  The accountant row is the clearest case. Its US figure is an")
        print("  all-levels mean and its Indian figure is mid-level, so it reports a")
        print("  larger multiple than software engineering — not because accountancy")
        print("  pays better to move for, but because the denominators sit at")
        print("  different points of the Indian distribution. Only the roles with a")
        print("  single basis carry a multiple worth quoting.")

    print("\n=== HOW BIG IS THE GAIN, REALLY ===")
    for occ in SALARIES:
        d = df[(df.occupation == occ) & (df.country != "India")].dropna(
            subset=["multiple_of_india"])
        if d.empty:
            print(f"  {occ:<20s} no Indian comparator — multiple cannot be computed")
            continue
        if occ in mixed:
            print(f"  {occ:<20s} SUPPRESSED — mixed seniority basis, see above")
            continue
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
    print(f"\n=== ROLE COVERAGE ===\n  {ROLE_COVERAGE_NOTE}.")
    if EXCLUDED:
        print("\n  Excluded, with the reason:")
        for (occ, c), why in EXCLUDED.items():
            print(f"    {occ} / {c}:\n      {why}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "occupation_wages.csv", index=False)
    print(f"\nCSV written: {out / 'occupation_wages.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
