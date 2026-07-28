#!/usr/bin/env python3
"""
india_split_adjust.py — build split-adjustment factors for the India panel.

WHY (2026-07-28). `global-market-data/warehouse/ohlcv/IN` carries RAW closes.
Its top-200 alone holds 71 unadjusted split events reading as ~-90% single-day
"returns" — NESTLEIND 2024-01-05, JSWSTEEL 2017-01-04 and EICHERMOT 2020-08-24
are all confirmed 1:10 splits. US/JP/KR panels are adjusted; India alone is not.
Measured cost of leaving it: three contaminated events out of 721 moved the tier
book's like-for-like CAGR by 4.9 points, and a -90% fake return is roughly 40
sigma for a large cap, so it would dominate any covariance estimate and
therefore every weight an optimiser produces.

METHOD — DETECT LOCALLY, VERIFY EXTERNALLY, NEVER GUESS.
  Price-discontinuity detection alone is NOT enough to adjust on: a genuine
  crash and a 1:2 split look identical in a close series, and "adjusting" a real
  -50% day would erase a true loss and manufacture alpha. So the discontinuity
  is only used to SIZE the problem; the adjustment itself comes from yfinance's
  corporate-action feed, which states the ratio and the date. A symbol is
  adjusted only where an external split record exists.

  Conversely the feed is fetched for the whole LIQUID universe rather than only
  for detected outliers, because small bonus issues (11:10 = -9%) fall under any
  sane detection threshold while still corrupting returns.

MATH. yfinance reports ratio R on date D, meaning one old share became R new
shares. Raw prices strictly BEFORE D are therefore R times too high:
    adj_close(t) = close(t) / prod(R_i for every split i with date_i > t)
Back-adjustment, so the most recent price is unchanged and historical prices are
scaled down — the same convention as every adjusted feed.

Usage — MUST be the market-pipeline venv python; the login default and
/usr/bin/python3 both lack yfinance (--build fails fast and says so):
  V=/Users/umashankar/market-pipeline/code/python_files/.venv/bin/python3
  $V scripts/india_split_adjust.py --build            # fetch + write factors
  $V scripts/india_split_adjust.py --patch-residual   # bonus issues (see above)
  $V scripts/india_split_adjust.py --verify           # discontinuities before/after
  $V scripts/india_split_adjust.py --show RELIANCE
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

WH = Path("/Users/umashankar/repos/global-market-data/warehouse/ohlcv/IN")
OUT = Path("/Users/umashankar/market-pipeline/data/india_split_factors.parquet")
MIN_TURNOVER = 1e7          # Rs 1 crore/day median — the tradeable universe
WORKERS = 4                 # lowered from 8: rate limiting was the failure source
DETECT_DROP = 0.18          # only for SIZING the problem, never for adjusting


def load_raw() -> pd.DataFrame:
    files = sorted(WH.glob("year=*.parquet"))
    df = pd.concat([pd.read_parquet(f, columns=["Date", "Symbol", "Close", "Volume"])
                    for f in files], ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def liquid_symbols(df: pd.DataFrame) -> list[str]:
    turn = (df["Close"] * df["Volume"]).groupby(df["Symbol"]).median()
    return sorted(turn[turn > MIN_TURNOVER].index)


def fetch_splits(sym: str, retries: int = 3):
    """Authoritative splits for one symbol, or None if the FETCH FAILED.

    🔴 The first version returned [] on exception, making "the request failed"
    indistinguishable from "this symbol has no splits". Under 8-way concurrency
    yfinance rate-limited enough requests that TATASTEEL (1:10, 2022-07-28),
    YESBANK (1:5, 2017-09-21), SRF and SHRIRAMFIN all silently recorded as
    split-free — and the verify step still showed ~-90% days that the table
    claimed did not exist. None vs [] is the whole fix: a failure is retried and
    then reported, never quietly folded into the result.
    """
    import time
    import yfinance as yf
    last_err = None
    for attempt in range(retries):
        got_any_response = False
        for suffix in (".NS", ".BO"):
            try:
                s = yf.Ticker(sym + suffix).splits
                got_any_response = True
                if s is not None and len(s):
                    return [(sym, str(d)[:10], float(r)) for d, r in s.items()
                            if r and r > 0 and abs(r - 1.0) > 1e-9]
            except Exception as e:                    # noqa: BLE001
                last_err = e
        if got_any_response:
            return []          # a real response that genuinely lists no splits
        time.sleep(1.5 * (attempt + 1))
    return None                # every attempt errored — caller must not treat as empty


VENV_PY = ("/Users/umashankar/market-pipeline/code/python_files/.venv/bin/python3")


def require_yfinance() -> None:
    """Fail in the first second, not after a 4.4M-row load and 1,815 threads.

    Three interpreters live on this machine and only one can run this script:
    Homebrew's python3 (the login default) has neither yfinance nor duckdb,
    /usr/bin/python3 has duckdb/pandas/psycopg2 but NOT yfinance, and the
    market-pipeline venv has all of it. Discovered the ugly way — the import
    sat inside the thread worker, so a missing module surfaced as a
    ThreadPoolExecutor traceback several minutes into a run that had already
    done all its expensive work.
    """
    try:
        import yfinance  # noqa: F401
    except ImportError:
        raise SystemExit(
            "yfinance is not available to this interpreter "
            f"({sys.executable}).\n\n"
            f"Run with the market-pipeline venv instead:\n"
            f"  {VENV_PY} scripts/india_split_adjust.py --build\n"
        )


def build(args) -> int:
    require_yfinance()
    df = load_raw()
    syms = liquid_symbols(df)
    print(f"IN panel: {df.Symbol.nunique():,} symbols · "
          f"{len(syms):,} above Rs {MIN_TURNOVER/1e7:.0f}cr median turnover")

    rows: list[tuple[str, str, float]] = []
    failed: list[str] = []
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(fetch_splits, s): s for s in syms}
        for f in as_completed(futs):
            res = f.result()
            if res is None:
                failed.append(futs[f])
            else:
                rows.extend(res)
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(syms)} · {len(rows)} splits · "
                      f"{len(failed)} failed", flush=True)

    # Second pass, serial, over everything that errored — a symbol whose fetch
    # failed must never be written as "no splits".
    if failed:
        print(f"  retrying {len(failed)} failed symbol(s) serially …", flush=True)
        still: list[str] = []
        for s in failed:
            res = fetch_splits(s, retries=4)
            (still.append(s) if res is None else rows.extend(res))
        failed = still

    fac = pd.DataFrame(rows, columns=["symbol", "split_date", "ratio"])
    if fac.empty:
        print("no splits returned — refusing to write an empty factor table")
        return 1
    if failed:
        print(f"  ⚠ {len(failed)} symbol(s) still unresolved after retry — "
              f"their splits are NOT in the table: {', '.join(failed[:12])}"
              f"{' …' if len(failed) > 12 else ''}")
    fac["split_date"] = pd.to_datetime(fac.split_date)
    # Only splits inside the panel's own date range can affect it.
    lo, hi = df.Date.min(), df.Date.max()
    fac = fac[(fac.split_date >= lo) & (fac.split_date <= hi)]
    fac = fac.sort_values(["symbol", "split_date"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fac.to_parquet(OUT, index=False)
    print(f"\nwrote {len(fac)} in-range splits across {fac.symbol.nunique()} "
          f"symbols -> {OUT}")
    print(fac.ratio.value_counts().head(8).to_string())
    return 0


def factors_for(px: pd.DataFrame, fac: pd.DataFrame) -> pd.DataFrame:
    """Cumulative divisor per (date, symbol): product of every LATER split."""
    div = pd.DataFrame(1.0, index=px.index, columns=px.columns)
    for sym, g in fac.groupby("symbol"):
        if sym not in div.columns:
            continue
        col = pd.Series(1.0, index=px.index)
        for d, r in zip(g.split_date, g.ratio):
            col.loc[col.index < d] *= r      # prices BEFORE the split are R x high
        div[sym] = col
    return div


def adjust(px: pd.DataFrame, fac: pd.DataFrame) -> pd.DataFrame:
    return px / factors_for(px, fac)


def adjust_long(df: pd.DataFrame, fac: pd.DataFrame | None = None) -> pd.DataFrame:
    """Apply split adjustment to a long (Date, Symbol, Close, Volume) frame.

    BOTH legs are adjusted: Close /= R and Volume *= R. Adjusting price alone
    would leave turnover (Close x Volume) understated by R before every split,
    and turnover is what selects the universe — so a price-only fix would
    quietly bias liquidity ranking against any name that later split. In
    reality a split changes neither the rupee turnover nor the market cap.
    """
    if fac is None:
        if not OUT.exists():
            return df
        fac = pd.read_parquet(OUT)
    if fac.empty:
        return df
    fac = fac.copy()
    fac["split_date"] = pd.to_datetime(fac.split_date)
    out = df.copy()
    div = pd.Series(1.0, index=out.index)
    by_sym = {s: g for s, g in fac.groupby("symbol")}
    for sym, idx in out.groupby("Symbol").groups.items():
        g = by_sym.get(sym)
        if g is None:
            continue
        d = out.loc[idx, "Date"]
        f = pd.Series(1.0, index=idx)
        for sd, r in zip(g.split_date, g.ratio):
            f[d.values < np.datetime64(sd)] *= r
        div.loc[idx] = f.values
    out["Close"] = out["Close"] / div.values
    if "Volume" in out.columns:
        out["Volume"] = out["Volume"] * div.values
    return out


def _discontinuities(px: pd.DataFrame) -> int:
    r = px.pct_change(fill_method=None)
    return int(((r < -DETECT_DROP) & (r.shift(-1) < 0.20)).sum().sum())


def patch_residual(args) -> int:
    """Capture BONUS issues, which `.splits` does not report.

    Splits alone leave a residual class behind: Indian companies issue bonus
    shares constantly, and a bonus halves (or worse) the price exactly like a
    split while Yahoo's `.splits` feed stays silent about it. Confirmed cases
    left standing after the split pass — MINDTREE 2016-03-09 (-55.7%, 1:1
    bonus), BAJAJFINSV 2022-09-13 (-47.9%, 1:1), BAJFINANCE 2025-06-16 (a 1:2
    split AND a 4:1 bonus, of which only the 2x split was reported).

    Yahoo's ADJUSTED close does account for bonuses, so the authority used here
    is the adjusted series itself: adj/raw jumps by exactly the action ratio on
    the action date. Dividends are excluded by construction — auto_adjust=False
    keeps 'Close' raw of splits AND dividends, so the ratio isolates the
    share-count events. A genuine crash moves adj and raw together and leaves
    the ratio flat, so this cannot 'adjust away' a real loss.
    """
    import yfinance as yf
    fac = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame(
        columns=["symbol", "split_date", "ratio"])
    df = load_raw()
    syms = liquid_symbols(df)
    px = (df[df.Symbol.isin(syms)]
          .pivot_table(index="Date", columns="Symbol", values="Close").sort_index())
    adj_px = adjust(px, fac)
    r = adj_px.pct_change(fill_method=None)
    resid = ((r < -0.30) & (r.shift(-1) < 0.20))
    targets = sorted(resid.columns[resid.any()])
    print(f"{len(targets)} symbol(s) still show a >30% unreversed drop after "
          f"the split pass — checking each against Yahoo's adjusted series")

    new_rows, checked = [], 0
    for sym in targets:
        dates = list(resid.index[resid[sym]])
        try:
            h = yf.Ticker(sym + ".NS").history(period="max", auto_adjust=False)
            if h.empty or "Adj Close" not in h.columns:
                continue
            ratio = (h["Adj Close"] / h["Close"]).dropna()
            ratio.index = pd.DatetimeIndex(ratio.index).tz_localize(None)
        except Exception:                                  # noqa: BLE001
            continue
        checked += 1
        for d in dates:
            win = ratio.loc[(ratio.index >= d - pd.Timedelta(days=4)) &
                            (ratio.index <= d + pd.Timedelta(days=4))]
            if len(win) < 2:
                continue
            jump = float(win.iloc[-1] / win.iloc[0])
            # a share-count action shows as a clean multiplicative jump; a
            # dividend-only adjustment is tiny and a real crash is ~1.0
            if jump > 1.15:
                known = fac[(fac.symbol == sym) &
                            (abs((fac.split_date - d).dt.days) <= 4)].ratio.prod()
                extra = jump / (known if known else 1.0)
                if extra > 1.15:
                    new_rows.append((sym, str(d)[:10], round(extra, 4)))
                    print(f"    {sym:14s} {str(d)[:10]}  bonus/extra ratio "
                          f"{extra:.3f}" + (f" (split {known:g} already known)"
                                            if known else ""))

    if not new_rows:
        print(f"  checked {checked} symbol(s) — no additional share-count actions found")
        return 0
    add = pd.DataFrame(new_rows, columns=["symbol", "split_date", "ratio"])
    add["split_date"] = pd.to_datetime(add.split_date)
    out = (pd.concat([fac, add], ignore_index=True)
             .drop_duplicates(subset=["symbol", "split_date"], keep="last")
             .sort_values(["symbol", "split_date"]).reset_index(drop=True))
    out.to_parquet(OUT, index=False)
    print(f"\n  added {len(add)} bonus/extra action(s) · table now {len(out)} rows")
    return 0


def verify(args) -> int:
    if not OUT.exists():
        print(f"{OUT} missing — run --build first")
        return 1
    fac = pd.read_parquet(OUT)
    df = load_raw()
    syms = liquid_symbols(df)
    px = (df[df.Symbol.isin(syms)]
          .pivot_table(index="Date", columns="Symbol", values="Close").sort_index())
    before = _discontinuities(px)
    adj = adjust(px, fac)
    after = _discontinuities(adj)
    print(f"liquid universe: {px.shape[1]} symbols × {len(px)} bars")
    print(f"  discontinuities (>{DETECT_DROP:.0%} drop, no next-day reversal)")
    print(f"    before adjustment : {before}")
    print(f"    after  adjustment : {after}   ({before - after} removed)")
    r = adj.pct_change(fill_method=None).stack()
    print("\n  worst remaining single-day returns (should be real events):")
    for (d, s), v in r.nsmallest(6).items():
        print(f"    {s:14s} {str(d)[:10]}  {v:+.1%}")
    return 0


def show(args) -> int:
    fac = pd.read_parquet(OUT)
    g = fac[fac.symbol == args.show]
    print(g.to_string(index=False) if len(g) else f"no splits recorded for {args.show}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--patch-residual", action="store_true",
                    help="capture bonus issues .splits does not report")
    ap.add_argument("--show", metavar="SYMBOL")
    a = ap.parse_args()
    if a.build:
        return build(a)
    if a.patch_residual:
        return patch_residual(a)
    if a.verify:
        return verify(a)
    if a.show:
        return show(a)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
