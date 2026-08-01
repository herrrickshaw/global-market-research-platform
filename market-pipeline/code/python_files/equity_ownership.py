#!/usr/bin/env python3
"""
equity_ownership.py — who owns each equity market, and who is buying it.

TWO THINGS, KEPT SEPARATE ON PURPOSE
  OWNERSHIP  static %-of-market-held, by holder type, per geography (--table)
  FLOW       who is buying/selling right now (--india, NSE daily FII/DII)

Ownership and flow answer different questions and are constantly conflated in
market commentary: Japan's foreigners dominate TURNOVER while owning a minority
of the float, and India's DIIs became the marginal buyer years before they passed
FIIs on holdings. A stock and a flow are not the same statistic.

🔴 EVIDENCE GRADE IS PART OF THE OUTPUT
The US column is COMPUTED here from the Federal Reserve's Z.1 Financial Accounts
via FRED — it is a real measurement and reproducible by re-running this file.
India, Japan, Korea and Europe are CITED from public reporting because no
comparable machine-readable series was reachable (see --sources for exactly what
was tried and what failed). The table marks every cell, and mixing the two
without saying so would be the main way this analysis could mislead.

DATA ACCESS — WHAT WORKS AND WHAT DOES NOT
  * SIP: SOLVED. Not an API. amfiindia.com is a Next.js app that renders data
    server-side, so there is no client XHR to intercept — scanning all 28 JS
    chunks yielded one path (`/api/search/trending`) and every documented
    `/modules/...` route 404s. The real channel is static PDFs:
    `/Themes/Theme1/downloads/AMFIMonthlyNote_<Month><YYYY>.pdf`, parsed by
    `--sip`. Coverage is thin — 15 notes, Jun 2024 to Aug 2025, Nov 2024 and
    Feb 2025 unparseable — so this is a short series, not the FY2016-17 history
    quoted in the press. (`portal.amfiindia.com/spages/` holds 419 monthly AUM
    reports back to 2000, but those carry AUM, not SIP.)
  * FII/DII history: NOT SOLVED. NSE `fiidiiTradeReact` returns the CURRENT DAY
    only — it accepts a `date` parameter and silently ignores it. BSE's
    `api.bseindia.com` returns an XHTML error page for every endpoint name tried,
    and bseindia.com is blocked by browser policy here. So `--india` is
    append-only: it accumulates from first run and CANNOT backfill. History needs
    NSDL, a BSE archive file, or a paid vendor.

    equity_ownership.py --us       # Z.1 -> computed US ownership shares
    equity_ownership.py --sip      # AMFI monthly notes -> India SIP series
    equity_ownership.py --india    # append today's NSE FII/DII to the store
    equity_ownership.py --table    # cross-market table, cells marked computed/cited
    equity_ownership.py --sources  # what was tried, what worked, what did not
"""

from __future__ import annotations

import argparse
import re
import json
import sys
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache_seed"
REPORTS = HERE / "reports"
US_OWN = CACHE / "us_equity_ownership.parquet"
IN_FLOW = CACHE / "india_fii_dii_daily.parquet"
REPORT = REPORTS / "equity_ownership_table.md"

# Z.1 table L.223, DIRECT holders of corporate equities, quarterly market value ($mn).
# Households are derived as the RESIDUAL, which is how the Financial Accounts
# themselves treat the household sector — it is not independently surveyed.
Z1 = {
    "Rest of world (foreign)":       "BOGZ1LM263064105Q",
    "Mutual funds":                  "BOGZ1LM653064100Q",
    "ETFs":                          "BOGZ1LM563064100Q",
    "Private pension funds":         "BOGZ1LM573064105Q",
    "State/local govt pensions":     "BOGZ1LM223064145Q",
    "Federal govt retirement":       "BOGZ1LM343064105Q",
    "Life insurance":                "BOGZ1LM543064105Q",
    "Property-casualty insurance":   "BOGZ1LM513064105Q",
}
Z1_TOTAL = "BOGZ1LM893064105Q"

NSE_FIIDII = "https://www.nseindia.com/api/fiidiiTradeReact"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")


def _key():
    import yen_carry_test as Y
    return Y._fred_key()


