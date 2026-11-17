#!/usr/bin/env python3
"""
eval_contract.py — the rules that decide whether an edge is REAL.

WHY THIS FILE EXISTS
────────────────────
The gate that judges a strategy lives in the same tree as the strategies it
judges, edited by the same hand on the same afternoon. Nothing stopped a
threshold from drifting until a result passed, and nothing recorded that it had
moved. Before this file, `MIN_NONOVERLAP = 15` was a bare literal in
data_sufficiency.py, `MIN_UNIVERSE_COV = 0.60` sat beside it, and `DSR > 0.95`
and `|t| ≳ 2` existed only as prose in docs/METHODOLOGY.md — so the two most
important numbers in the whole method were not in the code at all.

This is the single source for those numbers, and it is TAMPER-EVIDENT rather
than literally immutable: CONTRACT_HASH is a digest over every rule below, and
verify() raises when the two disagree. test_eval_contract.py calls verify(), so
changing a threshold without also updating the hash and adding a CHANGELOG
entry fails the test suite.

Changing a gate deliberately costs three lines of ceremony. Changing one by
accident, or quietly to make today's result pass, is no longer possible. That
asymmetry is the entire point — a gate you can move without noticing is not a
gate.

TO CHANGE A RULE
────────────────
  1. edit its Rule(...) below
  2. append a CHANGELOG entry saying what moved and WHY (evidence, not vibes)
  3. run `python3 eval_contract.py --rehash` and paste the new CONTRACT_HASH

Step 2 is not optional decoration. A threshold with no recorded reason is
indistinguishable from a threshold that was tuned until the answer was nice.

Run: python3 eval_contract.py            # print + verify
     python3 eval_contract.py --rehash   # recompute after a deliberate change
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    """One evaluation threshold, with the reasoning that set it."""
    value: object
    rationale: str      # what this rule prevents
    evidence: str       # where the number came from — a paper, or a run in this repo


# ══════════════════════════════════════════════════════════════════════════════
# THE CONTRACT
# ══════════════════════════════════════════════════════════════════════════════
# Sourced from docs/METHODOLOGY.md "when do we believe a result" — these are
# transcribed from the method, not invented here.

CONTRACT: dict[str, Rule] = {
    "min_nonoverlap_obs": Rule(
        15,
        "Below this a null result means 'underpowered, cannot conclude' — NOT "
        "'no effect'. Conflating the two is how a real edge gets discarded.",
        "Japan: ~11 non-overlap obs on J-Quants gave an insignificant value "
        "spread; the SAME test on 2011-2024 (~17-19 obs) gives +6.6%/6M, t 4.84. "
        "Nothing about Japan changed, only the power. docs/METHODOLOGY.md:59-62",
    ),
    "min_liquid_coverage": Rule(
        0.60,
        "Below this the covered names may be a non-random slice of the "
        "universe, so the result describes the sample, not the market.",
        "docs/METHODOLOGY.md:30,40 — flagged by data_sufficiency.py as "
        "'returns-only, coverage caveat'",
    ),
    "min_abs_t": Rule(
        2.0,
        "Significance floor, and it must be computed on NON-OVERLAPPING "
        "observations — overlapping windows autocorrelate and inflate t.",
        "docs/METHODOLOGY.md:29,37 — nonoverlap_t(), step = horizon",
    ),
    "min_dsr": Rule(
        0.95,
        "Corrects for how many factors were tried. A raw Sharpe from a wide "
        "sweep is a maximum, not an estimate; DSR is what survives that.",
        "Bailey & Lopez de Prado (2014), The Deflated Sharpe Ratio -> "
        "deflated_sharpe.py. Cleared by IN-trend 0.994, KR-breakout 0.99, "
        "EU-mom 0.985. docs/METHODOLOGY.md:38,43",
    ),
    "nonoverlap_step_is_horizon": Rule(
        True,
        "The step between observations must equal the holding horizon. Any "
        "smaller step reuses overlapping data and manufactures significance.",
        "docs/METHODOLOGY.md:29 — nonoverlap_t(), step = horizon",
    ),
}

# ══════════════════════════════════════════════════════════════════════════════
# CHANGELOG — every movement of every rule, newest last.
# ══════════════════════════════════════════════════════════════════════════════
CHANGELOG: list[dict] = [
    {
        "date": "2026-08-27",
        "rule": "*",
        "change": "contract established",
        "why": "Thresholds existed as bare literals in data_sufficiency.py and "
               "as prose in METHODOLOGY.md, with no record if they moved. "
               "Transcribed as-is — no value was changed when adopting this "
               "file, so this is a lift, not a retune.",
    },
]

# Digest over the VALUES only. Rationale/evidence text can be improved freely;
# moving a number cannot.
CONTRACT_HASH = "e815e640ed59e8ac"


class ContractViolation(RuntimeError):
    """An evaluation threshold moved without the ceremony."""


def contract_digest() -> str:
    payload = json.dumps({k: repr(r.value) for k, r in sorted(CONTRACT.items())},
                         sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def verify() -> None:
    """Raise if any threshold has moved without CONTRACT_HASH being updated."""
    actual = contract_digest()
    if actual != CONTRACT_HASH:
        raise ContractViolation(
            f"evaluation contract changed: recorded {CONTRACT_HASH}, computed "
            f"{actual}.\nA threshold moved. If deliberate: append a CHANGELOG "
            f"entry with the evidence, then run `python3 eval_contract.py "
            f"--rehash`. If you did not mean to change a gate, revert it."
        )
    if CHANGELOG[-1]["date"] < "2026-08-27":
        raise ContractViolation("CHANGELOG is missing its founding entry")


# Convenience accessors — import these rather than re-typing the literals.
verify()
MIN_NONOVERLAP_OBS: int = CONTRACT["min_nonoverlap_obs"].value
MIN_LIQUID_COVERAGE: float = CONTRACT["min_liquid_coverage"].value
MIN_ABS_T: float = CONTRACT["min_abs_t"].value
MIN_DSR: float = CONTRACT["min_dsr"].value


def main() -> int:
    ap = argparse.ArgumentParser(description="evaluation contract")
    ap.add_argument("--rehash", action="store_true",
                    help="print the digest to paste into CONTRACT_HASH")
    a = ap.parse_args()

    if a.rehash:
        print(f'CONTRACT_HASH = "{contract_digest()}"')
        return 0

    print(f"evaluation contract  [{CONTRACT_HASH}]")
    for name, r in CONTRACT.items():
        print(f"\n  {name} = {r.value!r}")
        print(f"    prevents: {r.rationale}")
        print(f"    evidence: {r.evidence}")
    try:
        verify()
    except ContractViolation as e:
        print(f"\n🔴 {e}")
        return 1
    print(f"\n✅ verified — {len(CHANGELOG)} changelog entr"
          f"{'y' if len(CHANGELOG) == 1 else 'ies'}, last "
          f"{CHANGELOG[-1]['date']} ({CHANGELOG[-1]['change']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
