#!/usr/bin/env python3
# build_mailer.py
# ===============
# Assemble the Daily Market Brief HTML (+ plain-text summary) — the ONE
# assembler for the live daily_pipeline.sh -> send_mailer.py path.
#
# Merged 2026-07-13 with the previously-separate, unused-on-this-branch
# build_email.py to avoid two overlapping report builders. This file now
# covers everything build_email.py did, plus what build_mailer.py already
# had:
#   1. Market snapshot (India/US/Europe vs 200-DMA)
#   2. India / US / Europe / Japan / Korea — fundamentals screener picks
#   3. India Cash Conversion Cycle (screener.in 228040)
#   4. Convergence — how many of the 3 independent
#      QUALITY screeners agree (P/C/B slots) INSIDE the picks table, with
#      Magic Formula (value) and technical screens in their own columns
#   5. Share Market News Picks — India + US (headline-driven, screener-independent)
#   6. Talk on the Street — per-ticker sentiment for the fundamental picks
#   7. Darvas Breakouts — India / US / Europe fresh-breakout fragments
#      (Japan/Korea skipped: darvas_breakouts.py has no scan-glob support for
#      those markets yet)
#   8. Global momentum top-15 + "other markets" world tour
#   9. 20-market 5-year scoreboard
#   10. Market Correlation Highlights — top clusters per market from
#       market_correlation_scan.py (NSE/US/Europe/Japan/Korea)
#   + educational-only / NOT-investment-advice disclaimer.
#
# Every section degrades gracefully to "n/a" / an empty-state message when
# its source data (a scan xlsx / combined JSON / darvas_breakouts.py /
# correlation_scan/*.txt) hasn't been generated yet — nothing here is fatal
# to the rest of the report.
#
#   from build_mailer import build; subj, text, html = build()

from __future__ import annotations

import ast
import datetime as _dt
import glob
import json
import os
import re
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")

import liquidity as liq
import run_global_analysis as rga
import market_performance as mp
import news_picks as npk

try:
    import darvas_breakouts as dbrk
except Exception:
    dbrk = None

_COL = {"High": "#1b7f37", "Medium": "#b8860b", "Low": "#b00"}
_SENT_COL = {"POSITIVE": "#1b7f37", "NEGATIVE": "#b00", "NEUTRAL": "#777"}


def _tv(x):
    return f"${x / 1e6:.1f}M" if pd.notna(x) else "—"


def _coverage_scope_note() -> str:
    """State WHY the brief covers two markets, rather than letting three vanish.

    A section that silently disappears reads as a bug or an oversight, and the
    reader has no way to tell a deliberate narrowing from a broken scan. The
    reason is specific and measurable, so it is printed.
    """
    try:
        import watchlist_markets as WM
    except Exception:                                          # noqa: BLE001
        return ""
    parked = " · ".join(f"<b>{k}</b> {v}" for k, v in WM.PARKED.items()
                        if k in ("JP", "KR", "EU"))
    return (f"<p class='mut' style='font-size:11px;margin:2px 0'>📍 <b>Per-name "
            f"coverage: {' + '.join(WM.COVERED)} only.</b> Japan, Korea and "
            f"Europe are parked — {parked}. Their stock-level picks, watchlist "
            f"rows and re-entry names are withheld until real ratios land; "
            f"market-level context below (regime, momentum scoreboard, "
            f"correlations) is price-derived and unaffected, so it still "
            f"covers them.</p>")


def _fund_coverage_note() -> str:
    """A one-line caveat on the fundamental screeners' alphabet coverage.

    The Piotroski picks now span the whole universe (served from the off-hours
    store, one yfinance call = none, no throttle). Coffee Can / Bull Cartel /
    Magic Formula still fetch live per-ticker and throttle alphabetically, so
    they remain A-skewed until Phases 2-3. Stating this stops a reader reading an
    A-heavy list as 'the best fundamental names in India' when it is partly an
    artifact of which names have been collected. The count is computed live so
    the note self-corrects as the store fills.
    """
    try:
        import data_registry as _R
        d = pd.read_parquet(_R.FUND_DIR / "IN_current.parquet")
        u = d.dropna(subset=["cfo", "total_assets"])
        n = u["ticker"].nunique()
        letters = u["ticker"].astype(str).str[0].nunique()
        # MEDIAN age of the store, never the newest row — one fresh ticker must
        # not make 1,300 stale ones look current (the max-mtime bug, again).
        ca = pd.to_datetime(d["collected_at"], errors="coerce", utc=True)
        age_d = float((pd.Timestamp.now(tz="UTC") - ca).dt.days.median())
    except Exception:
        n, letters, age_d = 0, 0, None
    if n < 50:
        return ("<p class='mut' style='font-size:11px;margin:2px 0'>⚠ Fundamentals "
                "coverage is still filling from the off-hours collector; picks may "
                "be alphabet-skewed until it completes.</p>")
    age_txt = "age unknown" if age_d is None else f"median {age_d:.0f}d old"
    # 10 days matches the registry tolerance for fundamentals.in_annual: beyond
    # it the off-hours SCHEDULE has broken, and screening on old financials while
    # presenting them as current is the stale-data failure this brief keeps
    # having to guard against.
    warn = ("" if age_d is None or age_d <= 10 else
            " <b>⚠ STALE — the off-hours collector has not refreshed in over 10 "
            "days; these fundamentals may predate recent results.</b>")
    return (f"<p class='mut' style='font-size:11px;margin:2px 0'>All four fundamental "
            f"screeners (Piotroski · Coffee Can · Magic Formula · Bull Cartel) run on "
            f"the <b>high-liquidity universe only</b> — liquidity is a criterion "
            f"applied before them. Data: off-hours store, {n} names, {letters} "
            f"first-letters, {age_txt}.{warn}</p>")


def _table(headers, rows):
    """A table that scrolls inside its own box instead of breaking the layout.

    Without the wrapper an 8-column table renders at ~800px inside a 375px phone
    viewport, so the whole brief is scaled down to fit and every number becomes
    unreadable. Most of this is read on a phone. The table scrolls sideways on
    its own now; the page does not.
    """
    h = "".join(f"<th align='left' style='padding:5px 8px'>{x}</th>" for x in headers)
    return (
        "<div class='tw' style='overflow-x:auto;-webkit-overflow-scrolling:touch'>"
        f"<table style='border-collapse:collapse;width:100%;font-size:13px;min-width:520px'>"
        f"<tr class='hd' style='background:#eef'>{h}</tr>{''.join(rows)}</table></div>"
    )


