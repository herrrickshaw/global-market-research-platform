"""The brief's prediction section must survive an empty or missing input file.

2026-09-15 → 2026-10-27: reentry_engine wrote a 1-byte reports/reentry_candidates.csv
on every zero-pick day, pandas raised EmptyDataError on it, and the except around
the whole block dropped the verdict counts, RSI zones, sell-review and tier counts
with it — 21 of ~30 briefs shipped without the section.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

import send_mailer as sm

SCORES = (
    "market,symbol,status,mkt_trend,mkt_vol,stock_state,kalman_drift_ann_pct,"
    "markov_e21d_pct,asof,verdict,rsi,rsi_zone\n"
    "IN,TBZ,playbook,bear,HIGH,bear,333.4,-0.9,2026-10-26,DEMOTE (market bear),52.0,BUY\n"
    "US,RDY,watch,bull,LOW,bull,12.0,0.4,2026-10-26,ENTER-OK,41.0,HOLD\n"
    "IN,INFY,watch,bear,HIGH,bear,-3.0,-0.1,2026-10-26,DEMOTE (market bear),28.0,BUY\n"
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "watchlist_prediction_scores.csv").write_text(SCORES)
    return tmp_path


def test_2026_10_27_empty_reentry_candidates_does_not_kill_the_section(root):
    (root / "reports" / "reentry_candidates.csv").write_text("\n")      # the 1-byte file
    html = sm.prediction_section(root)
    assert "Prediction lens" in html
    assert "DEMOTE 2" in html and "ENTER-OK 1" in html
    assert "RSI zones" in html and "BUY 2" in html
    assert "Re-entry queue" not in html                                 # nothing to say, said nothing


def test_missing_optional_files_render_the_core_section(root):
    html = sm.prediction_section(root)
    assert "Prediction lens" in html and "DEMOTE 2" in html


def test_a_corrupt_optional_file_loses_only_its_own_line(root, capsys):
    (root / "reports" / "held_sell_review.csv").write_text("symbol,kalman_drift_ann_pct\nX,notanumber\n")
    html = sm.prediction_section(root)
    assert "Prediction lens" in html and "RSI zones" in html
    assert "SELL-REVIEW (held" not in html          # the footer's "SELL-REVIEW is advisory" stays
    assert "sell-review line skipped" in capsys.readouterr().out


def test_fresh_reentry_candidates_are_listed(root):
    (root / "reports" / "reentry_candidates.csv").write_text(
        "market,symbol,rsi\nIN,TBZ,31.0\nUS,RDY,29.5\n")
    html = sm.prediction_section(root)
    assert "Re-entry queue" in html and "IN:TBZ (rsi 31)" in html


def test_no_scores_file_means_no_section(tmp_path):
    assert sm.prediction_section(tmp_path) == ""


def test_stale_reentry_candidates_are_ignored(root):
    p = root / "reports" / "reentry_candidates.csv"
    p.write_text("market,symbol,rsi\nIN,TBZ,31.0\n")
    old = (dt.datetime.now() - dt.timedelta(days=3)).timestamp()
    import os
    os.utime(p, (old, old))
    assert "Re-entry queue" not in sm.prediction_section(root)