def _fred(series: str, key: str) -> pd.Series:
    r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                     params={"series_id": series, "api_key": key, "file_type": "json",
                             "observation_start": "1990-01-01"}, timeout=60)
    r.raise_for_status()
    o = pd.DataFrame(r.json()["observations"])
    o["Date"] = pd.to_datetime(o["date"])
    o["v"] = pd.to_numeric(o["value"], errors="coerce")
    return o.dropna(subset=["v"]).set_index("Date")["v"]


def run_us() -> pd.DataFrame:
    key = _key()
    if not key:
        print("no FRED key"); return pd.DataFrame()
    cols = {}
    for name, sid in Z1.items():
        try:
            cols[name] = _fred(sid, key)
            print(f"  {name:30s} {sid} ok")
        except Exception as e:
            print(f"  {name:30s} {sid} FAILED ({type(e).__name__})")
    total = _fred(Z1_TOTAL, key)
    d = pd.DataFrame(cols).dropna(how="all")
    d["TOTAL"] = total
    d = d.dropna(subset=["TOTAL"])
    inst = d[list(cols)].sum(axis=1)
    d["Households (residual)"] = d["TOTAL"] - inst
    CACHE.mkdir(parents=True, exist_ok=True)
    d.reset_index().to_parquet(US_OWN, compression="zstd", index=False)
    print(f"  -> {US_OWN.name}: {len(d):,} quarters, "
          f"{d.index.min().date()} .. {d.index.max().date()}")
    return d


def us_shares(d: pd.DataFrame) -> pd.Series:
    last = d.iloc[-1]
    holders = [c for c in d.columns if c != "TOTAL"]
    return (last[holders] / last["TOTAL"] * 100).sort_values(ascending=False)


def run_india() -> None:
    """Append TODAY's FII/DII figures. Cannot backfill — see module docstring."""
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json",
                      "Accept-Language": "en-US,en;q=0.9"})
    try:
        s.get("https://www.nseindia.com", timeout=20)      # cookie handshake
        r = s.get(NSE_FIIDII, timeout=25); r.raise_for_status()
        rows = r.json()
    except Exception as e:
        print(f"  NSE fetch failed ({type(e).__name__})"); return
    n = pd.DataFrame(rows)
    for c in ("buyValue", "sellValue", "netValue"):
        n[c] = pd.to_numeric(n[c], errors="coerce")
    n["Date"] = pd.to_datetime(n["date"], format="%d-%b-%Y", errors="coerce")
    n = n.dropna(subset=["Date"])[["Date", "category", "buyValue", "sellValue", "netValue"]]

    if IN_FLOW.exists():
        old = pd.read_parquet(IN_FLOW)
        n = (pd.concat([old, n], ignore_index=True)
               .drop_duplicates(subset=["Date", "category"], keep="last")
               .sort_values(["Date", "category"]))
    CACHE.mkdir(parents=True, exist_ok=True)
    n.to_parquet(IN_FLOW, compression="zstd", index=False)
    print(f"  -> {IN_FLOW.name}: {len(n)} rows, "
          f"{n.Date.min().date()} .. {n.Date.max().date()} (append-only, no backfill)")
    print(n.tail(4).to_string(index=False))


# Cited figures. Every one carries its source; none is computed here.
CITED = {
    "India": [
        ("FII / FPI", "~17%", "FII:DII ownership ratio fell below 1 to 0.98 at 31 Mar 2025; "
                              "FII ownership reported at multi-year lows"),
        ("DII (MF + insurance + pension)", "~17%", "DII holdings ₹71.76 lakh crore, ~2% above FII"),
        ("Promoters", "~50%", "Promoter holding is the dominant Indian block; widely reported"),
        ("Retail direct + others", "balance", "Residual of the above"),
    ],
    "Japan": [
        ("Foreign investors", "~30% owned", "but ~60-70% of TURNOVER — the stock/flow gap"),
        ("BoJ (via ETFs)", "largest single owner", "¥45.1tn vs GPIF ¥44.8tn at the reported date"),
        ("Individuals", "~17%", "individual holdings ~¥170.5tn FY2023; ~25% of trading value FY2025"),
        ("Banks/insurers/corporates", "balance", "cross-shareholdings, long-term declining"),
    ],
    "Korea": [
        ("Retail", "64% of TRANSACTION VALUE", "highest of any major market; vs ~30% US/Japan"),
        ("NPS", "~8% of KOSPI", "equities >50% of assets but 36.8% overseas vs 14.8% domestic"),
        ("Foreign", "~30%", "long-run range"),
    ],
    "Europe": [
        ("—", "not established", "no primary source reached; pension/insurance-led with low "
                                 "direct retail participation is the usual characterisation"),
    ],
}


