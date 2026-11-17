"""scan_files.py — one answer to "which scan workbook, and from which day?"

Every scan writes `<prefix>_YYYYMMDD_HHMM.xlsx`. The send-path modules used
to carry their own copies of the regex that reads that stamp back, which is
how two gates could in principle disagree about what "today's scan" means.
`price_gate` and `validate_brief` both read it from here now.

The stamp is the day the workbook was BUILT. The session it holds is one
earlier (the 03:00 India build holds the previous close) — callers that need
the session ask `market_sessions`, not this module.
"""
from __future__ import annotations

import datetime as dt
import glob
import re
from pathlib import Path

_STAMP = re.compile(r"_(\d{8})_\d{4}\.xlsx$")

SCAN_GLOBS = {
    "IN": "indian_full_scan/indian_full_scan_*.xlsx",
    "US": "us_full_scan/us_full_scan_*.xlsx",
    "JP": "japan_scan/japan_market_scan_*.xlsx",
    "KR": "korea_scan/korea_market_scan_*.xlsx",
    "EU": "european_scan/european_market_scan_*.xlsx",
}


def latest(market: str, root: Path | str = ".") -> str:
    """Newest workbook on disk for `market`, or '' if there is none.

    Newest on DISK, not newest by stamp: the two agree unless someone copies an
    old file in, and the stamp check in `age_days` is what catches that.
    """
    files = sorted(glob.glob(str(Path(root) / SCAN_GLOBS[market])))
    return files[-1] if files else ""


def stamp(path: str) -> dt.date | None:
    """The build day encoded in the filename, or None if it carries none."""
    m = _STAMP.search(Path(path).name)
    if not m:
        return None
    try:
        return dt.datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def age_days(path: str, today: dt.date | None = None) -> int | None:
    """Days between the workbook's build day and today. None if unparseable."""
    d = stamp(path)
    if d is None:
        return None
    return ((today or dt.date.today()) - d).days


def staleness_note(path: str, today: dt.date | None = None) -> str:
    """'' if the workbook is today's, otherwise one line naming the real problem.

    A workbook left over from a day the scan did not run shows up downstream as
    ordinary price mismatches — true, but it points at the prices rather than at
    the missing run (Sat 2026-08-01: "1 price mismatch beyond 2.0%" when the
    fact was that Friday's file was still on disk because 03:00 never fired).
    """
    today = today or dt.date.today()
    age = age_days(path, today)
    if not age or age <= 0:
        return ""
    return (f"  ⚠ SCAN IS {age} DAY(S) OLD — {Path(path).name}; expected "
            f"{today:%Y-%m-%d}. The scan step did not run, so any mismatch "
            f"below is stale data, not a bad pick.")
