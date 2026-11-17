# Entropy / bond–equity linkage — literature check

Companion to `entropic_rc_test.md`, which is the computed result. This file records
what the surrounding literature says, and — importantly — the boundary of what our
test actually establishes.

## 1. Parker changed his own estimator after the 2017 paper

The paper we replicated is Parker (2017), *Entropy* **19**, 292. His later work
([Parker 2020, *Entropy* 22, 1058](https://pmc.ncbi.nlm.nih.gov/articles/PMC7513185/);
[SSRN 3309694](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3309694)) uses a
**different estimation procedure**: maturities from 1-month to 30-year rather than the
five short ones, and solving for **σ** (the computational-error term) using the 3-month
timescale, rather than solving for R with σ fixed at 1.

Two things follow, and they cut in opposite directions:

- **It strengthens the diagnosis.** The 2020 paper does **not** report negative R/C
  values at all. Its trigger conditions are R/C in a *bounded* region near 1.0 —
  "R/C < 1.02" and "R/C < 1.065" — with the qualitative rule that "when R/C nears its
  minimum, the variance of R/C peaks." The −56.78 and −24.35 crisis means in the 2017
  Table 2 are therefore anomalous by the author's own later standards, and appear not
  to have been carried forward.
- **It bounds our claim.** We tested the 2017 specification, and our reconstruction is
  demonstrably faithful to it (bull zones I and V reproduce his published numbers to
  ~2 decimal places). We have **not** tested the 2020 σ-solving variant. Nothing here
  refutes that version; it was not run.

## 2. The bond↔equity transfer-entropy literature does not say what the popular summaries say

The widely-circulated claim is that equity markets lead in normal times, bonds take
over during turbulence, and entropy spikes across both in a crisis. The actual
empirical work is more equivocal:

- Applying effective and Rényi transfer entropy to G7 government bonds and equities,
  flow is **dynamic and state-dependent** in both magnitude and direction, and for the
  US the flow in either direction is **stronger in normal markets than in bear or bull
  tail states** — the opposite of "the barrier breaks down in a crisis."
  ([ResearchGate](https://www.researchgate.net/publication/367286972_Does_the_dynamics_between_government_bond_and_equity_markets_validate_the_adaptive_market_hypothesis_evidence_from_transfer_entropy))
- Method caveat that matters more than the findings: Jizba, Lavička & Tabachová
  (*Entropy* 2022, 24, 855, in the volume supplied) show Rényi TE recovers coupling
  **direction only below the onset of synchronisation**. Markets synchronise in
  crises, which is exactly the regime where the direction question is interesting.
  Any "bonds led equities in 2008" claim from TE needs to clear this bar first.

## 3. Crisis entropy goes DOWN, not up — repeatedly confirmed

The single most commonly repeated error in the popular summaries. For equity indices
measured by sequential-regularity entropy, crises make markets **more** regular:

- Olbryś & Majewska (*Entropy* 2022, 24, 921): 36 European + US indices, GFC and
  COVID, SampEn **decreases** during both turbulences; statistically significant, and
  homogeneous across developed and emerging markets.
  ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9318915/))
- They note this agrees with prior work — Ortiz-Cruz et al. (crude oil, multi-scale
  ApEn), Wang & Wang (S&P 500 during COVID), Risso (indices during crashes) — all
  finding entropy falling in downturns.

**The reconciliation:** these are different quantities. Shannon entropy of the return
*distribution* rises in a crisis (returns disperse). Sequential entropy (SampEn/ApEn)
*falls*, because sustained trends repeat patterns. Summaries that say "entropy spikes
in a crisis" conflate the two. Any entropy feature built here must state which one it
is measuring.

## 4. What this implies for our own test

Our finding — Var(R/C) is dominated by the plain 10Y–3M term spread, and correlates
+0.82 with it — is consistent with the broader pattern that entropy-derived yield-curve
quantities tend to be reparameterisations of the term structure rather than new
information. The literature that finds genuine incremental signal is the
**transfer-entropy-on-returns** strand, not the entropic-yield-curve strand.

## Sources

- [Parker 2020, Information Processing and Absorption Ratios (Entropy)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7513185/)
- [Parker, R/C and Fractal Zooming (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3309694)
- [Bond–equity dynamics and the adaptive market hypothesis via transfer entropy](https://www.researchgate.net/publication/367286972_Does_the_dynamics_between_government_bond_and_equity_markets_validate_the_adaptive_market_hypothesis_evidence_from_transfer_entropy)
- [Effective transfer entropy in credit markets (Springer)](https://link.springer.com/article/10.1007/s10260-021-00614-1)
- [Olbryś & Majewska, Regularity in Stock Market Indices within Turbulence Periods](https://pmc.ncbi.nlm.nih.gov/articles/PMC9318915/)
- [Entropy as a Tool for Analysis of Stock Market Efficiency During Crisis](https://pmc.ncbi.nlm.nih.gov/articles/PMC11675851/)
- [An entropy-based early warning indicator for systemic risk](https://www.sciencedirect.com/science/article/abs/pii/S1042443116300476)
