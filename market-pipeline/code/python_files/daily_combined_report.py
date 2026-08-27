# daily_combined_report.py
# =========================
# Combines the two pipelines into ONE daily report with two labelled components:
#
#   1. "STOCK PICKS BASED ON FUNDAMENTALS"  ← pipeline_historical (screeners)
#   2. "TALK ON THE STREET"                 ← pipeline_news (live sentiment)
#
# and a CONVERGENCE section highlighting stocks where BOTH agree
# (fundamentally strong AND positive in the news = highest conviction).
#
# THE TWO APPROACHES (see APPROACHES.md for the full write-up):
#   • FUNDAMENTAL/HISTORICAL — objective screeners on 5yr price+financials
#     (offline, deterministic, backtestable). Answers "is this structurally
#     sound by its own numbers?". Backward-looking; misses catalysts.
#   • NEWS/SENTIMENT — live headlines, company-name matched, VADER-scored
#     (online, noisy, forward-looking). Answers "what is the market saying now?".
#     Captures catalysts; provider-dependent and sometimes mis-signed.
#   CONVERGENCE is a CROSS-CHECK (different failure modes), NOT a buy signal.
#
# Efficient design: the fundamental screeners run on the FULL universe (offline,
# from cache); news sentiment then runs ONLY on the fundamental shortlist + a
# market-mood gauge — so we never burn news quota on 7,000 stocks.
#
# Usage:
#   python daily_combined_report.py --market IN          # full NSE+BSE universe
#   python daily_combined_report.py --market US
#   python daily_combined_report.py --market IN --html   # emit HTML fragment
#
# Output: combined_report_results/combined_<market>_<ts>.{json,html}
#
# ⚠️ Educational/research only. Mechanical screeners + noisy sentiment. NOT advice.

from __future__ import annotations

import argparse
import glob
import json
import os
import threading
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

OUT_DIR = Path("./combined_report_results"); OUT_DIR.mkdir(exist_ok=True)

# Hard wall-clock cap on the optional street-talk component (see get_street_talk).
# 300s is ~40x the 7s this step takes on a healthy day, so it will not clip a
# merely slow provider — it only catches a genuine wedge.
STREET_TALK_TIMEOUT = float(os.environ.get("STREET_TALK_TIMEOUT", "300"))

DISCLAIMER = ("⚠️  Two independent views: mechanical fundamental screeners + noisy "
              "news sentiment. Convergence is NOT a buy signal. Educational/research "
              "only. NOT investment advice. Consult a SEBI-registered advisor.")


# ══════════════════════════════════════════════════════════════════════════════
# COMPONENT 1 — STOCK PICKS BASED ON FUNDAMENTALS
# ══════════════════════════════════════════════════════════════════════════════

# Map each screener sheet → the short tag shown in the report
SCREENER_SHEETS = {
    "Triple_Hits":       "TripleHit",
    "Multi_Screen_Hits": "MultiScreen",
    "Piotroski_Strong":  "Piotroski",
    "Coffee_Can":        "CoffeeCan",
    "Magic_Formula":     "MagicFormula",
    "Bull_Cartel":       "BullCartel",
    "Golden_Crossover":  "GoldenCross",
    "Darvas_Signals":    "Darvas",
}

# ── Convergence grading ───────────────────────────────────────────────────────
# The FOUR independent fundamental screeners. Convergence is graded as how many
# of these four agree on a name: 2/4, 3/4, 4/4 — so the reader picks a
# confidence level instead of being handed one binary verdict.
#
# Technical screens are counted SEPARATELY and never inflate the score. A Darvas
# breakout is not independent evidence of value or quality — it reads price,
# which the fundamental four do not. Conflating them is what made
# "CoffeeCan+Darvas+Piotroski" (2 fundamental screeners) rank as a "Triple Hit"
# alongside a name three fundamental screeners actually agreed on.
FUNDAMENTAL_SCREENS = ("Piotroski", "CoffeeCan", "MagicFormula", "BullCartel")
TECHNICAL_SCREENS   = ("Darvas", "GoldenCross")

# Floor for appearing in the convergence table at all. 1/4 is not convergence,
# it is a single screener with an opinion.
CONV_MIN = int(os.environ.get("CONVERGENCE_MIN", "2"))

# Fixed slot order so the same screener is always in the same position and a
# column of these can be read downward. Matches the mailer's P C M B indicator.
SCREEN_SLOTS = (("Piotroski", "P"), ("CoffeeCan", "C"),
                ("MagicFormula", "M"), ("BullCartel", "B"))


