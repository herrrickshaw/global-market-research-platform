#!/usr/bin/env python3
"""
Single definition of the price-band ladder, shared by every consumer.

Two things read this: the daily mailer's "By price band" section
(build_mailer._price_band_rows) and the deeper cross-section report
(price_band_analysis.py). They run off DIFFERENT sources — the mailer off the
combined-report JSON picks payload, the report off the raw scan workbook — and
compute different things from them, so their loaders and aggregations are
deliberately NOT shared. What must never drift between them is the ladder
itself: if the mailer says "₹500–1000" and the report says "₹500–1500", the
two disagree about the same stock and neither is checkable against the other.

So this module owns exactly the parts that have to agree — the band edges, the
labels, the bucketing, the capacity rule and the caveat — and nothing else.

A band is NOT a valuation statement. In India the share price is mostly face
value x share count, so "cheap stock" is a category error. Measured on the
2026-09-03 India universe (1,392 names) earnings yield FALLS monotonically as
price rises, 5.5% in the bottom band to 2.7% in the top: the pricier bands are
where you pay up for quality, not where quality is dearer per rupee of
earnings. What the bands do track is liquidity and business size, which is what
changes the position you can actually take — hence capacity() below.
"""
from __future__ import annotations

import pandas as pd

# Per-market and in LOCAL currency. A rupee ladder applied to US dollar prices
# would put every US name in the bottom bucket, so each market gets its own.
# India's edges are the ones asked for; the US ladder is a working analogue and
# has no research behind it — change it freely.
BANDS: dict[str, list[tuple[float, float]]] = {
    "IN": [(0, 250), (250, 500), (500, 1000), (1000, 5000), (5000, float("inf"))],
    "US": [(0, 10), (10, 50), (50, 200), (200, 1000), (1000, float("inf"))],
}

# Currency symbols for band LABELS only. Callers that already own a fuller map
# (build_mailer._CCY) should pass it as `ccy=` so there is one source of truth
# at the call site rather than two maps drifting apart here.
CCY = {"IN": "₹", "US": "$"}

# Position that keeps you at this share of median daily turnover. %ADV is the
# constraint that actually kills a small-cap edge as size grows — the platform's
# own cost model puts the illiquid-Piotroski edge as surviving ~$100k and dead
# by $10M — so the ladder carries it rather than leaving it to be inferred.
ADV_PCT = 5.0

CAVEAT = (
    "A band is not a valuation call: the share price is mostly face value x "
    "share count, and measured across the universe earnings yield falls as "
    "price rises, so the higher bands are where you pay up for quality rather "
    "than where it is dearer."
)


def bands_for(market: str) -> list[tuple[float, float]]:
    """
    Raises for a market with no ladder, rather than silently substituting
    DEFAULT_MARKET's edges. build_mailer.py already keeps EU/JP/KR picks-row
    builders "deliberately LEFT IN PLACE ... restoring a market is re-adding
    its block here" — the moment one of those gets wired to
    _price_band_rows(eu_data, "EU"), a silent US-dollar-ladder fallback would
    bucket euro/yen prices on the wrong numeric scale and produce a
    plausible-looking but meaningless report. A KeyError surfaces the gap
    immediately instead.
    """
    key = str(market).upper()
    if key not in BANDS:
        raise KeyError(
            f"no price-band ladder for market {key!r} — add an entry to "
            f"price_bands.BANDS (have: {sorted(BANDS)})"
        )
    return BANDS[key]


def label(lo: float, hi: float, market: str, ccy: dict | None = None) -> str:
    sym = (ccy or CCY).get(str(market).upper(), "")
    return f"{sym}{lo:,.0f}+" if hi == float("inf") else f"{sym}{lo:,.0f}–{hi:,.0f}"


def labels_for(market: str, ccy: dict | None = None) -> list[str]:
    return [label(lo, hi, market, ccy) for lo, hi in bands_for(market)]


def assign(prices, market: str, ccy: dict | None = None) -> pd.Categorical:
    """
    Bucket a price series. Left-closed / right-open, so a name at exactly the
    boundary lands in the higher band and no price is counted twice.

    Both consumers go through this rather than filtering by hand, which is what
    guarantees the mailer and the report bucket a given stock identically.
    """
    edges = [lo for lo, _ in bands_for(market)] + [float("inf")]
    return pd.cut(
        pd.to_numeric(prices, errors="coerce"),
        bins=edges,
        labels=labels_for(market, ccy),
        right=False,
        include_lowest=True,
        ordered=True,
    )


def capacity(turnover, adv_pct: float = ADV_PCT):
    """Position size that stays within `adv_pct` of daily turnover."""
    return pd.to_numeric(turnover, errors="coerce") * adv_pct / 100.0


def fmt_money(v, symbol: str = "$") -> str:
    """
    Compact money for a table cell: $42k / $4.2M. NaN renders as an em dash.

    Parameter is named `symbol`, not `ccy` like label()/labels_for()/assign() —
    those take a market->symbol MAP, this takes a single symbol STRING. Same
    name, different type would let a caller pass the map by copying the
    ccy=_CCY pattern used elsewhere in this module; f-string interpolation of
    a dict never raises, so that mistake would silently embed a dict repr()
    into the output instead of erroring.
    """
    if v is None or not pd.notna(v):
        return "—"
    v = float(v)
    if abs(v) >= 1e6:
        return f"{symbol}{v / 1e6:,.1f}M"
    return f"{symbol}{v / 1e3:,.0f}k"
