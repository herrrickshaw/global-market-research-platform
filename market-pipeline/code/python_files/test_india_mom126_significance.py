#!/usr/bin/env python3
"""test_india_mom126_significance.py — hand-computed checks for the daily,
non-overlapping India mom126 re-test, before trusting it on real data or
letting it write to zone_rules.json. Run: python3 test_india_mom126_significance.py"""
import json

import numpy as np
import pandas as pd

import backtest_india_mom126_significance as SIG


def test_retest_spread_hand_computed_clear_signal():
    # 18 names, 300 daily bars -- big enough that a tercile (>=6 names) is
    # populated. WINNERS (W0-5) trend up over the whole window (strong 126d
    # momentum); LOSERS (L0-5) trend down; FLATs fill the middle tercile.
    # Forward 10-day return should be clearly positive for winners and
    # negative for losers -> a strong, real spread.
    idx = pd.bdate_range("2020-01-01", periods=300)
    data = {}
    for i in range(6):
        data[f"W{i}"] = np.linspace(100, 100 + 20 * (i + 1), 300)
    for i in range(6):
        data[f"L{i}"] = np.linspace(100, 100 - 8 * (i + 1), 300)
    for i in range(6):
        data[f"F{i}"] = np.full(300, 100.0)
    w = pd.DataFrame(data, index=idx)
    res = SIG.retest_spread(w, lookback=126, fwd=10, start=str(idx[0].date()))
    assert res["spread_pct"] is not None, res
    assert res["spread_pct"] > 0, f"trending winners must beat trending losers, got {res}"
    assert res["n_indep_obs"] > 10, res
    print("  test_retest_spread_hand_computed_clear_signal: PASS")


def test_retest_spread_no_signal_when_no_trend():
    # All names random-walk around the same level with no persistent trend --
    # forward-tercile spread should be small/noisy, not a strong signal.
    rng = np.random.default_rng(42)
    idx = pd.bdate_range("2020-01-01", periods=400)
    data = {f"N{i}": 100 + np.cumsum(rng.normal(0, 0.3, 400)) for i in range(20)}
    w = pd.DataFrame(data, index=idx)
    res = SIG.retest_spread(w, lookback=126, fwd=10, start=str(idx[0].date()))
    if res["t_stat"] is not None:
        assert abs(res["t_stat"]) < 3.0, \
            f"pure noise should not produce a huge t-stat, got {res}"
    print("  test_retest_spread_no_signal_when_no_trend: PASS")


def test_retest_spread_too_few_obs_returns_none():
    idx = pd.bdate_range("2020-01-01", periods=50)  # well under 126+10
    w = pd.DataFrame({f"N{i}": 100.0 for i in range(10)}, index=idx)
    res = SIG.retest_spread(w, lookback=126, fwd=10, start=str(idx[0].date()))
    assert res["spread_pct"] is None, "must not fabricate a number with insufficient history"
    print("  test_retest_spread_too_few_obs_returns_none: PASS")


def test_wire_result_promotes_on_significant_positive(tmp_path=None):
    import backtest_india_mom126_significance as SIGmod
    orig_json, orig_md = SIGmod.OUT_JSON, SIGmod.OUT_MD
    fake_json = SIGmod.HERE / "test_scratch_zone_rules.json"
    fake_md = SIGmod.HERE / "test_scratch_zone_rules.md"
    fake_json.write_text(json.dumps({"IN": {"rule": "trend", "spread_pct": 0.15, "t": 0.56, "all": {}}}))
    fake_md.write_text("# doc\n")
    SIGmod.OUT_JSON, SIGmod.OUT_MD = fake_json, fake_md
    try:
        status = SIGmod.wire_result({"spread_pct": 0.5, "t_stat": 2.0, "n_indep_obs": 50})
        out = json.loads(fake_json.read_text())
        assert out["IN"]["rule"] == "mom126", out
        assert "WIRED" in status and "NOT WIRED" not in status
    finally:
        SIGmod.OUT_JSON, SIGmod.OUT_MD = orig_json, orig_md
        fake_json.unlink(missing_ok=True)
        fake_md.unlink(missing_ok=True)
    print("  test_wire_result_promotes_on_significant_positive: PASS")


def test_wire_result_leaves_unchanged_on_insignificant():
    import backtest_india_mom126_significance as SIGmod
    orig_json, orig_md = SIGmod.OUT_JSON, SIGmod.OUT_MD
    fake_json = SIGmod.HERE / "test_scratch_zone_rules2.json"
    fake_md = SIGmod.HERE / "test_scratch_zone_rules2.md"
    fake_json.write_text(json.dumps({"IN": {"rule": "trend", "spread_pct": 0.15, "t": 0.56, "all": {}}}))
    fake_md.write_text("# doc\n")
    SIGmod.OUT_JSON, SIGmod.OUT_MD = fake_json, fake_md
    try:
        status = SIGmod.wire_result({"spread_pct": 0.2, "t_stat": 1.1, "n_indep_obs": 50})
        out = json.loads(fake_json.read_text())
        assert out["IN"]["rule"] == "trend", "must NOT promote on an insignificant result"
        assert "NOT WIRED" in status
    finally:
        SIGmod.OUT_JSON, SIGmod.OUT_MD = orig_json, orig_md
        fake_json.unlink(missing_ok=True)
        fake_md.unlink(missing_ok=True)
    print("  test_wire_result_leaves_unchanged_on_insignificant: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
