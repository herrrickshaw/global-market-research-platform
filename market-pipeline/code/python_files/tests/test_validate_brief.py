"""Send gate 2 of 2: ``validate_brief`` — the external-witness jury.

Every test here is a documented incident replayed as a fixture. The dates in the
names are the mornings the real gate got it wrong (or right); if one of these
goes red, the brief will be suppressed or shipped for the same reason again.
"""
from __future__ import annotations

import datetime as dt

import pytest

import validate_brief as vb

D = dt.date


def ans(price: float, date: dt.date, ours: float, tol: float = 2.0) -> dict:
    diff = abs(ours - price) / price * 100
    return {"price": price, "date": date, "diff_pct": round(diff, 2),
            "verdict": "agree" if diff <= tol else "disagree"}


# ── _judge: one name's verdict ───────────────────────────────────────────────

class TestJudge:
    def test_no_witness_is_unverifiable_not_a_failure(self):
        # AUSTENG-class BSE-only names 404 everywhere; that says nothing about the pick.
        r = vb._judge("AUSTENG", 100.0, {}, D(2026, 10, 26))
        assert r["status"] == "skip"

    def test_single_current_witness_that_agrees_passes(self):
        r = vb._judge("INFY", 1166.0, {"yfinance": ans(1166.0, D(2026, 10, 26), 1166.0)},
                      D(2026, 10, 26))
        assert r["status"] == "ok"

    def test_single_current_witness_that_disagrees_is_a_mismatch(self):
        # The MODISONLTD shape: our price frozen, the one witness current.
        r = vb._judge("MODISONLTD", 100.0, {"yfinance": ans(130.0, D(2026, 10, 26), 100.0)},
                      D(2026, 10, 26))
        assert r["status"] == "MISMATCH"

    def test_2026_10_27_bse_lone_lagging_witness_abstains(self):
        """The suppression this suite was written after.

        BSE Ltd is answered only by yfinance (alphavantage rejects BSE.BSE,
        twelvedata 404s). yfinance quoted the 10-23 close while ours was the
        correct 10-26 bhavcopy close; the lone stale vote blocked a good brief.
        """
        r = vb._judge("BSE", 3359.0, {"yfinance": ans(3230.8, D(2026, 10, 23), 3359.0)},
                      session=D(2026, 10, 26))
        assert r["status"] == "skip", r
        assert "abstained" in r["why"]

    def test_lag_beyond_window_still_votes(self):
        # Seven weeks behind is not "a few days behind" — that IS the stale-feed bug.
        lag = vb.WITNESS_LAG_DAYS + 1
        r = vb._judge("X", 100.0,
                      {"yfinance": ans(130.0, D(2026, 10, 26) - dt.timedelta(days=lag), 100.0)},
                      session=D(2026, 10, 26))
        assert r["status"] == "MISMATCH"

    def test_lag_exactly_at_window_abstains(self):
        on_edge = D(2026, 10, 26) - dt.timedelta(days=vb.WITNESS_LAG_DAYS)
        r = vb._judge("X", 100.0, {"yfinance": ans(130.0, on_edge, 100.0)},
                      session=D(2026, 10, 26))
        assert r["status"] == "skip"

    def test_2026_10_20_older_session_witness_abstains_when_a_newer_one_exists(self):
        # yfinance HDFCBANK @10-16 (2.31% off) vs alphavantage @10-19 (0.06%).
        r = vb._judge("HDFCBANK", 688.05, {
            "yfinance": ans(704.0, D(2026, 10, 16), 688.05),
            "alphavantage": ans(688.2, D(2026, 10, 19), 688.05),
        }, session=D(2026, 10, 19))
        assert r["status"] == "ok"
        assert r["stale"] == ["yfinance"]
        assert r["agree"] == ["alphavantage"]

    def test_2026_08_29_tie_between_current_witnesses_is_a_mismatch(self):
        # A split jury is not a confirmation — this is why a third witness exists.
        r = vb._judge("INFY", 1166.0, {
            "yfinance": ans(1166.0, D(2026, 10, 26), 1166.0),
            "alphavantage": ans(1230.0, D(2026, 10, 26), 1166.0),
        }, session=D(2026, 10, 26))
        assert r["status"] == "MISMATCH"

    def test_majority_of_current_witnesses_wins(self):
        r = vb._judge("INFY", 1166.0, {
            "yfinance": ans(1166.0, D(2026, 10, 26), 1166.0),
            "alphavantage": ans(1230.0, D(2026, 10, 26), 1166.0),
            "twelvedata": ans(1166.0, D(2026, 10, 26), 1166.0),
        }, session=D(2026, 10, 26))
        assert r["status"] == "ok"
        assert r["disagree"] == ["alphavantage"]

    def test_our_stale_price_against_current_witnesses_is_caught(self):
        # If OUR number is the frozen one, every current witness disagrees.
        r = vb._judge("X", 100.0, {
            "yfinance": ans(130.0, D(2026, 10, 26), 100.0),
            "alphavantage": ans(130.2, D(2026, 10, 26), 100.0),
        }, session=D(2026, 10, 26))
        assert r["status"] == "MISMATCH"


