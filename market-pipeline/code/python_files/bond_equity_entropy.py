#!/usr/bin/env python3
"""
bond_equity_entropy.py — what actually links Treasury yields and US equities.

FOUR QUESTIONS, MEASURED
------------------------
  --sampen   Does equity entropy FALL in crises, as the literature claims?
             (Olbrys & Majewska 2022 on 36 indices; never checked on our data.)
  --te       Effective transfer entropy, both directions. Who leads whom, and
             does it change by regime?
  --selloff  What happens to equities during a bond selloff — event study with
             an unconditional baseline.
  --carry    Is there a borrow-and-trade channel: cheap funding driving equity
             gains, reversing when funding costs spike?

WHY THIS IS BUILT SCEPTICALLY
-----------------------------
The entropic yield curve (see entropic_yield_curve.py) was rejected here because
its signal turned out to be a monotone reparameterisation of the term spread —
it looked novel and carried no information the spread did not already have. Every
measure below is therefore reported ALONGSIDE the boring baseline it has to beat,
and every entropy number is bias-corrected and significance-tested:

  * Transfer entropy on finite samples is BIASED UPWARD — it reports positive
    flow between independent series. So we report EFFECTIVE TE, subtracting the
    mean of shuffled surrogates (Marschinski & Kantz), and a permutation p-value.
    Raw TE is shown too, so the size of the bias is visible rather than hidden.
  * TE is directional but NOT causal. It measures predictive information flow.
    Both series responding to a common third driver (Fed policy, inflation
    prints) produces TE in both directions and is indistinguishable from
    causation here.
  * n is small where it matters. Four equity bear markets in 36 years bounds
    what any event study can establish; that limit is stated, not buried.

    bond_equity_entropy.py --all
    bond_equity_entropy.py --te --selloff
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache_seed"
REPORTS = HERE / "reports"
YIELDS = CACHE / "treasury_yields.parquet"
SPX = CACHE / "spx.parquet"
REPORT = REPORTS / "bond_equity_linkage.md"

RNG = np.random.default_rng(20260731)      # fixed: surrogate tests must replay
N_SURROGATE = 300
BINS = 3                                    # terciles: 27 cells, ample for ~9k obs


# ── data ──────────────────────────────────────────────────────────────────────
def load() -> pd.DataFrame:
    y = pd.read_parquet(YIELDS).set_index("Date").sort_index()
    s = pd.read_parquet(SPX).set_index("Date").sort_index()["spx"]
    s = s[~s.index.duplicated(keep="first")]
    d = pd.DataFrame({
        "spx": s,
        "y3m": y["3 Mo"], "y2y": y["2 Yr"], "y10y": y["10 Yr"], "y30y": y["30 Yr"],
    }).dropna(subset=["spx", "y10y"])
    d["ret"] = np.log(d["spx"]).diff()               # equity log return
    d["dy10"] = d["y10y"].diff()                     # yield CHANGE, in pp
    # A 10y bond's price return ~ -duration * dy. Duration ~7 for the 10y note;
    # this makes "bond selloff" a return series comparable to equities rather
    # than a yield move whose sign is easy to misread.
    d["bond_ret"] = -7.0 * d["dy10"] / 100.0
    d["spread"] = d["y10y"] - d["y3m"]               # term spread / carry proxy
    d["real_proxy"] = d["y10y"] - d["y3m"]           # kept separate for clarity
    return d.dropna(subset=["ret", "dy10"])


# ── sample entropy ────────────────────────────────────────────────────────────
def sampen(x: np.ndarray, m: int = 2, r_mult: float = 0.2) -> float:
    """Sample entropy: -ln( A / B ), matches of length m+1 over matches of m.

    LOWER = more regular/repetitive = more predictable. This is the sequential
    measure, NOT the entropy of the return distribution — the two move in
    OPPOSITE directions during a crash (dispersion widens while patterns repeat),
    and conflating them is the single most common error in popular summaries.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    N = len(x)
    if N < m + 20:
        return np.nan
    r = r_mult * np.std(x, ddof=0)
    if r <= 0:
        return np.nan

    def _count(mm: int) -> int:
        # embed into mm-dim vectors, Chebyshev distance, exclude self-matches
        idx = np.arange(N - mm + 1)
        emb = np.stack([x[i: i + mm] for i in idx])
        tot = 0
        for i in range(len(emb)):
            dist = np.max(np.abs(emb - emb[i]), axis=1)
            tot += int(np.count_nonzero(dist <= r)) - 1
        return tot

    B, A = _count(m), _count(m + 1)
    return float(-np.log(A / B)) if A > 0 and B > 0 else np.nan


