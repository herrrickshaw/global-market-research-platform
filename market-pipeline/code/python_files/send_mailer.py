#!/usr/bin/env python3
# send_mailer.py
# ==============
# Build the Daily Market Brief and SEND it by email — with ZERO Claude/LLM tokens.
# This is the token-free replacement for the Gmail-draft-via-MCP step: pure Python
# + Gmail SMTP, so it can run unattended from cron/launchd.
#
# Credentials via environment (never hard-code):
#   GMAIL_USER          your gmail address
#   GMAIL_APP_PASSWORD  a Google "App Password" (Account → Security → App passwords)
#   MAIL_TO             recipient (defaults to GMAIL_USER)
#
#   python3 send_mailer.py            # build + send (or save .html if no creds)
#   python3 send_mailer.py --draft    # just write brief_today.html, don't send
#
# Nothing here calls an LLM: data, screeners, sentiment (VADER) and assembly are
# all local. The only network is market data + the SMTP send.

from __future__ import annotations

import os

import env_loader as _env
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from build_mailer import build

# 2026-08-12 (user): the brief covers India and the US — the two markets an
# Indian investor can actually trade — and nothing else. This switch controls
# the "Also watching" Darvas-count strip for tier 2/3 (EU/JP/KR + the weekly
# long tail). The scans behind it still run daily in daily_research.sh and
# still populate market_daily.snapshots; only the email stops carrying them.
# Set back to True to restore the strip — _technical_section() is unchanged.
INCLUDE_TECHNICAL_MARKETS = False


def _digest_section() -> tuple:
    """(html, subject_suffix) for the watchlist digest, appended below the
    brief so the morning is ONE email, not two (user, 2026-07-23).

    Failure-isolated on purpose: the digest importing half the pipeline must
    never block the brief — a broken digest renders as an error strip and the
    brief still ships. Running it here also runs watchlist hygiene (entry
    backfill, sell-zone eviction, >3-week purge) exactly once per morning.
    """
    try:
        import pandas as pd
        import watchlist_digest as W
        wl_path = Path(W.__file__).resolve().parent / "watchlist.csv"
        wl = pd.read_csv(wl_path)
        # 🔴 COVERAGE GATE AT THE POINT OF SEND (2026-07-29). watchlist_repair
        # prunes parked markets, but it runs FIRST in the pipeline while the
        # screeners that add rows run after it — so a JP/KR/EU name added during
        # today's run would sit in the file until tomorrow's prune and would be
        # MAILED tonight. Filtering here is what actually guarantees the brief
        # only carries markets whose fundamentals can support a per-name claim.
        # Applied to the digest's view only; the file itself is left to
        # watchlist_repair so the two do not fight over it.
        import watchlist_markets as WM
        _parked = wl[~wl["market"].map(WM.covered)].copy() if "market" in wl else wl.iloc[0:0]
        wl = WM.restrict(wl)
        if len(_parked):
            print(f"  digest: coverage gate held back {len(_parked)} row(s) "
                  f"outside {'/'.join(WM.COVERED)}")
        wl, evicted, purged, changed = W.maintain(wl)
        if changed:
            # 🔴 WRITE BACK THE PARKED ROWS TOO. maintain() returns only the
            # filtered frame, so persisting it alone would DELETE every JP/KR/EU
            # row from watchlist.csv silently and without archiving — turning a
            # display filter into data loss. watchlist_repair owns removal, and
            # it archives to watchlist_purged.csv with a reason; this path must
            # leave the file no smaller than it found it.
            pd.concat([wl, _parked], ignore_index=True).to_csv(wl_path, index=False)
        if evicted:
            print("  digest: evicted " + ", ".join(evicted))
        if purged:
            print("  digest: purged " + ", ".join(purged))
        frames = {}
        rows = W.build_rows(wl, frames_out=frames)
        W.assign_sectors(rows)
        W.assign_recommendations(rows)
        try:                                   # shadow-mode learned-model recs (IN/KR)
            W.annotate_learned(rows)
        except Exception as e:
            print(f"  digest: learned recs skipped ({e})")
        try:                                   # link SELL signals to the news flow
            from sell_news import annotate_sell_news
            annotate_sell_news(rows)
        except Exception as e:
            print(f"  digest: sell-news skipped ({e})")
        as_of = max([r["last"] for r in rows if r["last"]] or ["?"])
        # picks-based subject: the digest is portfolio-free (2026-07-23), so
        # the subject counts what the ANALYSIS found, not what is held
        picks = [r for r in rows if r.get("status") in ("watch", "signal", "justified")
                 and not r.get("missing") and not r.get("below_floor")]
        buy_n = sum(1 for r in picks if r.get("rec", r.get("zone")) == "BUY")
        new_n = sum(1 for r in picks
                    if r.get("days_in") is not None and r["days_in"] <= 1)
        # charts (treemap / RRG / breadth) — fail-soft PNGs. Body references
        # them as cid: inline images (image MIME parts do NOT count toward
        # Gmail's ~102KB HTML clip); the full attachment inlines them as data:
        # URIs so it stays a self-contained file.
        pngs = {}
        try:
            import watchlist_viz as V
            pngs = V.build_all(rows, frames, W.zone_series)
        except Exception as ve:  # noqa: BLE001
            print(f"  digest charts skipped: {str(ve)[:100]}")
        import base64
        cid_refs = {k: f"cid:{k}" for k in pngs}
        data_refs = {k: "data:image/png;base64," + base64.b64encode(v).decode()
                     for k, v in pngs.items()}
        # model portfolios: monthly-rebalanced co-movement bundles of the picks
        bundle_vals = []
        try:
            import portfolio_bundles as PB
            analysis = [r for r in rows
                        if r.get("status") in ("watch", "signal", "justified")]
            store = PB.maybe_build(analysis, frames)
            bundle_vals = PB.value(store, analysis, frames)
            if bundle_vals:
                print(f"  bundles: {len(bundle_vals)} model portfolios "
                      f"(built {store.get('built')})")
        except Exception as be:  # noqa: BLE001
            print(f"  bundles skipped: {str(be)[:100]}")
        # body = trimmed (stays under Gmail's ~102KB clip); attachment = the
        # SAME rows rendered untrimmed — attachments don't count toward the
        # clip, so nothing is lost, only demoted a click away.
        return (W.render(rows, as_of, purged=purged, images=cid_refs,
                         bundles=bundle_vals),
                f" + 📊 Picks ({len(picks)} · {buy_n} buy-zone · "
                f"{len(bundle_vals)} bundles)",
                W.render(rows, as_of, purged=purged, full=True, images=data_refs,
                         bundles=bundle_vals),
                pngs)
    except Exception as e:  # noqa: BLE001 — isolation is the whole point
        print(f"  digest section failed (brief still sent): {str(e)[:120]}")
        return (f'<p style="color:#ca3433;font-size:12px">watchlist digest '
                f'failed this morning: {str(e)[:200]}</p>', "", None, {})


