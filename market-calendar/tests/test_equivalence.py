"""
Prove the extracted package is behaviourally identical to every copy it replaces.

Each original is loaded straight from its repo path by file location, so these
tests compare against the real files still in use, not a transcription of them.
A repo that is absent is skipped, never silently passed.

Network: none. india_live.get_holidays() would hit nsepython, so every test
passes an explicit holiday set or compares the hardcoded fallback directly.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys

import pytest

HOME = pathlib.Path.home()
PKG = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(PKG))

from market_calendar_core import computed, india_live, markets  # noqa: E402

# --- the originals, by family -------------------------------------------------
FAMILY_A = {  # market_calendar.py — India live
    "market-pipeline": HOME / "market-pipeline/code/python_files/market_calendar.py",
    "global-market-data": HOME / "repos/global-market-data/market_calendar.py",
    "global-stock-screener": HOME / "repos/global-stock-screener/market_calendar.py",
}
FAMILY_B2 = {  # market_holidays.py — table-driven, ISO codes
    "global-market-data": HOME / "repos/global-market-data/market_holidays.py",
    "global-stock-screener": HOME / "repos/global-stock-screener/market_holidays.py",
}
FAMILY_B1 = {  # market_holidays.py — computed, word vocabulary
    "BazaarTalks": HOME / "BazaarTalks/market_holidays.py",
    "global-market-scanners": HOME / "repos/global-market-scanners/market_holidays.py",
}

DAYS = [dt.date(2025, 1, 1) + dt.timedelta(days=i) for i in range(730)]


def _load(name: str, path: pathlib.Path):
    """Import an original copy by file path under a unique module name."""
    if not path.exists():
        pytest.skip(f"{path} not on disk")
    spec = importlib.util.spec_from_file_location(f"_orig_{name}_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- Family A
@pytest.mark.parametrize("repo,path", sorted(FAMILY_A.items()))
def test_india_fallback_identical(repo, path):
    """The hardcoded fallback holiday set must match exactly — it is what the
    pipeline falls back to when the live NSE call fails, so a drift here is a
    silently wrong trading calendar."""
    orig = _load(repo, path)
    assert orig._FALLBACK == india_live._FALLBACK, f"{repo} fallback drifted"


@pytest.mark.parametrize("repo,path", sorted(FAMILY_A.items()))
def test_india_is_trading_day_identical(repo, path):
    orig = _load(repo, path)
    hol = india_live._FALLBACK
    mine = [india_live.is_trading_day(d, hol) for d in DAYS]
    theirs = [orig.is_trading_day(d, hol) for d in DAYS]
    assert mine == theirs, f"{repo} disagrees on {sum(a!=b for a,b in zip(mine,theirs))} days"


@pytest.mark.parametrize("repo,path", sorted(FAMILY_A.items()))
def test_india_parse_identical(repo, path):
    orig = _load(repo, path)
    for s in ("15-Jan-2026", "2026-01-15", "15-January-2026", "  2026-03-21 ", "junk"):
        assert orig._parse(s) == india_live._parse(s), f"{repo} _parse({s!r})"


# ---------------------------------------------------------------- Family B2
@pytest.mark.parametrize("repo,path", sorted(FAMILY_B2.items()))
def test_markets_tables_identical(repo, path):
    orig = _load(repo, path)
    assert orig._WEEKEND == markets._WEEKEND, f"{repo} weekend rules drifted"
    assert orig._HOLIDAYS == markets._HOLIDAYS, f"{repo} holiday tables drifted"


@pytest.mark.parametrize("repo,path", sorted(FAMILY_B2.items()))
def test_markets_is_trading_day_identical(repo, path):
    orig = _load(repo, path)
    # every market EXCEPT IN, which delegates to the live NSE fetch
    for m in sorted(set(markets._HOLIDAYS) | set(markets._WEEKEND)):
        if m == "IN":
            continue
        mine = [markets.is_trading_day(m, d) for d in DAYS]
        theirs = [orig.is_trading_day(m, d) for d in DAYS]
        assert mine == theirs, f"{repo}/{m} disagrees"


@pytest.mark.parametrize("repo,path", sorted(FAMILY_B2.items()))
def test_markets_next_and_last_identical(repo, path):
    orig = _load(repo, path)
    probes = [dt.date(2025, 12, 24), dt.date(2026, 1, 1), dt.date(2026, 5, 1)]
    for m in ("US", "JP", "SA", "DE"):
        for d in probes:
            assert markets.next_trading_day(m, d) == orig.next_trading_day(m, d)
            assert markets.last_trading_day(m, d) == orig.last_trading_day(m, d)


def test_markets_saudi_weekend_is_not_the_default():
    """Guards the one genuinely market-specific rule in the table."""
    assert markets.weekend("SA") == {4, 5}
    assert markets.weekend("US") == {5, 6}
    assert markets.is_trading_day("SA", dt.date(2026, 1, 4)) is True   # Sunday
    assert markets.is_trading_day("US", dt.date(2026, 1, 4)) is False


# ---------------------------------------------------------------- Family B1
@pytest.mark.parametrize("repo,path", sorted(FAMILY_B1.items()))
def test_computed_is_trading_day_identical(repo, path):
    orig = _load(repo, path)
    for m in ("US", "India", "Japan", "Korea", "Europe", "NSE", "NYSE", "XETRA"):
        mine = [computed.is_trading_day(m, d) for d in DAYS]
        theirs = [orig.is_trading_day(m, d) for d in DAYS]
        assert mine == theirs, f"{repo}/{m} disagrees"


@pytest.mark.parametrize("repo,path", sorted(FAMILY_B1.items()))
def test_computed_trading_days_identical(repo, path):
    orig = _load(repo, path)
    for m in ("US", "India", "Europe"):
        assert list(computed.trading_days(m, "2026-01-01", "2026-12-31")) == \
               list(orig.trading_days(m, "2026-01-01", "2026-12-31")), m


def test_computed_easter_known_values():
    """Easter drives every European movable closure; pin it to known dates."""
    assert computed._easter(2025) == dt.date(2025, 4, 20)
    assert computed._easter(2026) == dt.date(2026, 4, 5)


# ------------------------------------------------- the incompatibility itself
def test_the_three_families_are_not_interchangeable():
    """This is the reason the package exports nothing at top level. If these ever
    become compatible the assertion fails and the docstring needs rewriting."""
    import inspect
    a = list(inspect.signature(india_live.is_trading_day).parameters)
    b = list(inspect.signature(markets.is_trading_day).parameters)
    c = list(inspect.signature(computed.is_trading_day).parameters)
    assert a == ["d", "holidays"]
    assert b == ["market", "d", "hol"]
    assert c == ["market", "d"]
    assert a != b and b != c

    # and they disagree on vocabulary: markets speaks ISO, computed speaks words
    assert markets.holidays("India") == set()      # unknown key -> empty
    assert computed._canon("NSE") == "India"
