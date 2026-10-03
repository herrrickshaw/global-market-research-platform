#!/usr/bin/env python3
"""
purge_embargo.py — purging and embargo for time-series train/test splits.

WHY THIS EXISTS. 2026-08-23 research round (4 parallel agents: foundational
algorithm, critiques, empirical effect-sizes, implementation reality; see
research/LITERATURE_REGISTER.md "CPCV / embargo" section for full sourcing)
confirmed the repo has zero purging/embargo anywhere — `walk_forward_backtest.py`
splits 60/20/20 with a literal ZERO-day gap between train and test while
scoring forward returns up to 252 trading days out, so a training observation's
own label can extend past the test boundary and leak information the model
should not have had. The research converged, independently, across all four
agents, on the same conclusion: build this minimal function, do NOT build full
Combinatorial Purged Cross-Validation — CPCV's documented value is a Sharpe
*distribution* for overfitting detection (via C(N,k) combinatorial retrains),
not leakage prevention, which purging + embargo alone already solve, at a
fraction of the complexity and zero combinatorial blowup.

THE TWO MECHANISMS (kept as separate, independently testable primitives,
matching how the literature describes them as distinct — AFML Ch.7 §§7.4.1-2,
p.105/p.107, via mlfinlab's docs+source and reasonableddeviations.com):

  PURGE   — drop any training observation whose LABEL WINDOW [t, t+horizon]
            overlaps the test period's label-relevant range. This is the
            mechanism that actually prevents the leakage: without it, a
            training row dated just before the test period can have a label
            computed from prices INSIDE the test period.

  EMBARGO — an additional buffer of `embargo_days` beyond what pure purging
            requires. No single literature formula exists for its length; the
            reference implementation (mlfinlab) defaults to a % of the
            dataset, while several expositors argue "embargo >= horizon" on
            theoretical grounds. This repo's longest evaluated horizon is 252
            trading days (HORIZONS in walk_forward_backtest.py /
            backtest_screeners.py), so `EMBARGO_DAYS = 252` below is the
            conservative, source-justified default — not a fitted number.

For a SIMPLE ONE-DIRECTIONAL WALK-FORWARD split (train always precedes test
precedes val, no k-fold wraparound), the two mechanisms combine into one
required gap: `gap = horizon_days + embargo_days` trading days between the
train/test boundary and again between test/val. `train_test_val_gap()` below
implements exactly that for `walk_forward_backtest.py`'s PERIODS dict shape.
The lower-level `purge_mask()` / `embargo_mask()` are kept general so a future
k-fold or CPCV scheme (if ever justified) can reuse them without a rewrite.

🔴 MEASURED 2026-08-23 against this repo's own PERIODS and real NSE trading
dates (2016-01-01 -> 2026-07-13): the full `EMBARGO_DAYS=252` default (matching
the longest evaluated horizon) is TOO EXPENSIVE for two of three period
configs — `3y` and `5y` don't have enough remaining history after the required
504-trading-day (252+252) gap to fit a val window at all; `purged_period_cfg()`
correctly raises rather than silently producing a garbage result. Even `10y`
survives but test_start shifts 743 calendar days later. This is the exact
"purge+embargo data loss in tension with sample size" tension the 2026-08-23
critiques-agent predicted from the literature, now confirmed on real data. A
horizon-matched, smaller embargo — e.g. `horizon_days=63, embargo_days=63`
(matched to the T+3mo horizon rather than the max) — fits all three periods
comfortably (~185-190 calendar day shift each) and is the practical default
for THIS repo's period definitions; `EMBARGO_DAYS=252` remains the module's
general-purpose default for callers with deeper history.

USAGE
    from purge_embargo import purge_mask, embargo_mask, train_test_val_gap

    # low-level, general (works for k-fold too):
    purged = purge_mask(train_dates, test_start, test_end, horizon_days=252)
    embargoed = embargo_mask(train_dates, boundary=test_end, embargo_days=252,
                             direction="after")
    keep = train_dates[~(purged | embargoed)]

    # high-level, for a simple chronological train/test/val split:
    test_start, val_start = train_test_val_gap(
        train_end=pd.Timestamp("2024-12-31"),
        naive_test_start=pd.Timestamp("2025-01-02"),
        naive_val_start=pd.Timestamp("2025-07-01"),
        horizon_days=252, embargo_days=252, trading_dates=nifty_index_dates)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EMBARGO_DAYS = 252  # conservative default: this repo's longest evaluated horizon


def purge_mask(obs_dates: pd.DatetimeIndex, boundary_start: pd.Timestamp,
               boundary_end: pd.Timestamp, horizon_days: int) -> np.ndarray:
    """True for each date in `obs_dates` whose label window [d, d+horizon]
    (in TRADING days, approximated here via calendar-day Timedelta since
    callers pass an already-trading-day-only DatetimeIndex — see note below)
    overlaps [boundary_start, boundary_end]. Use this to purge TRAINING rows
    whose labels would see into a TEST/VAL period.

    horizon_days counts TRADING days, but the overlap check compares against
    the boundary dates directly on obs_dates' own index — so as long as
    obs_dates is itself a trading-day-only index (as every price panel in
    this repo is), `d + horizon_days` positions correctly lands `horizon_days`
    trading days later by looking up the (position + horizon_days)'th entry,
    not by adding a calendar Timedelta. See `_label_end()`.
    """
    obs_dates = pd.DatetimeIndex(obs_dates).sort_values()
    label_end = _label_end(obs_dates, horizon_days)
    return (obs_dates <= boundary_end) & (label_end >= boundary_start)


def embargo_mask(obs_dates: pd.DatetimeIndex, boundary: pd.Timestamp,
                 embargo_days: int, direction: str = "after") -> np.ndarray:
    """True for each date within `embargo_days` TRADING days of `boundary`,
    on the given side. direction="after" embargoes dates following boundary
    (the standard case: buffer right after a test fold before training can
    resume); direction="before" embargoes dates preceding it (relevant for
    k-fold, where a train fold can sit chronologically before a test fold)."""
    obs_dates = pd.DatetimeIndex(obs_dates).sort_values()
    pos = obs_dates.searchsorted(boundary)  # position OF boundary itself (left match)
    if direction == "after":
        cutoff_pos = min(pos + embargo_days, len(obs_dates) - 1)
        cutoff = obs_dates[cutoff_pos]
        return (obs_dates > boundary) & (obs_dates <= cutoff)
    elif direction == "before":
        cutoff_pos = max(pos - embargo_days, 0)
        cutoff = obs_dates[cutoff_pos]
        return (obs_dates < boundary) & (obs_dates >= cutoff)
    raise ValueError(f"direction must be 'after' or 'before', got {direction!r}")


def _label_end(obs_dates: pd.DatetimeIndex, horizon_days: int) -> pd.DatetimeIndex:
    """The date `horizon_days` TRADING days after each date in obs_dates,
    found by position in the same trading-day index (correct for horizons
    measured in bars) rather than by adding a calendar Timedelta (which
    would be wrong across weekends/holidays)."""
    n = len(obs_dates)
    idx = np.arange(n) + horizon_days
    idx = np.clip(idx, 0, n - 1)
    return obs_dates[idx]


def train_test_val_gap(train_end: pd.Timestamp, naive_test_start: pd.Timestamp,
                       naive_val_start: pd.Timestamp, horizon_days: int,
                       trading_dates: pd.DatetimeIndex,
                       embargo_days: int = EMBARGO_DAYS) -> tuple[pd.Timestamp, pd.Timestamp]:
    """For a simple chronological train/test/val split (walk_forward_backtest.py's
    PERIODS shape — NOT k-fold), return corrected (test_start, val_start) that
    each open `horizon_days + embargo_days` TRADING days after the boundary
    they follow, guaranteeing zero label-window overlap plus the embargo
    buffer, without needing to purge individual rows (there's nothing to
    purge: the gap itself ensures no train row's label reaches into test, and
    no test row's label reaches into val).

    `trading_dates` must be the actual trading calendar for the market being
    split (e.g. the India or US panel's own Date index) — gaps are counted in
    real trading days, not calendar days, or a 252-trading-day gap would
    silently become ~365 calendar days and eat extra history for nothing.
    """
    trading_dates = pd.DatetimeIndex(trading_dates).sort_values().unique()
    gap = horizon_days + embargo_days

    def _shift(after: pd.Timestamp, naive: pd.Timestamp) -> pd.Timestamp:
        pos = trading_dates.searchsorted(after)  # position OF `after` itself
        target_pos = pos + gap
        if target_pos >= len(trading_dates):
            raise ValueError(
                f"gap of {gap} trading days from {after.date()} runs past the "
                f"end of the supplied trading calendar ({trading_dates[-1].date()}) "
                f"— not enough history after this boundary for horizon="
                f"{horizon_days}d + embargo={embargo_days}d")
        shifted = trading_dates[target_pos]
        # never move the boundary EARLIER than the caller's naive date --
        # if the naive split already had more slack than the gap requires,
        # keep it; the gap is a MINIMUM, not a fixed offset.
        return max(shifted, naive)

    test_start = _shift(train_end, naive_test_start)

    # The val-side gap must be measured from test's LAST observation, not its
    # first — otherwise a train->test gap that delays test_start would
    # incorrectly shrink the test->val gap too. Test's last observation under
    # the NAIVE schedule is always the trading day immediately before
    # naive_val_start, regardless of where test_start itself ended up, so
    # anchor there rather than on the (possibly-shifted) test_start.
    naive_val_pos = trading_dates.searchsorted(naive_val_start)
    if naive_val_pos == 0:
        raise ValueError(f"naive_val_start {naive_val_start.date()} is at or "
                         f"before the start of the trading calendar")
    test_end_naive = trading_dates[naive_val_pos - 1]
    val_start = _shift(test_end_naive, naive_val_start)

    return test_start, val_start
