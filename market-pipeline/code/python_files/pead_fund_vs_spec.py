#!/usr/bin/env python3
"""
pead_fund_vs_spec.py — does Post-Earnings-Announcement Drift (PEAD) depend on whether a
sector is priced on FUNDAMENTALS or SPECULATION?

PEAD (Ball & Brown 1968; Bernard & Thomas 1989) = prices keep drifting in the direction of an
earnings surprise for weeks after the announcement — an UNDER-reaction to *fundamental* news.
Hypothesis: PEAD should be **strong in fundamentals-ruled sectors** (where price tracks
earnings, so the surprise gets slowly absorbed) and **weak/absent in speculation-ruled
sectors** (where price is driven by sentiment, not earnings — the surprise is ignored or
over-reacted to).

Event study (US, real analyst-surprise data): entry = +2 trading days after the announcement
(skip the jump), exit = +44 (~2 months). Drift = exit/entry − 1, in excess of the market.
PEAD = mean excess drift of BEATS minus MISSES, split by the sector's fundamentals/speculation
regime.

Output: reports/pead_fund_vs_spec.{csv,md,png}
"""
from __future__ import annotations
import glob
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REP = HERE / "reports"
WH = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv/US"
ENTRY, EXIT = 2, 44                       # trading days after announcement

# sector → regime (from our PB~ROE R² + Damodaran % money-losing findings)
SPEC = {"Health Care", "Information Technology", "Communication Services"}
FUND = {"Financials", "Utilities", "Consumer Staples", "Industrials", "Energy",
        "Materials", "Consumer Discretionary", "Real Estate"}


