#!/usr/bin/env python3
"""
Where does an Indian professional's salary convert best into repatriated savings?

WHAT THIS RANKS, AND WHAT IT DOES NOT
-------------------------------------
This is a *retention efficiency* ranking, not a quality-of-life ranking. It
answers one question: given the same gross USD salary, which destination lets
you keep the most, move it home most cheaply, and hold Indian assets on the
best treaty terms?

It deliberately does not model:
  - Cost of living. Savings are income minus tax minus what you spend, and
    only the tax leg is here. Zurich and Dubai do not cost the same to live in.
  - Wage levels. The same-gross-salary premise is a strong one — a role paying
    US$120k in Dubai may pay US$180k in San Francisco and US$70k in Madrid.
    Retention efficiency is a multiplier on income, not a substitute for it.
  - Currency, asset returns, healthcare, schooling, visa risk, or whether you
    want to live there.

So read it as one input to "where should I live", not the answer. The two
rankings below exist because the answer genuinely differs by intent.

TWO OBJECTIVES
--------------
  ACCUMULATE   A finite stint, then repatriate. Income retention dominates,
               remittance friction and India-side treaty treatment matter, and
               forfeited social security is a pure loss because you leave
               before vesting. Permanent residency is worth nothing to you.

  SETTLE       Build a life there. Retention still matters, but you will vest
               your pension so a missing SSA costs far less, and the treaty
               capital-gains shield on Indian assets matters less because your
               assets will not be mostly Indian.

Every input is sourced from the same country table the remittance estimator
uses. Weights are judgement and are swept.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from india_remittance_estimator import (  # noqa: E402
    COUNTRIES,
    SSA_STATUS,
    TAX_BASIS_NOTES,
    bloc_of,
    build,
)

# --------------------------------------------------------------------------
# PARAMS — judgement. Swept by --weights-sensitivity.
# --------------------------------------------------------------------------
# Component weights per objective. Must sum to 1 within an objective.
WEIGHTS = {
    # Residency carries zero weight under ACCUMULATE: you are leaving anyway, so
    # a citizenship path you will never use is worth nothing. Under SETTLE it is
    # the second-heaviest term, because a destination you cannot legally remain
    # in is not a place you can settle, whatever its tax rate.
    "ACCUMULATE": {"retention": 0.50, "remit_friction": 0.15, "india_treaty": 0.20,
                   "ssa": 0.15, "residency": 0.00},
    "SETTLE":     {"retention": 0.40, "remit_friction": 0.03, "india_treaty": 0.05,
                   "ssa": 0.12, "residency": 0.40},
}

# Whether you can actually stay. Structural facts about immigration regimes,
# not contested statistics.
#   citizenship  — a naturalisation path exists and is used in practice
#   long-term    — renewable long-residency schemes (UAE golden visa, Saudi
#                  premium residency, Qatar's permanent residency permit) but
#                  no realistic route to citizenship
#   employment   — residence is tied to an employer; the stint ends when the
#                  job does, and there is no path onward
RESIDENCY_PATH = {
    "UAE": "long-term", "Saudi Arabia": "long-term", "Qatar": "long-term",
    "Kuwait": "employment", "Oman": "employment", "Bahrain": "employment",
    "Malaysia": "long-term", "Hong Kong": "citizenship", "Thailand": "long-term",
    "Indonesia": "employment",
}
RESIDENCY_SCORE = {"citizenship": 1.0, "long-term": 0.4, "employment": 0.0}

# Which tax archetype represents each bloc's typical earner, mirroring the
# estimator. Blue-collar Gulf migration is a different question from
# professional migration, so both are reported.
ARCHETYPES = {"professional": "tax_burden_120k_pct", "worker": "tax_burden_30k_pct"}

# A missing SSA only bites if you leave before vesting. Under ACCUMULATE you
# do; under SETTLE you mostly do not.
SSA_SCORE = {"in force": 1.0, "signed 2026-02-10, NOT yet in force": 0.35, "none": 0.0}

# Countries with no personal income tax also have no social security to lose,
# so a missing SSA is not a penalty there — it is a non-event. Without this the
# Gulf gets marked down for lacking an agreement it has no use for.
NO_SS_SYSTEM = {"UAE", "Saudi Arabia", "Qatar", "Kuwait", "Oman", "Bahrain"}


def _norm(s: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Min-max to 0-1 across the countries that have the datum at all."""
    v = s.astype(float)
    lo, hi = v.min(), v.max()
    if pd.isna(lo) or hi == lo:
        return pd.Series([0.5] * len(v), index=v.index).where(v.notna())
    out = (v - lo) / (hi - lo)
    return out if higher_is_better else 1 - out


