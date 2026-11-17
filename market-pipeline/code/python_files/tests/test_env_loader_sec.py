"""``env_loader.sec_user_agent`` — the one place the SEC EDGAR contact comes from.

Seven modules used to hardcode a personal address in their User-Agent. The
address now comes from SEC_CONTACT_EMAIL; these tests pin the header shape,
the precedence (environment over credential file) and the no-contact fallback.
"""
from __future__ import annotations

import pytest

import env_loader as env


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """No real credential files, no leftover environment, warning flag reset."""
    monkeypatch.setattr(env, "_files", lambda: {})
    monkeypatch.delenv("SEC_CONTACT_EMAIL", raising=False)
    monkeypatch.setattr(env, "_SEC_WARNED", False)


def test_header_is_app_name_then_contact(monkeypatch):
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "ops@example.com")
    assert env.sec_user_agent() == {"User-Agent": "market-research ops@example.com"}
    assert env.sec_user_agent("StockScanner") == {"User-Agent": "StockScanner ops@example.com"}


def test_credential_file_is_used_when_env_is_unset(monkeypatch):
    monkeypatch.setattr(env, "_files", lambda: {"SEC_CONTACT_EMAIL": "file@example.com"})
    assert env.sec_user_agent()["User-Agent"].endswith(" file@example.com")


def test_environment_wins_over_credential_file(monkeypatch):
    monkeypatch.setattr(env, "_files", lambda: {"SEC_CONTACT_EMAIL": "file@example.com"})
    monkeypatch.setenv("SEC_CONTACT_EMAIL", "env@example.com")
    assert env.sec_user_agent()["User-Agent"].endswith(" env@example.com")


def test_missing_contact_still_sends_a_header_and_warns_once(capsys):
    first = env.sec_user_agent("StockScanner")
    second = env.sec_user_agent("StockScanner")
    assert first == second == {"User-Agent": "StockScanner"}
    err = capsys.readouterr().err
    assert err.count("SEC_CONTACT_EMAIL is not set") == 1


def test_no_source_module_hardcodes_a_contact_address():
    """The address must not creep back into any SEC caller."""
    import re
    from pathlib import Path
    root = Path(env.__file__).resolve().parent
    offenders = []
    for f in ("universe_sources.py", "sec_fundamentals.py", "earnings_dates_sec_8k.py",
              "us_fundamentals_edgar.py", "backtest_screeners.py", "full_us_market_scan.py",
              "symbol_master.py"):
        text = (root / f).read_text(errors="replace")
        for m in re.finditer(r"User-Agent[^\n]*", text):
            if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", m.group(0)):
                offenders.append(f"{f}: {m.group(0)[:60]}")
    assert offenders == []
