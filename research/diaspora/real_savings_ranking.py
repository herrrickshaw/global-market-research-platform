#!/usr/bin/env python3
"""
Cost of living, wage levels, and whether any of it beats Indian inflation.

The destination ranking measures retention efficiency — what fraction of a
given salary survives tax and transfer. Its stated blind spot was that it
modelled neither what you earn nor what you spend. This closes that, and then
asks the question that actually decides whether working abroad builds wealth:
does the savings stream outrun inflation *in India*, where the money lands?

THE PPP TRAP, AND HOW THIS AVOIDS IT
------------------------------------
The obvious move — take nominal wages, subtract a cost-of-living index — double
counts if the wage series is already PPP-adjusted, which the OECD's is. PPP
wage = nominal wage deflated by the host price level, so cost of living is
*already* inside the number.

So this works in PPP-USD throughout. In PPP terms a fixed real basket costs the
same everywhere by construction, which means cost of living collapses into a
single constant:

    savings_ppp = wage_ppp x (1 - tax) - real_basket

The basket size is the one free parameter and is swept. Converting the surplus
into Indian purchasing power multiplies by a constant that is identical across
host countries, so it cannot change the ranking — only the level.

THE INFLATION TEST
------------------
Savings earned abroad are a claim on Indian goods. Their real value erodes at
the Indian rate, not the host rate. So the hurdle a remitter has to clear is
Indian inflation, and which Indian inflation depends on what the money is for:

  - Family consumption support  -> India CPI (headline)
  - Education fees              -> CPI education services
  - Medical support             -> CPI health
  - Property and construction   -> WPI, which is running far hotter
  - Gold and personal effects   -> CPI personal care and effects, hotter still

Rather than guess per-country wage growth, this inverts the question and
reports the *breakeven*: the nominal wage growth a remitter needs just to stand
still in India. Comparing that to what advanced-economy wages actually do is
where the finding is.

All India figures come from MoSPI, live, via the MCP server. Host wage figures
are OECD and are graded — see WAGE_GRADE, and read it before quoting anything.

Usage:
    python3 research/diaspora/real_savings_ranking.py
    python3 research/diaspora/real_savings_ranking.py --basket 30000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gulf_wage_model import blended_wage as gulf_blended_wage  # noqa: E402
from india_remittance_estimator import COUNTRIES, build  # noqa: E402

# ===========================================================================
# SOURCED — India side. MoSPI, fetched 2026-08-19 via the MoSPI MCP server.
# Refresh: scripts/refresh_india_deflators.py (documented in README).
# ===========================================================================
MOSPI_VINTAGE = "MoSPI, fetched 2026-08-19"

# CPI base 2024, All India, Combined (rural+urban), series Current, Jul-2026.
INDIA_CPI = {
    "CPI (General)": 4.45,
    "Food and beverages": 5.24,
    "Housing, water, electricity, gas and other fuels": 2.16,
    "Health": 1.34,
    "Education services": 3.64,
    "Transport": 4.43,
    "Restaurants and accommodation services": 7.72,
    "Personal care, social protection and miscellaneous goods and services": 14.77,
    "Information and communication": 0.63,
}
INDIA_CPI_ASOF = "July 2026, base 2024=100, index 107.94"

# WPI base 2011-12, headline. April-2026 index 167.0 vs April-2025 154.2.
INDIA_WPI_INDEX = {"2025-04": 154.2, "2026-04": 167.0}
INDIA_WPI_YOY = round((167.0 / 154.2 - 1) * 100, 2)   # 8.30%

# What remittance money is typically for, mapped to the index that actually
# prices it. The point of the mapping is that headline CPI is the wrong hurdle
# for most of these.
USE_OF_FUNDS = {
    "family consumption support": "Food and beverages",
    "education fees": "Education services",
    "medical support": "Health",
    "rent / utilities at home": "Housing, water, electricity, gas and other fuels",
    "gold and personal effects": "Personal care, social protection and miscellaneous goods and services",
}

# ===========================================================================
# SOURCED — host side. Average annual wages, 2024, USD at PPP.
# GRADE A: OECD "Average annual wages" / Pensions at a Glance 2025.
# GRADE C: Gulf figures are recruitment-survey national averages, not a
#          statistical office, not PPP-adjusted, and — the part that matters —
#          not migrant-specific. Gulf pay is strongly bimodal and the Indian
#          population there skews heavily to the lower mode, so these overstate
#          the typical Indian migrant's wage substantially. They are carried so
#          the Gulf is not silently absent, and are excluded from the
#          like-for-like table.
# ===========================================================================
WAGE_PPP_USD_2024 = {
    "United States": 82933, "Switzerland": 87468, "Netherlands": 75370,
    "Germany": 69433, "Canada": 69417, "Australia": 67000,
    "United Kingdom": 63691, "Japan": 49446, "Singapore": 93643,
}

# Gulf wages now come from the ILO-anchored segment model rather than
# recruitment-survey national averages, which overstated the Indian migrant
# wage by 4.3-5.4x. See gulf_wage_model.py. Grade B rather than A: it is a
# model over statutory floors and published skill references, not a wage
# series — but it is migrant-specific, which the OECD figures are not.
GULF_MODELLED = gulf_blended_wage().set_index("scenario").blended_indian_migrant_usd_yr
for _c in ("Qatar", "UAE", "Saudi Arabia", "Kuwait", "Oman", "Bahrain"):
    WAGE_PPP_USD_2024[_c] = int(GULF_MODELLED["central"])

WAGE_GRADE = {c: ("B - ILO-anchored segment model, Indian-migrant-specific, nominal not PPP"
                  if c in {"Qatar", "UAE", "Saudi Arabia", "Kuwait", "Oman", "Bahrain"}
                  else ("B - OECD Asia/Pacific report, different vintage" if c == "Singapore"
                        else "A - OECD average annual wages 2024, USD PPP"))
              for c in WAGE_PPP_USD_2024}

# ===========================================================================
# INGEST SLOT — OECD Taxing Wages, net personal average tax rate.
# ===========================================================================
# The series: "net personal average tax rate" — personal income tax plus
# employee social security contributions, net of cash benefits, as a percentage
# of gross wage earnings, for a SINGLE PERSON WITHOUT CHILDREN at 100% OF THE
# AVERAGE WAGE.
#
# It is the right series for this module and not merely a convenient one: it is
# quoted at exactly the income the OECD average wage measures, so pairing the
# two needs no interpolation at all. Where a country appears here, this rate is
# used directly and the two-point interpolation is skipped.
#
# oecd.org returns 403 from this environment's egress proxy, so the table could
# not be read. TO FILL: open Taxing Wages (any recent edition), take the
# net-personal-average-tax-rate column from the single-no-children /
# 100%-of-average-wage table, and add rows below as
# "Country": rate_pct. Countries in WAGE_PPP_USD_2024_EXTENDED that gain a rate
# here become rankable on savings immediately — nothing else needs changing.
#
# Known anchor from the published summary, for checking whatever you paste in:
# Denmark is the highest in the OECD at 35.3% (2025) / 35.7% (2024), and only
# Denmark, Germany, Lithuania and Slovenia exceeded 35% in the 2024 edition.
# VERIFICATION ATTEMPT, 2026-08-20 — deliberately left unfilled.
#
# The OECD publishes net income at the average wage in USD, and those figures
# were retrieved: Switzerland 87,303; Netherlands 67,017; Luxembourg 63,385;
# United Kingdom 63,277; Norway 63,052; Iceland 60,863; Canada 60,811;
# Ireland 60,643; Australia 60,275 (single worker, average wage, 2025).
#
# They CANNOT be reconciled with the average-wage series in WAGE_PPP_USD_2024
# and must not be used to derive rates from it. The UK is the proof: a net
# income of 63,277 against the 63,691 gross carried here implies a tax rate of
# 0.65%, which is impossible. Switzerland's net of 87,303 is likewise higher
# than its gross on that series. The two are published on different conversion
# bases, so dividing one by the other produces nonsense.
#
# What the check DID establish, and it is worth keeping: the OECD-wide average
# net personal average tax rate for a single worker at average earnings was
# 25.1% in 2025. The mean effective rate this module computes across its ranked
# set is 23.3% — the right neighbourhood, which is a sanity check passed rather
# than a validation of any individual country.
#
# So the slot stays empty. Filling it from figures that cannot be reconciled
# would be worse than the gap it leaves.
OECD_NPATR_AT_AVERAGE_WAGE: dict[str, float] = {}

OECD_NET_INCOME_AT_AW_USD_2025 = {
    "Switzerland": 87303, "Netherlands": 67017, "Luxembourg": 63385,
    "United Kingdom": 63277, "Norway": 63052, "Iceland": 60863,
    "Canada": 60811, "Ireland": 60643, "Australia": 60275,
}
OECD_NET_INCOME_NOTE = ("Retrieved for verification and NOT usable as a rate denominator — "
                        "published on a different conversion basis from the average-wage series. "
                        "See the comment above OECD_NPATR_AT_AVERAGE_WAGE.")
OECD_AVG_NPATR_2025_PCT = 25.1
OECD_NPATR_SOURCE = ("OECD Taxing Wages — net personal average tax rate, single person "
                     "no children, 100% of average wage")
OECD_NPATR_SANITY = {"max_country": "Denmark", "max_rate_2024": 35.7, "max_rate_2025": 35.3}


# PARAM — the real basket, in PPP-USD. One number, because in PPP terms a fixed
# real standard of living costs the same everywhere by construction. Swept.
DEFAULT_BASKET_USD = 28000


# The single-basket logic holds only where wages are PPP-adjusted AND the
# migrant consumes something like a national-standard basket. Neither is true in
# the Gulf: the wages here are nominal, and a Gulf labour migrant's housing and
# food are largely provided in kind by the employer — Qatar's minimum wage is
# literally structured as basic + accommodation + food for that reason. Applying
# the advanced-economy basket to a US$15,123 Gulf wage returns negative savings,
# which the observed remittance flow falsifies outright.
GULF = {"UAE", "Saudi Arabia", "Qatar", "Kuwait", "Oman", "Bahrain"}
GULF_PER_REMITTER_USD = 8659.0   # central, from the remittance estimator


def effective_tax_rate(wage: pd.Series, r30: pd.Series, r120: pd.Series) -> pd.Series:
    """Tax rate at the wage actually being taxed.

    The source table carries two points on each country's schedule: the burden
    at US$30k and at US$120k. The first version of this module applied the
    $120k rate to the average wage — but the average wage is US$40-93k, so a
    progressive schedule was being charged at a rate belonging to an income
    nobody in the sample earns. Germany was the worst case: 42.2% applied to a
    US$69,433 wage.

    Linear interpolation between the two known points, clamped outside them. A
    real schedule is piecewise-linear with more kinks than this, so it is an
    approximation — but an approximation anchored at both ends beats using one
    end for everything.
    """
    span = (wage - 30000) / (120000 - 30000)
    return (r30 + (r120 - r30) * span.clip(0, 1)).round(2)


def build_frame(basket: float) -> pd.DataFrame:
    df = build(COUNTRIES, 0.5)
    d = df[df.country.isin(WAGE_PPP_USD_2024)].copy()
    d["wage_ppp_usd"] = d.country.map(WAGE_PPP_USD_2024)
    d["wage_grade"] = d.country.map(WAGE_GRADE)
    d["effective_tax_pct"] = effective_tax_rate(
        d.wage_ppp_usd, d.tax_burden_30k_pct, d.tax_burden_120k_pct)
    # An OECD rate, where present, is quoted at exactly this wage — so it
    # replaces the interpolation rather than being averaged with it.
    oecd = d.country.map(OECD_NPATR_AT_AVERAGE_WAGE)
    d["tax_basis"] = ["OECD net personal average tax rate" if pd.notna(v)
                      else "interpolated from the $30k/$120k schedule" for v in oecd]
    d["effective_tax_pct"] = oecd.fillna(d.effective_tax_pct)
    d["net_wage_ppp_usd"] = (d.wage_ppp_usd * (1 - d.effective_tax_pct / 100)).round(0)
    # Gulf rows are carried for their wage only. They get no basket and no
    # savings figure, because none can be computed without double-counting —
    # see the diagnostic in main().
    d["real_basket_usd"] = basket
    d.loc[d.country.isin(GULF), "real_basket_usd"] = float("nan")
    d["savings_ppp_usd"] = (d.net_wage_ppp_usd - d.real_basket_usd).round(0)
    d["savings_rate_pct"] = (d.savings_ppp_usd / d.net_wage_ppp_usd * 100).round(1)
    # Transfer cost bites the remitted surplus, not the gross wage.
    cost = d.send_cost_pct_q3_25.fillna(d.send_cost_pct_q3_25.mean())
    d["savings_landed_india_usd"] = (d.savings_ppp_usd * (1 - cost / 100)).round(0)
    return d.sort_values("savings_landed_india_usd", ascending=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="reports")
    ap.add_argument("--basket", type=float, default=DEFAULT_BASKET_USD)
    args = ap.parse_args()

    print("=== INDIA-SIDE DEFLATORS ===")
    print(f"  Source: {MOSPI_VINTAGE}")
    print(f"  CPI as of {INDIA_CPI_ASOF}")
    print(f"  {'CPI (General)':<70s} {INDIA_CPI['CPI (General)']:>6.2f}%")
    for k, v in sorted(INDIA_CPI.items(), key=lambda kv: -kv[1]):
        if k != "CPI (General)":
            print(f"  {k:<70s} {v:>6.2f}%")
    print(f"  {'WPI (headline, Apr-2026 vs Apr-2025)':<70s} {INDIA_WPI_YOY:>6.2f}%")
    print("\n  Note the spread. Wholesale inflation is running at nearly double consumer")
    print("  inflation, and the fastest-moving consumer division by a wide margin is")
    print("  personal care and effects — the line that carries gold. Both are exactly")
    print("  where remittance money goes when it is not funding daily consumption.")

    d = build_frame(args.basket)

    print(f"\n=== SAVINGS PER YEAR, PPP-USD (real basket = US${args.basket:,.0f}) ===")
    like = d[d.wage_grade.str.startswith("A")]
    dropped = like[like.net_wage_ppp_usd.isna()]
    like = like[like.net_wage_ppp_usd.notna()]
    print("\n--- Like-for-like: OECD PPP wages only (grade A) ---")
    t = like.copy()
    t.insert(0, "rank", range(1, len(t) + 1))
    print(t[["rank", "country", "wage_ppp_usd", "tax_burden_30k_pct", "tax_burden_120k_pct",
             "effective_tax_pct", "net_wage_ppp_usd", "savings_ppp_usd", "savings_rate_pct",
             "savings_landed_india_usd"]].to_string(index=False))

    if len(dropped):
        print(f"  Excluded for want of a tax datum, not ranked: "
              f"{', '.join(dropped.country)} (wage is known, burden is not).")

    print("\n--- All countries with any wage datum, grade shown. Not like-for-like. ---")
    print(d[["country", "bloc", "wage_ppp_usd", "net_wage_ppp_usd", "savings_ppp_usd",
             "savings_rate_pct", "savings_landed_india_usd", "wage_grade"]].to_string(index=False))

    print("\n=== THE GULF: wage gap closed, basket gap not ===")
    gw = d.loc[d.country == "UAE", "wage_ppp_usd"].iat[0]
    implied = gw - GULF_PER_REMITTER_USD
    print(f"  The ILO-anchored model puts the blended Indian migrant wage at "
          f"US${gw:,.0f}/yr,")
    print(f"  replacing recruitment-survey national averages that overstated it 4.3-5.4x.")
    print(f"  That closes the wage gap. The basket gap is now what blocks a like-for-like")
    print(f"  comparison, and it is not a detail: applying the advanced-economy basket")
    print(f"  (US${args.basket:,.0f}) to this wage returns negative savings, which the observed")
    print(f"  remittance flow falsifies outright. Gulf migrants plainly do save.")
    print(f"\n  What the living cost must be, inferred rather than sourced:")
    print(f"    wage US${gw:,.0f} - remittance US${GULF_PER_REMITTER_USD:,.0f} = "
          f"US${implied:,.0f}/yr, about US${implied / 12:,.0f}/month.")
    print(f"  That is corroborated from an unexpected direction: Qatar's ILO-developed")
    print(f"  minimum wage is structured as basic pay PLUS accommodation PLUS food, both")
    print(f"  provided in kind. A migrant whose housing and meals are employer-supplied")
    print(f"  has exactly the small out-of-pocket basket this implies.")
    print(f"\n  But it is derived FROM the remittance figure, so using it would make Gulf")
    print(f"  savings equal Gulf remittances by construction — circular, and worth no")
    print(f"  ranking place. The Gulf therefore stays out of the ranked tables. What has")
    print(f"  changed is the reason: it is no longer the wage that is unknown.")

    print("\n=== THE RECONCILIATION: retention efficiency vs absolute savings ===")
    from savings_destination_ranking import score  # noqa: PLC0415
    base = build(COUNTRIES, 0.5)
    ret = (score(base, "ACCUMULATE", "professional").dropna(subset=["score"])
           .reset_index(drop=True))
    ret["retention_rank"] = ret.index + 1
    m = like.merge(ret[["country", "retention_rank", "score"]], on="country", how="left")
    m["savings_rank"] = range(1, len(m) + 1)
    m = m.rename(columns={"score": "retention_score"})
    print(m[["country", "retention_rank", "retention_score", "savings_rank",
             "savings_landed_india_usd"]].to_string(index=False))
    us = m.loc[m.country == "United States"].iloc[0]
    de = m.loc[m.country == "Germany"].iloc[0]
    # Both columns are already ranks, so Pearson on them IS Spearman — and avoids
    # a scipy dependency this repo does not otherwise need at runtime.
    corr = m.retention_rank.corr(m.savings_rank)
    print(f"\n  The two rankings disagree — rank correlation {corr:+.2f} — and the disagreement")
    print(f"  is the finding. The United States ranks {int(us.retention_rank)} of the full set on retention")
    print(f"  efficiency and {int(us.savings_rank)} of {len(m)} on absolute savings. Within this like-for-like")
    tax_rank = int((m.tax_burden_120k_pct < us.tax_burden_120k_pct).sum()) + 1
    wage_rank = int((m.wage_ppp_usd > us.wage_ppp_usd).sum()) + 1
    print(f"  group, wage levels do the work: the US has the {wage_rank}{'st' if wage_rank == 1 else 'th'} largest wage and the")
    print(f"  {tax_rank}{'nd' if tax_rank == 2 else 'th'}-lightest burden of {len(m)}, and it is the wage that separates it — Australia's")
    print(f"  burden is lighter still and it lands {us.savings_landed_india_usd / m.loc[m.country == 'Australia', 'savings_landed_india_usd'].iat[0]:.1f}x less. The earlier ranking named")
    print("  this as its blind spot; this is that blind spot measured rather than asserted.")
    print(f"  Germany runs the other way — {int(de.retention_rank)} on retention, {int(de.savings_rank)} on savings — because a")
    print(f"  {de.effective_tax_pct:.1f}% effective burden on a wage no higher than Canada's leaves little behind.")
    print("  The Gulf cannot be placed on this table at all: its wage data is grade C, so")
    print("  the zero-tax-versus-high-wage question stays open at this evidence standard.")

    print("\n--- Basket sensitivity: does the order survive? ---")
    rows = []
    for b in (20000, 24000, 28000, 32000, 36000):
        s = build_frame(b)
        s = s[s.wage_grade.str.startswith("A")]
        rows.append({"basket_usd": b, "top4": " > ".join(s.country.head(4)),
                     "top_savings_rate_pct": s.savings_rate_pct.iloc[0]})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n=== THE INFLATION TEST: what wage growth do you need to stand still? ===")
    print("  Savings earned abroad are a claim on Indian goods, so the hurdle is Indian")
    print("  inflation, and which one depends on what the money is for.\n")
    rows = []
    for use, idx in USE_OF_FUNDS.items():
        rows.append({"money is for": use, "priced by (MoSPI)": idx,
                     "india inflation %": INDIA_CPI[idx],
                     "breakeven host wage growth %": INDIA_CPI[idx]})
    rows.append({"money is for": "property / construction", "priced by (MoSPI)": "WPI headline",
                 "india inflation %": INDIA_WPI_YOY, "breakeven host wage growth %": INDIA_WPI_YOY})
    rows.append({"money is for": "general / mixed", "priced by (MoSPI)": "CPI (General)",
                 "india inflation %": INDIA_CPI["CPI (General)"],
                 "breakeven host wage growth %": INDIA_CPI["CPI (General)"]})
    print(pd.DataFrame(rows).to_string(index=False))

    print("\n  Read that against what advanced-economy wages actually do — nominal growth")
    print("  in the low single digits through this cycle. The implications are uncomfortable:")
    print(f"    - Funding family consumption needs {INDIA_CPI['Food and beverages']:.2f}% wage growth just to hold.")
    print(f"    - Funding education needs {INDIA_CPI['Education services']:.2f}%.")
    print(f"    - Buying property needs {INDIA_WPI_YOY:.2f}%, which essentially no advanced-economy")
    print("      wage is delivering. A remitter saving for Indian property is losing ground")
    print("      every year the transfer is deferred.")
    print(f"    - Accumulating gold needs {INDIA_CPI['Personal care, social protection and miscellaneous goods and services']:.2f}%, which nothing is delivering.")
    print(f"    - Only medical support ({INDIA_CPI['Health']:.2f}%) and home rent/utilities "
          f"({INDIA_CPI['Housing, water, electricity, gas and other fuels']:.2f}%) sit low")
    print("      enough that ordinary wage growth clears them comfortably.")
    print("\n  This is the part the tax-retention ranking could not see. A destination can")
    print("  top the retention table and still lose real ground, because the hurdle is set")
    print("  in India and has nothing to do with the host country's tax code.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "real_savings_ranking.csv"
    d.to_csv(path, index=False)
    print(f"\nCSV written: {path}")

    print("\n=== WHAT IS STILL MISSING ===")
    print("  - The remaining asymmetry now runs AGAINST the advanced economies. Gulf")
    print("    wages are migrant-specific (ILO-anchored segment model); OECD wages are")
    print("    national averages. Indian migrants in the Gulf earn far below their host")
    print("    average, which is now corrected — but Indian migrants in the US and UK")
    print("    earn ABOVE theirs, concentrated in technology, medicine and finance, and")
    print("    that is not corrected because no migrant-specific series for them was")
    print("    reachable. So the advanced-economy savings figures here are understated,")
    print("    and the Gulf comparison below is the conservative one.")
    print("  - Per-country nominal wage growth is not sourced, which is why the test is")
    print("    framed as a breakeven rather than a realised real return.")
    print("  - masaladeutsch.blogspot.com was requested as a source and is blocked by")
    print("    this environment's egress policy (403). Nothing from it is used here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
