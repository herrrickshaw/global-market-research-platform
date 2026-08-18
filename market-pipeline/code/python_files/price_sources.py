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
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode

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


_CREDS = Path.home() / ".config" / "market-secrets" / "credentials.env"


def _key(name: str) -> str | None:
    """Read one key from the canonical credential store.

    Parsed here rather than sourced: the file has a value containing shell
    metacharacters and `. credentials.env` dies on it under zsh with a parse
    error, which would take the gate down for a reason that has nothing to do
    with prices. Env var wins so a run can override without touching the file.
    """
    v = os.environ.get(name)
    if v:
        return v
    try:
        for ln in _CREDS.read_text().splitlines():
            m = re.match(rf"\s*{re.escape(name)}=(.*)$", ln)
            if m:
                v = m.group(1).strip().strip('"').strip("'")
                return v or None
    except OSError:
        return None
    return None


def _alphavantage(sym: str, asof: _dt.date) -> dict:
    """Alpha Vantage daily bars. The third path to this market, after Yahoo and screener.in.

    🔴 QUOTES BSE, NOT NSE — and that is deliberate, not a defect. The `.NSE`
    suffix returns an empty series (measured 2026-08-18); only `.BSE` resolves.
    So this witness reaches the market through a DIFFERENT EXCHANGE than the scan,
    which is exactly the independence the gate wants — but it means a small basis
    against our NSE close is normal and must not read as a mismatch. Measured the
    same day across the gate's own sample, all on the correct 2026-08-17 date:

        BHARTIARTL 0.010% · HDFCBANK 0.137% · INFY 0.167%
        RELIANCE   0.183% · ICICIBANK 0.183% · SBIN 0.263%

    Worst 0.263% against a 2.0% tolerance — 7x headroom. Picks are liquidity-gated
    so they trade actively on both exchanges; if that gate is ever loosened, this
    basis widens and this comment is where to start looking.

    🔴 FREE TIER IS 25 REQUESTS/DAY. The gate samples ~6 names, so one run costs 6.
    That leaves room for a retry but NOT for a second daily caller — anything else
    reaching for this key will silently starve the send gate. Alpha Vantage answers
    a quota refusal with HTTP 200 and a prose "Note"/"Information" body rather than
    an error status, so the absent-series branch below reports it as an error and
    the source drops out of the quorum instead of being read as "no data".
    """
    k = _key("ALPHAVANTAGE_KEY")
    if not k:
        return {"error": "no ALPHAVANTAGE_KEY"}
    try:
        r = _get("https://www.alphavantage.co/query?" + urlencode({
            "function": "TIME_SERIES_DAILY", "symbol": f"{sym}.BSE",
            "apikey": k, "outputsize": "compact"}))
        if r.status_code != 200:
            return {"error": f"http {r.status_code}"}
        j = r.json()
        ts = j.get("Time Series (Daily)")
        if not ts:
            # Quota/throttle notes and unknown tickers both land here. Keep the
            # first words of whichever key came back so the ledger distinguishes
            # "we ran out of quota" from "this name is not covered".
            note = (j.get("Note") or j.get("Information")
                    or j.get("Error Message") or "no series")
            return {"error": f"av: {str(note)[:70]}"}
        days = [d for d in ts if d <= asof.isoformat()]
        if not days:
            return {"error": "no rows on/before asof"}
        d = max(days)
        return {"price": float(ts[d]["4. close"]),
                "date": _dt.date.fromisoformat(d)}
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"av: {str(e)[:60]}"}


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
# 🔴 screener IS NO LONGER REGISTERED (2026-08-18, by request: witness this market
# some other way). _screener() is kept above, working, so restoring it is adding
# one dict entry — same treatment _stooq gets, and for the same reason: the
# finding should be cheap to revisit.
#
# THE SEARCH THAT PRODUCED THIS LINE. Everything below was tested against the
# gate's own sample on 2026-08-18, all six names, known-good 2026-08-17 NSE closes:
#
#   alphavantage  WORKS via .BSE — registered. Worst basis 0.263% vs 2.0% tol.
#   EODHD         404 Ticker Not Found on .NSE and .BSE. Key is a FREE plan
#                 (20 req/day) and India is not in it. Revisit only if upgraded.
#   stooq         re-tested per the note above: still HTML, not CSV, on .in/.ns/
#                 .bo/bare. The 2026-08-12 finding holds — it does not serve NSE.
#   nsepython     equity_history raises KeyError('data') standalone; it needs
#                 browser cookies, which is not something an unattended 06:30 job
#                 should depend on. (Installed, so cheap to re-check.)
#   moneycontrol  priceapi techCharts endpoint no longer returns JSON.
#   Hugging Face  no live feed exists. Of 100 'stock' datasets, 3 are India-related
#                 and all are static bulk dumps (newest touched 2026-08-13, one
#                 abandoned in 2023). A gate needs YESTERDAY's close; a snapshot
#                 hub structurally cannot serve that. Dead end, not a near miss.
#   PyPI survey   jugaad-data is maintained but reads NSE bhavcopy — CIRCULAR, it
#                 is the scan's own source. yahooquery is Yahoo again, so it would
#                 add a column to the ledger without adding a witness. bsedata is
#                 live-quote only (fails the date-anchored rule) and last released
#                 2024. investpy has been dead since Investing.com blocked it in
#                 2022. twelvedata is alive and covers India but needs an account
#                 that does not exist yet — the one worth signing up for.
#
# Two witnesses, same count as before, but a better pair: both are date-anchored,
# so unlike screener.in they can testify DURING market hours — the defect that
# suppressed the 2026-08-11 brief. The pair is also exchange-diverse (Yahoo→NSE,
# Alpha Vantage→BSE), so a single-exchange feed problem no longer convinces
# everyone at once.
#
# 🔴 A TIE IS A MISMATCH (validate_brief's majority rule), so with exactly two
# witnesses one odd vote suppresses the send. That was equally true of the old
# pair, but it is the reason to add a third rather than settle here: Twelve Data
# is the cheapest route to breaking ties.
SOURCES = {"yfinance": _yfinance, "alphavantage": _alphavantage}


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
    measured rather than assumed.

    🔴 READ echo_rate BEFORE agree_rate. It is the share of answered checks where
    the source returned our number EXACTLY — and a high value means the source is
    not a witness at all, it is our own figure coming back by a different pipe.
    Such a source scores a perfect response_rate and a perfect agree_rate while
    carrying zero information, so the two rates that look like a track record are
    exactly the ones an echo aces.

    This is not hypothetical. Measured 2026-08-18 over the ledger to date:

        yfinance      63 checks   89% exact     <- NSE close, re-served
        screener      52 checks   48% exact     <- NSE close, 4-sig-fig rounded
        alphavantage   6 checks    0% exact     <- BSE order book

    yfinance returned 1969.300048828125 against our 1969.3 — precisely
    float32(1969.3), i.e. our own value round-tripped through someone's 32-bit
    float, not a price anybody observed twice. screener's non-zero half is its
    documented rounding, not a second opinion. So the gate spent months with two
    witnesses giving one testimony, and would have agreed with itself whatever NSE
    published.

    WHY NO AMOUNT OF SHOPPING FIXES THIS. An Indian equity's close is defined by
    the exchange's matching engine; it is an administrative fact NSE publishes, not
    a measurement that can be taken independently twice. Every aggregator
    redistributes that same fact. The only genuine second observation is ANOTHER
    EXCHANGE — BSE runs a separate order book on the same companies, arbitraged to
    ~0.1-0.3%, and that basis IS the evidence of independence. So a new source is
    worth adding only if it quotes a different exchange; point it at NSE and it is
    a third echo.

    WHAT EACH WITNESS IS FOR (do not "simplify" the gate down to the agreeable one):
      yfinance      liveness + mapping. Date-anchored and answers during market
                    hours, so it proves our number matches NSE's published number
                    and that neither feed is frozen. NOT a price check — it is
                    structurally incapable of disagreeing about the NSE close.
      alphavantage  the actual price check, because it is a different exchange.
    """
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
                                      THEN ABS(diff_pct) END), 3)      AS avg_abs_diff,
                       -- diff_pct is stored rounded to 3dp, so =0 means the two
                       -- agreed to within 0.0005% — an echo, not a coincidence.
                       SUM(CASE WHEN verdict IN ('agree','disagree')
                                 AND diff_pct = 0 THEN 1 ELSE 0 END)   AS exact
                  FROM source_check WHERE asof >= ? GROUP BY source ORDER BY source""",
                (since,)).fetchall()
    except Exception as e:                                     # noqa: BLE001
        print(f"  (source ledger unreadable: {e})")
        return []
    out = []
    for src, n, errs, agree, dis, avg, exact in rows:
        answered = n - (errs or 0)
        out.append({
            "source": src, "checks": n,
            "response_rate": round(answered / n * 100, 1) if n else 0.0,
            "agree_rate": round((agree or 0) / answered * 100, 1) if answered else 0.0,
            "disagreements": dis or 0,
            "avg_abs_diff_pct": avg,
            # Share of ANSWERED checks that came back identical to our own figure.
            # High = echo, not witness. See the docstring.
            "echo_rate": round((exact or 0) / answered * 100, 1) if answered else 0.0,
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
