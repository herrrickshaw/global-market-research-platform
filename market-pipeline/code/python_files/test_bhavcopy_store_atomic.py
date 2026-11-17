#!/usr/bin/env python3
"""test_bhavcopy_store_atomic.py — a failed LMDB rebuild must leave the
previous store readable (2026-10-26: MDB_MAP_FULL mid-build left an EMPTY
store, so every India name in the mailer read "not in cache").
Run: python3 test_bhavcopy_store_atomic.py
"""
import importlib
import os
import sys
import tempfile

import pandas as pd


def _frame(n=5, start=100.0):
    idx = pd.date_range("2026-10-19", periods=n, freq="B")
    c = pd.Series([start + i for i in range(n)], index=idx)
    return pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1000})


def _fresh_store_module(cache):
    os.environ["BHAV_CACHE"] = cache
    sys.modules.pop("bhavcopy_store", None)
    return importlib.import_module("bhavcopy_store")


def test_failed_build_keeps_previous_store():
    with tempfile.TemporaryDirectory() as d:
        bs = _fresh_store_module(d)
        assert bs.build({"OLD": _frame()}, verbose=False) == 1
        bs._MAP_SIZE = 64 * 1024                      # force MDB_MAP_FULL
        big = {f"S{i}": _frame(400) for i in range(200)}
        try:
            bs.build(big, verbose=False)
            raise AssertionError("expected the undersized build to fail")
        except AssertionError:
            raise
        except Exception:
            pass
        assert bs.get("OLD") is not None, "previous store was destroyed by a failed build"
        assert bs.symbols() == ["OLD"]
        assert not (bs.STORE.parent / (bs.STORE.name + ".old")).exists()
    print("  test_failed_build_keeps_previous_store: PASS")


def test_successful_build_replaces_store():
    with tempfile.TemporaryDirectory() as d:
        bs = _fresh_store_module(d)
        bs.build({"A": _frame()}, verbose=False)
        bs.build({"B": _frame(start=50.0)}, verbose=False)
        assert bs.get("A") is None and float(bs.get("B")["Close"].iloc[-1]) == 54.0
        leftovers = [p.name for p in bs.STORE.parent.iterdir() if p.name != bs.STORE.name]
        assert leftovers == [], leftovers
    print("  test_successful_build_replaces_store: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
