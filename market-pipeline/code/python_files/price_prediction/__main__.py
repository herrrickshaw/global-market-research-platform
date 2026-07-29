"""CLI: walk-forward evaluation of Markov / Kalman / LSTM / GRU predictors.

    python -m price_prediction --market US --top 20 --test-days 500
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from .data import load_panel, top_liquid_symbols
from .evaluate import evaluate_universe

REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "python_files", "reports")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="US")
    ap.add_argument("--top", type=int, default=20, help="most-liquid symbols to test")
    ap.add_argument("--test-days", type=int, default=500)
    ap.add_argument("--refit-every", type=int, default=125)
    ap.add_argument("--symbols", nargs="*", help="explicit symbol list (overrides --top)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    panel = load_panel(args.market)
    symbols = args.symbols or top_liquid_symbols(panel, n=args.top)
    print(f"{args.market}: evaluating {len(symbols)} symbols, "
          f"{args.test_days} test days, refit every {args.refit_every}")

    results = evaluate_universe(panel, symbols, test_days=args.test_days,
                                refit_every=args.refit_every)

    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "reports",
        f"price_prediction_{args.market.lower()}.csv")
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    results.to_csv(out, index=False)

    summary = results.groupby("model")[
        ["dir_acc", "rmse", "strat_sharpe", "strat_ann_ret", "bh_sharpe"]
    ].mean().sort_values("strat_sharpe", ascending=False)
    print("\n=== mean across symbols (walk-forward, no costs) ===")
    print(summary.round(4).to_string())
    print(f"\nper-symbol rows -> {out}")


if __name__ == "__main__":
    main()