def _load_combined(market: str) -> dict:
    files = sorted(glob.glob(f"combined_report_results/combined_{market}_*.json"))
    if not files:
        return {}
    try:
        return json.load(open(files[-1]))
    except Exception:
        return {}


def _news_rows(market: str, top: int = None):
    top = _DETAIL_CAP["news"] if top is None else top
    try:
        picks = npk.news_picks(market, top=top)
    except Exception:
        return []
    rows = []
    for p in picks:
        rows.append(
            f"<tr><td style='padding:4px 8px'><b>{p['symbol']}</b></td>"
            f"<td>{p['name']}</td>"
            f"<td style='color:{_SENT_COL.get(p['label'], '#777')};font-weight:600'>{p['label']} ({p['score']:+.2f})</td>"
            f"<td>{p['mentions']}</td>"
            f"<td class='mut' style='color:#555'>{p['headline']}</td></tr>"
        )
    return rows


# Convergence reads as a fraction in the picks table itself, so the reader maps
# "how many screeners agree" to a name without crossing to a second section and
# matching symbols by eye. 4/4 is rare and worth the strongest colour; 1/4 is one
# screener with an opinion and is deliberately muted rather than hidden.
_CONV_COL = {3: "#1b5e20", 2: "#2e7d32", 1: "#999"}
_N_FUND_SCREENS = 3


def _conv_cell(n_fund) -> str:
    try:
        n = int(n_fund)
    except (TypeError, ValueError):
        return "<td style='color:#999'>—</td>"
    return (f"<td style='color:{_CONV_COL.get(n, '#999')};font-weight:700;"
            f"white-space:nowrap'>{n}/{_N_FUND_SCREENS}</td>")


# Fixed slot order, so the same screener is always in the same position and the
# column can be read down rather than across. Spelling the names out repeated a
# ~30-character string on every row — at 3/4 almost always the same three — which
# is exactly the kind of cell the eye stops reading.
_SCREEN_SLOTS = (("Piotroski", "P"), ("CoffeeCan", "C"), ("BullCartel", "B"))


def _slots_cell(fund_screens, n_fund) -> str:
    """P C M B with the passing ones lit and the rest dimmed to a dot."""
    have = {s.strip() for s in str(fund_screens or "").split("+")}
    col = _CONV_COL.get(_safe_int(n_fund), "#999")
    marks = []
    for tag, letter in _SCREEN_SLOTS:
        if tag in have:
            marks.append(f"<b style='color:{col}'>{letter}</b>")
        else:
            marks.append("<span style='color:#ccc'>·</span>")
    return ("<td style='font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
            "letter-spacing:2px;white-space:nowrap'>" + "".join(marks) + "</td>")


def _safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _market_picks_rows(data: dict, market: str, cap: int = None):
    """Fundamentals-screener picks rows for India/US, liquidity-annotated.

    The Tier column ("Triple Hit"/"Multi-Screen") is gone: it counted technical
    screens alongside fundamental ones, so CoffeeCan+Darvas+Piotroski — two
    fundamental screeners and a breakout — ranked as a "Triple Hit" beside a name
    three fundamental screeners actually agreed on. The fraction cannot lie that
    way, and the two screen groups are now separate columns so the reader can see
    which kind of agreement they are looking at.
    """
    cap = _DETAIL_CAP["picks"] if cap is None else cap
    picks = data.get("picks") or []
    if not picks:
        return []
    p = pd.DataFrame(picks)
    p["Market"] = market
    p = liq.annotate(p)
    lr = {"High": 0, "Medium": 1, "Low": 2, "Unknown": 3}
    # Pre-ladder payloads have no N_Fund; fall back to the old tier order so an
    # older combined JSON still renders in a sane sequence instead of blank.
    if "N_Fund" in p.columns:
        p["_o"] = -pd.to_numeric(p["N_Fund"], errors="coerce").fillna(0)
        p["_t"] = -pd.to_numeric(p.get("N_Tech"), errors="coerce").fillna(0)
    else:
        p["_o"] = p["Tier"].map({"Triple Hit": 0, "Multi-Screen": 1,
                                 "Single-Screen": 2}).fillna(3)
        p["_t"] = 0
    p["_l"] = p["Liquidity"].map(lr).fillna(3)
    rows = []
    for _, r in p.sort_values(["_o", "_t", "_l"]).head(cap).iterrows():
        fund = r.get("Fund_Screens") or r.get("Screens") or ""
        tech = r.get("Tech_Screens") or "—"
        # Value gets its own cell and its own colour. It is a different question
        # from the quality fraction beside it (cheap vs good), so it must not be
        # mistaken for a fourth vote — see VALUE_SCREENS in daily_combined_report.
        val = ("<td style='color:#6a1b9a;font-weight:700;white-space:nowrap'>MF ✓</td>"
               if _safe_int(r.get("N_Value")) else "<td style='color:#ccc'>·</td>")
        rows.append(
            f"<tr><td style='padding:4px 8px'><b>{r.Symbol}</b></td>"
            f"{_conv_cell(r.get('N_Fund'))}"
            f"{_slots_cell(fund, r.get('N_Fund'))}"
            f"{val}"
            f"<td style='color:#777'>{tech}</td>"
            f"<td>{_tv(r.get('Turnover_USD'))}</td>"
            f"<td style='color:{_COL.get(r.Liquidity, '#777')};font-weight:600'>{r.Liquidity}</td></tr>"
        )
    return rows


def _pio(v):
    try:
        return int(float(v))
    except Exception:
        return None


