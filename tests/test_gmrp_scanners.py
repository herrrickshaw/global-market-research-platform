"""Offline tests for backend/scanners/{darvas,piotroski,coffee_can}.py and backend/column_map.py.

The scanners import ``column_map`` and ``damodaran`` as top-level modules.
``damodaran`` needs xlrd and Excel files, so it is replaced by a fake whose
sector PE is controllable per test.
"""
import math
import sys

import numpy as np
import pandas as pd
import pytest

import gmrp_helpers as H


@pytest.fixture()
def mods(monkeypatch):
    sector_pe = {}
    fake_dam = H.fake_module("damodaran", get_sector_pe=lambda s: sector_pe.get(s))
    monkeypatch.setitem(sys.modules, "damodaran", fake_dam)
    cm = H.load("column_map", "backend", "column_map.py")
    monkeypatch.setitem(sys.modules, "column_map", cm)
    ns = type("NS", (), {})()
    ns.cm = cm
    ns.sector_pe = sector_pe
    for n in ("darvas", "piotroski", "coffee_can"):
        m = H.load("gmrp_" + n, "backend", "scanners", n + ".py")
        monkeypatch.setitem(sys.modules, "gmrp_" + n, m)
        setattr(ns, n, m)
    yield ns
    for n in ("column_map", "gmrp_darvas", "gmrp_piotroski", "gmrp_coffee_can"):
        sys.modules.pop(n, None)


def row(**kw):
    return pd.Series(kw, dtype=object)


# ── column_map ───────────────────────────────────────────────────────────────

def test_normalize_columns_renames_and_coerces(mods):
    df = pd.DataFrame({
        "Name": ["A", "B"],
        "ROE %": ["1,234.5", "12%"],
        "Debt to equity": [" 0.4 ", "bad"],
        "Unrelated": ["x", "y"],
    })
    out = mods.cm.normalize_columns(df)
    assert list(out.columns) == ["name", "roe", "debt_to_equity", "Unrelated"]
    assert out["roe"].tolist() == [1234.5, 12.0]
    assert out["debt_to_equity"].iloc[0] == 0.4
    assert math.isnan(out["debt_to_equity"].iloc[1])
    # non-canonical column untouched; name column not coerced
    assert out["Unrelated"].tolist() == ["x", "y"]
    assert out["name"].tolist() == ["A", "B"]
    # input not mutated
    assert "ROE %" in df.columns


def test_normalize_columns_first_alias_wins_and_case_insensitive(mods):
    df = pd.DataFrame({"CMP Rs.": [1], "price": [2]})
    out = mods.cm.normalize_columns(df)
    # 'CMP Rs.' is the first alias of cmp; 'price' (alias 'Price') must not also map to cmp
    assert out["cmp"].tolist() == [1]
    assert "price" in out.columns


def test_normalize_columns_does_not_map_one_source_twice(mods):
    # 'Sector' is an alias of sector; a second column with alias of the same canonical is left alone
    df = pd.DataFrame({"Sector": ["a"], "Industry": ["b"]})
    out = mods.cm.normalize_columns(df)
    assert out["sector"].tolist() == ["a"]
    assert out["Industry"].tolist() == ["b"]


def test_completeness(mods):
    r = pd.Series({"a": 1, "b": np.nan, "c": 3})
    assert mods.cm.completeness(r, ["a", "b", "c", "d"]) == 50.0
    assert mods.cm.completeness(r, ["a", "b", "c"]) == 66.7
    assert mods.cm.completeness(r, []) == 100.0
    assert mods.cm.completeness(r, ["a"]) == 100.0


def test_sanitize_result(mods):
    res = mods.cm.sanitize_result({
        "a": float("nan"), "b": float("inf"), "c": -float("inf"), "d": 1.5,
        "e": np.float64(2.5), "f": np.int64(3), "g": "s", "h": None,
        "nested": {"x": float("nan"), "y": np.bool_(True)},
    })
    assert res["a"] is None and res["b"] is None and res["c"] is None
    assert res["d"] == 1.5
    assert res["e"] == 2.5 and type(res["e"]) is float
    assert res["f"] == 3 and type(res["f"]) is int
    assert res["g"] == "s" and res["h"] is None
    assert res["nested"]["x"] is None
    assert res["nested"]["y"] is True


# ── darvas ───────────────────────────────────────────────────────────────────

