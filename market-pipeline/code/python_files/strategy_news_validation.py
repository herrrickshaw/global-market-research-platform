#!/usr/bin/env python3
"""
strategy_news_validation.py — which screens pick names the market is talking about.

THE QUESTION
────────────
Name-level convergence asks "does the street agree about THIS stock". This asks
the level up: of the names each SCREEN selects, what share does the news cover
at all, and how does that compare with the market's own base rate? A screen
whose picks are covered far more often than a random name from the same universe
is selecting on something the market is currently paying attention to.

WHAT THIS IS NOT — READ BEFORE USING IT
───────────────────────────────────────
It measures ATTENTION, NOT RETURNS. News coverage says a name is being
discussed, not that the screen makes money. The two come apart constantly: the
most-covered names are the largest and most liquid, and this project's own
cost/capacity work found the edge lives in the ILLIQUID tail — so a screen that
scores badly here may be the better strategy, precisely because nobody is
writing about its picks.

Whether a strategy WORKS is answered by validation_registry.py (backtested,
fixed-horizon, multiple-testing corrected) and nothing here changes a single
entry in it. Read this as "what is the market looking at", never as validation.

TWO CONFOUNDS, BOTH REPORTED RATHER THAN CORRECTED
──────────────────────────────────────────────────
1. LIQUIDITY. Big liquid names get more press whatever screen picks them, so a
   screen tilted to large caps inherits a higher coverage rate for free. The
   liquidity mix of each screen's picks is printed alongside its lift so the
   confound is visible in the same row. Correcting for it properly needs a
   matched-sample design, which is more than a daily report should assert.
2. SAMPLE SIZE. The India news pool matched 53 distinct tickers on 2026-08-27
   against 954 fundamental picks, so a single day gives most screens single-digit
   counts. Rows below the evaluation contract's floor are marked UNDERPOWERED
   and carry no verdict — the same rule the backtests face, applied here.

Because one day is thin by construction, every run appends to a dated history
and the report shows the cumulative view alongside today's. The cumulative
sample is what eventually becomes readable.

Usage:
    python3 strategy_news_validation.py --market IN
    python3 strategy_news_validation.py --market IN --html
    python3 strategy_news_validation.py --history          # cumulative only
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
HIST = HERE / "reports" / "strategy_news_validation_history.csv"

# The floor for saying anything at all, taken from the tamper-evident evaluation
# contract rather than re-declared here — the same gate the backtests clear.
try:
    from eval_contract import MIN_NONOVERLAP_OBS as MIN_OBS
except Exception:                                              # noqa: BLE001
    MIN_OBS = 15


def _strategy_picks(market: str) -> tuple[pd.DataFrame, int]:
    """(picks with a Screens column, size of the scanned universe)."""
    import daily_combined_report as R
    picks = R.get_fundamental_picks(market)
    universe = 0
    try:
        import glob
        d = "indian_full_scan" if market == "IN" else "us_full_scan"
        f = sorted(glob.glob(f"{d}/*_full_scan_*.xlsx"))[-1]
        universe = len(pd.read_excel(f, sheet_name="All_Stocks"))
    except Exception:                                          # noqa: BLE001
        pass
    return picks, universe


def _covered(market: str) -> dict:
    """{SYMBOL: {score, label, mentions}} for every name the news pool matches."""
    import news_picks as npk
    try:
        rows = npk.news_picks(market, top=5000, min_mentions=1)
    except Exception:                                          # noqa: BLE001
        return {}
    return {str(r["symbol"]).upper(): r for r in rows}


def analyse(market: str) -> dict:
    picks, universe = _strategy_picks(market)
    cov = _covered(market)
    if picks.empty:
        return {"market": market, "rows": pd.DataFrame(), "universe": universe,
                "n_covered": len(cov), "base_rate": None}

    import liquidity as liq
    picks = picks.copy()
    picks["Market"] = market
    picks = liq.annotate(picks)

    # Base rate: share of the SCANNED UNIVERSE the news touches at all. Without
    # this denominator a coverage rate is unreadable — 12% means nothing until
    # you know whether the market's own rate is 3% or 30%.
    base = (len(cov) / universe) if universe else None

    strategies = ["Piotroski", "CoffeeCan", "MagicFormula", "BullCartel",
                  "Darvas", "GoldenCross"]
    out = []
    for s in strategies:
        sel = picks[picks["Screens"].astype(str).str.contains(s, na=False)]
        n = len(sel)
        if not n:
            continue
        hit = sel[sel["Symbol"].astype(str).str.upper().isin(cov)]
        k = len(hit)
        scores = [cov[str(x).upper()]["score"] for x in hit["Symbol"]]
        rate = k / n
        liq_mix = sel["Liquidity"].value_counts(normalize=True).to_dict() \
            if "Liquidity" in sel.columns else {}
        out.append({
            "date": str(date.today()), "market": market, "strategy": s,
            "picks": n, "covered": k, "coverage_rate": round(rate, 4),
            "lift": round(rate / base, 2) if base else None,
            "mean_sentiment": round(sum(scores) / len(scores), 3) if scores else None,
            "pct_high_liq": round(liq_mix.get("High", 0.0), 3),
            "powered": k >= MIN_OBS,
        })
    df = pd.DataFrame(out).sort_values("coverage_rate", ascending=False)
    return {"market": market, "rows": df, "universe": universe,
            "n_covered": len(cov), "base_rate": base}


def append_history(df: pd.DataFrame) -> None:
    """Upsert on (date, market, strategy) — a re-run REPLACES that day's row.

    A plain append double-counts every re-run: running the India report twice on
    2026-08-27 put Darvas in the cumulative view at 810 picks when the day had
    405. The pooled sample is the whole point of keeping history, so it must not
    inflate every time the report is regenerated, previewed, or retried.
    """
    if df.empty:
        return
    HIST.parent.mkdir(parents=True, exist_ok=True)
    key = ["date", "market", "strategy"]
    if HIST.exists():
        try:
            old = pd.read_csv(HIST)
            merged = pd.concat([old, df], ignore_index=True)
            merged = merged.drop_duplicates(subset=key, keep="last")
        except Exception:                                      # noqa: BLE001
            merged = df
    else:
        merged = df
    merged.sort_values(key).to_csv(HIST, index=False)


def cumulative(market: str | None = None) -> pd.DataFrame:
    """Pooled view across every run so far — where a readable sample comes from."""
    if not HIST.exists():
        return pd.DataFrame()
    h = pd.read_csv(HIST)
    if market:
        h = h[h["market"] == market]
    if h.empty:
        return h
    g = h.groupby(["market", "strategy"]).agg(
        days=("date", "nunique"), picks=("picks", "sum"),
        covered=("covered", "sum"),
        mean_sentiment=("mean_sentiment", "mean")).reset_index()
    g["coverage_rate"] = (g["covered"] / g["picks"]).round(4)
    g["powered"] = g["covered"] >= MIN_OBS
    return g.sort_values("coverage_rate", ascending=False)


def print_report(res: dict) -> None:
    m, df, base = res["market"], res["rows"], res["base_rate"]
    print(f"\n{'='*74}")
    print(f"  🔬 STRATEGY VALIDATION — {m}: which screens pick names the market covers")
    print(f"{'='*74}")
    print(f"  universe {res['universe']:,} scanned · {res['n_covered']} names matched "
          f"by news · base rate {base:.1%}" if base else "  base rate unavailable")
    if df.empty:
        print("  no strategy picks today.")
        return
    print(f"\n  {'strategy':<14}{'picks':>7}{'covered':>9}{'rate':>8}{'lift':>7}"
          f"{'sent':>8}{'%High liq':>11}  verdict")
    print("  " + "─"*72)
    for _, r in df.iterrows():
        lift = f"{r['lift']:.2f}x" if pd.notna(r["lift"]) else "—"
        sent = f"{r['mean_sentiment']:+.2f}" if pd.notna(r["mean_sentiment"]) else "—"
        verdict = "" if r["powered"] else f"UNDERPOWERED (<{MIN_OBS})"
        print(f"  {r['strategy']:<14}{r['picks']:>7}{r['covered']:>9}"
              f"{r['coverage_rate']:>7.1%}{lift:>7}{sent:>8}"
              f"{r['pct_high_liq']:>10.0%}  {verdict}")

    cum = cumulative(m)
    if not cum.empty:
        print(f"\n  ── cumulative across {int(cum['days'].max())} run(s) ──")
        for _, r in cum.iterrows():
            flag = "" if r["powered"] else f"  UNDERPOWERED (<{MIN_OBS})"
            print(f"  {r['strategy']:<14}{int(r['picks']):>7}{int(r['covered']):>9}"
                  f"{r['coverage_rate']:>7.1%}{flag}")

    print(f"\n  ⚠️  ATTENTION, NOT RETURNS. Coverage says a name is being discussed,")
    print(f"      not that the screen makes money — and the most-covered names are")
    print(f"      the most liquid, where this project's own work found the edge is")
    print(f"      WEAKEST. Whether a strategy works is validation_registry.py's")
    print(f"      answer, not this table's. Rows under {MIN_OBS} covered names carry")
    print(f"      no verdict at all.")


def to_html(res: dict) -> str:
    df, base = res["rows"], res["base_rate"]
    if df.empty:
        return "<p class='mut' style='color:#777'>No strategy picks today.</p>"
    h = ["<table style='border-collapse:collapse;font-size:13px;width:100%'>",
         "<tr style='background:#eef'><th align='left' style='padding:5px 8px'>Strategy</th>"
         "<th align='left'>Picks</th><th align='left'>Covered</th>"
         "<th align='left'>Rate</th><th align='left'>Lift</th>"
         "<th align='left'>Sentiment</th><th align='left'>% High liq</th></tr>"]
    for _, r in df.iterrows():
        dim = "" if r["powered"] else "color:#999"
        lift = f"{r['lift']:.2f}×" if pd.notna(r["lift"]) else "—"
        sent = f"{r['mean_sentiment']:+.2f}" if pd.notna(r["mean_sentiment"]) else "—"
        note = "" if r["powered"] else " <span style='color:#b8860b'>underpowered</span>"
        h.append(f"<tr style='{dim}'><td style='padding:4px 8px'><b>{r['strategy']}</b>"
                 f"{note}</td><td>{r['picks']}</td><td>{r['covered']}</td>"
                 f"<td>{r['coverage_rate']:.1%}</td><td>{lift}</td>"
                 f"<td>{sent}</td><td>{r['pct_high_liq']:.0%}</td></tr>")
    h.append("</table>")
    h.append(f"<p class='mut' style='font-size:11px;color:#666;margin:4px 0'>"
             f"<b>Lift</b> is coverage rate ÷ the market's own base rate "
             f"({base:.1%} of the scanned universe appears in the news pool). "
             f"<b>This measures attention, not returns</b> — the most-covered names "
             f"are the most liquid, where this project's cost/capacity work found "
             f"the edge is weakest. Whether a strategy works is answered by the "
             f"validated-edge registry, not by this table. Rows with fewer than "
             f"{MIN_OBS} covered names are underpowered and carry no verdict.</p>")
    return "\n".join(h)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--market", default="IN", choices=["IN", "US"])
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--history", action="store_true", help="cumulative view only")
    ap.add_argument("--no-append", action="store_true")
    a = ap.parse_args()

    if a.history:
        c = cumulative()
        print(c.to_string(index=False) if not c.empty else "no history yet")
        return 0

    res = analyse(a.market)
    print_report(res)
    if not a.no_append:
        append_history(res["rows"])
    if a.html:
        out = HERE / f"strategy_validation_{a.market}.html"
        out.write_text(to_html(res))
        print(f"\n  📄 → {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
