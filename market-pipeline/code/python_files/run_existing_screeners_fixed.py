#!/usr/bin/env python3
"""
run_existing_screeners_fixed.py — applies the SAME fixed-horizon rigor built
for the literature-sourced factor screens to this repo's OWN production
screeners: Darvas box breakout, Golden Cross (50/200 DMA), and Piotroski
F-Score. Comparable, side-by-side numbers against tonight's other five
screens (momentum, 52w-high, gross profitability, accruals, debt turnaround
— all negative vs. benchmark).

Darvas + Golden Cross reuse `backtest_screeners.detect_darvas_signals()` /
`detect_golden_cross_signals()` DIRECTLY — the actual production detection
logic this repo's own daily scan uses (already entry-bar-fixed 2026-08-22),
not a reimplementation. Scored with `score_fixed_horizon()` from
run_factor_backtests_fixed.py (same staleness guard, same split-artifact
guard, same real benchmarks) rather than backtest_screeners.py's own
compute_forward_returns(), so the numbers are directly comparable to
tonight's other five screens on identical methodology.

Piotroski F-Score (9-point, Piotroski 2000) is built fresh here from
`public.global_fundamentals`, using the SAME per-fiscal-period cross-sectional
pattern as factor_screens.gross_profitability()/accruals() — US only, same
India total_assets gap. Threshold >=7 matches this repo's own existing
convention at build_mailer.py:227 (`pio >= 7`).

    run_existing_screeners_fixed.py --symbols 400
"""
import argparse
import subprocess
import sys
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import backtest_screeners as BS  # noqa: E402 -- real detect_darvas_signals/detect_golden_cross_signals
import signal_tracker as ST  # noqa: E402
from run_factor_backtests_fixed import score_fixed_horizon, report  # noqa: E402


def _liquid_symbols(mkt: str, n: int) -> list:
    p = ST.PANELS.get(mkt)
    if not p or not p.exists():
        return []
    px = ST._panel(p, columns=["Date", "Symbol", "Close", "Volume"])
    px["turn"] = px["Close"] * px["Volume"]
    liq = px.groupby("Symbol")["turn"].median().sort_values(ascending=False)
    counts = px.groupby("Symbol").size()
    ok = [s for s in liq.index if counts.get(s, 0) >= 300]
    return ok[:n]


def scan_price_screener(fn, markets: list, n_symbols: int) -> pd.DataFrame:
    """fn is detect_darvas_signals or detect_golden_cross_signals -- the real
    production functions, unmodified. Walks each symbol's full local price
    history once (these are event detectors, not periodic-rebalance rankers,
    so no monthly loop is needed -- every historical breakout/cross IS the
    signal set)."""
    all_rows = []
    for mkt in markets:
        p = ST.PANELS.get(mkt)
        if not p or not p.exists():
            print(f"    {mkt}: no local panel, skipped"); continue
        syms = _liquid_symbols(mkt, n_symbols)
        px = ST._panel(p, columns=["Date", "Symbol", "Close", "High", "Low", "Volume"])
        px["Symbol"] = px["Symbol"].astype(str).str.upper()
        n_hits = 0
        for sym in syms:
            df = px[px["Symbol"] == sym].set_index("Date").sort_index()
            if len(df) < 260:
                continue
            try:
                sigs = fn(df)
            except Exception:
                continue
            for s in sigs:
                all_rows.append({"symbol": sym, "market": mkt, "signal_date": s["date"]})
                n_hits += 1
        print(f"    {mkt}: {len(syms)} symbols scanned, {n_hits} historical signals")
    return pd.DataFrame(all_rows)


def _psql(query: str) -> pd.DataFrame:
    result = subprocess.run(["psql", "-d", "market_data", "-A", "-F,", "-c", query],
                            capture_output=True, text=True, check=True)
    return pd.read_csv(StringIO(result.stdout))


