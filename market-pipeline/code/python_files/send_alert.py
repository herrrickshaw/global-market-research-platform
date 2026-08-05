#!/usr/bin/env python3
# send_alert.py
# ==============
# Short failure-alert email for daily_pipeline.sh — sent when one or more
# pipeline steps fail, separate from (and usually arriving before) the main
# daily brief. Reuses the same Gmail SMTP credentials as send_mailer.py
# (GMAIL_USER, GMAIL_APP_PASSWORD, MAIL_TO); if they aren't configured this
# just logs what it would have sent instead of failing the pipeline.
#
#   python3 send_alert.py "US full market scan" "Japan full market scan"

from __future__ import annotations

import datetime as _dt
import os

import env_loader as _env
import smtplib
import sys
from email.mime.text import MIMEText


def _run_log_name(explicit: str | None = None) -> str:
    """The log for the run that is ENDING, which may have started yesterday.

    Callers pass --log, because only the caller knows which pipeline it is. The
    glob is a fallback and covers every pipeline that can raise an alert:
    pipeline_lib.sh sections write <section>_pipeline_YYYYMMDD.log, daily_mailer.sh
    writes daily_mailer_YYYYMMDD.log. Globbing daily_pipeline_* alone pointed the
    2026-08-05 ingest alert at daily_pipeline_20260728.log — a week-old log
    belonging to a script retired 2026-07-29.
    """
    if explicit:
        return explicit
    from pathlib import Path
    here = Path(__file__).resolve().parent
    logs = sorted({p for pat in ("*_pipeline_2*.log", "daily_mailer_2*.log")
                   for p in here.glob(pat)},
                  key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0].name if logs else (
        f"daily_mailer_{_dt.date.today():%Y%m%d}.log")


def _brief_actually_sent_since(when: _dt.datetime | None = None):
    """Was a brief sent since `when`? Returns the marker dict, or None.

    The FAILURES array is collected DURING the run and replayed at the end. In a
    9-hour run that means the alert can assert something that stopped being true
    hours earlier — which is exactly what happened on 2026-07-29: the mailer step
    at 22:55 recorded "NOT SENT — price reconcile flagged 3 market(s)", the
    underlying staleness was then fixed and a clean brief went out at 03:36, and
    at 08:08 the alert still announced the brief had not been sent. Two emails,
    the later one contradicting the earlier.

    So a claim this specific gets re-checked against evidence at alert time
    rather than trusted because it was true once.
    """
    import json
    from pathlib import Path
    m = Path(__file__).resolve().parent / "state" / "last_brief_sent.json"
    if not m.exists():
        return None
    try:
        d = json.loads(m.read_text())
        ts = _dt.datetime.fromisoformat(d["sent_at"])
    except Exception:                                          # noqa: BLE001
        return None
    # Default: anything sent today counts. A pipeline that starts before
    # midnight and alerts after it would wrongly discard a same-run send if this
    # compared against "today" alone, so the run's own start is passed in when
    # known and the fallback is generous rather than strict.
    if when is not None:
        return d if ts >= when else None
    return d if ts.date() == _dt.date.today() else None


def reconcile_failures(failed_steps: list) -> tuple[list, list]:
    """Split recorded failures into (still true, resolved since being recorded)."""
    sent = _brief_actually_sent_since()
    if not sent:
        return list(failed_steps), []
    live, resolved = [], []
    for s in failed_steps:
        if "NOT SENT" in s.upper():
            resolved.append(f"{s}  ->  RESOLVED: a brief WAS sent at "
                            f"{sent['sent_at']} ('{sent['subject'][:60]}')")
        else:
            live.append(s)
    return live, resolved


def send_alert(failed_steps: list, pipeline: str = "", log: str = "") -> bool:
    if not failed_steps:
        return True
    failed_steps, resolved = reconcile_failures(failed_steps)
    if not failed_steps and resolved:
        # Every failure turned out to be stale. Sending an alert here would be
        # the contradiction this function exists to prevent.
        print("  [alert] all recorded failures resolved before the run ended "
              "— no alert sent:")
        for r in resolved:
            print(f"    {r}")
        return True
    user = _env.get("GMAIL_USER")
    pw = _env.get("GMAIL_APP_PASSWORD")
    to = (_env.get("MAIL_TO") or user)
    today = _dt.date.today().strftime("%d %b %Y")
    # The log is named for the date the run STARTED. A run that crosses midnight
    # (this one began 22:36 and ended 08:08) would otherwise point the reader at
    # a file that does not exist.
    log_name = _run_log_name(log)
    # Name the pipeline that actually failed. Hardcoding daily_pipeline.sh sent an
    # alert on 2026-08-05 blaming a script retired a week earlier, for a failure
    # that came from ingest.sh.
    who = pipeline or log_name.split("_2")[0] or "pipeline"
    subject = f"⚠️ {who} — {len(failed_steps)} step(s) failed ({today})"
    body = (
        f"{len(failed_steps)} step(s) failed in today's {who} run ({today}):\n\n"
        + "\n".join(f"  - {s}" for s in failed_steps)
        + f"\n\nEach failed step falls back to cached/skipped data — the rest of the "
        f"pipeline still ran. Check {log_name} for details."
    )
    if resolved:
        # Shown, not silently dropped: the reader should be able to see that a
        # failure was recorded and then fixed, rather than wonder why an earlier
        # symptom went unmentioned.
        body += ("\n\nRecorded during the run but NO LONGER TRUE when it "
                 "finished:\n\n" + "\n".join(f"  - {r}" for r in resolved))
    if not (user and pw) or len(pw) < 16 or "PUT-YOUR" in pw:
        print(f"  [alert] no valid GMAIL_APP_PASSWORD set — alert not sent. Would have said:\n{body}")
        return False
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
    print(f"  [alert] sent '{subject}' -> {to}")
    return True


if __name__ == "__main__":
    # Hand-parsed, not argparse: the positionals are free-text failure labels
    # ("ingest: [3b/7] NSE/BSE extras (indices, ...)") and argparse mangles them.
    _args, _pipeline, _log = [], "", ""
    _it = iter(sys.argv[1:])
    for _a in _it:
        if _a == "--pipeline":
            _pipeline = next(_it, "")
        elif _a == "--log":
            _log = next(_it, "")
        else:
            _args.append(_a)
    send_alert(_args, pipeline=_pipeline, log=_log)
