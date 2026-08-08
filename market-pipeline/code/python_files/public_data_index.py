#!/usr/bin/env python3
"""
public_data_index.py — index of what NSE / BSE / other public sources ACTUALLY expose.

WHY THIS EXISTS
---------------
Two catalogs already exist and neither answers this question:

    docs/DATA_SOURCES.md      the ~17 upstreams we PULL FROM (source_registry.py)
    .ruflo data-library       the 10,528 datasets we ALREADY HOLD

Both describe the demand side. Collection has always been driven by an immediate
need, so the map of what is *available and unused* has never been drawn — and you
cannot decide not to collect something you do not know exists.

WHAT THIS IS NOT
----------------
🔴 It is not a list of endpoints written from recall. Every row here is PROBED and
carries the evidence of its own probe: status, content-type, and the actual shape
returned (JSON top-level keys, record count, CSV header). An endpoint that 404s is
recorded as dead rather than quietly dropped, because "we tried it and it is gone"
is itself worth knowing and stops the next person re-deriving it.

Rows are therefore CLAIMS WITH RECEIPTS. `status=OK` means this run got a parseable
payload; anything else names the failure. Nothing is asserted on reputation.

COMPLETENESS — read this before treating the output as exhaustive
-----------------------------------------------------------------
This is a broad, honest sweep, NOT proof of completeness. NSE and BSE publish no
machine-readable index of their own endpoints, so the candidate list is assembled
by hand and can only ever be a lower bound. `--verify-only` re-probes what is
already known; new candidates must be added deliberately. The output says "at
least these exist", never "only these exist".

USED / UNUSED
-------------
Each row is grepped against the repo for a distinctive fragment of its URL, so the
index separates:

    USED    already wired into a collector
    UNUSED  live, parseable, and nobody is reading it   <- the point of this file

    public_data_index.py --probe            # probe everything, write the index
    public_data_index.py --probe --site nse # one site
    public_data_index.py --report           # rebuild markdown from the last probe
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache_seed"
PANEL = CACHE / "public_data_index.parquet"
DOC = HERE / "docs" / "PUBLIC_DATA_INDEX.md"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

# A liquid, long-listed symbol used wherever an endpoint needs one. Deliberately a
# large-cap: a thin name can 200-with-no-rows and make a live endpoint look empty.
SYM_NSE, SYM_BSE = "RELIANCE", "500325"


def _recent_weekday():
    """Most recent weekday, for endpoints that require a date.

    Deliberately not holiday-aware: if it lands on one, the endpoint answers with
    an empty payload and `_shape` reports EMPTY — which is an honest result, not a
    false DEAD. Anything cleverer would need a calendar this file should not own.
    """
    from datetime import date, timedelta
    d = date.today()
    while d.weekday() > 4:
        d -= timedelta(days=1)
    return d

# ─────────────────────────────────────────────────────────────────────────────
# CANDIDATES.  (site, id, category, url, what it gives you)
#
# Grouped by what the data IS, not by which page it sits behind, because the
# question this file answers is "what can we know about a company/market", not
# "what does the website look like".
# ─────────────────────────────────────────────────────────────────────────────
NSE_API = "https://www.nseindia.com/api"
BSE_API = "https://api.bseindia.com/BseIndiaAPI/api"

CANDIDATES = [
    # ── NSE: universe & reference ────────────────────────────────────────────
    ("nse", "nse-equity-master",     "reference",   f"{NSE_API}/equity-master", "index -> constituent-list names"),
    ("nse", "nse-index-names",       "reference",   f"{NSE_API}/index-names", "every index NSE publishes"),
    ("nse", "nse-all-indices",       "prices",      f"{NSE_API}/allIndices", "live level+change for all indices"),
    ("nse", "nse-holiday-master",    "reference",   f"{NSE_API}/holiday-master?type=trading", "trading holiday calendar"),
    ("nse", "nse-market-status",     "reference",   f"{NSE_API}/marketStatus", "open/closed per segment"),
    ("nse", "nse-eq-stockindices",   "prices",      f"{NSE_API}/equity-stockIndices?index=NIFTY%2050", "index constituents w/ live quote"),

    # ── NSE: per-company ─────────────────────────────────────────────────────
    ("nse", "nse-quote-equity",      "prices",      f"{NSE_API}/quote-equity?symbol={SYM_NSE}", "live quote + 52w + band"),
    ("nse", "nse-quote-trade-info",  "microstructure", f"{NSE_API}/quote-equity?symbol={SYM_NSE}&section=trade_info", "delivery %, order book, VWAP"),
    ("nse", "nse-historical-cm",     "prices",      f"{NSE_API}/historical/cm/equity?symbol={SYM_NSE}", "daily OHLCV history"),
    ("nse", "nse-corp-info",         "corp-actions", f"{NSE_API}/top-corp-info?symbol={SYM_NSE}&market=equities", "per-company announcements bundle"),
    ("nse", "nse-shareholding",      "ownership",   f"{NSE_API}/corporate-share-holdings-master?index=equities&symbol={SYM_NSE}", "promoter/public %, 22 quarters"),

    # ── NSE: disclosure streams (market-wide) ────────────────────────────────
    ("nse", "nse-announcements",     "disclosure",  f"{NSE_API}/corporate-announcements?index=equities", "every corporate announcement"),
    ("nse", "nse-board-meetings",    "disclosure",  f"{NSE_API}/corporate-board-meetings?index=equities", "board meeting calendar"),
    ("nse", "nse-fin-results",       "fundamentals", f"{NSE_API}/corporates-financial-results?index=equities&period=Quarterly", "quarterly results as filed"),
    ("nse", "nse-insider",           "ownership",   f"{NSE_API}/corporates-pit?index=equities", "insider trading (PIT/SAST)"),
    ("nse", "nse-event-calendar",    "disclosure",  f"{NSE_API}/event-calendar", "forthcoming corporate events"),
    ("nse", "nse-corp-actions",      "corp-actions", f"{NSE_API}/corporates-corporateActions?index=equities", "dividends, splits, bonus"),
    ("nse", "nse-circulars",         "regulatory",  f"{NSE_API}/circulars", "exchange circulars"),

    # ── NSE: flows & activity ────────────────────────────────────────────────
    ("nse", "nse-fii-dii",           "flows",       f"{NSE_API}/fiidiiTradeReact", "daily FII/DII cash buy/sell"),
    ("nse", "nse-large-deals",       "flows",       f"{NSE_API}/snapshot-capital-market-largedeal", "bulk / block / short deals"),
    ("nse", "nse-gainers",           "microstructure", f"{NSE_API}/live-analysis-variations?index=gainers", "top gainers"),
    ("nse", "nse-most-active",       "microstructure", f"{NSE_API}/live-analysis-most-active-securities?index=value", "most active by value"),
    ("nse", "nse-52w-high",          "microstructure", f"{NSE_API}/live-analysis-data-52weekhighstock", "52-week high hits"),

    # ── NSE: derivatives ─────────────────────────────────────────────────────
    ("nse", "nse-optionchain-idx",   "derivatives", f"{NSE_API}/option-chain-indices?symbol=NIFTY", "index option chain w/ OI+IV"),
    ("nse", "nse-optionchain-eq",    "derivatives", f"{NSE_API}/option-chain-equities?symbol={SYM_NSE}", "single-stock option chain"),
    ("nse", "nse-quote-derivative",  "derivatives", f"{NSE_API}/quote-derivative?symbol={SYM_NSE}", "futures/options quotes per underlying"),
    ("nse", "nse-liveequity-deriv",  "derivatives", f"{NSE_API}/liveEquity-derivatives?index=nse50_fut", "live F&O board"),

    # ── NSE: other segments ──────────────────────────────────────────────────
    ("nse", "nse-sme-emerge",        "segment",     f"{NSE_API}/live-analysis-emerge", "SME Emerge board"),
    ("nse", "nse-mf-etf",            "segment",     f"{NSE_API}/etf", "ETF board"),
    ("nse", "nse-ipo-current",       "segment",     f"{NSE_API}/ipo-current-issue", "live IPO issues"),
    ("nse", "nse-debt-market",       "segment",     f"{NSE_API}/liveBonds-traded-on-cm?type=bonds", "traded bonds"),

    # ── BSE ──────────────────────────────────────────────────────────────────
    # 🔴 Route names here are NOT guessed. The first pass invented four
    # plausible-looking ones (Corpforthcoming, FinancialResultsNew, Sensexview,
    # ShpPromoterNPublicShareholding); every one 302'd to api.bseindia.com/
    # error_Bse.html, which redirects back — surfacing as TooManyRedirects, a
    # symptom that looks like a transport fault and is actually "no such route".
    # The names below are read off the maintained `bse` package's own request
    # sites and then PROBED here, so they carry the same receipts as everything
    # else. See docs: a wrong route name is indistinguishable from a dead API
    # unless you look at the redirect target.
    ("bse", "bse-scrip-list",        "reference",   f"{BSE_API}/ListofScripData/w?Group=&Scripcode=&industry=&segment=Equity&status=Active", "full active scrip master"),
    ("bse", "bse-quote",             "prices",      f"{BSE_API}/StockReachGraph/w?scripcode={SYM_BSE}&flag=0&fromdate=&todate=&seriesid=", "price series for a scrip"),
    ("bse", "bse-comheader",         "reference",   f"{BSE_API}/ComHeadernew/w?quotetype=EQ&scripcode={SYM_BSE}&seriesid=", "company header / industry"),
    ("bse", "bse-announcements",     "disclosure",  f"{BSE_API}/AnnGetData/w?strCat=-1&strPrevDate=&strScrip=&strSearch=P&strToDate=&strType=C&subcategory=-1", "corporate announcements"),
    ("bse", "bse-scrip-header",      "prices",      f"{BSE_API}/getScripHeaderData/w?scripcode={SYM_BSE}", "live quote header (O/H/L/C)"),
    ("bse", "bse-stock-trading",     "microstructure", f"{BSE_API}/StockTrading/w?flag=&quotetype=EQ&scripcode={SYM_BSE}", "trading detail / market depth"),
    ("bse", "bse-results-tab",       "fundamentals", f"{BSE_API}/TabResults_PAR/w?scripcode={SYM_BSE}&tabtype=RESULTS", "filed financial results"),
    # A same-day window on this one returns list[0] even when the route is fine —
    # "forthcoming" means future-dated, so probing [today, today] tests nothing.
    ("bse", "bse-forth-results",     "disclosure",  f"{BSE_API}/Corpforthresults/w?fromdate={{d8}}&todate={{d8fwd}}", "forthcoming results calendar"),
    ("bse", "bse-corp-actions",      "corp-actions", f"{BSE_API}/DefaultData/w?Fdate={{d8}}&TDate={{d8}}&Purposecode=&scripcode=", "corporate actions (ex-dates)"),
    ("bse", "bse-index-archive",     "prices",      f"{BSE_API}/IndexArchDailyAll/w?fmdt={{dslash}}&todt={{dslash}}&index=All&period=D", "daily close, every BSE index"),
    ("bse", "bse-advance-decline",   "microstructure", f"{BSE_API}/advanceDecline/w?val=Index", "advance/decline breadth"),
    ("bse", "bse-high-low",          "microstructure", f"{BSE_API}/MktHighLowData/w?HLflag=H&Grpcode=&indexcode=&scripcode=", "52-week high/low hits"),
    ("bse", "bse-ann-subcat",        "reference",   f"{BSE_API}/AnnSubCategoryGetData/w", "announcement category taxonomy"),
    ("bse", "bse-bhavcopy",          "prices",      "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{d8}_F_0000.CSV", "official EOD bhavcopy CSV"),

    # ── Regulators / registries / other public ───────────────────────────────
    ("other", "amfi-nav",            "funds",       "https://www.amfiindia.com/spages/NAVAll.txt", "daily NAV, every MF scheme"),
    ("other", "rbi-wss",             "macro",       "https://www.rbi.org.in/Scripts/WSSView.aspx", "weekly statistical supplement"),
    ("other", "sebi-fpi",            "flows",       "https://www.sebi.gov.in/statistics/fpi-investment.html", "FPI investment statistics"),
    ("other", "nsdl-fpi",            "flows",       "https://www.fpi.nsdl.co.in/web/Reports/ReportItem.aspx?ReportId=27", "FPI fortnightly AUC"),
    ("other", "mca-master",          "registry",    "https://www.mca.gov.in/mcafoportal/showCompanyMasterData.do", "company master (CIN, status)"),
    ("other", "ibbi-cirp",           "registry",    "https://ibbi.gov.in/en/cirp", "insolvency (CIRP) cases"),
    ("other", "ccil-gsec",           "macro",       "https://www.ccilindia.com/", "G-sec / repo / forex benchmarks"),
    ("other", "datagov-in",          "macro",       "https://api.data.gov.in/lists?format=json&limit=5", "data.gov.in dataset catalog"),
]


def _session(site: str) -> requests.Session:
    """Per-site session. NSE and BSE both gate on a prior page visit.

    NSE hands out cookies only after a homepage GET; a cold API call returns 401
    even though the endpoint is public. BSE checks Referer instead. Getting this
    wrong makes every endpoint look dead, which is the single easiest way to
    produce a confidently wrong index.
    """
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    try:
        if site == "nse":
            s.headers["Accept"] = "*/*"
            s.get("https://www.nseindia.com", timeout=20)
            time.sleep(1.0)
        elif site == "bse":
            s.headers.update({"Accept": "application/json",
                              "Referer": "https://www.bseindia.com/"})
            s.get("https://www.bseindia.com", timeout=20)
            time.sleep(1.0)
    except Exception:
        pass                    # a failed handshake still leaves a usable session
    return s


def _shape(r: requests.Response) -> tuple:
    """Describe what actually came back: (status, n_records, shape-string).

    The shape string is the evidence. A bare 200 proves nothing — NSE returns 200
    with an empty dict for several endpoints — so the index records the top-level
    keys and a record count and lets the reader judge.
    """
    ctype = r.headers.get("content-type", "").split(";")[0]
    body = r.text or ""
    if not body.strip():
        return "EMPTY", 0, "empty body"

    if "json" in ctype or body.lstrip()[:1] in "[{":
        try:
            j = r.json()
        except Exception:
            return "ERROR", 0, f"unparseable json ({len(body)}b)"
        if isinstance(j, list):
            n = len(j)
            keys = sorted(j[0].keys())[:8] if n and isinstance(j[0], dict) else []
            return ("OK" if n else "EMPTY"), n, f"list[{n}] keys={keys}"
        if isinstance(j, dict):
            if not j:
                return "EMPTY", 0, "empty object"
            # Count the biggest embedded list — that is the payload
            n = max([len(v) for v in j.values() if isinstance(v, list)] or [0])
            return "OK", n, f"object keys={sorted(j.keys())[:10]} max_list={n}"
        return "OK", 0, f"scalar {type(j).__name__}"

    if "csv" in ctype or "text/plain" in ctype:
        try:
            head = body[:4000]
            df = pd.read_csv(io.StringIO(head), sep=None, engine="python", nrows=5)
            return "OK", body.count("\n"), f"delimited cols={list(df.columns)[:8]}"
        except Exception:
            return "OK", body.count("\n"), f"text {len(body)}b (undelimited)"

    if "html" in ctype:
        # HTML is not automatically useless — it may be a scrapeable table — but
        # it is NOT an API, and conflating the two is how a catalog overpromises.
        n = body.lower().count("<table")
        return ("HTML" if n else "HTML-NOAPI"), n, f"html {len(body)}b, {n} table(s)"

    return "OK", 0, f"{ctype} {len(body)}b"


# Path words too generic to prove anything. "Reports" matched _gb.py, _survival.py
# and community.py on the first run — files with no connection to NSDL whatsoever.
_GENERIC = {"reports", "reportitem", "report", "index", "data", "search", "query",
            "public", "static", "content", "default", "common", "download", "web",
            "scripts", "pages", "portal", "service", "services", "getdata", "lists"}


def _fragment(url: str):
    """Pick a path token distinctive enough that a match actually means something.

    Endpoint names like `corporate-share-holdings-master` or `fiidiiTradeReact` are
    self-identifying; `.aspx` paths like `/web/Reports/ReportItem.aspx` are not, and
    a match on those is noise. Returns None rather than guessing — an honest
    "unknown" beats a confident wrong attribution in either direction.
    """
    path = url.split("?")[0].split("//")[-1]
    toks = [t.rsplit(".", 1)[0] for t in path.split("/")[1:] if t]
    good = [t for t in toks
            if len(t) >= 8 and t.lower() not in _GENERIC
            and ("-" in t or not t.islower())]        # hyphenated or camelCase
    return max(good, key=len) if good else None


def _used_by_repo(url: str) -> str:
    """Is any of OUR code already fetching this?

    🔴 MUST NOT search .venv. The first run did, and site-packages/nse/NSE.py plus
    site-packages/nsepython/rahu.py — third-party wrappers that name every NSE
    endpoint in their own source — matched almost everything. That reported 26
    endpoints as USED when our own collectors touch far fewer, which inverts the
    one number this whole file exists to produce: the size of the unused gap.

    Returns "?" when no distinctive fragment exists, so unknowns are never silently
    counted as unused.
    """
    frag = _fragment(url)
    if not frag:
        return "?"
    try:
        out = subprocess.run(
            ["grep", "-rl", "--include=*.py",
             "--exclude-dir=.venv", "--exclude-dir=site-packages",
             "--exclude-dir=node_modules", "--exclude-dir=.git",
             frag, str(HERE)],
            capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:
        return "?"
    files = [Path(p).name for p in out.splitlines()
             if Path(p).name != "public_data_index.py"]
    return ",".join(sorted(files)[:3])


def reattribute() -> int:
    """Recompute used_by on the stored probe without re-hitting the network."""
    if not PANEL.exists():
        print("  no probe data — run --probe first"); return 1
    d = pd.read_parquet(PANEL)
    before = (d.used_by != "").sum()
    d["used_by"] = [_used_by_repo(u) for u in d.url]
    d.to_parquet(PANEL, compression="zstd", index=False)
    now = (~d.used_by.isin(["", "?"])).sum()
    print(f"  used_by recomputed: {before} -> {now} genuinely used "
          f"({(d.used_by == '?').sum()} unattributable)")
    return report()


def probe(site_filter: str = "", sleep: float = 1.2) -> int:
    todo = [c for c in CANDIDATES if not site_filter or c[0] == site_filter]
    print(f"  probing {len(todo)} endpoints"
          f"{' for ' + site_filter if site_filter else ''}")
    day = _recent_weekday()
    rows, sessions = [], {}
    for i, (site, cid, cat, url, gives) in enumerate(todo, 1):
        from datetime import timedelta
        url = (url.replace("{d8fwd}", (day + timedelta(days=45)).strftime("%Y%m%d"))
                  .replace("{d8}", day.strftime("%Y%m%d"))
                  .replace("{dslash}", day.strftime("%d/%m/%Y")))
        if site not in sessions:
            sessions[site] = _session(site)
        s = sessions[site]
        # 🔴 `Accept: application/json` makes BSE 404 a FILE download. The bhavcopy
        # CSV returns 200/835KB with minimal headers and 404/8KB with the JSON
        # Accept — same URL, same session age, isolated with a 90s cooldown so
        # throttling could not explain it. Content negotiation, not a dead route.
        # File endpoints therefore ask for */*, and only JSON APIs claim JSON.
        is_file = re.search(r"\.(csv|zip|txt|xls[xm]?|json)$", url.split("?")[0], re.I)
        try:
            r = s.get(url, timeout=25,
                      headers={"Accept": "*/*"} if is_file else None)
            http = r.status_code
            if http == 200:
                status, n, shape = _shape(r)
            elif http in (401, 403):
                status, n, shape = "AUTH/BLOCKED", 0, f"http {http}"
            elif http == 404:
                # 🔴 A 404 IS NOT PROOF OF A DEAD ROUTE — at least not on BSE,
                # which soft-blocks a client that has been going too fast by
                # answering 404 with an ~8KB HTML page instead of 429. The
                # bhavcopy URL returned 200/835KB, then 404 twice under load,
                # then 200/835KB again after a 120s pause. Same URL throughout.
                # So: back off and ask once more, and only then call it dead.
                # Without this the index confidently records live endpoints as
                # gone, which is the most expensive error it could make.
                # Two escalating pauses. 20s was measured to be too short after a
                # burst — the bhavcopy URL still 404'd at 20s and returned 200 at
                # 120s. Cheap in practice: this path only runs on an actual 404.
                # It is the SESSION that gets flagged, not just the pace. The same
                # bhavcopy URL 404'd at 20s AND at 90s on the burst session, but
                # returned 200/835KB on a freshly handshaken one. So the retry
                # rebuilds the session rather than only waiting — waiting alone
                # was measured and is not sufficient.
                status, n, shape = "DEAD", 0, "http 404"
                for wait in (15, 60):
                    time.sleep(wait)
                    try:
                        s2 = _session(site)          # fresh cookies, fresh handshake
                        r2 = s2.get(url, timeout=30)
                    except Exception as e2:
                        status, n, shape = "ERROR", 0, f"404 then {type(e2).__name__}"
                        break
                    if r2.status_code == 200:
                        http = 200
                        status, n, shape = _shape(r2)
                        shape += f" (recovered: fresh session +{wait}s)"
                        sessions[site] = s2          # keep the good one
                        break
                    status, n, shape = "DEAD", 0, f"http 404 (fresh session, {wait}s)"
            else:
                status, n, shape = "ERROR", 0, f"http {http}"
        except requests.TooManyRedirects:
            # Do NOT report this as UNREACHABLE. BSE answers an unknown route with
            # 302 -> error_Bse.html, which redirects back; the loop surfaces as a
            # transport exception and reads as "the host is broken" when it really
            # means "that route does not exist". Re-ask without following, so the
            # index records the redirect TARGET as the evidence.
            try:
                rr = s.get(url, timeout=20, allow_redirects=False)
                loc = rr.headers.get("location", "")
                http, status, n = rr.status_code, "BAD-ROUTE", 0
                shape = f"302 -> {loc[:60]}" if loc else "redirect loop"
            except Exception as e2:
                http, status, n, shape = 0, "UNREACHABLE", 0, type(e2).__name__
        except Exception as e:
            http, status, n, shape = 0, "UNREACHABLE", 0, type(e).__name__
        used = _used_by_repo(url)
        rows.append({"site": site, "id": cid, "category": cat, "url": url,
                     "gives": gives, "http": http, "status": status,
                     "records": n, "shape": shape, "used_by": used})
        flag = "✓" if status == "OK" else " "
        tag = "USED" if used else ""
        print(f"  {flag} [{i:>2}/{len(todo)}] {cid:<24} {status:<13} {tag:<4} {shape[:64]}")
        time.sleep(sleep)

    d = pd.DataFrame(rows)
    if PANEL.exists() and site_filter:
        old = pd.read_parquet(PANEL)
        d = pd.concat([old[old.site != site_filter], d], ignore_index=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    d.to_parquet(PANEL, compression="zstd", index=False)
    print(f"\n  -> {PANEL.name}: {len(d)} endpoints "
          f"({(d.status == 'OK').sum()} live, {(d.used_by == '').sum()} unused)")
    return report()


def report() -> int:
    if not PANEL.exists():
        print("  no probe data — run --probe first"); return 1
    d = pd.read_parquet(PANEL)
    live = d[d.status == "OK"]
    unused = live[live.used_by == ""]
    unknown = live[live.used_by == "?"]

    L = ["# Public data index — what NSE / BSE / others actually expose", "",
         "Every row was **probed**, not recalled. `status` is the result of this "
         "tool's own request; `shape` is the payload it got back. An endpoint "
         "listed as DEAD was tried and returned 404 — recorded so nobody "
         "re-derives it. Rebuild with `public_data_index.py --probe`.", "",
         "🔴 **This is a lower bound, not a complete enumeration.** Neither NSE nor "
         "BSE publishes a machine-readable index of its own endpoints, so the "
         "candidate list is hand-assembled. It says *at least these exist* — never "
         "*only these exist*.", "",
         f"**{len(d)} endpoints probed · {len(live)} live · {len(unused)} live and "
         f"currently unused.**", "",
         "## The gap — live, parseable, and nobody is reading it", "",
         "This is the answer to \"we only fetch what we need\": everything below is "
         "available right now at no additional access cost.", "",
         "| site | endpoint | category | what it gives | payload |",
         "|---|---|---|---|---|"]
    for _, r in unused.sort_values(["site", "category"]).iterrows():
        L.append(f"| {r.site} | `{r.id}` | {r.category} | {r.gives} | {r['shape'][:70]} |")

    L += ["", "## Already wired in", "",
          "Attribution greps our own `.py` files only — **never `.venv`**. The "
          "`nse` and `nsepython` packages name every NSE endpoint in their own "
          "source, so searching site-packages marked almost everything as used.", "",
          "| site | endpoint | what it gives | consumed by |", "|---|---|---|---|"]
    for _, r in live[~live.used_by.isin(["", "?"])].sort_values(["site", "id"]).iterrows():
        L.append(f"| {r.site} | `{r.id}` | {r.gives} | `{r.used_by}` |")

    if len(unknown):
        L += ["", "### Unattributable", "",
              "No path token distinctive enough to grep for, so usage is genuinely "
              "unknown — listed separately rather than counted as unused.", "",
              "| site | endpoint | what it gives |", "|---|---|---|"]
        for _, r in unknown.sort_values(["site", "id"]).iterrows():
            L.append(f"| {r.site} | `{r.id}` | {r.gives} |")

    dead = d[d.status != "OK"]
    L += ["", "## Not usable as an API (recorded so it is not re-attempted)", "",
          "| site | endpoint | status | detail | what it would have given |",
          "|---|---|---|---|---|"]
    for _, r in dead.sort_values(["status", "site"]).iterrows():
        L.append(f"| {r.site} | `{r.id}` | {r.status} | {r['shape'][:44]} | {r.gives} |")

    L += ["", "## Coverage by category", "",
          "| category | live | unused |", "|---|---|---|"]
    for cat, g in live.groupby("category"):
        L.append(f"| {cat} | {len(g)} | {(g.used_by == '').sum()} |")

    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(L) + "\n")
    print(f"  -> {DOC.relative_to(HERE)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--reattribute", action="store_true")
    ap.add_argument("--site", default="", choices=["", "nse", "bse", "other"])
    ap.add_argument("--sleep", type=float, default=1.2)
    a = ap.parse_args()
    if a.probe:
        return probe(site_filter=a.site, sleep=a.sleep)
    if a.reattribute:
        return reattribute()
    if a.report:
        return report()
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