def _darvas_full(**over):
    base = dict(cmp=97.0, high_52w=100.0, low_52w=50.0, volume=150, volume_30d_avg=100,
                roe=16, net_profit_margin=11, debt_to_equity=0.4, promoter_holding=51,
                eps_growth_5y=11, pe=20, sector="x", sector_pe=20, name="N", ticker="T")
    base.update(over)
    return row(**base)


def test_darvas_all_pass_is_buy_10(mods):
    r = mods.darvas._score(_darvas_full())
    assert r["score"] == 10 and r["max_score"] == 10 and r["signal"] == "BUY"
    assert all(v is True for v in r["criteria"].values())
    assert r["name"] == "N" and r["ticker"] == "T"


def test_darvas_near_high_boundary(mods):
    # exactly 3% below high passes (<=); just beyond fails
    assert mods.darvas._score(_darvas_full(cmp=97.0))["criteria"]["price_near_52w_high"] is True
    assert mods.darvas._score(_darvas_full(cmp=96.9))["criteria"]["price_near_52w_high"] is False


def test_darvas_volume_boundary_inclusive(mods):
    assert mods.darvas._score(_darvas_full(volume=150, volume_30d_avg=100))["criteria"]["volume_breakout"] is True
    assert mods.darvas._score(_darvas_full(volume=149, volume_30d_avg=100))["criteria"]["volume_breakout"] is False
    assert mods.darvas._score(_darvas_full(volume_30d_avg=0))["criteria"]["volume_breakout"] is None


def test_darvas_box_floor_boundary_inclusive(mods):
    assert mods.darvas._score(_darvas_full(cmp=85.0))["criteria"]["above_box_floor"] is True
    assert mods.darvas._score(_darvas_full(cmp=84.9))["criteria"]["above_box_floor"] is False


def test_darvas_strict_thresholds(mods):
    c = lambda **k: mods.darvas._score(_darvas_full(**k))["criteria"]  # noqa: E731
    assert c(roe=15)["roe_gt_15"] is False and c(roe=15.1)["roe_gt_15"] is True
    assert c(net_profit_margin=10)["profit_margin_gt_10"] is False
    assert c(net_profit_margin=10.1)["profit_margin_gt_10"] is True
    assert c(debt_to_equity=0.5)["low_debt"] is False and c(debt_to_equity=0.49)["low_debt"] is True
    assert c(promoter_holding=50)["promoter_holding_gt_50"] is False
    assert c(promoter_holding=50.1)["promoter_holding_gt_50"] is True
    assert c(eps_growth_5y=10)["eps_growth_gt_10"] is False
    assert c(eps_growth_5y=10.1)["eps_growth_gt_10"] is True


def test_darvas_margin_falls_back_to_opm(mods):
    r = _darvas_full(net_profit_margin=np.nan, opm=12)
    assert mods.darvas._score(r)["criteria"]["profit_margin_gt_10"] is True
    r = _darvas_full(net_profit_margin=np.nan, opm=np.nan)
    assert mods.darvas._score(r)["criteria"]["profit_margin_gt_10"] is None


def test_darvas_growth_fallback_chain_with_missing_keys(mods):
    # fallback works when the primary key is absent (Series.get -> None)
    r = _darvas_full(profit_growth_5y=11)
    r = r.drop("eps_growth_5y")
    assert mods.darvas._score(r)["criteria"]["eps_growth_gt_10"] is True
    r = _darvas_full().drop("eps_growth_5y")
    r["profit_growth_3y"] = 11
    assert mods.darvas._score(r)["criteria"]["eps_growth_gt_10"] is True
    r = _darvas_full(eps_growth_5y=np.nan)
    assert mods.darvas._score(r)["criteria"]["eps_growth_gt_10"] is None


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="darvas.py `a or b or c`: NaN is truthy, so a NaN eps_growth_5y (how "
                          "every missing DataFrame cell looks) never falls back to profit_growth_5y")
def test_darvas_growth_fallback_on_nan_primary(mods):
    r = _darvas_full(eps_growth_5y=np.nan, profit_growth_5y=11)
    assert mods.darvas._score(r)["criteria"]["eps_growth_gt_10"] is True


