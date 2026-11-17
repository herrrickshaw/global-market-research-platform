#!/usr/bin/env python3
"""
validation_registry.py — the MECE partition of every (filter, market)
combination tracked in filter_watchlist.csv, by validation status.

METHOD: CEME, per https://powerful-problem-solving.com/be-more-mece
(user-provided 2026-08-23) — Collectively Exhaustive first (enumerate every
combination that actually exists, via filter_watchlists.FILTERS, not from
memory), THEN Mutually Exclusive (assign each to exactly one status, no
overlap). test_validation_registry.py proves both properties hold: every
FILTERS pair is covered, and none is covered twice.

STATUSES (mutually exclusive, collectively exhaustive over every entry):
  VALIDATED_EDGE   backtested 2026-08-23 with fixed-horizon rigor (real
                   benchmark, entry-bar-correct, staleness/split-guarded) —
                   POSITIVE result. Currently: darvas x IN only.
  TESTED_NO_EDGE   same rigor, result was zero or negative.
  INCONCLUSIVE     same rigor, but sample too small/immature to conclude
                   either way (currently: golden_cross, both markets — only
                   566 raw signals total, too rare for a mature 1yr sample).
  UNTESTED         never run through the 2026-08-23 fixed-horizon backtest.

🔴 A caught mistake, worth keeping visible: filter_watchlists.py's
`piotroski` filter reads India's scan-xlsx Piotroski_Score column (IN-only).
The "Piotroski F-Score" backtested 2026-08-23 in
run_existing_screeners_fixed.py was built FRESH from
public.global_fundamentals and is US-only (same total_assets gap as
gross_profitability/accruals) — it is NOT the same signal as
filter_watchlists.py's IN-only piotroski, despite the shared name. So
piotroski x IN is UNTESTED here, not TESTED_NO_EDGE — the US Piotroski
result does not transfer to it. Do not conflate them again.

Sources for every entry below are real run outputs from 2026-08-23, not
recollection — see research/LITERATURE_REGISTER.md "Existing-screener +
screener.in round" for the full backtest output this was built from.
"""
from dataclasses import dataclass

VALIDATED_EDGE = "VALIDATED_EDGE"
TESTED_NO_EDGE = "TESTED_NO_EDGE"
INCONCLUSIVE = "INCONCLUSIVE"
UNTESTED = "UNTESTED"

ALL_STATUSES = {VALIDATED_EDGE, TESTED_NO_EDGE, INCONCLUSIVE, UNTESTED}


@dataclass(frozen=True)
class Validation:
    status: str
    evidence: str  # one-line summary with the real number, or why untested/inconclusive


REGISTRY: dict[tuple[str, str], Validation] = {
    ("darvas", "IN"): Validation(
        VALIDATED_EDGE,
        "+1.41% vs bench @1yr, n=17,963, win 60%, monotonic -0.40%->+1.41% "
        "across 1mo/3mo/6mo/1yr. Corroborates code/python_files/CLAUDE.md's "
        "pre-existing 'India|momentum/trend, +5.3%/6M' finding."),
    ("darvas", "US"): Validation(
        TESTED_NO_EDGE, "-1.87% vs bench @1yr, n=16,267."),
    ("darvas", "KR"): Validation(UNTESTED, "no local price panel depth confirmed for this backtest"),
    ("darvas", "JP"): Validation(UNTESTED, "no local price panel depth confirmed for this backtest"),
    ("darvas", "EU"): Validation(UNTESTED, "no local price panel depth confirmed for this backtest"),

    ("ema", "US"): Validation(UNTESTED, "not run in the 2026-08-23 round"),
    ("ema", "KR"): Validation(UNTESTED, "not run in the 2026-08-23 round"),
    ("ema", "JP"): Validation(UNTESTED, "not run in the 2026-08-23 round"),
    ("ema", "EU"): Validation(UNTESTED, "not run in the 2026-08-23 round"),

    ("piotroski", "IN"): Validation(
        UNTESTED,
        "the IN-only scan-xlsx Piotroski_Score was never backtested; the "
        "Piotroski F-Score tested 2026-08-23 was a DIFFERENT, US-only "
        "computation from global_fundamentals — does not transfer to this row"),

    ("golden_cross", "IN"): Validation(
        INCONCLUSIVE, "only 247 signals total, no mature 1yr sample; 6mo +0.38% vs bench"),
    ("golden_cross", "US"): Validation(
        INCONCLUSIVE, "only 227 signals total, no mature 1yr sample; 6mo -6.12% vs bench"),
    ("golden_cross", "KR"): Validation(UNTESTED, "not run in the 2026-08-23 round"),
    ("golden_cross", "JP"): Validation(UNTESTED, "not run in the 2026-08-23 round"),
    ("golden_cross", "EU"): Validation(UNTESTED, "not run in the 2026-08-23 round"),
}


def status_of(filt: str, mkt: str) -> Validation:
    """Never guess — an unregistered pair is a bug (FILTERS grew without a
    matching registry entry), not silently UNTESTED. Fails loudly."""
    key = (filt, mkt)
    if key not in REGISTRY:
        raise KeyError(f"({filt!r}, {mkt!r}) is not in validation_registry.REGISTRY — "
                       f"a new filter/market pair was added to filter_watchlists.FILTERS "
                       f"without a corresponding entry here. Add one (even UNTESTED) "
                       f"rather than let this raise.")
    return REGISTRY[key]