def score(df: pd.DataFrame, objective: str, archetype: str, weights=None) -> pd.DataFrame:
    w = dict(weights or WEIGHTS[objective])
    tax_col = ARCHETYPES[archetype]
    d = df.copy()

    # 1. income retention — the dominant term, and the best-populated one
    d["retention_pct"] = 100 - d[tax_col]
    c_ret = _norm(d.retention_pct, True)

    # 2. remittance friction: send cost, plus a penalty for a levy on the
    #    transfer itself. The US 1% excise applies only to cash-funded
    #    transfers, so it is a partial penalty, not a full one.
    levy_pen = d.remittance_levy.map(lambda x: 0.0 if x == "none" else 0.5)
    friction = d.send_cost_pct_q3_25 + levy_pen
    c_fri = _norm(friction, False)

    # 3. India-side treaty treatment: lower withholding on dividends and
    #    interest is better, and a treaty that leaves non-share capital gains
    #    taxable only in the country of residence is worth a lot to anyone
    #    holding Indian mutual funds.
    treaty = d[["dtaa_dividend_pct", "dtaa_interest_pct"]].mean(axis=1)
    c_tre = _norm(treaty, False)
    shield = d.treaty_cg_shield_nonshare.map({True: 1.0, False: 0.0})
    c_tre = pd.concat([c_tre, shield], axis=1).mean(axis=1, skipna=True)

    # 4. social security portability
    c_ssa = d.ssa_status.map(SSA_SCORE)
    c_ssa = c_ssa.where(~d.country.isin(NO_SS_SYSTEM), 1.0)

    # 5. can you stay?
    d["residency_path"] = d.country.map(lambda c: RESIDENCY_PATH.get(c, "citizenship"))
    c_res = d.residency_path.map(RESIDENCY_SCORE)

    comps = {"retention": c_ret, "remit_friction": c_fri, "india_treaty": c_tre,
             "ssa": c_ssa, "residency": c_res}
    for k, v in comps.items():
        d[f"c_{k}"] = (v * 100).round(1)

    # Coverage-aware: score on the components a country actually has, and
    # renormalise the weights over those. A country scored on two of four is
    # not thereby penalised — but its completeness is reported so the reader
    # can discount it.
    num = sum(comps[k].fillna(0) * w[k] for k in w)
    den = sum(comps[k].notna().astype(float) * w[k] for k in w)
    d["score"] = (num / den.replace(0, float("nan")) * 100).round(1)
    d["data_completeness_pct"] = (den / sum(w.values()) * 100).round(0)
    d["objective"] = objective
    d["archetype"] = archetype
    return d.sort_values("score", ascending=False)


