#!/usr/bin/env python3
"""
market_playbook.py — the actionable synthesis: for EACH market, the retail-accessible edges
ranked by priority, from this project's backtested evidence. Only the "harvestable" quadrant
(durable + retail-accessible, low information-asymmetry tax) is recommended; win-rate traps and
privileged/HFT edges are excluded by construction.

Priority score per (edge, market): 3 = PRIMARY (strongest validated edge), 2 = secondary,
1 = base layer (always-on), 0 = n/a, −1 = AVOID (tested and fails there).

Output: reports/market_playbook.{md,png} + reports/market_playbook.csv
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

REP = Path(__file__).resolve().parent / "reports"
MKTS = ["IN", "US", "KR", "JP", "EU", "CN"]
EDGES = ["Value-reversion (cheap PE)", "Value+Quality Long/Short", "Momentum / Trend",
         "Quality (hi-ROE) overlay", "Insider sentiment (6-12m)", "Passive core (DCA+rebalance)"]

# score + evidence note per (edge, market)
P = {
 "Value-reversion (cheap PE)": {
   "IN": (2, "+5.3%/6M t2.5 (sector-relative), long-only"), "US": (3, "+1.7%/3M t2.3 — best US edge, hold ≤3M"),
   "KR": (2, "+3.85%/6M t1.5"), "JP": (3, "+6.6%/6M t4.84 — strongest value anywhere"),
   "EU": (0, "underpowered — can't recommend yet"), "CN": (-1, "TESTED & FAILS (t0.3) — do not run")},
 "Value+Quality Long/Short": {
   "IN": (-1, "−1.0%/6M — momentum runs shorts over"), "US": (1, "+1.7%/6M t1.0 marginal"),
   "KR": (3, "+4.83%/6M t4.17 — STRONGEST edge of all; full L/S"), "JP": (2, "ROE available; extension of value"),
   "EU": (0, "no fundamentals depth"), "CN": (-1, "value leg fails")},
 "Momentum / Trend": {
   "IN": (3, "trend DSR 0.994 — most robust factor found; long-only"), "US": (1, "mom DSR 0.90 fragile — light"),
   "KR": (2, "breakout DSR 0.99"), "JP": (-1, "no DSR survivor — whipsaws"),
   "EU": (3, "mom252 DSR 0.985 — primary EU edge"),
   "CN": (-1, "TESTED & FAILS at 6M too (W−L −0.7%, t−0.2) — any CN momentum is fast/retail-inaccessible")},
 "Quality (hi-ROE) overlay": {
   "IN": (2, "earns premium behind the liquidity gate"), "US": (-1, "Piotroski INVERTED in US"),
   "KR": (2, "hi-ROE cheap = the Korea discount"), "JP": (1, "pairs with value"),
   "EU": (0, ""), "CN": (0, "")},
 "Insider sentiment (6-12m)": {
   "IN": (1, "filings-based, 6-12m outperformance"), "US": (1, "SEC Form 4, documented edge"),
   "KR": (1, "DART disclosures"), "JP": (1, "EDINET disclosures"), "EU": (1, ""), "CN": (0, "disclosure quality low")},
 "Passive core (DCA+rebalance)": {m: (1, "always-on base: DCA + annual rebalance, vol-targeted") for m in MKTS},
}
CHAR = {"IN": "momentum / long-only", "US": "mixed / efficient — light", "KR": "mean-reversion / full L/S",
        "JP": "value-reversion", "EU": "momentum (bull)", "CN": "speculation-ruled — passive only"}


def main() -> int:
    rows = []
    for e in EDGES:
        for m in MKTS:
            s, note = P[e].get(m, (0, ""))
            rows.append({"edge": e, "market": m, "priority": s, "note": note})
    d = pd.DataFrame(rows)
    d.to_csv(REP / "market_playbook.csv", index=False)

    # ---- per-market ranked playbook (markdown) ----
    L = ["# Market playbook — retail-accessible edges, ranked by priority per market", "",
         "Only durable + retail-harvestable edges (low information-asymmetry tax). Ranked by this "
         "project's backtests. 🥇 primary · 🥈 secondary · ⚙️ base · 🚫 avoid (tested & fails).", ""]
    tag = {3: "🥇 PRIMARY", 2: "🥈 secondary", 1: "⚙️ base", -1: "🚫 AVOID"}
    for m in MKTS:
        L += [f"## {m} — *{CHAR[m]}*", ""]
        sub = d[(d.market == m) & (d.priority != 0)].sort_values("priority", ascending=False)
        for _, r in sub.iterrows():
            L.append(f"- {tag[r.priority]} — **{r.edge}** — {r.note}")
        L.append("")
    L += ["## Rules that apply everywhere", "",
          "- **Horizon:** monthly-to-6-month rebalances only. Fast signals lose to the "
          "information-asymmetry tax (you'd be the counterparty).",
          "- **Sizing:** inverse-vol + vol-target + a kill-switch (halves max drawdown).",
          "- **Capacity:** the edge is illiquidity-driven — **~$300–500k** before it decays; a "
          "retail/family-office edge, not institutional.",
          "- **Read spreads, not win-rate:** ~50% hit-rate is normal; the profit is in magnitude.",
          "- **Long-only vs long/short:** short only where the market mean-reverts (KR ✅); never "
          "short a trending market (IN 🚫).",
          "- **Costs:** net of round-trip cost the edge must still clear — worst in IN/CN (wide "
          "spreads), best in US.", "",
          "> Descriptive research — not investment advice. Every ranking traces to a committed "
          "backtest (`edge_matrix`, `valuation_reversion_*`, `deflated_sharpe`, `value_quality_ls`)."]
    (REP / "market_playbook.md").write_text("\n".join(L))

    # ---- heatmap: edge × market priority ----
    piv = d.pivot(index="edge", columns="market", values="priority").reindex(EDGES)[MKTS]
    fig, ax = plt.subplots(figsize=(11, 6))
    cmap = plt.cm.RdYlGn
    ax.imshow(piv.values, cmap=cmap, vmin=-1.5, vmax=3, aspect="auto")
    ax.set_xticks(range(len(MKTS))); ax.set_xticklabels(MKTS, fontsize=13, fontweight="bold")
    ax.set_yticks(range(len(EDGES))); ax.set_yticklabels(EDGES, fontsize=10)
    lab = {3: "PRIMARY", 2: "2nd", 1: "base", 0: "—", -1: "AVOID"}
    for i, e in enumerate(EDGES):
        for j, m in enumerate(MKTS):
            v = piv.values[i, j]
            ax.text(j, i, lab.get(int(v), ""), ha="center", va="center", fontsize=8,
                    fontweight="bold" if v == 3 else "normal",
                    color="white" if v == -1 else "black")
    ax.set_title("Market playbook — retail-accessible edges by priority per market\n"
                 "(green PRIMARY = swing here · red AVOID = tested & fails)", fontsize=12)
    ax.xaxis.set_label_position("top"); ax.xaxis.tick_top()
    ax.set_xticks(np.arange(-.5, len(MKTS), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(EDGES), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    plt.tight_layout(); plt.savefig(REP / "market_playbook.png", dpi=150, bbox_inches="tight")
    print("\n".join(L))
    print("\nwrote reports/market_playbook.{md,png,csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
