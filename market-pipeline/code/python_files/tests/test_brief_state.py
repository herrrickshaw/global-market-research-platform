"""``brief_state`` — the one owner of the last-sent record."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

import brief_state as bs

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def state(monkeypatch, tmp_path):
    p = tmp_path / "state" / "last_brief_sent.json"
    monkeypatch.setattr(bs, "STATE_FILE", p)
    return p


def test_record_then_read_round_trips(state):
    assert bs.record_sent("Brief", "x@example.com", pid=42) is True
    d = bs.last_sent()
    assert d["subject"] == "Brief" and d["to"] == "x@example.com" and d["pid"] == 42
    assert dt.datetime.fromisoformat(d["sent_at"]).date() == dt.date.today()


def test_record_creates_the_state_directory(state):
    assert not state.parent.exists()
    bs.record_sent("Brief", "x")
    assert state.exists()


def test_unreadable_or_absent_record_is_none(state):
    assert bs.last_sent() is None
    state.parent.mkdir()
    state.write_text("{not json")
    assert bs.last_sent() is None
    state.write_text(json.dumps({"subject": "no sent_at"}))
    assert bs.last_sent() is None


def test_sent_since_uses_run_start_when_given(state):
    bs.record_sent("Brief", "x")
    now = dt.datetime.now()
    assert bs.sent_since(now - dt.timedelta(minutes=1)) is not None
    assert bs.sent_since(now + dt.timedelta(minutes=1)) is None


def test_sent_since_falls_back_to_calendar_day(state):
    state.parent.mkdir()
    y = dt.datetime.now() - dt.timedelta(days=1)
    state.write_text(json.dumps({"sent_at": y.isoformat(timespec="seconds"), "subject": "old"}))
    assert bs.sent_since() is None
    assert bs.sent_since(today=y.date()) is not None


def test_cli_sent_today_prints_record_or_nothing(tmp_path):
    p = tmp_path / "s.json"
    env = {"BRIEF_STATE_FILE": str(p), "PATH": "/usr/bin:/bin"}
    out = subprocess.run([sys.executable, str(ROOT / "brief_state.py"), "--sent-today"],
                         env=env, capture_output=True, text=True, check=True).stdout
    assert out == ""
    p.write_text(json.dumps({"sent_at": dt.datetime.now().isoformat(timespec="seconds"),
                             "subject": "📈 Daily Market Brief — today"}))
    out = subprocess.run([sys.executable, str(ROOT / "brief_state.py"), "--sent-today"],
                         env=env, capture_output=True, text=True, check=True).stdout
    assert out.startswith(f"{dt.date.today():%Y-%m-%d}T") and out.endswith("|📈 Daily Market Brief — today")