def test_darvas_pe_uses_damodaran_then_row_then_absolute(mods):
    # Damodaran sector PE wins over the row's sector_pe: 1.5 * 10 = 15
    mods.sector_pe["x"] = 10
    assert mods.darvas._score(_darvas_full(pe=14.9, sector_pe=100))["criteria"]["pe_vs_sector"] is True
    assert mods.darvas._score(_darvas_full(pe=15.0, sector_pe=100))["criteria"]["pe_vs_sector"] is False
    # no Damodaran value -> row sector_pe
    mods.sector_pe.clear()
    assert mods.darvas._score(_darvas_full(pe=29.9, sector_pe=20))["criteria"]["pe_vs_sector"] is True
    assert mods.darvas._score(_darvas_full(pe=30.0, sector_pe=20))["criteria"]["pe_vs_sector"] is False
    # neither -> absolute 35
    r = _darvas_full(sector_pe=np.nan, pe=34.9)
    assert mods.darvas._score(r)["criteria"]["pe_vs_sector"] is True
    r = _darvas_full(sector_pe=np.nan, pe=35)
    assert mods.darvas._score(r)["criteria"]["pe_vs_sector"] is False
    # sector_pe of 0 is treated as unavailable
    r = _darvas_full(sector_pe=0, pe=34)
    assert mods.darvas._score(r)["criteria"]["pe_vs_sector"] is True
    # no pe at all
    assert mods.darvas._score(_darvas_full(pe=np.nan))["criteria"]["pe_vs_sector"] is None


def test_darvas_price_strength_boundary_and_degenerate_range(mods):
    # (cmp-l52)/(h52-l52) strictly > 0.5
    assert mods.darvas._score(_darvas_full(cmp=75.0))["criteria"]["price_strength"] is False
    assert mods.darvas._score(_darvas_full(cmp=75.1))["criteria"]["price_strength"] is True
    assert mods.darvas._score(_darvas_full(high_52w=50.0, low_52w=50.0))["criteria"]["price_strength"] is None
    assert mods.darvas._score(_darvas_full(low_52w=np.nan))["criteria"]["price_strength"] is None


def test_darvas_nonpositive_high_disables_price_checks(mods):
    c = mods.darvas._score(_darvas_full(high_52w=0))["criteria"]
    assert c["price_near_52w_high"] is None and c["above_box_floor"] is None


def test_darvas_signal_thresholds(mods):
    # build rows hitting exactly 4, 3, 7, 6 passing criteria via the all-pass base
    def score_with(fails):
        base = _darvas_full()
        for k, v in fails.items():
            base[k] = v
        return mods.darvas._score(base)
    seven = score_with(dict(roe=1, debt_to_equity=2, promoter_holding=1))
    assert seven["score"] == 7 and seven["signal"] == "BUY"
    six = score_with(dict(roe=1, debt_to_equity=2, promoter_holding=1, eps_growth_5y=1))
    assert six["score"] == 6 and six["signal"] == "WATCH"
    four = score_with(dict(roe=1, debt_to_equity=2, promoter_holding=1, eps_growth_5y=1,
                           net_profit_margin=1, pe=99))
    assert four["score"] == 4 and four["signal"] == "WATCH"
    three = score_with(dict(roe=1, debt_to_equity=2, promoter_holding=1, eps_growth_5y=1,
                            net_profit_margin=1, pe=99, volume=1))
    assert three["score"] == 3 and three["signal"] == "AVOID"


def test_darvas_empty_row_all_none_avoid_and_scan_sanitizes(mods):
    out = mods.darvas.scan(pd.DataFrame([{"name": "Z"}]))
    assert len(out) == 1
    r = out[0]
    assert r["score"] == 0 and r["signal"] == "AVOID"
    assert r["completeness"] == 0.0
    assert r["cmp"] is None  # NaN/None sanitised, never NaN
    assert set(r["criteria"].values()) == {None}


def test_darvas_scan_empty_frame(mods):
    assert mods.darvas.scan(pd.DataFrame()) == []


def test_darvas_scan_sanitizes_nan_outputs(mods):
    df = pd.DataFrame([{"cmp": 100.0, "high_52w": 100.0, "low_52w": 0.0, "roe": np.nan}])
    r = mods.darvas.scan(df)[0]
    assert r["roe"] is None
    assert r["cmp"] == 100.0


# ── piotroski ────────────────────────────────────────────────────────────────

def test_piotroski_all_computable_pass(mods):
    r = mods.piotroski._score(row(roa=5, ocf=20, total_assets=100, debt_to_equity=0.4,
                                  current_ratio=2, opm=25, asset_turnover=0.6))
    # F3 and F7 are never computable -> max reachable is 7
    assert r["score"] == 7 and r["signal"] == "WATCH"
    assert r["criteria"]["F3_roa_improving"] is None and r["criteria"]["F7_no_dilution"] is None
    assert r["max_score"] == 9 and r["used_precomputed"] is False


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="piotroski.py `opm or net_profit_margin`: NaN opm is truthy so the "
                          "net-margin fallback is skipped")
