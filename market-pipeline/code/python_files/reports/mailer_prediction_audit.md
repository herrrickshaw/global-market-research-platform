# Mailer picks × prediction strategy — audit (2026-07-27)

## A — Retro regime-gate on the live signal tracker

Scored June signals (5d/21d fixed horizons, excess vs market median), joined to the point-in-time basket trend regime:

| market   |   h |   n_all |   ungated_excess |   n_bull |   gated_excess |   n_blocked |   blocked_excess |
|:---------|----:|--------:|-----------------:|---------:|---------------:|------------:|-----------------:|
| IN       |   5 |    6855 |            -0.49 |        0 |         nan    |        6855 |            -0.49 |
| IN       |  21 |    4402 |            -0.05 |        0 |         nan    |        4402 |            -0.05 |
| US       |   5 |   11709 |             0.93 |    11709 |           0.93 |           0 |           nan    |
| US       |  21 |    1982 |             2.2  |     1982 |           2.2  |           0 |           nan    |

## B — Current watchlist through the prediction lens

446 active names scored (deep-panel markets only; panel as-of dates shown). Verdict = market gate first, then stock-level Markov state + Kalman drift.

| market   | verdict                          |   n |
|:---------|:---------------------------------|----:|
| IN       | DEMOTE (market bear)             | 216 |
| JP       | ENTER-OK                         |   3 |
| JP       | HOLD-OK                          |   7 |
| KR       | DEMOTE (market bear)             |  27 |
| US       | ENTER-OK                         | 103 |
| US       | HOLD-OK                          |  58 |
| US       | WEAK (stock bear-state, drift<0) |  32 |

### Strongest ENTER-OK names (by Kalman drift)

| market   | symbol   | status    | mkt_trend   | mkt_vol   | stock_state   |   kalman_drift_ann_pct |   markov_e21d_pct | asof       | verdict   |
|:---------|:---------|:----------|:------------|:----------|:--------------|-----------------------:|------------------:|:-----------|:----------|
| JP       | 3776.T   | justified | bull        | MID       | bull          |                   94.4 |             -0.89 | 2026-07-01 | ENTER-OK  |
| JP       | 7815.T   | playbook  | bull        | MID       | bull          |                   93.1 |             -1.25 | 2026-07-01 | ENTER-OK  |
| JP       | 8387.T   | playbook  | bull        | MID       | bull          |                   85.6 |              1.3  | 2026-07-01 | ENTER-OK  |
| US       | RTB      | signal    | bull        | MID       | bull          |                 1040.8 |            -11.83 | 2026-07-17 | ENTER-OK  |
| US       | CRNX     | signal    | bull        | MID       | bull          |                  821.3 |             -1.86 | 2026-07-17 | ENTER-OK  |
| US       | OTLK     | signal    | bull        | MID       | bull          |                  653.9 |              1.06 | 2026-07-17 | ENTER-OK  |
| US       | MNPR     | signal    | bull        | MID       | bull          |                  505   |             -1.97 | 2026-07-17 | ENTER-OK  |
| US       | WBX      | signal    | bull        | MID       | bull          |                  481   |             -9.96 | 2026-07-17 | ENTER-OK  |
| US       | ZBIO     | signal    | bull        | MID       | bull          |                  410.6 |              8.14 | 2026-07-17 | ENTER-OK  |
| US       | FORR     | signal    | bull        | MID       | bull          |                  391.1 |             -1.37 | 2026-07-17 | ENTER-OK  |
| US       | HELP     | signal    | bull        | MID       | bull          |                  390.4 |              1.78 | 2026-07-17 | ENTER-OK  |
| US       | EXFY     | signal    | bull        | MID       | bull          |                  384.2 |             -3.21 | 2026-07-17 | ENTER-OK  |
| US       | SLN      | signal    | bull        | MID       | bull          |                  384.2 |              1.59 | 2026-07-17 | ENTER-OK  |
| US       | VRNS     | signal    | bull        | MID       | bull          |                  353.5 |              3.17 | 2026-07-17 | ENTER-OK  |
| US       | ASBP     | signal    | bull        | MID       | bull          |                  301.4 |            -10.11 | 2026-07-17 | ENTER-OK  |

### WEAK names (stock-level negatives despite market gate pass)

| market   | symbol   | status   | mkt_trend   | mkt_vol   | stock_state   |   kalman_drift_ann_pct |   markov_e21d_pct | asof       | verdict                          |
|:---------|:---------|:---------|:------------|:----------|:--------------|-----------------------:|------------------:|:-----------|:---------------------------------|
| US       | JCI      | held     | bull        | MID       | bear          |                   -3.2 |              0.99 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | TXN      | held     | bull        | MID       | bear          |                  -16.7 |              2.76 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | TSM      | held     | bull        | MID       | bear          |                  -19.2 |              1.5  | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | GLNG     | held     | bull        | MID       | bear          |                  -20.8 |              4.41 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | EMR      | held     | bull        | MID       | bear          |                  -28   |              0.44 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | GOOG     | held     | bull        | MID       | bear          |                  -28.8 |              2.71 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | FDX      | held     | bull        | MID       | bear          |                  -29.2 |              0.55 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | TSLA     | held     | bull        | MID       | bear          |                  -33.6 |              0.68 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | DIS      | held     | bull        | MID       | bear          |                  -34.8 |             -0.66 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
| US       | COST     | held     | bull        | MID       | bear          |                  -51.5 |              1.38 | 2026-07-17 | WEAK (stock bear-state, drift<0) |