# ── helpers ───────────────────────────────────────────────────────────────────

class TestScanDating:
    def test_scan_date_parses_the_filename_stamp(self):
        assert vb._scan_date("indian_full_scan/indian_full_scan_20261027_0300.xlsx") == D(2026, 10, 27)

    def test_scan_date_falls_back_to_today_on_junk(self, today):
        assert vb._scan_date("indian_full_scan/weird.xlsx") == today

    def test_staleness_note_silent_for_today(self, today):
        assert vb._scan_staleness_note(f"x/indian_full_scan_{today:%Y%m%d}_0300.xlsx") == ""

    def test_staleness_note_names_the_missing_run_for_yesterday(self, today):
        y = today - dt.timedelta(days=1)
        note = vb._scan_staleness_note(f"x/indian_full_scan_{y:%Y%m%d}_0300.xlsx")
        assert "1 DAY(S) OLD" in note and "scan step did not run" in note

    def test_session_is_newest_date_any_source_quoted(self):
        fetched = [("A", 1.0, {"s": {"date": D(2026, 10, 23)}}),
                   ("B", 1.0, {"s": {"date": D(2026, 10, 26)}, "t": {"date": D(2026, 10, 20)}})]
        assert vb._session(fetched) == D(2026, 10, 26)
        assert vb._session([]) is None


# ── validate(): the whole gate with the sources stubbed ──────────────────────

def _install_sources(monkeypatch, table: dict[str, dict[str, dict]]):
    """table[symbol][source] -> {"price","date"} | {"error"}; absent source = error."""
    import price_sources

    names = sorted({s for v in table.values() for s in v})
    monkeypatch.setattr(price_sources, "SOURCES", {n: None for n in names})

    def fetch_all(sym, asof, polite=0.0):
        got = table.get(sym, {})
        return {n: got.get(n, {"error": "404"}) for n in names}

    monkeypatch.setattr(price_sources, "fetch_all", fetch_all)
    monkeypatch.setattr(price_sources, "record", lambda rows: None)


@pytest.fixture
def workbook(monkeypatch, scan_workbook, today):
    rows = [{"Symbol": s, "LTP": p, "Median_Turnover": t} for s, p, t in [
        ("HDFCBANK", 688.05, 900), ("ICICIBANK", 1403.0, 800), ("RELIANCE", 1201.8, 700),
        ("INFY", 1166.0, 600), ("BHARTIARTL", 1917.5, 500), ("BSE", 3359.0, 400),
        ("AUSTENG", 12.0, 300),
    ]]
    p = scan_workbook("indian_full_scan", "indian_full_scan", rows, today)
    monkeypatch.setattr(vb, "_latest_scan", lambda: str(p))
    return p