def show(d: pd.DataFrame, title: str, n: int = 10) -> pd.DataFrame:
    print(f"\n=== {title} ===")
    top = d.dropna(subset=["score"]).head(n).copy()
    top.insert(0, "rank", range(1, len(top) + 1))
    print(top[["rank", "country", "bloc", "score", "retention_pct", "c_retention",
               "c_remit_friction", "c_india_treaty", "c_ssa", "c_residency",
               "residency_path", "data_completeness_pct", "ssa_status"]].to_string(index=False))
    return top


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="reports")
    ap.add_argument("--archetype", choices=list(ARCHETYPES) + ["both"], default="both")
    args = ap.parse_args()

    base = build(COUNTRIES, 0.5)
    base = base[base[ARCHETYPES["professional"]].notna() | base[ARCHETYPES["worker"]].notna()]

    frames, tops = [], {}
    archetypes = list(ARCHETYPES) if args.archetype == "both" else [args.archetype]
    for arch in archetypes:
        for obj in WEIGHTS:
            d = score(base, obj, arch)
            frames.append(d)
            label = f"{obj} · {arch} archetype"
            tops[(obj, arch)] = show(d, f"TOP 10 — {label}")

    print("\n--- Where the headline destinations actually land, and why ---")
    watch = ["United States", "United Kingdom", "Canada", "Australia", "Germany", "Singapore", "UAE"]
    rows = []
    for obj in WEIGHTS:
        d = score(base, obj, "professional").dropna(subset=["score"]).reset_index(drop=True)
        for c in watch:
            hit = d.index[d.country == c]
            if len(hit) == 0:
                continue
            r = d.loc[hit[0]]
            drags = [n for n, v in (("tax", r.c_retention), ("transfer cost", r.c_remit_friction),
                                    ("India treaty terms", r.c_india_treaty),
                                    ("social security not portable", r.c_ssa),
                                    ("no route to stay", r.c_residency))
                     if pd.notna(v) and v < 40]
            rows.append({"objective": obj, "country": c, "rank": int(hit[0]) + 1,
                         "score": r.score, "held back by": ", ".join(drags) or "-"})
    print(pd.DataFrame(rows).to_string(index=False))
    print("\n  The United States is the single largest source of remittances to India and")
    print("  ranks nowhere near the top on either objective. Four things stack against it:")
    print("  a ~29% burden at $120k, no social security agreement with India (FICA is")
    print("  forfeited unless you reach 40 quarters), no treaty shield on non-share")
    print("  capital gains, and a 1% excise on cash-funded remittances from Jan 2026.")
    print("  People clearly still go — which is the point that the ranking cannot see:")
    print("  US wage levels are high enough that a worse multiplier on a much bigger")
    print("  number still wins on absolute savings. Retention efficiency is not income.")

    print("\n--- Weight sensitivity: does the top 3 survive reweighting? ---")
    rows = []
    for obj in WEIGHTS:
        for name, w in {
            "as published": WEIGHTS[obj],
            "retention only": {"retention": 1.0, "remit_friction": 0, "india_treaty": 0,
                               "ssa": 0, "residency": 0},
            "retention halved": {**WEIGHTS[obj], "retention": WEIGHTS[obj]["retention"] / 2},
            "ssa doubled": {**WEIGHTS[obj], "ssa": WEIGHTS[obj]["ssa"] * 2},
        }.items():
            d = score(base, obj, "professional", w)
            rows.append({"objective": obj, "weighting": name,
                         "top3": " > ".join(d.dropna(subset=["score"]).country.head(3))})
    print(pd.DataFrame(rows).to_string(index=False))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "savings_destination_ranking.csv"
    pd.concat(frames).to_csv(path, index=False)
    print(f"\nCSV written: {path}")

    print("\n=== READ THIS BEFORE USING THE RANKING ===")
    print("  Cost of living is not modelled. This ranks how much of a given salary")
    print("  survives tax and transfer, not how much is left after rent and school fees.")
    print("  Nor are wage levels: the same-gross premise flatters low-tax, low-wage")
    print("  markets and penalises high-tax, high-wage ones. A US role often pays a")
    print("  large enough premium to beat a Gulf role on absolute savings despite")
    print("  ranking below it here.")
    print("\n  Two specific distortions worth knowing about:")
    for c, note in TAX_BASIS_NOTES.items():
        print(f"    {c}: {note}")
    print("\n  And one correction to the source table, found while checking this:")
    for c, st in SSA_STATUS.items():
        print(f"    {c}: {st} — it was previously carried as in force, which overstated")
        print(f"      the protection on contributions made there today.")
    print("\n  Structural point the numbers cannot show: the Gulf's advantage is")
    print("  time-boxed. There is no permanent residency or citizenship path, so")
    print("  accumulation there is a finite window ending in departure. The advanced")
    print("  economies tax far more heavily but sell something the Gulf does not.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
