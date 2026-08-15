#!/usr/bin/env python3
# price_sources.py
# ================
# Independent close-price lookups for validate_brief.py, plus a running ledger of
# how well each source has actually held up.
#
# WHY THIS EXISTS. The brief gate used to have exactly one witness, screener.in,
# and inherited that witness's quirks as if they were facts about the data. The
# worst of them: screener.in only prints "<date> - close price" while the market
# is SHUT. Once NSE opens it serves an undated live quote, so mid-session the
# gate could not prove it was comparing closes at all and had to suppress. On
# 2026-08-11 that blocked a brief whose six sampled names all agreed to within
# 0.9% — the data was fine, the witness just could not testify at that hour.
#
# 🔴 THE FIX IS NOT "SCRAPE A DIFFERENT SITE". Any live-quote page has the same
# defect: at 11:00 IST nothing that quotes the current price can tell you what
# the last close was. The fix is to ask a DATE-ANCHORED question — "what did this
# close at on or before <date>?" — which has a stable answer at any hour. Sources
# below therefore return (price, date) and the caller compares BOTH.
#
# 🔴 INDEPENDENCE IS THE WHOLE POINT. The India scan is built from NSE/BSE
# bhavcopy, so bhavcopy must never appear here: validating a file against the
# file it was made from is circular and proves nothing. Every source here reaches
# the market by a different path than the scan did.

from __future__ import annotations

import datetime as _dt
import json
import re
import sqlite3
import time
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (research)"}


def _get(url: str, tries: int = 3, timeout: int = 25):
    """
    GET with backoff on THROTTLING ONLY.

    🔴 A THROTTLE AND A 404 MEAN OPPOSITE THINGS HERE, AND RETRYING BOTH WOULD BE
    WRONG. screener.in 404s for every BSE-only name on the NSE-shaped URL — that
    is a real, permanent answer ("I don't cover this"), and retrying it three
    times would triple the request volume against the very host we are trying not
    to annoy, while changing nothing. So only 429 and 5xx are retried; 4xx comes
    straight back.

    Why this matters for the send gate: a source that errors is dropped from the
    quorum in validate_brief, and the brief is suppressed when too few sources
    answer. Before this, one 429 during the 06:30 window was enough to lose a
    source silently — indistinguishable from that source disagreeing. A
    suppressed brief is a lost deliverable, so it should take a genuine
    disagreement, not a rate limiter.

    Honours Retry-After when the server sends it; otherwise exponential backoff
    with jitter so parallel callers do not re-collide in lockstep.
    """
    import random
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
        except Exception as e:                                 # noqa: BLE001
            last = e
            if attempt == tries - 1:
                raise
            time.sleep((2 ** attempt) + random.uniform(0, 0.5))
            continue
        if r.status_code == 429 or 500 <= r.status_code < 600:
            if attempt == tries - 1:
                return r
            wait = r.headers.get("Retry-After")
            try:
                delay = float(wait) if wait else (2 ** attempt) + random.uniform(0, 0.5)
            except ValueError:
                delay = (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(min(delay, 30))
            continue
        return r
    raise last if last else RuntimeError("unreachable")


_LEDGER = Path(__file__).resolve().parent / "state" / "source_accuracy.db"


# ─── sources ──────────────────────────────────────────────────────────────────
# Each returns {"price": float, "date": date} or {"error": str}. An error means
# "this witness could not testify", NOT "the pick is bad" — the caller must keep
# those apart, because conflating them is how a flaky network becomes a fake
# price mismatch.

def _yfinance(sym: str, asof: _dt.date) -> dict:
    """Latest close on or before `asof`. Date-anchored, so market hours are irrelevant."""
    try:
        import yfinance as yf
        # Reach back far enough to survive a long holiday run, then take the last
        # row: asking for a single day returns nothing on a holiday and would read
        # as "no data" rather than "the close you want is a few days back".
        h = yf.Ticker(f"{sym}.NS").history(
            start=asof - _dt.timedelta(days=12),
            end=asof + _dt.timedelta(days=1), auto_adjust=False)
        if h is None or not len(h):
            return {"error": "no rows"}
        # 🔴 DROP NaN CLOSES BEFORE TAKING THE LAST ROW. Yahoo emits a row for a
        # session whose close it does not have yet — measured 2026-08-12 04:38
        # IST, where 2026-08-11 came back present-but-NaN for every name tested.
        # Taking iloc[-1] blindly returned NaN, which then propagates into the
        # diff and surfaces as a phantom price mismatch: the gate would suppress
        # a perfectly good brief and blame the data. An absent close must read as
        # "no answer", never as an answer of NaN.
        h = h[h["Close"].notna()]
        if not len(h):
            return {"error": "no close yet"}
        return {"price": float(h["Close"].iloc[-1]), "date": h.index[-1].date()}
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"yf: {str(e)[:60]}"}


def _stooq(sym: str, asof: _dt.date) -> dict:
    """Stooq's daily CSV. Independent of both Yahoo and screener.in."""
    try:
        r = _get(f"https://stooq.com/q/d/l/?s={sym.lower()}.in&i=d")
        if r.status_code != 200 or "Date" not in r.text[:64]:
            return {"error": f"http {r.status_code}"}
        best = None
        for line in r.text.strip().splitlines()[1:]:
            parts = line.split(",")
            if len(parts) < 5:
                continue
            try:
                d = _dt.date.fromisoformat(parts[0])
            except ValueError:
                continue
            if d <= asof and (best is None or d > best[0]):
                best = (d, float(parts[4]))
        return {"price": best[1], "date": best[0]} if best else {"error": "no rows"}
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"stooq: {str(e)[:60]}"}


