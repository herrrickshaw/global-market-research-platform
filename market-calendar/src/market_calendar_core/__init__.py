"""
market_calendar_core — the trading-day calendar that existed five times.

The cross-repo knowledge graph flagged `is_trading_day` / `trading_days` as
"the same symbol in 8 repos". They were not the same function. Three different
implementations shared those two names, with **incompatible signatures**:

    india_live.is_trading_day(d, holidays=None)        # no market argument
    markets.is_trading_day(market, d, hol=None)        # ISO codes: IN, US, JP
    computed.is_trading_day(market, d)                 # words: India, US, Japan

Importing the wrong one silently returns a wrong answer rather than raising, so
this package keeps them in separate modules and deliberately exports NOTHING at
top level. Import the module you mean:

    from market_calendar_core import india_live, markets, computed

Which is which
--------------
india_live  India/NSE only. Pulls the live NSE holiday list via nsepython, caches
            it, and unions a hardcoded fallback. This is the authoritative India
            source; `markets` delegates to it for "IN".
            Extracted from: market-pipeline, global-market-data,
            global-stock-screener, stock-screener-platform (identical but for
            formatting and the cache path).

markets     19 markets, table-driven, ISO-style codes. Handles per-market weekend
            rules (Saudi rests Fri/Sat). Delegates "IN" to india_live.
            Extracted from: global-market-data, global-stock-screener (logic
            block byte-identical; only the data table's formatting differed).

computed    5 market groups, holidays *computed* rather than tabled (Easter
            algorithm + fixed dates + a curated movable list), pandas-based, and
            it accepts exchange aliases (NSE, NYSE, XETRA...). Returns a
            DatetimeIndex from trading_days(market, start, end) — a different
            shape from the other two. Also carries should_run_today().
            Extracted from: BazaarTalks, global-market-scanners (byte-identical).

`markets` and `computed` are NOT interchangeable: they disagree on vocabulary
("IN" vs "India") and on method (table vs computed), so they can return different
answers for the same day. Migrating a caller from one to the other is a
behaviour change and needs its own test, not a find-and-replace.

Equivalence with the originals is enforced by tests/test_equivalence.py, which
imports every original copy still on disk and asserts identical results.
"""

__all__ = ["india_live", "markets", "computed"]
__version__ = "0.1.0"
