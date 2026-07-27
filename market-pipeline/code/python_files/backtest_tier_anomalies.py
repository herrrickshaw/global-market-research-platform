#!/usr/bin/env python3
"""
backtest_tier_anomalies.py — replay the tier-2/3 eviction criteria over 10y history.

Question (2026-07-27): if the prediction+RSI eviction rules had run historically,
how often would evictions be VALIDATED vs come back as ANOMALIES (tier 3), and
what do the anomalies look like?

Replayed criteria (exactly the live presets):
  EVICT (WEAK) at date t:  market gate BULL (basket breadth: >50% of names
                           above their 200DMA) AND stock Markov state == bear
                           AND Kalman annualized drift < 0
  then track forward (the tier-2 rules):
    ANOMALY   first touch of +10% vs eviction close, or +5% while the stock's
              per-market RSI zone is BUY
    VALIDATED first touch of −15%, or 90 calendar days with neither → age-out
  RSI bands per market (prediction_filter.RSI_BANDS): momentum IN buys 50-75;
  mean-revert US/JP/KR buys ≤35, sells ≥70.

Models are the REAL ones (price_prediction.kalman_trend / markov_regime),
fitted once per name over its whole history; monthly evaluation dates then do
pure lookups. Universe: top-N by median turnover per market.

Output: reports/tier_anomaly_backtest.md + reports/tier_anomaly_events.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prediction_filter import RSI_BANDS, rsi_zone
from price_prediction.kalman_trend import KalmanTrendModel
from price_prediction.markov_regime import label_states

WH = Path("/Users/umashankar/repos/global-market-data/warehouse/ohlcv")
MARKETS = ["US", "JP", "KR", "IN"]
TOP_N = 200                 # most-liquid names per market
EVAL_FREQ = "ME"            # monthly evaluation dates
START = "2018-01-01"        # warm-up uses 2016-17
PROMOTE_RET, PROMOTE_RET_RSI, AGEOUT_RET, AGEOUT_DAYS = 10.0, 5.0, -15.0, 90


def load_market(mkt: str) -> pd.DataFrame:
    files = sorted((WH / mkt).glob("year=*.parquet"))
    df = pd.concat([pd.read_parquet(f, columns=["Date", "Symbol", "Close", "Volume"])
                    for f in files], ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def rsi14_series(c: pd.Series) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def analyze_market(mkt: str) -> list[dict]:
    print(f"[{mkt}] loading …", flush=True)
    df = load_market(mkt)
    turn = (df["Close"] * df["Volume"]).groupby(df["Symbol"]).median()
    syms = turn.nlargest(TOP_N).index
    px = (df[df.Symbol.isin(syms)]
          .pivot_table(index="Date", columns="Symbol", values="Close").sort_index())
    px = px.loc["2016":]
    print(f"[{mkt}] {px.shape[1]} names × {len(px)} bars", flush=True)

    # market gate: breadth — fraction of names above their 200DMA
    dma200 = px.rolling(200).mean()
    breadth = (px > dma200).mean(axis=1)
    market_bull = breadth > 0.5

    kal = KalmanTrendModel()
    eval_dates = pd.date_range(START, px.index.max(), freq=EVAL_FREQ)
    events = []

    for i, sym in enumerate(px.columns, 1):
        c = px[sym].dropna()
        if len(c) < 400:
            continue
        logp = np.log(c)
        lr = logp.diff().dropna()
        try:
            states = label_states(lr)                       # bull/side/bear labels
            slope = kal.filter(logp)["slope"] * 252 * 100   # annualized drift %
        except Exception:
            continue
        rsi = rsi14_series(c)
        # label_states: -1 warm-up, 0 bear, 1 chop, 2 bull (states.min() would
        # wrongly select the warm-up rows — that bug cut events from ~2k to 31)
        bear = states == 0

        open_until = pd.Timestamp.min
        for t in eval_dates:
            if t <= open_until or t not in c.index:
                # snap t to the last bar on/before month-end
                idx = c.index.searchsorted(t, side="right") - 1
                if idx < 0:
                    continue
                tt = c.index[idx]
            else:
                tt = t
            if tt <= open_until:
                continue
            if tt not in bear.index or tt not in slope.index:
                continue
            mb = market_bull.reindex([tt], method="ffill").iloc[0]
            if not (mb and bool(bear.loc[tt]) and float(slope.loc[tt]) < 0):
                continue
            # eviction event → forward outcome
            p0 = float(c.loc[tt])
            fwd = c.loc[tt:].iloc[1:]
            fwd = fwd[fwd.index <= tt + pd.Timedelta(days=AGEOUT_DAYS)]
            if fwd.empty:
                continue
            ret = (fwd / p0 - 1) * 100
            outcome, days, exit_ret = "ageout_validated", AGEOUT_DAYS, float(ret.iloc[-1])
            for dt, r in ret.items():
                z = rsi_zone(mkt, float(rsi.loc[dt]) if dt in rsi.index and pd.notna(rsi.loc[dt]) else None)
                if r >= PROMOTE_RET or (r >= PROMOTE_RET_RSI and z == "BUY"):
                    outcome = "ANOMALY"
                    days, exit_ret = (dt - tt).days, float(r)
                    break
                if r <= AGEOUT_RET:
                    outcome = "validated_decline"
                    days, exit_ret = (dt - tt).days, float(r)
                    break
            events.append({
                "market": mkt, "symbol": sym, "evict_date": tt.date(),
                "rsi_at_evict": round(float(rsi.loc[tt]), 1) if tt in rsi.index and pd.notna(rsi.loc[tt]) else None,
                "drift_at_evict": round(float(slope.loc[tt]), 1),
                "outcome": outcome, "days": days, "exit_ret_pct": round(exit_ret, 2),
            })
            open_until = tt + pd.Timedelta(days=days)
        if i % 50 == 0:
            print(f"[{mkt}] {i}/{px.shape[1]} names …", flush=True)
    print(f"[{mkt}] {len(events)} eviction events", flush=True)
    return events


def main():
    all_events = []
    for m in MARKETS:
        try:
            all_events += analyze_market(m)
        except Exception as e:
            print(f"[{m}] failed: {e}")
    ev = pd.DataFrame(all_events)
    ev.to_csv(HERE / "reports/tier_anomaly_events.csv", index=False)

    L = ["# Tier-2/3 eviction backtest — anomalies under the preset criteria",
         f"\nCriteria: evict on market-bull + Markov bear-state + negative Kalman drift; "
         f"anomaly at +{PROMOTE_RET}% (or +{PROMOTE_RET_RSI}% in RSI BUY band); "
         f"validated at {AGEOUT_RET}% or {AGEOUT_DAYS}d. "
         f"Top {TOP_N} liquid names/market, monthly evals {START}→.\n"]
    for mkt, g in ev.groupby("market"):
        n = len(g)
        an = (g.outcome == "ANOMALY").mean() * 100
        vd = (g.outcome == "validated_decline").mean() * 100
        ao = (g.outcome == "ageout_validated").mean() * 100
        med_exit = g[g.outcome == "ANOMALY"].exit_ret_pct.median()
        med_days = g[g.outcome == "ANOMALY"].days.median()
        rsi_an = g[g.outcome == "ANOMALY"].rsi_at_evict.median()
        rsi_ok = g[g.outcome != "ANOMALY"].rsi_at_evict.median()
        L.append(f"## {mkt} — {n} evictions")
        L.append(f"- ANOMALY {an:.1f}% (median +{med_exit:.1f}% in {med_days:.0f}d) · "
                 f"validated-decline {vd:.1f}% · age-out {ao:.1f}%")
        L.append(f"- RSI at eviction: anomalies median {rsi_an:.0f} vs validated {rsi_ok:.0f}")
        yr = g.assign(y=pd.to_datetime(g.evict_date).dt.year).groupby("y").outcome
        yl = " · ".join(f"{y}:{(o=='ANOMALY').mean()*100:.0f}%" for (y, o) in
                        ((y, gg) for y, gg in yr))
        L.append(f"- anomaly rate by year: {yl}\n")
    md = "\n".join(L)
    (HERE / "reports/tier_anomaly_backtest.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