def send(subject: str, text: str, html: str, attachments=None,
         inline_images=None) -> bool:
    """attachments: optional [(filename, html_str), ...] — attached as
    text/html files. inline_images: optional {cid: png_bytes} referenced from
    the body as <img src="cid:...">. Neither counts toward Gmail's ~102KB HTML
    clip, which is exactly why charts and the full digest ride here while the
    body stays trimmed.

    MIME shape: mixed( related( alternative(text, html), images... ), files )
    """
    from email.mime.image import MIMEImage

    user = _env.get("GMAIL_USER")
    pw = _env.get("GMAIL_APP_PASSWORD")
    to = (_env.get("MAIL_TO") or user)
    if not (user and pw) or len(pw) < 16 or "PUT-YOUR" in pw:
        Path("brief_today.html").write_text(html)
        print("  no valid GMAIL_APP_PASSWORD set — saved brief_today.html instead of sending")
        return False
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text, "plain"))
    alt.attach(MIMEText(html, "html"))
    core = alt
    if inline_images:
        core = MIMEMultipart("related")
        core.attach(alt)
        for cid, png in inline_images.items():
            img = MIMEImage(png, "png")
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=f"{cid}.png")
            core.attach(img)
    if attachments:
        msg = MIMEMultipart("mixed")
        msg.attach(core)
        for fname, content in attachments:
            part = MIMEText(content, "html")
            part.add_header("Content-Disposition", "attachment", filename=fname)
            msg.attach(part)
    else:
        msg = core
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())
    print(f"  sent '{subject}' → {to}"
          + (f" (+{len(attachments)} attachment)" if attachments else ""))
    # Durable proof that a brief went out, for anything that later needs to ask
    # "was one actually sent?" — the send was previously recorded ONLY as a line
    # of stdout, so no other process could tell. On 2026-07-29 the pipeline's
    # end-of-run alert reported "mailer: NOT SENT" at 08:08 from a FAILURES entry
    # recorded at 22:55, four and a half hours after a brief had in fact been
    # sent out-of-band at 03:36. Written after sendmail() returns, so it records
    # a send that happened, never one that was merely attempted. brief_state
    # owns the file and never raises here.
    import brief_state
    brief_state.record_sent(subject, to, os.getpid())
    return True


