# mom126 zone-rule fix — simulated BUY-basket performance

Long-only, equal-weight, weekly-rebalanced BUY-tercile basket, held 10 trading days, compounded over non-overlapping periods (matching backtest_zone_rules.py's de-overlap technique). OLD = the live bug (mom126 ranked by 5-day return). NEW = the fix (ranked by real 126-day/~6mo return). Educational/research only. NOT investment advice.

| market   | version                  |   n_periods |   total_return_pct |   cagr_pct |   win_rate_pct |   sharpe |
|:---------|:-------------------------|------------:|-------------------:|-----------:|---------------:|---------:|
| US       | OLD (buggy, d5-ranked)   |         225 |              -51.8 |       -8.2 |           48.4 |    -0.35 |
| US       | NEW (fixed, d126-ranked) |         225 |                3.1 |        0.4 |           56.9 |     0.11 |
| US       | Benchmark (^GSPC)        |         225 |              179.8 |       12.7 |           64   |     0.79 |
| JP       | OLD (buggy, d5-ranked)   |         224 |               45.8 |        4.5 |           58.9 |     0.36 |
| JP       | NEW (fixed, d126-ranked) |         225 |               87.4 |        7.6 |           62.2 |     0.51 |
| JP       | Benchmark (^N225)        |         224 |              191   |       13.3 |           58.9 |     0.7  |
| EU       | OLD (buggy, d5-ranked)   |         225 |               36.5 |        3.7 |           59.6 |     0.31 |
| EU       | NEW (fixed, d126-ranked) |         225 |              122.1 |        9.7 |           63.1 |     0.71 |
| EU       | Benchmark (^STOXX50E)    |         225 |               79.1 |        7   |           58.7 |     0.45 |