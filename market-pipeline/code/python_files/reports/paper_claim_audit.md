# Auditing the prior paper's claims — which hold up, and on what data?

The working paper's own thesis is **measurement quality > data quantity: honest re-measurement turns nulls into real results.** We audit each claim for *auditability* (can it be reproducibly checked?) and cross-check it against THIS session's deeper, point-in-time data.

| claim | paper's number | data basis | auditable | our cross-check |
|---|---|---|:--:|---|
| **H4 Liquidity premium** | +4.24%/qtr, t=2.16 (10y Fama-MacBeth, US) | 10y PIT US | 🟢 high | CONFIRMED — our cost/capacity study independently finds the edge IS illiquidity (LARGE∩ILLIQ strongest). Most auditable claim in the paper. |
| **H3 PEAD w/ real filing dates** | IC 0.010→0.102 (10×); US≈0, Brazil +0.24 | PIT EDGAR dates | 🟢 high | CONFIRMED + REFINED — our US PEAD is modest (+1.05%) and concentrates in high-uncertainty/less-efficient SECTORS (biotech/tech), the same 'inefficient pocket' logic; metric differs (IC vs event drift). |
| **H2 Accumulation (OBV/CMF)** | +10.8%/6M top-minus-bottom, monotone (1.0) | volume, PIT | 🟢 high | AUDITABLE but NOT re-tested this session — volume-accumulation was outside our factor set. Verifiable from OHLCV; open item. |
| **H1 Quality (QMJ) loadings** | value −0.88, momentum +0.36 (vs real FF factors) | FF factors + snapshot fund. | 🟡 partial | DIRECTIONALLY CONFIRMED — we find quality is 'expensive not cheap' and travels with momentum; the FF loadings are re-checkable, but the quality basket rests on snapshot fundamentals. |
| **Method: PIT + 102 CI checks** | reproducible, integrity-verified, commit-signed | code | 🟢 high | STRONG — this session runs the same discipline (sufficiency gate, DSR, non-overlap t) and extends it; the reproducibility apparatus is the point. |
| **Data ceiling: snapshot fundamentals** | ~731 firms, ~40/market, CURRENT values (ex-US) | current snapshot | 🔴 limited | THE KEY LIMIT — the paper honestly flags it (C1). THIS SESSION FIXED IT: deep PIT fundamentals collected (JP EDINET 2011-24, CN baostock+pubDate 10y, KR DART) — snapshot-limited claims are now properly auditable. |

## The audit verdict

1. **Most auditable & independently confirmed: H4 (liquidity premium).** It rests on the *only* deep (10-year, PIT) sample in the paper, clears t>2, and our own cost/capacity study re-found it from scratch. This is the paper's most trustworthy result.
2. **H3 (PEAD) confirmed and refined.** The paper's 'drift lives in less-efficient markets, ≈0 in the US' becomes, at the sector level this session, 'drift lives in the less-efficient (high-uncertainty/speculative) *pockets* — biotech/tech — even within the US.' Same mechanism, finer cut. (Note: IC vs event-window drift are different estimators.)
3. **H1 (quality) directionally confirmed** — quality is expensive + momentum-like, exactly as we find; the FF loadings are re-checkable.
4. **H2 (accumulation) is auditable but we have not re-run it** — an honest open item.
5. **The paper's honesty is its strength.** It flags its own ceiling — fundamentals outside the US/liquidity test are a *current snapshot*, so those cross-sectional sizes are 'direction right, magnitude rough.' That is precisely the auditability limit.

## The meta-finding — this session IS the paper's thesis, executed

The paper argued that *nulls are often measurement defects, not absent effects*, and that the fix is better dating / longer samples / finer cuts — **not more data**. This session is a live demonstration: **Japan's value effect was an underpowered null on shallow (snapshot/J-Quants) data and became +6.6%/6M, t 4.84 once deep EDINET history was added.** China's null *survived* the same treatment (1,993 stocks × 10y, PIT) — proving the guard cuts both ways. We didn't just audit the paper; we **extended its auditability** by collecting the deep point-in-time fundamentals it lacked. Same research program, one version later.

> Verdicts reference the prior paper's committed figures and this session's committed backtests (`valuation_reversion_*`, `data_sufficiency`, cost/capacity, PEAD). Research, not investment advice.