def _technical_section() -> str:
    """Tier 2 (EU/JP/KR, daily) + Tier 3 (everything else, weekly) Darvas
    signal counts — TECHNICAL ONLY, never a fundamentals-based pick. Added
    2026-07-31 per the user's 3-tier priority (market_tiers.py): tier 1
    (IN/US) keeps its full fundamentals-backed digest above unchanged;
    watchlist_markets.PARKED's reasons tier 2/3 can't carry a per-name
    fundamentals claim are still real and unchanged — this section only
    ever reports Darvas breakout counts from market_daily.snapshots, which
    weekly_extended_scan.py (tier 3) and the existing daily scans (tier 2)
    already populate. Failure-isolated like every other optional block
    here — must never block the core brief."""
    try:
        import pg_client
        import watchlist_markets as WM
        if not pg_client.connect():
            return ""
        conn = pg_client.get_connection()
        cur = conn.cursor()
        cur.execute("""
            WITH latest AS (
                SELECT market, MAX(as_of_date) AS d FROM market_daily.snapshots GROUP BY market
            )
            SELECT s.market, l.d,
                   COUNT(*) FILTER (WHERE s.darvas_signal ILIKE '%%BUY%%') AS signals,
                   COUNT(*) AS total
            FROM market_daily.snapshots s JOIN latest l ON s.market = l.market AND s.as_of_date = l.d
            GROUP BY s.market, l.d
        """)
        by_market = {WM.norm(m): (asof, sig, tot) for m, asof, sig, tot in cur.fetchall()}

        def _row(tier: int, label: str) -> str:
            parts = []
            for m in WM.technical_markets(tier):
                hit = by_market.get(m)
                if not hit:
                    continue
                asof, sig, tot = hit
                parts.append(f"{m} {sig}/{tot} ({asof:%d %b})")
            return (f'<div style="margin:3px 0"><b>{label}:</b> ' + " · ".join(parts) + "</div>"
                    if parts else "")

        t2 = _row(2, "Tier 2 — daily, technical only")
        t3 = _row(3, "Tier 3 — weekly, technical only")
        if not (t2 or t3):
            return ""
        return (
            '<div style="background:#eef4f6;border-left:4px solid #0B2F4A;'
            'padding:10px 14px;margin:12px 0;border-radius:6px;font-size:13px">'
            '<b>📈 Also watching (Darvas breakout counts, no fundamentals claim)</b>'
            + t2 + t3 +
            '<div style="color:#777;font-size:11px;margin-top:4px">Tier 2/3 fundamentals '
            'coverage gap is unchanged (see watchlist_markets.PARKED) — these counts are '
            'price/volume signals only, never a per-name pick.</div></div>')
    except Exception as e:  # noqa: BLE001 — isolation is the whole point
        print(f"  technical section skipped: {str(e)[:100]}")
        return ""


def _csv(path: Path, **kw):
    """A DataFrame from `path`, or an EMPTY one if the file is missing, empty or
    unparseable. The 1-byte file reentry_engine writes on a zero-pick day made
    pandas raise EmptyDataError, and the except around the whole prediction
    block dropped every other line with it — 21 of ~30 briefs from 2026-09-15
    shipped without the section. A missing optional input is "nothing to say",
    never "say nothing"."""
    import pandas as pd
    try:
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()
        return pd.read_csv(path, **kw)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, ValueError):
        return pd.DataFrame()


