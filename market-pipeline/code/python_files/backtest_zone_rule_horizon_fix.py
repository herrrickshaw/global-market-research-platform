#!/usr/bin/env python3
"""Verification backtest: quantify the cost of the watchlist_digest.py zone-rule bug.

assign_recommendations() maps EVERY non-trend rule ("revert", "mom_st",
"mom126") to the SAME field, r["d5"] (5-trading-day return):

    key = {"revert": "d5", "mom_st": "d5", "mom126": "d5"}.get(rule, "d5")

"revert" is INTENDED to use d5 (5d return), inverted -- that part is correct
and matches backtest_zone_rules.py's own "revert" signal (tercile of r5,
inverted). But "mom_st" (1-month) and "mom126" (6-month) are then ranked by
the SAME d5 field, non-inverted (top tercile = BUY) -- since the digest never
computes d21/d126 fields at all. This is exactly the "mom5" candidate below:
non-inverted top-tercile of the SAME r5 series "revert" already uses.

Reuses backtest_zone_rules.py's load_closes/zone_signals/score verbatim --
same panels, same forward-10d spread methodology, same de-overlapped t-stat.
"""
import numpy as np
import pandas as pd
from backtest_zone_rules import load_closes, score, MARKETS, TERCILE

for mkt in MARKETS:
    w = load_closes(mkt)
    r5 = w.pct_change(1, fill_method=None)

    def tercile_sig(r):
        lo = r.rank(axis=1, pct=True)
        return (lo >= 1 - TERCILE).astype(int) - (lo <= TERCILE).astype(int)

    mom5 = tercile_sig(r5)          # the ACTUAL live signal today (buggy)
    revert = -mom5                  # the INTENDED "revert" signal (sanity check, should match doc)

    sp_mom5, t_mom5 = score(w, mom5, w)
    sp_revert, t_revert = score(w, revert, w)
    print(f"{mkt}: mom5(live-buggy-behavior)={sp_mom5:+.3f}% (t{t_mom5:+.2f})   "
          f"revert(correct, sanity-check)={sp_revert:+.3f}% (t{t_revert:+.2f})")
