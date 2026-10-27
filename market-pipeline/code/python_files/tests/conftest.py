"""Shared fixtures for the mailer send-gate test suite.

Hermetic by construction: nothing here touches the network, Postgres, Cassandra,
the real scan workbooks or ``state/``. Every module under test reaches those
through a small number of seams (``price_sources.fetch_all``,
``scan_price_reconcile.fresh_quotes`` / ``warehouse_prev_close``,
``send_alert._brief_actually_sent_since``'s state file) and the fixtures below
replace exactly those seams.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# price_sources opens its accuracy ledger lazily; never let a test write the
# real one. send_alert reads SMTP creds through env_loader; a test must never
# be able to send.
os.environ.setdefault("PRICE_SOURCES_DB", ":memory:")
for _k in ("SMTP_USER", "SMTP_PASS", "SMTP_TO", "GMAIL_APP_PASSWORD"):
    os.environ.pop(_k, None)


@pytest.fixture
def today() -> dt.date:
    return dt.date.today()


@pytest.fixture
def scan_workbook(tmp_path):
    """Factory: write a minimal All_Stocks workbook named like the real scans."""
    import pandas as pd

    def _make(market_dir: str, prefix: str, rows: list[dict], stamp: dt.date | None = None,
              hhmm: str = "0300") -> Path:
        d = tmp_path / market_dir
        d.mkdir(parents=True, exist_ok=True)
        stamp = stamp or dt.date.today()
        p = d / f"{prefix}_{stamp:%Y%m%d}_{hhmm}.xlsx"
        pd.DataFrame(rows).to_excel(p, sheet_name="All_Stocks", index=False)
        return p

    return _make
