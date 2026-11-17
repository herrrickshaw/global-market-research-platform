#!/usr/bin/env python3
"""
test_fixed_horizon_scorer.py — proves the fixed-horizon scorer against
hand-computed synthetic data BEFORE it touches real signals. Written first,
per this session's established discipline (purge_embargo.py, factor_screens.py
were all tested before running for real; this removes the "score as of
today" confound found in run_factor_backtests.py's first fixed-horizon pass
would need the exact same discipline or it would just move the bug).

Run: python3 test_fixed_horizon_scorer.py
"""
import numpy as np
import pandas as pd

from run_factor_backtests_fixed import score_fixed_horizon, HORIZONS_TRADING_DAYS


def _panel(prices: dict, mkt="TEST") -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", periods=400)
    return pd.DataFrame({sym: pd.Series(p, index=idx[:len(p)]) if not np.isscalar(p)
                         else pd.Series(p, index=idx)
                         for sym, p in prices.items()})


def test_fixed_horizon_hand_computed():
    idx = pd.bdate_range("2020-01-01", periods=400)
    # FOO: price rises 1%/day compounding after entry.
    px = pd.Series([100 * (1.01 ** i) for i in range(400)], index=idx)
    wide = pd.DataFrame({"FOO": px, "BENCH": pd.Series(100.0, index=idx)})  # flat benchmark
    signals = pd.DataFrame([{"symbol": "FOO", "market": "TEST", "signal_date": idx[10]}])

    scored = score_fixed_horizon(signals, "symbol", wide_override={"TEST": wide},
                                 bench_override={"TEST": wide["BENCH"]})
    row = scored[scored["symbol"] == "FOO"].iloc[0]
    # entry = idx[11] (first bar after signal_date), price = 100*1.01^11
    entry_px = 100 * (1.01 ** 11)
    for h_name, h_days in HORIZONS_TRADING_DAYS.items():
        exit_pos = 11 + h_days
        if exit_pos >= 400:
            assert pd.isna(row[f"ret_{h_name}"]), f"{h_name} should be NaN past panel end"
            continue
        exit_px = 100 * (1.01 ** exit_pos)
        expected_ret = (exit_px / entry_px - 1) * 100
        assert abs(row[f"ret_{h_name}"] - expected_ret) < 0.01, \
            f"{h_name}: got {row[f'ret_{h_name}']}, expected {expected_ret}"
        # benchmark is flat -> xret should equal raw ret exactly
        assert abs(row[f"xret_{h_name}"] - expected_ret) < 0.01
    print("  test_fixed_horizon_hand_computed: PASS")


def test_fixed_horizon_past_panel_end_is_nan_not_fabricated():
    idx = pd.bdate_range("2020-01-01", periods=30)  # short panel
    px = pd.Series(np.linspace(100, 110, 30), index=idx)
    wide = pd.DataFrame({"FOO": px, "BENCH": pd.Series(100.0, index=idx)})
    signals = pd.DataFrame([{"symbol": "FOO", "market": "TEST", "signal_date": idx[5]}])
    scored = score_fixed_horizon(signals, "symbol", wide_override={"TEST": wide},
                                 bench_override={"TEST": wide["BENCH"]})
    row = scored.iloc[0]
    assert pd.notna(row["ret_1mo"]), "1mo horizon should resolve with 30 bars"
    assert pd.isna(row["ret_1yr"]), "1yr horizon must be NaN, not fabricated, with only 30 bars"
    print("  test_fixed_horizon_past_panel_end_is_nan_not_fabricated: PASS")


def test_stale_entry_still_excluded_in_fixed_horizon_mode():
    idx1 = pd.bdate_range("2020-01-01", periods=10)
    idx2 = pd.bdate_range("2024-01-01", periods=300)  # a multi-year gap, like CETX
    px = pd.concat([pd.Series(100.0, index=idx1), pd.Series(110.0, index=idx2)])
    wide = pd.DataFrame({"GAPPY": px, "BENCH": pd.Series(100.0, index=px.index)})
    signals = pd.DataFrame([{"symbol": "GAPPY", "market": "TEST", "signal_date": idx1[-1]}])
    scored = score_fixed_horizon(signals, "symbol", wide_override={"TEST": wide},
                                 bench_override={"TEST": wide["BENCH"]})
    assert scored.empty, "a signal whose next bar is years away must still be excluded as stale"
    print("  test_stale_entry_still_excluded_in_fixed_horizon_mode: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
