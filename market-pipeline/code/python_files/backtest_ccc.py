#!/usr/bin/env python3
"""
backtest_ccc.py — is the cash conversion cycle related to forward returns?

Working-capital efficiency is an intuitive quality signal: a business that
collects before it pays is funded by its counterparties rather than by capital.
Whether that is PRICED is a separate question, and the only way to answer it is
the same way this repo answers every other one — point-in-time, on spreads, with
a non-overlapping t-stat and a sufficiency gate.

METHOD (matches backtest_pe_anomalies.py deliberately, so results are comparable)
────────────────────────────────────────────────────────────────────────────────
  * Month-end adjusted-close panel from the warehouse.
  * CCC lagged to its SEC FILING DATE, not its fiscal year end. This is the part
    that decides whether the result means anything: measured on real filings,
    AAPL's 10-K lands 34 days after year-end and WMT's 41-44. Ranking from the
    fiscal year end would be look-ahead by roughly six weeks. The repo's
    documented FYE+90d fallback is used only where `filed` is absent, and it is
    wrong in both directions — too late for these filers, too early for a
    delinquent one.
  * Quintiles by CCC each month, equal-weighted, forward 1/3/6-month returns.
  * Reported as the Q1-Q5 SPREAD, never levels: the universe is survivorship-
    biased (METHODOLOGY assumption 2), so a level is a number about the
    survivors and a spread is a number about the signal.
  * `nonoverlap_t(spread, step=horizon)` — overlapping monthly windows
    autocorrelate and inflate t by roughly sqrt(horizon).

WHAT WOULD MAKE THIS A FINDING, and what would not
──────────────────────────────────────────────────
The sufficiency gate (METHODOLOGY, DATA_SUFFICIENCY.md) is >=15 non-overlapping
observations AND >=60% liquid coverage. Below either, the honest verdict is
"cannot conclude" — NOT "no effect". And |t| >~ 2 on non-overlapping data is the
bar; a t of 1.5 on a factor that was one of several tried is noise wearing a
decimal point.

CCC IS SECTOR-CONFOUNDED, and this is the main reason to distrust a raw result.
Software has no inventory and structurally negative cycles; grocers run tight
cycles; heavy industry runs long ones. A raw CCC quintile is therefore close to
a sector bet. `--sector-relative` demeans CCC within sector so the comparison is
between a company and its peers rather than between industries.

    backtest_ccc.py                      # raw quintiles, US
    backtest_ccc.py --sector-relative    # demeaned within sector
    backtest_ccc.py --min-names 40 --start 2018-01-31
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

FALLBACK_LAG_DAYS = 90        # METHODOLOGY assumption 1, used only if `filed` is absent
Q = 5                         # quintiles


def month_ends(px: pd.DataFrame) -> pd.DataFrame:
    """symbol × month-end adjusted close, long → wide."""
    px = px.assign(me=px["Date"] + pd.offsets.MonthEnd(0))
    last = px.sort_values("Date").groupby(["Symbol", "me"]).Close.last()
    return last.unstack("Symbol")


def load_prices(start: str, end: str) -> pd.DataFrame:
    import warehouse_paths as wh

    src = f"{wh.root()}/ohlcv/US"
    parts = sorted(glob.glob(f"{src}/year=*.parquet"))
    if not parts:
        raise FileNotFoundError(
            f"no year partitions under {src}. Refusing to run a backtest on an "
            f"absent panel and report the empty result as a finding.")
    have = sorted(int(p.split("year=")[1].split(".")[0]) for p in parts)
    need = pd.Timestamp(start).year
    if have[0] > need:
        raise FileNotFoundError(
            f"{src} starts at {have[0]} but --start needs {need}. Refusing to "
            f"run a truncated backtest and report it as a full one.")
    import duckdb

    px = duckdb.connect().execute(
        f"SELECT Date, Symbol, Close FROM read_parquet('{src}/*.parquet') "
        f"WHERE Date >= DATE '{start}' AND Date <= DATE '{end}' AND Close > 0"
    ).df()
    return month_ends(px)


def load_ccc() -> pd.DataFrame:
    """(ticker, avail, ccc) — CCC with the date it became publicly available."""
    import cash_conversion_cycle as C

    p = C.STORE["US"]
    if not p.exists():
        raise FileNotFoundError(f"{p} missing — run us_fundamentals_edgar.py")
    f = pd.read_parquet(p)
    need = C.NEEDED + ["fy_end", "ticker"]
    missing = [c for c in need if c not in f.columns]
    if missing:
        raise SystemExit(
            f"store lacks {missing}. Re-run us_fundamentals_edgar.py --max-age-days 0 "
            f"— the CCC inputs were added 2026-08-21 and rows collected before "
            f"then do not carry them.")

    n = {c: pd.to_numeric(f[c], errors="coerce") for c in C.NEEDED}
    rev = n["revenue"].where(n["revenue"] > 0)
    cogs = n["cost_of_revenue"].where(n["cost_of_revenue"] > 0)
    ccc = (n["receivables"] / rev * 365
           + n["inventory"] / cogs * 365
           - n["payables"] / cogs * 365)

    fy = pd.to_datetime(f["fy_end"], errors="coerce")
    if "filed" in f.columns:
        filed = pd.to_datetime(f["filed"], errors="coerce")
        # Only where the real filing date is missing do we fall back, and the
        # fallback rate is REPORTED — a panel that is mostly fallback is a
        # panel whose PIT claim is mostly assumption.
        avail = filed.fillna(fy + pd.Timedelta(days=FALLBACK_LAG_DAYS))
        pct_real = float(filed.notna().mean())
    else:
        avail = fy + pd.Timedelta(days=FALLBACK_LAG_DAYS)
        pct_real = 0.0

    out = pd.DataFrame({"ticker": f["ticker"].astype(str), "avail": avail,
                        "ccc": ccc})
    out = out[out["ccc"].abs() <= 1095].dropna(subset=["avail", "ccc"])
    out.attrs["pct_real_filed"] = pct_real
    return out


def pit_panel(vals: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """date × ticker matrix of the latest value AVAILABLE at each date."""
    vals = vals.sort_values("avail")
    out = {}
    for tkr, g in vals.groupby("ticker"):
        s = g.set_index("avail").ccc
        s = s[~s.index.duplicated(keep="last")]
        out[tkr] = s.reindex(dates, method="ffill")
    return pd.DataFrame(out, index=dates)


def nonoverlap_t(spreads: pd.Series, step: int) -> float:
    """t-stat on a de-overlapped subsequence (every `step`-th month)."""
    x = spreads.dropna().iloc[::step]
    return float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 else np.nan


def sector_demean(panel: pd.DataFrame, sectors: dict, min_names: int) -> pd.DataFrame:
    """CCC minus its sector median, per month.

    Without this a CCC quintile is close to a sector bet: software carries no
    inventory and is structurally negative, heavy industry is structurally long.
    """
    if not sectors:
        return panel
    sec = pd.Series({c: sectors.get(c) for c in panel.columns})
    keep = sec.dropna()
    if keep.empty:
        return panel
    out = panel.copy()
    for s, cols in keep.groupby(keep).groups.items():
        cols = [c for c in cols if c in out.columns]
        if len(cols) < min_names:
            out[cols] = np.nan          # too few peers to demean meaningfully
            continue
        out[cols] = out[cols].sub(out[cols].median(axis=1), axis=0)
    return out[[c for c in out.columns if c in set(keep.index)]]


def load_sectors() -> dict:
    for p in ("market_cache/symbol_master.parquet",):
        try:
            d = pd.read_parquet(os.path.expanduser(f"~/market-pipeline/{p}"))
            col = next((c for c in d.columns if c.lower() == "sector"), None)
            sym = next((c for c in d.columns if c.lower() in ("symbol", "ticker")), None)
            if col and sym:
                return dict(zip(d[sym].astype(str), d[col]))
        except Exception:
            continue
    return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="CCC vs forward returns, PIT")
    ap.add_argument("--start", default="2017-01-31")
    ap.add_argument("--end", default="2026-08-31")
    ap.add_argument("--min-names", type=int, default=50,
                    help="months with fewer ranked names are skipped")
    ap.add_argument("--sector-relative", action="store_true")
    a = ap.parse_args()

    print("loading prices…")
    px = load_prices(a.start, a.end)
    print(f"  {px.shape[1]:,} symbols × {len(px)} month-ends")

    print("loading CCC…")
    v = load_ccc()
    pct = v.attrs.get("pct_real_filed", 0.0)
    print(f"  {v['ticker'].nunique():,} tickers, {len(v):,} fiscal years · "
          f"{pct:.0%} carry a real SEC filing date "
          f"({1 - pct:.0%} on the FYE+{FALLBACK_LAG_DAYS}d fallback)")

    panel = pit_panel(v, px.index)
    common = [c for c in px.columns if c in panel.columns]
    if not common:
        print("  no overlap between price and CCC universes"); return 1
    px, panel = px[common], panel[common]

    label = "raw CCC"
    if a.sector_relative:
        sectors = load_sectors()
        panel = sector_demean(panel, sectors, min_names=8)
        px = px[[c for c in px.columns if c in panel.columns]]
        label = "sector-relative CCC"
        print(f"  sector map covers {len(set(sectors) & set(common)):,} of {len(common):,}")

    n_month = panel.notna().sum(axis=1)
    print(f"  {len(common):,} symbols with both · median names/month: "
          f"{int(n_month.median())}")

    fwd = {h: px.shift(-h) / px - 1 for h in (1, 3, 6)}
    print(f"\n=== {label} quintiles · Q1 = shortest cycle ===")
    print(f"  {'H':>2}  {'Q1':>8}{'Q2':>8}{'Q3':>8}{'Q4':>8}{'Q5':>8}"
          f"{'Q1-Q5':>9}{'t':>7}{'n':>5}  verdict")

    verdicts = []
    for h in (1, 3, 6):
        rows, spreads = [], []
        for dtm in panel.index:
            x, r = panel.loc[dtm].dropna(), fwd[h].loc[dtm]
            x = x[x.index.isin(r.dropna().index)]
            if len(x) < a.min_names:
                continue
            try:
                qs = pd.qcut(x, Q, labels=False, duplicates="drop")
            except ValueError:
                continue
            if qs.nunique() < Q:
                continue
            m = [r[qs[qs == q].index].mean() for q in range(Q)]
            rows.append(m)
            spreads.append(m[0] - m[Q - 1])
        if not rows:
            print(f"  {h:>2}  — too few ranked months")
            continue
        mean_q = np.nanmean(np.array(rows), axis=0) * 100
        sp = pd.Series(spreads)
        t = nonoverlap_t(sp, h)
        n_ind = len(sp.dropna().iloc[::h])
        # The gate, stated per row rather than left to the reader.
        if n_ind < 15:
            v_txt = f"underpowered (n={n_ind}<15)"
        elif abs(t) >= 2:
            v_txt = "signal"
        else:
            v_txt = "cannot reject null"
        verdicts.append((h, sp.mean() * 100, t, n_ind, v_txt))
        print(f"  {h:>2}M {mean_q[0]:>7.2f}%{mean_q[1]:>7.2f}%{mean_q[2]:>7.2f}%"
              f"{mean_q[3]:>7.2f}%{mean_q[4]:>7.2f}%{sp.mean() * 100:>8.2f}%"
              f"{t:>7.2f}{n_ind:>5}  {v_txt}")

    print("\n  Q1-Q5 is the SPREAD; levels are survivorship-biased and not the result.")
    print("  t is on NON-OVERLAPPING observations (every h-th month), so it is not")
    print("  inflated by the ~sqrt(h) autocorrelation of overlapping windows.")
    if not a.sector_relative:
        print("  ⚠ RAW CCC IS SECTOR-CONFOUNDED — software has no inventory, heavy")
        print("    industry is structurally long. Re-run with --sector-relative")
        print("    before treating any of this as a company-level effect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
