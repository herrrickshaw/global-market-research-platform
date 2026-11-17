"""``send_alert`` must never announce a lost brief that is sitting in the inbox.

2026-07-29 and 2026-08-25 both produced that false alarm; the re-check against
``state/last_brief_sent.json`` is the fix and this pins it.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

import send_alert as sa


@pytest.fixture
def state_file(monkeypatch, tmp_path):
    """Point brief_state (the file's owner) at a temp record we control."""
    import brief_state
    p = tmp_path / "state" / "last_brief_sent.json"
    monkeypatch.setattr(brief_state, "STATE_FILE", p)

    def write(sent_at: dt.datetime, subject="Daily Market Brief"):
        p.parent.mkdir(exist_ok=True)
        p.write_text(json.dumps({"sent_at": sent_at.isoformat(timespec="seconds"),
                                 "subject": subject, "to": "x@example.com", "pid": 1}))
        return p

    return write


class TestBriefActuallySent:
    def test_missing_state_means_not_sent(self, monkeypatch, tmp_path):
        import brief_state
        monkeypatch.setattr(brief_state, "STATE_FILE", tmp_path / "nope.json")
        assert sa._brief_actually_sent_since() is None

    def test_sent_today_counts(self, state_file):
        state_file(dt.datetime.now().replace(microsecond=0))
        assert sa._brief_actually_sent_since() is not None

    def test_sent_yesterday_does_not_count(self, state_file):
        state_file(dt.datetime.now() - dt.timedelta(days=1))
        assert sa._brief_actually_sent_since() is None

    def test_explicit_run_start_wins_over_calendar_day(self, state_file):
        # A run that starts 23:50 and alerts 00:10 must still see its own send.
        sent = dt.datetime.now().replace(microsecond=0)
        state_file(sent)
        assert sa._brief_actually_sent_since(sent - dt.timedelta(minutes=5)) is not None
        assert sa._brief_actually_sent_since(sent + dt.timedelta(minutes=5)) is None

    def test_corrupt_state_is_treated_as_not_sent(self, state_file, tmp_path):
        (tmp_path / "state").mkdir(exist_ok=True)
        (tmp_path / "state" / "last_brief_sent.json").write_text("{not json")
        assert sa._brief_actually_sent_since() is None


class TestReconcileFailures:
    def test_without_a_send_every_failure_stands(self, monkeypatch, tmp_path):
        import brief_state
        monkeypatch.setattr(brief_state, "STATE_FILE", tmp_path / "nope.json")
        live, resolved = sa.reconcile_failures(["mailer: NOT SENT — gate", "India: scan"])
        assert live == ["mailer: NOT SENT — gate", "India: scan"] and resolved == []

    @pytest.mark.parametrize("claim", [
        "mailer: NOT SENT — brief failed external price validation",
        "send lost: lock held by pid 123, no brief for 2026-08-25",
        "SEND LOST — the brief did not go out",
    ])
    def test_every_lost_brief_phrasing_is_downgraded_after_a_real_send(self, state_file, claim):
        state_file(dt.datetime.now().replace(microsecond=0))
        live, resolved = sa.reconcile_failures([claim, "India: CCC scrape test"])
        assert live == ["India: CCC scrape test"]
        assert len(resolved) == 1 and "RESOLVED" in resolved[0]

    def test_unrelated_failures_are_never_downgraded(self, state_file):
        state_file(dt.datetime.now().replace(microsecond=0))
        live, resolved = sa.reconcile_failures(["US: full market scan", "TIMEOUT: [3/13]"])
        assert resolved == [] and len(live) == 2
