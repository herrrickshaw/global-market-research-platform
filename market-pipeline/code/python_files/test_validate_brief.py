#!/usr/bin/env python3
"""test_validate_brief.py — a name's ONLY witness lagging a few sessions must
abstain, not fail the send (2026-10-27: BSE Ltd was answered only by yfinance
@10-23, 3.97% off our correct 10-26 bhavcopy close of 3359, and the lone stale
vote suppressed a correct brief). A witness frozen for weeks must still fail it.
Run: python3 test_validate_brief.py
"""
import datetime as dt

import pandas as pd

import price_sources
import validate_brief as vb

D23, D26, D27 = dt.date(2026, 10, 23), dt.date(2026, 10, 26), dt.date(2026, 10, 27)

# The 2026-10-27 06:36 run, from state/source_accuracy.db.
OURS = {"HDFCBANK": 688.05, "ICICIBANK": 1403.0, "RELIANCE": 1201.8,
        "INFY": 1166.0, "BHARTIARTL": 1917.5, "BSE": 3359.0}
YF = {"HDFCBANK": 692.80, "ICICIBANK": 1394.20, "RELIANCE": 1190.00,
      "INFY": 1153.80, "BHARTIARTL": 1892.10, "BSE": 3230.80}
AV = {"HDFCBANK": 688.20, "ICICIBANK": 1402.00, "RELIANCE": 1202.00,
      "INFY": 1165.00, "BHARTIARTL": 1917.00}


def _ans(ours, price, date, tol=2.0):
    diff = abs(ours - price) / price * 100
    return {"price": price, "date": date, "diff_pct": round(diff, 2),
            "verdict": "agree" if diff <= tol else "disagree"}


def test_lone_lagging_witness_abstains():
    c = vb._judge("BSE", 3359.0, {"yfinance": _ans(3359.0, 3230.80, D23)}, D26)
    assert c["status"] == "skip", c
    assert "abstained" in c["why"]
    print("  test_lone_lagging_witness_abstains: PASS")


def test_lone_witness_frozen_for_weeks_still_fails():
    # MODISONLTD shape: the only witness is seven weeks behind and disagrees.
    c = vb._judge("MODISONLTD", 284.6,
                  {"yfinance": _ans(284.6, 250.0, D26 - dt.timedelta(days=49))}, D26)
    assert c["status"] == "MISMATCH", c
    print("  test_lone_witness_frozen_for_weeks_still_fails: PASS")


def test_lone_current_witness_disagreeing_still_fails():
    # Our price is the stale one: a witness AT the session disagrees -> suppress.
    c = vb._judge("BSE", 3230.80, {"yfinance": _ans(3230.80, 3359.0, D26)}, D26)
    assert c["status"] == "MISMATCH", c
    print("  test_lone_current_witness_disagreeing_still_fails: PASS")


def test_bse_2026_10_27_replay_passes():
    def fetch_all(sym, asof):
        out = {"yfinance": {"price": YF[sym], "date": D23}}
        out["alphavantage"] = ({"price": AV[sym], "date": D26} if sym in AV
                               else {"error": "av: Invalid API call."})
        out["twelvedata"] = ({"price": 1166.0, "date": D26} if sym == "INFY"
                             else {"error": "http 404"})
        return out

    frame = pd.DataFrame({"Symbol": list(OURS), "LTP": list(OURS.values()),
                          "Median_Turnover": range(len(OURS), 0, -1)})
    saved = (vb._latest_scan, vb._scan_staleness_note, vb._scan_date, vb.pd.read_excel,
             price_sources.fetch_all, price_sources.record)
    vb._latest_scan = lambda: "indian_full_scan_20261027_0300.xlsx"
    vb._scan_staleness_note = lambda f: ""
    vb._scan_date = lambda f: D27
    vb.pd.read_excel = lambda f, sheet: frame
    price_sources.fetch_all, price_sources.record = fetch_all, lambda rows: None
    try:
        r = vb.validate(sample=6, tol=2.0)
    finally:
        (vb._latest_scan, vb._scan_staleness_note, vb._scan_date, vb.pd.read_excel,
         price_sources.fetch_all, price_sources.record) = saved
    status = {c["symbol"]: c["status"] for c in r["checks"]}
    assert status["BSE"] == "skip", status
    assert all(s == "ok" for k, s in status.items() if k != "BSE"), status
    assert r["verified"] == 5 and r["ok"], r["reason"]
    print("  test_bse_2026_10_27_replay_passes: PASS")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)}/{len(tests)} tests passed")
