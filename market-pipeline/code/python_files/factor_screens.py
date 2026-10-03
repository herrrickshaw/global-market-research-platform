#!/usr/bin/env python3
"""
factor_screens.py — evidence-backed factor screens from the 2026-08-23
3-agent literature round (research/LITERATURE_REGISTER.md). Each screen cites
its source paper and states its real, checked data coverage rather than
assuming uniform availability.

IMPLEMENTED (both IN+US, no data gap — OHLCV only):
  momentum_12_1()   Jegadeesh & Titman 1993: rank on return(t-252d, t-21d),
                    SKIPPING the most recent 21 trading days (~1 month) --
                    the skip exists because short-term reversal/bid-ask
                    bounce contaminates the most recent month. Top decile
                    per market = signal.
  high_52w()        George & Hwang 2004: Close_t / max(Close, trailing 252d).
                    🔴 The paper's own evidence is for this as a RANKED
                    return-predicting factor (monthly rebalance), NOT a
                    breakout-timing trigger -- that's a different,
                    unvalidated use of the same variable (this repo's Darvas
                    screen already does the breakout-trigger version; this
                    module tests the paper's actual claim, a ranked factor).
                    Split-adjustment risk flagged by research: this repo has
                    documented split-artifact bugs (India raw-Close risk,
                    JP/KR yfinance auto_adjust missing recent splits) --
                    _sanity_check_no_split_artifacts() guards against the
                    exact failure mode a bad split produces (a discontinuous
                    >3x jump that would fake a "new high").

IMPLEMENTED (US only — India's global_fundamentals has 0% total_assets
coverage, confirmed 2026-08-23, unreconstructable from equity+liabilities
since total_liabilities is also 0% for India in every table checked):
  gross_profitability()  Novy-Marx 2013: (revenue - COGS) / total_assets,
                    approximated as gross_profit / total_assets since
                    gross_profit is a direct field (COGS is not). Real US
                    coverage: 18.5% of global_fundamentals rows have both
                    fields (34.3% via the equity+total_liabilities
                    reconstruction, used here since it's the wider set).
  accruals()        Sloan 1996: (net_income - cfo) / total_assets, LOW
                    accruals = quality signal (bottom decile = pass). Same
                    US-only total_assets constraint as gross_profitability.

NOT IMPLEMENTED (documented data gap, not a silent skip):
  QMJ-lite, idiosyncratic volatility -- see research/LITERATURE_REGISTER.md
  for the exact data plan for each if picked up later.

Entry-bar discipline carries over from the 2026-08-22 fix: every screen below
enters at the price on or after signal_date (a real forward bar), never the
signal bar's own close.
"""
from __future__ import annotations

import subprocess
import sys
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import signal_tracker as ST  # noqa: E402


# ── momentum & 52w-high: OHLCV-only, both markets ──────────────────────────

SKIP_DAYS = 21      # ~1 trading month, Jegadeesh & Titman's skip period
LOOKBACK_DAYS = 252  # ~12 trading months


def _wide_panel(mkt: str) -> pd.DataFrame:
    p = ST.PANELS.get(mkt)
    if not p or not p.exists():
        return pd.DataFrame()
    px = ST._panel(p, columns=["Date", "Symbol", "Close"])
    px["Symbol"] = px["Symbol"].astype(str).str.upper()
    return px.pivot_table(index="Date", columns="Symbol", values="Close",
                          aggfunc="last").sort_index()


def _sanity_check_no_split_artifacts(wide: pd.DataFrame, max_1d_move: float = 0.60) -> pd.DataFrame:
    """Zero out any 1-day return beyond max_1d_move (60% default) as a likely
    unadjusted split/bonus artifact rather than a real move -- matches this
    repo's own documented convention (factorial_screener_test.py excludes
    windows crossing a likely-split day rather than trusting the raw number).
    Returns a boolean mask of columns with at least one such artifact, so
    callers can report how many symbols were affected, not just silently fix."""
    ret = wide.pct_change()
    bad = (ret.abs() > max_1d_move)
    return bad