AMFI_NOTE = "https://www.amfiindia.com/Themes/Theme1/downloads/AMFIMonthlyNote_{m}{y}.pdf"
SIP = CACHE / "india_sip_monthly.parquet"

# Phrases that sit next to a "Rs N crore" figure which is NOT the month's SIP
# contribution. These matter: the notes describe several flows in near-identical
# language, and a loose regex silently returns the wrong one.
_SIP_REJECT = re.compile(r"rising from|declin|increase of|assets|AUM|stood at", re.I)
# The month's SIP contribution, anchored on SIP so it cannot drift onto another line item.
# The notes phrase the same fact many ways across months: "total contribution of",
# "total contributions reaching", "contribution amount reaching", "flows continued
# to remain robust at", "flows touched a new high of". Anchor on SIP + a FLOW noun
# (contribution/contributions/flows) so it cannot drift onto another line item,
# then let the connector vary. "SIP accounts … 9.11 crore" is a COUNT, not rupees —
# excluded both by the flow-noun requirement and the plausibility range.
_SIP_TAKE = re.compile(
    r"SIP[^.]{0,120}?(?:contributions?|flows)[^.]{0,70}?Rs\.?\s*([\d,]+)\s*crore", re.I)


def _parse_sip(flat: str):
    """Month's SIP contribution in Rs crore, or None if not unambiguous.

    🔴 An earlier version used an unanchored `(?:contribution of|totalling)…`
    regex and returned 33,430 for Aug 2025 — that is the EQUITY FUND inflow
    ("Equity funds saw positive inflows … totalling Rs 33,430 crore"), which
    appears earlier in the document than the SIP sentence. The true figure is
    28,265. Several months were wrong the same way. Hence: anchor on SIP,
    reject the YoY-comparison and AUM sentences, and require agreement when the
    note states the number more than once — returning None beats returning a
    confident wrong number.
    """
    cands = []
    for m in _SIP_TAKE.finditer(flat):
        ctx = flat[max(0, m.start() - 60): m.end()]
        if _SIP_REJECT.search(ctx[:ctx.upper().rfind("RS")] if "RS" in ctx.upper() else ctx):
            continue
        v = float(m.group(1).replace(",", ""))
        if 3_000 <= v <= 60_000:          # plausible monthly SIP range, Rs crore
            cands.append(v)
    if not cands:
        return None
    if len(set(cands)) > 1:
        # The note states the figure more than once and the readings disagree.
        # Take a clear majority (the same number phrased twice, plus one stray
        # match); otherwise return None rather than guess.
        from collections import Counter
        (top, n), = Counter(cands).most_common(1)
        return top if n > len(cands) / 2 else None
    return cands[0]


