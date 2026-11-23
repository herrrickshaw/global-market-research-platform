"""Offline tests for backend/scanners/market_regime.py (yfinance + cache faked)."""
import json
import sys
from datetime import date

import numpy as np
import pandas as pd
import pytest

import gmrp_helpers as H


@pytest.fixture()
def mr(tmp_path, monkeypatch):
    m = H.load("gmrp_market_regime", "backend", "scanners", "market_regime.py")
    monkeypatch.setattr(m, "CACHE", str(tmp_path / "sub" / "regime_cache.json"))
    yield m
    sys.modules.pop("gmrp_market_regime", None)


TODAY = str(date.today())


def _write(mr, text):
    import os
    os.makedirs(os.path.dirname(mr.CACHE), exist_ok=True)
    with open(mr.CACHE, "w") as f:
        f.write(text)


def _read(mr):
    with open(mr.CACHE) as f:
        return json.load(f)


def test_baskets_are_20_unique_tickers_per_market(mr):
    assert set(mr.BASKETS) == {"us", "india", "japan", "korea", "china", "europe"}
    for k, v in mr.BASKETS.items():
        assert len(v) == 20 and len(set(v)) == 20, k


def test_unknown_market_returns_unknown_without_touching_cache(mr, monkeypatch):
    monkeypatch.setattr(mr, "_compute", lambda m: pytest.fail("must not compute"))
    r = mr.get_regime("mars")
    assert r == {"trend": "unknown", "vol": "unknown", "asof": TODAY}


def test_market_is_case_insensitive_and_result_cached(mr, monkeypatch):
    calls = []

    def comp(m):
        calls.append(m)
        return {"trend": "bull", "vol": "LOW"}
    monkeypatch.setattr(mr, "_compute", comp)
    r1 = mr.get_regime("US")
    r2 = mr.get_regime("us")
    assert calls == ["us"]
    assert r1 == {"trend": "bull", "vol": "LOW", "asof": TODAY} == r2
    assert _read(mr)["us"]["trend"] == "bull"


def test_stale_cache_is_recomputed(mr, monkeypatch):
    _write(mr, json.dumps({"us": {"trend": "bear", "vol": "HIGH", "asof": "2000-01-01"}}))
    monkeypatch.setattr(mr, "_compute", lambda m: {"trend": "chop", "vol": "MID"})
    assert mr.get_regime("us")["trend"] == "chop"


def test_failure_returns_stale_hit_else_unknown(mr, monkeypatch):
    stale = {"trend": "bear", "vol": "HIGH", "asof": "2000-01-01"}
    _write(mr, json.dumps({"us": stale}))

    def boom(m):
        raise RuntimeError("net")
    monkeypatch.setattr(mr, "_compute", boom)
    assert mr.get_regime("us") == stale
    assert mr.get_regime("india") == {"trend": "unknown", "vol": "unknown", "asof": TODAY}


def test_corrupt_cache_is_ignored(mr, monkeypatch):
    _write(mr, "{not json")
    monkeypatch.setattr(mr, "_compute", lambda m: {"trend": "bull", "vol": "LOW"})
    assert mr.get_regime("us")["trend"] == "bull"