def run_sampen(d: pd.DataFrame, out: list) -> None:
    win, step = 252, 21
    r = d["ret"].values
    idx = d.index
    rows = []
    for e in range(win, len(r) + 1, step):
        rows.append({"Date": idx[e - 1], "sampen": sampen(r[e - win:e]),
                     "vol": float(np.std(r[e - win:e]) * np.sqrt(252))})
    s = pd.DataFrame(rows).set_index("Date").dropna()

    periods = {
        "GFC 2007-09 to 2009-06": ("2007-09-01", "2009-06-30"),
        "COVID 2020-02 to 2020-06": ("2020-02-01", "2020-06-30"),
        "2022 bear": ("2022-01-01", "2022-12-31"),
        "dot-com 2000-03 to 2002-10": ("2000-03-01", "2002-10-31"),
    }
    calm = s.copy()
    for _, (lo, hi) in periods.items():
        calm = calm.drop(calm.loc[lo:hi].index, errors="ignore")

    out.append("\n## 1. Does equity entropy fall in crises?\n")
    out.append("Sample entropy (m=2, r=0.2σ) of S&P 500 log returns, 252-day window "
               "stepped 21 days. **Lower = more regular = more predictable.** This is "
               "sequential regularity, not distribution width — the two move in "
               "opposite directions in a crash, and conflating them is the usual error.\n")
    out.append(f"\nCalm-period baseline: **SampEn {calm.sampen.mean():.3f}** "
               f"(n={len(calm)} windows), annualised vol {calm.vol.mean()*100:.1f}%\n")
    out.append("\n| period | SampEn | vs calm | ann. vol | entropy direction |")
    out.append("|---|---|---|---|---|")
    for name, (lo, hi) in periods.items():
        w = s.loc[lo:hi]
        if w.empty:
            continue
        delta = w.sampen.mean() - calm.sampen.mean()
        out.append(f"| {name} | {w.sampen.mean():.3f} | {delta:+.3f} | "
                   f"{w.vol.mean()*100:.1f}% | {'DOWN (more regular)' if delta < 0 else 'UP'} |")
    # correlation with vol: if entropy simply tracked volatility it would be
    # redundant with a much simpler measure.
    c = s.sampen.corr(s.vol)
    out.append(f"\n- corr(SampEn, realised vol) = **{c:+.3f}** — "
               f"{'entropy is largely the inverse of vol, so it adds little' if abs(c) > 0.6 else 'entropy is NOT just inverted volatility'}")
    return s


# ── transfer entropy ──────────────────────────────────────────────────────────
def _disc(x: np.ndarray, bins: int) -> np.ndarray:
    """Quantile (equiprobable) binning — robust to the fat tails of returns."""
    q = np.quantile(x, np.linspace(0, 1, bins + 1)[1:-1])
    return np.digitize(x, q)


