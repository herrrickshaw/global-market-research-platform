#!/usr/bin/env python3
"""
paper_claim_audit.py — audit the claims in the prior working paper ("A Reproducible
Multi-Market Equity-Factor Platform", v2.0, Global Market Scanners) for AUDITABILITY:
can each claim be independently re-verified, on what data, and does THIS session's newer
(deeper, point-in-time) data confirm, refine, or extend it?

Two axes:
  auditability (0-10): how reproducibly can the claim be checked? high = long PIT sample +
    committed code; low = rests on a current-snapshot of fundamentals (no history).
  confirmation (0-10): does this session's independent work support it? high = we re-found
    it on better data; low = untested by us.

Output: reports/paper_claim_audit.{md,png}
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

REP = Path(__file__).resolve().parent / "reports"

# (claim, paper number, data basis, auditability, confirmation, our-session cross-check)
C = [
 ("H4 Liquidity premium", "+4.24%/qtr, t=2.16 (10y Fama-MacBeth, US)", "10y PIT US", 9, 9,
  "CONFIRMED — our cost/capacity study independently finds the edge IS illiquidity (LARGE∩ILLIQ strongest). Most auditable claim in the paper."),
 ("H3 PEAD w/ real filing dates", "IC 0.010→0.102 (10×); US≈0, Brazil +0.24", "PIT EDGAR dates", 8, 8,
  "CONFIRMED + REFINED — our US PEAD is modest (+1.05%) and concentrates in high-uncertainty/less-efficient SECTORS (biotech/tech), the same 'inefficient pocket' logic; metric differs (IC vs event drift)."),
 ("H2 Accumulation (OBV/CMF)", "+10.8%/6M top-minus-bottom, monotone (1.0)", "volume, PIT", 8, 4,
  "AUDITABLE but NOT re-tested this session — volume-accumulation was outside our factor set. Verifiable from OHLCV; open item."),
 ("H1 Quality (QMJ) loadings", "value −0.88, momentum +0.36 (vs real FF factors)", "FF factors + snapshot fund.", 6, 8,
  "DIRECTIONALLY CONFIRMED — we find quality is 'expensive not cheap' and travels with momentum; the FF loadings are re-checkable, but the quality basket rests on snapshot fundamentals."),
 ("Method: PIT + 102 CI checks", "reproducible, integrity-verified, commit-signed", "code", 10, 9,
  "STRONG — this session runs the same discipline (sufficiency gate, DSR, non-overlap t) and extends it; the reproducibility apparatus is the point."),
 ("Data ceiling: snapshot fundamentals", "~731 firms, ~40/market, CURRENT values (ex-US)", "current snapshot", 3, 10,
  "THE KEY LIMIT — the paper honestly flags it (C1). THIS SESSION FIXED IT: deep PIT fundamentals collected (JP EDINET 2011-24, CN baostock+pubDate 10y, KR DART) — snapshot-limited claims are now properly auditable."),
]


def main() -> int:
    d = pd.DataFrame(C, columns=["claim", "number", "basis", "auditability", "confirmation", "note"])
    L = ["# Auditing the prior paper's claims — which hold up, and on what data?", "",
         "The working paper's own thesis is **measurement quality > data quantity: honest "
         "re-measurement turns nulls into real results.** We audit each claim for *auditability* "
         "(can it be reproducibly checked?) and cross-check it against THIS session's deeper, "
         "point-in-time data.", "",
         "| claim | paper's number | data basis | auditable | our cross-check |",
         "|---|---|---|:--:|---|"]
    rate = lambda s: "🟢 high" if s >= 7 else "🟡 partial" if s >= 4 else "🔴 limited"
    for _, r in d.iterrows():
        L.append(f"| **{r.claim}** | {r.number} | {r.basis} | {rate(r.auditability)} | {r.note} |")
    L += ["", "## The audit verdict", "",
          "1. **Most auditable & independently confirmed: H4 (liquidity premium).** It rests on the "
          "*only* deep (10-year, PIT) sample in the paper, clears t>2, and our own cost/capacity "
          "study re-found it from scratch. This is the paper's most trustworthy result.",
          "2. **H3 (PEAD) confirmed and refined.** The paper's 'drift lives in less-efficient markets, "
          "≈0 in the US' becomes, at the sector level this session, 'drift lives in the less-efficient "
          "(high-uncertainty/speculative) *pockets* — biotech/tech — even within the US.' Same "
          "mechanism, finer cut. (Note: IC vs event-window drift are different estimators.)",
          "3. **H1 (quality) directionally confirmed** — quality is expensive + momentum-like, exactly "
          "as we find; the FF loadings are re-checkable.",
          "4. **H2 (accumulation) is auditable but we have not re-run it** — an honest open item.",
          "5. **The paper's honesty is its strength.** It flags its own ceiling — fundamentals outside "
          "the US/liquidity test are a *current snapshot*, so those cross-sectional sizes are "
          "'direction right, magnitude rough.' That is precisely the auditability limit.", "",
          "## The meta-finding — this session IS the paper's thesis, executed", "",
          "The paper argued that *nulls are often measurement defects, not absent effects*, and that "
          "the fix is better dating / longer samples / finer cuts — **not more data**. This session is "
          "a live demonstration: **Japan's value effect was an underpowered null on shallow "
          "(snapshot/J-Quants) data and became +6.6%/6M, t 4.84 once deep EDINET history was added.** "
          "China's null *survived* the same treatment (1,993 stocks × 10y, PIT) — proving the guard "
          "cuts both ways. We didn't just audit the paper; we **extended its auditability** by "
          "collecting the deep point-in-time fundamentals it lacked. Same research program, one "
          "version later.", "",
          "> Verdicts reference the prior paper's committed figures and this session's committed "
          "backtests (`valuation_reversion_*`, `data_sufficiency`, cost/capacity, PEAD). Research, "
          "not investment advice."]
    (REP / "paper_claim_audit.md").write_text("\n".join(L))

    # viz — auditability × confirmation map
    fig, ax = plt.subplots(figsize=(12, 7.5))
    for _, r in d.iterrows():
        ax.scatter(r.auditability, r.confirmation, s=200, edgecolor="k", zorder=3,
                   color="#1a9850" if min(r.auditability, r.confirmation) >= 7 else
                         "#fdae61" if min(r.auditability, r.confirmation) >= 4 else "#d73027")
        ax.annotate(r.claim, (r.auditability, r.confirmation), fontsize=8.5,
                    xytext=(6, 4), textcoords="offset points")
    ax.axvline(6.5, ls="--", c="grey", alpha=.5); ax.axhline(6.5, ls="--", c="grey", alpha=.5)
    ax.text(8.5, 9.7, "TRUSTWORTHY\n(auditable + confirmed)", color="#1a9850", ha="center", fontweight="bold", fontsize=11)
    ax.text(1.8, 9.7, "confirmed but\nsnapshot-limited", color="#e08214", ha="center", fontsize=9.5)
    ax.text(8.5, 2.2, "auditable,\nnot yet re-run", color="#555", ha="center", fontsize=9.5)
    ax.set_xlabel("Auditability  →  (reproducible check on deep PIT data)", fontsize=11)
    ax.set_ylabel("Confirmation by this session  →", fontsize=11)
    ax.set_title("Auditing the prior paper's claims: which are reproducibly verifiable, and does new data confirm them?",
                 fontsize=11.5)
    ax.set_xlim(0, 11); ax.set_ylim(0, 11)
    plt.tight_layout(); plt.savefig(REP / "paper_claim_audit.png", dpi=150, bbox_inches="tight")
    print("\n".join(L))
    print("\nwrote reports/paper_claim_audit.{md,png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
