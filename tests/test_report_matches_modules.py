"""
Guard against the published report drifting away from the code.

research/diaspora/report/salary-to-savings.html carries its figures as
hardcoded literals — it is a static page, not a template rendered at build
time. That is fine until someone changes a parameter in the modules and the
report silently keeps showing the old numbers while looking authoritative.

These tests parse the figures back out of the HTML and check them against what
the modules produce today. If they fail, the report needs regenerating, not the
test relaxing.

Run:
    python -m pytest tests/test_report_matches_modules.py -v
"""

import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "research", "diaspora"))

from gulf_wage_model import blended_wage  # noqa: E402,F401
from real_savings_ranking import build_frame  # noqa: E402
from us_debt_service import scenarios  # noqa: E402

REPORT = os.path.join(ROOT, "research", "diaspora", "report", "salary-to-savings.html")

CASE_RE = re.compile(
    r'c:"(?P<c>[^"]+)",sub:"(?P<sub>[^"]+)",gross:(?P<gross>\d+),'
    r'tax:(?P<tax>\d+),debt:(?P<debt>\d+),fee:(?P<fee>\d+),land:(?P<land>\d+)'
)
BASKET = 28000


@pytest.fixture(scope="module")
def html():
    with open(REPORT, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def cases(html):
    out = [m.groupdict() for m in CASE_RE.finditer(html)]
    for c in out:
        for k in ("gross", "tax", "debt", "fee", "land"):
            c[k] = int(c[k])
    assert out, "no waterfall cases parsed — the data block's shape changed"
    return out


def test_the_report_exists_and_is_self_contained(html):
    assert "<title>" in html
    # Google Fonts is the one external host the artifact CSP allows.
    hosts = set(re.findall(r'https?://([a-z0-9.-]+)', html))
    allowed = {"fonts.googleapis.com", "fonts.gstatic.com", "claude.ai"}
    assert hosts <= allowed, f"unexpected external host(s): {hosts - allowed}"


def test_every_waterfall_reconciles(cases):
    """gross - tax - basket - debt - fee must equal what lands. This is pure
    internal arithmetic and must hold exactly."""
    for c in cases:
        got = c["gross"] - c["tax"] - BASKET - c["debt"] - c["fee"]
        assert got == c["land"], f"{c['c']} ({c['sub']}) is off by {got - c['land']}"


def test_gross_and_tax_match_the_savings_model(cases):
    d = build_frame(BASKET).set_index("country")
    for c in cases:
        row = d.loc[c["c"]]
        assert c["gross"] == int(row.wage_ppp_usd), c["c"]
        expected_tax = round(float(row.wage_ppp_usd) - float(row.net_wage_ppp_usd))
        assert abs(c["tax"] - expected_tax) <= 1, f"{c['c']}: tax drifted"


def test_debt_free_cases_match_the_landed_savings_figure(cases):
    d = build_frame(BASKET).set_index("country")
    for c in cases:
        if c["debt"]:
            continue
        assert abs(c["land"] - int(d.loc[c["c"], "savings_landed_india_usd"])) <= 1, c["c"]


def test_us_debt_cases_match_the_debt_module(cases):
    sc = scenarios(87.0).set_index("scenario")
    mapping = {
        "student loan + used car": "US student loan + used car",
        "Indian education loan + new car": "Indian education loan + new car",
    }
    checked = 0
    for c in cases:
        key = mapping.get(c["sub"])
        if key is None:
            continue
        assert abs(c["land"] - int(sc.loc[key, "lands_in_india_usd_yr"])) <= 1, c["sub"]
        assert abs(c["debt"] - int(sc.loc[key, "debt_service_usd_yr"])) <= 1, c["sub"]
        checked += 1
    assert checked == len(mapping), "the US debt cases went missing from the report"


def test_headline_figures_in_the_prose_match_the_model(html):
    """The tiles and tables quote numbers in text. Spot-check the load-bearing
    ones so prose and charts cannot disagree."""
    d = build_frame(BASKET).set_index("country")
    us = int(d.loc["United States", "savings_landed_india_usd"])
    jp = int(d.loc["Japan", "savings_landed_india_usd"])
    assert f"${us:,}" in html, "the US headline figure is stale"
    assert f"${jp:,}" in html, "the Japan headline figure is stale"


def test_india_inflation_figures_in_the_report_match_mospi(html):
    from real_savings_ranking import INDIA_CPI, INDIA_WPI_YOY

    assert f"{INDIA_CPI['CPI (General)']:.2f}%" in html
    assert f"{INDIA_WPI_YOY:.2f}%" in html


def test_the_basket_quoted_in_the_report_is_the_one_the_model_uses(html, cases):
    assert "US$28,000" in html or "$28,000" in html
    d = build_frame(BASKET).set_index("country")
    row = d.loc["Netherlands"]
    implied = float(row.net_wage_ppp_usd) - float(row.savings_ppp_usd)
    assert round(implied) == BASKET


def test_the_salaried_scope_limit_is_stated_in_the_report(html):
    """The report is a salaried-worker model and must say so, not imply it."""
    assert "salaried</em> migrants throughout" in html or "salaried" in html
    assert "salaried-worker rankings" in html.lower() or "salaried-worker" in html


def test_the_gulf_business_decomposition_matches_the_module(html):
    """The report quotes the implied business remittance at three owner shares.
    They must match what salaried_vs_business computes."""
    import re

    from salaried_vs_business import gulf_decomposition

    d = gulf_decomposition()
    d = d[d.salaried_remit_rate == "40%"].set_index("business_owner_share")
    quoted = {int(m) for m in re.findall(r'\{l:"\d+% own businesses",v:(\d+)\}', html)}
    assert quoted, "the split-chart data block's shape changed"
    for share in ("3%", "5%", "10%"):
        expected = int(d.loc[share, "implied_business_remit_usd_yr"])
        assert expected in quoted, f"{share} owner share: report says {quoted}, module says {expected}"


def test_the_us_payroll_contrast_is_quoted_correctly(html):
    from salaried_vs_business import US_TAX_MECHANICS

    assert f"{US_TAX_MECHANICS['self_employment_pct']}%" in html
    assert f"{US_TAX_MECHANICS['employee_fica_pct']}%" in html


def test_the_gulf_wage_anchor_in_the_report_matches_the_ilo_model(html):
    from gulf_wage_model import blended_wage

    central = int(blended_wage().set_index("scenario").blended_indian_migrant_usd_yr["central"])
    assert f"{central:,}" in html, "the Gulf blended wage quoted in the report is stale"
