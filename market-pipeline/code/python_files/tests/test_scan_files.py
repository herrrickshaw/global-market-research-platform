"""``scan_files`` — the one parser of scan-workbook filenames."""
from __future__ import annotations

import datetime as dt

import scan_files as sf

D = dt.date


def test_stamp_reads_the_build_day():
    assert sf.stamp("indian_full_scan/indian_full_scan_20261027_0300.xlsx") == D(2026, 10, 27)


def test_stamp_is_none_for_junk_or_impossible_dates():
    assert sf.stamp("notes.xlsx") is None
    assert sf.stamp("x_99999999_0000.xlsx") is None


def test_age_days_is_relative_to_the_given_today():
    p = "us_full_scan/us_full_scan_20261027_0314.xlsx"
    assert sf.age_days(p, today=D(2026, 10, 27)) == 0
    assert sf.age_days(p, today=D(2026, 10, 28)) == 1
    assert sf.age_days("junk.xlsx", today=D(2026, 10, 28)) is None


def test_staleness_note_silent_today_loud_yesterday():
    p = "indian_full_scan/indian_full_scan_20261027_0300.xlsx"
    assert sf.staleness_note(p, today=D(2026, 10, 27)) == ""
    note = sf.staleness_note(p, today=D(2026, 10, 28))
    assert "1 DAY(S) OLD" in note and "scan step did not run" in note


def test_latest_picks_the_newest_file_per_market(tmp_path):
    d = tmp_path / "indian_full_scan"
    d.mkdir()
    for s in ("20261026_0300", "20261027_0300"):
        (d / f"indian_full_scan_{s}.xlsx").write_bytes(b"")
    assert sf.latest("IN", root=tmp_path).endswith("indian_full_scan_20261027_0300.xlsx")
    assert sf.latest("US", root=tmp_path) == ""