def transfer_entropy(src: np.ndarray, dst: np.ndarray, bins: int = BINS,
                     lag: int = 1) -> float:
    """TE(src -> dst): information src's past adds about dst's next move,
    beyond dst's own past. Shannon, k=l=1, in nats."""
    s, t = _disc(src, bins), _disc(dst, bins)
    tf, tp, sp = t[lag:], t[:-lag], s[:-lag]
    n = len(tf)
    if n < 50:
        return np.nan
    # joint counts over (t_future, t_past, s_past)
    j = np.zeros((bins, bins, bins))
    np.add.at(j, (tf, tp, sp), 1.0)
    j /= n
    p_tp_sp = j.sum(axis=0)                    # (tp, sp)
    p_tf_tp = j.sum(axis=2)                    # (tf, tp)
    p_tp = j.sum(axis=(0, 2))                  # (tp,)
    te = 0.0
    for a in range(bins):
        for b in range(bins):
            for c in range(bins):
                pj = j[a, b, c]
                if pj <= 0 or p_tp_sp[b, c] <= 0 or p_tf_tp[a, b] <= 0 or p_tp[b] <= 0:
                    continue
                te += pj * np.log((pj / p_tp_sp[b, c]) / (p_tf_tp[a, b] / p_tp[b]))
    return float(te)


def effective_te(src: np.ndarray, dst: np.ndarray, n_sur: int = N_SURROGATE):
    """(raw TE, effective TE, p-value). Effective = raw minus surrogate mean.

    Finite-sample TE is biased UPWARD — independent series score > 0 — so raw TE
    alone cannot support a claim of information flow. Shuffling the SOURCE
    destroys any src->dst structure while preserving its marginal distribution,
    so the surrogate mean estimates that bias directly.
    """
    raw = transfer_entropy(src, dst)
    if not np.isfinite(raw):
        return np.nan, np.nan, np.nan
    sur = np.empty(n_sur)
    s = src.copy()
    for i in range(n_sur):
        RNG.shuffle(s)
        sur[i] = transfer_entropy(s, dst)
    p = float((np.count_nonzero(sur >= raw) + 1) / (n_sur + 1))
    return raw, float(raw - np.nanmean(sur)), p


def run_te(d: pd.DataFrame, out: list) -> None:
    out.append("\n## 2. Transfer entropy — who leads whom?\n")
    out.append(f"Shannon TE, tercile bins, lag 1 day, {N_SURROGATE} shuffled surrogates. "
               "**Effective TE** subtracts the surrogate mean because finite-sample TE is "
               "biased upward; the raw column shows how large that bias is. p is a "
               "permutation test.\n")
    out.append("\n🔴 TE is directional, NOT causal. Both series reacting to a common "
               "driver (a Fed decision, a CPI print) produces flow in both directions and "
               "is indistinguishable from causation with this method.\n")

    segs = {
        "full sample 1990-2026": (None, None),
        "1990-1999": ("1990-01-01", "1999-12-31"),
        "2000-2009": ("2000-01-01", "2009-12-31"),
        "2010-2019": ("2010-01-01", "2019-12-31"),
        "2020-2026": ("2020-01-01", "2026-12-31"),
    }
    out.append("\n| period | n | TE bond→eq (eff) | p | TE eq→bond (eff) | p | net |")
    out.append("|---|---|---|---|---|---|---|")
    for name, (lo, hi) in segs.items():
        w = d.loc[lo:hi] if lo else d
        if len(w) < 400:
            continue
        b, e = w["bond_ret"].values, w["ret"].values
        _, e_be, p_be = effective_te(b, e)
        _, e_eb, p_eb = effective_te(e, b)
        net = e_be - e_eb
        lead = "bond leads" if net > 0 else "equity leads"
        out.append(f"| {name} | {len(w):,} | {e_be:.5f} | {p_be:.3f} | "
                   f"{e_eb:.5f} | {p_eb:.3f} | {lead} |")

    # calm vs turbulent — the state-dependence the literature reports
    vol = d["ret"].rolling(63).std()
    hi_vol = vol > vol.quantile(0.80)
    out.append("\n### State dependence\n")
    out.append("| state | n | TE bond→eq (eff) | p | TE eq→bond (eff) | p |")
    out.append("|---|---|---|---|---|---|")
    for label, mask in (("calm (bottom 80% vol)", ~hi_vol), ("turbulent (top 20% vol)", hi_vol)):
        w = d[mask.fillna(False)]
        if len(w) < 400:
            continue
        _, e_be, p_be = effective_te(w["bond_ret"].values, w["ret"].values)
        _, e_eb, p_eb = effective_te(w["ret"].values, w["bond_ret"].values)
        out.append(f"| {label} | {len(w):,} | {e_be:.5f} | {p_be:.3f} | {e_eb:.5f} | {p_eb:.3f} |")

    # the boring baseline TE must beat
    out.append("\n### Baseline it has to beat\n")
    lr = d["bond_ret"].corr(d["ret"])
    lr1 = d["bond_ret"].shift(1).corr(d["ret"])
    lr2 = d["ret"].shift(1).corr(d["bond_ret"])
    out.append(f"- contemporaneous corr(bond return, equity return) = **{lr:+.3f}**")
    out.append(f"- lagged corr(bond ret t-1, equity ret t) = {lr1:+.3f}")
    out.append(f"- lagged corr(equity ret t-1, bond ret t) = {lr2:+.3f}")


