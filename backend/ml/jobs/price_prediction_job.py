"""Adapter: price_prediction_backtest (Markov/Kalman/LSTM regime models)."""
from __future__ import annotations

import os
import sys

from backend.ml import registry

REPO_PATH = os.environ.get(
    "PRICE_PRED_REPO_PATH", os.path.expanduser("~/price_prediction_backtest")
)


def run(params: dict) -> dict:
    market = params["market"]
    top = int(params.get("top", 20))
    test_days = int(params.get("test_days", 500))
    refit_every = int(params.get("refit_every", 125))

    if REPO_PATH not in sys.path:
        sys.path.insert(0, REPO_PATH)
    from price_prediction.data import load_panel, top_liquid_symbols
    from price_prediction.evaluate import evaluate_universe

    panel = load_panel(market)
    symbols = params.get("symbols") or top_liquid_symbols(panel, n=top)
    results = evaluate_universe(panel, symbols, test_days=test_days, refit_every=refit_every)

    summary = (
        results.groupby("model")[["dir_acc", "rmse", "strat_sharpe", "strat_ann_ret"]]
        .mean()
        .round(4)
    )
    metrics = {
        f"{model}_{col}": float(val)
        for model, row in summary.iterrows()
        for col, val in row.items()
    }

    try:
        with registry.start_run(experiment="price_prediction", run_name=market):
            registry.log_params(
                {"market": market, "top": top, "test_days": test_days, "refit_every": refit_every}
            )
            registry.log_metrics(metrics)
    except Exception:
        pass  # tracking is best-effort; the evaluation result still returns below

    return {"market": market, "symbols": len(symbols), "summary": summary.to_dict()}