def _fundamentals_picks_rows(
    glob_pattern: str, ticker_cols: list, has_strong_flag: bool, coffee_col: str, top: int = 15
):
    """Shared by _eu_picks_rows()/_jp_picks_rows()/_kr_picks_rows() -- these 3 markets
    have no combined JSON, so each reads its own scan's Fundamentals sheet directly.
    EU has no Piotroski_Strong flag (has_strong_flag=False collapses pio_ok to a plain
    score>=7 check, matching EU's original filter exactly); JP/KR do."""
    files = sorted(glob.glob(glob_pattern))
    if not files:
        return []
    try:
        xl = pd.ExcelFile(files[-1])
        if "Fundamentals" not in xl.sheet_names:
            return []
        fd = pd.read_excel(files[-1], sheet_name="Fundamentals")
    except Exception:
        return []

    cands = []
    for _, r in fd.iterrows():
        pio = _pio(r.get("Piotroski_Score"))
        strong = has_strong_flag and str(r.get("Piotroski_Strong", "")).upper() == "YES"
        cc = str(r.get(coffee_col, "")).upper() == "PASS"
        pio_ok = strong or (pio is not None and pio >= 7)
        if not (pio_ok or cc):
            continue
        cands.append((pio, pio_ok, cc, r))
    cands.sort(key=lambda x: -(x[0] if x[0] is not None else -1))

    rows = []
    for pio, pio_ok, cc, r in cands[:top]:
        code = ""
        for c in ticker_cols:
            code = str(r.get(c, "") or "").strip()
            if code:
                break
        name = str(r.get("Name", "") or code).split(",")[0]
        tier = "Triple Hit" if (pio_ok and cc) else "Multi-Screen"
        screens = "+".join(s for s, ok in (("Piotroski", pio_ok), ("CoffeeCan", cc)) if ok) or "—"
        rows.append(
            f"<tr><td style='padding:4px 8px'><b>{code}</b></td><td>{name}</td>"
            f"<td>{tier}</td><td>{screens}</td>"
            f"<td>{'n/a' if pio is None else pio}</td></tr>"
        )
    return rows


def _eu_picks_rows(top: int = 15):
    """Europe has no combined JSON — read the EU scan's Fundamentals sheet directly."""
    return _fundamentals_picks_rows(
        "european_scan/european_market_scan*.xlsx",
        ticker_cols=["Symbol"],
        has_strong_flag=False,
        coffee_col="CoffeeCan_Class",
        top=top,
    )


def _jp_picks_rows(top: int = 15):
    """Japan has no combined JSON — read the JP scan's Fundamentals sheet directly.
    Uses Piotroski_Strong (YES/NO) and a plain CoffeeCan (PASS/FAIL) column."""
    return _fundamentals_picks_rows(
        "japan_scan/japan_market_scan*.xlsx",
        ticker_cols=["Code", "YF_Ticker"],
        has_strong_flag=True,
        coffee_col="CoffeeCan",
        top=top,
    )


def _kr_picks_rows(top: int = 15):
    """Korea has no combined JSON — read the KR scan's Fundamentals sheet directly.
    Same shape as _jp_picks_rows() (Piotroski_Strong YES/NO + CoffeeCan PASS/FAIL)."""
    return _fundamentals_picks_rows(
        "korea_scan/korea_market_scan*.xlsx",
        ticker_cols=["Code", "YF_Ticker"],
        has_strong_flag=True,
        coffee_col="CoffeeCan",
        top=top,
    )


def _convergence_note(data: dict) -> str:
    """One line under the picks table: what the fraction means, and how the
    universe is distributed across the four levels.

    This replaces the standalone convergence section. That section listed the
    same names a second time, so the reader had to match symbols by eye between
    two tables to answer "how much agreement is behind this pick?". The fraction
    now sits in the row itself and this line supplies the denominator context —
    one place to look instead of two.
    """
    picks = data.get("picks") or []
    if not picks:
        return ""
    counts: dict[int, int] = {}
    for p in picks:
        try:
            n = int(p.get("N_Fund"))
        except (TypeError, ValueError):
            continue
        counts[n] = counts.get(n, 0) + 1
    if not counts:
        return ("<p class='mut' style='font-size:11px;margin:2px 0;color:#777'>"
                "Convergence unavailable — this report predates the 4-screener "
                "ladder.</p>")
    n_mf = sum(1 for p in picks if _safe_int(p.get("N_Value")))
    mono = "font-family:ui-monospace,Menlo,monospace"
    dist = " &middot; ".join(
        f"<b style='color:{_CONV_COL[lv]}'>{lv}/3</b> {counts.get(lv, 0)}"
        for lv in (3, 2, 1))
    return ("<p class='mut' style='font-size:11px;margin:2px 0;color:#666'>"
            "<b>Convergence</b> = how many of the three <b>quality</b> screeners "
            "agree — all three judge the business from its financials with no "
            "reference to price — read left to right as "
            f"<b style='{mono}'>P</b>iotroski "
            f"<b style='{mono}'>C</b>offee&nbsp;Can "
            f"<b style='{mono}'>B</b>ull&nbsp;Cartel "
            "(<span style='color:#ccc'>·</span> = did not pass). "
            "<b style='color:#6a1b9a'>MF ✓</b> (Magic Formula) is kept in its own "
            "column because it gates on <i>earnings yield</i> — it asks whether a "
            "name is <b>cheap</b>, not whether it is <b>good</b>, so it is not a "
            "fourth vote. Technical screens are separate for the same reason. "
            f"Today: {dist} &middot; <b style='color:#6a1b9a'>MF ✓</b> {n_mf}.</p>")


def _talk_rows(data: dict, cap: int = 10):
    talk = data.get("talk") or {}
    scored = [
        (s, t)
        for s, t in talk.items()
        if isinstance(t, dict) and t.get("label") not in (None, "NO_DATA")
    ]
    scored.sort(key=lambda kv: -float(kv[1].get("score", 0)))
    rows = []
    for sym, t in scored[:cap]:
        col = _SENT_COL.get(t.get("label"), "#777")
        rows.append(
            f"<tr><td style='padding:4px 8px'><b>{sym}</b></td>"
            f"<td style='color:{col};font-weight:600'>{t.get('label')}</td>"
            f"<td>{float(t.get('score', 0)):+.2f}</td><td>{t.get('n_articles', 0)}</td></tr>"
        )
    return rows


_DARVAS_LABEL = {"IN": "🇮🇳 India", "US": "🇺🇸 US", "EU": "🇪🇺 Europe"}


