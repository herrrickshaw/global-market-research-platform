# mom126 zone-rule fix — simulated BUY-basket performance

Long-only, equal-weight, weekly-rebalanced BUY-tercile basket, held 10 trading days, compounded over non-overlapping periods (matching backtest_zone_rules.py's de-overlap technique). OLD = the live bug (mom126 ranked by 5-day return). NEW = the fix (ranked by real 126-day/~6mo return). Educational/research only. NOT investment advice.

| market   | live_status                                | version                  |   n_periods |   total_return_pct |   cagr_pct |   win_rate_pct |   sharpe |
|:---------|:-------------------------------------------|:-------------------------|------------:|-------------------:|-----------:|---------------:|---------:|
| US       | LIVE on mom126                             | OLD (buggy, d5-ranked)   |         225 |              -51.8 |       -8.2 |           48.4 |    -0.35 |
| US       | LIVE on mom126                             | NEW (fixed, d126-ranked) |         225 |                3.1 |        0.4 |           56.9 |     0.11 |
| US       | LIVE on mom126                             | Benchmark (^GSPC)        |         225 |              179.8 |       12.7 |           64   |     0.79 |
| JP       | LIVE on mom126                             | OLD (buggy, d5-ranked)   |         224 |               45.8 |        4.5 |           58.9 |     0.36 |
| JP       | LIVE on mom126                             | NEW (fixed, d126-ranked) |         225 |               87.4 |        7.6 |           62.2 |     0.51 |
| JP       | LIVE on mom126                             | Benchmark (^N225)        |         224 |              191   |       13.3 |           58.9 |     0.7  |
| EU       | LIVE on mom126                             | OLD (buggy, d5-ranked)   |         225 |               36.5 |        3.7 |           59.6 |     0.31 |
| EU       | LIVE on mom126                             | NEW (fixed, d126-ranked) |         225 |              122.1 |        9.7 |           63.1 |     0.71 |
| EU       | LIVE on mom126                             | Benchmark (^STOXX50E)    |         225 |               79.1 |        7   |           58.7 |     0.45 |
| KR       | NOT live (currently uses a different rule) | OLD (buggy, d5-ranked)   |         225 |              -28.2 |       -3.8 |           52.4 |    -0.09 |
| KR       | NOT live (currently uses a different rule) | NEW (fixed, d126-ranked) |         225 |              -30.2 |       -4.1 |           53.8 |    -0.1  |
| KR       | NOT live (currently uses a different rule) | Benchmark (^KS11)        |         225 |              176.8 |       12.6 |           52.4 |     0.64 |
| IN       | NOT live (currently uses a different rule) | OLD (buggy, d5-ranked)   |         225 |              105.5 |        8.7 |           53.8 |     0.48 |
| IN       | NOT live (currently uses a different rule) | NEW (fixed, d126-ranked) |         225 |              223.8 |       14.7 |           57.8 |     0.73 |
| IN       | NOT live (currently uses a different rule) | Benchmark (^NSEI)        |         225 |              129.7 |       10.2 |           57.8 |     0.68 |