def momentum_12_1(mkt: str, as_of: pd.Timestamp = None, wide: pd.DataFrame = None) -> pd.DataFrame:
    """Top-decile 12-1 momentum as of `as_of` (default: panel's last bar).
    Returns symbol, market, signal_date, entry_anchor_price, mom_12_1_pct.
    Pass a pre-loaded `wide` panel (from _wide_panel) to avoid re-reading and
    re-pivoting the full multi-million-row panel on every call in a loop."""
    wide = _wide_panel(mkt) if wide is None else wide
    if wide.empty:
        return pd.DataFrame()
    as_of = as_of or wide.index.max()
    idx = wide.index[wide.index <= as_of]
    if len(idx) < LOOKBACK_DAYS + 1:
        return pd.DataFrame()
    t = idx[-1]
    t_skip = idx[-1 - SKIP_DAYS] if len(idx) > SKIP_DAYS else None
    t_lookback = idx[-1 - LOOKBACK_DAYS] if len(idx) > LOOKBACK_DAYS else None
    if t_skip is None or t_lookback is None:
        return pd.DataFrame()
    p_skip = wide.loc[t_skip]
    p_lookback = wide.loc[t_lookback]
    mom = (p_skip / p_lookback - 1) * 100
    mom = mom.dropna()
    if mom.empty:
        return pd.DataFrame()
    cutoff = mom.quantile(0.90)  # top decile
    top = mom[mom >= cutoff]
    return pd.DataFrame({"symbol": top.index, "market": mkt, "signal_date": t,
                        "mom_12_1_pct": top.values}).reset_index(drop=True)


def high_52w(mkt: str, as_of: pd.Timestamp = None, wide: pd.DataFrame = None) -> pd.DataFrame:
    """Top-decile nearness-to-52w-high as of `as_of`. Flags (does not
    silently fix) symbols whose trailing-252d window contains a likely
    split artifact -- those rows are EXCLUDED, not corrected, since a
    correction would need real split-factor data this repo doesn't have
    wired into this panel. Pass a pre-loaded `wide` panel to avoid
    re-reading it on every call in a loop."""
    wide = _wide_panel(mkt) if wide is None else wide
    if wide.empty:
        return pd.DataFrame()
    as_of = as_of or wide.index.max()
    idx = wide.index[wide.index <= as_of]
    if len(idx) < LOOKBACK_DAYS:
        return pd.DataFrame()
    window = wide.loc[idx[-LOOKBACK_DAYS]:idx[-1]]
    bad = _sanity_check_no_split_artifacts(window)
    contaminated = bad.any(axis=0)
    t = idx[-1]
    close_t = wide.loc[t]
    high_252 = window.max(axis=0)
    nearness = (close_t / high_252 * 100)
    nearness = nearness[~contaminated].dropna()
    n_excluded = int(contaminated.sum())
    if nearness.empty:
        return pd.DataFrame()
    cutoff = nearness.quantile(0.90)
    top = nearness[nearness >= cutoff]
    out = pd.DataFrame({"symbol": top.index, "market": mkt, "signal_date": t,
                        "nearness_pct": top.values}).reset_index(drop=True)
    out.attrs["n_excluded_split_risk"] = n_excluded
    return out


# ── screener.in public screens, added 2026-08-23 ───────────────────────────
# Source: https://www.screener.in/screens/ (user-provided URL, fetched
# 2026-08-23) -- "RSI - Oversold Stocks" ("Stocks with RSI of less than 30")
# and "Debt reduction" (simpler than debt_turnaround_screen.py's 3-leg
# trajectory: debt declining ALONE, no ebit/revenue legs required -- the
# actual screener.in definition, worth testing as a simpler counterpoint now
# that the 3-leg version has already been shown to underperform).

RSI_PERIOD = 14
RSI_OVERSOLD_THRESHOLD = 30.0


