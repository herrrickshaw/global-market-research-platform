#!/usr/bin/env python3
"""
backtest_overnight_intraday.py — replicate Lou, Polk & Skouras (2019), "A tug of war:
overnight versus intraday expected returns", JFE 134(1), on our five markets.

Paper (Table I, Table II, App. Table A2): split each stock's return into
  intraday_s  = Close_s / Open_s - 1
  overnight_s = (1 + close_to_close_s) / (1 + intraday_s) - 1
compound both within each month, sort stocks into deciles at month-end and look at the
NEXT month's overnight and intraday components of the winner-minus-loser portfolio.
Claims tested:
  ON   sort on last month's overnight return -> continues overnight, reverses intraday
  ID   sort on last month's intraday return  -> continues intraday, reverses overnight
  MOM  12-2 momentum                          -> profits earned overnight, not intraday
  STR  1-month reversal (low minus high)      -> reported for its component split

Deviations from the paper, forced by the data (all disclosed in the report):
  * open = exchange daily open, not the 9:30-10:00 VWAP (paper fn. 8: results robust to
    CRSP open / first trade). Flat opens (Open == previous close) zero the overnight
    leg; the robustness run drops stocks with >20% such days in the sort month.
  * no market cap: "value weight" = formation-month median turnover, normalised within
    exchange suffix (GBp-quoted .L, SEK, HUF names would otherwise swamp EUR ones).
    NYSE breakpoints -> own-market quantiles; microcap screen -> drop bottom 30% by
    turnover (+ $5 floor in US).
  * raw long-short spreads with Newey-West(3) t-stats; no CAPM/FF3 (no factor data for
    JP/KR/IN/EU).
  * stock-months containing a price break (close or open outside 0.5x-2x the prior
    close — splits the adjuster missed, bad prints) are dropped in the sort AND holding
    month. The holding-month filter uses future data; it removes data errors plus a few
    real crashes/doublings, so treat magnitudes as slightly conservative.

Data: warehouse ohlcv (US/JP/KR yfinance-adjusted + corrected_symbols overlay; IN
split-adjusted panel; EU raw). Output: reports/overnight_intraday_backtest.md and
reports/overnight_intraday_monthly.csv.

Usage:  backtest_overnight_intraday.py [--markets KR,JP]   (default: all five)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import warehouse_paths as _wh

MARKETS = ["US", "JP", "KR", "IN", "EU"]
START = "2016-01-01"
LAST_HOLD = "2026-08"         # last complete holding month
MIN_DAYS = 15                 # trading days required in a month
LIQ_CUT = 0.30                # drop bottom 30% by normalised turnover
US_PRICE_FLOOR = 5.0
FLAT_OPEN_MAX = 0.20
NW_LAGS = 3
MIN_NAMES = 100               # >= 10 names per decile
REPORT = HERE / "reports" / "overnight_intraday_backtest.md"
MONTHLY_CSV = HERE / "reports" / "overnight_intraday_monthly.csv"


def _source_sql(mkt: str) -> str:
    """SELECT producing Date, Symbol, Open, Close, Volume for one market."""
    cols = "Date, Symbol, Open, Close, Volume"
    if mkt == "IN":
        return f"SELECT {cols} FROM read_parquet('{_wh.ohlcv_adj_in()}/*.parquet')"
    base = f"read_parquet('{_wh.market(mkt)}/*.parquet')"
    overlay = _wh.ohlcv().parent / "ohlcv_adj" / mkt / "corrected_symbols.parquet"
    if mkt in ("US", "JP", "KR") and overlay.exists():
        return (f"SELECT {cols} FROM {base} WHERE Symbol NOT IN "
                f"(SELECT DISTINCT Symbol FROM read_parquet('{overlay}')) "
                f"UNION ALL SELECT {cols} FROM read_parquet('{overlay}')")
    return f"SELECT {cols} FROM {base}"


def monthly_panel(con: duckdb.DuckDBPyConnection, mkt: str) -> pd.DataFrame:
    """Per stock-month: total, overnight and intraday returns plus screens."""
    q = f"""
    WITH d AS (
      SELECT Symbol, Date, Open, Close, Volume,
             LAG(Close) OVER (PARTITION BY Symbol ORDER BY Date) AS pc
      FROM ({_source_sql(mkt)})
      WHERE Date >= '{START}' AND Close > 0
    ), r AS (
      SELECT Symbol, Date, date_trunc('month', Date) AS month, Close, Volume,
             Close / pc - 1                                          AS cc,
             CASE WHEN Open > 0 THEN Close / Open - 1 ELSE 0 END     AS intra,
             (Close / pc > 2 OR Close / pc < 0.5
              OR (Open > 0 AND (Open / pc > 2 OR Open / pc < 0.5)))  AS brk,
             (Open = pc)                                             AS flat_open
      FROM d WHERE pc > 0
    )
    SELECT Symbol, month,
           count(*)                                         AS n_days,
           exp(sum(ln(1 + cc))) - 1                         AS ret,
           exp(sum(ln(1 + intra))) - 1                      AS r_id,
           exp(sum(ln((1 + cc) / (1 + intra)))) - 1         AS r_on,
           bool_or(brk)                                     AS brk,
           avg(CASE WHEN flat_open THEN 1 ELSE 0 END)       AS flat_share,
           median(Close * coalesce(Volume, 0))              AS turnover,
           arg_max(Close, Date)                             AS px
    FROM r
    GROUP BY Symbol, month
    """
    df = con.execute(q).df()
    df["month"] = pd.to_datetime(df["month"]).dt.to_period("M")
    # break months carry garbage returns — null them so they can neither sort nor pay
    df.loc[df["brk"], ["ret", "r_on", "r_id"]] = np.nan
    # currency-invariant turnover: divide by the suffix group's monthly median
    df["suffix"] = df["Symbol"].str.extract(r"(\.[A-Z]+)$", expand=False).fillna("")
    med = df.groupby(["month", "suffix"])["turnover"].transform("median").replace(0, np.nan)
    df["turn_norm"] = (df["turnover"] / med).fillna(0.0)
    return df


def signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add formation signals and next-month (holding) returns per stock."""
    df = df.sort_values(["Symbol", "month"]).reset_index(drop=True)
    df["_lr"] = np.log1p(df["ret"])
    g = df.groupby("Symbol", sort=False)
    mnum = df["month"].apply(lambda p: p.year * 12 + p.month)   # integer month index

    # next-month holding returns — only when the next row is the next calendar month
    fwd_ok = g["month"].shift(-1).notna() & (mnum.groupby(df["Symbol"]).shift(-1) == mnum + 1)
    for c in ("ret", "r_on", "r_id", "n_days"):
        df[f"fwd_{c}"] = g[c].shift(-1).where(fwd_ok)

    # 12-2 momentum for holding month t+1: returns of months t-10..t-1 plus t-11 ...
    # i.e. the 11 months ending the month before the formation month (skip month t)
    lagged = g["_lr"].shift(1)
    mom = (lagged.groupby(df["Symbol"]).rolling(11, min_periods=11).sum()
           .reset_index(level=0, drop=True))
    span_ok = (mnum - mnum.groupby(df["Symbol"]).shift(11)) == 11
    df["mom"] = np.expm1(mom).where(span_ok)
    return df.drop(columns="_lr")


