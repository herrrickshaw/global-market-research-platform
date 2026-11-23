"""Offline tests for backend/scanners/daily_scanner.py (pure pandas, no I/O)."""
import math
import sys

import numpy as np
import pandas as pd
import pytest

import gmrp_helpers as H

ds = H.load("gmrp_daily_scanner", "backend", "scanners", "daily_scanner.py")


# ── helpers ──────────────────────────────────────────────────────────────────

def test_col_returns_numeric_or_nan_series():
    df = pd.DataFrame({"a": ["1", "x", None]}, index=[5, 6, 7])
    s = ds._col(df, "a")
    assert s.iloc[0] == 1 and math.isnan(s.iloc[1]) and math.isnan(s.iloc[2])
    miss = ds._col(df, "nope")
    assert list(miss.index) == [5, 6, 7] and miss.isna().all()


def test_vcrit_and_pts():
    passes = pd.Series([True, False, True])
    valid = pd.Series([True, True, False])
    c = ds._vcrit(passes, valid)
    assert list(c)[:2] == [True, False] and pd.isna(c.iloc[2])
    assert list(ds._pts(c)) == [1, 0, 0]
    assert list(ds._pts(c, 2)) == [2, 0, 0]


def test_r_rounds_and_rejects_nan_inf_and_garbage():
    assert ds._r(1.23456) == 1.23
    assert ds._r("2.005") in (2.0, 2.01)
    assert ds._r(float("nan")) is None and ds._r(float("inf")) is None
    assert ds._r(None) is None and ds._r("abc") is None
    assert ds._r(0) == 0.0


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="daily_scanner.py:70 _b(): bool(NaN) is True, and _vcrit() fills "
                          "invalid cells with NaN, so every criterion lacking data is reported True")
def test_b_nan_is_none():
    assert ds._b(float("nan")) is None


def test_b():
    assert ds._b(None) is None
    assert ds._b(np.bool_(True)) is True
    assert ds._b(0) is False

    class Bad:
        def __bool__(self):
            raise ValueError
    assert ds._b(Bad()) is None


def test_strs_fillna_and_missing_column():
    df = pd.DataFrame({"a": ["x", None, 3]})
    assert ds._strs(df, "a", "d") == ["x", "d", "3"]
    assert ds._strs(df, "zz", "d") == ["d", "d", "d"]
    assert ds._strs(df, "zz") == ["", "", ""]


# ── scan_darvas ──────────────────────────────────────────────────────────────

def drow(**kw):
    base = dict(ticker="T", name="N", cmp=90.0, high_52w=100.0, low_52w=50.0, ema_50=80.0, rsi=55.0)
    base.update(kw)
    return base


def one(f, **kw):
    return f(pd.DataFrame([drow(**kw)]))[0]


def test_darvas_empty():
    assert ds.scan_darvas(pd.DataFrame()) == []
    assert ds.scan_piotroski(pd.DataFrame()) == []


def test_darvas_core_four_criteria_pass_is_buy_with_score_6():
    r = one(ds.scan_darvas)
    assert r["score"] == 6 and r["max_score"] == 6 and r["signal"] == "BUY"
    assert r["criteria"]["near_52w_high"] is True and r["criteria"]["above_ema50"] is True
    assert r["criteria"]["range_strength"] is True and r["criteria"]["rsi_healthy"] is True
    assert r["completeness"] == 31   # 4 of 13 -> round(30.77)
    assert r["ticker"] == "T" and r["name"] == "N"
    assert r["rsi_signal"] == "HOLD"


def test_darvas_near_high_boundary_15pct_inclusive():
    assert one(ds.scan_darvas, cmp=85.0)["criteria"]["near_52w_high"] is True
    assert one(ds.scan_darvas, cmp=84.9)["criteria"]["near_52w_high"] is False


def test_darvas_range_strength_boundary_60pct_inclusive():
    assert one(ds.scan_darvas, cmp=80.0)["criteria"]["range_strength"] is True   # (80-50)/50 = .6
    assert one(ds.scan_darvas, cmp=79.9)["criteria"]["range_strength"] is False


def test_darvas_rsi_band_inclusive():
    for v, exp in [(40, True), (68, True), (39.9, False), (68.1, False)]:
        assert one(ds.scan_darvas, rsi=v)["criteria"]["rsi_healthy"] is exp, v


def test_darvas_signal_thresholds():
    # above ema50 (2) + near high (2) = 4 -> WATCH when others fail
    r = one(ds.scan_darvas, cmp=90.0, low_52w=0.0, high_52w=100.0, rsi=10)
    assert r["score"] == 5 and r["signal"] == "BUY"      # 2+2+1(range .9)+0
    r = one(ds.scan_darvas, cmp=90.0, high_52w=200.0, low_52w=0.0, rsi=10)
    # near-high fails (55%), ema ok (2), range 0.45 fails, rsi fails
    assert r["score"] == 2 and r["signal"] == "AVOID"
    r = one(ds.scan_darvas, cmp=90.0, high_52w=200.0, low_52w=0.0, rsi=50)
    assert r["score"] == 3 and r["signal"] == "WATCH"


