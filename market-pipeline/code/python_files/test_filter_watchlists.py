#!/usr/bin/env python3
"""
test_filter_watchlists.py — proves the add/evict/purge state machine in
filter_watchlists.py against a simulated multi-day sequence, run against a
scratch copy of PURGED_ARCHIVE so real data is never touched.

Run: python3 test_filter_watchlists.py
"""
import os
import tempfile
from pathlib import Path

import pandas as pd

import filter_watchlists as FW


def _day(n: int) -> pd.Timestamp:
    return pd.Timestamp("2026-01-01") + pd.Timedelta(days=n)


def test_new_pass_adds_active():
    wl = pd.DataFrame(columns=["symbol", "market", "filter", "status", "entry_date",
                               "entry_price", "last_pass_date", "miss_count",
                               "evicted_date", "last_price"])
    wl, stats = FW.update_membership(wl, "darvas", "IN", {"FOO"}, {"FOO": 100.0}, _day(0))
    assert stats["added"] == 1
    row = wl[(wl.symbol == "FOO")].iloc[0]
    assert row["status"] == "active" and row["miss_count"] == 0
    assert row["entry_price"] == 100.0
    print("  test_new_pass_adds_active: PASS")


def test_continued_pass_resets_miss_count():
    wl = pd.DataFrame([{"symbol": "FOO", "market": "IN", "filter": "darvas",
                       "status": "active", "entry_date": _day(0), "entry_price": 100.0,
                       "last_pass_date": _day(0), "miss_count": 3,
                       "evicted_date": pd.NaT, "last_price": 100.0}])
    wl, stats = FW.update_membership(wl, "darvas", "IN", {"FOO"}, {"FOO": 105.0}, _day(4))
    assert stats["still_passing"] == 1
    row = wl.iloc[0]
    assert row["miss_count"] == 0, "a pass today must reset the miss streak"
    assert row["last_price"] == 105.0
    print("  test_continued_pass_resets_miss_count: PASS")


def test_miss_increments_but_does_not_evict_below_threshold():
    wl = pd.DataFrame([{"symbol": "FOO", "market": "IN", "filter": "darvas",
                       "status": "active", "entry_date": _day(0), "entry_price": 100.0,
                       "last_pass_date": _day(0), "miss_count": 4,
                       "evicted_date": pd.NaT, "last_price": 100.0}])
    # EVICT_SESSIONS=5: miss_count going 4 -> 5 must NOT evict (threshold is > 5, not >= 5)
    wl, stats = FW.update_membership(wl, "darvas", "IN", set(), {}, _day(5))
    assert stats["missed"] == 1 and stats["evicted"] == 0
    row = wl.iloc[0]
    assert row["miss_count"] == 5 and row["status"] == "active", \
        f"miss_count={row['miss_count']} status={row['status']} -- must still be active at exactly 5"
    print("  test_miss_increments_but_does_not_evict_below_threshold: PASS")


def test_miss_evicts_past_threshold():
    wl = pd.DataFrame([{"symbol": "FOO", "market": "IN", "filter": "darvas",
                       "status": "active", "entry_date": _day(0), "entry_price": 100.0,
                       "last_pass_date": _day(0), "miss_count": 5,
                       "evicted_date": pd.NaT, "last_price": 100.0}])
    # miss_count 5 -> 6 must NOW evict (> EVICT_SESSIONS=5)
    wl, stats = FW.update_membership(wl, "darvas", "IN", set(), {}, _day(6))
    assert stats["evicted"] == 1
    row = wl.iloc[0]
    assert row["status"] == "evicted" and row["miss_count"] == 6
    assert row["evicted_date"] == _day(6)
    print("  test_miss_evicts_past_threshold: PASS")


def test_evicted_name_revives_on_new_pass():
    wl = pd.DataFrame([{"symbol": "FOO", "market": "IN", "filter": "darvas",
                       "status": "evicted", "entry_date": _day(0), "entry_price": 100.0,
                       "last_pass_date": _day(0), "miss_count": 6,
                       "evicted_date": _day(6), "last_price": 90.0}])
    wl, stats = FW.update_membership(wl, "darvas", "IN", {"FOO"}, {"FOO": 95.0}, _day(10))
    assert stats["revived"] == 1
    row = wl.iloc[0]
    assert row["status"] == "active" and row["miss_count"] == 0
    assert pd.isna(row["evicted_date"]), "revival must clear evicted_date"
    print("  test_evicted_name_revives_on_new_pass: PASS")


def test_purge_boundary_exact():
    # PURGE_SESSIONS=15: evicted on day 6, still present at day 21 (15 days
    # later, NOT > 15) -- must survive; at day 22 (16 days later, > 15) --
    # must be purged. Route PURGED_ARCHIVE to a scratch file so this never
    # touches the real archive.
    real_archive = FW.PURGED_ARCHIVE
    with tempfile.TemporaryDirectory() as td:
        FW.PURGED_ARCHIVE = Path(td) / "purged_scratch.csv"
        try:
            wl = pd.DataFrame([{"symbol": "FOO", "market": "IN", "filter": "darvas",
                               "status": "evicted", "entry_date": _day(0),
                               "entry_price": 100.0, "last_pass_date": _day(0),
                               "miss_count": 6, "evicted_date": _day(6),
                               "last_price": 90.0}])
            wl, stats = FW.update_membership(wl, "darvas", "IN", set(), {}, _day(21))
            assert stats["purged"] == 0, "15 days since eviction must NOT purge yet"
            assert len(wl) == 1

            wl, stats = FW.update_membership(wl, "darvas", "IN", set(), {}, _day(22))
            assert stats["purged"] == 1, "16 days since eviction must purge"
            assert len(wl) == 0
            assert FW.PURGED_ARCHIVE.exists(), "purged rows must be archived, not just dropped"
            archived = pd.read_csv(FW.PURGED_ARCHIVE)
            assert len(archived) == 1 and archived.iloc[0]["symbol"] == "FOO"
        finally:
            FW.PURGED_ARCHIVE = real_archive
    print("  test_purge_boundary_exact: PASS")


def test_independent_membership_across_filters_same_symbol():
    # the whole point of this design: FOO can be evicted from darvas while
    # simultaneously active in piotroski, same symbol+market, independent state.
    wl = pd.DataFrame([
        {"symbol": "FOO", "market": "IN", "filter": "darvas", "status": "evicted",
         "entry_date": _day(0), "entry_price": 100.0, "last_pass_date": _day(0),
         "miss_count": 6, "evicted_date": _day(6), "last_price": 90.0},
        {"symbol": "FOO", "market": "IN", "filter": "piotroski", "status": "active",
         "entry_date": _day(0), "entry_price": 100.0, "last_pass_date": _day(5),
         "miss_count": 0, "evicted_date": pd.NaT, "last_price": 100.0},
    ])
    # a darvas record run for FOO must not touch its piotroski row
    wl, stats = FW.update_membership(wl, "darvas", "IN", {"FOO"}, {"FOO": 95.0}, _day(10))
    pio_row = wl[wl["filter"] == "piotroski"].iloc[0]
    assert pio_row["status"] == "active" and pio_row["miss_count"] == 0, \
        "piotroski membership must be untouched by a darvas-only update"
    print("  test_independent_membership_across_filters_same_symbol: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