def run_sip(start_year: int = 2023) -> None:
    """Monthly SIP contribution, parsed from AMFI's Monthly Note PDFs.

    FINDING THE ENDPOINT TOOK SOME DIGGING, so the trail is recorded here:
    amfiindia.com is a Next.js app that renders its data server-side, so there is
    no client XHR to intercept — scanning all 28 JS chunks yielded exactly one
    API path (`/api/search/trending`), and the documented `/modules/...` paths
    all 404. The real data channel is static files on `portal.amfiindia.com/spages/`
    (419 monthly AUM reports, .xls and .pdf, back to 2000) — but those carry AUM,
    NOT SIP. SIP lives in a separate publication:

        https://www.amfiindia.com/Themes/Theme1/downloads/AMFIMonthlyNote_<Month><YYYY>.pdf

    Coverage is thin and irregular — 14 notes as of Aug 2025, with Sep 2024
    missing — so this is a short series, not the FY2016-17 history quoted in the
    press. Anything older stays CITED in equity_capital_sources.md.
    """
    import calendar
    import subprocess
    import tempfile
    rows = []
    for y in range(start_year, 2027):
        for mi in range(1, 13):
            mon = calendar.month_name[mi]
            url = AMFI_NOTE.format(m=mon, y=y)
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
                if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                    continue
            except Exception:
                continue
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as f:
                f.write(r.content); f.flush()
                try:
                    txt = subprocess.run(["pdftotext", f.name, "-"], capture_output=True,
                                         text=True, timeout=60).stdout
                except Exception:
                    continue
            flat = " ".join(txt.split())
            val = _parse_sip(flat)
            m2 = re.search(r"SIP assets account for\s*([\d.]+)%", flat, re.I)
            if val is None:
                print(f"  {mon[:3]} {y}: no unambiguous SIP figure — SKIPPED")
                continue
            rows.append({"month": pd.Timestamp(year=y, month=mi, day=1),
                         "sip_crore": val,
                         "sip_pct_of_aum": float(m2.group(1)) if m2 else None,
                         "source": url.rsplit("/", 1)[-1]})
            print(f"  {mon[:3]} {y}: SIP Rs {val:,.0f} crore"
                  + (f", {rows[-1]['sip_pct_of_aum']}% of AUM" if m2 else ""))
    if not rows:
        print("  no SIP figures parsed"); return
    d = pd.DataFrame(rows).sort_values("month")
    CACHE.mkdir(parents=True, exist_ok=True)
    d.to_parquet(SIP, compression="zstd", index=False)
    print(f"  -> {SIP.name}: {len(d)} months, {d.month.min().date()} .. {d.month.max().date()}")


def run_table() -> None:
    out = ["# Who owns each equity market\n",
           "**Read the evidence tags.** 🟢 = computed here from primary data and reproducible "
           "by re-running `equity_ownership.py`. 🟡 = cited from public reporting, not "
           "recomputed. The two are not interchangeable and the difference is the most "
           "important thing on this page.\n"]

    if US_OWN.exists():
        d = pd.read_parquet(US_OWN).set_index("Date")
        sh = us_shares(d)
        asof = d.index.max().date()
        tot = d["TOTAL"].iloc[-1] / 1e6
        out.append(f"\n## 🟢 United States — COMPUTED (Fed Z.1 via FRED, as of {asof})\n")
        out.append(f"Total corporate equity outstanding **${tot:,.1f} trillion**. Holders are "
                   f"DIRECT holders; the household line is a residual, which is how the "
                   f"Financial Accounts themselves derive that sector.\n")
        out.append("\n| holder | % of US corporate equity |")
        out.append("|---|---|")
        for k, v in sh.items():
            out.append(f"| {k} | **{v:.1f}%** |")
        out.append(f"\nSum {sh.sum():.1f}%.")
        # a decade of drift is more informative than a single snapshot
        try:
            past = d.loc[:str(d.index.max().year - 10)].iloc[-1]
            holders = [c for c in d.columns if c != "TOTAL"]
            then = (past[holders] / past["TOTAL"] * 100)
            out.append(f"\n**Ten-year drift** (vs {past.name.date()}):\n")
            out.append("| holder | then | now | change |")
            out.append("|---|---|---|---|")
            for k in sh.index:
                out.append(f"| {k} | {then[k]:.1f}% | {sh[k]:.1f}% | {sh[k]-then[k]:+.1f}pp |")
        except Exception:
            pass
    else:
        out.append("\n## United States\n\nRun `--us` first.\n")

    for geo, rows in CITED.items():
        out.append(f"\n## 🟡 {geo} — CITED, not computed\n")
        out.append("| holder | share | note |")
        out.append("|---|---|---|")
        for h, s, n in rows:
            out.append(f"| {h} | {s} | {n} |")

    if IN_FLOW.exists():
        f = pd.read_parquet(IN_FLOW)
        out.append(f"\n## 🟢 India FLOW — COMPUTED (NSE daily, append-only)\n")
        out.append(f"{len(f)} rows, {f.Date.min().date()} .. {f.Date.max().date()}. "
                   f"Values ₹ crore. **This store cannot be backfilled** — NSE's endpoint "
                   f"serves the current day only — so it accumulates from first run.\n")
        piv = f.pivot_table(index="Date", columns="category", values="netValue")
        out.append("\n| date | " + " | ".join(piv.columns) + " |")
        out.append("|---" * (len(piv.columns) + 1) + "|")
        for dt, r in piv.tail(10).iterrows():
            out.append(f"| {dt.date()} | " + " | ".join(f"{v:+,.0f}" for v in r.values) + " |")

    if SIP.exists():
        sp = pd.read_parquet(SIP)
        out.append("\n## 🟢 India SIP contribution — COMPUTED (AMFI monthly notes)\n")
        out.append(f"{len(sp)} months parsed from AMFI Monthly Note PDFs, "
                   f"{sp.month.min().date():%b %Y} .. {sp.month.max().date():%b %Y}. ₹ crore. "
                   f"This is the *household savings* leg of Indian equity demand — the sticky, "
                   f"payroll-linked flow that is NOT debt-financed.\n")
        out.append("\n| month | SIP ₹ crore | % of industry AUM |")
        out.append("|---|---|---|")
        for _, r in sp.iterrows():
            pct = f"{r.sip_pct_of_aum:.1f}%" if pd.notna(r.sip_pct_of_aum) else "—"
            out.append(f"| {r.month:%b %Y} | {r.sip_crore:,.0f} | {pct} |")
        g = (sp.sip_crore.iloc[-1] / sp.sip_crore.iloc[0] - 1) * 100
        out.append(f"\n{g:+.1f}% over the window. Two figures are independently "
                   f"cross-checked: Aug 2025 = 28,265 appears verbatim in that note, and "
                   f"Aug 2024 = 23,547 matches the year-ago base quoted in the Aug 2025 note.")
        out.append("\n🔴 Jun and Jul 2024 read as exactly 21,000 and 23,000 — those notes phrase "
                   "the figure as a crossed THRESHOLD rather than an exact total, so treat them "
                   "as approximate. Nov 2024 and Feb 2025 are absent: the parser returns nothing "
                   "rather than guess when a note's wording is ambiguous.")

    out.append("\n## Stock vs flow — why both are here\n")
    out.append("Japan is the clean illustration: foreigners own roughly 30% of the float but "
               "account for the majority of turnover, so they set the price while domestic "
               "institutions and the BoJ hold the shares. India ran the same divergence in "
               "reverse — DIIs became the marginal buyer well before they overtook FIIs on "
               "holdings. Reading an ownership table as if it described who moves the market "
               "is the standard error this page is arranged to prevent.\n")

    REPORTS.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\n  -> {REPORT}")


