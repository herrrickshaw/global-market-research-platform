#!/usr/bin/env python3
"""
us_close_fallback.py — fill a US session yfinance has not published, from Nasdaq.

🔴 WHY THIS EXISTS. 2026-10-22: the brief went out flagged "United States 20 Oct
close · 1 session behind" although NYSE had closed 21 Oct nine hours earlier.
It was not throttling. yfinance returned the 21 Oct row with Close=NaN for every
name (AAPL, MSFT, NVDA, SPY…), `dropna` removed it, and every consumer quietly
fell back one session — the same shape as the 2026-08-28 incident. Hours later
the row was still NaN, so retrying cannot fix it. Nasdaq's public historical
endpoint already carried the real 21 Oct OHLCV (AAPL 343.99).

(EDGAR was considered and rejected: it serves filings, not prices.) The bulk
screener endpoint was also rejected — it lags a session behind (AAPL showed the
20 Oct close), which is worse than useless because it looks current.

Per-ticker, ~17 req/s with 8 workers, so ~7-10 min for the full universe. Only
tickers whose newest bar predates the expected session are asked.

GUARD. Nasdaq prices are raw, yfinance's are split/dividend adjusted. Each fill
is accepted only if Nasdaq's close for the ticker's own LAST BAR date agrees
with our stored close within TOL, so a split or a mis-keyed symbol is skipped
rather than spliced in as a fake 50% move. yfinance backfills the true bar on a
later run and the callers' dedup (keep last / drop_duplicates) replaces ours.
"""
from __future__ import annotations

import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

URL = "https://api.nasdaq.com/api/quote/{}/historical"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
WORKERS = 8
TOL = 0.01          # max |nasdaq_close / stored_close - 1| on the shared date
MAX_GAP_DAYS = 7    # don't chase tickers dead for longer than this


def _num(s):
    try:
        return float(str(s).replace("$", "").replace(",", ""))
    except ValueError:
        return float("nan")


def _fetch(sym: str, since: dt.date, tries: int = 3):
    """Nasdaq rows for `sym` from `since`, as {date: (o, h, l, c, v)} or None."""
    for attempt in range(tries):
        try:
            r = requests.get(
                URL.format(sym.replace("-", ".")),
                params=dict(assetclass="stocks", fromdate=since.isoformat(), limit=15),
                headers=HEADERS, timeout=15,
            )
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            data = (r.json().get("data") or {}).get("tradesTable") or {}
            out = {}
            for row in data.get("rows") or []:
                d = dt.datetime.strptime(row["date"], "%m/%d/%Y").date()
                out[d] = (_num(row["open"]), _num(row["high"]), _num(row["low"]),
                          _num(row["close"]), _num(row["volume"]))
            return out
        except Exception:
            time.sleep(1 + attempt)
    return None


def expected_us_session() -> dt.date:
    import market_sessions as ms
    return ms.expected_session("US")


def fetch_missing(ref: dict, expected: dt.date, workers: int = WORKERS) -> dict:
    """ref: {symbol: (last_bar_date, last_close)} for tickers behind `expected`.

    Returns {symbol: (o, h, l, c, v)} for the expected session, guard-checked.
    """
    todo = {s: v for s, v in ref.items()
            if v[0] < expected and (expected - v[0]).days <= MAX_GAP_DAYS}
    if not todo:
        return {}

    def one(item):
        sym, (last_d, last_c) = item
        rows = _fetch(sym, last_d)
        if not rows or expected not in rows:
            return sym, None, "absent"
        bar = rows[expected]
        if not all(x == x and x > 0 for x in bar[:4]) or not bar[1] >= bar[2]:
            return sym, None, "invalid"
        if last_d in rows and last_c and abs(rows[last_d][3] / last_c - 1) > TOL:
            return sym, None, "mismatch"
        return sym, bar, "ok"

    got, why = {}, {}
    with ThreadPoolExecutor(workers) as pool:
        for sym, bar, status in pool.map(one, todo.items()):
            if bar:
                got[sym] = bar
            else:
                why[status] = why.get(status, 0) + 1
    print(f"  Nasdaq fallback for session {expected}: filled {len(got):,}/{len(todo):,} "
          f"behind-ticker(s); skipped {why or 'none'}")
    return got


def patch_frames(frames: dict, expected: dt.date | None = None) -> dict:
    """In-place: append the expected-session bar to OHLCV frames lacking it.

    frames: {ticker: DataFrame(DatetimeIndex; Open High Low Close Volume)}.
    Returns {ticker: new_frame} for the tickers actually changed.
    """
    expected = expected or expected_us_session()
    ref = {}
    for t, df in frames.items():
        if df is not None and len(df) and "Close" in df:
            ref[t] = (df.index[-1].date(), float(df["Close"].iloc[-1]))
    got = fetch_missing(ref, expected)
    changed = {}
    for t, (o, h, l, c, v) in got.items():
        df = frames[t]
        row = pd.DataFrame([[o, h, l, c, v]], columns=["Open", "High", "Low", "Close", "Volume"],
                           index=pd.DatetimeIndex([pd.Timestamp(expected)], name=df.index.name))
        new = pd.concat([df, row.reindex(columns=df.columns)])
        new = new[~new.index.duplicated(keep="last")].sort_index()
        new.attrs.pop("stale", None)
        frames[t] = changed[t] = new
    return changed
