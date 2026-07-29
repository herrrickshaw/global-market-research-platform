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

Usage:
    import watchlist_markets as WM
    if not WM.covered(mkt):
        continue
    df = WM.restrict(df)          # drops rows outside the covered set
"""
from __future__ import annotations

# Canonical short codes, as used in watchlist.csv's `market` column.
COVERED: tuple[str, ...] = ("IN", "US")

# Deliberately parked, with the reason each is out. Kept as data rather than a
# comment so the brief can state WHY a market is absent instead of silently
# omitting it — an unexplained gap reads as an oversight.
PARKED: dict[str, str] = {
    "JP": "fundamentals are quality scores in `pb` (4 distinct values), not ratios",
    "KR": "fundamentals are quality scores in `roe` (80/55/40/20), not ratios",
    "EU": "fundamentals are quality scores in `pb`; ratios table has no EU rows",
    "CN": "no real fundamentals; not in fundamentals.ratios",
    "HK": "Cassandra partition empty as of 2026-07-29",
}

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