def test_piotroski_margin_fallback_on_nan_opm(mods):
    r = mods.piotroski._score(row(opm=np.nan, net_profit_margin=25))
    assert r["criteria"]["F8_operating_margin"] is True


def test_piotroski_roa_derived_from_profit_and_assets(mods):
    r = mods.piotroski._score(row(net_profit=10, total_assets=200))
    assert r["criteria"]["F1_roa_positive"] is True
    r = mods.piotroski._score(row(net_profit=-10, total_assets=200))
    assert r["criteria"]["F1_roa_positive"] is False
    # zero assets: no division, ROA stays unknown
    r = mods.piotroski._score(row(net_profit=10, total_assets=0))
    assert r["criteria"]["F1_roa_positive"] is None
    # explicit roa takes precedence over derivation
    r = mods.piotroski._score(row(roa=-1, net_profit=10, total_assets=200))
    assert r["criteria"]["F1_roa_positive"] is False


def test_piotroski_accruals_strict_and_requires_positive_assets(mods):
    base = dict(roa=5, ocf=5, total_assets=100)
    assert mods.piotroski._score(row(**base))["criteria"]["F4_low_accruals"] is False  # 5 > 5 false
    assert mods.piotroski._score(row(roa=5, ocf=5.1, total_assets=100))["criteria"]["F4_low_accruals"] is True
    assert mods.piotroski._score(row(roa=5, ocf=9, total_assets=0))["criteria"]["F4_low_accruals"] is None
    assert mods.piotroski._score(row(roa=5, ocf=9, total_assets=-1))["criteria"]["F4_low_accruals"] is None


def test_piotroski_strict_thresholds(mods):
    c = lambda **k: mods.piotroski._score(row(**k))["criteria"]  # noqa: E731
    assert c(ocf=0)["F2_ocf_positive"] is False and c(ocf=0.1)["F2_ocf_positive"] is True
    assert c(debt_to_equity=0.5)["F5_low_leverage"] is False
    assert c(debt_to_equity=0.49)["F5_low_leverage"] is True
    assert c(current_ratio=1.5)["F6_current_ratio"] is False
    assert c(current_ratio=1.51)["F6_current_ratio"] is True
    assert c(opm=20)["F8_operating_margin"] is False and c(opm=20.1)["F8_operating_margin"] is True
    assert c(asset_turnover=0.5)["F9_asset_turnover"] is False
    assert c(asset_turnover=0.51)["F9_asset_turnover"] is True


def test_piotroski_opm_falls_back_to_net_margin_and_roe_for_turnover(mods):
    assert mods.piotroski._score(row(net_profit_margin=25))["criteria"]["F8_operating_margin"] is True
    assert mods.piotroski._score(row(roe=16))["criteria"]["F9_asset_turnover"] is True
    assert mods.piotroski._score(row(roe=15))["criteria"]["F9_asset_turnover"] is False
    # turnover present => ROE ignored
    assert mods.piotroski._score(row(asset_turnover=0.1, roe=99))["criteria"]["F9_asset_turnover"] is False


def test_piotroski_precomputed_score_used_and_signal_boundaries(mods):
    for sc, sig in [(8, "BUY"), (9, "BUY"), (7, "WATCH"), (6, "WATCH"), (5, "AVOID"), (0, "AVOID")]:
        r = mods.piotroski._score(row(piotroski_score=sc))
        assert r["score"] == sc and r["signal"] == sig, sc
        assert r["used_precomputed"] is True
        assert "_note" in r["criteria"]


def test_piotroski_scan_handles_empty_and_nan(mods):
    assert mods.piotroski.scan(pd.DataFrame()) == []
    out = mods.piotroski.scan(pd.DataFrame([{"name": "q", "piotroski_score": 7.0}]))
    assert out[0]["score"] == 7 and isinstance(out[0]["score"], int)
    assert out[0]["cmp"] is None


# ── coffee can ───────────────────────────────────────────────────────────────

def _cc(**over):
    base = dict(sales_growth_10y=11, profit_growth_10y=11, roce=16, debt_to_equity=0.9,
                promoter_pledge=9, market_cap=101)
    base.update(over)
    return row(**base)


def test_coffee_can_all_pass_buy(mods):
    r = mods.coffee_can._score(_cc())
    assert r["signal"] == "BUY" and r["passed"] is True and r["score"] == 1
    assert all(v is True for v in r["criteria"].values())


