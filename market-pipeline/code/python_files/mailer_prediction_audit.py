#!/usr/bin/env python3
"""mailer_prediction_audit.py — run the prediction strategy over the live
mailer output: retro-gate the scored signal tracker, and score the current
watchlist through the Markov-regime + Kalman-trend lens.

Part A (retro): join each scored signal in reports/signal_outcomes.parquet to
its market's point-in-time trend regime (trimmed top-20 basket, EMA100 —
same construction as market_regime.py) and compare realized excess returns
gated (bull-only entries) vs ungated.

Part B (now): for active watchlist rows (watch/signal/playbook/held) in
markets with deep panels, compute per-stock Kalman slope (annualized drift),
Markov regime state + expected 21d return, current market trend/vol regime,
and a verdict: ENTER-OK (bull mkt, stock bull-state, slope>0), HOLD-OK,
DEMOTE (market gate), or WEAK (stock-level signals negative).

Outputs: reports/mailer_prediction_audit.md + reports/watchlist_prediction_scores.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path.home() / "price_prediction_backtest"))

from price_prediction.kalman_trend import KalmanTrendModel          # noqa: E402
from price_prediction.markov_regime import MarkovRegimeModel, label_states  # noqa: E402
from market_regime import BASKETS, _ALIAS                            # noqa: E402

# ── panel source ─────────────────────────────────────────────────────────────
# 2026-08-24: this used to read the monolithic panels at
# global-stock-screener/cache_seed/ltm/<MKT>.parquet. Those files DO NOT EXIST
# for any market this module needs. GSS and GMD were deleted and recreated
# LFS-free on 2026-08-04; the 15 small country panels survived, and the five
# large ones — exactly IN/US/JP/KR/CN — were the LFS objects that did not.
# Every run since then failed on IN and aborted the whole loop, so part_b has
# been dead for ALL five markets, not just India.
#
# The monoliths were superseded on 2026-07-22 anyway (see the README still
# sitting in that directory): the canonical store is the year-partitioned
# warehouse, which the daily pipeline refreshes every morning.
#
# Prefer ohlcv_adj over ohlcv. The adjusted tree is back-adjusted for splits
# and bonuses; the raw tree is not. On the raw tree MWL's 1:10 split shows up
# as a -90% single-day return, which would poison both the Kalman slope and the
# Markov state labelling. The |log return| < 0.5 filter downstream was a crude
# guard against exactly this; reading the adjusted tree makes it real.
WAREHOUSE = Path.home() / ".cache/market-warehouse"
LTM = Path.home() / "repos/global-stock-screener/cache_seed/ltm"  # legacy fallback
PANEL_MKT = {"IN": "IN", "US": "US", "JP": "JP", "KR": "KR", "CN": "CN"}

# Both callers only ever pivot Close, so don't pay to read OHLCV.
_PANEL_COLS = ["Date", "Symbol", "Close"]


def _panel(mkt: str, since_year: int | None = None) -> pd.DataFrame:
    """Long panel (Date, Symbol, Close) for one market.

    Resolution order: adjusted warehouse → raw warehouse → legacy monolith.
    Raises FileNotFoundError naming every path tried, so a future breakage of
    this kind is diagnosable from the log line instead of a bare errno 2.

    since_year bounds the read to year partitions >= that year. Default None
    keeps the whole history, which is what the backtest-shaped callers here
    want. A caller that only needs a trailing window should say so: US alone is
    16.4M rows / 1.3 GB across 11 partitions, and a 252-bar rolling high does
    not need 2015. The legacy monolith is not partitioned, so the bound cannot
    apply there — it is filtered by Date instead.
    """
    tried = []
    for tree, adjusted in (("ohlcv_adj", True), ("ohlcv", False)):
        mdir = WAREHOUSE / tree / mkt
        tried.append(str(mdir))
        files = sorted(mdir.glob("year=*.parquet")) if mdir.is_dir() else []
        if since_year is not None:
            files = [f for f in files
                     if f.stem.partition("=")[2].isdigit()
                     and int(f.stem.partition("=")[2]) >= since_year]
        if not files:
            continue
        df = pd.concat(
            [pd.read_parquet(f, columns=_PANEL_COLS) for f in files],
            ignore_index=True)
        if not adjusted:
            print(f"    [{mkt}] WARNING: no adjusted panel — using raw Close. "
                  f"Splits are NOT adjusted in this market.")
        df["Date"] = pd.to_datetime(df["Date"])
        return df.dropna(subset=["Close"])

    legacy = LTM / f"{mkt}.parquet"
    tried.append(str(legacy))
    if legacy.exists():
        df = pd.read_parquet(legacy)
        df["Date"] = pd.to_datetime(df["Date"])
        if since_year is not None:
            df = df[df["Date"].dt.year >= since_year]
        return df

    raise FileNotFoundError(
        f"no price panel for {mkt}; tried " + ", ".join(tried))


def _basket_symbols(mkt: str, cols) -> list[str]:
    """Map market_regime baskets to panel symbol conventions (IN bare, KR .KS)."""
    want = BASKETS[_ALIAS.get(mkt.lower(), mkt.lower())]
    out = []
    for t in want:
        for cand in (t, t.replace(".NS", "")):
            if cand in cols:
                out.append(cand)
                break
    return out


def trend_series(mkt: str, close: pd.DataFrame) -> pd.Series:
    basket = _basket_symbols(mkt, close.columns)
    ret = close[basket].pct_change()
    ret = ret.mask(ret.abs() > 0.6)
    n = ret.notna().sum(axis=1)
    trimmed = (ret.sum(axis=1) - ret.max(axis=1) - ret.min(axis=1)) / (n - 2)
    idx = (1 + trimmed.where(n > 4).dropna()).cumprod()
    ema = idx.ewm(span=100, min_periods=100).mean()
    slope = ema.diff(5)
    t = pd.Series("chop", index=idx.index)
    t[(idx > ema) & (slope > 0)] = "bull"
    t[(idx < ema) & (slope < 0)] = "bear"
    t[ema.isna()] = "warmup"
    return t


def part_a() -> str:
    so = pd.read_parquet(HERE / "reports/signal_outcomes.parquet")
    so = so[(so.status == "scored") & so.market.isin(["IN", "US"])].copy()
    so["signal_date"] = pd.to_datetime(so.signal_date)
    lines = ["## A — Retro regime-gate on the live signal tracker",
             "", "Scored June signals (5d/21d fixed horizons, excess vs market "
             "median), joined to the point-in-time basket trend regime:", ""]
    rows = []
    for mkt in ["IN", "US"]:
        try:
            p = _panel(mkt)
        except FileNotFoundError as e:
            print(f"    [{mkt}] skipped — {e}")
            continue
        close = p.pivot_table(index="Date", columns="Symbol", values="Close",
                              aggfunc="last").sort_index()
        tr = trend_series(mkt, close)
        sub = so[so.market == mkt].copy()
        sub["trend"] = tr.reindex(sub.signal_date.values).values
        for h in [5.0, 21.0]:
            hh = sub[(sub.h == h)].dropna(subset=["excess_ret"])
            if hh.empty:
                continue
            all_ex = hh.excess_ret.mean() * 100
            gated = hh[hh.trend == "bull"]
            blocked = hh[hh.trend != "bull"]
            rows.append(dict(market=mkt, h=int(h), n_all=len(hh),
                             ungated_excess=round(all_ex, 2),
                             n_bull=len(gated),
                             gated_excess=round(gated.excess_ret.mean() * 100, 2) if len(gated) else np.nan,
                             n_blocked=len(blocked),
                             blocked_excess=round(blocked.excess_ret.mean() * 100, 2) if len(blocked) else np.nan))
    t = pd.DataFrame(rows)
    lines.append(t.to_markdown(index=False))
    return "\n".join(lines), t


def part_b() -> tuple[str, pd.DataFrame]:
    wl = pd.read_csv(HERE / "watchlist.csv")
    active = wl[wl.status.isin(["watch", "signal", "playbook", "held",
                                "value-hold", "justified"])].copy()
    from market_regime import get_regime
    out = []
    for mkt in ["IN", "US", "JP", "KR", "CN"]:
        names = active[active.market == mkt]
        if names.empty:
            continue
        reg = get_regime(mkt)
        # One unavailable market must not abort the other four. Before
        # 2026-08-24 it did: IN is first in this list, its panel was missing,
        # and the raised errno 2 took US/JP/KR/CN down with it.
        try:
            p = _panel(PANEL_MKT[mkt])
        except FileNotFoundError as e:
            print(f"    [{mkt}] skipped — {e}")
            continue
        close = p.pivot_table(index="Date", columns="Symbol", values="Close",
                              aggfunc="last").sort_index()
        for _, r in names.iterrows():
            sym = str(r.symbol)
            if sym not in close.columns:
                continue
            s = close[sym].dropna()
            if len(s) < 300:
                continue
            lr = np.log(s).diff().dropna()
            lr = lr[lr.abs() < 0.5]
            # Kalman slope -> annualized drift %
            kal = KalmanTrendModel().filter(np.log(s.loc[lr.index]))
            drift = float(kal["slope"].iloc[-1]) * 252 * 100
            # Markov: state today + expected 21d return
            states = label_states(lr)
            m = MarkovRegimeModel().fit(states, lr)
            st = int(states.iloc[-1])
            e21 = m.predict_return(st) * 21 * 100
            st_name = {0: "bear", 1: "chop", 2: "bull"}.get(st, "warmup")
            if reg["trend"] == "bear":
                verdict = "DEMOTE (market bear)"
            elif reg["trend"] == "chop" and reg.get("vol") == "HIGH":
                verdict = "DEMOTE (chop+HIGH vol)"
            elif st_name == "bull" and drift > 0:
                verdict = "ENTER-OK"
            elif drift > 0 or st_name != "bear":
                verdict = "HOLD-OK"
            else:
                verdict = "WEAK (stock bear-state, drift<0)"
            out.append(dict(market=mkt, symbol=sym, status=r.status,
                            mkt_trend=reg["trend"], mkt_vol=reg.get("vol"),
                            stock_state=st_name,
                            kalman_drift_ann_pct=round(drift, 1),
                            markov_e21d_pct=round(e21, 2),
                            asof=str(s.index[-1].date()), verdict=verdict))
    df = pd.DataFrame(out).sort_values(["market", "verdict", "kalman_drift_ann_pct"],
                                       ascending=[True, True, False])
    lines = ["", "## B — Current watchlist through the prediction lens", "",
             f"{len(df)} active names scored (deep-panel markets only; panel "
             f"as-of dates shown). Verdict = market gate first, then stock-level "
             "Markov state + Kalman drift.", "",
             df.groupby(["market", "verdict"]).size().rename("n").reset_index()
               .to_markdown(index=False), "",
             "### Strongest ENTER-OK names (by Kalman drift)", "",
             df[df.verdict == "ENTER-OK"].head(15).to_markdown(index=False), "",
             "### WEAK names (stock-level negatives despite market gate pass)", "",
             df[df.verdict.str.startswith("WEAK")].head(10).to_markdown(index=False)]
    return "\n".join(lines), df


def purge_weak(scores: pd.DataFrame) -> None:
    """Move WEAK-verdict names to watchlist_purged.csv — through the
    held-status guard: protected rows (held/value-hold/sold) are flagged in
    their note instead of being removed."""
    from watchlist_digest import guard_droppable, PROTECTED_STATUSES

    wl = pd.read_csv(HERE / "watchlist.csv")
    weak_keys = set(zip(scores[scores.verdict.str.startswith("WEAK")].symbol,
                        scores[scores.verdict.str.startswith("WEAK")].market))
    idx = [i for i, r in wl.iterrows() if (r.symbol, r.market) in weak_keys]
    droppable, protected = guard_droppable(wl, idx)
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    reason = "prediction audit: stock bear-state + negative Kalman drift"
    for i in protected:
        note = str(wl.at[i, "note"])
        tag = f"weak {today} ({reason}) — protected status, not purged"
        if f"weak {today}" not in note:
            wl.at[i, "note"] = (note + " | " if note not in ("nan", "") else "") + tag
    if droppable:
        arch = wl.loc[droppable].copy()
        arch["status"] = "purged"
        arch["purged_date"] = today
        arch["reason"] = reason
        arch.to_csv(HERE / "watchlist_purged.csv", mode="a", index=False, header=False)
        wl = wl.drop(index=droppable).reset_index(drop=True)
    wl.to_csv(HERE / "watchlist.csv", index=False)
    print(f"purged {len(droppable)}; protected (flagged only): {len(protected)} "
          f"[{', '.join(sorted(PROTECTED_STATUSES))}]")


def main():
    a_text, a_df = part_a()
    b_text, b_df = part_b()
    if "--purge-weak" in sys.argv:
        purge_weak(b_df)
    md = ("# Mailer picks × prediction strategy — audit "
          f"({pd.Timestamp.today().date()})\n\n" + a_text + "\n" + b_text + "\n")
    (HERE / "reports/mailer_prediction_audit.md").write_text(md)
    b_df.to_csv(HERE / "reports/watchlist_prediction_scores.csv", index=False)
    print(md[:3000])
    print("\nwrote reports/mailer_prediction_audit.md and "
          "reports/watchlist_prediction_scores.csv")


if __name__ == "__main__":
    main()
