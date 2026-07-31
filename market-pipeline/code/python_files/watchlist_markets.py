#!/usr/bin/env python3
"""
watchlist_markets.py — which markets the watchlist is allowed to carry.

WHY THIS EXISTS. The watchlist spanned five markets (IN 336 · US 278 · KR 139 ·
JP 73 · EU 26 on 2026-07-29) but the fundamental data behind three of them does
not support the claims the brief makes about them. As of 2026-07-29 the
Cassandra store holds quality SCORES in ratio-named columns for exactly those
markets — `pb` takes four distinct values (25/40/50/65) in japan and europe,
`roe` takes 80/55/40/20 in china and korea — while india's `roe` on the same
column is a genuine fraction (0.160). Postgres tells the same story from the
other side: fundamentals.ratios covers us, korea and india only, and of those
only us and india carry real P/E at usable density (2,365 and 1,221 symbols).

So JP/KR/EU names were being screened, scored, ranked and mailed on fundamentals
that are either absent or are a 0-100 grade wearing a ratio's name. Carrying
them makes the brief look broader than the evidence is. Two well-evidenced
markets beat five, three of which cannot be checked.

🔴 THIS IS A DATA-COVERAGE DECISION, NOT A MARKET VIEW. Nothing here says Japan
or Korea are bad markets — the earlier zone-rule work found KR mean-reversion
among the strongest effects measured anywhere. It says the pipeline cannot
currently support a per-name fundamental claim about them. When the fundamentals
land and completeness_graph stops flagging them, add the code back here and the
whole chain follows; that is the point of having one list rather than fourteen.

2026-07-31 UPDATE — 3-tier priority (user-set, see market_tiers.py):
    Tier 1 (IN, US)          — daily, full fundamentals-backed watchlist (COVERED, unchanged)
    Tier 2 (EU, JP, KR)      — daily, TECHNICAL ONLY (see below — the PARKED
                               reasons for these three are unchanged and real)
    Tier 3 (everything else) — weekly, TECHNICAL ONLY, via weekly_extended_scan.py

This file's `COVERED`/`PARKED` split stays exactly as evidenced above — it
answers "can we mail a per-name FUNDAMENTALS claim for this market", not
"does this market get scanned at all". Tier 2/3 markets ARE now scanned
(daily for tier 2 via the existing full_*_market_scan.py scripts, weekly
for tier 3 via weekly_extended_scan.py) and DO get a mailer section — see
`technical_markets()` below — it just carries Darvas/technical signals
only, never a PE/ROE/fundamentals-based pick, because the data still can't
support one for these markets. Reversing PARKED itself requires the
underlying Cassandra/Postgres fundamentals gap to close first, same as the
file always said.

Usage:
    import watchlist_markets as WM
    if not WM.covered(mkt):
        continue
    df = WM.restrict(df)          # drops rows outside the covered (fundamentals) set
    WM.technical_markets(2)       # ['EU','JP','KR'] — tier 2, technical-only mailer section
"""
from __future__ import annotations

import market_tiers as _MT

# Canonical short codes, as used in watchlist.csv's `market` column.
# = market_tiers.TIER1 — the only markets with fundamentals good enough to
# back a per-name claim (see PARKED below for why tiers 2/3 aren't here).
COVERED: tuple[str, ...] = tuple(_MT.TIER1)

# Deliberately parked FROM FUNDAMENTALS-BASED COVERAGE, with the reason each
# is out. Kept as data rather than a comment so the brief can state WHY a
# market has no fundamentals claim instead of silently omitting one — an
# unexplained gap reads as an oversight. Does NOT mean "not scanned at all"
# — see technical_markets() for tier 2/3's technical-only mailer coverage.
PARKED: dict[str, str] = {
    "JP": "fundamentals are quality scores in `pb` (4 distinct values), not ratios",
    "KR": "fundamentals are quality scores in `roe` (80/55/40/20), not ratios",
    "EU": "fundamentals are quality scores in `pb`; ratios table has no EU rows",
    "CN": "no real fundamentals; not in fundamentals.ratios",
    "HK": "Cassandra partition empty as of 2026-07-29",
}


def technical_markets(tier: int | None = None) -> list[str]:
    """Markets eligible for TECHNICAL-ONLY coverage (Darvas/momentum, no
    fundamentals claim) — tier 2 and 3 in market_tiers.py. Pass a specific
    tier (2 or 3) to filter, or None for both combined."""
    if tier is not None:
        return list(_MT.ALL_TIERS.get(tier, []))
    return list(_MT.TIER2) + list(_MT.TIER3)

# Long forms seen in scan files and Cassandra, mapped to the canonical code.
_ALIAS = {"india": "IN", "in": "IN", "nse": "IN", "bse": "IN",
          "us": "US", "usa": "US", "united states": "US",
          "japan": "JP", "jp": "JP", "korea": "KR", "kr": "KR",
          "europe": "EU", "eu": "EU", "china": "CN", "cn": "CN",
          "hong_kong": "HK", "hk": "HK"}


def norm(market: str) -> str:
    """Canonical code for any spelling of a market name."""
    if market is None:
        return ""
    m = str(market).strip()
    return _ALIAS.get(m.lower(), m.upper())


def covered(market: str) -> bool:
    return norm(market) in COVERED


def restrict(df, col: str = "market"):
    """Drop rows outside the covered set. No-op if the column is absent."""
    if df is None or getattr(df, "empty", True) or col not in getattr(df, "columns", []):
        return df
    return df[df[col].map(covered)].copy()


def why_absent(market: str) -> str:
    """Human-readable reason a market is not carried, for the brief."""
    return PARKED.get(norm(market), "not in the covered set")


if __name__ == "__main__":
    print(f"covered: {', '.join(COVERED)}")
    for k, v in PARKED.items():
        print(f"  parked {k}: {v}")
