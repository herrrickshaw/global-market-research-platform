#!/usr/bin/env python3
"""
score_screens_vs_factor_indices.py — how much do our screens agree with NSE's?

THE QUESTION. The platform builds Darvas (momentum/trend) and Piotroski
(quality) screens. NSE builds NIFTY200 Momentum 30 and NIFTY200 Quality 30 from
a published rulebook and marks them to market daily. If two independent attempts
at "momentum" disagree completely, at least one of them is not measuring
momentum — so the overlap is a free, external check on construct validity.

🔴 THE COMPARISON IS ONLY FAIR INSIDE THE INDEX'S OWN PARENT UNIVERSE, and
getting this wrong is the single easiest way to produce a meaningless number.
NIFTY200 Momentum 30 selects from the Nifty 200. Our scan runs over ~3,484 India
names. Scored globally, a screen that picks brilliant smallcaps looks like a
failure purely because those names were never ELIGIBLE — the disagreement would
be about the universe, not about momentum. So every comparison below is
restricted to the parent index first, and the unrestricted number is reported
separately and labelled as what it is.

🔴 AND OVERLAP MUST BE TESTED AGAINST CHANCE, NOT EYEBALLED. Picking 30 of 200
at random already hits ~4.5 of a 30-name index. A raw "we matched 6" means
nothing without the null. This uses the hypergeometric distribution — the exact
test for sampling without replacement — reporting P(overlap >= observed).

🔴 CADENCE. NSE rebalances semi-annually (cut-offs 31 Jan / 31 Jul, on 6-month
average data); our scan is daily. A daily screen SHOULD disagree with a
six-month-stale membership list at the edges, and that disagreement is not
error. Treat the overlap as a floor on agreement, never as an accuracy score.

MEASURED 2026-08-17 (2,367 India names; Darvas flagged 624, Piotroski 2,023):

    screen     index                    universe   picks  overlap  E[chance]   p
    darvas     nifty200Momentum30       N200(200)     75      14       11.2  0.178
    darvas     nifty500Momentum50       N500(500)    170      29       17.0  0.0002
    piotroski  nifty200Quality30        N200(200)    196      30       29.4  0.519
    piotroski  nifty500Quality50        N500(500)    481      50       48.1  0.130

🔴 THE PIOTROSKI ROWS ARE A NULL RESULT DRESSED AS A PERFECT ONE. 30 of 30 and
50 of 50 look like total agreement; they are nothing of the kind. The screen
flags 2,023 of 2,367 names (85%) and 196 of the 200 Nifty 200 names, so it
CANNOT miss a member — chance alone predicts 29.4 of 30. A filter that admits
85% of its universe carries almost no information, and the containment is
arithmetic, not agreement. This is the same "absence of a discriminating test"
shape as E-028: with fundamentals largely `median_imputed`, most names sit inside
every acceptance band by construction.

Darvas is the real result: at Nifty 500 scope 29 of 50 against 17 expected,
p = 0.0002 — genuine, independent agreement with a rulebook it has never seen.
At Nifty 200 it is 14 against 11.2 (p = 0.18), i.e. indistinguishable from chance
within the large-cap band where momentum is most crowded.

LITERATURE, and what it says to change:

  * Jegadeesh & Titman (1993) established momentum on 6-12 month formation
    windows — the horizon NSE uses. Carhart (1997) made it the fourth factor.
    Darvas is a price-structure rule rather than a ranked return, which is why
    partial agreement rather than identity is the expected outcome.
  * Standard momentum construction SKIPS THE MOST RECENT MONTH to avoid the
    short-term reversal effect. Darvas does not, and its box logic keys on the
    most recent bars specifically — the single clearest divergence from the
    literature and the most testable change here.
  * NSE normalises momentum by VOLATILITY (as does residual-momentum work);
    Darvas does not scale by dispersion at all, so it will over-weight
    high-variance names that a vol-adjusted score demotes.
  * Asness, Frazzini & Pedersen (Quality Minus Junk) define quality on
    profitability, growth and safety — close to NSE's ROE / D-E / EPS-variability
    triple, and notably a RANKING rather than a pass/fail count. Piotroski (2000)
    was designed as a 9-point score used to sort within a value universe, not as
    a standalone universal filter; using it as the latter is what produces an 85%
    pass rate.
  * Bender et al., "Foundations of Factor Investing" (MSCI), and Pástor &
    Stambaugh (2003) on liquidity motivate the eligibility screen NSE applies —
    impact cost <= 0.50% on a Rs 10 crore portfolio — which is a better-specified
    liquidity gate than a turnover floor and is worth adopting directly.

    python3 score_screens_vs_factor_indices.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from math import comb

import pandas as pd

sys.path.insert(0, os.path.expanduser("~/backend"))

# screen -> (factor index, parent universe index, what NSE says it measures)
PAIRS = [
    ("darvas",    "nifty200Momentum30_list", "Nifty 200",
     "6M+12M return, volatility-adjusted"),
    ("darvas",    "nifty500Momentum50_list", "Nifty 500",
     "6M+12M return, volatility-adjusted"),
    ("piotroski", "nifty200Quality30_list",  "Nifty 200",
     "ROE, debt/equity, 5y EPS-growth variability"),
    ("piotroski", "nifty500Quality50_list",  "Nifty 500",
     "ROE, debt/equity, 5y EPS-growth variability"),
]
PARENT = {"Nifty 200": "niftv200", "Nifty 500": "nifty500"}   # resolved below


def psql(sql: str) -> list[str]:
    r = subprocess.run(["psql", "-d", "market_data", "-tAq", "-c", sql],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:200])
    return [l for l in r.stdout.strip().splitlines() if l]


def members(index_like: str) -> set[str]:
    rows = psql("SELECT DISTINCT symbol FROM indices.nse_membership "
                f"WHERE index_name ILIKE '{index_like}'")
    return set(rows)


def hypergeom_sf(k: int, N: int, K: int, n: int) -> float:
    """P(X >= k) drawing n from N with K successes. Exact, no scipy dependency."""
    if n == 0 or K == 0:
        return 1.0
    tot = comb(N, n)
    return sum(comb(K, i) * comb(N - K, n - i)
               for i in range(k, min(K, n) + 1) if N - K >= n - i) / tot


def get_picks() -> tuple[set[str], set[str], int]:
    """Run the live scanners over the India universe in Cassandra."""
    from db import cassandra_client as cass
    from db.quote_updater import get_market_quotes_df
    from scanners.daily_scanner import scan_darvas, scan_piotroski
    if not cass.connect():
        raise RuntimeError("Cassandra unreachable — cannot score live picks")
    d = get_market_quotes_df("india")
    dar = pd.DataFrame(scan_darvas(d))
    pio = pd.DataFrame(scan_piotroski(d))
    D = set(dar.loc[dar.signal.isin(("BUY", "WATCH")), "ticker"].str.upper()) if len(dar) else set()
    P = set(pio.loc[pio.signal.isin(("BUY", "WATCH")), "ticker"].str.upper()) if len(pio) else set()
    return D, P, len(d)


def main() -> int:
    darvas, piotroski, universe_n = get_picks()
    picks = {"darvas": darvas, "piotroski": piotroski}
    print(f"# Screens vs NSE factor indices\n")
    print(f"Scanned {universe_n:,} India names — Darvas flagged {len(darvas):,}, "
          f"Piotroski {len(piotroski):,}.\n")
    print("| screen | NSE index | universe | eligible picks | index | overlap | "
          "expected by chance | P(>=obs) |")
    print("|---|---|---|---|---|---|---|---|")

    for screen, idx, parent_label, _rule in PAIRS:
        idx_members = members(idx)
        # Exact names verified against the table: 'nifty200list' (200) and
        # 'nifty500list' (500). Matching on a LIKE pattern here would silently
        # union several 500-name variants (EqualWeight, Multicap502525,
        # SmallCap500) that are DIFFERENT portfolios of the same size.
        parent = members("nifty200list" if parent_label == "Nifty 200" else "nifty500list")
        if not idx_members or not parent:
            print(f"| {screen} | {idx} | {parent_label} | — | — | — | — | index or parent missing |")
            continue

        # Restrict BOTH sides to the parent universe: the index is a subset of it
        # by construction, and our picks must be too for the draw to be comparable.
        elig = picks[screen] & parent
        K = len(idx_members & parent)
        N, n = len(parent), len(elig)
        k = len(elig & idx_members)
        exp = n * K / N if N else 0
        p = hypergeom_sf(k, N, K, n)
        print(f"| {screen} | {idx} | {parent_label} ({N}) | {n} | {K} | **{k}** | "
              f"{exp:.1f} | {p:.4f} |")

    # The unrestricted number, reported separately and labelled.
    print("\n**Unrestricted (whole India universe) — shown only to make the "
          "universe effect visible; it is NOT the comparable figure:**\n")
    for screen, idx, _p, _r in PAIRS[:1] + PAIRS[2:3]:
        m = members(idx)
        print(f"- {screen}: {len(picks[screen] & m)} of {len(m)} {idx} names, "
              f"out of {len(picks[screen]):,} picks across the full universe")

    print("\n**What each side finds that the other does not (Nifty 200 scope):**\n")
    for screen, idx, parent_label, rule in PAIRS[:1] + PAIRS[2:3]:
        m = members(idx)
        parent = members("nifty200list")
        elig = picks[screen] & parent
        only_us = sorted(elig - m)[:10]
        only_nse = sorted((m & parent) - elig)[:10]
        print(f"- **{screen}** vs `{idx}` (NSE rule: {rule})")
        print(f"    - ours only: {', '.join(only_us) or '—'}")
        print(f"    - NSE only : {', '.join(only_nse) or '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
