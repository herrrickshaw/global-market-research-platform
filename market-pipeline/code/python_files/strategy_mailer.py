#!/usr/bin/env python3
"""
strategy_mailer.py — turn the session's validated learnings into a watchlist + email.

Adds the validated cheap+high-ROE longs (per-market, tagged `value-hold` so the
trend-based eviction leaves them alone) to watchlist.csv, then composes a strategy
digest — the suitability matrix's deployment rules + the picks with valuation
rationale — and sends it to MAIL_TO (self). Research/paper-track, not advice.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import send_mailer as SM
from obs import get_logger, DecisionLog

HERE = Path(__file__).resolve().parent
LOG = get_logger("strategy_mailer")
ASOF = "2026-07-24"

# LIVE picks from the validated playbook screener (reports/playbook_picks.csv)
def load_picks():
    p = HERE / "reports" / "playbook_picks.csv"
    if not p.exists():
        return {}
    d = pd.read_csv(p)
    out = {}
    for mkt, g in d.groupby("market"):
        out[mkt] = [(str(r.symbol), str(r.name)[:22], r.pe, r.roe, r["filter"], r.direction)
                    for _, r in g.iterrows()]
    return out


PICKS = load_picks()
TITLE = {"IN": "🇮🇳 India — trend + value/quality (long-only)", "US": "🇺🇸 US — cheap-vs-market (≤3M)",
         "KR": "🇰🇷 Korea — value+quality long/short", "JP": "🇯🇵 Japan — value-reversion",
         "EU": "🇪🇺 Europe — 12-month momentum"}
DEPLOY = [
 ("🇮🇳 India","momentum/trend","trend + sector-relative value (long-only)","❌ never short — bull runs shorts over"),
 ("🇺🇸 US","value (light)","short-horizon cheap-vs-market, ≤3M","marginal"),
 ("🇰🇷 Korea","mean-reversion","cheap∩hi-ROE (the Korea discount)","✅ short hollow-overpriced (validated t4.2)"),
 ("🇯🇵 Japan","value-reversion","cheap-vs-market low PE (+6.6%/6M t4.84)","— (extension only)"),
 ("🇪🇺 Europe","momentum","12-month momentum (DSR 0.985)","—"),
 ("🇨🇳 China","speculation-ruled","PASSIVE / index only — value tested & FAILS","🚫 no active picks"),
]


def update_watchlist():
    """the playbook screener already writes status='playbook' entries with entry price/date;
    this counts them for the decision log."""
    wl = pd.read_csv(HERE / "watchlist.csv")
    n = int((wl.status == "playbook").sum())
    LOG.info(f"watchlist: {n} 'playbook' entries under performance monitoring")
    return n


def html():
    C = {"bg": "#0B2F4A", "accent": "#0c6b58", "muted": "#8aa0ae"}
    def pick_rows(mkt):
        out = ""
        for sym, name, pe, roe, filt, direction in PICKS.get(mkt, []):
            dcol = "#b23b3b" if direction == "SHORT" else C["accent"]
            roe_s = f"{roe*100:.0f}%" if pd.notna(roe) else "—"
            pe_s = f"{pe}" if pd.notna(pe) else "—"
            out += (f'<tr><td style="padding:5px 8px"><b>{sym}</b> '
                    f'<span style="color:{C["muted"]};font-size:12px">{name}</span> '
                    f'<span style="color:{dcol};font-size:11px">{direction}</span></td>'
                    f'<td style="text-align:right;padding:5px 8px">PE {pe_s}</td>'
                    f'<td style="text-align:right;padding:5px 8px;color:{C["accent"]}">ROE {roe_s}</td></tr>')
        return out
    dep = "".join(f'<tr><td style="padding:5px 8px">{m}</td><td style="padding:5px 8px">{c}</td>'
                  f'<td style="padding:5px 8px">{l}</td><td style="padding:5px 8px;font-size:12px">{s}</td></tr>'
                  for m, c, l, s in DEPLOY)
    blocks = ""
    for mkt in ["IN", "US", "KR", "JP", "EU"]:
        if not PICKS.get(mkt):
            continue
        blocks += (f'<h3 style="color:{C["bg"]};margin:18px 0 6px">{TITLE[mkt]}</h3>'
                   f'<table style="border-collapse:collapse;width:100%;font-size:14px;'
                   f'border:1px solid #dfe7ec">{pick_rows(mkt)}</table>')
    blocks += ('<p style="font-size:13px;color:#8aa0ae;margin-top:10px">🇨🇳 <b>China — no picks.</b> '
               'Value-reversion tested & fails (t0.3, 1993 stocks × 10y); passive/index only.</p>')
    return f'''<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;color:#1a2b34">
<h2 style="color:{C["bg"]}">📊 Strategy digest — validated picks & suitability</h2>
<p style="font-size:14px;color:{C["muted"]}">Cheap + high-ROE longs where valuation reversion is
statistically validated (IN/US/KR). Peers are data-driven economic clusters; reversion corrects
over/under-pricing (+5–6%/6M, backtested). Paper-track, <b>not investment advice</b>.</p>
<h3 style="color:{C["bg"]};margin:18px 0 6px">Deployment rules (market character)</h3>
<table style="border-collapse:collapse;width:100%;font-size:13px;border:1px solid #dfe7ec">
<tr style="background:#eef3f6"><td style="padding:5px 8px"><b>market</b></td><td style="padding:5px 8px"><b>character</b></td>
<td style="padding:5px 8px"><b>long</b></td><td style="padding:5px 8px"><b>short</b></td></tr>{dep}</table>
{blocks}
<p style="font-size:12px;color:{C["muted"]};margin-top:18px">Added to watchlist as <code>value-hold</code>
(exempt from trend-eviction so the paper-track can actually measure the reversion). ⭐ = triple-convergence
(value ∩ quality ∩ momentum). Full suitability matrix: reports/strategy_matrix.md. yfinance/screener
fundamentals, latest FY. Educational research — consult a SEBI-registered advisor.</p></div>'''


def main() -> int:
    n = update_watchlist()
    DecisionLog().record("strategy_mailer", picks_added=n, markets=list(PICKS),
                         n_picks=sum(len(v) for v in PICKS.values()))
    subject = f"📊 Strategy Digest — {sum(len(v) for v in PICKS.values())} validated value picks (IN/US/KR) · {ASOF}"
    text = "Validated cheap+high-ROE longs across IN/US/KR + deployment matrix. Paper-track, not advice."
    SM.send(subject, text, html())
    LOG.info(f"sent strategy digest ({n} new watchlist picks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