def _wavg(x: pd.Series, w: pd.Series) -> float:
    w = w.clip(lower=0)
    return float(np.average(x, weights=w)) if w.sum() > 0 else float(x.mean())


def ls_series(df: pd.DataFrame, mkt: str, flat_filter: bool) -> pd.DataFrame:
    """Monthly winner-minus-loser returns (EW and VW) for each strategy."""
    base = df[(df["n_days"] >= MIN_DAYS) & (df["fwd_n_days"] >= MIN_DAYS)
              & df["ret"].notna() & df["fwd_ret"].notna()]
    if mkt == "US":
        base = base[base["px"] >= US_PRICE_FLOOR]
    if flat_filter:
        base = base[base["flat_share"] <= FLAT_OPEN_MAX]
    base = base[base["month"] < pd.Period(LAST_HOLD, "M")]
    strategies = {"ON": ("r_on", 1), "ID": ("r_id", 1), "MOM": ("mom", 1), "STR": ("ret", -1)}
    out = []
    for month, cs in base.groupby("month"):
        cs = cs[cs["turn_norm"] >= cs["turn_norm"].quantile(LIQ_CUT)]
        for name, (col, sign) in strategies.items():
            x = cs.dropna(subset=[col])
            if len(x) < MIN_NAMES:
                continue
            dec = pd.qcut(x[col].rank(method="first"), 10, labels=False)
            hi, lo = x[dec == 9], x[dec == 0]
            if sign < 0:
                hi, lo = lo, hi
            row = {"market": mkt, "flat_filter": flat_filter, "strategy": name,
                   "month": month + 1, "n_stocks": len(x)}
            for comp in ("ret", "r_on", "r_id"):
                fc = f"fwd_{comp}"
                row[f"ew_{comp}"] = hi[fc].mean() - lo[fc].mean()
                row[f"vw_{comp}"] = _wavg(hi[fc], hi["turn_norm"]) - _wavg(lo[fc], lo["turn_norm"])
            out.append(row)
    return pd.DataFrame(out)