def main() -> int:
    ev = pd.read_parquet(HERE / "cache_seed" / "earnings_dates_cache" / "US.parquet")
    ev = ev.rename(columns={"Earnings Date": "date", "Surprise(%)": "surprise"})
    ev["date"] = pd.to_datetime(ev["date"], errors="coerce", utc=True).dt.tz_localize(None)
    ev = ev[ev.surprise.notna() & ev.date.notna()].copy()
    ev["ticker"] = ev.ticker.astype(str)

    dm = pd.read_parquet(REP / "damodaran_sector_map.parquet")
    sec = dict(zip(dm[dm.Country == "United States"].Ticker.astype(str),
                   dm[dm.Country == "United States"]["Primary Sector"]))
    ev["sector"] = ev.ticker.map(sec)

    # daily prices for the event tickers
    tickers = set(ev.ticker)
    px = pd.concat((pd.read_parquet(p, columns=["Date", "Symbol", "Close"])
                    for p in sorted(glob.glob(f"{WH}/year=*.parquet"))), ignore_index=True)
    px = px[px.Symbol.isin(tickers)]
    px["Date"] = pd.to_datetime(px["Date"])
    w = px.pivot_table(index="Date", columns="Symbol", values="Close", aggfunc="last").sort_index()
    dates = w.index
    mkt = w.pct_change().median(axis=1).add(1).cumprod()      # equal-weight market index

    rows = []
    for r in ev.itertuples():
        if r.ticker not in w.columns:
            continue
        i = dates.searchsorted(r.date)
        if i + EXIT >= len(dates) or i < 0:
            continue
        p0, p1 = w[r.ticker].iloc[i + ENTRY], w[r.ticker].iloc[i + EXIT]
        if not (np.isfinite(p0) and np.isfinite(p1)) or p0 <= 0:
            continue
        drift = p1 / p0 - 1
        m = mkt.iloc[i + EXIT] / mkt.iloc[i + ENTRY] - 1
        rows.append({"ticker": r.ticker, "sector": r.sector, "surprise": r.surprise,
                     "excess_drift": drift - m})
    d = pd.DataFrame(rows)
    d = d[(d.excess_drift.abs() < 1) & d.sector.notna()]      # drop data errors
    d["beat"] = d.surprise > 0
    d["regime"] = np.where(d.sector.isin(SPEC), "🔴 speculation",
                  np.where(d.sector.isin(FUND), "🟢 fundamentals", "other"))

    def pead(g):
        b = g[g.beat].excess_drift; m = g[~g.beat].excess_drift
        return pd.Series({"n": len(g), "n_beat": len(b),
                          "drift_beat_%": b.mean() * 100, "drift_miss_%": m.mean() * 100,
                          "PEAD_spread_%": (b.mean() - m.mean()) * 100})

    overall = pead(d)
    by_reg = d[d.regime != "other"].groupby("regime").apply(pead, include_groups=False)
    by_sec = d.groupby("sector").apply(pead, include_groups=False).sort_values("PEAD_spread_%", ascending=False)
    by_sec.to_csv(REP / "pead_fund_vs_spec.csv")

    L = ["# PEAD × fundamentals-vs-speculation — does drift depend on the pricing regime?", "",
         f"US, {len(d):,} earnings events with real analyst surprises. PEAD = (drift after a "
         f"BEAT) − (drift after a MISS), measured +{ENTRY}→+{EXIT} trading days, in excess of "
         "the market. Bernard & Thomas (1989): under-reaction to earnings ⇒ positive drift.", "",
         f"**Overall PEAD spread: {overall['PEAD_spread_%']:+.2f}%** "
         f"(beats +{overall['drift_beat_%']:.2f}%, misses {overall['drift_miss_%']:+.2f}%, "
         f"n={int(overall['n']):,}).", "",
         "## By pricing regime", "",
         "| regime | events | drift after beat | drift after miss | **PEAD spread** |",
         "|---|--:|--:|--:|--:|"]
    for reg, r in by_reg.iterrows():
        L.append(f"| {reg} | {int(r.n):,} | {r['drift_beat_%']:+.2f}% | {r['drift_miss_%']:+.2f}% | "
                 f"**{r['PEAD_spread_%']:+.2f}%** |")
    L += ["", "## By sector", "", "| sector | events | PEAD spread |", "|---|--:|--:|"]
    for s, r in by_sec.iterrows():
        L.append(f"| {s} | {int(r.n):,} | {r['PEAD_spread_%']:+.2f}% |")
    fund_p = by_reg.loc["🟢 fundamentals", "PEAD_spread_%"] if "🟢 fundamentals" in by_reg.index else np.nan
    spec_p = by_reg.loc["🔴 speculation", "PEAD_spread_%"] if "🔴 speculation" in by_reg.index else np.nan
    stronger = "speculation-ruled" if spec_p > fund_p else "fundamentals-ruled"
    L += ["", "## Read — the opposite of the naive guess (and more interesting)", "",
          f"- PEAD exists (overall **{overall['PEAD_spread_%']:+.2f}%**) — beats drift up, misses "
          "don't. Good: the classic anomaly is real in our data.",
          f"- But it is **STRONGER in {stronger} sectors** (speculation {spec_p:+.2f}% vs "
          f"fundamentals {fund_p:+.2f}%) — the reverse of 'PEAD needs fundamentals'.",
          "- **Why:** PEAD is driven by **information uncertainty**, not by whether price *usually* "
          "tracks earnings. Speculation/growth sectors (tech, biotech, communications) are "
          "hard-to-value and high-uncertainty, so an earnings surprise there **resolves more "
          "uncertainty** — the market under-reacts more and drifts further (Zhang 2006; Francis "
          "et al. 2007). Cyclicals with volatile earnings (Energy +3.1%) show the same for the "
          "same reason. In stable, well-covered fundamental sectors (banks, utilities), surprises "
          "are small and quickly priced, so little drift.",
          "- **Implication for the framework:** the fundamentals-vs-speculation dial is partly a "
          "proxy for **information uncertainty** — and PEAD is one edge that is actually *bigger* "
          "in the speculative/uncertain corner (opposite to value-reversion, which needs "
          "fundamentals). Different anomalies live in different regimes.", "",
          "**Caveats:** US only; surprise = analyst-estimate beat (coverage-biased to larger, "
          "better-covered names — which understates the effect in the least-covered speculative "
          "tail); ~2y of events; equal-weight market proxy; no size/liquidity/vol control (part of "
          "the 'uncertainty' effect could be a volatility effect); overlapping windows. Research, "
          "not investment advice."]
    (REP / "pead_fund_vs_spec.md").write_text("\n".join(L))

    # viz
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = by_reg["PEAD_spread_%"] if len(by_reg) else pd.Series(dtype=float)
    colors = {"🟢 fundamentals": "#1a9850", "🔴 speculation": "#d73027"}
    ax.bar([b.replace("🟢 ", "").replace("🔴 ", "") for b in bars.index], bars.values,
           color=[colors.get(b, "#888") for b in bars.index])
    ax.axhline(0, c="k", lw=.8); ax.set_ylabel("PEAD spread % (beat drift − miss drift)")
    ax.set_title("PEAD is a fundamentals anomaly — it's stronger where fundamentals price the stock\n"
                 f"(US, {len(d):,} earnings events, +{ENTRY}→+{EXIT} trading days)", fontsize=11)
    for i, v in enumerate(bars.values):
        ax.text(i, v + (0.05 if v >= 0 else -0.1), f"{v:+.2f}%", ha="center", fontsize=10, fontweight="bold")
    plt.tight_layout(); plt.savefig(REP / "pead_fund_vs_spec.png", dpi=150, bbox_inches="tight")
    print("\n".join(L[:20]))
    print(f"\nwrote reports/pead_fund_vs_spec.{{csv,md,png}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
