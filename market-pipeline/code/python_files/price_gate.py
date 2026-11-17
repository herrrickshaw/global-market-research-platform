#!/usr/bin/env python3
"""
price_gate.py — the one gate between a built brief and the send.

Until 2026-10-27 this was two scripts called three times from step [13/13]:
scan_price_reconcile for IN, again for US, then validate_brief for IN. Both
asked Yahoo about the India sample — reconcile with an undated "last close",
the jury with a date-anchored one — so India was checked against the same
source twice and the weaker check could suppress on drift the stronger one
had already explained. For the US the reconcile's live spot-check is also
circular in a way worth naming: the US scan is itself built from yfinance,
so Yahoo can only ever tell us the scan is STALE, never that it is WRONG.

What runs now, per market, cheapest first:

  1. WORKBOOK AGE      a scan not built today means the 03:00 step did not
                       run; price drift below would be a consequence, not the
                       cause (Sat 2026-08-01). Fails before any price is read.
  2. WAREHOUSE SIGNATURE  a liquid name whose LTP equals yesterday's
                       market_daily.snapshots close to the cent is suspicious;
                       a majority of them is a re-served cache (INFY/SKHY
                       class, 2026-07-27). No network. Fails in any session.
  3a. IN: WITNESS JURY (validate_brief) — three independent paths to the
                       market, date-anchored closes, majority rule, abstain
                       rules for lagging witnesses. This is the price check.
  3b. US: LIVE SPOT-CHECK — Yahoo is the only source we have for US, so it
                       is re-quoted fresh and compared. In session, one name
                       over tolerance is drift (2026-07-28, NVDA); only a
                       majority breach fails. Closed, one breach fails.

Exit 0 = send. Exit 1 = do not send; the reason is also written to
state/price_gate_reason.txt so the shell can name the blocker in the alert
without parsing this script's stdout.

    python3 price_gate.py                      # IN US, jury sample 6
    python3 price_gate.py --markets US         # staleness + spot-check only
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pandas as pd

import market_sessions as ms
import scan_files
import validate_brief

HERE = Path(__file__).resolve().parent
REASON_FILE = HERE / "state" / "price_gate_reason.txt"

# The scan is produced at 03:00 and consumed at 06:30 the SAME day, so a
# workbook older than today means the producing job did not run.
MAX_SCAN_AGE_DAYS = 0
LIQ_COL = "Turnover_USD"   # present in every All_Stocks sheet

# market -> (symbol column, price column, yfinance suffix, has independent witnesses)
# "has witnesses" decides step 3: the jury where one exists, Yahoo where not.
MARKETS = {
    "IN": ("Symbol", "LTP", ".NS", True),
    "US": ("Symbol", "LTP", "", False),
    "JP": ("YF_Ticker", "LTP_JPY", "", False),
    "KR": ("YF_Ticker", "LTP_KRW", "", False),
    "EU": ("Symbol", "LTP", "", False),
}


def _quorum(n: int) -> int:
    """Names that must breach together before an in-session FAIL: a strict
    majority of what was actually checked, floor 2 so a one-name sample can
    never fail on a single quote. (2026-08-12: `(n+1)//2` was only a majority
    for odd n; at n=8 it let 4/8 drifting breakouts suppress a correct brief.)"""
    return max(2, n // 2 + 1)


def warehouse_prev_close(market: str) -> pd.DataFrame:
    """Previous session's ltp per symbol from market_daily.snapshots (via psql)."""
    sql = f"""SELECT symbol, ltp FROM market_daily.snapshots
              WHERE market='{market}' AND as_of_date =
                (SELECT MAX(as_of_date) FROM market_daily.snapshots
                 WHERE market='{market}' AND as_of_date < CURRENT_DATE)"""
    try:
        r = subprocess.run(["psql", "-d", "market_data", "--csv", "-c", sql],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            return pd.read_csv(StringIO(r.stdout))
    except Exception:                                                  # noqa: BLE001
        pass
    return pd.DataFrame(columns=["symbol", "ltp"])


def fresh_quotes(tickers: list[str]) -> dict[str, float]:
    """Fresh last closes via a NEW yfinance session — deliberately no cache."""
    import yfinance as yf
    out: dict[str, float] = {}
    try:
        data = yf.download(tickers, period="1d", progress=False,
                           auto_adjust=False, threads=True)
        closes = data.get("Close", data)
        if isinstance(closes, pd.Series):          # single ticker
            out[tickers[0]] = float(closes.dropna().iloc[-1])
        else:
            for t in tickers:
                if t in closes.columns:
                    s = closes[t].dropna()
                    if len(s):
                        out[t] = float(s.iloc[-1])
    except Exception as e:                                             # noqa: BLE001
        print(f"    fresh-quote batch failed: {e}")
    return out


def staleness(market: str, sample: int = 8, tolerance: float = 2.0,
              root: Path | None = None) -> tuple[bool, str]:
    """Steps 1, 2 and (markets without witnesses) 3b. Returns (ok, reason)."""
    sym_col, px_col, suffix, has_witnesses = MARKETS[market]
    scan_path = scan_files.latest(market, root or HERE)
    if not scan_path:
        print(f"  [{market}] no scan workbook — SKIP")
        return True, ""
    name = Path(scan_path).name

    age = scan_files.age_days(scan_path)
    if age is not None and age > MAX_SCAN_AGE_DAYS:
        print(f"  [{market}] ❌ STALE WORKBOOK — {name} is {age} day(s) old; the scan "
              f"step did not run. Price drift would be a CONSEQUENCE, not the cause.")
        return False, f"{market}: stale workbook — {name} is {age} day(s) old; the scan step did not run"

    df = pd.read_excel(scan_path, sheet_name="All_Stocks")
    if sym_col not in df.columns or px_col not in df.columns:
        print(f"  [{market}] missing {sym_col}/{px_col} in {name} — SKIP")
        return True, ""
    liquid = (df.sort_values(LIQ_COL, ascending=False).head(sample)
              if LIQ_COL in df.columns else df.head(sample))
    liquid = liquid[[sym_col, px_col]].dropna()

    wh = warehouse_prev_close(market)
    n_sig = 0
    if not wh.empty:
        m = liquid.merge(wh, left_on=liquid[sym_col].astype(str).str.replace(
            r"\.(NS|BO|T|KS|KQ)$", "", regex=True), right_on="symbol", how="left")
        n_sig = int((abs(m[px_col] - m["ltp"]) < 1e-6).sum())
        if n_sig:
            print(f"  [{market}] ⚠ {n_sig}/{len(liquid)} liquid names EXACTLY equal "
                  f"yesterday's warehouse close (stale-cache signature)")
    if n_sig >= _quorum(len(liquid)):
        print(f"  [{market}] {name}: FAIL — re-served yesterday's closes "
              f"({n_sig}/{len(liquid)} exact matches)")
        return False, f"{market}: re-served yesterday's closes ({n_sig}/{len(liquid)} exact warehouse matches)"

    if has_witnesses:
        print(f"  [{market}] {name}: workbook is today's, signature clean — prices go to the witness jury")
        return True, ""

    # 3b — the only source for this market is Yahoo, so re-quote it fresh.
    tickers = [str(s) + suffix if suffix and not str(s).endswith(suffix) else str(s)
               for s in liquid[sym_col]]
    fresh = fresh_quotes(tickers)
    in_session = ms.is_open(market)
    if in_session:
        tolerance = tolerance * 2
        print(f"  [{market}] market in session — tolerance loosened to {tolerance:.1f}% (intraday drift)")
    n_checked = n_stale = 0
    worst = ("", 0.0)
    for (_, row), tkr in zip(liquid.iterrows(), tickers, strict=True):
        if tkr not in fresh or not fresh[tkr]:
            continue
        n_checked += 1
        diff = abs(row[px_col] - fresh[tkr]) / fresh[tkr] * 100
        if diff > tolerance:
            n_stale += 1
            print(f"    !! {tkr:14s} scan={row[px_col]:<12g} fresh={fresh[tkr]:<12g} diff={diff:.2f}%")
            if diff > worst[1]:
                worst = (tkr, diff)
    if n_checked == 0:
        print(f"  [{market}] live spot-check unavailable (yfinance) — warehouse signature only")
        return True, ""
    need = _quorum(n_checked) if in_session else 1
    if n_stale < need:
        drift = (f" — {n_stale}/{n_checked} over tolerance, below the {need}-name in-session "
                 f"quorum (drift, worst {worst[0]} {worst[1]:.1f}%)" if n_stale else "")
        print(f"  [{market}] {name}: {n_checked} checked · PASS{drift}")
        return True, ""
    print(f"  [{market}] {name}: {n_checked} checked · FAIL — {n_stale}/{n_checked} stale "
          f"(worst {worst[0]} {worst[1]:.1f}%)")
    return False, f"{market}: {n_stale}/{n_checked} stale vs live (worst {worst[0]} {worst[1]:.1f}%)"


def run(markets: list[str], sample: int = 6, spot_sample: int = 8,
        tolerance: float = validate_brief.PRICE_TOL_PCT,
        reason_file: Path | None = None) -> int:
    """The whole gate. Prints its evidence; returns the exit code."""
    failures: list[str] = []
    for m in markets:
        ok, why = staleness(m, spot_sample, tolerance)
        if not ok:
            failures.append(why)

    # The jury costs Alpha Vantage quota (25/day) — do not spend it judging a
    # workbook step 1 or 2 has already failed.
    if "IN" in markets and not any(f.startswith("IN:") for f in failures):
        r = validate_brief.validate(sample, tolerance)
        print("\n".join(validate_brief.report_lines(r, tolerance)))
        if not r["ok"]:
            failures.append(f"IN: {r['reason']}")

    reason = "; ".join(failures)
    rf = reason_file or REASON_FILE
    try:
        rf.parent.mkdir(parents=True, exist_ok=True)
        rf.write_text(reason)
    except OSError as e:
        print(f"  (reason file not written: {e})")
    if failures:
        bar = "=" * 72
        print(f"\n{bar}\n  ❌  PRICE GATE FAILED — DO NOT SEND\n  {reason}\n{bar}\n")
        return 1
    print("  ✓ price gate passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--markets", nargs="+", default=["IN", "US"], choices=list(MARKETS))
    ap.add_argument("--sample", type=int, default=6, help="names the witness jury samples")
    ap.add_argument("--spot-sample", type=int, default=8, help="liquid names per market for steps 2/3b")
    ap.add_argument("--tolerance", type=float, default=validate_brief.PRICE_TOL_PCT)
    a = ap.parse_args()
    print(f"price gate — markets: {', '.join(a.markets)} (jury sample {a.sample}, "
          f"spot sample {a.spot_sample}, tol {a.tolerance}%)")
    return run(a.markets, a.sample, a.spot_sample, a.tolerance)


if __name__ == "__main__":
    sys.exit(main())
