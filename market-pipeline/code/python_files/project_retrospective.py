#!/usr/bin/env python3
"""
project_retrospective.py — the full-project retrospective: the analysis arc from day one,
the consolidated findings (with confidence), the prioritised GAPS to fix, and what is novel
enough to PUBLISH. Emits a doc + a gap-priority map (impact × effort).
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

REP = Path(__file__).resolve().parent / "reports"

# consolidated findings: (finding, confidence 0-10, status)
FIND = [
 ("Market character decides the playbook (IN mom, KR L/S, JP/US value, EU mom, CN passive)", 9, "validated"),
 ("Value-reversion works IN/US/KR/JP (t2.3–4.84), FAILS in China (t0.3, powered null)", 9, "validated"),
 ("Momentum/trend survives multiple-testing in IN/KR/EU (Deflated Sharpe >0.95)", 8, "validated"),
 ("Fundamentals-vs-speculation is the master dial (explains China null + biotech + PEAD routing)", 8, "validated"),
 ("Three regimes not two: current-fundamentals / R&D-growth / speculation (R&D-adj ROIC)", 7, "validated"),
 ("PEAD lives in the SPECULATIVE corner (information uncertainty), opposite of value-reversion", 7, "validated"),
 ("Edge is MAGNITUDE not hit-rate (~50% accuracy yet profitable); illiquidity-driven, ~$300–500k cap", 8, "validated"),
 ("Information-asymmetry tax is horizon-dependent → retail can only harvest SLOW edges", 8, "validated"),
 ("Measurement > data quantity (Japan flip: null→+6.6%/6M t4.84 via EDINET depth)", 9, "validated"),
 ("Country-ERP: China's cheapness is NOT risk-justified (CRP 0.91%) → speculation confirmed", 7, "validated"),
 ("China: NEITHER value (t0.3) NOR 6M momentum (t−0.2) works — passive only (was tentative, now tested)", 8, "validated"),
 ("KR value+quality L/S HALVES net of borrow (+4.83%→+2.3%/6M, t4.2→2.0); US L/S turns negative net", 8, "validated"),
 ("China is BIMODAL — anchored SOE core (Utilities PB~ROE R²0.90) + speculative retail growth-periphery", 6, "validated (small-n caveat)"),
 ("Fundamentals-vs-speculation is MARKET×SECTOR-specific, not poolable across markets", 7, "validated"),
 ("EU value effect", 2, "underpowered — cannot conclude"),
]

# gaps: (gap, impact 0-10, effort 0-10 to fix, fix)
GAP = [
 ("valuation_clusters only IN/US/KR — JP/EU/CN have no peer clusters (screener falls back)", 8, 3,
  "re-run valuation_clustering.py on JP_full/CN_full/EU_union (data now exists) → fills JP/EU picks"),
 ("Full-universe fundamentals-vs-speculation incomplete (US-only preview)", 6, 4,
  "join Damodaran sector map (48k, instant) to all markets → the cross-market speculation map"),
 ("H2 Accumulation (prior paper) never re-tested this session", 5, 4,
  "OBV/Chaikin accumulation backtest — auditable open item from the paper"),
 ("Confusion matrix on SHORT-horizon signals (PEAD/momentum) not done", 6, 4,
  "where the info-asymmetry tax actually bites — run the net-of-cost classifier on fast signals"),
 ("EV/EBITDA sector map not run (dam_vebitda downloaded)", 5, 2,
  "capital-structure-neutral re-do of the sector map — de-distorts financials/asset-heavy"),
 ("Time-series speculation only US 2017–2025, shallow", 5, 5,
  "deeper history + other markets once sector collection completes"),
 ("Short-borrow cost not modelled in KR/JP long/short returns", 6, 3,
  "haircut the short leg by a locate+borrow estimate — the L/S t-stats are gross"),
 ("Regime (bull/bear) not wired into the LIVE screener (static filters)", 5, 4,
  "condition the playbook screener on the breadth-regime proxy already built"),
 ("EU depth pre-2021 paywalled → EU value stays underpowered", 4, 7,
  "national registries / paid vendor — low priority, hard"),
 ("Live forward performance = zero (paper-track just started)", 7, 9,
  "TIME — the picks were only just watchlisted; needs weeks/months to validate out-of-sample"),
]

# publish candidates: (title, novelty 0-10, venue)
PUB = [
 ("Measurement over quantity: the Japan value flip (null→edge via deep PIT data)", 9, "note/blog + v3 paper"),
 ("Fundamentals-vs-speculation as a master dial (sector+market, PEAD routing)", 8, "working paper section"),
 ("Cross-market factor character map (which factor fits which market, 6 markets deep-data)", 8, "v3 of the platform paper"),
 ("Information-asymmetry tax × horizon: why retail can only harvest slow edges", 7, "blog/note"),
 ("Three regimes: separating R&D-growth from speculation (R&D-adjusted ROIC)", 6, "note"),
]


def main() -> int:
    L = ["# Project retrospective — findings, gaps, and what to publish", "",
         "A full-arc review from the platform's origin to the live paper-track: what we've "
         "established, what's still open, and which insights are novel enough to publish.", "",
         "## The analysis arc (phases)", "",
         "1. **Build** — multi-market platform, income/balance statements from the paper-track, "
         "10-stage pipeline, regime survival, Lasso/learning-rate, AWS/Colab sweep, mailer/watchlist.",
         "2. **Validate** — PIT reversion backtests, Deflated Sharpe, value+quality L/S, the "
         "suitability matrix; the market-character meta-finding.",
         "3. **Guard** — the anti-false-outcome layer: data_sufficiency, data_ledger, "
         "source_registry, the every-3-days check; caught false JP/EU/CN verdicts.",
         "4. **Collect** — deep PIT fundamentals (CN baostock 10y, JP EDINET/J-Quants, EU union, "
         "JPX sectors, Damodaran) with anti-throttle (baostock, curl_cffi); the Japan flip.",
         "5. **Explain** — fundamentals-vs-speculation (3 lenses + Damodaran + ROIC/WACC + "
         "country-ERP), PEAD routing, the confusion-matrix/information-asymmetry synthesis.",
         "6. **Evaluate** — 70 strategies (durability × access), screener.in popular screens, an "
         "audit of the prior working paper.",
         "7. **Operationalise** — the market playbook → live playbook screener → watchlist → daily "
         "mailer (sent). Research is now a running system.", "",
         "## Consolidated findings", "",
         "| finding | confidence | status |", "|---|--:|---|"]
    for f, c, s in FIND:
        L.append(f"| {f} | {c}/10 | {s} |")
    L += ["", "## Gaps to fix (prioritised by impact ÷ effort)", "",
          "| gap | impact | effort | fix |", "|---|--:|--:|---|"]
    for g, i, e, fx in sorted(GAP, key=lambda x: -(x[1] / max(x[2], 1))):
        L.append(f"| {g} | {i} | {e} | {fx} |")
    L += ["", "### ✅ Cleared this pass\n\n1. Extended valuation clustering to JP/EU/CN (JP picks 3→8). 2. CN momentum backtested — fails at 6M (t−0.2), corrects the 'likely' claim. 3. Borrow-haircut on L/S — KR halves to +2.3%/6M t2.0, US turns negative. 4. Full-universe fund-vs-spec (all 6 markets, 95% sectors) — China-bimodal + not-poolable findings. 5. EV/EBITDA cross-check.\n\n### Residual backlog (bigger / time-gated)", "",
          "1. **Extend valuation clustering to JP/EU/CN** — the data now exists; instantly fills the "
          "thin JP/EU picks and gives peer-relative value everywhere (impact 8, effort 3).",
          "2. **Backtest CN momentum** — resolve the one asserted-but-untested claim (impact 6, effort 3).",
          "3. **Haircut the KR/JP L/S returns for borrow cost** — the strongest edge (KR t4.2) is gross "
          "of the short-leg cost; net it before trusting the magnitude (impact 6, effort 3).",
          "4. **Join the Damodaran 48k sector map to all markets** — completes the cross-market "
          "speculation map without waiting on the yfinance crawl (impact 6, effort 3).", "",
          "## What to publish", "",
          "| insight | novelty | vehicle |", "|---|--:|---|"]
    for t, n, v in sorted(PUB, key=lambda x: -x[1]):
        L.append(f"| {t} | {n}/10 | {v} |")
    L += ["", "**The headline publishable contribution:** *measurement quality dominates data "
          "quantity* — demonstrated live by the Japan flip (an underpowered null became a t 4.84 edge "
          "when deep PIT history replaced a snapshot) **and** its mirror, China (a null that "
          "*survived* the same deepening). This is the inverse of the replication crisis and extends "
          "the prior working paper to a v3 with genuine cross-market deep data. The "
          "fundamentals-vs-speculation dial and the retail-harvestability framing are the two other "
          "sections worth writing up.", "",
          "> Descriptive research retrospective. Not investment advice."]
    (REP / "project_retrospective.md").write_text("\n".join(L))

    # gap-priority map: impact × effort
    fig, ax = plt.subplots(figsize=(12, 8))
    for g, i, e, _ in GAP:
        col = "#1a9850" if (i >= 6 and e <= 4) else "#fdae61" if i >= 5 else "#999999"
        ax.scatter(e, i, s=140, color=col, edgecolor="k", zorder=3)
        ax.annotate(g[:44], (e, i), fontsize=7, xytext=(5, 3), textcoords="offset points")
    ax.axvspan(0, 4.5, ymin=0.55, alpha=.06, color="green")
    ax.text(2.2, 9.4, "DO NEXT\n(high impact, low effort)", color="#1a9850", ha="center", fontweight="bold", fontsize=11)
    ax.text(8, 9.4, "big projects", color="#555", ha="center", fontsize=10)
    ax.set_xlabel("effort to fix  →", fontsize=11); ax.set_ylabel("impact  →", fontsize=11)
    ax.set_title("Gap-priority map — what to fix next (top-left = quick wins)", fontsize=12)
    ax.set_xlim(0, 10.5); ax.set_ylim(2, 10.5)
    plt.tight_layout(); plt.savefig(REP / "project_retrospective.png", dpi=150, bbox_inches="tight")
    print("\n".join(L))
    print("\nwrote reports/project_retrospective.{md,png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