def _ccc_rows(top: int = 12):
    """India Cash Conversion Cycle screen — screener.in/screens/228040. Lowest/
    negative CCC = collects from customers before paying suppliers (strong
    working-capital efficiency). Live-scrapes each run (refreshing the local
    cache); falls back to the cached parquet if the live fetch fails."""
    # 🔴 2026-08-21: THE SCRAPE IS NO LONGER THE SOURCE. CCC used to be fetched
    # whole from screener.in on every build, with a silent fall back to a cached
    # parquet of unstated vintage — so a stale cache and a fresh scrape rendered
    # identically. That single endpoint took out step [6/13] twice in three days.
    #
    # It is now COMPUTED from filings (cash_conversion_cycle.py: EDGAR for US,
    # the yfinance store for India), and screener.in only fills tickers the
    # filings cannot. No network call is made here at all — a section of the
    # brief should not depend on a third-party host answering at build time.
    cdf = pd.DataFrame()
    try:
        import cash_conversion_cycle as ccc_mod

        c = ccc_mod.ccc("IN")
        if not c.empty:
            cdf = pd.DataFrame({"Symbol": c["ticker"],
                                "Cash_Cycle": c["ccc"],
                                "_src": c["source"]})
    except Exception:
        pass
    if cdf.empty:
        try:
            cdf = pd.read_parquet("cache_seed/india_ccc_screen.parquet")
            cdf["_src"] = "screener.in (cache)"
        except Exception:
            return []
    if cdf.empty or "Cash_Cycle" not in cdf.columns:
        return []
    cdf = cdf.copy()
    cdf["Cash_Cycle"] = pd.to_numeric(cdf["Cash_Cycle"], errors="coerce")
    cdf = cdf.dropna(subset=["Cash_Cycle"])
    cdf["Market"] = "IN"
    cdf = liq.annotate(cdf)
    cdf = cdf[cdf["Liquidity"].isin(["High", "Medium"])].sort_values("Cash_Cycle").head(top)
    rows = []
    for _, r in cdf.iterrows():
        rows.append(
            f"<tr><td style='padding:4px 8px'><b>{r.Symbol}</b></td>"
            f"<td>{r.get('Name', '')}</td><td>{r.Cash_Cycle:.1f}</td>"
            f"<td>{r.get('ROCE', '')}</td>"
            f"<td style='color:{_COL.get(r.Liquidity, '#777')};font-weight:600'>{r.Liquidity}</td>"
            # The source is RENDERED, not just recorded. The old code fell back
            # to a cached scrape inside `except Exception: pass`, so a stale
            # cache and a live fetch produced identical output and a reader had
            # no way to tell which they were looking at.
            f"<td style='color:#888;font-size:10.5px'>{r.get('_src', '')}</td></tr>"
        )
    return rows


def _darvas_section(market: str, cap: int = None) -> str:
    """Fresh Darvas breakouts for one market, capped to `cap` rows for readability
    (a full-universe scan can surface 100+ "fresh" breakouts — the header still
    reports the true Tier-1/Tier-2 totals, only the table is truncated)."""
    cap = _DETAIL_CAP["darvas"] if cap is None else cap
    if dbrk is None:
        return "<p class='mut' style='color:#777'>Darvas fragment unavailable (darvas_breakouts.py not importable).</p>"
    label = _DARVAS_LABEL.get(market, market)
    try:
        _, df = dbrk.build(market, write_csv=False)
    except Exception as e:
        return f"<p class='mut' style='color:#777'>Darvas fragment for {market} unavailable ({e}).</p>"
    if df.empty:
        return (
            f"<h3>📈 {label} — Darvas Breakouts</h3>"
            f'<p class="mut" style="color:#777" class="mut">No fresh breakouts in the latest scan.</p>'
        )
    n1 = int((df["Tier"] == 1).sum())
    n2 = int((df["Tier"] == 2).sum())
    shown_note = f", top {cap} of {len(df)} shown" if len(df) > cap else ""
    # Regime gate (10y replay, price_prediction_backtest): bear-regime
    # breakouts are dead-to-negative — keep the table but say so up front.
    try:
        from market_regime import get_regime
        _reg = get_regime(market)
    except Exception:
        _reg = {"trend": "unknown", "vol": "unknown"}
    _badge_color = {"bull": "#1a7f37", "bear": "#c62828", "chop": "#b26a00"}.get(_reg["trend"], "#777")
    regime_html = (
        f'<span style="font-weight:600;color:{_badge_color}">'
        f'{_reg["trend"].upper()} regime · {_reg.get("vol", "?")} vol</span>'
    )
    if _reg["trend"] == "bear":
        regime_html += (
            ' <span style="color:#c62828">— breakouts historically dead in bear '
            'regimes (10y replay: excess ≤0 in US/JP/IN); treat as watch-only, '
            'not entries</span>'
        )
    elif _reg["trend"] == "chop" and _reg.get("vol") == "HIGH":
        regime_html += (
            ' <span style="color:#c62828">— chop + HIGH vol: weakest breakout '
            'cell in the 10y replay; treat as watch-only</span>'
        )
    elif _reg.get("vol") == "HIGH":
        regime_html += (
            ' <span style="color:#b26a00">— HIGH vol: breakout follow-through '
            'historically weaker (LOW/MID-vol wins 4 of 5 markets); size down</span>'
        )
    head = (
        "<tr><th>Tier</th><th>Symbol</th><th>Name</th><th>Exch</th>"
        "<th>LTP</th><th>Day</th><th>Darvas Box</th><th>vs Box Top</th>"
        "<th>Box Pos</th><th>50/200</th><th>GC</th></tr>"
    )
    body = dbrk.rows_html(df.head(cap), market)
    return (
        f"<h3>📈 {label} — Darvas Breakouts "
        f'<span style="font-weight:400;color:#777" class="mut">({n1} Tier-1 · {n2} Tier-2{shown_note})</span></h3>'
        f'<p style="font-size:12px;margin:2px 0 6px">{regime_html}</p>'
        f'<div class="trail" style="overflow-x:auto">'
        f'<table style="border-collapse:collapse;width:100%;font-size:12.5px">'
        f"{head}{body}</table></div>"
        f'<p style="font-size:11px;color:#888;margin-top:4px">Tier 1 = Golden Cross + '
        f"Darvas breakout, box position ≤130%. Tier 2 = box position 100–120%, above "
        f'200-DMA, up day, ≥250 daily bars. <b>Darvas Box</b> = bottom–top of the '
        f'current box; the top is the breakout level. <b>vs Box Top</b> = how far '
        f'price sits above that level (+) or below it (−) — every fresh breakout is '
        f'above by definition, so amber (&gt;+5%) marks a move already extended past '
        f'its trigger. "Box Pos" &gt;100% = trading above the box.</p>'
    )


# 🔴 INDIA AND US ONLY (2026-07-29). Europe, Japan and Korea are parked because
# their fundamentals cannot support a per-name claim: the store holds quality
# SCORES in ratio-named columns for exactly those markets (`pb` takes four
# distinct values in JP/EU, `roe` takes 80/55/40/20 in KR), while india's `roe`
# on the same column is a real fraction. fundamentals.ratios has no EU rows at
# all. Reasons per market live in watchlist_markets.PARKED and are STATED in the
# brief rather than the markets silently vanishing — an unexplained gap reads as
# an oversight, and a reader should know coverage narrowed on purpose.
#
# The space they occupied is spent on depth in the two markets that survive
# scrutiny, not left blank: see the _DETAIL_CAP bump below.
_CORR_MARKETS = [
    ("nse", "🇮🇳 India (NSE)"),
    ("us", "🇺🇸 US"),
]