def test_darvas_lazy_load_ignores_optional_columns_full_load_uses_them():
    extra = dict(ema_20=85.0, ema_200=70.0, roe=20.0, pe=15.0, pb=2.0, debt_to_equity=0.5,
                 macd=1.0, macd_signal=0.5, volume_ratio=2.0, bb_pct=0.8, bb_upper=95.0,
                 bb_lower=60.0, stoch_k=60.0, stoch_d=50.0, atr_14=2.0, beta=1.1,
                 current_ratio=2.0)
    lazy = one(ds.scan_darvas, **extra)
    assert lazy["roe"] is None and lazy["max_score"] == 6
    full = ds.scan_darvas(pd.DataFrame([drow(**extra)]), lazy_load=False)[0]
    assert full["roe"] == 20.0 and full["max_score"] == 15 and full["score"] == 15
    assert full["completeness"] == 100
    assert all(v is True for v in full["criteria"].values())


def test_darvas_full_load_optional_boundaries():
    def f(**kw):
        return ds.scan_darvas(pd.DataFrame([drow(**kw)]), lazy_load=False)[0]["criteria"]
    assert f(roe=12)["buffett_roe"] is False and f(roe=12.1)["buffett_roe"] is True
    assert f(pe=5)["buffett_pe"] is True and f(pe=30)["buffett_pe"] is True
    assert f(pe=4.9)["buffett_pe"] is False and f(pe=30.1)["buffett_pe"] is False
    assert f(debt_to_equity=1.0)["buffett_de"] is False and f(debt_to_equity=0.99)["buffett_de"] is True
    assert f(volume_ratio=1.5)["volume_surge"] is False and f(volume_ratio=1.51)["volume_surge"] is True
    assert f(bb_pct=0.5)["bb_upper_half"] is False and f(bb_pct=0.51)["bb_upper_half"] is True
    assert f(macd=1, macd_signal=1)["macd_bull"] is False
    assert f(ema_20=80, ema_50=80)["ema_cross"] is False
    assert f(cmp=70, ema_200=70)["above_ema200"] is False
    # stoch: K within [20,80] and K > D
    assert f(stoch_k=20, stoch_d=10)["stoch_bullish"] is True
    assert f(stoch_k=80, stoch_d=10)["stoch_bullish"] is True
    assert f(stoch_k=19.9, stoch_d=10)["stoch_bullish"] is False
    assert f(stoch_k=80.1, stoch_d=10)["stoch_bullish"] is False
    assert f(stoch_k=50, stoch_d=50)["stoch_bullish"] is False


def test_darvas_missing_values_are_none_not_false():
    r = ds.scan_darvas(pd.DataFrame([{"ticker": "Q"}]))[0]
    assert r["score"] == 0 and r["signal"] == "AVOID" and r["completeness"] == 0
    assert r["cmp"] is None and r["volume"] is None


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="daily_scanner.py:70 _b(NaN) -> True: criteria with no data are emitted as True")
def test_darvas_missing_values_criteria_are_none():
    r = ds.scan_darvas(pd.DataFrame([{"ticker": "Q"}]))[0]
    assert set(r["criteria"].values()) == {None}


def test_darvas_zero_high_or_flat_range_scores_nothing_for_that_criterion():
    r = one(ds.scan_darvas, high_52w=0.0)
    assert r["score"] == 2 + 1      # only above-ema50 (2) and rsi (1) can score
    r = one(ds.scan_darvas, high_52w=50.0, low_52w=50.0)
    assert r["score"] == 2 + 2 + 1      # near-high (2) + ema50 (2) + rsi (1); range invalid


def test_darvas_output_row_count_and_order_and_volume_int():
    df = pd.DataFrame([drow(ticker="A", volume=1500.7), drow(ticker="B", volume=np.nan),
                       drow(ticker="C", _exchange="NSE", sector="S", industry="I", rsi_signal="BUY")],
                      index=[10, 20, 30])
    out = ds.scan_darvas(df)
    assert [r["ticker"] for r in out] == ["A", "B", "C"]
    assert out[0]["volume"] == 1500 and out[1]["volume"] is None
    assert out[2]["_exchange"] == "NSE" and out[2]["sector"] == "S" and out[2]["rsi_signal"] == "BUY"


# ── scan_piotroski ───────────────────────────────────────────────────────────

def test_piotroski_all_eleven_pass_is_buy():
    r = ds.scan_piotroski(pd.DataFrame([dict(
        ticker="T", cmp=90.0, high_52w=100.0, ema_20=85.0, ema_50=80.0, rsi=55.0, roe=10.0,
        opm=20.0, pb=2.0, debt_to_equity=0.4, current_ratio=2.0, revenue_growth=5.0, atr_14=1.0)]))[0]
    assert r["score"] == 11 and r["max_score"] == 11 and r["signal"] == "BUY"
    assert r["completeness"] == 100 and all(v is True for v in r["criteria"].values())


