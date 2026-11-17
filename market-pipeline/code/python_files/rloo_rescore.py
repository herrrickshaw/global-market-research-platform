#!/usr/bin/env python3
"""
rloo_rescore.py — re-score price screens against an RLOO peer-group baseline.

WHY THIS EXISTS
───────────────
Every screen in this repo reports the raw forward return of its picks. That
number confounds three things that ought to be separated:

  1. the market-day  (everything went up that week)
  2. the factor tilt (the screen quietly selects illiquid names, and illiquid
                      names moved)
  3. actual selection skill

Raw return measures all three. Only (3) is an edge. This is the same variance
problem RL hit with the vanilla policy gradient: the raw return is a terrible
learning signal, and the fix is to subtract an action-independent baseline.

RLOO (REINFORCE Leave-One-Out) gives the exact construction. In RLOO you
sample K completions for one prompt and score each against the mean of the
OTHER K-1. Because a completion is excluded from its own baseline, the
baseline stays action-independent and the estimator stays unbiased.

Translated to a screener:

    prompt      →  one (market, date) cross-section
    completions →  every eligible name trading that day
    the pick    →  the name the screen selected
    baseline_i  →  mean forward return of the OTHER eligible names
    advantage_i →  r_i - baseline_i

A screen with no skill scores zero advantage no matter how well the market did.
That is the whole point: it is unfoolable by beta.

Peers are matched on market x date x liquidity tier. The stratification is not
cosmetic — this repo has already established that the illiquid-Piotroski edge
is about ILLIQUIDITY, not size. Comparing a pick only against names in its own
liquidity quintile is what separates "the screen picks well" from "the screen
is a liquidity proxy". Both versions are reported so the gap is visible.

DATA
────
Reads ~/.cache/market-warehouse/ohlcv_adj — the BACK-ADJUSTED panel. This is
not optional. The raw ohlcv panel stores unadjusted Close: MWL's 1:10 split on
2026-07-10 appears there as a -90% return. Scoring against raw Close would
manufacture enormous fake advantages. EU has no adjusted panel and is skipped.

ZERO LOOKAHEAD
──────────────
The Darvas box is formed on bars strictly BEFORE the signal bar (repo standing
rule). Entry is at the signal bar's close; forward returns run from that close.
Nothing in signal formation touches data at or after t.

STATISTICS
──────────
Advantages are not independent: overlapping h-day forward windows on adjacent
dates share price paths. Reporting a naive t over ~10^5 picks would be
nonsense. Instead advantages are collapsed to one mean per (market, date)
cohort, and the t-stat on that series uses Newey-West HAC errors with lag = h,
which is the standard correction for exactly this overlap.

Usage:
    .venv/bin/python3 rloo_rescore.py                  # all markets, 21d + 63d
    .venv/bin/python3 rloo_rescore.py --markets IN
    .venv/bin/python3 rloo_rescore.py --start 2020-01-01
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

WAREHOUSE = os.path.expanduser("~/.cache/market-warehouse/ohlcv_adj")
RAW_WAREHOUSE = os.path.expanduser("~/.cache/market-warehouse/ohlcv")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

# A single-day close ratio at or below this, on an UNADJUSTED panel, is a
# corporate action rather than a price move. MWL's 1:10 split prints as 0.098.
# Real one-day losses this deep exist but are vanishingly rare next to the
# thousands of splits in a 10-year, 8,000-name universe, so the guard drops
# far more fake returns than real ones — and the count is reported either way.
SPLIT_RATIO = 0.55

MARKETS = ["IN", "US", "JP", "KR"]
HORIZONS = [21, 63]
N_TIERS = 5

# Darvas — constants taken from scan_core.py, not re-chosen here
DARVAS_CONFIRM = 3        # consecutive bars a high must hold to confirm a box edge
FRESH_MAX_POS = 120.0     # Position_in_Box% ceiling for a "fresh" breakout
FRESH_MIN_BARS = 250      # history floor, per darvas_breakouts.py Tier 2
# Golden cross
FAST, SLOW = 50, 200
# Eligibility
MIN_HISTORY = SLOW + 5
LIQ_WINDOW = 60


# ─────────────────────────────────────────────────────────────────────────────
# panel loading
# ─────────────────────────────────────────────────────────────────────────────
def load_panel(market: str, start: str | None) -> tuple[pd.DataFrame, ...]:
    """Return (close, high, low, volume) as date x symbol frames, float32."""
    mdir = os.path.join(WAREHOUSE, market)
    adjusted = True
    if not _has_years(mdir):
        # ohlcv_adj holds real year partitions for INDIA ONLY; US/JP/KR contain
        # just a corrected_symbols.parquet. Fall back to the raw tree and let
        # the caller apply a split guard — see split_contaminated().
        mdir = os.path.join(RAW_WAREHOUSE, market)
        adjusted = False
    if not os.path.isdir(mdir):
        raise FileNotFoundError(f"no panel for {market} at {mdir}")
    # Must be year=*.parquet specifically. ohlcv_adj/{US,JP,KR} contain a
    # corrected_symbols.parquet and NO year partitions — a bare *.parquet glob
    # silently reads that symbol-mapping file as if it were a price panel.
    files = sorted(f for f in os.listdir(mdir)
                   if f.startswith("year=") and f.endswith(".parquet"))
    if not files:
        raise FileNotFoundError(
            f"{mdir} has no year=*.parquet partitions "
            f"(contents: {sorted(os.listdir(mdir))[:4]})")

    parts = []
    for f in files:
        d = pd.read_parquet(
            os.path.join(mdir, f),
            columns=["Date", "Symbol", "High", "Low", "Close", "Volume"])
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    if start:
        df = df[df.Date >= pd.Timestamp(start)]
    df = df.dropna(subset=["Close"])
    df = df[df.Close > 0]

    close = df.pivot_table(index="Date", columns="Symbol", values="Close",
                           aggfunc="last").astype("float32").sort_index()
    high = df.pivot_table(index="Date", columns="Symbol", values="High",
                          aggfunc="last").astype("float32").reindex_like(close)
    low = df.pivot_table(index="Date", columns="Symbol", values="Low",
                         aggfunc="last").astype("float32").reindex_like(close)
    vol = df.pivot_table(index="Date", columns="Symbol", values="Volume",
                         aggfunc="last").astype("float32").reindex_like(close)
    return close, high, low, vol, adjusted


# ─────────────────────────────────────────────────────────────────────────────
# signals — all strictly walk-forward
# ─────────────────────────────────────────────────────────────────────────────
def _pivot_high(high: pd.DataFrame, confirm: int) -> pd.DataFrame:
    """h[i] strictly greater than each of the next `confirm` highs."""
    fwd = high.iloc[::-1].rolling(confirm, min_periods=confirm).max().iloc[::-1]
    return high > fwd.shift(-1)          # max over [i+1, i+confirm]


def _pivot_low(low: pd.DataFrame, confirm: int) -> pd.DataFrame:
    fwd = low.iloc[::-1].rolling(confirm, min_periods=confirm).min().iloc[::-1]
    return low < fwd.shift(-1)


def _take(frame: pd.DataFrame, idx: pd.DataFrame) -> np.ndarray:
    """frame values gathered at the row indices in `idx` (NaN-safe)."""
    v = frame.to_numpy()
    i = idx.to_numpy()
    ok = np.isfinite(i)
    safe = np.where(ok, np.nan_to_num(i, nan=0.0), 0.0).astype(np.int64)
    out = np.take_along_axis(v, safe, axis=0)
    return np.where(ok, out, np.nan)


def darvas_box(close: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame,
               confirm: int = DARVAS_CONFIRM):
    """Port of scan_core.compute_darvas_box, evaluated at EVERY bar.

    The production function is called once per symbol on the trailing window
    and returns today's box. Re-scoring needs the same box at every historical
    bar, so the backward scan is re-expressed as a forward-fill:

      box_top(t) = high[i], i = the most recent pivot high with i <= t-1-confirm

    which is exactly what `for i in range(n-confirm-1, -1, -1): ... break` finds,
    with the current bar excluded from its own box (standing repo rule, and the
    reason the reference slices `h = highs[:-1]`).

    Returns (box_top, box_bottom, box_top_idx). box_bottom is the FIRST pivot
    low at or after box_top_idx, matching the reference's forward scan over
    `seg`; where no pivot low has formed yet the reference falls back to
    min(seg), which is applied here too.
    """
    n = len(close)
    pos = pd.DataFrame(np.repeat(np.arange(n)[:, None], close.shape[1], axis=1),
                       index=close.index, columns=close.columns, dtype="float64")

    ph = _pivot_high(high, confirm)
    ph_idx = pos.where(ph).ffill()
    # shift by 1+confirm: the pivot's confirming bars must all lie strictly
    # before t, so the newest usable pivot sits at t-1-confirm.
    bt_idx = ph_idx.shift(1 + confirm)
    box_top = _take(high, bt_idx)

    pl = _pivot_low(low, confirm)
    pl_idx = pos.where(pl).bfill()          # first pivot low at or after each k
    bb_idx = pd.DataFrame(_take(pl_idx, bt_idx), index=close.index,
                          columns=close.columns)
    # a pivot low is only usable once its own confirming bars are in the past
    bb_idx = bb_idx.where(bb_idx.to_numpy() <= (pos.to_numpy() - 1 - confirm))
    box_bottom = _take(low, bb_idx)

    return (pd.DataFrame(box_top, index=close.index, columns=close.columns),
            pd.DataFrame(box_bottom, index=close.index, columns=close.columns),
            bt_idx)


def golden_cross_state(close: pd.DataFrame):
    """(fresh cross today, 50DMA above 200DMA) — mirrors compute_golden_crossover."""
    fast = close.rolling(FAST, min_periods=FAST).mean()
    slow = close.rolling(SLOW, min_periods=SLOW).mean()
    above = fast > slow
    fresh = above & ~above.shift(1).fillna(False)
    return fresh.fillna(False), above.fillna(False)


def build_screens(close, high, low, vol):
    """The screens as the pipeline actually defines them.

    darvas_breakout  every name trading above its box — the raw BREAKOUT_BUY
                     state the scans tag. NOT a fresh-cross event: the
                     reference sets the signal from `current > box_top` alone,
                     which is why a scan tags ~1,100 India names at once.

    darvas_fresh     the distillation darvas_breakouts.py actually emails —
                     breakout AND position-in-box <= 120% AND above the 200DMA
                     AND an up day AND >= 250 bars of history. Scoring both is
                     the point: it measures whether the freshness filter earns
                     its keep over the raw state.

    golden_cross     50DMA crossing above 200DMA today.
    """
    box_top, box_bottom, _ = darvas_box(close, high, low)
    breakout = (close > box_top).fillna(False)

    rng = box_top - box_bottom
    pos_in_box = ((close - box_bottom) / rng.where(rng > 0)) * 100

    dma200 = close.rolling(SLOW, min_periods=SLOW).mean()
    up_day = close > close.shift(1)
    bars = close.notna().cumsum()
    fresh_cross, _ = golden_cross_state(close)

    fresh = (breakout
             & (pos_in_box <= FRESH_MAX_POS)
             & (close > dma200)
             & up_day
             & (bars >= FRESH_MIN_BARS)).fillna(False)

    return {"darvas_breakout": breakout,
            "darvas_fresh": fresh,
            "golden_cross": fresh_cross}


# ─────────────────────────────────────────────────────────────────────────────
# eligibility + liquidity tiers
# ─────────────────────────────────────────────────────────────────────────────
def build_eligibility(close: pd.DataFrame, vol: pd.DataFrame):
    """Eligible mask + liquidity tier (1 = most liquid) per date x symbol.

    Tiers are within-market cross-sectional quintiles of trailing median
    turnover. Deliberately NOT a currency constant: one USD floor is four
    different percentile filters across four markets, which this repo
    established the hard way.
    """
    turnover = (close * vol).rolling(LIQ_WINDOW, min_periods=30).median()
    has_hist = close.notna().cumsum() >= MIN_HISTORY
    eligible = has_hist & close.notna() & turnover.notna() & (turnover > 0)

    t = turnover.where(eligible)
    # rank -> quintile, per date
    ranks = t.rank(axis=1, pct=True, ascending=False)
    tier = np.ceil(ranks * N_TIERS).clip(1, N_TIERS)
    return eligible, tier


def forward_returns(close: pd.DataFrame, h: int) -> pd.DataFrame:
    return (close.shift(-h) / close) - 1.0


def winsorize_xs(fwd: np.ndarray, eligible: np.ndarray,
                 lo: float = 1.0, hi: float = 99.0) -> tuple[np.ndarray, int]:
    """Clip forward returns to the [lo, hi] percentile of each day's own
    cross-section.

    An RLOO baseline is a MEAN, so one bad tick moves every peer's advantage.
    The US panel's 63-day forward returns have a median of +0.39% and a maximum
    of 8,425,630 — a single cell like that dominates a 5,000-name baseline
    completely.

    Clipping to the day's own percentiles is applied identically to picks and
    to peers, so it cannot move the advantage in a chosen direction; it only
    stops individual cells from having unbounded leverage. Applied to EVERY
    market, not just the broken one, so the markets stay comparable.
    """
    out = fwd.copy()
    vals = np.where(eligible & np.isfinite(fwd), fwd, np.nan)
    with np.errstate(invalid="ignore"):
        lo_v = np.nanpercentile(vals, lo, axis=1, keepdims=True)
        hi_v = np.nanpercentile(vals, hi, axis=1, keepdims=True)
    clipped = np.clip(out, lo_v, hi_v)
    n = int(np.nansum((clipped != out) & np.isfinite(out)))
    return np.where(np.isfinite(out), clipped, out), n


def _has_years(d: str) -> bool:
    return os.path.isdir(d) and any(f.startswith("year=") and
                                    f.endswith(".parquet")
                                    for f in os.listdir(d))


def split_contaminated(close: pd.DataFrame, h: int) -> np.ndarray:
    """True where the h-day forward window contains a probable split.

    Only meaningful on an unadjusted panel. Without this, an unadjusted 1:10
    split inside the window is a -90% forward return: it would swamp the pick's
    advantage AND drag the peer baseline, in opposite directions depending on
    which side of the trade the split landed on.
    """
    ratio = close / close.shift(1)
    # SYMMETRIC. The first version of this guard only caught price DROPS, which
    # misses reverse splits entirely — and a 1:10 reverse multiplies price by
    # ten, i.e. a +900% "return". US carries thousands of them (1,179 daily
    # ratios >= 9x), and they are the reason the first US run reported a +26.6%
    # mean 63-day return against a +0.39% median.
    bad = ((ratio <= SPLIT_RATIO) | (ratio >= 1.0 / SPLIT_RATIO)).fillna(False)
    # a window starting at t covers bars t+1 .. t+h
    fwd_any = (bad.iloc[::-1].rolling(h, min_periods=1).max().iloc[::-1]
               .shift(-1).fillna(0) > 0)
    return fwd_any.to_numpy()


# ─────────────────────────────────────────────────────────────────────────────
# the RLOO estimator
# ─────────────────────────────────────────────────────────────────────────────
def rloo_advantage(fwd: np.ndarray, eligible: np.ndarray,
                   group: np.ndarray | None, n_groups: int):
    """Leave-one-out advantage for every eligible cell.

    baseline_i = (sum(peers) - r_i) / (n_peers - 1)     <- excludes i, so the
    advantage_i = r_i - baseline_i                          baseline is
                                                            action-independent
    Returns (advantage, peer_count) with NaN where the peer group is too small.
    Shapes are date x symbol.
    """
    valid = eligible & np.isfinite(fwd)
    r = np.where(valid, fwd, 0.0)

    adv = np.full(fwd.shape, np.nan, dtype="float64")
    cnt = np.zeros(fwd.shape, dtype="float64")

    if group is None:                                  # one pool per date
        s = r.sum(axis=1, keepdims=True)
        n = valid.sum(axis=1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            base = (s - r) / (n - 1)
        ok = valid & (n > 1)
        adv = np.where(ok, fwd - base, np.nan)
        cnt = np.broadcast_to(n, fwd.shape).astype("float64")
        return adv, cnt

    for g in range(1, n_groups + 1):                   # one pool per date x tier
        m = valid & (group == g)
        rg = np.where(m, r, 0.0)
        s = rg.sum(axis=1, keepdims=True)
        n = m.sum(axis=1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            base = (s - rg) / (n - 1)
        ok = m & (n > 1)
        adv = np.where(ok, fwd - base, adv)
        cnt = np.where(ok, np.broadcast_to(n, fwd.shape), cnt)
    return adv, cnt


def newey_west_t(x: np.ndarray, lag: int):
    """t-stat of mean(x) with HAC (Bartlett) errors. x is the per-date series."""
    x = x[np.isfinite(x)]
    n = x.size
    if n < 12:
        return np.nan, np.nan, n
    mu = x.mean()
    e = x - mu
    lag = int(min(lag, n - 2))
    g0 = (e @ e) / n
    var = g0
    for k in range(1, lag + 1):
        gk = (e[k:] @ e[:-k]) / n
        var += 2.0 * (1.0 - k / (lag + 1.0)) * gk
    if var <= 0:
        return np.nan, np.nan, n
    se = np.sqrt(var / n)
    return mu, mu / se, n


# ─────────────────────────────────────────────────────────────────────────────
# driver
# ─────────────────────────────────────────────────────────────────────────────
def score_market(market: str, start: str | None, rows: list, diag: list):
    close, high, low, vol, adjusted = load_panel(market, start)
    eligible, tier = build_eligibility(close, vol)

    dates = close.index
    el = eligible.to_numpy()
    ti = np.nan_to_num(tier.to_numpy(), nan=0.0)

    diag.append(dict(market=market, symbols=close.shape[1], dates=len(dates),
                     span=f"{dates.min().date()} → {dates.max().date()}",
                     eligible_cells=int(el.sum()),
                     panel="adjusted" if adjusted else "RAW + split guard"))

    sig_cache = {name: s.to_numpy()
                 for name, s in build_screens(close, high, low, vol).items()}

    for h in HORIZONS:
        fwd = forward_returns(close, h).to_numpy()
        if not adjusted:
            fwd = np.where(split_contaminated(close, h), np.nan, fwd)
        fwd, n_wins = winsorize_xs(fwd, el)
        # a signal is only scoreable if the full forward window exists
        has_fwd = np.isfinite(fwd)

        adv_all, _ = rloo_advantage(fwd, el, None, 0)
        adv_tier, cnt_tier = rloo_advantage(fwd, el, ti, N_TIERS)

        for name, sig in sig_cache.items():
            pick = sig & el & has_fwd
            if pick.sum() == 0:
                continue

            raw = np.where(pick, fwd, np.nan)
            aa = np.where(pick, adv_all, np.nan)
            at = np.where(pick, adv_tier, np.nan)

            # collapse to one cohort mean per date, then HAC across dates
            with np.errstate(invalid="ignore"):
                raw_d = np.nanmean(np.where(pick, raw, np.nan), axis=1)
                aa_d = np.nanmean(aa, axis=1)
                at_d = np.nanmean(at, axis=1)

            mu_raw, t_raw, nd = newey_west_t(raw_d, h)
            mu_aa, t_aa, _ = newey_west_t(aa_d, h)
            mu_at, t_at, _ = newey_west_t(at_d, h)

            # what liquidity tier does this screen actually live in?
            picked_tier = np.where(pick, ti, np.nan)
            med_tier = np.nanmedian(picked_tier)

            rows.append(dict(
                market=market, screen=name, horizon=h,
                n_picks=int(pick.sum()), n_dates=int(nd),
                median_tier=float(med_tier),
                raw_ret=mu_raw, raw_t=t_raw,
                adv_mkt=mu_aa, adv_mkt_t=t_aa,
                adv_tier=mu_at, adv_tier_t=t_at,
            ))
        del fwd, adv_all, adv_tier
    del close, high, low, vol, eligible, tier


def fmt(v, pct=True, nd=2):
    if v is None or not np.isfinite(v):
        return "  n/a"
    return f"{v*100:+.{nd}f}%" if pct else f"{v:+.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", nargs="*", default=MARKETS)
    ap.add_argument("--start", default=None,
                    help="ISO date; default = full panel history")
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "rloo_rescore.md"))
    args = ap.parse_args()

    rows, diag = [], []
    for m in args.markets:
        print(f"[{m}] loading adjusted panel …", flush=True)
        try:
            score_market(m, args.start, rows, diag)
        except FileNotFoundError as e:
            print(f"  ! skipped: {e}", flush=True)
            continue
        print(f"  done ({len([r for r in rows if r['market']==m])} rows)",
              flush=True)

    if not rows:
        sys.exit("no results — every market failed to load")

    res = pd.DataFrame(rows).sort_values(["screen", "horizon", "market"])
    os.makedirs(OUT_DIR, exist_ok=True)
    res.to_csv(args.out.replace(".md", ".csv"), index=False)

    # ── report ──────────────────────────────────────────────────────────────
    L = []
    L.append(f"# RLOO peer-group re-score — {datetime.now():%Y-%m-%d %H:%M}")
    L.append("")
    L.append("Every screen scored three ways on the same picks:")
    L.append("")
    L.append("| column | meaning |")
    L.append("|---|---|")
    L.append("| `raw` | forward return of the picks. Confounds market, factor tilt and skill. |")
    L.append("| `adv_mkt` | RLOO advantage vs **all** eligible names that market-day. Removes the market. |")
    L.append("| `adv_tier` | RLOO advantage vs eligible names **in the same liquidity quintile**. Removes the market *and* the liquidity tilt. This is the selection-skill number. |")
    L.append("")
    L.append("t-stats are Newey-West HAC on the per-date cohort series "
             "(lag = horizon), not on individual picks — overlapping forward "
             "windows make a naive per-pick t meaningless.")
    L.append("")
    L.append("Source panel: `~/.cache/market-warehouse/ohlcv_adj` "
             "(split/bonus back-adjusted). Darvas boxes exclude the signal bar.")
    L.append("")

    for h in sorted(res.horizon.unique()):
        L.append(f"## Horizon: {h} trading days")
        L.append("")
        L.append("| screen | mkt | picks | dates | med tier | raw | adv vs mkt | t | adv vs tier | t |")
        L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        sub = res[res.horizon == h]
        for _, r in sub.iterrows():
            L.append(
                f"| `{r.screen}` | {r.market} | {r.n_picks:,} | {r.n_dates:,} "
                f"| {r.median_tier:.0f} | {fmt(r.raw_ret)} "
                f"| {fmt(r.adv_mkt)} | {fmt(r.adv_mkt_t, pct=False)} "
                f"| {fmt(r.adv_tier)} | {fmt(r.adv_tier_t, pct=False)} |")
        L.append("")

    L.append("## Panel diagnostics")
    L.append("")
    L.append("| market | panel | symbols | dates | span | eligible cells |")
    L.append("|---|---|---:|---:|---|---:|")
    for d in diag:
        L.append(f"| {d['market']} | {d['panel']} | {d['symbols']:,} | {d['dates']:,} "
                 f"| {d['span']} | {d['eligible_cells']:,} |")
    L.append("")
    L.append("## Reading this")
    L.append("")
    L.append("A screen whose `raw` is strongly positive but whose `adv_tier` is "
             "flat did not pick well — it was carried by the market, or it is a "
             "liquidity proxy. The gap between `adv_mkt` and `adv_tier` is "
             "exactly the size of the factor tilt.")
    L.append("")
    L.append("`|t| >= 2` on `adv_tier` is the bar for a claim of selection skill, "
             "and even that is a single-hypothesis bar — this table tests "
             f"{len(res)} combinations, so a Bonferroni-adjusted threshold is "
             f"nearer |t| >= {abs(round(2.8,1))}.")

    with open(args.out, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"\nwrote {args.out}")
    print(f"wrote {args.out.replace('.md', '.csv')}")

    # console summary
    print()
    print(res[["market", "screen", "horizon", "n_picks", "median_tier",
               "raw_ret", "adv_mkt", "adv_mkt_t", "adv_tier", "adv_tier_t"]]
          .to_string(index=False,
                     float_format=lambda v: f"{v:,.4f}"))


if __name__ == "__main__":
    main()
