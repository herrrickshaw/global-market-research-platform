from datetime import date

from jobsearch.connections import load_connections, parse_date

SAMPLE = "tests/fixtures/connections_sample.csv"


def test_preamble_is_skipped_and_rows_parse():
    conns = load_connections(SAMPLE)
    assert [c.first_name for c in conns][:2] == ["Asha", "Bruno"]
    assert conns[0].company == "Shell plc"


def test_nameless_placeholder_rows_are_dropped():
    """LinkedIn emits date-only rows for deactivated profiles; they carry no signal."""
    conns = load_connections(SAMPLE)
    assert all(c.first_name or c.last_name for c in conns)
    assert len(conns) == 6  # 7 data rows minus 1 placeholder


def test_dates_parse():
    assert parse_date("12 Mar 2024") == date(2024, 3, 12)
    assert parse_date("") is None
    assert parse_date("not a date") is None
