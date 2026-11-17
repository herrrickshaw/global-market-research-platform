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
# 🔴 AND RETURNING A DATE IS NOT THE SAME AS BEING DATE-ANCHORED. Measured
# 2026-08-18 mid-session: yfinance answered with a row stamped TODAY carrying the
# live intraday price, so it passed every date check while comparing our close
# against a moving tick — the identical defect, wearing a valid-looking date.
# A source here must return the last COMPLETED session, and each one is
# responsible for refusing an in-progress session itself; the caller cannot tell
# a settled close from a live tick by looking at the pair.
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
    """Latest COMPLETED close on or before `asof`.

    🔴 A ROW DATED TODAY IS NOT A CLOSE WHILE THE SESSION IS OPEN. This used to
    claim it was "date-anchored, so market hours are irrelevant", and that was
    wrong in the one way that mattered: once NSE opens, Yahoo emits a row stamped
    with TODAY's date carrying the live intraday price. Nothing errors — a date is
    present, so the gate's date check passes — and the comparison silently becomes
    our close against a moving tick. Caught 2026-08-18 09:20 IST, mid-session:

        HDFCBANK   ours 729.0   yfinance 726.35 @08-18   alphavantage 730.00 @08-17
        INFY       ours 1139.9  yfinance 1121.60 @08-18  alphavantage 1138.00 @08-17

    Those 0.36% and 1.63% gaps are the market moving, not corroboration. This is
    the SAME defect screener.in was retired for; screener merely announced it by
    serving an undated quote, while yfinance hid it behind a plausible date.

    Why it is dangerous rather than merely noisy: validate_brief counts a tie as a
    mismatch, and the quorum is two. One sampled name moving >2% intraday would
    make this source "disagree", tie the vote and SUPPRESS the send — a lost brief
    caused by a normal day's trading. INFY reached 1.63% on the run that found it.

    So rows dated today are dropped outright. Yahoo flags nothing to distinguish a
    settled close from a live tick, and after the session ends today's row is a
    real close but still the WRONG one: the India scan is built at 03:00, before
    the open, so it always holds the previous session. The witness must answer the
    question the scan actually asks.

    This is a no-op for historical queries — `end=asof+1` already excludes today
    whenever `asof` is in the past — so it bites only in the live case it is for.
    """
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
        # Drop the in-progress session. See the docstring — this is the whole
        # point of the function, not a tidy-up.
        h = h[h.index.date < _dt.date.today()]
        if not len(h):
            return {"error": "no completed session on/before asof"}
        return {"price": float(h["Close"].iloc[-1]), "date": h.index[-1].date()}
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"yf: {str(e)[:60]}"}


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
            #
            # 🔴 REDACT BEFORE THIS STRING IS STORED. Alpha Vantage's rate-limit
            # message QUOTES YOUR API KEY BACK AT YOU ("We have detected your API
            # key as <key>..."), and this string is written verbatim into
            # state/source_accuracy.db by price_sources.record(). Caught 2026-08-18
            # the first time the quota was actually hit: the key landed in the
            # ledger, and that ledger sits in a repo whose origin is PUBLIC. The
            # key we sent is redacted by value, plus any key-shaped token as a
            # backstop, because the next provider to do this will word it
            # differently.
            note = str(j.get("Note") or j.get("Information")
                       or j.get("Error Message") or "no series")[:200]
            note = note.replace(k, "<redacted>")
            note = re.sub(r"[A-Za-z0-9_\-]{16,}", "<redacted>", note)
            return {"error": f"av: {note[:70]}"}
        days = [d for d in ts if d <= asof.isoformat()]
        if not days:
            return {"error": "no rows on/before asof"}
        d = max(days)
        return {"price": float(ts[d]["4. close"]),
                "date": _dt.date.fromisoformat(d)}
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"av: {str(e)[:60]}"}