def test_coffee_can_strict_thresholds(mods):
    c = lambda **k: mods.coffee_can._score(_cc(**k))["criteria"]  # noqa: E731
    assert c(sales_growth_10y=10)["revenue_cagr_gt_10"] is False
    assert c(profit_growth_10y=10)["profit_cagr_gt_10"] is False
    assert c(roce=15)["roce_gt_15"] is False
    assert c(debt_to_equity=1)["de_lt_1"] is False and c(debt_to_equity=0.99)["de_lt_1"] is True
    assert c(promoter_pledge=10)["low_promoter_pledge"] is False
    assert c(promoter_pledge=9.9)["low_promoter_pledge"] is True
    assert c(market_cap=100)["min_market_cap"] is False


def test_coffee_can_growth_fallback_chain_with_missing_keys(mods):
    r = _cc().drop("sales_growth_10y")
    r["sales_growth_5y"] = 12
    assert mods.coffee_can._score(r)["criteria"]["revenue_cagr_gt_10"] is True
    r = _cc().drop("sales_growth_10y")
    r["sales_growth_3y"] = 12
    assert mods.coffee_can._score(r)["criteria"]["revenue_cagr_gt_10"] is True
    r = _cc().drop("profit_growth_10y")
    r["profit_growth_3y"] = 12
    assert mods.coffee_can._score(r)["criteria"]["profit_cagr_gt_10"] is True
    r = _cc(sales_growth_10y=np.nan)
    assert mods.coffee_can._score(r)["criteria"]["revenue_cagr_gt_10"] is None


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="coffee_can.py `a or b or c`: NaN is truthy, so a NaN 10y growth blocks "
                          "the documented 10Y -> 5Y -> 3Y fallback")
def test_coffee_can_revenue_fallback_on_nan_primary(mods):
    r = mods.coffee_can._score(_cc(sales_growth_10y=np.nan, sales_growth_5y=12))
    assert r["criteria"]["revenue_cagr_gt_10"] is True


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="coffee_can.py `opm or net_profit_margin`: NaN opm blocks the margin fallback "
                          "for moat points")
def test_coffee_can_moat_margin_fallback_on_nan_opm(mods):
    assert mods.coffee_can._score(_cc(opm=np.nan, net_profit_margin=41))["moat_score"] == 2


def test_coffee_can_watch_ratio_boundary(mods):
    # 6 criteria: 4/6 = 0.667 < 0.7 -> AVOID; 5/6 -> WATCH
    five = mods.coffee_can._score(_cc(roce=1))
    assert five["signal"] == "WATCH" and five["passed"] is False and five["score"] == 0
    four = mods.coffee_can._score(_cc(roce=1, debt_to_equity=5))
    assert four["signal"] == "AVOID"
    # unevaluated criteria are excluded from the denominator: 7/10 style case with 3 known (2/3)
    r = mods.coffee_can._score(row(roce=16, debt_to_equity=0.5, market_cap=50))
    assert r["signal"] == "AVOID"
    # 1 known passing -> all evaluated pass -> BUY (documented behaviour of 'evaluated' only)
    r = mods.coffee_can._score(row(roce=16))
    assert r["signal"] == "BUY"


def test_coffee_can_no_data_is_avoid_not_buy(mods):
    r = mods.coffee_can._score(row())
    assert r["signal"] == "AVOID" and r["passed"] is False and r["score"] == 0


def test_coffee_can_moat_points(mods):
    m = lambda **k: mods.coffee_can._score(_cc(**k))["moat_score"]  # noqa: E731
    # base: opm none, roe none, roce 16 (no), de 0.9 (no)
    assert m() == 0
    assert m(opm=40) == 1 and m(opm=40.1) == 2
    assert m(opm=25) == 0 and m(opm=25.1) == 1
    assert m(net_profit_margin=41) == 2   # fallback when opm missing
    assert m(roe=20) == 0 and m(roe=20.1) == 1
    assert m(roce=25) == 0 and m(roce=25.1) == 1
    assert m(debt_to_equity=0.3) == 0 and m(debt_to_equity=0.29) == 1
    assert m(opm=50, roe=25, roce=30, debt_to_equity=0.1) == 5


def test_coffee_can_scan_sanitises(mods):
    out = mods.coffee_can.scan(pd.DataFrame([{"name": "a", "roce": 30.0}]))
    assert out[0]["pe"] is None and out[0]["roe"] is None
    assert mods.coffee_can.scan(pd.DataFrame()) == []
