#!/usr/bin/env python3
"""test_watchlist_digest_zone_rules.py — proves the mom_st/mom126 key-mapping
fix (2026-08-23) actually ranks by the intended horizon field, not d5 for
everything. Run: python3 test_watchlist_digest_zone_rules.py
"""
import watchlist_digest as WD


def _row(symbol, d5=None, d21=None, d126=None):
    return {"symbol": symbol, "market": "US", "zone": "HOLD",
            "d5": d5, "d21": d21, "d126": d126, "missing": False}


def test_mom126_ranks_by_d126_not_d5():
    # A: weak d126 but strong d5 -- must NOT be flagged BUY under mom126.
    # B: strong d126 but weak d5 -- must BE flagged BUY under mom126.
    # C-F: filler so the tercile has enough names to rank.
    rows = [
        _row("A", d5=50.0, d126=-30.0),
        _row("B", d5=-50.0, d126=40.0),
        _row("C", d5=0.0, d126=0.0),
        _row("D", d5=0.0, d126=1.0),
        _row("E", d5=0.0, d126=-1.0),
        _row("F", d5=0.0, d126=2.0),
    ]
    orig_rules, orig_regime = WD._zone_rules, WD._zone_regime
    WD._zone_rules = lambda: {"US": {"rule": "mom126"}}
    WD._zone_regime = lambda: {}
    try:
        WD.assign_recommendations(rows)
    finally:
        WD._zone_rules, WD._zone_regime = orig_rules, orig_regime
    by_sym = {r["symbol"]: r for r in rows}
    assert by_sym["B"]["rec"] == "BUY", \
        f"B has the strongest d126 (+40) -- must be BUY under mom126, got {by_sym['B']['rec']}"
    assert by_sym["A"]["rec"] != "BUY", \
        f"A has the weakest d126 (-30) despite a huge d5 -- must NOT be BUY under mom126, got {by_sym['A']['rec']}"
    print("  test_mom126_ranks_by_d126_not_d5: PASS")


def test_mom_st_ranks_by_d21_not_d5():
    rows = [
        _row("A", d5=50.0, d21=-30.0),
        _row("B", d5=-50.0, d21=40.0),
        _row("C", d5=0.0, d21=0.0),
        _row("D", d5=0.0, d21=1.0),
        _row("E", d5=0.0, d21=-1.0),
        _row("F", d5=0.0, d21=2.0),
    ]
    orig_rules, orig_regime = WD._zone_rules, WD._zone_regime
    WD._zone_rules = lambda: {"US": {"rule": "mom_st"}}
    WD._zone_regime = lambda: {}
    try:
        WD.assign_recommendations(rows)
    finally:
        WD._zone_rules, WD._zone_regime = orig_rules, orig_regime
    by_sym = {r["symbol"]: r for r in rows}
    assert by_sym["B"]["rec"] == "BUY", \
        f"B has the strongest d21 (+40) -- must be BUY under mom_st, got {by_sym['B']['rec']}"
    assert by_sym["A"]["rec"] != "BUY", \
        f"A has the weakest d21 (-30) despite a huge d5 -- must NOT be BUY under mom_st, got {by_sym['A']['rec']}"
    print("  test_mom_st_ranks_by_d21_not_d5: PASS")


def test_revert_still_uses_d5_inverted():
    # revert is the one rule that SHOULD use d5, inverted (buy oversold).
    rows = [
        _row("A", d5=50.0),   # overbought -> must NOT be BUY
        _row("B", d5=-50.0),  # oversold -> must BE BUY
        _row("C", d5=0.0), _row("D", d5=1.0), _row("E", d5=-1.0), _row("F", d5=2.0),
    ]
    orig_rules, orig_regime = WD._zone_rules, WD._zone_regime
    WD._zone_rules = lambda: {"US": {"rule": "revert"}}
    WD._zone_regime = lambda: {}
    try:
        WD.assign_recommendations(rows)
    finally:
        WD._zone_rules, WD._zone_regime = orig_rules, orig_regime
    by_sym = {r["symbol"]: r for r in rows}
    assert by_sym["B"]["rec"] == "BUY", f"most oversold (d5=-50) must be BUY under revert, got {by_sym['B']['rec']}"
    assert by_sym["A"]["rec"] != "BUY", f"most overbought (d5=+50) must NOT be BUY under revert, got {by_sym['A']['rec']}"
    print("  test_revert_still_uses_d5_inverted: PASS")


def test_missing_horizon_field_excludes_name_not_crash():
    # A young listing with <126 bars has d126=None -- must be excluded from
    # mom126 ranking, not crash and not silently rank as the lowest value.
    rows = [
        _row("YOUNG", d5=99.0, d126=None),
        _row("B", d126=10.0), _row("C", d126=0.0), _row("D", d126=-10.0),
        _row("E", d126=5.0), _row("F", d126=-5.0),
    ]
    orig_rules, orig_regime = WD._zone_rules, WD._zone_regime
    WD._zone_rules = lambda: {"US": {"rule": "mom126"}}
    WD._zone_regime = lambda: {}
    try:
        WD.assign_recommendations(rows)
    finally:
        WD._zone_rules, WD._zone_regime = orig_rules, orig_regime
    by_sym = {r["symbol"]: r for r in rows}
    assert by_sym["YOUNG"]["rec"] == "HOLD", \
        f"a name with no d126 must fall back to its default rec (HOLD/zone), not be ranked, got {by_sym['YOUNG']['rec']}"
    print("  test_missing_horizon_field_excludes_name_not_crash: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
