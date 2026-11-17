# Deflated Sharpe — multiple-testing correction on the factor optimiser

Each desk×regime picks the best of 10 factors → selection bias. `IR_exp_max` is the info ratio you'd expect from the best of that many random trials; `DSR` is P(the chosen factor's true edge beats that benchmark). **DSR ≥ 0.95 passes.**

**3 of 10 selected factors survive the correction.**

| market | regime | chosen | trials | IR chosen | IR exp-max | DSR | verdict |
|---|---|---|--:|--:|--:|--:|---|
| IN | bull | trend | 10 | 2.34 | 1.6 | 0.994 | ✅ real |
| IN | bear | def_revert | 10 | 0.86 | 0.74 | 0.627 | ⚠️ fragile |
| US | bull | mom252 | 10 | 1.19 | 0.83 | 0.901 | ⚠️ fragile |
| US | bear | def_revert | 10 | 0.55 | 0.87 | 0.245 | ⚠️ fragile |
| JP | bull | golden_cross | 10 | 0.84 | 0.56 | 0.857 | ⚠️ fragile |
| JP | bear | revert | 10 | 0.84 | 1.44 | 0.105 | ⚠️ fragile |
| KR | bull | breakout | 10 | 2.04 | 1.22 | 0.99 | ✅ real |
| KR | bear | def_revert | 10 | 1.32 | 1.63 | 0.156 | ⚠️ fragile |
| EU | bull | mom252 | 10 | 1.39 | 0.8 | 0.985 | ✅ real |
| EU | bear | revert | 10 | 1.18 | 1.23 | 0.466 | ⚠️ fragile |

> DSR near 1 ⇒ the winner clears the bar set by trying 10 factors — a real edge, not the luckiest draw. Fragile cells (DSR < 0.95) should be treated as unproven and defaulted to the incumbent rule, or re-tested out-of-sample. Near-normal returns assumed (skew≈0); the AWS run can plug in realised skew/kurtosis per factor. Not investment advice.