def piotroski_fscore(mkt: str = "US") -> pd.DataFrame:
    """9-point Piotroski F-Score, computed per fiscal_period with a prior-
    period comparison for the 5 YoY criteria. Same total_assets constraint
    as gross_profitability()/accruals() in factor_screens.py -- US only."""
    if mkt != "US":
        raise ValueError("piotroski_fscore is US-only — same total_assets gap "
                         "documented in factor_screens.py")
    d = _psql("""
        select ticker, fiscal_period, filed, fy_end, net_income, cfo, revenue,
               gross_profit, long_term_debt, current_assets, current_liabilities,
               shares, coalesce(total_assets, equity + total_liabilities) as assets_est
        from public.global_fundamentals
        where market = 'US'
        order by ticker, fiscal_period;
    """)
    if d.empty:
        return d
    d["filed"] = pd.to_datetime(d["filed"], errors="coerce")
    d["fy_end"] = pd.to_datetime(d["fy_end"], errors="coerce")
    d["signal_date"] = d["filed"].fillna(d["fy_end"] + pd.Timedelta(days=90))
    d = d.sort_values(["ticker", "fiscal_period"])
    g = d.groupby("ticker", group_keys=False)

    roa = d["net_income"] / d["assets_est"]
    roa_prior = g["net_income"].shift(1) / g["assets_est"].shift(1)
    lev = d["long_term_debt"] / d["assets_est"]
    lev_prior = g["long_term_debt"].shift(1) / g["assets_est"].shift(1)
    cr = d["current_assets"] / d["current_liabilities"]
    cr_prior = g["current_assets"].shift(1) / g["current_liabilities"].shift(1)
    gm = d["gross_profit"] / d["revenue"]
    gm_prior = g["gross_profit"].shift(1) / g["revenue"].shift(1)
    at = d["revenue"] / d["assets_est"]
    at_prior = g["revenue"].shift(1) / g["assets_est"].shift(1)
    shares_prior = g["shares"].shift(1)

    pts = pd.DataFrame(index=d.index)
    pts["p1_roa_pos"] = (roa > 0).astype(int)
    pts["p2_cfo_pos"] = (d["cfo"] > 0).astype(int)
    pts["p3_droa"] = (roa > roa_prior).astype(int)
    pts["p4_accruals"] = (d["cfo"] > d["net_income"]).astype(int)
    pts["p5_lev_down"] = (lev < lev_prior).astype(int)
    pts["p6_cr_up"] = (cr > cr_prior).astype(int)
    pts["p7_no_dilution"] = (d["shares"] <= shares_prior).astype(int)
    pts["p8_gm_up"] = (gm > gm_prior).astype(int)
    pts["p9_at_up"] = (at > at_prior).astype(int)
    # each point only counts if its inputs are actually present -- a missing
    # field must not silently score as "failed" (0), which would understate
    # every company's real F-score. NaN inputs make that point NaN, excluded
    # from the sum and from the max-achievable-points denominator per row.
    valid = pd.DataFrame({
        "p1_roa_pos": roa.notna(), "p2_cfo_pos": d["cfo"].notna(),
        "p3_droa": roa.notna() & roa_prior.notna(),
        "p4_accruals": d["cfo"].notna() & d["net_income"].notna(),
        "p5_lev_down": lev.notna() & lev_prior.notna(),
        "p6_cr_up": cr.notna() & cr_prior.notna(),
        "p7_no_dilution": d["shares"].notna() & shares_prior.notna(),
        "p8_gm_up": gm.notna() & gm_prior.notna(),
        "p9_at_up": at.notna() & at_prior.notna(),
    })
    for c in pts.columns:
        pts.loc[~valid[c], c] = np.nan

    d["fscore"] = pts.sum(axis=1, skipna=True)
    d["fscore_max"] = valid.sum(axis=1)
    d = d[d["fscore_max"] >= 7]  # need at least 7 of 9 criteria evaluable to trust the score
    hits = d[d["fscore"] >= 7]  # matches build_mailer.py:227's pio>=7 convention
    return hits[["ticker", "signal_date", "fscore", "fscore_max"]].rename(
        columns={"ticker": "symbol"}).assign(market="US").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", type=int, default=400,
                    help="most-liquid symbols per market for the price-based screeners")
    a = ap.parse_args()

    print("=" * 90)
    print("  EXISTING SCREENERS, FIXED-HORIZON BACKTEST — 2026-08-23")
    print("  Same rigor as tonight's literature-sourced screens: real benchmarks,")
    print("  entry-bar-correct, staleness- and split-artifact-guarded, fixed horizons.")
    print("=" * 90)

    print("\n[1/3] Darvas box breakout (detect_darvas_signals, the real production logic)...")
    darvas = scan_price_screener(BS.detect_darvas_signals, ["IN", "US"], a.symbols)
    darvas_scored = score_fixed_horizon(darvas, "symbol") if not darvas.empty else pd.DataFrame()
    report("DARVAS BOX BREAKOUT", darvas_scored, len(darvas))

    print("\n[2/3] Golden Cross (detect_golden_cross_signals, the real production logic)...")
    gc = scan_price_screener(BS.detect_golden_cross_signals, ["IN", "US"], a.symbols)
    gc_scored = score_fixed_horizon(gc, "symbol") if not gc.empty else pd.DataFrame()
    report("GOLDEN CROSS (50/200 DMA)", gc_scored, len(gc))

    print("\n[3/3] Piotroski F-Score >=7 (US only, per-period, real total_assets constraint)...")
    pio = piotroski_fscore("US")
    pio_scored = score_fixed_horizon(pio, "symbol") if not pio.empty else pd.DataFrame()
    report("PIOTROSKI F-SCORE >=7 (US)", pio_scored, len(pio))

    print(f"\n{'='*90}")


if __name__ == "__main__":
    main()