def _slots(fund_screens) -> str:
    have = {s.strip() for s in str(fund_screens or "").split("+")}
    return "".join(letter if tag in have else "·" for tag, letter in SCREEN_SLOTS)


CONV_LEVEL = {4: "4/4 — full", 3: "3/4 — strong", 2: "2/4 — moderate"}
CONV_COLOR = {4: "#1b5e20", 3: "#2e7d32", 2: "#f57f17"}

# Cap the rendered convergence list; the counts-per-level line reports the rest.
CONV_SHOW = int(os.environ.get("CONVERGENCE_SHOW", "25"))


def get_fundamental_picks(market: str, run_fresh: bool = False) -> pd.DataFrame:
    """
    Build the COMBINED, DEDUPLICATED set of every stock that passed ANY screener
    in the latest full scan — not just Triple/Multi-Screen hits. Each stock is
    tagged with the list of screeners it appears in and a tier:
        Triple Hit  > Multi-Screen (3+)  > Single-Screen
    This is the universe on which Talk-on-the-Street sentiment is run.
    """
    print("  [Component 1] Fundamental picks — union of ALL screener sheets …")
    scan_dir = "indian_full_scan" if market == "IN" else "us_full_scan"
    pat = f"{scan_dir}/*_full_scan_*.xlsx"
    files = sorted(glob.glob(pat))

    if run_fresh or not files:
        import subprocess, sys
        script = "full_indian_market_scan.py" if market == "IN" else "full_us_market_scan.py"
        print(f"  [Component 1] Running fresh scan ({script}) …")
        cmd = [sys.executable, script, "--workers", "10"]
        if market == "US": cmd += ["--min-price", "2"]
        subprocess.run(cmd, timeout=14400)
        files = sorted(glob.glob(pat))

    if not files:
        return pd.DataFrame()

    f  = files[-1]
    xl = pd.ExcelFile(f)
    agg: dict = {}   # symbol → {screens:set, piotroski, ltp}

    def _add(sym, tag, piotroski=None, ltp=None):
        sym = str(sym or "").strip()
        if not sym:
            return
        e = agg.setdefault(sym, {"screens": set(), "piotroski": None, "ltp": None})
        e["screens"].add(tag)
        if piotroski is not None and pd.notna(piotroski): e["piotroski"] = piotroski
        if ltp is not None and pd.notna(ltp):             e["ltp"] = ltp

    # Layout A — separate per-screener sheets (US scan)
    for sheet, tag in SCREENER_SHEETS.items():
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(f, sheet_name=sheet)
        for _, r in df.iterrows():
            if sheet == "Darvas_Signals" and \
               str(r.get("Darvas_Signal","")).upper() != "BREAKOUT_BUY":
                continue
            _add(r.get("Symbol"), tag, r.get("Piotroski_Score"), r.get("LTP"))

    # Layout B — single column-based "Fundamentals" sheet (Indian scan)
    if "Fundamentals" in xl.sheet_names:
        fd = pd.read_excel(f, sheet_name="Fundamentals")
        for _, r in fd.iterrows():
            sym, ltp, pio = r.get("Symbol"), r.get("LTP"), r.get("Piotroski_Score")
            if str(r.get("Piotroski_Strong","")).upper() == "YES":
                _add(sym, "Piotroski", pio, ltp)
            if str(r.get("CoffeeCan","")).upper() == "PASS":
                _add(sym, "CoffeeCan", pio, ltp)
            if str(r.get("MagicFormula","")).upper() == "PASS":
                _add(sym, "MagicFormula", pio, ltp)
            if str(r.get("BullCartel","")).upper() == "PASS":
                _add(sym, "BullCartel", pio, ltp)
            if str(r.get("Darvas_Signal","")).upper() == "BREAKOUT_BUY":
                _add(sym, "Darvas", pio, ltp)
    # Golden Cross from All_Stocks (column-based, both layouts)
    if "All_Stocks" in xl.sheet_names:
        a = pd.read_excel(f, sheet_name="All_Stocks")
        if "GC_Signal" in a.columns:
            for _, r in a[a["GC_Signal"].astype(str).str.upper()=="GOLDEN_CROSS"].iterrows():
                _add(r.get("Symbol"), "GoldenCross", r.get("Piotroski_Score"), r.get("LTP"))

    picks = []
    for sym, e in agg.items():
        screens = e["screens"]
        n = len([s for s in screens if s not in ("TripleHit","MultiScreen")])
        # Independent fundamental agreement (0-4) vs price-based confirmation
        # (0-2), kept apart on purpose — see FUNDAMENTAL_SCREENS above.
        n_fund = len(screens & set(FUNDAMENTAL_SCREENS))
        n_tech = len(screens & set(TECHNICAL_SCREENS))
        if "TripleHit" in screens:
            tier = "Triple Hit"
        elif "MultiScreen" in screens or n >= 3:
            tier = "Multi-Screen"
        else:
            tier = "Single-Screen"
        picks.append({
            "Symbol": sym, "Tier": tier,
            "Screens": "+".join(sorted(s for s in screens
                                       if s not in ("TripleHit","MultiScreen"))) or "—",
            "N_Screens": n,
            "N_Fund": n_fund, "N_Tech": n_tech,
            "Fund_Screens": "+".join(sorted(screens & set(FUNDAMENTAL_SCREENS))) or "—",
            "Tech_Screens": "+".join(sorted(screens & set(TECHNICAL_SCREENS))) or "—",
            "Piotroski": e["piotroski"], "LTP": e["ltp"],
        })

    df = pd.DataFrame(picks)
    if not df.empty:
        # Rank by INDEPENDENT fundamental agreement first. This ordering also
        # decides which names reach Talk-on-the-Street (build_report sends the
        # top 25), so the news enrichment lands on the most convergent names
        # rather than on whatever the old conflated Tier happened to float up.
        df = df.sort_values(["N_Fund","N_Tech","N_Screens"],
                            ascending=[False,False,False])
    n_triple = int((df["Tier"]=="Triple Hit").sum()) if not df.empty else 0
    n_multi  = int((df["Tier"]=="Multi-Screen").sum()) if not df.empty else 0
    print(f"  [Component 1] {len(df)} UNIQUE fundamental picks across all screeners "
          f"({n_triple} triple, {n_multi} multi-screen, "
          f"{len(df)-n_triple-n_multi} single-screen)")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# COMPONENT 2 — TALK ON THE STREET (news sentiment)