def _twelvedata(sym: str, asof: _dt.date) -> dict:
    """Twelve Data daily bars — the tie-breaker. Reaches NSE directly.

    Registered to fix the failure mode that suppressed the 2026-08-29 brief: with
    exactly two witnesses, validate_brief's majority rule makes a 1-1 split a
    MISMATCH, so ONE stale witness is enough to block a correct send. That morning
    yfinance had not yet rolled forward to the 28-Aug session and was serving the
    27-Aug close under it; our scan and Alpha Vantage both had 28-Aug and agreed to
    0.03% on INFY. The jury split 1-1 and the send was suppressed on data that the
    official NSE bhavcopy later confirmed was correct. A third voice ends that.

    Note this witness quotes NSE, the same exchange as the scan, unlike Alpha
    Vantage's BSE path — so expect ~0% basis here, not the 0.1-0.3% that is normal
    there. That costs some exchange diversity, but the pair already covers both
    exchanges; what was missing was a third VOTE, and Twelve Data is the only
    surveyed provider that covers India live (see the findings block below).

    🔴 NEEDS TWELVEDATA_KEY in the canonical credential store. Absent, this returns
    an error and validate_brief drops it from the quorum entirely — it does not vote
    "no". So registering it before the key exists is inert, never harmful.

    Free tier is 800 requests/day and 8/minute; the gate samples ~6 names per run,
    so unlike the Alpha Vantage key this one is in no danger of being starved by a
    second caller.
    """
    k = _key("TWELVEDATA_KEY")
    if not k:
        return {"error": "no TWELVEDATA_KEY"}
    try:
        r = _get("https://api.twelvedata.com/time_series?" + urlencode({
            "symbol": sym, "exchange": "NSE", "interval": "1day",
            "outputsize": "30", "apikey": k}))
        if r.status_code != 200:
            return {"error": f"http {r.status_code}"}
        j = r.json()
        vals = j.get("values")
        if not vals:
            # Twelve Data reports quota and unknown symbols as status:error with a
            # 200 body, same shape as Alpha Vantage's prose notes. Redact before
            # returning: this string is written verbatim into source_accuracy.db by
            # record(), and that ledger lives in a repo whose origin is PUBLIC.
            note = str(j.get("message") or j.get("status") or "no values")[:200]
            note = note.replace(k, "<redacted>")
            note = re.sub(r"[A-Za-z0-9_\-]{16,}", "<redacted>", note)
            return {"error": f"td: {note[:70]}"}
        rows = {v["datetime"][:10]: v for v in vals if v.get("datetime")}
        days = [d for d in rows if d <= asof.isoformat()]
        if not days:
            return {"error": "no rows on/before asof"}
        d = max(days)
        return {"price": float(rows[d]["close"]),
                "date": _dt.date.fromisoformat(d)}
    except Exception as e:                                     # noqa: BLE001
        return {"error": f"td: {str(e)[:60]}"}


# ─── the registry ─────────────────────────────────────────────────────────────
# Three witnesses, three paths to the market: Yahoo→NSE, Alpha Vantage→BSE,
# Twelve Data→NSE direct. All answer with the last COMPLETED session, so they
# can testify during market hours. WHY THREE: validate_brief counts a tie as a
# mismatch, so with two witnesses one stale vote suppresses a correct send
# (2026-08-29, INFY). Two is the count at which being right and being outvoted
# look identical.
#
# RETIRED, with the finding that retired them (code in git history before
# 2026-10-27 if a re-test is ever wanted):
#   screener.in   2026-08-18 — serves an undated live quote once NSE opens, so
#                 it could not testify mid-session (suppressed the 08-11 brief).
#   stooq         2026-08-12 — returns HTML, not CSV, for NSE names under every
#                 suffix; it does not serve this market.
# Surveyed and rejected 2026-08-18: EODHD (no India on the free plan), nsepython
# (needs browser cookies), moneycontrol (endpoint gone), Hugging Face datasets
# (static dumps), jugaad-data (reads bhavcopy — circular), yahooquery (Yahoo
# again — a column, not a witness), bsedata (live-quote only), investpy (dead).
#
# ⚠️ Until TWELVEDATA_KEY exists in the credential store, _twelvedata returns an
# error and validate_brief drops it from the quorum — back to two witnesses.
SOURCES = {"yfinance": _yfinance, "alphavantage": _alphavantage,
           "twelvedata": _twelvedata}


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
      yfinance      liveness + mapping. Proves our number matches NSE's published
                    number and that neither feed is frozen. NOT a price check — it
                    is structurally incapable of disagreeing about the NSE close.
                    Its echo_rate is therefore SUPPOSED to sit near 100%; a fall
                    means it started answering with something that is not the
                    close, which is exactly how the intraday-tick bug showed up
                    (88.9% -> 81.2% on 2026-08-18) — read a DROP here as a defect
                    in the source, not as it becoming a better witness.
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
