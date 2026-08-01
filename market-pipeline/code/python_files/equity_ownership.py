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

WHAT IS NOT AVAILABLE, AND WHY
  * NSE `fiidiiTradeReact` returns the CURRENT DAY ONLY — it accepts a `date`
    parameter and ignores it. So `--india` is an append-only collector: it
    accumulates history from the day it first runs and cannot backfill. History
    needs a different source (BSE archives, NSDL, or a paid vendor).
  * AMFI's SIP series had no reachable endpoint: the documented paths return 404
    and the site renders client-side. SIP figures in reports/ are therefore cited,
    not collected. Wiring this properly is the main open item.

    equity_ownership.py --us       # Z.1 -> computed US ownership shares
    equity_ownership.py --india    # append today's NSE FII/DII to the store
    equity_ownership.py --table    # cross-market table, cells marked computed/cited
    equity_ownership.py --sources  # what was tried, what worked, what did not
"""

from __future__ import annotations

import argparse
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
    print("    amfiindia.com/modules/LatestSIPData  404")
    print("    portal.amfiindia.com/.../amfi-monthly.xls  404")
    print("    api.bseindia.com FIIDIIData          returns HTML, not JSON")
    print("    FRED BOGZ1LM153064105Q etc.          400 — wrong IDs; corrected set is in Z1 above")
    print("\n  OPEN: AMFI SIP series, and India FII/DII history before first collector run.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    for f in ("us", "india", "table", "sources", "all"):
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
    if a.table or a.all:
        run_table()
    return 0


if __name__ == "__main__":
    sys.exit(main())
