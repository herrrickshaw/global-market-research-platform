#!/usr/bin/env python3
"""brief_state.py — the one reader and writer of `state/last_brief_sent.json`.

That file is the authoritative answer to "did a brief actually go out?". It is
written by send_mailer after `sendmail()` returns, and consulted by:

  * send_alert, before it repeats a "NOT SENT" claim recorded hours earlier
    (2026-07-29: alert at 08:08 contradicted a brief sent at 03:36);
  * daily_mailer.sh, when a 06:30 send finds the lock held and must decide
    between SEND LOST and "a redundant peer, stay quiet" (2026-08-25);
  * anything else that asks the question later.

Those used to be four separate parsers, one of them a Python heredoc inside
the shell script. One module, one path, one notion of "sent today".

    python3 brief_state.py --sent-today   # prints "<sent_at>|<subject>" or nothing

`BRIEF_STATE_FILE` overrides the path (tests, sandboxes); otherwise it is
`state/last_brief_sent.json` next to this file.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

STATE_FILE = Path(os.environ.get("BRIEF_STATE_FILE")
                  or Path(__file__).resolve().parent / "state" / "last_brief_sent.json")


def last_sent() -> dict | None:
    """The last send record, or None if there is none or it is unreadable."""
    try:
        d = json.loads(STATE_FILE.read_text())
        dt.datetime.fromisoformat(d["sent_at"])      # must parse, or it is no record
        return d
    except Exception:                                                  # noqa: BLE001
        return None


def sent_since(when: dt.datetime | None = None, today: dt.date | None = None) -> dict | None:
    """The record if a brief went out since `when` (or today, when `when` is None).

    A run that starts before midnight and asks after it would wrongly discard
    its own send if this compared against "today" alone, so callers that know
    their start time pass it; the calendar-day fallback is generous on purpose.
    """
    d = last_sent()
    if d is None:
        return None
    ts = dt.datetime.fromisoformat(d["sent_at"])
    if when is not None:
        return d if ts >= when else None
    return d if ts.date() == (today or dt.date.today()) else None


def record_sent(subject: str, to: str, pid: int | None = None) -> bool:
    """Write the record. Never raises: a marker failure must not turn a
    successful send into a failure. Returns False if it could not write."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({
            "sent_at": dt.datetime.now().isoformat(timespec="seconds"),
            "subject": subject, "to": to, "pid": pid if pid is not None else os.getpid(),
        }, indent=2))
        return True
    except Exception as e:                                             # noqa: BLE001
        print(f"  (send marker not written: {str(e)[:60]})")
        return False


def main(argv: list[str]) -> int:
    if "--sent-today" in argv:
        d = sent_since()
        if d:
            sys.stdout.write(f"{d['sent_at']}|{d.get('subject', '')[:60]}")
        return 0
    d = last_sent()
    print(json.dumps(d, indent=2) if d else "no send recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