# Caps were sized for five markets competing for one email. With three parked,
# the remaining two get roughly the room the five shared.
_DETAIL_CAP = {"picks": 24, "news": 12, "darvas": 30}


def _corr_section(top_n: int = 3) -> str:
    """🔗 Market Correlation Highlights — top clusters per market, read from
    market_correlation_scan.py's plain-text cluster report
    (correlation_scan/<market>_correlation_clusters.txt). Each market is parsed
    independently; a missing/malformed file for one market degrades to an
    'n/a' line for that market only, never raises."""
    blocks = []
    for key, label in _CORR_MARKETS:
        try:
            files = sorted(glob.glob(f"correlation_scan/{key}_correlation_clusters.txt"))
            if not files:
                blocks.append(
                    f"<p style='font-size:12px;margin:6px 0'><b>{label}</b>: "
                    f"n/a (no correlation scan yet)</p>"
                )
                continue
            text = open(files[-1]).read()
            header = next((l for l in text.splitlines() if "symbols" in l and "period=" in l), "")
            m = re.search(r"([\d,]+)\s+symbols", header)
            n_sym = m.group(1) if m else "?"
            cl_lines = [l.strip() for l in text.splitlines() if l.strip().startswith("(")]
            items = []
            for l in cl_lines[:top_n]:
                mm = re.match(r"\((\d+)\)\s+(\[.*\])", l)
                if not mm:
                    continue
                size = mm.group(1)
                try:
                    members = ast.literal_eval(mm.group(2))
                except Exception:
                    members = []
                shown = ", ".join(str(x) for x in members[:8]) + (" …" if len(members) > 8 else "")
                items.append(f"<li>({size}) {shown}</li>")
            if not items:
                blocks.append(
                    f"<p style='font-size:12px;margin:6px 0'><b>{label}</b>: "
                    f"{n_sym} symbols scanned, no clusters &gt;1 found</p>"
                )
            else:
                blocks.append(
                    f"<p style='font-size:12px;margin:8px 0 2px'><b>{label}</b> "
                    f"({n_sym} symbols, {len(cl_lines)} clusters found)</p>"
                    f"<ul style='font-size:12px;margin:2px 0 6px 18px'>{''.join(items)}</ul>"
                )
        except Exception:
            blocks.append(
                f"<p style='font-size:12px;margin:6px 0'><b>{label}</b>: "
                f"n/a (error reading correlation scan)</p>"
            )
    return "".join(blocks)


_FLAG = {"IN": "🇮🇳", "US": "🇺🇸", "JP": "🇯🇵", "KR": "🇰🇷", "EU": "🇪🇺"}

# Markets this email actually quotes. A vintage row for a market the brief does
# not cover reads as a coverage claim for content that is not there (the reason
# EU/JP/KR were dropped from this block on 2026-08-12).
_QUOTED = ["IN", "US"]


def _as_of_html() -> str:
    """State the data vintage explicitly: WHICH session, from where, how old.

    Every price here is a LAST OFFICIAL CLOSE, not a live quote, and the brief is
    read hours later — often with the market already open. Measured 2026-07-15 at
    09:15 IST, live quotes had already drifted from that morning's closes:
    HDFCBANK 809.4 -> 812.0, ICICIBANK 1407.7 -> 1417.0, INFY 1092.9 -> 1077.0
    (1.5%). "Data as of last close" does not convey that. This does.

    🔴 REWRITTEN 2026-08-19. The previous version reported the scan FILE'S MTIME
    ("🇺🇸 US · last close at scan time · scanned 19 Aug 04:59") over prices that
    were the 17 Aug close. Both halves were true; together they were misleading,
    because mtime says when we looked and never what we are looking at. That
    morning a reader had no way to tell a two-day-old price from a fresh one.

    The session is now recovered from the PRICES THEMSELVES (data_state, which
    matches scan LTPs back against dated bars) and stated outright, alongside the
    venue, the close time in the venue's own zone, and the source. When the
    quoted data is behind the session that has actually closed and published, the
    block says so FIRST, in the header, rather than leaving it to be inferred
    from two dates in a table.
    """
    import datetime as _d

    try:
        import data_state as _ds

        rows = _ds.provenance(_QUOTED)
    except Exception:
        rows = []
    if not rows:
        return ""

    gen = _d.datetime.now()
    behind = [r for r in rows if r["stale"]]
    ahead = [r for r in rows if r["ahead"]]

    body = ""
    for r in rows:
        flag = _FLAG.get(r["market"], "")
        sess = f"{r['session']:%d %b %Y} close" if r["session"] else "unknown"
        when = (f"{r['closed_local']:%H:%M %Z}" if r["closed_local"] else "")
        age = ("" if not r["behind"] or r["behind"] < 0 else
               f" · <b style='color:#c62828'>{r['behind']} session"
               f"{'s' if r['behind'] > 1 else ''} behind</b>")
        body += (
            f"<tr><td style='padding:2px 10px 2px 0'>{flag} {r['label']}</td>"
            f"<td style='padding:2px 10px 2px 0'><b>{sess}</b>{age}</td>"
            f"<td style='padding:2px 0;color:#777'>{r['venue']} {when} · {r['source']}</td></tr>"
        )

    if behind:
        names = ", ".join(f"{r['label']} ({r['session']:%d %b})" for r in behind)
        head = (f"<b style='color:#c62828'>⚠️ Stale data: {names} — the latest "
                f"published close is newer than what is quoted below.</b> Treat "
                f"those figures as historical, not current. ")
        bg, bar = "#fdecea", "#c62828"
    elif ahead:
        head = ("<b style='color:#e65100'>⚠️ Provisional: at least one market "
                "below is quoted from a session that has not finished trading, "
                "so those prices are intraday, not closes.</b> ")
        bg, bar = "#fff3e0", "#e65100"
    else:
        head = "<b>⏱ Prices are last official closes — not live.</b> "
        bg, bar = "#fffbe6", "#f9a825"

    return (
        f"<div class='note' style='background:{bg};border-left:3px solid {bar};"
        f"padding:8px 11px;margin:0 0 14px;font-size:11.5px;color:#444'>"
        f"{head}"
        f"This brief was generated <b>{gen:%d %b %Y, %H:%M}</b>. Each market below "
        f"shows the exact session its prices come from — not when the file was "
        f"written. Markets move: once trading reopens, live quotes will differ "
        f"from every price here (on 15 Jul, quotes had moved up to ~1.5% from the "
        f"morning's closes by 09:15). Nothing here reflects activity after the "
        f"close shown."
        f"<table style='margin-top:6px;font-size:11px;border-collapse:collapse'>{body}</table>"
        "</div>"
    )


