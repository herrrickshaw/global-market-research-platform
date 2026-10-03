#!/usr/bin/env python3
"""
debt_turnaround_screen.py — companies riding OUT of a debt cycle INTO rising
operating profit and revenue: a fundamentals TRAJECTORY filter, not a
single-snapshot condition like Piotroski or Darvas.

DATA SOURCE AND ITS REAL LIMITS (checked 2026-08-23, do not assume otherwise):
`public.global_fundamentals` is the only table with both a debt figure and
revenue/ebit together. Two other candidates were checked and rejected:
  - India's dedicated PIT source (`market_cache/nse_xbrl/pit_quarterly.parquet`,
    data_registry.py "xbrl.pit_quarterly") has real filing-dated P&L data but
    NO balance-sheet debt field at all -- unusable for the debt leg.
  - `global_fundamentals.filed` (the point-in-time filing date) is 100%
    populated for US but 0.0% for India -- genuinely empty, not sparse.

So: US uses REAL point-in-time `filed` dates (rigorous). India uses the
FYE+90d proxy already established and disclosed elsewhere in this repo
(pe_bands.py) -- NOT point-in-time, a known and inherited limitation, not a
new one introduced here. Coverage (2026-08-23): US long_term_debt 21.1% /
ebit 57.4% of rows; India long_term_debt 87.2% / ebit 81.9%. Requiring all
three legs (debt+ebit+revenue) across 3 consecutive periods shrinks the
usable universe further than either percentage alone suggests -- the real
resulting counts are reported by this script, not assumed.

THE TRAJECTORY (3 consecutive fiscal periods, oldest to newest: t-2, t-1, t):
  DEBT LEG      long_term_debt strictly declining: debt[t] < debt[t-1] < debt[t-2]
  PROFIT LEG    ebit strictly rising AND ebit[t] > 0 -- the ">0" is what makes
                this a TURNAROUND signal ("into an operating profit cycle"),
                not just "losing less money"
  REVENUE LEG   revenue strictly rising: rev[t] > rev[t-1] > rev[t-2]

All three required simultaneously. Signal date = the period-t filing date
(US: real `filed`; India: fy_end + 90 calendar days).

    debt_turnaround_screen.py --scan              # detect all historical signals, both markets
    debt_turnaround_screen.py --scan --market US
    debt_turnaround_screen.py --backtest           # score forward returns on detected signals
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import signal_tracker as ST  # noqa: E402 -- reuse PANELS/_panel/BENCH

OUT = HERE.parent.parent / "research" / "debt_turnaround_signals.parquet"


def detect_trajectory(df: pd.DataFrame) -> pd.DataFrame:
    """df: one market's fundamentals, columns ticker, fiscal_period (sortable),
    signal_date (already resolved -- real filed for US, fy_end+90d for India),
    long_term_debt, ebit, revenue. Returns one row per (ticker, signal_date)
    where the trajectory condition holds looking back from that period.

    Pure function, no I/O -- see test_debt_turnaround_screen.py for the
    exact hand-computed cases this is checked against."""
    df = df.sort_values(["ticker", "fiscal_period"]).copy()
    g = df.groupby("ticker", group_keys=False)

    debt_p1, debt_p2 = g["long_term_debt"].shift(1), g["long_term_debt"].shift(2)
    ebit_p1, ebit_p2 = g["ebit"].shift(1), g["ebit"].shift(2)
    rev_p1, rev_p2 = g["revenue"].shift(1), g["revenue"].shift(2)

    debt_ok = df["long_term_debt"].notna() & debt_p1.notna() & debt_p2.notna() \
        & (df["long_term_debt"] < debt_p1) & (debt_p1 < debt_p2)
    profit_ok = df["ebit"].notna() & ebit_p1.notna() & ebit_p2.notna() \
        & (df["ebit"] > ebit_p1) & (ebit_p1 > ebit_p2) & (df["ebit"] > 0)
    revenue_ok = df["revenue"].notna() & rev_p1.notna() & rev_p2.notna() \
        & (df["revenue"] > rev_p1) & (rev_p1 > rev_p2)

    hit = debt_ok & profit_ok & revenue_ok
    out = df.loc[hit, ["ticker", "market", "signal_date", "long_term_debt",
                       "ebit", "revenue", "fiscal_period"]].copy()
    out["debt_decline_pct"] = ((df.loc[hit, "long_term_debt"] / debt_p2.loc[hit] - 1) * 100)
    out["ebit_growth_pct"] = ((df.loc[hit, "ebit"] / ebit_p2.loc[hit].abs() - 1) * 100
                              if hit.any() else pd.Series(dtype=float))
    out["revenue_growth_pct"] = ((df.loc[hit, "revenue"] / rev_p2.loc[hit] - 1) * 100)
    return out.reset_index(drop=True)


def _psql(query: str) -> pd.DataFrame:
    """Read-only SELECT via psql, no password (matches this repo's
    established access pattern). Returns a DataFrame from CSV output."""
    result = subprocess.run(
        ["psql", "-d", "market_data", "-A", "-F,", "-c", query],
        capture_output=True, text=True, check=True)
    from io import StringIO
    return pd.read_csv(StringIO(result.stdout))


def fetch_market(mkt: str) -> pd.DataFrame:
    d = _psql(f"""
        select ticker, fiscal_period, fy_end, filed,
               long_term_debt, ebit, revenue
        from public.global_fundamentals
        where market = '{mkt}'
          and (long_term_debt is not null or ebit is not null)
        order by ticker, fiscal_period;
    """)
    if d.empty:
        return d
    d["fy_end"] = pd.to_datetime(d["fy_end"], errors="coerce")
    if mkt == "US":
        d["filed"] = pd.to_datetime(d["filed"], errors="coerce")
        d["signal_date"] = d["filed"]
        d.loc[d["signal_date"].isna(), "signal_date"] = d["fy_end"] + pd.Timedelta(days=90)
    else:
        # India: filed is 0% populated -- disclosed FYE+90d proxy, not PIT.
        d["signal_date"] = d["fy_end"] + pd.Timedelta(days=90)
    d["market"] = mkt
    return d


def scan(markets: list[str]) -> pd.DataFrame:
    all_hits = []
    for mkt in markets:
        print(f"  fetching {mkt} fundamentals...")
        d = fetch_market(mkt)
        if d.empty:
            print(f"    {mkt}: no rows"); continue
        hits = detect_trajectory(d)
        print(f"    {mkt}: {d['ticker'].nunique()} tickers, {len(d)} ticker-periods "
              f"-> {len(hits)} trajectory signals ({hits['ticker'].nunique() if len(hits) else 0} unique tickers)")
        all_hits.append(hits)
    out = pd.concat(all_hits, ignore_index=True) if all_hits else pd.DataFrame()
    if not out.empty:
        out.to_parquet(OUT, index=False)
        print(f"\n  -> {OUT}  ({len(out)} signals)")
    return out


def _india_benchmark() -> pd.Series:
    """NIFTYBEES spliced onto the real NIFTY 50 index — now a thin alias for
    ST.india_benchmark(), which is where the construction lives.

    This was a verbatim copy of that splice until 2026-09-11, and it carried two
    bugs the copy in research/stock_pick_performance.py carried too: the seam
    factor divided NIFTYBEES's LAST bar by the index's FIRST bar (off by +0.69%
    once the two series drifted six weeks apart), and concatenating the whole
    index series left duplicate dates wherever the two overlapped. Both are
    fixed in the canonical version. Keep delegating; do not re-inline it."""
    return ST.india_benchmark()


def backtest(signals: pd.DataFrame, min_days: int = 21) -> None:
    today = pd.Timestamp.today().normalize()
    signals = signals.copy()
    signals["signal_date"] = pd.to_datetime(signals["signal_date"])
    signals["days_held"] = (today - signals["signal_date"]).dt.days
    ready = signals[signals["days_held"] >= min_days]
    print(f"\n  {len(ready)} of {len(signals)} signals aged >= {min_days}d")
    if ready.empty:
        print("  nothing to backtest yet"); return

    benches = {}
    rows, skipped = [], {"no_panel": 0, "not_in_panel": 0, "too_early": 0, "no_bench": 0}
    for mkt, grp in ready.groupby("market"):
        p = ST.PANELS.get(mkt)
        if not p or not p.exists():
            skipped["no_panel"] += len(grp); continue
        px = ST._panel(p, columns=["Date", "Symbol", "Close"])
        px["Symbol"] = px["Symbol"].astype(str).str.upper()
        wide = px.pivot_table(index="Date", columns="Symbol", values="Close",
                              aggfunc="last").sort_index()
        if mkt == "IN":
            bench = _india_benchmark()
        else:
            b = ST.BENCH.get(mkt)
            bench = wide[b].dropna() if b in wide.columns else pd.Series(dtype=float)
        for _, r in grp.iterrows():
            sym = str(r["ticker"]).upper()
            if sym not in wide.columns:
                skipped["not_in_panel"] += 1; continue
            s = wide[sym].dropna()
            entry_s = s[s.index <= r["signal_date"]]
            if entry_s.empty:
                skipped["too_early"] += 1; continue
            entry_px, entry_dt = float(entry_s.iloc[-1]), entry_s.index[-1]
            after = s[s.index >= entry_dt]
            if len(after) < 2:
                skipped["too_early"] += 1; continue
            last_px, last_dt = float(after.iloc[-1]), after.index[-1]
            ret = (last_px / entry_px - 1) * 100
            bafter = bench[(bench.index >= entry_dt) & (bench.index <= last_dt)]
            if len(bafter) >= 2:
                bench_ret = (float(bafter.iloc[-1]) / float(bafter.iloc[0]) - 1) * 100
            else:
                bench_ret = np.nan
                skipped["no_bench"] += 1
            rows.append({"ticker": sym, "market": mkt, "signal_date": r["signal_date"],
                        "entry_date": entry_dt, "entry_price": entry_px,
                        "last_price": last_px, "ret_pct": ret, "bench_ret_pct": bench_ret,
                        "xret_pct": ret - bench_ret if pd.notna(bench_ret) else np.nan,
                        "days_held": (last_dt - entry_dt).days})
    d = pd.DataFrame(rows)
    skip_msg = ", ".join(f"{k}={v}" for k, v in skipped.items() if k != "no_bench" and v)
    print(f"  scored: {len(d)}  skipped: {skip_msg or 'none'}")
    if skipped["no_bench"]:
        print(f"  {skipped['no_bench']} scored rows have no benchmark window covering "
              f"their hold (xret_pct = NaN, excluded from 'vs bench' medians, NOT "
              f"dropped from ret_pct)")
    if d.empty:
        return
    print(f"\n  {'market':<7}{'n':>5}{'med ret%':>10}{'med vs bench':>14}{'win%':>7}{'med days':>10}")
    for mkt, g in d.groupby("market"):
        print(f"  {mkt:<7}{len(g):>5}{g.ret_pct.median():>10.2f}"
              f"{g.xret_pct.median():>14.2f}{(g.ret_pct>0).mean()*100:>6.0f}%"
              f"{g.days_held.median():>10.0f}")
    print(f"\n  OVERALL: n={len(d)}, median return {d.ret_pct.median():.2f}%, "
          f"median vs benchmark {d.xret_pct.median():.2f}%, "
          f"win rate (raw, not vs bench) {(d.ret_pct>0).mean()*100:.0f}%")
    print(f"  'vs benchmark' is what matters — beating the index over the SAME "
          f"holding period, not the sign of the raw return, which is inflated here "
          f"by uneven, often multi-year hold lengths (median {d.days_held.median():.0f}d).")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--market", type=str, default=None, help="IN or US; default both")
    ap.add_argument("--min-days", type=int, default=21)
    a = ap.parse_args()
    markets = [a.market] if a.market else ["US", "IN"]

    if a.scan or (not a.backtest):
        signals = scan(markets)
    else:
        signals = pd.read_parquet(OUT) if OUT.exists() else pd.DataFrame()

    if a.backtest:
        if signals.empty and OUT.exists():
            signals = pd.read_parquet(OUT)
        backtest(signals, a.min_days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