def nw_mean(x: pd.Series) -> tuple[float, float, int]:
    """Mean (percent per month) and Newey-West t-stat."""
    x = x.dropna()
    if len(x) < 24:
        return np.nan, np.nan, len(x)
    fit = sm.OLS(x.values, np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    return 100 * fit.params[0], fit.tvalues[0], len(x)


def summarise(ls: pd.DataFrame) -> pd.DataFrame:
    rows = []
    keys = ["flat_filter", "strategy", "market"]
    for key, grp in ls.groupby(keys):
        r = dict(zip(keys, key))
        n = 0
        for w in ("vw", "ew"):
            for comp, label in (("ret", "close"), ("r_on", "night"), ("r_id", "day")):
                m, t, n = nw_mean(grp[f"{w}_{comp}"])
                r[f"{w}_{label}"], r[f"{w}_{label}_t"] = m, t
        r["months"], r["avg_stocks"] = n, grp["n_stocks"].mean()
        rows.append(r)
    return pd.DataFrame(rows)


def pooled(ls: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight average across markets of each month's long-short return."""
    cols = [c for c in ls.columns if c[:3] in ("vw_", "ew_")] + ["n_stocks"]
    avg = ls.groupby(["flat_filter", "strategy", "month"])[cols].mean().reset_index()
    avg["market"] = "ALL (avg)"
    return avg


def fmt_table(s: pd.DataFrame, w: str, markets: list[str]) -> str:
    head = ("| Strategy | Market | Months | Stocks | Close-to-close | Overnight | Intraday |\n"
            "|---|---|---:|---:|---:|---:|---:|\n")
    order = {"ON": 0, "ID": 1, "MOM": 2, "STR": 3}
    mk = {m: i for i, m in enumerate(markets + ["ALL (avg)"])}
    s = s.assign(_o=s["strategy"].map(order), _m=s["market"].map(mk)).sort_values(["_o", "_m"])

    def cell(r, k):
        v, t = r[f"{w}_{k}"], r[f"{w}_{k}_t"]
        return f"{v:+.2f}% ({t:+.1f})" if pd.notna(v) else "n/a"

    lines = [f"| {r['strategy']} | {r['market']} | {r['months']} | {r['avg_stocks']:.0f} "
             f"| {cell(r, 'close')} | {cell(r, 'night')} | {cell(r, 'day')} |"
             for _, r in s.iterrows()]
    return head + "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default=",".join(MARKETS))
    markets = [m.strip().upper() for m in ap.parse_args().markets.split(",")]

    con = duckdb.connect()
    con.execute("SET threads=6")
    series = []
    for mkt in markets:
        print(f"[{mkt}] building monthly panel ...", flush=True)
        panel = signals(monthly_panel(con, mkt))
        print(f"[{mkt}] {panel['Symbol'].nunique():,} symbols, {len(panel):,} stock-months, "
              f"{int(panel['brk'].sum()):,} break months dropped", flush=True)
        for flat in (False, True):
            series.append(ls_series(panel, mkt, flat))
    ls = pd.concat(series, ignore_index=True)
    if len(markets) > 1:
        ls = pd.concat([ls, pooled(ls)], ignore_index=True)
    ls.to_csv(MONTHLY_CSV, index=False)
    summ = summarise(ls)

    md = [
        "# Overnight vs intraday tug of war — replication on " + "/".join(markets),
        "",
        "Replicates Lou, Polk & Skouras (2019), *A tug of war: overnight versus intraday "
        "expected returns*, JFE 134(1) — Table I (ON/ID sorts), Table II (MOM, STR) and "
        "Appendix Table A2 (international). Generated by `backtest_overnight_intraday.py`.",
        "",
        f"Holding months: {ls['month'].min()} – {ls['month'].max()}. Cells: mean monthly "
        f"winner-minus-loser (decile 10 − 1) return, Newey-West({NW_LAGS}) t-stat in "
        "parentheses. STR is low-minus-high. ALL (avg) = equal-weight average across "
        "markets of each month's spread.",
        "",
        "**Paper benchmarks (US 1993–2013, VW, excess):** ON sort → overnight +3.47% "
        "(t 16.6), intraday −3.24% (t −9.3). ID sort → intraday +2.19% (t 6.7), overnight "
        "−1.81% (t −8.4). Nine non-US markets pooled: ON overnight +2.31% (t 6.9), ID "
        "intraday +2.80% (t 6.2), cross-period reversal of similar size. MOM (12-2): "
        "overnight CAPM alpha +0.98% (t 3.8), intraday −0.02% (t −0.1). STR (low − high): "
        "no close-to-close effect; overnight +0.93% (t 4.3), intraday −1.05% (t −3.3).",
        "",
    ]
    for flat, title in ((False, "Main run"), (True, "Robustness: drop stocks with >20% flat opens")):
        s = summ[summ["flat_filter"] == flat]
        md += [f"## {title}", "", "### Turnover-weighted (value-weight proxy)", "",
               fmt_table(s, "vw", markets), "", "### Equal-weighted", "",
               fmt_table(s, "ew", markets), ""]
    md += [
        "## Deviations from the paper",
        "",
        "- Open is the exchange daily open, not the 9:30–10:00 VWAP (paper footnote 8 "
        "reports robustness to CRSP opens). Flat opens set the overnight leg to zero.",
        "- No market cap: weights are formation-month median turnover normalised within "
        "exchange suffix; breakpoints are own-market quantiles; the microcap screen is the "
        f"bottom {LIQ_CUT:.0%} by turnover (plus a ${US_PRICE_FLOOR:.0f} floor in US).",
        "- Raw long-short spreads only — no CAPM/FF3 adjustment, no transaction costs.",
        "- Stock-months with a price break (close or open outside 0.5×–2× prior close) are "
        "dropped in both sort and holding month; the holding-month filter uses future data.",
        "- ~10 years (2016–2026) vs the paper's 21; EU is a pooled multi-exchange panel on "
        "raw (unadjusted) prices.",
        "",
    ]
    REPORT.write_text("\n".join(md))
    print(f"wrote {REPORT}\nwrote {MONTHLY_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