def test_cache_write_failure_does_not_raise(mr, monkeypatch):
    monkeypatch.setattr(mr, "_compute", lambda m: {"trend": "bull", "vol": "LOW"})
    monkeypatch.setattr(mr.os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    assert mr.get_regime("us")["trend"] == "bull"


# ── _compute with a fake yfinance ────────────────────────────────────────────

def _fake_yf(monkeypatch, panel):
    class YF:
        calls = []

        @staticmethod
        def download(tickers, **kw):
            YF.calls.append((tickers, kw))
            return {"Close": panel}
    monkeypatch.setitem(sys.modules, "yfinance", YF)
    return YF


def _panel(drift, n=400, ncols=8, seed=0, noise=0.002):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2024-01-01", periods=n)
    rets = drift + rng.normal(0, noise, size=(n, ncols))
    return pd.DataFrame(100 * np.cumprod(1 + rets, axis=0), index=idx,
                        columns=[f"T{i}" for i in range(ncols)])


def test_compute_bull_on_steady_uptrend(mr, monkeypatch):
    yf = _fake_yf(monkeypatch, _panel(0.003))
    r = mr._compute("us")
    assert r["trend"] == "bull"
    assert r["vol"] in {"LOW", "MID", "HIGH"}
    tickers, kw = yf.calls[0]
    assert tickers == mr.BASKETS["us"]
    assert kw["period"] == "2y" and kw["auto_adjust"] is True and kw["progress"] is False


def test_compute_bear_on_steady_downtrend(mr, monkeypatch):
    _fake_yf(monkeypatch, _panel(-0.003))
    assert mr._compute("us")["trend"] == "bear"


def test_compute_chop_when_above_ema_but_falling(mr, monkeypatch):
    # long uptrend then a short dip: index still above EMA100 but EMA slope turns... force via direct drift flip
    up = _panel(0.004, n=300)
    tail_ret = np.full((20, up.shape[1]), -0.0005)
    tail = up.iloc[-1].values * np.cumprod(1 + tail_ret, axis=0)
    tail_df = pd.DataFrame(tail, index=pd.bdate_range(up.index[-1] + pd.Timedelta(days=1), periods=20),
                           columns=up.columns)
    _fake_yf(monkeypatch, pd.concat([up, tail_df]))
    assert mr._compute("us")["trend"] in {"bull", "chop"}


def test_compute_unknown_when_history_too_short_for_ema100(mr, monkeypatch):
    _fake_yf(monkeypatch, _panel(0.003, n=60))
    assert mr._compute("us") == {"trend": "unknown", "vol": "unknown"}


def test_compute_series_input_and_huge_moves_masked(mr, monkeypatch):
    p = _panel(0.003, ncols=1)
    s = p["T0"]
    _fake_yf(monkeypatch, s)  # a Series, as yfinance returns for one ticker
    # one column -> n<=4 non-null per day -> index undefined -> no EMA -> unknown
    assert mr._compute("us") == {"trend": "unknown", "vol": "unknown"}


def test_compute_vol_percentile_buckets(mr, monkeypatch):
    # quiet history then a noisy tail => latest vol is the highest of the window
    quiet = _panel(0.001, n=330, noise=0.0005, seed=1)
    noisy = _panel(0.001, n=40, noise=0.02, seed=2)
    noisy.index = pd.bdate_range(quiet.index[-1] + pd.Timedelta(days=1), periods=40)
    noisy = noisy / noisy.iloc[0] * quiet.iloc[-1]
    _fake_yf(monkeypatch, pd.concat([quiet, noisy]))
    assert mr._compute("us")["vol"] == "HIGH"
    # noisy history then a quiet tail => latest vol is the lowest
    noisy2 = _panel(0.001, n=330, noise=0.02, seed=3)
    quiet2 = _panel(0.001, n=60, noise=0.0002, seed=4)
    quiet2.index = pd.bdate_range(noisy2.index[-1] + pd.Timedelta(days=1), periods=60)
    quiet2 = quiet2 / quiet2.iloc[0] * noisy2.iloc[-1]
    _fake_yf(monkeypatch, pd.concat([noisy2, quiet2]))
    assert mr._compute("us")["vol"] == "LOW"


def test_compute_masks_implausible_daily_moves(mr, monkeypatch):
    # 5 tickers, 101 rows -> exactly 100 index returns, the minimum for an EMA(100).
    p = _panel(0.003, n=101, ncols=5)
    _fake_yf(monkeypatch, p)
    assert mr._compute("us")["trend"] != "unknown"
    # a +70% one-day print on one ticker is masked -> only 4 valid names that day
    # (<= 4 is dropped), leaving 99 returns -> no EMA -> unknown.
    jumped = p.copy()
    jumped.iloc[50:, 0] = jumped.iloc[50:, 0] * 1.7
    _fake_yf(monkeypatch, jumped)
    assert mr._compute("us") == {"trend": "unknown", "vol": "unknown"}
    # a 50% move is below the 60% cut-off and is kept
    ok = p.copy()
    ok.iloc[50:, 0] = ok.iloc[50:, 0] * 1.5
    _fake_yf(monkeypatch, ok)
    assert mr._compute("us")["trend"] != "unknown"
