"""Regression tests for findings of the 2026-10-25 static-analysis sweep.

Each test failed on the code it was written against (ruff F821 / import-smoke)
and demonstrates the user-visible wrong behaviour, not just the lint hit.
"""
import importlib
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
STOCK_SCREENER = ROOT / "stock-screener"


@pytest.fixture
def stock_screener_path():
    sys.path.insert(0, str(STOCK_SCREENER))
    try:
        yield
    finally:
        sys.path.remove(str(STOCK_SCREENER))


# ── screener_extended_filters.py:1043  F821 undefined name `Path` ──────────
def test_screener_extended_filters_main_writes_index(tmp_path, monkeypatch, capsys):
    """`main()` used `Path.home()` eight lines before `from pathlib import Path`
    was executed, so running the script as documented died with a NameError
    *after* printing the whole report and never wrote screener_filters_index.json."""
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    mod = importlib.import_module("screener_extended_filters")

    mod.main()  # raised NameError: name 'Path' is not defined

    out = tmp_path / "screener_filters_index.json"
    assert out.exists()
    import json
    data = json.loads(out.read_text())
    assert data["total_screens"] == len(mod.SCREENER_CRITERIA) + len(mod.COMPOSITE_SCREENS)


# ── stock-screener/modern_resilience_scorer.py:152  F821 undefined `industry` ─
@pytest.mark.parametrize(
    "info, expected",
    [
        # Healthcare: pricing_power_sector 0.85, no revenue -> resilience 0.5
        ({"sector": "Healthcare", "totalRevenue": 0}, (0.85 + 0.5) / 2),
        # Luxury industry branch: 0.90, no revenue -> 0.5
        ({"sector": "Consumer Cyclical", "industry": "Luxury Goods", "totalRevenue": 0}, (0.90 + 0.5) / 2),
        # Technology with healthy margin: 0.65 + 0.80
        ({"sector": "Technology", "totalRevenue": 1e9, "profitMargins": 0.15}, (0.65 + 0.80) / 2),
        # yfinance reports the sector as "Utilities", but the code tests
        # `'utility' in sector.lower()` which is NOT a substring match, so the
        # 0.80 branch is unreachable for real data. Modelling slip, recorded as
        # suspected in triage.json rather than silently "fixed" here.
        pytest.param(
            {"sector": "Utilities", "totalRevenue": 1e9, "profitMargins": 0.15}, (0.80 + 0.80) / 2,
            marks=pytest.mark.xfail(strict=True, reason="'utility' never matches sector 'Utilities'"),
        ),
    ],
)
def test_pricing_power_scores_non_energy_sectors(stock_screener_path, info, expected):
    """For every sector except Energy the method hit `industry.lower()` on an
    undefined name, the bare `except Exception` swallowed the NameError and
    every stock silently got the neutral 0.5 — the sector logic never ran."""
    mod = importlib.import_module("modern_resilience_scorer")
    scorer = mod.ModernResilienceScorer("TEST")
    scorer.info = info
    assert scorer.calculate_pricing_power() == pytest.approx(expected)


def test_pricing_power_without_industry_key(stock_screener_path):
    """yfinance `.info` often lacks `industry`; a missing key must not fall back to 0.5."""
    mod = importlib.import_module("modern_resilience_scorer")
    scorer = mod.ModernResilienceScorer("TEST")
    scorer.info = {"sector": "Financial Services", "totalRevenue": 0}
    assert scorer.calculate_pricing_power() == pytest.approx((0.75 + 0.5) / 2)


# ── import smoke: psycopg2 / folium imported but not declared ───────────────
def _declared_requirements() -> set[str]:
    names = set()
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        names.add(re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0].lower().replace("_", "-"))
    return names


def _third_party_imports(paths) -> set[str]:
    found = set()
    pat = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
    for p in paths:
        found.update(pat.findall(p.read_text(errors="ignore")))
    return found


def test_scripts_db_and_map_imports_are_declared():
    """scripts/nse_index_*.py, scripts/amfi_nav_collect.py and
    api-data-integration/*map*.py import psycopg2 / folium, which
    requirements.txt did not list, so a fresh `pip install -r requirements.txt`
    venv cannot import them (import-smoke: ModuleNotFoundError)."""
    imports = _third_party_imports(
        list((ROOT / "scripts").glob("nse_index_*.py"))
        + [ROOT / "scripts" / "amfi_nav_collect.py"]
        + list((ROOT / "api-data-integration").glob("*map*.py"))
    )
    assert "psycopg2" in imports and "folium" in imports  # guard: the scripts still use them
    declared = _declared_requirements()
    assert declared & {"psycopg2", "psycopg2-binary", "psycopg"}, "psycopg2 not in requirements.txt"
    assert "folium" in declared, "folium not in requirements.txt"
