#!/usr/bin/env python3
"""
strategy_evaluation.py — evaluate the 70 trading strategies from strike.money through this
project's evidence, on two axes that actually decide whether *you* can profit:

  X — RETAIL ACCESSIBILITY: 10 = anyone can run it; 0 = requires the speed/data/flow advantage
      we measured as the information-asymmetry tax (you'd be the counterparty who loses).
  Y — EDGE DURABILITY: 10 = survives multiple-testing / backed by our backtests + literature;
      0 = a win-rate mirage or a data-mined pattern that fails out of sample.

The sweet spot (top-right) = durable AND harvestable by a non-privileged trader — and it is
exactly the slow, magnitude edges this platform validated. Win-rate claims are deliberately
ignored: our confusion-matrix test showed hit-rate is the wrong lens (edge is magnitude).

Output: reports/strategy_evaluation.{csv,md,png}
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

REP = Path(__file__).resolve().parent / "reports"

# (strategy, family, retail_access 0-10, durability 0-10, verdict-note tied to our evidence)
S = [
 # ---- systematic factor / value / momentum (our validated turf) ----
 ("Factor Investing (value/mom/quality)", "systematic", 9, 8, "our core: value-reversion + momentum survive DSR (IN/US/KR/JP)"),
 ("Mean Reversion (value, monthly)", "systematic", 9, 8, "value-reversion +5-6%/6M where fundamentals rule; fails in China"),
 ("Momentum / Trend-Following", "systematic", 8, 7, "survives DSR in TRENDING markets (IN/KR/EU); whipsaws in JP"),
 ("Position Trading", "systematic", 8, 7, "long-horizon trend; capacity-friendly, low info-tax"),
 ("Pairs / Stat-Arb / Cointegration", "systematic", 6, 6, "real mean-reversion of spreads but crowded + execution-sensitive"),
 ("Regression / Correlation trading", "systematic", 6, 5, "trend-deviation reversion; modest, decays (McLean-Pontiff)"),
 # ---- passive / allocation (robust, low edge) ----
 ("Dollar-Cost Averaging", "passive", 10, 6, "market beta not alpha, but robust + zero info-tax"),
 ("Portfolio Rebalancing", "passive", 9, 6, "harvests mean-reversion; Sharpe +0.2-0.5 plausible"),
 ("Risk Parity", "passive", 8, 6, "vol-weighted diversification; robust, not an alpha"),
 ("Tail-Risk Hedging", "passive", 7, 5, "insurance — costs premium, protects drawdown"),
 ("Hedging", "passive", 8, 5, "MPT risk reduction; not a return source"),
 # ---- event-driven (real edge, but short-horizon = high info-tax) ----
 ("PEAD / Earnings Trading", "event", 4, 6, "real (Bernard-Thomas); stronger in high-uncertainty sectors, but the fast trader eats the first move"),
 ("News Trading", "event", 3, 4, "sentiment drives it (our finding) but seconds-horizon = you lose to speed"),
 ("M&A / Merger Arb", "event", 4, 6, "real deal-risk premium; needs capital + deal access"),
 ("Insider Sentiment", "event", 7, 6, "documented 6-12mo outperformance; retail-accessible via filings"),
 ("Dividend Capture", "event", 6, 2, "price drops ~by the dividend; weak after tax"),
 # ---- technical patterns (mostly fail multiple-testing) ----
 ("Breakout Trading", "technical", 7, 4, "36% raw, needs filters; fragile under DSR (Darvas loses in IN)"),
 ("Price Action / Candlesticks", "technical", 7, 2, "fails multiple-testing; VLM study: only short-horizon, regime-bound"),
 ("Fibonacci Retracement", "technical", 7, 2, "no robust out-of-sample edge; arbitrary levels"),
 ("Smart Money Concepts", "technical", 7, 2, "narrative, not a tested edge"),
 ("Reversal Trading", "technical", 7, 2, "41% win-rate (their own number) — negative expectancy"),
 ("Range Trading", "technical", 7, 3, "high win-rate but negative skew (small wins, big losses)"),
 ("Gap Trading", "technical", 5, 3, "70% fill but tiny edge, fast, slippage-heavy"),
 ("Seasonal Trading", "technical", 8, 2, "mostly data-mined; multiple-testing kills most"),
 ("Social / Copy Trading", "technical", 8, 2, "no durable edge; you copy the lag"),
 # ---- options / volatility (structural edge to SELLERS, retail buyers lose) ----
 ("Vol Selling / Theta / Vol-Crush", "options", 5, 6, "vol-risk-premium is real for SELLERS; tail risk; needs margin"),
 ("Options Buying (OTM)", "options", 6, 1, "80-90% of NSE OTM buyers lose — negative edge"),
 ("Calendar / Delta-neutral / Gamma / Skew", "options", 4, 5, "real structural edges but need infra + constant management"),
 ("Basis / Funding-rate Arb", "options", 3, 6, "convergence is predictable; needs scale + low cost"),
 # ---- market structure / HFT (real edge, ENTIRELY privileged — the info-asymmetry side) ----
 ("HFT / Latency Arb", "market-structure", 1, 8, "real but pure speed advantage — retail is the prey, not the hunter"),
 ("Market Making", "market-structure", 1, 7, "earns the spread — needs colocation + inventory tech"),
 ("Order Flow / Tape Reading", "market-structure", 2, 5, "the informed side of our info-asymmetry tax"),
 ("VWAP Trading", "market-structure", 4, 4, "institutional execution benchmark, not an alpha"),
 ("Dark Pool / Liquidity Grab / Scalping", "market-structure", 1, 2, "scalping: 80-95% lose; dark-pool needs privileged data"),
 ("Arbitrage (classic)", "market-structure", 3, 6, "0.1-0.5%/trade, 70-90% hit — but competed to zero without speed"),
 # ---- sentiment / macro / crypto ----
 ("Sentiment Analysis (FII/fear-greed)", "sentiment", 5, 4, "IS the speculation driver (our China/Iran finding); short-lived"),
 ("Macro / Rates / Inflation Trading", "macro", 5, 5, "real cycle edge; hard to systematize, slow"),
 ("Crypto / DeFi / Yield / Staking", "crypto", 6, 3, "different asset class; yield real but smart-contract + vol risk"),
 ("Quant / Algo / AI Trading", "meta", 5, 5, "only as good as the underlying signal — a wrapper, not an edge"),
]


def main() -> int:
    d = pd.DataFrame(S, columns=["strategy", "family", "retail_access", "durability", "note"])
    d["harvestable"] = (d.retail_access >= 6) & (d.durability >= 6)
    d.sort_values(["harvestable", "durability", "retail_access"], ascending=False).to_csv(
        REP / "strategy_evaluation.csv", index=False)

    harvest = d[d.harvestable].sort_values("durability", ascending=False)
    L = ["# Evaluating 70 trading strategies (strike.money) through this project's evidence", "",
         "Two axes decide whether *you* can profit: **durability** (does the edge survive "
         "multiple-testing?) and **retail accessibility** (can you run it, or does it need the "
         "speed/data advantage we measured as the information-asymmetry tax?). Win-rate claims are "
         "ignored — our confusion-matrix test showed the edge is *magnitude*, not hit-rate.", "",
         "## ✅ The harvestable set (durable AND retail-accessible)", "",
         "| strategy | family | access | durability | why (our evidence) |", "|---|---|--:|--:|---|"]
    for _, r in harvest.iterrows():
        L.append(f"| {r.strategy} | {r.family} | {r.retail_access} | {r.durability} | {r.note} |")
    L += ["", "## 🔴 Real edge, but NOT for you (privileged — you're the counterparty)", "",
          "| strategy | access | durability | why |", "|---|--:|--:|---|"]
    for _, r in d[(d.durability >= 5) & (d.retail_access <= 3)].sort_values("durability", ascending=False).iterrows():
        L.append(f"| {r.strategy} | {r.retail_access} | {r.durability} | {r.note} |")
    L += ["", "## ⚠️ Retail-accessible but no durable edge (the win-rate traps)", "",
          "| strategy | access | durability | why |", "|---|--:|--:|---|"]
    for _, r in d[(d.durability <= 3) & (d.retail_access >= 6)].sort_values("durability").iterrows():
        L.append(f"| {r.strategy} | {r.retail_access} | {r.durability} | {r.note} |")
    L += ["", "## The three lessons this project proves about that list", "",
          "1. **Durable edge and retail access rarely coexist.** The top-right corner is nearly all "
          "*slow, systematic, magnitude* strategies (value-reversion, momentum, factor, position) — "
          "exactly what we validated. Everything fast and durable (HFT, market-making, arb) lives "
          "top-left: real, but it *is* the information-asymmetry tax being charged to retail.",
          "2. **Win-rate is a marketing lens.** Range/gap/reversal advertise 41-80% win rates yet "
          "carry negative skew; our confusion matrix showed value-reversion wins only ~50% of the "
          "time and still profits — magnitude, not frequency.",
          "3. **Speculation strategies work only where speculation rules.** Sentiment/news/technical "
          "patterns 'work' in retail-driven, high-uncertainty regimes (and are then arbitraged by "
          "the fast) — the same fundamentals-vs-speculation dial from the sector work.", "",
          "> Scores are judgemental, grounded in this repo's backtests + the cited literature, not a "
          "fresh backtest of all 70. Research, not investment advice."]
    (REP / "strategy_evaluation.md").write_text("\n".join(L))

    # ---- the 2D map ----
    fam_c = {"systematic": "#1a9850", "passive": "#66bd63", "event": "#4575b4", "technical": "#d73027",
             "options": "#fdae61", "market-structure": "#762a83", "sentiment": "#f46d43",
             "macro": "#5aae61", "crypto": "#8073ac", "meta": "#999999"}
    fig, ax = plt.subplots(figsize=(13, 9))
    ax.axhspan(6, 10.5, xmin=0.55, alpha=.06, color="green")     # sweet spot
    for _, r in d.iterrows():
        ax.scatter(r.retail_access, r.durability, s=120, color=fam_c.get(r.family, "#888"),
                   edgecolor="k", linewidth=.5, alpha=.85, zorder=3)
        ax.annotate(r.strategy.split("(")[0].strip()[:26], (r.retail_access, r.durability),
                    fontsize=6.3, xytext=(3, 3), textcoords="offset points")
    ax.axvline(5.5, ls="--", c="grey", alpha=.5); ax.axhline(5.5, ls="--", c="grey", alpha=.5)
    ax.text(8.3, 9.7, "HARVESTABLE\n(durable + retail)", fontsize=11, color="#1a9850", ha="center", fontweight="bold")
    ax.text(2.3, 9.7, "PRIVILEGED\n(real, needs speed/data)", fontsize=10.5, color="#762a83", ha="center", fontweight="bold")
    ax.text(8.3, 1.1, "WIN-RATE TRAPS\n(accessible, no edge)", fontsize=10.5, color="#d73027", ha="center", fontweight="bold")
    ax.text(2.3, 1.1, "worst of both", fontsize=9.5, color="#555", ha="center")
    ax.set_xlabel("Retail accessibility  →  (10 = anyone; 0 = needs the info-asymmetry advantage)", fontsize=11)
    ax.set_ylabel("Edge durability  →  (10 = survives multiple-testing; 0 = mirage)", fontsize=11)
    ax.set_title("70 trading strategies mapped by what actually matters: durable edge × who can capture it",
                 fontsize=12)
    ax.set_xlim(-0.5, 10.8); ax.set_ylim(0, 10.6)
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=f, ms=8) for f, c in fam_c.items()]
    ax.legend(handles=handles, fontsize=8, loc="lower left", ncol=2, title="family")
    plt.tight_layout(); plt.savefig(REP / "strategy_evaluation.png", dpi=150, bbox_inches="tight")
    print("\n".join(L[:34]))
    print(f"\nwrote reports/strategy_evaluation.{{csv,md,png}} ({len(d)} strategies, "
          f"{d.harvestable.sum()} harvestable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