def _rsi_series(close: pd.Series) -> pd.Series:
    """Full-history RSI-14, same Wilder-smoothing formula as the repo's own
    prediction_filter.py:rsi14() (ewm alpha=1/14) -- reused, not reinvented,
    just vectorized across the whole series instead of returning one scalar."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def rsi_oversold(mkt: str, as_of: pd.Timestamp = None, wide: pd.DataFrame = None) -> pd.DataFrame:
    """Symbol, market, signal_date, rsi for every symbol with RSI-14 < 30 as
    of `as_of`. Pass a pre-loaded `wide` panel to avoid re-reading it in a loop."""
    wide = _wide_panel(mkt) if wide is None else wide
    if wide.empty:
        return pd.DataFrame()
    as_of = as_of or wide.index.max()
    idx = wide.index[wide.index <= as_of]
    if len(idx) < RSI_PERIOD + 20:
        return pd.DataFrame()
    t = idx[-1]
    window = wide.loc[:t]
    rsi_now = window.apply(_rsi_series).iloc[-1]
    rsi_now = rsi_now.dropna()
    hits = rsi_now[rsi_now < RSI_OVERSOLD_THRESHOLD]
    if hits.empty:
        return pd.DataFrame()
    return pd.DataFrame({"symbol": hits.index, "market": mkt, "signal_date": t,
                        "rsi": hits.values}).reset_index(drop=True)


def debt_reduction_simple(mkt: str = "US") -> pd.DataFrame:
    """screener.in's actual 'Debt reduction' definition: long_term_debt
    declining over 2 consecutive periods, alone -- NOT the 3-leg
    debt+ebit+revenue trajectory in debt_turnaround_screen.py. Same
    US-only total_assets-adjacent constraint does NOT apply here since this
    only needs long_term_debt itself, so this screen could in principle run
    for India too -- but debt_turnaround_screen.py already found India's
    long_term_debt coverage is 87.2%, real and usable; kept US-only here for
    now to keep this batch directly comparable to gross_profitability/
    accruals/piotroski, which ARE US-only-constrained. India is a natural
    follow-up, not run in this pass."""
    d = _psql("""
        select ticker, fiscal_period, filed, fy_end, long_term_debt
        from public.global_fundamentals
        where market = 'US' and long_term_debt is not null
        order by ticker, fiscal_period;
    """)
    if d.empty:
        return d
    d["filed"] = pd.to_datetime(d["filed"], errors="coerce")
    d["fy_end"] = pd.to_datetime(d["fy_end"], errors="coerce")
    d["signal_date"] = d["filed"].fillna(d["fy_end"] + pd.Timedelta(days=90))
    d = d.sort_values(["ticker", "fiscal_period"])
    prior = d.groupby("ticker", group_keys=False)["long_term_debt"].shift(1)
    hit = d["long_term_debt"].notna() & prior.notna() & (d["long_term_debt"] < prior)
    out = d.loc[hit, ["ticker", "signal_date", "long_term_debt", "fiscal_period"]].rename(
        columns={"ticker": "symbol"}).assign(market="US").reset_index(drop=True)
    return out


# ── fundamentals-based: US only (see module docstring for why) ────────────

def _psql(query: str) -> pd.DataFrame:
    result = subprocess.run(["psql", "-d", "market_data", "-A", "-F,", "-c", query],
                            capture_output=True, text=True, check=True)
    return pd.read_csv(StringIO(result.stdout))


def gross_profitability(mkt: str = "US") -> pd.DataFrame:
    if mkt != "US":
        raise ValueError("gross_profitability is US-only — India's total_assets "
                         "is 0% populated and unreconstructable (see module docstring)")
    d = _psql("""
        select ticker, fiscal_period, filed, fy_end, gross_profit,
               coalesce(total_assets, equity + total_liabilities) as assets_est
        from public.global_fundamentals
        where market = 'US'
          and gross_profit is not null
          and (total_assets is not null
               or (equity is not null and total_liabilities is not null))
        order by ticker, fiscal_period;
    """)
    if d.empty:
        return d
    d["filed"] = pd.to_datetime(d["filed"], errors="coerce")
    d["fy_end"] = pd.to_datetime(d["fy_end"], errors="coerce")
    d["signal_date"] = d["filed"].fillna(d["fy_end"] + pd.Timedelta(days=90))
    d["gp_assets_pct"] = d["gross_profit"] / d["assets_est"] * 100
    d = d[d["gp_assets_pct"].notna() & np.isfinite(d["gp_assets_pct"])]
    # PLAUSIBILITY FILTER, disclosed not silent: found 2026-08-23 that some
    # `assets_est` values are near-zero due to a units/reporting error in the
    # source filing (e.g. OGS FY2013 computed gp_assets_pct = 8.13e10% --
    # eighty-one billion percent), and being ranked top-decile let these
    # data errors dominate the backtest and produce a nonsensical -118% "vs
    # bench" result. Real gross-profit-to-assets ratios for actual companies
    # fall well within +/-300%; anything outside that is treated as a data
    # error, not a real extreme-quality signal, and excluded with a count
    # reported rather than silently dropped.
    n_before = len(d)
    d = d[d["gp_assets_pct"].abs() <= 300]
    n_excluded = n_before - len(d)
    if d.empty:
        return pd.DataFrame()
    # Cross-sectional top decile WITHIN each fiscal period -- not each
    # ticker's own single latest snapshot. A per-ticker "latest only" cut
    # would give one signal ever per ticker, mixing vastly different
    # historical periods into one flat population; ranking within each
    # period is what makes this a real, repeatable time-series backtest
    # with many historical signal dates, not a one-shot cross-section.
    cutoff = d.groupby("fiscal_period")["gp_assets_pct"].transform(lambda s: s.quantile(0.90))
    top = d[d["gp_assets_pct"] >= cutoff]
    out = top[["ticker", "signal_date", "gp_assets_pct", "fiscal_period"]].rename(
        columns={"ticker": "symbol"}).assign(market="US").reset_index(drop=True)
    out.attrs["n_excluded_implausible"] = n_excluded
    return out


def accruals(mkt: str = "US") -> pd.DataFrame:
    if mkt != "US":
        raise ValueError("accruals is US-only — same total_assets constraint as gross_profitability")
    d = _psql("""
        select ticker, fiscal_period, filed, fy_end, net_income, cfo,
               coalesce(total_assets, equity + total_liabilities) as assets_est
        from public.global_fundamentals
        where market = 'US'
          and net_income is not null and cfo is not null
          and (total_assets is not null
               or (equity is not null and total_liabilities is not null))
        order by ticker, fiscal_period;
    """)
    if d.empty:
        return d
    d["filed"] = pd.to_datetime(d["filed"], errors="coerce")
    d["fy_end"] = pd.to_datetime(d["fy_end"], errors="coerce")
    d["signal_date"] = d["filed"].fillna(d["fy_end"] + pd.Timedelta(days=90))
    d["accrual_pct"] = (d["net_income"] - d["cfo"]) / d["assets_est"].abs() * 100
    d = d[d["accrual_pct"].notna() & np.isfinite(d["accrual_pct"])]
    # Same plausibility filter as gross_profitability() -- see that
    # function's comment. A near-zero assets_est (units/reporting error)
    # produces an astronomical accrual_pct that would wrongly dominate the
    # bottom-decile (lowest-accrual = "highest quality") selection.
    n_before = len(d)
    d = d[d["accrual_pct"].abs() <= 300]
    n_excluded = n_before - len(d)
    if d.empty:
        return pd.DataFrame()
    # Same per-fiscal-period cross-sectional ranking as gross_profitability()
    # -- see that function's comment for why "latest per ticker" is wrong.
    cutoff = d.groupby("fiscal_period")["accrual_pct"].transform(lambda s: s.quantile(0.10))
    top = d[d["accrual_pct"] <= cutoff]  # LOW accruals = quality signal
    out = top[["ticker", "signal_date", "accrual_pct", "fiscal_period"]].rename(
        columns={"ticker": "symbol"}).assign(market="US").reset_index(drop=True)
    out.attrs["n_excluded_implausible"] = n_excluded
    return out