def _market_snapshot_html() -> str:
    idx = [("^NSEI", "Nifty 50"), ("^GSPC", "S&P 500"), ("^STOXX50E", "Euro Stoxx 50")]
    try:
        import yfinance as yf
    except Exception:
        yf = None
    cells = []
    for tkr, name in idx:
        last = dma50 = dma200 = None
        stance200, col200 = "n/a", "#888"
        stance50, col50 = "n/a", "#888"
        cross_note = ""
        if yf is not None:
            try:
                h = yf.download(tkr, period="1y", progress=False, auto_adjust=True)
                closes = pd.to_numeric(h["Close"].squeeze(), errors="coerce").dropna()
                if len(closes):
                    last = float(closes.iloc[-1])
                    if len(closes) >= 50:
                        dma50 = float(closes.rolling(50).mean().iloc[-1])
                        stance50 = "above 50-DMA" if last > dma50 else "below 50-DMA"
                        col50 = "#2e7d32" if last > dma50 else "#c62828"
                    if len(closes) >= 200:
                        dma200 = float(closes.rolling(200).mean().iloc[-1])
                        stance200 = (
                            "above 200-DMA (bullish)"
                            if last > dma200
                            else "below 200-DMA (cautious)"
                        )
                        col200 = "#2e7d32" if last > dma200 else "#c62828"
                    if dma50 is not None and dma200 is not None:
                        cross_note = " · Golden Cross" if dma50 > dma200 else " · Death Cross"
            except Exception:
                pass
        cells.append(
            f"<td style='padding:8px 12px;vertical-align:top'>"
            f"<div style='font-size:12px;color:#888'>{name}</div>"
            f"<div style='font-size:17px;font-weight:700'>{'n/a' if last is None else f'{last:,.0f}'}</div>"
            f"<div style='font-size:11px;color:{col200}'>{stance200} · 200-DMA "
            f"{'n/a' if dma200 is None else f'{dma200:,.0f}'}</div>"
            f"<div style='font-size:11px;color:{col50}'>{stance50} · 50-DMA "
            f"{'n/a' if dma50 is None else f'{dma50:,.0f}'}{cross_note}</div></td>"
        )
    # Regime strip: per-market trend/vol gate state (10y-replay-backed).
    try:
        from market_regime import get_regime
        _rc = {"bull": "#1a7f37", "bear": "#c62828", "chop": "#b26a00"}
        chips = []
        for code, flag in [("IN", "🇮🇳"), ("US", "🇺🇸"), ("EU", "🇪🇺"),
                           ("JP", "🇯🇵"), ("KR", "🇰🇷"), ("CN", "🇨🇳")]:
            r = get_regime(code)
            c = _rc.get(r["trend"], "#777")
            chips.append(
                f"<span style='margin-right:12px'>{flag} "
                f"<b style='color:{c}'>{r['trend'].upper()}</b>"
                f"<span style='color:#888'>/{r.get('vol', '?')}</span></span>")
        regime_strip = (
            "<div style='font-size:11.5px;margin:6px 0 0;padding:6px 10px;"
            "background:#f5f5f5;border-radius:4px'>"
            "<b>Regime gate:</b> " + "".join(chips) +
            "<span style='color:#888'>— breakout entries only in BULL "
            "(bear breakouts dead, 10y replay)</span></div>")
    except Exception:
        regime_strip = ""
    return (f"<table style='border-collapse:collapse;width:100%'><tr>{''.join(cells)}</tr></table>"
            f"{regime_strip}")


