#!/usr/bin/env python3
"""
screener_evaluation.py — evaluate screener.in's most-popular Indian screens against this
project's India evidence.

India verdicts we lean on (all committed backtests):
  • Momentum/Trend (50>200 DMA) — Deflated-Sharpe 0.994, the most robust factor found.
  • Value-reversion (sector-relative cheap PE) — +5.3%/6M, t2.5.
  • Quality (high ROE / Piotroski) — earns a premium, BUT only behind the liquidity gate.
  • The edge is ILLIQUIDITY, not size — value/quality mispricing lives in the small, illiquid
    tail; large-cap names are efficiently priced (cost/capacity study). So a market-cap FLOOR
    (blue-chip screens) fights the very edge it's trying to harvest.
  • India is long-only — never short.

Each popular screen is scored on factor alignment + liquidity-friendliness → an effectiveness
verdict. Popularity ≠ effectiveness.

Output: reports/screener_evaluation.{csv,md,png}
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

REP = Path(__file__).resolve().parent / "reports"

# (screen, factor family, factor_align 0-10, liquidity_friendly 0-10, verdict, why)
S = [
 ("Golden Crossover (50>200 DMA)", "trend", 10, 8, "EFFECTIVE",
  "our PRIMARY India edge — trend survives Deflated Sharpe (Bailey & Lopez de Prado "
  "2014) at 0.994; no size cap"),
 ("Magic Formula (ROCE + earnings yield)", "quality+value", 8, 7, "EFFECTIVE",
  "combines the two validated factors; Greenblatt travels to India; no cap floor"),
 ("Value Stocks (hi OPM/ROCE, low D/E)", "quality+value", 8, 7, "EFFECTIVE",
  "targets validated quality+value, keeps the illiquid tail where the edge lives"),
 ("High Growth + High RoE + Low PE", "quality+value+growth", 8, 6, "EFFECTIVE",
  "multi-factor sweet spot; all three validated in India"),
 ("The Bull Cartel (quarterly growth)", "earnings momentum", 7, 6, "GOOD",
  "earnings momentum aligns with India's momentum character; can be crowded/priced"),
 ("Growth Stocks (GARP / G-Factor)", "growth+quality", 6, 6, "GOOD",
  "growth+quality tilt; India is momentum-friendly, but GARP crowds"),
 ("Low on 10Y Avg Earnings (Graham)", "deep value", 6, 6, "MODERATE",
  "value reverts in India, but absolute deep-value catches value traps (use sector-relative)"),
 ("Piotroski Scan (F = 9)", "quality", 6, 5, "MODERATE",
  "quality earns a premium BUT F-score alone is weak without the liquidity gate (US F is inverted)"),
 ("FII Buying (institutional flow)", "flow / sentiment", 5, 6, "MODERATE",
  "FII flow chases momentum (some signal) but you follow the lag; short-lived, front-run-able"),
 ("Benjamin Graham & Buffett (sales>₹250cr)", "value + size floor", 5, 4, "MODERATE",
  "value works, but the sales floor starts excluding the illiquid tail where the edge is strongest"),
 ("Highest Dividend Yield", "dividend / value", 4, 5, "WEAK",
  "dividend-capture is weak; high-DY in India skews to low-growth PSU value traps"),
 ("Bluest of the Blue Chips (mcap>₹3000cr)", "large-cap value", 3, 2, "WEAK",
  "the large-cap FLOOR kills the illiquidity edge — big Indian names are efficiently priced; "
  "popular but the worst place to find mispricing"),
]


def main() -> int:
    d = pd.DataFrame(S, columns=["screen", "family", "factor_align", "liquidity_friendly", "verdict", "why"])
    d["score"] = (d.factor_align + d.liquidity_friendly) / 2
    d = d.sort_values("score", ascending=False)
    d.to_csv(REP / "screener_evaluation.csv", index=False)

    vcol = {"EFFECTIVE": "🟢", "GOOD": "🟢", "MODERATE": "🟡", "WEAK": "🔴"}
    L = ["# Evaluating screener.in's popular Indian screens — effective or just popular?", "",
         "Scored against this project's India backtests: **trend** (DSR 0.994, PRIMARY), "
         "**value-reversion** (+5.3%/6M, t2.5), **quality** (premium behind the liquidity gate), and "
         "the key finding that **the edge is illiquidity, not size** — so a market-cap floor fights "
         "the edge. India is long-only.", "",
         "| screen | family | verdict | effectiveness | why |", "|---|---|---|--:|---|"]
    for _, r in d.iterrows():
        L.append(f"| {r.screen} | {r.family} | {vcol[r.verdict]} {r.verdict} | {r.score:.1f}/10 | {r.why} |")
    L += ["", "## The pattern — popularity ≠ effectiveness", "",
          "- **Most effective:** *Golden Crossover* (our validated PRIMARY trend edge) and the "
          "multi-factor **quality+value screens without a size cap** (Magic Formula, Value Stocks, "
          "High-Growth-High-RoE-Low-PE). These target exactly the factors that survive our tests.",
          "- **The big trap — blue-chip / size-floor screens.** *Bluest of the Blue Chips* "
          "(mcap>₹3000cr) and Graham-Buffett (sales>₹250cr) are hugely popular, but our cost/"
          "capacity research shows India's mispricing lives in the **small, illiquid** tail — large "
          "caps are efficiently priced. A size floor systematically removes the edge. **Popular, but "
          "structurally weak.**",
          "- **Weak regardless of popularity:** *Highest Dividend Yield* (dividend-capture is weak; "
          "PSU value-trap skew), *FII Buying* (you follow the lag of a momentum chase).",
          "- **Use with a fix:** *Piotroski F=9* and *Graham deep-value* work **only** when run "
          "behind the **liquidity gate** and made **sector-relative** — raw versions catch traps.", "",
          "## How to actually use them (India playbook alignment)", "",
          "1. **Base signal:** Golden Crossover (trend) — the PRIMARY India edge.",
          "2. **Overlay:** one quality+value screen *without a market-cap floor* (Magic Formula or "
          "Value Stocks), run **behind the liquidity gate** (tradeable but not mega-cap).",
          "3. **Confirm:** sector-relative cheapness (not absolute deep-value) to dodge value traps.",
          "4. **Never** filter to blue-chips only, never short, size by inverse-vol, ~₹300–500k "
          "capacity before the edge decays.", "",
          "> Verdicts are grounded in this repo's committed India backtests (`deflated_sharpe`, "
          "`valuation_reversion`, cost/capacity study), not a fresh backtest of each screen's exact "
          "query. Research, not investment advice."]
    (REP / "screener_evaluation.md").write_text("\n".join(L))

    # viz
    fig, ax = plt.subplots(figsize=(11, 7))
    vc = {"EFFECTIVE": "#1a9850", "GOOD": "#66bd63", "MODERATE": "#fdae61", "WEAK": "#d73027"}
    d2 = d.sort_values("score")
    ax.barh(d2.screen, d2.score, color=[vc[v] for v in d2.verdict])
    ax.set_xlabel("effectiveness in Indian markets (our evidence)  →  factor alignment × liquidity-friendliness")
    ax.axvline(6.5, ls="--", c="grey", alpha=.5)
    for i, (s, v) in enumerate(zip(d2.score, d2.verdict)):
        ax.text(s + 0.1, i, v, va="center", fontsize=8)
    ax.set_title("screener.in popular screens, evaluated for India\n"
                 "green = targets a validated edge · red = popular but structurally weak (size-floor / dividend traps)",
                 fontsize=11)
    ax.set_xlim(0, 10)
    plt.tight_layout(); plt.savefig(REP / "screener_evaluation.png", dpi=150, bbox_inches="tight")
    print("\n".join(L))
    print("\nwrote reports/screener_evaluation.{csv,md,png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
