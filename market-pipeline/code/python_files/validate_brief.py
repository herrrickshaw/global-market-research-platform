#!/usr/bin/env python3
"""
validate_brief.py — cross-check the India scan against independent price
witnesses (price_sources.SOURCES) BEFORE sending.

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
Samples the most liquid India picks (most liquid => most likely to be quoted by
every witness) and asks each witness for the close on/before the scan's day:

  1. CLOSE DATE   — the strong check. Detects stale data directly; a price can
                    coincidentally look plausible, a wrong date cannot hide.
  2. PRICE        — within tolerance, by majority of the witnesses that answered
                    at the current session (see _judge for the abstain rules).

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
import json
import sys

import pandas as pd

import price_sources
import scan_files

# Exact equality is wrong to demand: Alpha Vantage quotes BSE against our NSE
# close (worst basis measured 0.263%), and the retired screener.in rounded to
# four significant figures. 2% is 7x the widest normal basis and still far
# below the ~4% gaps that have marked every real staleness incident.
PRICE_TOL_PCT = 2.0
MIN_VERIFIED = 3          # below this we cannot claim the brief was validated
WITNESS_LAG_DAYS = 5      # a name's only witnesses this far behind the sample abstain


def _latest_scan() -> str:
    return scan_files.latest("IN")


def _scan_staleness_note(path: str) -> str:
    return scan_files.staleness_note(path)


def _scan_date(path: str) -> _dt.date:
    """The day the workbook was built. Sources are anchored to this rather than to
    'now', which is what lets the gate run at any hour: the question becomes 'what
    did this close at on or before <scan day>?', and that has the same answer at
    11:00 as it does at 06:30."""
    return scan_files.stamp(path) or _dt.date.today()


def _session(fetched: list):
    """Newest close any source quoted for any name fetched so far (None if none)."""
    dates = [v["date"] for _, _, a in fetched for v in a.values()]
    return max(dates) if dates else None


def _judge(sym: str, ours: float, answered: dict, session) -> dict:
    """One name's verdict from the sources that answered for it.

    `session` is the newest close any source quoted for any name in the sample.
    """
    # AGREED RULE: pass on one, suppress on zero. A name with no answering
    # source is unverifiable — skipped, not failed, because a 404 on a
    # BSE-only name (AUSTENG) says nothing about the pick.
    if not answered:
        return {"symbol": sym, "status": "skip", "why": "no source answered"}
    newest = max(v["date"] for v in answered.values())
    # Every witness for this name is LAGGING the session the rest of the sample
    # reached, but only by a few days — so they abstain and the name is
    # unverifiable, exactly as if nobody had answered. Measured 2026-10-27: BSE
    # (BSE Ltd) is answered only by yfinance (alphavantage rejects `BSE.BSE`,
    # twelvedata 404s), which quoted the 10-23 close while ours was the correct
    # 10-26 bhavcopy close; the lone stale vote suppressed a correct send. The
    # same-name rule below could not help: there was no second witness to be
    # newer than it. Beyond WITNESS_LAG_DAYS the name still votes and the `off`
    # check still fails it — that is the MODISONLTD shape (frozen for weeks).
    if newest < session and (session - newest).days <= WITNESS_LAG_DAYS:
        seen = "; ".join(f"{s} {v['price']:.2f} @{v['date']}" for s, v in answered.items())
        return {"symbol": sym, "status": "skip",
                "why": f"only lagging witnesses, {seen} vs session {session} — abstained"}
    # A witness quoting an OLDER session than another witness for the same
    # name is comparing against a different close — it abstains. Measured
    # 2026-10-20: yfinance returned HDFCBANK @10-16 (2.31% off) while ours and
    # alphavantage agreed @10-19 (0.06%); the 1-1 tie suppressed a correct
    # send, as on 2026-09-11 (BHARTIARTL). If OUR price is the stale one, the
    # current witness still disagrees, so the MODISONLTD case is still caught.
    stale = [s for s, v in answered.items() if v["date"] < newest]
    voting = {s: v for s, v in answered.items() if s not in stale}
    agree = [s for s, v in voting.items() if v["verdict"] == "agree"]
    dis = [s for s, v in voting.items() if v["verdict"] == "disagree"]
    # Majority of the CURRENT sources that answered. With a single answer that
    # is just that answer; a tie counts as disagreement, because the gate's job
    # is to catch bad data and a split jury is not a confirmation.
    return {"symbol": sym, "status": "ok" if len(agree) > len(dis) else "MISMATCH",
            "ours": ours, "sources": answered, "newest": newest,
            "agree": agree, "disagree": dis, "stale": stale}


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
    ledger, fetched = [], []

    for r in picks.to_dict("records"):
        # Stop once enough names would vote at the session the sample has reached
        # so far. Judged again on the final session below, so a name counted here
        # can still turn into an abstention once a later name moves the session on.
        session = _session(fetched)
        if session and sum(_judge(*f, session)["status"] != "skip" for f in fetched) >= sample:
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
        fetched.append((sym, ours, answered))

    session = _session(fetched)
    checks = [_judge(*f, session) for f in fetched]
    verified = sum(c["status"] != "skip" for c in checks)

    price_sources.record(ledger)

    # Sources that were asked and answered NOTHING, with the reason they gave.
    # A silent source still appears in the header, which is how twelvedata sat
    # inert for 79 consecutive checks (registered 2026-08-29, `--source-report`
    # read `answered 0.0%`) while the line advertised three witnesses. That is
    # not cosmetic: silence drops the quorum back to two, and at two a 1-1 split
    # is a MISMATCH, so one stale witness suppresses a correct send — precisely
    # the failure the third witness was registered to prevent, and precisely
    # what suppressed the 2026-09-11 brief on a stale yfinance BHARTIARTL date.
    #
    # Diagnostic only: a silent source must NOT vote and must NOT fail the send.
    # An absent key is a missing witness, not evidence against the prices.
    mute = {}
    for src in price_sources.SOURCES:
        rows = [r for r in ledger if r["source"] == src]
        if rows and not any(r["theirs"] is not None for r in rows):
            errs = [r["error"] for r in rows if r["error"]]
            mute[src] = errs[0] if errs else "no answer"

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
    #
    # Judged on each name's NEWEST answer, not per source: a source that is behind
    # on some names (yfinance, 2026-10-20: 3 names @10-16, 3 @10-19) is a lagging
    # witness, not evidence the pick stopped trading. A name is off only when no
    # source quotes it at the session the rest of the sample reached.
    off, stale_feed = [], []
    dated = [c for c in checks if "newest" in c]
    if len(dated) >= 2:
        session = max(c["newest"] for c in dated)
        off = [f"{c['symbol']}@{c['newest']}" for c in dated if c["newest"] != session]
    for src in price_sources.SOURCES:
        ds = [c["sources"][src]["date"] for c in checks if src in c.get("sources", {})]
        if len(ds) < 2:
            continue
        common = max(set(ds), key=ds.count)
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
        reason = (f"no source quotes these names at the latest session — {off}. They "
                  f"are liquidity-gated so they trade every day; an older close means "
                  f"stale data, not a quirk.")
    elif stale_feed:
        reason = f"source feed frozen — {'; '.join(stale_feed)}"
    return {"ok": ok, "reason": reason, "scan": f.split("/")[-1], "asof": asof.isoformat(),
            "verified": verified, "checks": checks, "mute": mute}


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
    # .get with a default: the no-workbook early return carries no "mute" key,
    # and per the banner above a KeyError here would suppress the send.
    mute = r.get("mute") or {}
    for src, why in mute.items():
        print(f"  ⚠ {src} answered nothing ({why}) — NOT voting; "
              f"effective quorum {len(price_sources.SOURCES) - len(mute)} "
              f"of {len(price_sources.SOURCES)}")
    for c in r["checks"]:
        if c["status"] == "skip":
            print(f"    -  {c['symbol']:12s} skipped ({c['why']})")
            continue
        # round for display only: yfinance carries float32 artifacts
        # (1431.800048828125), which are noise here and make the line unreadable.
        detail = " · ".join(
            f"{s} {v['price']:.2f} ({v['diff_pct']}%) @{v['date']}"
            + (" [older session, not voting]" if s in c.get("stale", ()) else "")
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
