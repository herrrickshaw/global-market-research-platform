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


def _rank_under(rule, rows, mkt="US"):
    orig_rules, orig_regime = WD._zone_rules, WD._zone_regime
    WD._zone_rules = lambda: {}
    WD._zone_regime = lambda: {mkt: {"active_rule": rule, "current_regime": "bull"}}
    try:
        WD.assign_recommendations(rows)
    finally:
        WD._zone_rules, WD._zone_regime = orig_rules, orig_regime
    return {r["symbol"]: r for r in rows}


def test_hi52_buys_names_nearest_their_high():
    rows = [dict(_row(s), market="KR", hi52=v) for s, v in
            [("AT_HIGH", 0.0), ("NEAR", -3.0), ("MID1", -15.0), ("MID2", -18.0),
             ("FAR", -40.0), ("FAREST", -55.0)]]
    by = _rank_under("hi52", rows, "KR")
    assert by["AT_HIGH"]["rec"] == "BUY" and by["FAREST"]["rec"] == "SELL", \
        {k: v["rec"] for k, v in by.items()}
    assert by["AT_HIGH"]["rec_rule"] == "hi52"
    print("  test_hi52_buys_names_nearest_their_high: PASS")


def test_lowvol_buys_calmest_names():
    rows = [dict(_row(s), lowvol=v) for s, v in
            [("CALM", -0.8), ("CALM2", -1.0), ("M1", -2.0), ("M2", -2.2),
             ("WILD", -5.0), ("WILD2", -6.0)]]
    by = _rank_under("lowvol", rows)
    assert by["CALM"]["rec"] == "BUY" and by["WILD2"]["rec"] == "SELL", \
        {k: v["rec"] for k, v in by.items()}
    print("  test_lowvol_buys_calmest_names: PASS")


def test_health_notes_flags_flipped_and_decaying_not_healthy():
    health = {
        "KR": {"asof": "2026-10-23", "signals": {"rev5": {"status": "FLIPPED", "recent_ic": -0.04}}},
        "IN": {"asof": "2026-10-23", "signals": {"hi52": {"status": "DECAYING", "recent_ic": 0.01}}},
        "US": {"asof": "2026-10-23", "signals": {"mom126": {"status": "HEALTHY", "recent_ic": 0.03}}},
    }
    notes = WD.health_notes({"KR": "revert", "IN": "hi52", "US": "mom126"}, health,
                            today="2026-10-26")
    text = " ".join(notes)
    assert "FLIPPED" in text and "-0.040" in text, text
    assert "DECAYING" in text
    assert "6mo-momentum" not in text, "a HEALTHY rule must not be flagged"
    assert "over 45 days old" not in text
    print("  test_health_notes_flags_flipped_and_decaying_not_healthy: PASS")


def test_health_notes_reports_stale_file_and_tolerates_missing():
    health = {"JP": {"asof": "2026-07-01", "signals": {}}}
    notes = WD.health_notes({"JP": "mom126", "EU": "revert"}, health, today="2026-10-26")
    assert len(notes) == 1 and "JP" in notes[0] and "over 45 days old" in notes[0], notes
    assert WD.health_notes({"US": "trend"}, {}) == []
    print("  test_health_notes_reports_stale_file_and_tolerates_missing: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