def _agreeing(sym_prices: dict, date: dt.date, sources=("yfinance", "alphavantage")) -> dict:
    return {s: {src: {"price": p, "date": date} for src in sources} for s, p in sym_prices.items()}


SAMPLE = {"HDFCBANK": 688.05, "ICICIBANK": 1403.0, "RELIANCE": 1201.8,
          "INFY": 1166.0, "BHARTIARTL": 1917.5, "BSE": 3359.0}


class TestValidateGate:
    def test_clean_day_passes(self, workbook, monkeypatch):
        _install_sources(monkeypatch, _agreeing(SAMPLE, D(2026, 10, 26)))
        r = vb.validate(sample=6, tol=2.0)
        assert r["ok"], r["reason"]
        assert r["verified"] >= vb.MIN_VERIFIED

    def test_2026_10_27_replay_lone_stale_bse_no_longer_suppresses(self, workbook, monkeypatch):
        table = _agreeing({k: v for k, v in SAMPLE.items() if k != "BSE"}, D(2026, 10, 26))
        table["BSE"] = {"yfinance": {"price": 3230.8, "date": D(2026, 10, 23)}}
        _install_sources(monkeypatch, table)
        r = vb.validate(sample=6, tol=2.0)
        assert r["ok"], r["reason"]
        bse = next(c for c in r["checks"] if c["symbol"] == "BSE")
        assert bse["status"] == "skip"

    def test_one_real_mismatch_suppresses_and_names_it(self, workbook, monkeypatch):
        table = _agreeing(SAMPLE, D(2026, 10, 26))
        table["RELIANCE"] = {s: {"price": 1300.0, "date": D(2026, 10, 26)}
                             for s in ("yfinance", "alphavantage")}
        _install_sources(monkeypatch, table)
        r = vb.validate(sample=6, tol=2.0)
        assert not r["ok"]
        assert "RELIANCE" in r["reason"] and "mismatch" in r["reason"]

    def test_too_few_verifiable_names_cannot_confirm(self, workbook, monkeypatch):
        table = _agreeing({"HDFCBANK": 688.05, "ICICIBANK": 1403.0}, D(2026, 10, 26))
        _install_sources(monkeypatch, table)
        r = vb.validate(sample=6, tol=2.0)
        assert not r["ok"]
        assert "cannot confirm" in r["reason"]

    def test_one_name_frozen_at_older_session_is_flagged_off(self, workbook, monkeypatch):
        # MODISONLTD: liquid names trade daily, so one quoted only at an older
        # session than the rest — beyond the abstain window — is stale data.
        table = _agreeing(SAMPLE, D(2026, 10, 26))
        old = D(2026, 10, 26) - dt.timedelta(days=vb.WITNESS_LAG_DAYS + 3)
        table["BHARTIARTL"] = {s: {"price": 1917.5, "date": old}
                               for s in ("yfinance", "alphavantage")}
        _install_sources(monkeypatch, table)
        r = vb.validate(sample=6, tol=2.0)
        assert not r["ok"]
        assert "latest session" in r["reason"] and "BHARTIARTL" in r["reason"]

    def test_silent_source_is_reported_mute_and_does_not_vote(self, workbook, monkeypatch):
        table = _agreeing(SAMPLE, D(2026, 10, 26), sources=("yfinance",))
        for s in table.values():
            s["twelvedata"] = {"error": "td: no TWELVEDATA_KEY"}
        _install_sources(monkeypatch, table)
        r = vb.validate(sample=6, tol=2.0)
        assert r["ok"], r["reason"]
        assert "twelvedata" in r["mute"]

    def test_no_workbook_fails_closed(self, monkeypatch):
        monkeypatch.setattr(vb, "_latest_scan", lambda: "")
        r = vb.validate(sample=6, tol=2.0)
        assert not r["ok"] and "no India scan workbook" in r["reason"]