def build():
    today = _dt.date.today().strftime("%d %b %Y")

    ind_data = _load_combined("IN")
    us_data = _load_combined("US")
    mood = ind_data.get("mood") or {"mood": "n/a", "score": 0, "n_articles": 0}
    us_mood = us_data.get("mood") or {"mood": "n/a", "score": 0, "n_articles": 0}

    # 0. Market snapshot
    # Carry FX: a funding-currency (JPY/CHF) spike unwinds leveraged carry and
    # the selling lands on exactly the equities this brief covers — the 2024-08-05
    # yen-carry unwind took the Nikkei -12.4% in a session and the KOSPI -8.8%.
    # Best-effort: never let an FX hiccup break the brief.
    try:
        from carry_fx import carry_html as _carry_html

        carry_html_ = _carry_html()
    except Exception as _e:
        carry_html_ = (
            f"<p style='color:#777;font-size:12px'>carry FX unavailable ({str(_e)[:40]})</p>"
        )
    as_of_html = _as_of_html()
    snapshot_html = _market_snapshot_html()

    # 1. India / US fundamentals screener picks.
    #
    # 2026-08-12 (user): the brief covers the two markets an Indian investor can
    # actually TRADE — India directly, US via LRS/international brokerage — in
    # depth, instead of spreading across five. EU/JP/KR were never tradeable in
    # practice for this reader, and their fundamentals could not support a
    # per-name claim anyway (watchlist_markets.PARKED), so the sections were
    # costing space without earning it. _eu/_jp/_kr_picks_rows() and
    # _darvas_section("EU") are deliberately LEFT IN PLACE and still importable:
    # the scans keep running daily in daily_research.sh and still populate
    # market_daily.snapshots, so restoring a market is re-adding its block here,
    # not rebuilding the pipeline.
    ind_picks_rows = _market_picks_rows(ind_data, "IN")
    us_picks_rows = _market_picks_rows(us_data, "US")

    # 2. India CCC screen (screener.in 228040)
    ccc_rows = _ccc_rows()

    # 3. Convergence (fundamentals + street agree)
    # split per market: each geography's block owns its own convergence, so
    # "what about India?" is answerable in one place instead of six
    # Convergence now rides in the picks table itself (see _market_picks_rows);
    # these are the one-line legend + distribution that sit under each table.
    conv_in = _convergence_note(ind_data)
    conv_us = _convergence_note(us_data)
    convergence_html = conv_in + conv_us  # kept for any external caller

    # 4. Share Market News Picks — India + US
    in_news_rows = _news_rows("IN")
    us_news_rows = _news_rows("US")

    # 5. Talk on the Street — per-ticker sentiment for the fundamental picks
    in_talk_rows = _talk_rows(ind_data)
    us_talk_rows = _talk_rows(us_data)

    # 6. Darvas Breakouts — India / US (always rendered, both markets).
    # The EU section is dropped with the rest of the parked markets above.
    darvas_in = _darvas_section("IN")
    darvas_us = _darvas_section("US")

    # 7. Global momentum (top 15 overall)
    allh = rga.load_highlights()
    g = allh.head(15)
    g_rows = [
        f"<tr><td style='padding:4px 8px'>{r.Market}</td><td>{r.Symbol}</td>"
        f"<td>{r.ret_126:+.0f}</td><td>{r.rsi14}</td></tr>"
        for _, r in g.iterrows()
    ]

    # 7b. Other markets — top tradable mover per market (world tour, ex-IN/US)
    other_rows = []
    try:
        h = liq.annotate(allh.copy())
        names = {
            "TW": "Taiwan",
            "KR": "Korea",
            "JP": "Japan",
            "CN": "China",
            "HK": "Hong Kong",
            "CA": "Canada",
            "AU": "Australia",
            "UK": "UK",
            "DE": "Germany",
            "CH": "Switzerland",
            "SE": "Sweden",
            "FI": "Finland",
            "DK": "Denmark",
            "SG": "Singapore",
            "EU": "Euronext",
            "BR": "Brazil",
            "SA": "Saudi",
            "ZA": "S.Africa",
        }
        for m in [x for x in names if x in set(h.Market)]:
            sub = h[h.Market == m].sort_values("ret_126", ascending=False).head(1)
            if sub.empty:
                continue
            r = sub.iloc[0]
            other_rows.append(
                f"<tr><td style='padding:4px 8px'>{names[m]}</td>"
                f"<td><b>{r.Symbol}</b></td><td>{r.ret_126:+.0f}%</td>"
                f"<td style='color:{_COL.get(r.Liquidity, '#777')};font-weight:600'>{r.Liquidity}</td></tr>"
            )
    except Exception:
        pass

    # 8. 5y scoreboard
    p5 = mp.load()
    p_rows = [
        f"<tr><td style='padding:4px 8px'>{r.Market}</td><td>{r.Index}</td>"
        f"<td>{r['CAGR%']}</td><td>{r['Return_1y%']}</td><td>{r.Sharpe}</td></tr>"
        for _, r in p5.iterrows()
    ]

    # 9. Market Correlation Highlights — top clusters per market (NSE/US/Europe/Japan/Korea)
    try:
        corr_html = _corr_section()
    except Exception:
        corr_html = "<p class='mut' style='color:#777'>Correlation scan unavailable.</p>"

    html = f"""<div class="brief" style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:820px;width:100%;color:#1a1a1a;background:#ffffff">
<style>
h3{{font-size:14px;margin:14px 0 6px;color:#333}}
.trail{{overflow-x:auto;margin:6px 0}}
.trail table{{border-collapse:collapse;width:100%;font-size:12.5px}}
.trail th{{background:#eef;text-align:left;padding:5px 8px}}
.trail td{{padding:4px 8px;border-bottom:1px solid #f0f0f0}}

/* DARK MODE — this brief was unreadable in it.
   Every heading, the Convergence block and the Symbol column are set to greys
   (#333/#555/#777) on an implicit white page. A dark-theme client darkens the
   background but keeps those greys, so on 2026-07-21 the title, every section
   heading and the whole Convergence section rendered dark-on-dark: invisible,
   with no error and no clue that anything was missing.

   Overrides are deliberately NARROW — headings, muted text, table chrome. The
   inline green/red on gains, losses and sentiment carries meaning, so it is
   left alone; a blanket `.brief * {{color:...!important}}` would erase exactly
   the signal the colour is there to convey. */
@media (prefers-color-scheme: dark) {{
  .brief {{background:#151515 !important;color:#e8e8e8 !important}}
  .brief h1, .brief h2, .brief h3 {{color:#f3f3f3 !important}}
  .brief .muted, .brief .sub {{color:#b0b0b0 !important}}
  .brief .hd th {{background:#22304a !important;color:#f3f3f3 !important}}
  .brief td {{border-bottom-color:#2e2e2e !important}}
  .brief .note {{background:#221f14 !important;color:#e0dcc8 !important;
                 border-color:#5a4b1e !important}}
  .brief .liq {{background:#161d2b !important;color:#cfd8e8 !important}}
  .brief .tw {{background:transparent !important}}
}}
@media (max-width:600px) {{
  .brief h1 {{font-size:19px}}
  .brief h2 {{font-size:15px}}
  .brief table {{font-size:12px}}
}}
</style>
<h1 style="font-size:21px;margin:0 0 2px">📈 Daily Market Brief — {today}</h1>
<p class="sub" style="color:#666;font-size:13px;margin:0 0 10px">One block per market — screener, fundamentals, news and breakouts together · then global context</p>
{as_of_html}
<p class="liq" style="font-size:11px;color:#555;margin:0 0 14px;background:#f6f8fc;border-left:3px solid #1a73e8;padding:6px 9px"><b>These are HIGH-LIQUIDITY picks.</b> Liquidity is a screening criterion applied alongside Piotroski, Coffee Can and the other filters — every name below clears a median-turnover floor (~₹1cr/day in India, ~$120k elsewhere) <i>before</i> any fundamental test runs. In India that floor admits ~1,350 of ~7,800 listed equities; the ~4,500 lower-liquidity names are deliberately out of scope for now (harder to trade, data collected less regularly) and will be added as a separately-tagged tier once their collection is reliable. Untradable microcaps, ETFs and bonds are excluded. <b>Tier</b>: T1 mega ≥$12M/day · T2 large ≥$3M · T3 mid ≥$600k · T4 small ≥$120k.</p>
<h2 style="font-size:16px;border-bottom:2px solid #1a73e8;padding-bottom:3px">🌍 Market Snapshot</h2>
{snapshot_html}

<h2 style="font-size:16px;border-bottom:2px solid #1a73e8;padding-bottom:3px;margin-top:26px">🇮🇳 India <span style="font-weight:400;color:#666;font-size:13px">— mood {mood["mood"]} ({mood["score"]:+.2f}) from {mood.get("n_articles", 0)} articles</span></h2>
<h3 style="font-size:13px;margin:12px 0 4px;color:#333">Screener — most tradable</h3>
{_fund_coverage_note()}
{_coverage_scope_note()}
{_table(["Symbol", "Convergence", "P C B", "Value", "Technical", "Turnover", "Liquidity"], ind_picks_rows) if ind_picks_rows else "<p>no picks</p>"}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">Cash Conversion Cycle <span style="font-weight:400;color:#777" class="mut">(screener.in 228040)</span></h3>
<p style="font-size:11px;color:#666;margin:2px 0">Lowest/negative CCC = collects from customers before paying suppliers.</p>
{_table(["Symbol", "Name", "CCC days", "ROCE", "Liquidity"], ccc_rows) if ccc_rows else "<p>n/a</p>"}
{conv_in}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">🔥 News picks <span style="font-weight:400;color:#777" class="mut">— buzz, NOT a recommendation</span></h3>
{_table(["Symbol", "Name", "Sentiment", "Mentions", "Headline"], in_news_rows) if in_news_rows else "<p>n/a</p>"}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">🗞️ Talk on the Street <span style="font-weight:400;color:#777" class="mut">— per-ticker sentiment</span></h3>
{_table(["Symbol", "Sentiment", "Score", "Articles"], in_talk_rows) if in_talk_rows else "<p class='mut' style='color:#777'>No per-ticker news matches today.</p>"}
{darvas_in}

<h2 style="font-size:16px;border-bottom:2px solid #1a73e8;padding-bottom:3px;margin-top:26px">🇺🇸 US <span style="font-weight:400;color:#666;font-size:13px">— mood {us_mood["mood"]} ({us_mood["score"]:+.2f}) from {us_mood.get("n_articles", 0)} articles</span></h2>
<h3 style="font-size:13px;margin:12px 0 4px;color:#333">Screener — most tradable</h3>
{_table(["Symbol", "Convergence", "P C B", "Value", "Technical", "Turnover", "Liquidity"], us_picks_rows) if us_picks_rows else "<p>no picks (run daily_combined_report.py --market US)</p>"}
{conv_us}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">🔥 News picks <span style="font-weight:400;color:#777" class="mut">— buzz, NOT a recommendation</span></h3>
{_table(["Symbol", "Name", "Sentiment", "Mentions", "Headline"], us_news_rows) if us_news_rows else "<p>n/a</p>"}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">🗞️ Talk on the Street</h3>
{_table(["Symbol", "Sentiment", "Score", "Articles"], us_talk_rows) if us_talk_rows else "<p class='mut' style='color:#777'>No per-ticker news matches today.</p>"}
{darvas_us}

<h2 style="font-size:16px;border-bottom:2px solid #1a73e8;padding-bottom:3px;margin-top:26px">🌍 Global context</h2>
<h3 style="font-size:13px;margin:12px 0 4px;color:#333">Momentum — top 15 across 20 markets</h3>
{_table(["Mkt", "Symbol", "6mo %", "RSI"], g_rows)}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">Other markets — top tradable mover each <span style="font-weight:400;color:#777" class="mut">(≥$1M/day)</span></h3>
{_table(["Market", "Symbol", "6mo %", "Liquidity"], other_rows) if other_rows else "<p>n/a</p>"}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">20-market 5-year scoreboard</h3>
{_table(["Mkt", "Index", "5y CAGR%", "1y %", "Sharpe"], p_rows)}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">💱 Carry-trade FX <span style="font-weight:400;color:#777" class="mut">— the cross-asset channel into JP/KR/IN equities</span></h3>
{carry_html_}
<h3 style="font-size:13px;margin:14px 0 4px;color:#333">🔗 Correlation highlights</h3>
<p style="font-size:11px;color:#666;margin:2px 0">Top correlated-stock clusters per market, 1y returns. Statistical (not causal) groupings; they break down in stressed markets.</p>
{corr_html}
<p style="font-size:11px;color:#bf360c;border-top:1px solid #eee;padding-top:10px;margin-top:18px">⚠️ Educational/research only. NOT investment advice. Screener/Darvas/Convergence results are mechanical filters, not buy/sell signals. Liquidity/CCC are estimates; index figures price-only, local currency. Correlation clusters are statistical (not causal) groupings and can break down in stressed markets. Past performance does not guarantee future returns. Consult a SEBI-registered investment advisor.</p>
</div>"""

    text = (
        f"Daily Market Brief — {today}\n"
        f"Prices are last official closes, accurate as of generation "
        f"({_dt.datetime.now():%d %b %Y %H:%M}). Live quotes will differ.\n"
        f"India mood: {mood['mood']} ({mood['score']:+.2f}). US mood: {us_mood['mood']} ({us_mood['score']:+.2f}).\n"
        f"India/US/Europe/Japan/Korea screener picks + CCC + convergence + news picks + Darvas breakouts + "
        f"global momentum + 20-market 5y scoreboard + market correlation highlights.\n"
        f"Educational/research only. NOT investment advice."
    )
    subject = f"📈 Daily Market Brief — {today}"
    return subject, text, html