# ══════════════════════════════════════════════════════════════════════════════

def get_street_talk(symbols: list, market: str) -> tuple:
    """
    Market-mood gauge + per-ticker sentiment for the given symbols.
    Returns (market_mood dict, {symbol: sentiment dict}).
    """
    print(f"  [Component 2] Talk on the Street — news sentiment for "
          f"{len(symbols)} picks + market mood …")
    try:
        from sentiment_pipeline import SentimentPipeline
    except ImportError:
        return {}, {}

    def _fetch():
        sp = SentimentPipeline()
        mood = sp.get_market_mood(market)   # IN → Moneycontrol/ET; US → CNBC/MarketWatch
        talk = {}
        if symbols:
            res = sp.get_batch(symbols, market)
            for sym, s in res.items():
                talk[sym] = {"score": s.score, "label": s.label,
                             "n_articles": s.n_articles,
                             "headlines": s.top_headlines[:2]}
        return mood, talk

    # Component 2 is optional colour on top of the mechanical screeners — the
    # report already renders fine with an empty talk dict (see the ImportError
    # path above). So it must never be able to hold up the brief.
    #
    # Individual providers are bounded at their own call sites, but this is the
    # backstop for the class of bug that cost the 2026-08-07 brief: one
    # unbounded socket, four hours and fifty minutes, lock held, send exits 0.
    # A daemon thread caps this by wall clock without needing the callee to
    # cooperate — which matters, because the RSS path swallows exceptions per
    # feed, so a signal-based timeout there would be caught and discarded.
    # A stalled fetch is abandoned, not awaited; the process can still exit.
    out: dict = {}

    def _runner():
        try:
            out["value"] = _fetch()
        except Exception as exc:            # noqa: BLE001 - optional component
            out["error"] = exc

    t = threading.Thread(target=_runner, daemon=True, name="street-talk")
    t.start()
    t.join(STREET_TALK_TIMEOUT)

    if t.is_alive():
        print(f"  ⚠️  street talk exceeded {STREET_TALK_TIMEOUT:.0f}s — "
              f"continuing without sentiment (Component 1 is unaffected)")
        return {}, {}
    if "error" in out:
        print(f"  ⚠️  street talk failed ({out['error']}) — "
              f"continuing without sentiment (Component 1 is unaffected)")
        return {}, {}
    return out.get("value", ({}, {}))