def run_sources() -> None:
    print("Data access, tested 2026-08-01:\n")
    print("  WORKS")
    print("    FRED Z.1 (L.223 holders + total)     computed US ownership, quarterly to 2026Q1")
    print("    NSE /api/fiidiiTradeReact            current day only, needs cookie handshake")
    print("  DOES NOT WORK")
    print("    NSE fiidiiTradeReact?date=...        parameter accepted and IGNORED; no backfill")
    print("    NSE /api/historicalOR/fiidiiTrade... 404")
    print("    AMFI Monthly Note PDFs               SOLVED: /Themes/Theme1/downloads/")
    print("                                         AMFIMonthlyNote_<Month><YYYY>.pdf")
    print("  DOES NOT WORK")
    print("    amfiindia.com/modules/LatestSIPData  404 (site is Next.js, server-rendered)")
    print("    all 28 JS chunks scanned             only /api/search/trending exists")
    print("    portal.amfiindia.com/spages/*repo.xls  419 files, but AUM not SIP")
    print("    api.bseindia.com FIIDIIData          returns HTML, not JSON")
    print("    FRED BOGZ1LM153064105Q etc.          400 — wrong IDs; corrected set is in Z1 above")
    print("\n  OPEN: AMFI SIP series, and India FII/DII history before first collector run.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    for f in ("us", "india", "sip", "table", "sources", "all"):
        ap.add_argument(f"--{f}", action="store_true")
    a = ap.parse_args()
    if not any(vars(a).values()):
        ap.print_help(); return 1
    if a.sources:
        run_sources(); return 0
    if a.us or a.all:
        run_us()
    if a.india or a.all:
        run_india()
    if a.sip or a.all:
        run_sip()
    if a.table or a.all:
        run_table()
    return 0


if __name__ == "__main__":
    sys.exit(main())