def prediction_section(root: Path | str = ".") -> str:
    """Prediction-lens block (2026-07-27): verdict counts from the routine
    prediction filter + RSI zones + held SELL-REVIEW names + tiers + re-entry
    + today's prediction purges. Each optional line is guarded on its own, so
    one bad file costs one line, not the section. '' when there are no scores."""
    import pandas as pd

    import watchlist_markets as WM
    root = Path(root)
    s = _csv(root / "reports/watchlist_prediction_scores.csv")
    if s.empty or "verdict" not in s.columns:
        return ""
    vc = s["verdict"].astype(str).str.split(" ").str[0].value_counts()
    cnt = " · ".join(f"{k} {v}" for k, v in vc.items())
    rows = ""

    def line(label, fn):
        nonlocal rows
        try:
            rows += fn() or ""
        except Exception as e:                                        # noqa: BLE001
            print(f"  prediction: {label} line skipped: {str(e)[:60]}")

    def rsi():
        if "rsi_zone" not in s.columns:
            return ""
        rz = s["rsi_zone"].value_counts()
        return ('<div style="margin:4px 0"><b>RSI zones</b> '
                '(per-market read: momentum IN, mean-revert US): '
                + " · ".join(f"{k} {v}" for k, v in rz.items() if k != "?") + '</div>')

    def sell_review():
        h = _csv(root / "reports/held_sell_review.csv")
        if h.empty:
            return ""
        names = ", ".join(f"{r.symbol} ({float(r.kalman_drift_ann_pct):+.0f}%/yr)"
                          for r in h.head(12).itertuples())
        return (f'<div style="margin:4px 0"><b>SELL-REVIEW (held, bear state + neg drift):</b> '
                f'{names}' + (f" +{len(h)-12} more" if len(h) > 12 else "") + '</div>')

    def tiers():
        if not (root / "watchlist2.csv").exists():
            return ""
        w2, w3 = _csv(root / "watchlist2.csv"), _csv(root / "watchlist3.csv")
        t = f'<div style="margin:4px 0"><b>Tiers:</b> validation watchlist (2) {len(w2)} names'
        if len(w3):
            anoms = ", ".join(f"{r.symbol} ({r.trigger})" for r in w3.tail(5).itertuples())
            t += f' · <b>anomalies (3): {len(w3)}</b> — {anoms}'
        else:
            t += ' · anomalies (3): 0'
        return t + '</div>'

    def reentry_queue():
        import datetime as dtt
        p = root / "reports/reentry_candidates.csv"
        if not p.exists():
            return ""
        fresh = (dtt.date.today() - dtt.date.fromtimestamp(p.stat().st_mtime)).days <= 1
        rc = WM.restrict(_csv(p) if fresh else pd.DataFrame())
        if rc is None or rc.empty:
            return ""
        names = ", ".join(f"{r.market}:{r.symbol} (rsi {float(r.rsi):.0f})"
                          for r in rc.head(8).itertuples())
        # 🔴 THE EDGE CLAIM HERE WAS WITHDRAWN 2026-07-29. This block once
        # advertised "backtested excess +5-25%/63d, t 7-15"; the report it came
        # from now measures IN 63d at excess -2.01% median, t=0.06, and an
        # independent re-run agrees at t=0.27 on n=508. A retracted figure
        # outlives its retraction wherever it was copied — do not restore it.
        return (f'<div style="margin:4px 0"><b>↩ Re-entry queue '
                f'(mean-reversion engine, UNVALIDATED):</b> {names} '
                f'— <span style="color:#b00">no measured forward edge (t=0.06); '
                f'paper-track only</span></div>')

    def reentry_recent():
        rrd = WM.restrict(_csv(root / "reports/reentry_recent.csv", parse_dates=["trigger_date"]))
        if rrd is None or rrd.empty:
            return ""
        by = rrd.groupby("market").size().to_dict()
        top = "; ".join(f"{r.market} {r.symbol} ({r.trigger_date:%d %b}, +{r.ret_at_trigger:.0f}%)"
                        for r in rrd.head(10).itertuples())
        return (f'<div style="margin:4px 0"><b>Recent re-entry names (last 45d):</b> '
                f'{sum(by.values())} — ' + " · ".join(f"{k} {v}" for k, v in by.items())
                + f'<br><span style="font-size:12px">{top}</span></div>')

    def purged():
        p = _csv(root / "watchlist_purged.csv")
        if p.empty or "note" not in p.columns:
            return ""
        note = p["note"].astype(str)
        today = p[note.str.contains("prediction", case=False)
                  & note.str.contains(pd.Timestamp.today().strftime("%Y-%m-%d"))]
        if today.empty:
            return ""
        return (f'<div style="margin:4px 0"><b>Purged today (prediction filter):</b> '
                f'{len(today)} names — ' + ", ".join(today["symbol"].astype(str).head(10))
                + (" …" if len(today) > 10 else "") + '</div>')

    for label, fn in (("rsi", rsi), ("sell-review", sell_review), ("tiers", tiers),
                      ("re-entry queue", reentry_queue), ("re-entry recent", reentry_recent),
                      ("purged", purged)):
        line(label, fn)

    return ('<div style="background:#f4f0e8;border-left:4px solid #8a6d3b;'
            'padding:10px 14px;margin:12px 0;border-radius:6px;font-size:13px">'
            '<b>🔮 Prediction lens</b> (market regime × stock Markov state × '
            f'Kalman drift): {cnt}' + rows +
            '<div style="color:#777;font-size:11px;margin-top:4px">Kalman drift '
            'is a ranking, not a forecast; Markov 21d column vetoes ENTER-OK. '
            'Held names are never auto-purged — SELL-REVIEW is advisory.</div></div>')


