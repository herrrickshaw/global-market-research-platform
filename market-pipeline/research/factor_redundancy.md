# Factor Redundancy — spectral measurement
Executes BACKTEST_QUEUE.md #1/#9. Motivated by 2602.00196 (decorrelated signals combine well) and 2607.19005/2608.09641 (Halperin spectral method + m- participation ratio companion).

## IN
n_obs=263,359. **Participation ratio: 4.92 of 10** (effective independent factors). Effective rank (entropy-based): 6.53. Absorption ratio (top 3 PCs): 69.4%.

| pair | r |
|---|---:|
| golden_cross × breakout | +0.664 |
| trend × breakout | +0.590 |
| mom126 × mom252 | +0.581 |
| lowvol × def_revert | +0.561 |
| lowvol × qual_mom | +0.549 |
| revert × def_revert | +0.546 |
| trend × mom_st | +0.543 |
| mom126 × qual_mom | +0.537 |

<details><summary>full correlation matrix</summary>

|              |   trend |   revert |   mom126 |   mom_st |   golden_cross |   breakout |   lowvol |   mom252 |   qual_mom |   def_revert |
|:-------------|--------:|---------:|---------:|---------:|---------------:|-----------:|---------:|---------:|-----------:|-------------:|
| trend        |   1     |   -0.35  |    0.381 |    0.543 |          0.352 |      0.59  |    0.002 |    0.252 |      0.219 |       -0.189 |
| revert       |  -0.35  |    1     |   -0.142 |   -0.381 |         -0.041 |     -0.204 |   -0.03  |   -0.102 |     -0.097 |        0.546 |
| mom126       |   0.381 |   -0.142 |    1     |    0.294 |          0.522 |      0.507 |   -0.074 |    0.581 |      0.537 |       -0.115 |
| mom_st       |   0.543 |   -0.381 |    0.294 |    1     |          0.134 |      0.333 |   -0.016 |    0.207 |      0.16  |       -0.221 |
| golden_cross |   0.352 |   -0.041 |    0.522 |    0.134 |          1     |      0.664 |   -0.014 |    0.506 |      0.29  |       -0.031 |
| breakout     |   0.59  |   -0.204 |    0.507 |    0.333 |          0.664 |      1     |    0.142 |    0.46  |      0.362 |       -0.033 |
| lowvol       |   0.002 |   -0.03  |   -0.074 |   -0.016 |         -0.014 |      0.142 |    1     |   -0.043 |      0.549 |        0.561 |
| mom252       |   0.252 |   -0.102 |    0.581 |    0.207 |          0.506 |      0.46  |   -0.043 |    1     |      0.329 |       -0.08  |
| qual_mom     |   0.219 |   -0.097 |    0.537 |    0.16  |          0.29  |      0.362 |    0.549 |    0.329 |      1     |        0.241 |
| def_revert   |  -0.189 |    0.546 |   -0.115 |   -0.221 |         -0.031 |     -0.033 |    0.561 |   -0.08  |      0.241 |        1     |

</details>

## US
n_obs=261,488. **Participation ratio: 4.53 of 10** (effective independent factors). Effective rank (entropy-based): 6.22. Absorption ratio (top 3 PCs): 71.6%.

| pair | r |
|---|---:|
| golden_cross × breakout | +0.651 |
| trend × mom_st | +0.648 |
| mom126 × golden_cross | +0.610 |
| lowvol × qual_mom | +0.605 |
| trend × breakout | +0.595 |
| mom126 × mom252 | +0.593 |
| golden_cross × mom252 | +0.582 |
| mom126 × qual_mom | +0.570 |

<details><summary>full correlation matrix</summary>

|              |   trend |   revert |   mom126 |   mom_st |   golden_cross |   breakout |   lowvol |   mom252 |   qual_mom |   def_revert |
|:-------------|--------:|---------:|---------:|---------:|---------------:|-----------:|---------:|---------:|-----------:|-------------:|
| trend        |   1     |   -0.402 |    0.404 |    0.648 |          0.349 |      0.595 |    0.119 |    0.279 |      0.27  |       -0.147 |
| revert       |  -0.402 |    1     |   -0.143 |   -0.389 |         -0.046 |     -0.21  |   -0.036 |   -0.104 |     -0.094 |        0.491 |
| mom126       |   0.404 |   -0.143 |    1     |    0.289 |          0.61  |      0.566 |    0.109 |    0.593 |      0.57  |       -0.016 |
| mom_st       |   0.648 |   -0.389 |    0.289 |    1     |          0.158 |      0.378 |    0.062 |    0.203 |      0.183 |       -0.166 |
| golden_cross |   0.349 |   -0.046 |    0.61  |    0.158 |          1     |      0.651 |    0.164 |    0.582 |      0.369 |        0.061 |
| breakout     |   0.595 |   -0.21  |    0.566 |    0.378 |          0.651 |      1     |    0.382 |    0.511 |      0.468 |        0.105 |
| lowvol       |   0.119 |   -0.036 |    0.109 |    0.062 |          0.164 |      0.382 |    1     |    0.116 |      0.605 |        0.531 |
| mom252       |   0.279 |   -0.104 |    0.593 |    0.203 |          0.582 |      0.511 |    0.116 |    1     |      0.363 |        0.008 |
| qual_mom     |   0.27  |   -0.094 |    0.57  |    0.183 |          0.369 |      0.468 |    0.605 |    0.363 |      1     |        0.25  |
| def_revert   |  -0.147 |    0.491 |   -0.016 |   -0.166 |          0.061 |      0.105 |    0.531 |    0.008 |      0.25  |        1     |

</details>
