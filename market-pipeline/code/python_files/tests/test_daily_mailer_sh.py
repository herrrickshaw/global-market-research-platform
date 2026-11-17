"""``daily_mailer.sh`` lock and chain behaviour, run in a sandbox.

The script is copied into a temp tree with a stub ``.venv/bin/python3`` that
records every invocation and exits 0, so no scan, no email and no research
chain can run. What is under test is the shell logic that decided whether a
brief was lost on 2026-08-15 (lock exit 0) and 2026-08-25 (false SEND LOST).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "daily_mailer.sh"
LOCK = Path("/tmp/daily_pipeline.lock")

STUB = f"""#!/bin/bash
# records argv, swallows stdin, succeeds — unless the script name is listed in
# FAIL_ON (one per line), in which case it exits 1 like a gate that said no.
# brief_state.py is the one script run for real: the lock branch's decision
# depends on what it prints, and it is pure stdlib reading one JSON file.
root="$(dirname "$0")/../.."
echo "$@" >> "$root/calls.log"
if [ "$1" = "brief_state.py" ]; then
  BRIEF_STATE_FILE="$root/state/last_brief_sent.json" exec {sys.executable} {ROOT}/brief_state.py "${{@:2}}"
fi
cat >/dev/null
if [ -f "$root/FAIL_ON" ]; then
  for a in "$@"; do
    if grep -qxF "$a" "$root/FAIL_ON"; then
      # a failing price gate writes its reason the way the real one does
      [ "$a" = "price_gate.py" ] && [ -f "$root/GATE_REASON" ] \\
        && cp "$root/GATE_REASON" "$root/state/price_gate_reason.txt"
      exit 1
    fi
  done
fi
exit 0
"""


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    if LOCK.exists():
        pytest.skip("real /tmp/daily_pipeline.lock present — a pipeline run is in progress")
    src = SCRIPT.read_text()
    # cap() polls every CAP_POLL seconds per step; with every step stubbed to
    # exit instantly that is pure dead time. 1s keeps a full phase under a minute.
    assert "CAP_POLL=5\n" in src, "cap() poll interval moved — update the test harness"
    (tmp_path / "daily_mailer.sh").write_text(src.replace("CAP_POLL=5\n", "CAP_POLL=1\n", 1))
    # the research chain must be an inert stub too, in case a path ever reaches it
    (tmp_path / "daily_research.sh").write_text("#!/bin/bash\necho research >> calls.log\n")
    os.chmod(tmp_path / "daily_research.sh", 0o755)
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    (venv / "python3").write_text(STUB)
    os.chmod(venv / "python3", 0o755)
    (tmp_path / "state").mkdir()
    # caffeinate is harmless but noisy; hide it from PATH
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    yield tmp_path
    if LOCK.exists() and (LOCK / "pid").exists():
        try:
            if int((LOCK / "pid").read_text().strip()) == os.getpid():
                shutil.rmtree(LOCK)
        except ValueError:
            pass


def run(sandbox: Path, *args: str, timeout=300) -> subprocess.CompletedProcess:
    # stdin=DEVNULL: the stub python drains stdin, and the real script feeds the
    # state-file reader a heredoc; neither may ever block on the test runner's tty.
    return subprocess.run(["bash", "daily_mailer.sh", *args], cwd=sandbox, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=timeout)


@pytest.fixture
def held_lock():
    """Hold the real lock with a live pid (this test process) for the test's duration."""
    LOCK.mkdir()
    (LOCK / "pid").write_text(str(os.getpid()))
    try:
        yield
    finally:
        shutil.rmtree(LOCK, ignore_errors=True)


class TestLock:
    def test_2026_08_15_send_blocked_by_lock_fails_loudly_with_exit_75(self, sandbox, held_lock):
        r = run(sandbox, "--send")
        assert r.returncode == 75, r.stdout + r.stderr
        assert "SEND LOST" in r.stdout
        calls = (sandbox / "calls.log").read_text()
        assert "send_alert.py" in calls and "send lost" in calls

    def test_2026_08_25_send_blocked_after_a_real_send_today_is_quiet_exit_0(self, sandbox, held_lock):
        (sandbox / "state" / "last_brief_sent.json").write_text(json.dumps({
            "sent_at": dt.datetime.now().isoformat(timespec="seconds"),
            "subject": "Daily Market Brief", "to": "x", "pid": 1}))
        r = run(sandbox, "--send")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "not a lost send" in r.stdout
        assert "send_alert.py" not in (sandbox / "calls.log").read_text() \
            if (sandbox / "calls.log").exists() else True

    def test_data_phase_blocked_by_lock_is_a_plain_no_op_exit_0(self, sandbox, held_lock):
        r = run(sandbox, "--data")
        assert r.returncode == 0
        assert "already running" in r.stdout
        assert not (sandbox / "calls.log").exists()

    def test_stale_lock_from_dead_pid_is_cleared(self, sandbox):
        LOCK.mkdir()
        (LOCK / "pid").write_text("999999")        # no such process
        try:
            r = run(sandbox, "--send", "--draft", timeout=120)
            assert "already running" not in r.stdout
            assert "=== daily mailer" in r.stdout
        finally:
            shutil.rmtree(LOCK, ignore_errors=True)


