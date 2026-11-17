# market_tiers.py
# ================
# Priority tiers for the scan/analysis cadence across every market this
# platform touches. User-set 2026-07-31:
#   Tier 1 (daily, highest priority): India, US
#   Tier 2 (daily): Europe, Japan, Korea
#   Tier 3 (weekly): everything else
#
# Tier 1/2 markets already run daily via daily_mailer.sh/daily_research.sh's
# existing full_{us,indian,european,japan,korea}_*.py scan scripts — nothing
# in this module changes that. What Tier 1/2 lacked was never scan cadence,
# it was market-agnostic infrastructure (see [[project_intl_pit_and_ticker_reference]]).
#
# Tier 3 is exactly screener_kit.MARKETS minus what's already Tier 1/2 —
# screener_kit.py already has real, working seed OHLCV + kit.update()/
# kit.screen() for every one of these markets (confirmed live 2026-07-31:
# all 20 declared markets have real cached data, ~4-5 weeks stale, ready
# for a weekly refresh) — weekly_extended_scan.py is the thin wiring that
# runs it on a schedule and writes results where market_ingest.py's
# existing ticker_freshness view already knows how to find them.

from __future__ import annotations

TIER1 = ["IN", "US"]
TIER2 = ["EU", "JP", "KR"]

try:
    import screener_kit as _kit
    TIER3 = sorted(set(_kit.MARKETS) - set(TIER1) - set(TIER2))
except Exception:
    # screener_kit unavailable at import time (e.g. missing deps under a
    # bare interpreter) — fall back to the same list without importing it.
    TIER3 = sorted({"CN", "SG", "HK", "TW", "CA", "AU", "UK", "DE", "SA",
                     "BR", "CH", "ZA", "SE", "FI", "DK"})

ALL_TIERS = {1: TIER1, 2: TIER2, 3: TIER3}
CADENCE = {1: "daily", 2: "daily", 3: "weekly"}


def tier_of(market: str) -> int:
    m = market.upper()
    for t, markets in ALL_TIERS.items():
        if m in markets:
            return t
    return 3  # unknown markets default to lowest-priority cadence, not silently dropped


def cadence_of(market: str) -> str:
    return CADENCE[tier_of(market)]


if __name__ == "__main__":
    for t in (1, 2, 3):
        print(f"Tier {t} ({CADENCE[t]}): {', '.join(ALL_TIERS[t])}")