# ══════════════════════════════════════════════════════════════════════════════
# CONVERGENCE — where both components agree
# ══════════════════════════════════════════════════════════════════════════════

def find_convergence(picks: pd.DataFrame, talk: dict) -> pd.DataFrame:
    """
    Grade every pick by how many of the four INDEPENDENT fundamental screeners
    agree on it — 4/4, 3/4, 2/4 — so the reader chooses a confidence level
    rather than being handed one binary verdict.

    News is an ENRICHMENT COLUMN, never a gate. The previous version joined
    picks against `talk` and skipped any name `talk` did not cover, so when
    Talk-on-the-Street timed out (it returns {} on timeout) EVERY pick was
    skipped and the section rendered "no matching news coverage" — which reads
    as a finding when it actually means the check never ran. On 2026-08-27 that
    hid HINDCOPPER, a 3/4 name the independent buzz feed had already scored
    POSITIVE. Fundamental agreement is computed from the scan and is always
    available, so the ladder now survives a dead news feed.
    """
    if picks.empty:
        return pd.DataFrame()

    rows = []
    for _, p in picks.iterrows():
        n_fund = int(p.get("N_Fund", 0) or 0)
        if n_fund < CONV_MIN:
            continue
        t = talk.get(p["Symbol"]) or {}
        label = t.get("label", "NO_DATA")
        has_news = bool(t) and label != "NO_DATA"
        heads = t.get("headlines") or []
        rows.append({
            "Symbol": p["Symbol"],
            "Level": CONV_LEVEL.get(n_fund, f"{n_fund}/4"),
            "N_Fund": n_fund,
            "Fund_Screens": p.get("Fund_Screens", "—"),
            "Tech_Confirm": p.get("Tech_Screens", "—"),
            "N_Tech": int(p.get("N_Tech", 0) or 0),
            "Tier": p.get("Tier", ""),
            "News": label if has_news else "— no news data",
            "News_Score": float(t.get("score", 0.0)) if has_news else 0.0,
            "N_Articles": int(t.get("n_articles", 0)) if has_news else 0,
            "Top_Headline": heads[0]["title"][:80] if heads else "",
            # Retained so anything still filtering on the old string keeps working.
            "Convergence": ("✅ BOTH BULLISH" if label == "POSITIVE" else
                            "⚠️ NEWS NEGATIVE" if label == "NEGATIVE" else
                            "— news neutral" if has_news else "— no news data"),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        # Strongest fundamental agreement first; within a level, technical
        # confirmation then news score break the tie.
        df = df.sort_values(["N_Fund","N_Tech","News_Score"],
                            ascending=[False,False,False])
    return df


def convergence_counts(conv: pd.DataFrame) -> dict:
    """{4: n, 3: n, 2: n} — how many names sit at each confidence level."""
    if conv.empty:
        return {}
    return {int(k): int(v) for k, v in conv["N_Fund"].value_counts().items()}


# ══════════════════════════════════════════════════════════════════════════════
# REPORT ASSEMBLY
# ══════════════════════════════════════════════════════════════════════════════

def build_report(market: str, run_fresh: bool) -> dict:
    print(f"\n{'#'*72}\n  DAILY COMBINED REPORT — {market}\n{'#'*72}\n  {DISCLAIMER}\n")

    picks = get_fundamental_picks(market, run_fresh)
    # Street-talk only needs the symbols actually shown in the report (top 25,
    # Triple Hits first). Scoring all 300 picks via keyless news APIs stalls.
    symbols = picks.head(25)["Symbol"].tolist() if not picks.empty else []
    mood, talk = get_street_talk(symbols, market)
    convergence = find_convergence(picks, talk)

    return {"market": market, "generated": datetime.now().isoformat(),
            "picks": picks, "mood": mood, "talk": talk, "convergence": convergence}


def print_report(rep: dict):
    market = rep["market"]; cur = "₹" if market=="IN" else "$"

    print(f"\n{'='*74}")
    print(f"  📊 COMPONENT 1 — STOCK PICKS BASED ON FUNDAMENTALS")
    print(f"{'='*74}")
    picks = rep["picks"]
    if picks.empty:
        print("  No fundamental picks today.")
    else:
        # Convergence rides in the row, so tier and agreement are read together.
        # "Triple Hit" counted technical screens alongside fundamental ones and
        # could not be trusted as a measure of agreement; the fraction can.
        print(f"  {'Symbol':<14} {'Conv':<6} {'PCMB':<7} {'Technical':<14} {'Piotroski'}")
        print("  " + "─"*60)
        for _, r in picks.head(25).iterrows():
            print(f"  {str(r['Symbol']):<14} "
                  f"{int(r.get('N_Fund', 0))}/4   "
                  f"{_slots(r.get('Fund_Screens')):<7} "
                  f"{str(r.get('Tech_Screens', '—')):<14} {r.get('Piotroski','—')}")

    print(f"\n{'='*74}")
    print(f"  🗞️  COMPONENT 2 — TALK ON THE STREET (live news sentiment)")
    print(f"{'='*74}")
    mood = rep["mood"]
    src = "CNBC/MarketWatch" if market == "US" else "Moneycontrol/ET/BusinessLine/LiveMint"
    if mood:
        print(f"  Market mood: {mood.get('mood')} ({mood.get('score'):+.2f}) "
              f"from {mood.get('n_articles')} articles ({src})")
    talk = rep["talk"]
    if talk:
        print(f"\n  {'Symbol':<14} {'Sentiment':<10} {'Score':>7} {'Articles':>9}")
        print("  " + "─"*46)
        for sym, t in sorted(talk.items(), key=lambda x:-x[1]["score"]):
            if t["label"] != "NO_DATA":
                print(f"  {sym:<14} {t['label']:<10} {t['score']:>+7.2f} {t['n_articles']:>9}")

    print(f"\n{'='*74}")
    print(f"  ⭐ CONVERGENCE — HOW MANY OF THE 4 FUNDAMENTAL SCREENERS AGREE")
    print(f"{'='*74}")
    conv = rep["convergence"]
    if conv.empty:
        print(f"  No name reached {CONV_MIN}/4 fundamental screener agreement today.")
    else:
        counts = convergence_counts(conv)
        print("  " + " · ".join(f"{lv}/4: {counts.get(lv,0)}" for lv in (4,3,2))
              + f"  (screeners: {', '.join(FUNDAMENTAL_SCREENS)})")
        if not talk:
            print("  ⚠️  news enrichment unavailable — levels below are fundamental-only")
        for lv in (4, 3, 2):
            grp = conv[conv["N_Fund"] == lv]
            if grp.empty:
                continue
            print(f"\n  ── {CONV_LEVEL[lv]} ({len(grp)}) "
                  + "─"*max(0, 48-len(CONV_LEVEL[lv])))
            for _, r in grp.head(CONV_SHOW).iterrows():
                tech = f" +{r['Tech_Confirm']}" if r["N_Tech"] else ""
                news = (f"news {r['News_Score']:+.2f} ({r['N_Articles']} art)"
                        if r["N_Articles"] else "no news data")
                print(f"    {r['Symbol']:<12} {r['Fund_Screens']:<34}{tech:<16} {news}")
                if r["Top_Headline"]:
                    print(f"                 └─ {r['Top_Headline'][:60]}")
            if len(grp) > CONV_SHOW:
                print(f"    … {len(grp)-CONV_SHOW} more at this level")

    print(f"\n  {DISCLAIMER}\n")


def to_html(rep: dict) -> str:
    """Emit an HTML fragment for the daily mailer (two components + convergence)."""
    market = rep["market"]; cur = "₹" if market=="IN" else "$"
    picks, talk, conv, mood = rep["picks"], rep["talk"], rep["convergence"], rep["mood"]
    h = []
    # Component 1
    h.append('<h2>📊 Stock Picks Based on Fundamentals</h2>')
    h.append('<table><tr><th>Symbol</th><th>Convergence</th><th>P C M B</th>'
             '<th>Technical</th><th>Piotroski</th></tr>')
    for _, r in (picks.head(25).iterrows() if not picks.empty else []):
        h.append(f"<tr><td><b>{r['Symbol']}</b></td>"
                 f"<td><b>{int(r.get('N_Fund', 0))}/4</b></td>"
                 f"<td style='font-family:monospace;letter-spacing:2px'>"
                 f"{_slots(r.get('Fund_Screens'))}</td>"
                 f"<td>{r.get('Tech_Screens','—')}</td>"
                 f"<td>{r.get('Piotroski','—')}</td></tr>")
    h.append('</table>')
    # Component 2
    h.append('<h2>🗞️ Talk on the Street</h2>')
    if mood:
        col = {"POSITIVE":"#2e7d32","NEGATIVE":"#c62828"}.get(mood.get("mood"),"#f57f17")
        src = ("CNBC · MarketWatch" if market == "US"
               else "Moneycontrol · ET · BusinessLine · LiveMint")
        h.append(f'<p>Market mood: <b style="color:{col}">{mood.get("mood")} '
                 f'({mood.get("score"):+.2f})</b> from {mood.get("n_articles")} live articles '
                 f'({src})</p>')
    h.append('<table><tr><th>Symbol</th><th>Sentiment</th><th>Score</th><th>Articles</th></tr>')
    for sym, t in sorted(talk.items(), key=lambda x:-x[1]["score"]):
        if t["label"] == "NO_DATA": continue
        col = {"POSITIVE":"#2e7d32","NEGATIVE":"#c62828"}.get(t["label"],"#f57f17")
        h.append(f"<tr><td><b>{sym}</b></td><td style='color:{col}'>{t['label']}</td>"
                 f"<td>{t['score']:+.2f}</td><td>{t['n_articles']}</td></tr>")
    h.append('</table>')
    # Convergence — graded by how many of the four fundamental screeners agree
    h.append('<h2>⭐ Convergence — How Many of the 4 Fundamental Screeners Agree</h2>')
    if not conv.empty:
        counts = convergence_counts(conv)
        h.append('<p>' + " &middot; ".join(
            f'<b>{lv}/4:</b> {counts.get(lv,0)}' for lv in (4,3,2))
            + f' <span style="color:#777">({", ".join(FUNDAMENTAL_SCREENS)})</span></p>')
        if not talk:
            h.append('<p style="color:#f57f17">⚠️ News enrichment unavailable — '
                     'levels below are fundamental-only.</p>')
        for lv in (4, 3, 2):
            grp = conv[conv["N_Fund"] == lv]
            if grp.empty:
                continue
            h.append(f'<p style="color:{CONV_COLOR[lv]}"><b>{CONV_LEVEL[lv]}</b> '
                     f'({len(grp)})</p><ul>')
            for _, r in grp.head(CONV_SHOW).iterrows():
                tech = (f" &middot; technical: {r['Tech_Confirm']}"
                        if r["N_Tech"] else "")
                news = (f" &middot; news {r['News_Score']:+.2f} "
                        f"({r['N_Articles']} articles)" if r["N_Articles"]
                        else ' &middot; <span style="color:#777">no news data</span>')
                head = f": {r['Top_Headline']}" if r["Top_Headline"] else ""
                h.append(f"<li><b>{r['Symbol']}</b> — {r['Fund_Screens']}"
                         f"{tech}{news}{head}</li>")
            if len(grp) > CONV_SHOW:
                h.append(f'<li style="color:#777">… {len(grp)-CONV_SHOW} more</li>')
            h.append('</ul>')
    else:
        h.append(f'<p>No name reached {CONV_MIN}/4 fundamental screener agreement today.</p>')
    h.append(f'<p style="font-size:11px;color:#bf360c">{DISCLAIMER}</p>')
    return "\n".join(h)


def save(rep: dict, emit_html: bool):
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    base = OUT_DIR / f"combined_{rep['market']}_{ts}"
    payload = {
        "market": rep["market"], "generated": rep["generated"],
        "mood": rep["mood"],
        "picks": rep["picks"].to_dict("records") if not rep["picks"].empty else [],
        "convergence": rep["convergence"].to_dict("records") if not rep["convergence"].empty else [],
        "talk": rep["talk"],
    }
    base.with_suffix(".json").write_text(json.dumps(payload, default=str, indent=2))
    print(f"  📊 → {base}.json")
    if emit_html:
        base.with_suffix(".html").write_text(to_html(rep))
        print(f"  📄 → {base}.html  (drop into the daily mailer)")


def main():
    p = argparse.ArgumentParser(description="Daily combined report: fundamentals + street talk")
    p.add_argument("--market", choices=["IN","US"], default="IN")
    p.add_argument("--run-fresh", action="store_true", help="Run full scan fresh")
    p.add_argument("--html", action="store_true", help="Also emit HTML fragment")
    a = p.parse_args()
    rep = build_report(a.market, a.run_fresh)
    print_report(rep)
    save(rep, a.html)


if __name__ == "__main__":
    main()
