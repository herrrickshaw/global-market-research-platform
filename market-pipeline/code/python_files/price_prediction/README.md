# price_prediction — sequential models for next-day return forecasting

Three model families, evaluated identically and honestly against naive
baselines. Every prediction at day *t* uses information through day *t* only
and is scored on the realised return of day *t+1*.

## Models

| Model | File | Idea |
|---|---|---|
| Markov regime chain | `markov_regime.py` | 3 regimes (bear/chop/bull) from rolling trend vs. vol; first-order transition matrix; E[next ret] = T[state] · E[ret\|state] |
| Kalman trend filter | `kalman_trend.py` | Local-linear-trend state space on log price; filtered slope = expected next-day log return; fully online/causal |
| LSTM / GRU | `lstm_model.py` | 42-day windows of (return, vol, range, volume-z, momentum) → next-day return; scaling fit on train only |

## Baselines (any model must beat these to matter)

- `naive_zero` — predict ~0 (equivalent to always-long / buy & hold)
- `naive_yesterday` — 1-day momentum (yesterday's return as forecast)
- `naive_histmean` — expanding historical mean return

## Protocol

- Data: `~/repos/global-stock-screener/cache_seed/ltm/<MARKET>.parquet`
  (10y OHLCV; override dir via `LTM_DIR`). Universe = top-N median dollar
  volume with ≥8y history (skips truncated symbols like AAPL in the US panel).
- Walk-forward: last `--test-days` are out-of-sample; Markov/LSTM/GRU refit
  every `--refit-every` days on an expanding window; Kalman needs no refits.
- Metrics: directional accuracy, RMSE, and the annualised Sharpe of a
  frictionless sign(long/short) strategy vs. buy & hold.

## Run

```bash
~/.venvs/testing/bin/python -m price_prediction --market US --top 20 --test-days 500
~/.venvs/testing/bin/python -m price_prediction --market IN --symbols RELIANCE TCS
```

Per-symbol results land in `reports/price_prediction_<market>.csv`.

## Caveats

- No transaction costs, slippage, or borrow in `strat_sharpe`; a daily
  sign-flipping strategy trades constantly, so real-world costs would eat
  most or all of any small edge shown here.
- Daily close-to-close returns are close to unpredictable; expect directional
  accuracy near 0.5. The point of the harness is to *measure* that fairly,
  not to assume any of these models works.
- India panel: prefer adjusted series (raw-Close split risk — see repo memory).