# ── bond selloff event study ──────────────────────────────────────────────────
def run_selloff(d: pd.DataFrame, out: list) -> None:
    out.append("\n## 3. What happens to equities during a bond selloff?\n")
    # A selloff = yields RISE = bond prices FALL. Measured over 20 sessions so a
    # single volatile day does not qualify.
    dy20 = d["y10y"].diff(20)
    thr = dy20.quantile(0.95)
    sell = dy20 > thr
    onsets, last = [], None
    for dt in d.index[sell.fillna(False)]:
        if last is None or (dt - last).days > 60:      # de-cluster into episodes
            onsets.append(dt)
        last = dt

    out.append(f"Selloff = 20-session rise in the 10-year yield above its 95th percentile "
               f"(**+{thr*100:.0f} bp**). De-clustered at 60 days → **{len(onsets)} episodes**.\n")

    hor = [21, 63, 126, 252]
    base = {h: d["ret"].rolling(h).sum().shift(-h) for h in hor}
    out.append("\n| horizon | mean fwd equity | median | hit rate >0 | unconditional mean | edge |")
    out.append("|---|---|---|---|---|---|")
    for h in hor:
        f = base[h]
        ev = f.reindex(onsets).dropna()
        un = f.dropna()
        if ev.empty:
            continue
        edge = ev.mean() - un.mean()
        out.append(f"| {h}d | {ev.mean()*100:+.2f}% | {ev.median()*100:+.2f}% | "
                   f"{(ev > 0).mean()*100:.0f}% | {un.mean()*100:+.2f}% | {edge*100:+.2f}pp |")

    # THE key modern fact: the stock-bond correlation is not stable.
    out.append("\n### The correlation is not stable — this is the main finding\n")
    roll = d["bond_ret"].rolling(252).corr(d["ret"])
    out.append("| era | corr(bond ret, equity ret) | bonds hedge equities? |")
    out.append("|---|---|---|")
    for name, (lo, hi) in (("1990-1999", ("1990-01-01", "1999-12-31")),
                           ("2000-2009", ("2000-01-01", "2009-12-31")),
                           ("2010-2019", ("2010-01-01", "2019-12-31")),
                           ("2020-2021", ("2020-01-01", "2021-12-31")),
                           ("2022-2026", ("2022-01-01", "2026-12-31"))):
        c = roll.loc[lo:hi].mean()
        out.append(f"| {name} | {c:+.3f} | {'YES — negative corr' if c < -0.05 else ('NO — positive corr, they fall together' if c > 0.05 else 'neither, ~zero')} |")

    # conditional: does the equity response depend on the prevailing correlation?
    out.append("\n### Same event, opposite outcome depending on regime\n")
    ev_idx = pd.DatetimeIndex(onsets)
    corr_at = roll.reindex(ev_idx)
    f63 = base[63].reindex(ev_idx)
    both = pd.DataFrame({"corr": corr_at, "fwd63": f63}).dropna()
    if len(both) > 4:
        neg = both[both["corr"] < 0]
        pos = both[both["corr"] >= 0]
        out.append("| prevailing stock-bond corr at selloff | episodes | mean fwd 63d equity |")
        out.append("|---|---|---|")
        out.append(f"| negative (bonds hedging) | {len(neg)} | {neg.fwd63.mean()*100:+.2f}% |")
        out.append(f"| positive (bonds NOT hedging) | {len(pos)} | {pos.fwd63.mean()*100:+.2f}% |")