if __name__ == "__main__":
    import datetime as _dt

    subject, text, html = build()
    digest_html, digest_subj, digest_full, pngs = _digest_section()
    technical_html = _technical_section() if INCLUDE_TECHNICAL_MARKETS else ""

    # Web copy of the full watchlist (2026-07-27): upload to GDrive via rclone
    # and put the share link at the top of the digest — the attachment stays,
    # but the link opens on any device without downloading. Never fatal.
    wl_link = ""
    if digest_full:
        try:
            import subprocess as _sp
            _wl = Path("watchlist_full.html")
            _wl.write_text(digest_full)
            _sp.run(["rclone", "copy", str(_wl), "gdrive:/Market-Reports/"],
                    capture_output=True, timeout=60)
            _r = _sp.run(["rclone", "link", "gdrive:/Market-Reports/watchlist_full.html"],
                         capture_output=True, text=True, timeout=30)
            _url = next((l.strip() for l in _r.stdout.splitlines()
                         if l.startswith("http")), "")
            if _url:
                wl_link = (f'<p style="margin:10px 0"><a href="{_url}" '
                           f'style="color:#0B2F4A;font-weight:bold">📋 Full watchlist '
                           f'(web copy — always the latest send)</a></p>')
        except Exception as _e:
            print(f"  watchlist link skipped: {str(_e)[:60]}")

    pred_html = prediction_section()

    html = (html
            + '<div style="margin:22px 0 10px;border-top:3px solid #0B2F4A"></div>'
            + wl_link
            + pred_html
            + technical_html
            + digest_html)
    subject += digest_subj

    # --tag "<label>" prefixes the subject, e.g. `--tag "TEST 2"` -> "[TEST 2] …".
    # Readability trials send the same brief again on a day it has already gone
    # out, and the generated subject is identical every time — two indistinguishable
    # copies in the inbox, with no way to tell which one the feedback is about.
    # The tag also keeps a test out of the real morning brief's thread.
    _tag = ""
    if "--tag" in sys.argv:
        _i = sys.argv.index("--tag")
        if _i + 1 < len(sys.argv):
            _tag = sys.argv[_i + 1].strip()
    if _tag:
        subject = f"[{_tag}] {subject}"

    attachments = None
    if digest_full:
        fname = f"watchlist_full_{_dt.date.today():%Y-%m-%d}.html"
        attachments = [(fname, digest_full)]
    # bundle-validation report (monthly refresh, [16c]) rides as a small HTML
    # attachment so the "are we closet-indexing?" answer travels with the picks
    bv = Path("reports/bundle_validation.md")
    if attachments and bv.exists():
        import re as _re
        md = bv.read_text()
        h = md
        h = _re.sub(r"^## (.+)$", r'<h2 style="color:#0B2F4A;font-size:15px;margin:14px 0 4px">\1</h2>', h, flags=_re.M)
        h = _re.sub(r"^# (.+)$", r'<h1 style="color:#0B2F4A;font-size:18px">\1</h1>', h, flags=_re.M)
        h = _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", h)
        h = _re.sub(r"^- (.+)$", r'<div style="margin:2px 0 2px 12px">• \1</div>', h, flags=_re.M)
        h = ('<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
             'max-width:680px;font-size:13px;color:#333;background:#eef4f6;'
             'padding:14px;border-radius:8px">'
             + h.replace("\n\n", "<br>") + "</div>")
        attachments.append((f"bundle_validation_{_dt.date.today():%Y-%m}.html", h))
    # Utility layer (2026-07-27): publish the brief to a STABLE GDrive URL on
    # every send — availability (any device, no email client), latency
    # (pre-rendered static HTML), UX (same designed page), zero cost. The edge
    # layer (validated data, tested signals) already lives in the content;
    # this closes the Google-Finance utility gap for our own data.
    try:
        import subprocess as _sp2
        Path("brief_today.html").write_text(html)
        _sp2.run(["rclone", "copy", "brief_today.html", "gdrive:/Market-Reports/"],
                 capture_output=True, timeout=60)
    except Exception as _e:
        print(f"  brief publish skipped: {str(_e)[:60]}")

    if "--draft" in sys.argv:
        Path("brief_today.html").write_text(html)
        if digest_full:
            Path("watchlist_full.html").write_text(digest_full)
            print("  full digest draft → watchlist_full.html")
        for k, v in pngs.items():
            Path(f"digest_{k}.png").write_bytes(v)
        if pngs:
            print(f"  charts → {', '.join('digest_' + k + '.png' for k in pngs)}")
        print(f"  draft saved → brief_today.html ({subject})")
    else:
        send(subject, text, html, attachments=attachments, inline_images=pngs)