def calls(sandbox: Path) -> list[str]:
    p = sandbox / "calls.log"
    return p.read_text().splitlines() if p.exists() else []


class TestSendGates:
    """Steps [13/13] -> [SEND]: the wiring between the two gates and the mailer."""

    def test_gates_pass_then_send_mailer_runs_once_with_draft_flag(self, sandbox):
        r = run(sandbox, "--send", "--draft")
        assert r.returncode == 0
        sends = [c for c in calls(sandbox) if c.startswith("send_mailer.py")]
        assert sends == ["send_mailer.py --send --draft"], sends
        assert "send SUPPRESSED" not in r.stdout

    def test_2026_07_15_failed_gate_suppresses_and_saves_a_draft(self, sandbox):
        (sandbox / "FAIL_ON").write_text("price_gate.py\n")
        r = run(sandbox, "--send", "--draft")
        assert "send SUPPRESSED — price gate:" in r.stdout
        c = calls(sandbox)
        assert "send_mailer.py --draft" in c, "a suppressed send must still save the draft"
        assert not any(x == "send_mailer.py --send --draft" for x in c)
        alert = [x for x in c if x.startswith("send_alert.py")]
        assert alert and "NOT SENT" in alert[0]

    def test_2026_07_28_alert_carries_the_gates_own_reason(self, sandbox):
        # The gate writes WHY to a file; the shell must relay it verbatim rather
        # than guess which check failed (the 2026-07-28 and 2026-08-29 mislabels).
        (sandbox / "FAIL_ON").write_text("price_gate.py\n")
        (sandbox / "GATE_REASON").write_text("US: 5/8 stale vs live (worst NVDA 9.0%)")
        r = run(sandbox, "--send", "--draft")
        assert "price gate: US: 5/8 stale vs live (worst NVDA 9.0%)" in r.stdout
        alert = [x for x in calls(sandbox) if x.startswith("send_alert.py")]
        assert alert and "US: 5/8 stale vs live" in alert[0]

    def test_a_stale_reason_file_from_yesterday_is_not_reused(self, sandbox):
        # Every run clears the file before the gate; a pass leaves no reason behind.
        (sandbox / "state" / "price_gate_reason.txt").write_text("IN: yesterday's problem")
        r = run(sandbox, "--send", "--draft")
        assert r.returncode == 0 and "send SUPPRESSED" not in r.stdout
        assert not (sandbox / "state" / "price_gate_reason.txt").exists()

    def test_a_failed_scan_step_is_reported_but_does_not_block_the_gate(self, sandbox):
        (sandbox / "FAIL_ON").write_text("scan_bhavcopy.py\n")
        r = run(sandbox, "--send", "--draft")
        assert "scan failed" in r.stdout
        assert "[ALERT]" in r.stdout and "India: full screener scan" in r.stdout
        # the gate still ran — it is what decides, not the scan's exit code
        assert any(x.startswith("price_gate.py") for x in calls(sandbox))


class TestStepOrder:
    def test_watchlist_repair_runs_once_after_the_screens(self, sandbox):
        # 2026-10-27: the pre-screen repair was dropped; the post-screen pass is
        # the one that decides what watchlist_tiers syncs.
        run(sandbox, "--send", "--draft")
        c = calls(sandbox)
        repairs = [i for i, x in enumerate(c) if x == "watchlist_repair.py"]
        assert len(repairs) == 1, repairs
        screens = [i for i, x in enumerate(c)
                   if x.split()[0] in ("screen_value_rerating.py", "playbook_screener.py",
                                       "smallcap_screener.py")]
        assert len(screens) == 3 and max(screens) < repairs[0] < c.index("prediction_filter.py")


class TestChain:
    def test_draft_never_chains_research(self, sandbox):
        r = run(sandbox, "--send", "--draft", timeout=120)
        assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
        assert "chained: daily_research.sh" not in r.stdout
        assert "research" not in (sandbox / "calls.log").read_text()

    def test_header_records_which_phases_ran(self, sandbox):
        r = run(sandbox, "--data", timeout=120)
        assert "data=1 send=0" in r.stdout
        assert "chained" not in r.stdout


def test_stale_if_records_cause_only_when_upstream_failed():
    """stale_if tags dependents of a failed step and never touches control flow."""
    script = f"""set -uo pipefail
eval "$(sed -n '/^FAILURES=()/,/^}}/p' {SCRIPT})"
stale_if "India: bhavcopy refresh" "India scan" "rerun --data"
echo "n_before=${{#STALE[@]}}"
FAILURES+=("India: bhavcopy refresh")
stale_if "India: bhavcopy refresh" "India scan" "rerun --data"
stale_if "US: full market scan" "US report" "rerun --data"
echo "n_after=${{#STALE[@]}}"
echo "${{STALE[0]}}"
"""
    out = subprocess.run(["/bin/bash", "-c", script], capture_output=True, text=True).stdout
    assert "n_before=0" in out and "n_after=1" in out
    assert "India scan ran on cached data" in out and "remedy: rerun --data" in out