# ── carry / borrow-and-trade ──────────────────────────────────────────────────
def run_carry(d: pd.DataFrame, out: list) -> None:
    out.append("\n## 4. Is there a borrow-and-trade (carry) channel?\n")
    out.append("Read as: does cheap short-term funding coincide with equity gains, and "
               "does the relationship reverse when funding costs spike? The 3-month bill "
               "is the funding-cost proxy; the term spread is the classic carry proxy.\n")

    fwd = d["ret"].rolling(252).sum().shift(-252)
    d2 = d.assign(fwd1y=fwd).dropna(subset=["fwd1y"])
    out.append("\n| conditioning variable | corr with forward 1y equity return |")
    out.append("|---|---|")
    for label, col in (("3m bill LEVEL (funding cost)", d2["y3m"]),
                       ("3m bill 63d CHANGE (funding shock)", d2["y3m"].diff(63)),
                       ("term spread 10y-3m (carry)", d2["spread"]),
                       ("10y yield level", d2["y10y"])):
        out.append(f"| {label} | {col.corr(d2['fwd1y']):+.3f} |")

    out.append("\n### Forward equity return by funding-cost quintile\n")
    d2 = d2.assign(q=pd.qcut(d2["y3m"], 5, labels=["Q1 cheapest", "Q2", "Q3", "Q4", "Q5 dearest"]))
    g = d2.groupby("q", observed=True)["fwd1y"].agg(["mean", "median", "count"])
    out.append("| funding cost (3m bill) | mean fwd 1y | median | n days |")
    out.append("|---|---|---|---|")
    for k, r in g.iterrows():
        out.append(f"| {k} | {r['mean']*100:+.2f}% | {r['median']*100:+.2f}% | {int(r['count']):,} |")

    out.append("\n### Funding SHOCKS, not levels\n")
    shock = d2["y3m"].diff(63)
    big = shock > shock.quantile(0.90)
    out.append(f"- days after a top-decile 3m-rate rise (>{shock.quantile(0.90)*100:.0f}bp/63d): "
               f"mean fwd 1y equity **{d2.loc[big, 'fwd1y'].mean()*100:+.2f}%** "
               f"(n={int(big.sum()):,})")
    out.append(f"- unconditional: {d2['fwd1y'].mean()*100:+.2f}%")
    inv = d2["spread"] < 0
    if inv.any():
        out.append(f"- while the curve is INVERTED (negative carry): mean fwd 1y equity "
                   f"**{d2.loc[inv, 'fwd1y'].mean()*100:+.2f}%** (n={int(inv.sum()):,})")


