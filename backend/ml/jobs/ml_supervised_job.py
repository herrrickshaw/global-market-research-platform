"""Adapter: repos/global-stock-screener/ml_supervised.py train()."""
from __future__ import annotations

import os
import sys

REPO_PATH = os.environ.get(
    "GSS_REPO_PATH", os.path.expanduser("~/repos/global-stock-screener")
)


def run(params: dict) -> dict:
    market = params["market"]
    horizon = int(params.get("horizon", 252))

    if REPO_PATH not in sys.path:
        sys.path.insert(0, REPO_PATH)
    import ml_supervised

    return ml_supervised.train(market=market, horizon=horizon, verbose=False)
