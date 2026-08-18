#!/usr/bin/env python3
"""
validate_brief.py — cross-check the India scan against screener.in BEFORE sending.

WHY THIS EXISTS
---------------
The screeners emit *recommendations* (Darvas / golden cross / DMA). Checking the
brief against our own scan artifact only proves internal consistency — it cannot
detect a scan that is confidently wrong about the world. On 2026-07-15 every
internal check passed while the pipeline was:

  * quoting MODISONLTD at 284.6 / +3.6% from **2026-05-29**, seven weeks stale,
    and emitting it as a GOLDEN_CROSS pick (screener.in: Rs 289 / -2.71% on 14 Jul).
    Cause: NSE-precedence was applied per SYMBOL, so a stock that left NSE but
    still trades on BSE froze at its last NSE bar. 270 of 7,833 symbols, up to
    313 days stale. The brief, the scan, the parquet and the warehouse all agreed
    with each other and were all wrong together.
  * recommending LIQUIDSBI — an ETF — as a golden cross.
  * leading with AUSTENG on +16% while it turned over Rs 2.1 lakh/day.

Only an EXTERNAL source catches that class of bug. This encodes the rule so the
unattended 00:30 run is held to it too, not just the runs a human watches.

WHAT IT CHECKS
--------------
Samples the most liquid India picks (most liquid => most likely NSE-listed and
present on screener.in) and compares against screener.in's public company page:

  1. CLOSE DATE   — the strong check. Detects stale data directly; a price can
                    coincidentally look plausible, a wrong date cannot hide.
  2. PRICE        — within tolerance (screener.in rounds to ~4 significant
                    figures: it shows Rs 1,099 for 1098.8, Rs 289 for 289.75).

Exit codes:
  0  validated — safe to send
  1  MISMATCH or unverifiable — caller must NOT send

Usage:
    python3 validate_brief.py                 # sample 6, 2% tolerance
    python3 validate_brief.py --sample 8 --json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import re
import sys
import time

import pandas as pd
import requests

import price_sources

UA = {"User-Agent": "Mozilla/5.0 (research)"}
BASE = "https://www.screener.in/company/{}/"

# screener.in rounds to ~4 sig figs, so exact equality is wrong to demand:
#   1098.8 -> "Rs 1,099" (0.02%)   860.55 -> "Rs 861" (0.05%)   289.75 -> "Rs 289" (0.26%)
PRICE_TOL_PCT = 2.0
MIN_VERIFIED = 3          # below this we cannot claim the brief was validated


def _latest_scan() -> str:
    fs = sorted(glob.glob("indian_full_scan/indian_full_scan_*.xlsx"))
    return fs[-1] if fs else ""


def _scan_staleness_note(path: str) -> str:
    """'' if the workbook is today's, otherwise a line naming the real problem.

    Without this, a workbook left over from a day the scan did not run shows up
    here as ordinary price mismatches against screener.in — true, but it points
    at the prices rather than at the missing run. On Sat 2026-08-01 that read as
    '1 price mismatch beyond 2.0%' when the actual fact was that Friday's
    workbook was still on disk because the 03:00 job never fired.
    """
    name = path.rsplit("/", 1)[-1]
    m = re.search(r"_(\d{8})_\d{4}\.xlsx$", name)
    if not m:
        return ""
    try:
        stamp = _dt.datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return ""
    age = (_dt.date.today() - stamp).days
    if age <= 0:
        return ""
    return (f"  ⚠ SCAN IS {age} DAY(S) OLD — {name}; expected "
            f"{_dt.date.today():%Y-%m-%d}. The scan step did not run, so any mismatch "
            f"below is stale data, not a bad pick.")


def _scan_date(path: str) -> _dt.date:
    """The day the workbook was built. Sources are anchored to this rather than to
    'now', which is what lets the gate run at any hour: the question becomes 'what
    did this close at on or before <scan day>?', and that has the same answer at
    11:00 as it does at 06:30."""
    m = re.search(r"_(\d{8})_\d{4}\.xlsx$", path.rsplit("/", 1)[-1])
    if m:
        try:
            return _dt.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            pass
    return _dt.date.today()


def validate(sample: int, tol: float) -> dict:
    f = _latest_scan()
    if not f:
        return {"ok": False, "reason": "no India scan workbook found", "checks": []}
    note = _scan_staleness_note(f)
    if note:
        # stderr, not stdout: --json is consumed by machines and a human-readable
        # banner ahead of the document makes it unparseable.
        print(note, file=sys.stderr)
    d = pd.read_excel(f, "All_Stocks")
    if "Median_Turnover" in d.columns:
        d = d.sort_values("Median_Turnover", ascending=False)
    picks = d.head(sample * 3)          # over-sample: BSE-only names will 404

    asof = _scan_date(f)
    run_ts = _dt.datetime.now().isoformat(timespec="seconds")
    checks, verified, ledger = [], 0, []

    for r in picks.to_dict("records"):
        if verified >= sample:
            break
        sym, ours = str(r["Symbol"]), float(r["LTP"])
        answered = {}
        for src, got in price_sources.fetch_all(sym, asof).items():
            row = {"run_ts": run_ts, "asof": asof.isoformat(), "symbol": sym,
                   "source": src, "ours": ours, "theirs": None, "diff_pct": None,
                   "their_date": None, "verdict": "", "error": got.get("error", "")}
            if not got.get("error"):
                theirs = got["price"]
                diff = abs(ours - theirs) / theirs * 100 if theirs else 999
                verdict = "agree" if diff <= tol else "disagree"
                row.update(theirs=theirs, diff_pct=round(diff, 3),
                           their_date=got["date"].isoformat(), verdict=verdict)
                answered[src] = {"price": theirs, "date": got["date"],
                                 "diff_pct": round(diff, 2), "verdict": verdict}
            ledger.append(row)

        # AGREED RULE: pass on one, suppress on zero. A name with no answering
        # source is unverifiable — skipped, not failed, because a 404 on a
        # BSE-only name (AUSTENG) says nothing about the pick.
        if not answered:
            checks.append({"symbol": sym, "status": "skip", "why": "no source answered"})
            continue
        verified += 1
        agree = [s for s, v in answered.items() if v["verdict"] == "agree"]
        dis = [s for s, v in answered.items() if v["verdict"] == "disagree"]
        # Majority of the sources that ANSWERED. With a single answer that is just
        # that answer; a tie counts as disagreement, because the gate's job is to
        # catch bad data and a split jury is not a confirmation.
        checks.append({"symbol": sym, "status": "ok" if len(agree) > len(dis) else "MISMATCH",
                       "ours": ours, "sources": answered,
                       "agree": agree, "disagree": dis})

    price_sources.record(ledger)
    bad = [c for c in checks if c["status"] == "MISMATCH"]

    # Date agreement WITHIN each source, across names. Deliberately not across
    # sources: measured 2026-08-12, yfinance returned the 08-10 close while
    # screener returned 08-11 for the same request — both correct, they just
    # publish on different lags. Comparing dates between sources would fail on
    # that lag alone, every single run.
    #
    # Within a source the check keeps its original teeth: every pick is liquidity
    # -gated and therefore trades daily, so one name carrying an older close is
    # stale data, not a holiday quirk. That is the MODISONLTD case — a single name
    # frozen seven weeks back while every other check passed.
    off, stale_feed = [], []
    for src in price_sources.SOURCES:
        ds = [c["sources"][src]["date"] for c in checks if src in c.get("sources", {})]
        if len(ds) < 2:
            continue
        common = max(set(ds), key=ds.count)
        off += [f"{c['symbol']}@{src}" for c in checks
                if src in c.get("sources", {}) and c["sources"][src]["date"] != common]
        # A source whose whole feed is frozen agrees with itself perfectly, so the
        # per-name check above cannot see it. Lag is normal (yfinance is routinely
        # a day behind); a week is not.
        if (asof - common).days > 5:
            stale_feed.append(f"{src} newest close {common} vs scan {asof}")

    # The old MARKET-HOURS GUARD is gone, and deliberately so. It existed because
    # screener.in serves an undated live quote once NSE opens, so the date check
    # silently parsed nothing and prices were compared against intraday ticks
    # (2026-07-15 09:15 IST: 5 of 6 dates None). That is now handled at the source:
    # every source in the registry must refuse an in-progress session itself, so an
    # intraday tick can never reach this function. Unverifiable still means
    # unverifiable — it just no longer means "the market happens to be open".
    #
    # 🔴 DO NOT REINSTATE THE GUARD HERE IF THIS BREAKS AGAIN. A tick that arrives
    # under a plausible date is invisible at this level: measured 2026-08-18 09:20
    # IST, yfinance returned today's live price stamped with today's date and every
    # check in this function passed it. Only the source knows whether the session it
    # is quoting has settled, so the refusal belongs there — a guard here would be
    # re-solving the 2026-07-15 problem in the one place that cannot see it.
    ok = (verified >= MIN_VERIFIED) and not bad and not off and not stale_feed
    reason = ""
    if verified < MIN_VERIFIED:
        reason = (f"only {verified} of {sample} verifiable (need {MIN_VERIFIED}) — "
                  f"no source answered for the rest; cannot confirm")
    elif bad:
        names = ", ".join(f"{c['symbol']} (ours {c['ours']}, "
                          + "; ".join(f"{s} {v['price']} {v['diff_pct']}%"
                                      for s, v in c["sources"].items()) + ")"
                          for c in bad)
        reason = f"{len(bad)} price mismatch(es) beyond {tol}%: {names}"
    elif off:
        reason = (f"close dates disagree within a source — {off}. These names are "
                  f"liquidity-gated so they trade every day; an older close means "
                  f"stale data, not a quirk.")
    elif stale_feed:
        reason = f"source feed frozen — {'; '.join(stale_feed)}"
    return {"ok": ok, "reason": reason, "scan": f.split("/")[-1], "asof": asof.isoformat(),
            "verified": verified, "checks": checks}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=6)
    ap.add_argument("--tolerance", type=float, default=PRICE_TOL_PCT)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--source-report", type=int, nargs="?", const=30, metavar="DAYS",
                    help="print each source's measured track record and exit")
    a = ap.parse_args()

    # Reporting only reads the ledger, so it must never be able to fail a send.
    if a.source_report:
        rep = price_sources.report(a.source_report)
        print(json.dumps(rep, indent=1) if a.json else
              # echo% is printed FIRST among the rates and flagged, because it is
              # the one that can invalidate the other two: a source that returns
              # our own number scores 100% answered and 100% agreed while telling
              # us nothing. ≥80% means it is a pipeline check, not a witness.
              "\n".join(f"  {r['source']:12s} {r['checks']:5d} checks · "
                        f"echo {r['echo_rate']:5.1f}%{'  ⚠ ECHO' if r['echo_rate'] >= 80 else '        '} · "
                        f"answered {r['response_rate']:5.1f}% · "
                        f"agreed {r['agree_rate']:5.1f}% · "
                        f"{r['disagreements']} disagreement(s) · "
                        f"avg |diff| {r['avg_abs_diff_pct']}%" for r in rep)
              or "  (no checks recorded yet)")
        return 0

    r = validate(a.sample, a.tolerance)
    if a.json:
        # default=str: `checks` carries real date objects because the staleness
        # arithmetic below needs them; only the wire format wants strings.
        print(json.dumps(r, indent=1, default=str))
        return 0 if r["ok"] else 1

    # 🔴 THIS BRANCH IS THE PRODUCTION PATH. daily_mailer.sh calls this script
    # WITHOUT --json and reads only the exit code, so anything that raises in
    # here exits non-zero and is indistinguishable from a real validation
    # failure — a formatting bug would silently suppress every send forever.
    # Keep it in step with the shape `validate()` actually returns.
    srcs = ", ".join(price_sources.SOURCES)
    print(f"  validating {r.get('scan','?')} against {srcs} "
          f"(tolerance {a.tolerance}%, asof {r.get('asof','?')})")
    for c in r["checks"]:
        if c["status"] == "skip":
            print(f"    -  {c['symbol']:12s} skipped ({c['why']})")
            continue
        # round for display only: yfinance carries float32 artifacts
        # (1431.800048828125), which are noise here and make the line unreadable.
        detail = " · ".join(
            f"{s} {v['price']:.2f} ({v['diff_pct']}%) @{v['date']}"
            for s, v in c["sources"].items())
        print(f"    {'ok' if c['status'] == 'ok' else '!!'} {c['symbol']:12s} "
              f"ours={c['ours']:<10} {detail}")
    if r["ok"]:
        print(f"  ✓ validated: {r['verified']} names, every answering source agreed")
        return 0
    bar = "=" * 72
    print(f"\n{bar}\n  ❌  BRIEF FAILED EXTERNAL VALIDATION — DO NOT SEND\n  {r['reason']}\n{bar}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