def test_piotroski_boundaries():
    def f(**kw):
        base = dict(cmp=90.0, high_52w=100.0, ema_50=80.0, rsi=55.0)
        base.update(kw)
        return ds.scan_piotroski(pd.DataFrame([base]))[0]["criteria"]
    assert f(roe=0)["F1_roe_positive"] is False and f(roe=0.1)["F1_roe_positive"] is True
    assert f(debt_to_equity=0.5)["F5_low_leverage"] is False
    assert f(opm=15)["F8_op_margin"] is False and f(opm=15.1)["F8_op_margin"] is True
    assert f(revenue_growth=0)["F9_rev_growth"] is False
    assert f(rsi=40)["FX2_rsi_range"] is True and f(rsi=70)["FX2_rsi_range"] is True
    assert f(rsi=39.9)["FX2_rsi_range"] is False and f(rsi=70.1)["FX2_rsi_range"] is False
    assert f(cmp=80, high_52w=100)["FX3_near_high"] is True      # exactly 20%
    assert f(cmp=79.9, high_52w=100)["FX3_near_high"] is False
    assert f(current_ratio=1.5)["FX4_current_ratio"] is False
    assert f(pb=3)["FX5_pb_value"] is False and f(pb=2.99)["FX5_pb_value"] is True
    assert f(ema_20=80, ema_50=80)["FX6_ema_cross"] is False
    assert f(atr_14=2.7, cmp=90)["FX7_low_atr"] is False        # exactly 3% of 90
    assert f(atr_14=2.69, cmp=90)["FX7_low_atr"] is True
    assert f(atr_14=3.0, cmp=100)["FX7_low_atr"] is False       # exactly 3.00% (3/100 == 0.03 in floats)
    assert f(atr_14=2.99, cmp=100)["FX7_low_atr"] is True


def test_piotroski_atr_needs_positive_price():
    a = ds.scan_piotroski(pd.DataFrame([dict(cmp=0.0, atr_14=0.0, rsi=50.0)]))[0]
    b = ds.scan_piotroski(pd.DataFrame([dict(cmp=0.0, rsi=50.0)]))[0]
    assert a["max_score"] == b["max_score"] == 1 and a["score"] == b["score"] == 1


def test_piotroski_dynamic_thresholds():
    # 3 valid criteria (FX1, FX2, FX3): buy>=ceil(1.95)=2? ceil(3*.65)=2, watch>=ceil(1.2)=2
    r = ds.scan_piotroski(pd.DataFrame([dict(cmp=90.0, high_52w=100.0, ema_50=80.0, rsi=10.0)]))[0]
    assert r["max_score"] == 3 and r["score"] == 2 and r["signal"] == "BUY"
    r = ds.scan_piotroski(pd.DataFrame([dict(cmp=90.0, high_52w=100.0, ema_50=95.0, rsi=10.0)]))[0]
    assert r["score"] == 1 and r["signal"] == "AVOID"
    # 10 criteria: buy ceil(6.5)=7, watch ceil(4)=4
    base = dict(cmp=90.0, high_52w=100.0, ema_20=85.0, ema_50=80.0, rsi=55.0, roe=-1.0,
                opm=20.0, pb=2.0, debt_to_equity=0.4, current_ratio=2.0, revenue_growth=5.0)
    r = ds.scan_piotroski(pd.DataFrame([base]))[0]
    assert r["max_score"] == 10 and r["score"] == 9 and r["signal"] == "BUY"
    fail = dict(base, roe=1.0, ema_50=95.0, pb=9.0, debt_to_equity=5.0, current_ratio=0.5, revenue_growth=-1)
    r = ds.scan_piotroski(pd.DataFrame([fail]))[0]
    assert r["score"] == 4 and r["signal"] == "WATCH"
    fail2 = dict(fail, opm=1.0)
    r = ds.scan_piotroski(pd.DataFrame([fail2]))[0]
    assert r["score"] == 3 and r["signal"] == "AVOID"


def test_piotroski_no_data_max_score_clamped_to_one():
    r = ds.scan_piotroski(pd.DataFrame([{"ticker": "x"}]))[0]
    assert r["max_score"] == 1 and r["score"] == 0 and r["signal"] == "AVOID"
    assert r["completeness"] == 0


def test_piotroski_output_fields():
    df = pd.DataFrame([dict(ticker="A", name="Nm", volume=10, sector="S", industry="I",
                            _exchange="BSE", rsi_signal="BUY", cmp=1.0)])
    r = ds.scan_piotroski(df)[0]
    assert (r["ticker"], r["name"], r["volume"], r["sector"], r["industry"],
            r["_exchange"], r["rsi_signal"]) == ("A", "Nm", 10, "S", "I", "BSE", "BUY")