def _screener(sym: str, asof: _dt.date) -> dict:
    """screener.in's header. Kept as one voice among several, no longer the only one.

    Returns an error rather than a price when the header carries no close date —
    that is the market-open case, and an undated live tick is not evidence about
    a close. Downgrading it to a price-only check is precisely the silent pass
    that let the 2026-07-15 stale pick through.
    """
    try:
        r = _get(f"https://www.screener.in/company/{sym}/")
        if r.status_code != 200:
            # BSE-only names 404 on the NSE-shaped URL. Unverifiable here, not bogus.
            return {"error": f"http {r.status_code}"}
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")
        top = soup.select_one("#top") or soup
        txt = re.sub(r"\s+", " ", top.get_text(" ", strip=True))[:400]
        price = re.search(r"₹\s*([\d,]+(?:\.\d+)?)", txt)
        dm = re.search(r"(\d{1,2}\s+[A-Z][a-z]{2})\s*-?\s*close price", txt)
        if not price:
            return {"error": "no price in header"}
        if not dm:
            return {"error": "live quote (no close date)"}
        day, mon = dm.group(1).split()
        d = _dt.datetime.strptime(f"{day} {mon} {asof.year}", "%d %b %Y").date()
        # screener prints "11 Aug" with no year, so a date landing after `asof`
        # is ambiguous: either last December read as this December (a real year
        # rollover) or simply a close NEWER than the day we asked about. Only the
        # first is a year error. Rolling back on any overshoot dated a 2026-08-11
        # close as 2025-08-11 — a year-stale reading of perfectly current data,
        # which the date check would then report as catastrophic staleness.
        if (d - asof).days > 180:
            d = d.replace(year=asof.year - 1)
        return {"price": float(price.group(1).replace(",", "")), "date": d}
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"screener: {str(e)[:60]}"}


# 🔴 stooq is DELIBERATELY ABSENT despite _stooq() existing above. Measured
# 2026-08-12: stooq.com/q/d/l/ returns an HTML page rather than CSV for NSE names
# under every suffix tried (.in, .ns, bare), i.e. it does not serve this market.
# Registering a source that can never answer would not make the gate stronger —
# it would add a permanent 100%-error column to the accuracy ledger and dilute
# the very track record the ledger exists to measure. Kept as a function so the
# next person can re-test it cheaply rather than rediscover the finding.
#
# That leaves two witnesses, which is enough for the agreed rule (pass on one,
# suppress on zero) — and crucially yfinance is date-anchored, so unlike
# screener.in it can testify DURING market hours. That alone closes the gap that
# suppressed the 2026-08-11 brief.
SOURCES = {"yfinance": _yfinance, "screener": _screener}


# ─── ledger ───────────────────────────────────────────────────────────────────

def _db() -> sqlite3.Connection:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(_LEDGER)
    # DELETE journal, not WAL: this lives under a synced home directory and WAL
    # sidecars there have corrupted before.
    c.execute("PRAGMA journal_mode=DELETE")
    c.execute("""CREATE TABLE IF NOT EXISTS source_check (
                   run_ts TEXT, asof TEXT, symbol TEXT, source TEXT,
                   ours REAL, theirs REAL, diff_pct REAL,
                   their_date TEXT, verdict TEXT, error TEXT)""")
    return c


def record(rows: list[dict]) -> None:
    """Append this run's per-source outcomes. Never raises: the ledger is
    bookkeeping, and a bookkeeping fault must not be able to block a send."""
    if not rows:
        return
    try:
        with _db() as c:
            c.executemany(
                "INSERT INTO source_check VALUES (:run_ts,:asof,:symbol,:source,"
                ":ours,:theirs,:diff_pct,:their_date,:verdict,:error)", rows)
    except Exception as e:                                     # noqa: BLE001
        print(f"  (source ledger write failed, continuing: {type(e).__name__}: {e})")


def report(days: int = 30) -> list[dict]:
    """Per-source track record over the last `days`. This is the point of the
    ledger: after a few weeks it says which witnesses are worth listening to,
    measured rather than assumed."""
    since = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    try:
        with _db() as c:
            rows = c.execute("""
                SELECT source,
                       COUNT(*)                                        AS n,
                       SUM(error IS NOT NULL AND error != '')          AS errs,
                       SUM(verdict='agree')                            AS agree,
                       SUM(verdict='disagree')                         AS disagree,
                       ROUND(AVG(CASE WHEN verdict IN ('agree','disagree')
                                      THEN ABS(diff_pct) END), 3)      AS avg_abs_diff
                  FROM source_check WHERE asof >= ? GROUP BY source ORDER BY source""",
                (since,)).fetchall()
    except Exception as e:                                     # noqa: BLE001
        print(f"  (source ledger unreadable: {e})")
        return []
    out = []
    for src, n, errs, agree, dis, avg in rows:
        answered = n - (errs or 0)
        out.append({
            "source": src, "checks": n,
            "response_rate": round(answered / n * 100, 1) if n else 0.0,
            "agree_rate": round((agree or 0) / answered * 100, 1) if answered else 0.0,
            "disagreements": dis or 0,
            "avg_abs_diff_pct": avg,
        })
    return out


def fetch_all(sym: str, asof: _dt.date, polite: float = 0.6) -> dict:
    """Ask every source for `sym`'s close on/before `asof`. Returns {name: result}."""
    out = {}
    for name, fn in SOURCES.items():
        out[name] = fn(sym, asof)
        time.sleep(polite)
    return out


if __name__ == "__main__":
    import sys
    if "--report" in sys.argv:
        print(json.dumps(report(), indent=1))
    else:
        s = sys.argv[1] if len(sys.argv) > 1 else "RELIANCE"
        print(json.dumps(
            {k: {kk: str(vv) for kk, vv in v.items()}
             for k, v in fetch_all(s, _dt.date.today()).items()}, indent=1))