def _log_tokens_to_ruflo(subject: str, text: str, html: str, duration_seconds: float = 0):
    """Log token usage for watchlist_mailer to RUFLO monitoring system."""
    import json
    import subprocess
    from pathlib import Path

    # Estimate tokens: ~4 chars = 1 token (rough approximation)
    # More accurate: input (text size) + output (html size)
    input_chars = len(subject) + len(text)  # prompt + context
    output_chars = len(html)  # html output

    input_tokens = max(500, input_chars // 4)  # minimum 500 for model init
    output_tokens = max(2000, output_chars // 4)  # minimum 2000 for html generation

    token_data = {
        "taskId": "watchlist_mailer",
        "taskName": "Morning Watchlist Email",
        "model": "claude-3-5-haiku-20241022",
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "market": "india",
        "status": "success",
        "durationSeconds": duration_seconds
    }

    # Try to log to RUFLO
    try:
        logger_path = Path(__file__).parent.parent.parent.parent / ".ruflo" / "hooks" / "log-token-usage.js"
        if logger_path.exists():
            subprocess.run(
                ["node", str(logger_path)],
                input=json.dumps(token_data),
                text=True,
                capture_output=True,
                timeout=5
            )
    except Exception:
        pass  # Silent fail — don't break mailer if logging fails


if __name__ == "__main__":
    import time
    start_time = time.time()
    s, t, h = build()
    duration = time.time() - start_time
    open("brief_today.html", "w").write(h)
    print(s, "\n", t, "\nhtml bytes:", len(h))

    # Log to RUFLO
    _log_tokens_to_ruflo(s, t, h, duration_seconds=duration)
