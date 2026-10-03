"""Adapter: market-pipeline/code/python_files/ml_signal_engine.py MLSignalEngine."""
from __future__ import annotations

import os
import sys

import numpy as np

from backend.ml import registry

REPO_PATH = os.environ.get(
    "ML_SIGNAL_ENGINE_REPO_PATH",
    os.path.expanduser("~/market-pipeline/code/python_files"),
)


def run(params: dict) -> dict:
    market = params["market"]
    symbols: list[str] = params["symbols"]  # {symbol: ohlc_parquet_path} not assumed — caller supplies frames
    model_type = params.get("model_type", "ridge")

    if REPO_PATH not in sys.path:
        sys.path.insert(0, REPO_PATH)
    import pandas as pd

    from ml_signal_engine import MLSignalEngine

    engine = MLSignalEngine(model_type=model_type)
    rows = []
    for symbol, ohlc_path in symbols.items():
        df_ohlc = pd.read_parquet(ohlc_path)
        rows.append(engine.predict(symbol, df_ohlc))

    valid = [r for r in rows if r.get("train_rmse") is not None]
    metrics = {
        "mean_train_rmse": float(np.mean([r["train_rmse"] for r in valid])) if valid else 0.0,
        "symbols_evaluated": len(rows),
        "symbols_with_signal": len(valid),
    }

    try:
        with registry.start_run(experiment="ml_signal_engine", run_name=market):
            registry.log_params({"market": market, "model_type": model_type})
            registry.log_metrics(metrics)
    except Exception:
        pass

    return {"market": market, "signals": rows, "metrics": metrics}