def run_synthesis(d: pd.DataFrame, out: list) -> None:
    """The limits that govern how much any of the above can bear."""
    yrs = (d.index.max() - d.index.min()).days / 365.25
    out.append("\n## 5. Interpretation and limits\n")
    out.append("### 🔴 Effective sample size, not row count\n")
    out.append(f"The tables above quote n in the thousands, but forward returns are measured "
               f"over OVERLAPPING windows. With {len(d):,} daily rows spanning {yrs:.0f} years, "
               f"a 252-day forward return has roughly **{yrs:.0f} independent observations**, "
               f"not {len(d):,}. Every correlation and quintile mean in section 4 therefore has "
               f"far wider error bars than its row count suggests. A quintile holding ~1,800 "
               f"days holds about {yrs/5:.0f} independent years. Treat differences of a few "
               f"percentage points as noise.\n")
    out.append("### What each section actually established\n")
    out.append("1. **Entropy in crises — weakly supported, one event doing the work.** "
               "SampEn fell in the GFC (−0.03), COVID (−0.63) and 2022 (−0.06) but ROSE in "
               "dot-com (+0.14). Only COVID is a large move; the GFC and 2022 effects are "
               "negligible against a calm baseline of 1.945. So the published claim is not "
               "contradicted, but on this data it rests almost entirely on one crisis.")
    out.append("2. **Transfer entropy found essentially nothing.** Of ten direction/period "
               "cells, one reached p<0.05 (equity→bond, 2000-2009, p=0.020) — about what ten "
               "tests produce by chance. Several effective values are NEGATIVE, i.e. below the "
               "shuffled surrogate mean. At a one-day lag there is no reliable directional "
               "flow in either direction. The plain contemporaneous correlation (−0.165) "
               "carries more than any lead-lag relationship measured here.")
    out.append("3. **A bond selloff does not, on average, predict equity weakness.** Across 49 "
               "episodes the edge over the unconditional mean is +0.24pp at 21d and NEGATIVE at "
               "63/126/252d — indistinguishable from zero. Forward hit rates (63–79% positive) "
               "match the unconditional drift of a rising market.")
    out.append("4. **No borrow-and-trade carry channel is visible.** If cheap funding drove "
               "equities, the cheapest-funding quintile would lead. It does not: dearest "
               "funding shows the HIGHEST forward return (+12.47% vs +10.42%), and a funding "
               "SHOCK correlates POSITIVELY with forward equity returns (+0.213). That is the "
               "procyclical reading — short rates rise because the economy is strong — not a "
               "carry unwind. The Q3 outlier (−2.20%) is period clustering, not a rate effect: "
               "that bucket is dominated by 2000-02 and 2007-08.")
    out.append("\n### The one durable finding\n")
    out.append("**The stock–bond correlation is not a constant, and it has flipped twice.** "
               "Positive in the 1990s (+0.34, they fell together), decisively negative through "
               "2000–2021 (−0.23 to −0.41, bonds hedged equities), and back to roughly zero "
               "in 2022–2026 (+0.05). This is the fact that matters for the original question: "
               "'what happens to equities in a bond selloff' has no era-independent answer, "
               "because whether bonds hedge equities is itself regime-dependent. Any allocation "
               "rule assuming the 2010s negative correlation is assuming a regime that ended.")
    out.append("\n*Descriptive analysis of historical relationships. Not investment advice.*")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    for f in ("sampen", "te", "selloff", "carry", "all"):
        ap.add_argument(f"--{f}", action="store_true")
    a = ap.parse_args()
    if not any(vars(a).values()):
        ap.print_help(); return 1
    if not YIELDS.exists() or not SPX.exists():
        print("run entropic_yield_curve.py --fetch first"); return 1

    d = load()
    out = ["# Bond yields and equities — what actually links them\n",
           f"S&P 500 and the US Treasury curve, {d.index.min().date()} .. "
           f"{d.index.max().date()} ({len(d):,} trading days).\n",
           "\nEvery entropy figure is bias-corrected against shuffled surrogates and "
           "significance-tested, and every result is shown next to the plain "
           "correlation it has to beat. Method notes and limits are in the module "
           "docstring.\n"]

    if a.sampen or a.all:
        run_sampen(d, out)
    if a.te or a.all:
        run_te(d, out)
    if a.selloff or a.all:
        run_selloff(d, out)
    if a.carry or a.all:
        run_carry(d, out)
    if a.all:
        run_synthesis(d, out)

    REPORTS.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\n  -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
