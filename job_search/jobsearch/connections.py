"""Parse the LinkedIn ``Connections.csv`` export.

The export is not a plain CSV: LinkedIn prepends 2-4 note lines before the real
header row, so a naive ``csv.DictReader`` reads the notes as column names and
every downstream field lookup silently returns None. ``_seek_header`` finds the
true header instead of assuming a fixed offset, because the note count varies
between exports.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from .models import Connection
from .normalize import repair_mojibake

EXPECTED_HEADER = "First Name"
_MAX_PREAMBLE_LINES = 12

# LinkedIn writes "21 Feb 2026"; older and localised exports vary.
_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y", "%d.%m.%Y")


def _seek_header(handle: io.TextIOBase) -> None:
    """Advance *handle* to the line after the real CSV header."""
    pos = handle.tell()
    for _ in range(_MAX_PREAMBLE_LINES):
        line = handle.readline()
        if not line:
            break
        if line.lstrip("﻿").startswith(EXPECTED_HEADER):
            handle.seek(pos)
            return
        pos = handle.tell()
    # No recognisable header: rewind and let DictReader try the first line.
    handle.seek(0)


def parse_date(value: str) -> date | None:
    v = (value or "").strip()
    if not v:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _clean(value: str | None) -> str:
    """Strip whitespace and undo any codepage round-trip damage.

    Exports pulled through a text-extraction layer can arrive with UTF-8 decoded
    as a single-byte codepage; repairing at parse time keeps every downstream
    join key and report clean.
    """
    return repair_mojibake((value or "").strip())


def iter_connections(path: str | Path) -> Iterator[Connection]:
    """Yield a Connection per data row of a LinkedIn connections export."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        _seek_header(fh)
        for row in csv.DictReader(fh):
            first = _clean(row.get("First Name"))
            last = _clean(row.get("Last Name"))
            if not (first or last):
                continue
            yield Connection(
                first_name=first,
                last_name=last,
                url=_clean(row.get("URL")),
                email=_clean(row.get("Email Address")),
                company=_clean(row.get("Company")),
                position=_clean(row.get("Position")),
                connected_on=parse_date(row.get("Connected On", "")),
            )


def load_connections(path: str | Path) -> list[Connection]:
    return list(iter_connections(path))
