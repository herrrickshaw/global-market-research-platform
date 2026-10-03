#!/usr/bin/env python3
"""
trailing_returns.py — trailing returns over standard windows for any ticker
or a whole watchlist, plus a return-based analog of a moving-average golden
crossover for spotting momentum shifts between windows.

WINDOWS (measured BACKWARD from an as-of date — "how has this stock done over
the trailing N", the complement of every forward-return script in this repo,
which measures FORWARD from a signal date): 1d, 1wk, 3mo, 6mo, 1y, 5y.
1d is 1 TRADING day back (the standard daily-return convention); the rest are
CALENDAR-period offsets (pd.DateOffset) snapped to the nearest trading bar on
or before the target date — the standard convention for "6-month return" etc,
not a fixed trading-bar count (which would drift against real calendar
periods across markets with different holiday calendars).

WHY ANNUALIZED RATES, NOT RAW RETURNS, FOR CROSS-WINDOW COMPARISON. A raw 1-day
return (~0.3%) and a raw 5-year return (~40%) are not comparable numbers — the
5-year return LOOKS bigger but represents a slower rate of change. Annualizing
each window's return to a per-year rate ( (1+r)^(365/days) - 1 ) puts every
window on the same footing, and comparing a SHORT window's annualized rate to
a LONGER window's is the direct return-space analog of comparing a fast EMA
to a slow EMA: the short rate "crossing above" the long rate is a momentum-
shift signal, the same shape as a golden cross, without needing to compute
EMAs/DMAs on price at all.

PATTERN DETECTION — the worked example that motivated this module: "a 6-month
decline followed by 1 week of growth peaks investor interest." Implemented
literally as one of several named patterns in `classify_pattern()`:
  REVERSAL_UP    real long-window decline, real short-window bounce
                 (ret_6mo <= -REVERSAL_LONG_MIN and ret_1wk >= REVERSAL_THRESHOLD)
  REVERSAL_DOWN  the mirror: real rally, then a real short-window drop --
                 a possible exhaustion/pullback
  ACCEL_UP       a real 1wk rise (>= ACCEL_MIN_1WK) whose ANNUALIZED rate beats
                 the 6mo rate by ACCEL_MARGIN -- the golden-cross analog
  ACCEL_DOWN     the mirror -- recent momentum lagging the trend
  none of the above -> "" (no pattern flagged, most rows most days)
Rows whose trailing year holds a split-sized one-day jump are marked
split_suspect and get no pattern (raw US/EU/JP/KR panels are unadjusted).

USAGE
    # ad-hoc, one ticker:
    python3 trailing_returns.py --symbol RELIANCE --market IN

    # every ticker currently in a watchlist file (any CSV with symbol+market
    # columns -- watchlist.csv, filter_watchlist.csv, or a custom list):
    python3 trailing_returns.py --watchlist filter_watchlist.csv

    # as a library:
    from trailing_returns import trailing_returns
    df = trailing_returns([("RELIANCE", "IN"), ("AAPL", "US")])
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import signal_tracker as ST  # noqa: E402 -- reuse PANELS/_panel/resolve_symbol, same warehouse as the rest of this session's tools

# PANEL RESOLUTION AND SYMBOL MAPPING BOTH LIVE IN signal_tracker, which owns
# PANELS. Until 2026-09-16 that dict held only IN and US, so this script read
# "no local price panel for this market" for 3,812 of filter_watchlist.csv's
# 8,300 rows — every EU, JP and KR name — while the data sat on disk unread.
# EU/JP/KR are registered there now and the panel owner also owns the ticker-form
# mapping (ST.resolve_symbol), so this file keeps NO second copy of either: a
# private copy is what lets the two drift into disagreeing about which panel
# column a given ledger symbol means.
#
# CN is absent from PANELS on purpose — its partition is ~10 weeks stale. This
# script therefore reports CN as "no local price panel", which is the truthful
# answer, rather than pricing it off July closes.
PANEL_MARKETS = tuple(ST.PANELS)
_resolve_symbol = ST.resolve_symbol   # re-exported: global_price_bands imports it


def _panel_path(mkt: str):
    # India reads the split/bonus-adjusted panel like every other consumer:
    # raw India closes fake -90% crashes straight through every split.
    return ST.PANELS.get(mkt)

WINDOWS = {
    "ret_1d":  ("trading", 1),
    "ret_1wk": ("calendar", pd.DateOffset(weeks=1)),
    "ret_3mo": ("calendar", pd.DateOffset(months=3)),
    "ret_6mo": ("calendar", pd.DateOffset(months=6)),
    "ret_1y":  ("calendar", pd.DateOffset(years=1)),
    "ret_5y":  ("calendar", pd.DateOffset(years=5)),
}
WINDOW_DAYS = {  # approximate calendar days per window, for annualizing
    "ret_1d": 1, "ret_1wk": 7, "ret_3mo": 91, "ret_6mo": 182,
    "ret_1y": 365, "ret_5y": 365 * 5,
}
# THRESHOLDS TIGHTENED 2026-09-21. The originals (any 6mo sign + 3% week for a
# reversal; a 5pp annualized gap for acceleration) fired on 7,451 of 7,910
# filter_watchlist names — 94%, i.e. no filter at all. A 5pp gap is meaningless
# on an annualized 1wk rate (a 1% week annualizes to ~68%), so ACCEL fired on
# almost any non-flat week. Now both legs of every pattern need a real move.
REVERSAL_THRESHOLD = 5.0   # short-window (1wk) %, minimum move to call it a real bounce/drop
REVERSAL_LONG_MIN = 15.0   # long-window (6mo) %, minimum prior decline/rally to reverse FROM
ACCEL_MIN_1WK = 3.0        # raw 1wk %, floor so a quiet week can't "accelerate"
ACCEL_MARGIN = 50.0        # annualized percentage-point gap to call it a real acceleration

# SPLIT SUSPECTS. Only India reads an adjusted panel (see signal_tracker.PANELS);
# US/EU/JP/KR are raw closes, so an unadjusted split or reverse split prints as a
# one-day crash or moonshot (HUBC +1,251% in a week, JAGX +763% on 2026-09-21)
# and lands in whichever window spans it. Any one-day close ratio at or beyond
# these bounds inside the trailing 1y marks the row split_suspect and suppresses
# its pattern. A 2:1 split reads ~0.50, a 1:10 reverse ~10x. A 3:2 split (0.67)
# slips through on purpose: the bound also catches genuine -45% single-day
# crashes, and widening it further would drop real microcap events wholesale.
SPLIT_JUMP_UP = 1.9
SPLIT_JUMP_DOWN = 0.55
SPLIT_LOOKBACK = pd.DateOffset(years=1)


def _wide_panel(mkt: str) -> tuple[pd.DataFrame, pd.Timestamp]:
    mkt = mkt.upper()
    if mkt not in PANEL_MARKETS:
        return pd.DataFrame(), None
    p = _panel_path(mkt)
    if not p or not p.exists():
        return pd.DataFrame(), None
    px = ST._panel(p, columns=["Date", "Symbol", "Close"])
    px["Symbol"] = px["Symbol"].astype(str).str.upper()
    wide = px.pivot_table(index="Date", columns="Symbol", values="Close",
                          aggfunc="last").sort_index()
    return wide, (wide.index.max() if len(wide) else None)


def _nearest_on_or_before(s: pd.Series, target: pd.Timestamp):
    """Last value in `s` (a Date-indexed Series) at or before `target`, or
    (None, None) if nothing that old exists."""
    sub = s[s.index <= target]
    if sub.empty:
        return None, None
    return float(sub.iloc[-1]), sub.index[-1]


def _annualize(ret_pct: float, days: int) -> float:
    if ret_pct is None or not np.isfinite(ret_pct) or days <= 0:
        return np.nan
    r = ret_pct / 100.0
    try:
        return ((1 + r) ** (365.0 / days) - 1) * 100.0
    except (OverflowError, ValueError):
        return np.nan


def trailing_returns(symbols: list[tuple[str, str]],
                     as_of: pd.Timestamp = None) -> pd.DataFrame:
    """symbols: list of (symbol, market) pairs. Returns one row per symbol
    with ret_1d..ret_5y (% ) plus annualized rates and any detected pattern.
    A window with insufficient history is NaN, not a fabricated 0 or an
    error -- the row still reports every OTHER window that does have data."""
    rows = []
    panels: dict[str, tuple[pd.DataFrame, pd.Timestamp]] = {}
    for sym, mkt in symbols:
        sym = sym.strip().upper()
        if mkt not in panels:
            panels[mkt] = _wide_panel(mkt)
        wide, panel_end = panels[mkt]
        if wide.empty or panel_end is None:
            rows.append({"symbol": sym, "market": mkt, "as_of": None,
                        "error": "no local price panel for this market",
                        **{w: np.nan for w in WINDOWS},
                        **{f"{w}_ann": np.nan for w in WINDOWS}})
            continue
        eff_as_of = as_of if as_of is not None else panel_end
        col = _resolve_symbol(sym, mkt, wide.columns)
        if col is None:
            rows.append({"symbol": sym, "market": mkt, "as_of": eff_as_of,
                        "error": "symbol not in panel",
                        **{w: np.nan for w in WINDOWS},
                        **{f"{w}_ann": np.nan for w in WINDOWS}})
            continue
        s = wide[col].dropna()
        anchor_px, anchor_dt = _nearest_on_or_before(s, eff_as_of)
        row = {"symbol": sym, "market": mkt, "as_of": anchor_dt, "error": None,
               "split_suspect": False}
        if anchor_px is None:
            row["error"] = "no bar on or before as_of"
            row.update({w: np.nan for w in WINDOWS})
            row.update({f"{w}_ann": np.nan for w in WINDOWS})
            rows.append(row)
            continue
        for wname, (kind, spec) in WINDOWS.items():
            if kind == "trading":
                pos = s.index.searchsorted(anchor_dt)
                back_pos = pos - spec
                if back_pos < 0:
                    row[wname] = np.nan
                    continue
                base_px = float(s.iloc[back_pos])
            else:
                target = anchor_dt - spec
                base_px, _ = _nearest_on_or_before(s, target)
                if base_px is None:
                    row[wname] = np.nan
                    continue
            row[wname] = (anchor_px / base_px - 1) * 100 if base_px else np.nan
            row[f"{wname}_ann"] = _annualize(row[wname], WINDOW_DAYS[wname])
        row["split_suspect"] = _has_split_jump(s, anchor_dt)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["pattern"] = df.apply(classify_pattern, axis=1)
    return df


def _has_split_jump(s: pd.Series, anchor_dt: pd.Timestamp) -> bool:
    """True if any one-day close ratio in the trailing SPLIT_LOOKBACK looks
    like an unadjusted split/reverse split (see SPLIT_JUMP_* above)."""
    win = s[(s.index > anchor_dt - SPLIT_LOOKBACK) & (s.index <= anchor_dt)]
    ratio = (win / win.shift(1)).dropna()
    return bool(((ratio >= SPLIT_JUMP_UP) | (ratio <= SPLIT_JUMP_DOWN)).any())


def classify_pattern(row) -> str:
    """See module docstring for the four named patterns. Uses (ret_6mo,
    ret_1wk) for reversal detection -- the exact pair in the motivating
    example -- and (ret_1wk_ann, ret_6mo_ann) for acceleration. A split-
    suspect row gets no pattern: its returns are an artifact, not a move."""
    if row.get("split_suspect") == True:  # noqa: E712 -- np.bool_ / NaN-safe, `is True` misses np.True_
        return ""
    r6mo, r1wk = row.get("ret_6mo"), row.get("ret_1wk")
    if pd.notna(r6mo) and pd.notna(r1wk):
        if r6mo <= -REVERSAL_LONG_MIN and r1wk >= REVERSAL_THRESHOLD:
            return "REVERSAL_UP"
        if r6mo >= REVERSAL_LONG_MIN and r1wk <= -REVERSAL_THRESHOLD:
            return "REVERSAL_DOWN"
    a1wk, a6mo = row.get("ret_1wk_ann"), row.get("ret_6mo_ann")
    if pd.notna(a1wk) and pd.notna(a6mo) and pd.notna(r1wk):
        if r1wk >= ACCEL_MIN_1WK and a1wk > a6mo + ACCEL_MARGIN:
            return "ACCEL_UP"
        if r1wk <= -ACCEL_MIN_1WK and a1wk < a6mo - ACCEL_MARGIN:
            return "ACCEL_DOWN"
    return ""


def _read_watchlist(path: Path) -> list[tuple[str, str]]:
    d = pd.read_csv(path)
    if "status" in d.columns:  # watchlist.csv / filter_watchlist.csv shape
        active = d[d["status"].isin(["active", "held", "signal", "watch",
                                     "playbook", "justified", "value-hold"])]
    else:
        active = d
    return list(zip(active["symbol"].astype(str), active["market"].astype(str)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", type=str)
    ap.add_argument("--market", type=str)
    ap.add_argument("--watchlist", type=str)
    ap.add_argument("--as-of", type=str, default=None,
                    help="YYYY-MM-DD, defaults to the panel's own latest bar")
    ap.add_argument("--pattern-only", action="store_true",
                    help="print only rows with a non-empty pattern flag")
    a = ap.parse_args()

    as_of = pd.Timestamp(a.as_of) if a.as_of else None

    if a.watchlist:
        symbols = _read_watchlist(HERE / a.watchlist)
        symbols = list(dict.fromkeys(symbols))  # dedupe, keep order
    elif a.symbol and a.market:
        symbols = [(a.symbol, a.market)]
    else:
        ap.print_help()
        return 1

    print(f"  scoring {len(symbols)} symbol(s)...")
    df = trailing_returns(symbols, as_of=as_of)
    n_split = int(df["split_suspect"].fillna(False).astype(bool).sum())

    if a.pattern_only:
        df = df[df["pattern"] != ""]
        if df.empty:
            print("  no patterns flagged"); return 0

    cols = ["symbol", "market", "as_of", "ret_1d", "ret_1wk", "ret_3mo",
           "ret_6mo", "ret_1y", "ret_5y", "pattern", "split_suspect", "error"]
    with pd.option_context("display.max_rows", None, "display.width", 160):
        print(df[cols].round(2).to_string(index=False))

    if n_split:
        print(f"\n  {n_split} split-suspect row(s) (one-day close ratio >= {SPLIT_JUMP_UP}x "
              f"or <= {SPLIT_JUMP_DOWN}x in the trailing 1y) — pattern suppressed")

    n_err = df["error"].notna().sum()
    if n_err:
        print(f"\n  {n_err} row(s) had an issue (no panel / not in panel / no history) "
              f"— see the 'error' column above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
