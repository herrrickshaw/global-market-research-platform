#!/usr/bin/env python3
"""
edge_matrix.py — the Ted Williams / Buffett "fat-pitch" grid: filter/strategy × market,
coloured by where the real edge is, so you only SWING where your batting average is high.

Each cell = the backtested (or paper-track) edge for running that filter in that market,
with its significance. Green = the happy zone (swing); red = cold corner (take the pitch);
grey = not enough data to call. Sources: this repo's committed backtests + the paper-track.

Output: reports/edge_matrix.csv + reports/edge_matrix.png
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
MKTS = ["IN", "US", "KR", "JP", "EU", "CN"]

# each cell: (score in [-2..+2] for colour, short label with the number + significance)
# score: +2 strong validated edge · +1 positive · 0 underpowered/untested/neutral ·
#        -1 validated-negative / fails · (grey when label starts with '—')
G = lambda s, t: (s, t)
MATRIX = {
 "Value-reversion (cheap−rich, 6M)": {
   "IN": G(2, "+5.3% t2.5"), "US": G(2, "+1.7%/3M t2.3"), "KR": G(1, "+3.9% t1.5"),
   "JP": G(2, "+6.6% t4.8"), "EU": G(0, "— underpwr"), "CN": G(-1, "≈0 t0.0 FAILS")},
 "Value+Quality L/S (cheap∩hiROE − rich∩loROE)": {
   "IN": G(-1, "−1.0% FAILS"), "US": G(1, "+1.7% t1.0"), "KR": G(2, "+4.8% t4.2"),
   "JP": G(0, "— untested"), "EU": G(0, "— no fund"), "CN": G(0, "— untested")},
 "Momentum / Trend (bull, Deflated-Sharpe)": {
   "IN": G(2, "trend DSR.99"), "US": G(1, "mom DSR.90 frag"), "KR": G(2, "breakout DSR.99"),
   "JP": G(-1, "no DSR survivor"), "EU": G(2, "mom DSR.99"), "CN": G(0, "— untested")},
 "Mean-reversion (bear regime)": {
   "IN": G(-1, "weak"), "US": G(0, "fails DSR"), "KR": G(0, "fails DSR"),
   "JP": G(0, "fails DSR"), "EU": G(0, "fails DSR"), "CN": G(0, "—")},
 "Darvas breakout (paper-track excess)": {
   "IN": G(-1, "−0.29%"), "US": G(1, "+1.11%"), "KR": G(0, "— thin"),
   "JP": G(0, "— thin"), "EU": G(1, "+1.58%"), "CN": G(0, "—")},
 "Golden cross 50>200 (paper-track)": {
   "IN": G(1, "+0.61%"), "US": G(0, "— thin"), "KR": G(0, "— thin"),
   "JP": G(0, "— thin"), "EU": G(0, "— thin"), "CN": G(0, "—")},
 "Piotroski F-score / quality": {
   "IN": G(0, "liq-gated"), "US": G(-1, "INVERTED"), "KR": G(0, "—"),
   "JP": G(0, "—"), "EU": G(0, "—"), "CN": G(0, "—")},
}


def main() -> int:
    rows = list(MATRIX)
    scores = np.array([[MATRIX[r][m][0] for m in MKTS] for r in rows], float)
    labels = [[MATRIX[r][m][1] for m in MKTS] for r in rows]
    # grey-out underpowered/untested (label starts with — or 'liq' etc handled by score 0 + —)
    mask_grey = np.array([[MATRIX[r][m][1].strip().startswith("—") for m in MKTS] for r in rows])

    # CSV
    pd.DataFrame([{**{"strategy": r}, **{m: MATRIX[r][m][1] for m in MKTS}} for r in rows]) \
        .to_csv(HERE / "reports" / "edge_matrix.csv", index=False)

    # heatmap (Ted Williams style)
    fig, ax = plt.subplots(figsize=(11, 6.5))
    disp = np.where(mask_grey, np.nan, scores)
    cmap = plt.cm.RdYlGn.copy(); cmap.set_bad("#d9d9d9")
    ax.imshow(disp, cmap=cmap, vmin=-2, vmax=2, aspect="auto")
    ax.set_xticks(range(len(MKTS))); ax.set_xticklabels(MKTS, fontsize=13, fontweight="bold")
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows, fontsize=9)
    ax.set_xlabel("market", fontsize=11); ax.xaxis.set_label_position("top"); ax.xaxis.tick_top()
    for i in range(len(rows)):
        for j in range(len(MKTS)):
            ax.text(j, i, labels[i][j], ha="center", va="center", fontsize=7.5,
                    color="black", wrap=True)
    ax.set_title("Where's the edge? Filter × Market  —  swing only at the fat pitch\n"
                 "(Ted Williams / Buffett: green = your .400 zone, red = the .230 corner, grey = not enough data)",
                 fontsize=11, pad=30)
    ax.set_xticks(np.arange(-.5, len(MKTS), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(rows), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    plt.tight_layout()
    out = HERE / "reports" / "edge_matrix.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"wrote {out} + reports/edge_matrix.csv")
    # the fat pitches
    print("\nFAT PITCHES (swing — score +2):")
    for r in rows:
        for m in MKTS:
            if MATRIX[r][m][0] == 2:
                print(f"  {m}: {r.split('(')[0].strip()} ({MATRIX[r][m][1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
