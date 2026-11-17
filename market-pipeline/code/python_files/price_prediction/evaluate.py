"""Walk-forward evaluation of prediction models against naive baselines.

Protocol: the final `test_days` trading days are the out-of-sample period.
Trainable models (Markov, LSTM, GRU) are refit every `refit_every` days on an
expanding window ending at the refit date; the Kalman filter is inherently
online/causal. Every prediction at day t uses data through day t only and is
scored against the realised return of day t+1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .kalman_trend import KalmanTrendModel
from .markov_regime import MarkovRegimeModel, label_states


def _metrics(pred: pd.Series, actual: pd.Series) -> dict:
    df = pd.concat({"p": pred, "a": actual}, axis=1).dropna()
    p, a = df["p"], df["a"]
    nonzero = p != 0
    hit = float((np.sign(p[nonzero]) == np.sign(a[nonzero])).mean()) if nonzero.any() else np.nan
    strat = np.sign(p) * a  # long/short next-day strategy, no costs
    ann = np.sqrt(252)
    return {
        "n": len(df),
        "dir_acc": hit,
        "rmse": float(np.sqrt(((p - a) ** 2).mean())),
        "strat_ann_ret": float(strat.mean() * 252),
        "strat_sharpe": float(strat.mean() / (strat.std() + 1e-12) * ann),
        "bh_ann_ret": float(a.mean() * 252),
        "bh_sharpe": float(a.mean() / (a.std() + 1e-12) * ann),
    }


def evaluate_symbol(df: pd.DataFrame, test_days: int = 500, refit_every: int = 125,
                    seq_models: dict | None = None) -> pd.DataFrame:
    """df: symbol frame from data.symbol_series. Returns metric rows per model."""
    from .lstm_model import SeqModel, build_features

    ret = df["log_ret"]
    if len(ret) < test_days + 750:
        raise ValueError("history too short")
    actual = ret.shift(-1)  # realised next-day return, aligned to prediction day
    test_idx = ret.index[-test_days:]
    preds: dict[str, pd.Series] = {}

    # --- baselines -------------------------------------------------------
    preds["naive_zero"] = pd.Series(1e-12, index=test_idx)          # ≈ always long
    preds["naive_yesterday"] = ret.reindex(test_idx)                # momentum-1
    preds["naive_histmean"] = pd.Series(
        [ret.loc[:t].iloc[:-1].mean() for t in test_idx], index=test_idx)

    # --- Kalman (online, causal — one pass) ------------------------------
    preds["kalman"] = KalmanTrendModel().predict_return(
        np.log(df["Close"])).reindex(test_idx)

    # --- Markov + sequence nets: expanding-window refits -----------------
    states_all = label_states(ret)
    feats_all = build_features(df)
    seq_specs = seq_models or {"lstm": {}, "gru": {}}
    markov_p, seq_p = [], {k: [] for k in seq_specs}
    starts = list(range(0, test_days, refit_every))
    for s in starts:
        block = test_idx[s:s + refit_every]
        train_end = block[0]
        tr_ret = ret.loc[:train_end].iloc[:-1]

        m = MarkovRegimeModel().fit(states_all.loc[tr_ret.index], tr_ret)
        markov_p.append(pd.Series(
            [m.predict_return(int(states_all.loc[t])) for t in block], index=block))

        tr_feats = feats_all.loc[:train_end].iloc[:-1]
        for name, kw in seq_specs.items():
            sm = SeqModel(cell=name, **kw).fit(tr_feats, ret.reindex(tr_feats.index))
            # feed enough history before the block to fill the lookback window
            ctx = feats_all.loc[:block[-1]].iloc[-(len(block) + sm.lookback):]
            seq_p[name].append(sm.predict(ctx).reindex(block))

    preds["markov"] = pd.concat(markov_p)
    for name in seq_specs:
        preds[name] = pd.concat(seq_p[name])

    rows = []
    for name, p in preds.items():
        rows.append({"model": name, **_metrics(p, actual.reindex(test_idx))})
    return pd.DataFrame(rows).set_index("model")


def evaluate_universe(panel: pd.DataFrame, symbols: list[str], **kw) -> pd.DataFrame:
    from .data import symbol_series

    out = []
    for sym in symbols:
        try:
            res = evaluate_symbol(symbol_series(panel, sym), **kw)
        except Exception as e:  # short history, bad data — skip, don't die
            print(f"  skip {sym}: {e}")
            continue
        res["symbol"] = sym
        out.append(res.reset_index())
        print(f"  done {sym}")
    return pd.concat(out, ignore_index=True)
