#!/usr/bin/env python3
"""
price_quality.py — content-level audit of the PRICE stores, run beside freshness, because fresh and
correct are different properties and this pipeline has shipped each without the
other.

NOT THE SAME FILE AS `data_quality.py`. That sibling is a Great-Expectations-style
suite over the FUNDAMENTALS warehouse — ratio derivation, PE/PB/ROE coverage,
key uniqueness on ticker×fy_end. This one audits the PRICE stores the daily brief
is built from. Its freshness section reports each panel's max date per market;
this file exists because a max date is exactly what hid the 2026-08-19 failure.

WHY A SEPARATE LAYER
────────────────────
`data_state.py` asks one question: does this store hold the session it should?
A store can pass that and still be wrong, and both halves have actually failed
here:

  * FRESH BUT WRONG. `market_daily.snapshots` carried 18 and 19 Aug rows for
    NVDA all holding the 17 Aug close of 225.01. Correct date stamp, correct row
    count, frozen price. Every age-based check passed.
  * STALE BUT WELL-FORMED. The 19 Aug US scan was internally immaculate —
    5,829 rows, no nulls, sane ranges — and every price was a session old.

So freshness is graded by SESSION (data_state) and correctness by CONTENT
(here). Neither subsumes the other.

WHY "DATA AGE" IS THE WRONG HEADLINE METRIC
───────────────────────────────────────────
The standard freshness toolkit leads with latency and age — time between source
timestamp and local arrival. That metric is necessary and it is also precisely
the one that failed on 2026-08-19: `market_ingest.py --status` reported the US
feed at age 0d while two thirds of the universe was two sessions behind, because
rows HAD arrived on time — they just described the wrong session, and some
described no new session at all.

Age measures the pipe. These checks measure the payload. The one industry check
that does catch a frozen payload is expected-change-rate verification, and it is
implemented here as FLATLINE — the single most valuable check in this file for
this pipeline, because carry-forward is its characteristic failure.

THE CHECKS
──────────
  FLATLINE     symbols whose close has not moved across the last N sessions.
               A real session moves nearly every liquid name; a carried-forward
               or re-served cache moves none. This is the NVDA 225.01 detector.
  COVERAGE     symbols whose last bar predates the expected session. Reported as
               a fraction, so a 66%-failed refresh reads as 66% and not as pass.
  SCHEMA       required columns exist with usable types.
  RANGE        close > 0, high >= low, low <= close <= high, volume >= 0.
  NULLS        null closes among rows that claim to be bars.
  DUPES        repeated (symbol, session) — two prices for one close.
  GAPS         trading days absent between the store's own first and last bar.

SEVERITY IS ABOUT ACTION, NOT ALARM. FAIL means do not build a brief on this.
WARN means it is visible and someone should look. Thresholds are set from
measured behaviour on this data, and each one is justified where it is defined
rather than being a round number chosen for looking reasonable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass, asdict

import data_catalog as dc
import market_sessions as ms

FAIL, WARN, PASS, SKIP = "FAIL", "WARN", "PASS", "SKIP"
_ICON = {FAIL: "🔴", WARN: "🟡", PASS: "✅", SKIP: "—"}

# ── thresholds, each with its measured justification ──────────────────────────
# A normal session moves ~97-99% of liquid names by at least a cent. 2026-08-19
# measured 15.7% of US snapshot symbols identical across 17→19 Aug while the
# store was two sessions behind for most of the universe, and 84% identical
# would have been the reading had the carry-forward been total. 10% flat over 3
# sessions is comfortably outside normal and well inside a real freeze.
FLATLINE_WARN, FLATLINE_FAIL = 0.10, 0.30
FLATLINE_SESSIONS = 3

# A refresh that strands >5% of the universe is a broken refresh, not a few
# delisted names. 2026-08-19 stranded 66%.
COVERAGE_WARN, COVERAGE_FAIL = 0.05, 0.25

NULL_WARN, NULL_FAIL = 0.01, 0.05

# Checks whose Finding.value is a COUNT rather than a fraction. Kept as an
# explicit set so adding a count-valued check forces a decision here instead
# of silently inheriting percentage formatting.
_COUNT_CHECKS = {"gaps"}
DUPE_WARN = 0.001


@dataclass
class Finding:
    dataset: str
    check: str
    status: str
    value: float | None
    detail: str

    @property
    def bad(self) -> bool:
        return self.status == FAIL


def _grade(v: float, warn: float, fail: float) -> str:
    return FAIL if v >= fail else (WARN if v >= warn else PASS)


def _src_for(ds: dc.Dataset) -> tuple[str, str] | None:
    """(duckdb source, symbol expression) for a price dataset, or None.

    Per-ticker trees carry the symbol in the FILENAME, not a column, so they are
    read with `filename=true` and the symbol recovered from the path. Auditing
    them matters more than auditing the tidy long-format panels: on 2026-08-19
    `market_cache/ohlc` was the store the US scan actually read, and it was the
    one nothing could see into.
    """
    loc = ds.location
    if ds.id.startswith("warehouse."):
        try:
            import warehouse_paths as wh

            return f"{wh.root()}/ohlcv/{ds.market}/*.parquet", '"Symbol"'
        except Exception:
            return None
    if loc.endswith(".parquet"):
        return loc, '"Symbol"'
    if (p := dc.Path(loc)).is_dir() and any(p.glob("*.parquet")):
        return (f"{loc}/*.parquet",
                "regexp_extract(filename, '([^/]+)\\.parquet$', 1)")
    return None


def audit_price_store(ds: dc.Dataset, expected: dt.date) -> list[Finding]:
    import duckdb

    got = _src_for(ds)
    if not got:
        return [Finding(ds.id, "schema", SKIP, None, "no readable parquet source")]
    src, SYM = got
    per_ticker = SYM.startswith("regexp")
    # `filename=true` is only legal (and only needed) for the globbed tree.
    READ = (f"read_parquet('{src}', filename=true)" if per_ticker
            else f"read_parquet('{src}')")
    con = duckdb.connect()
    out: list[Finding] = []

    try:
        cols = {c[0].lower(): c[1] for c in
                con.execute(f"DESCRIBE SELECT * FROM {READ}").fetchall()}
    except Exception as e:
        return [Finding(ds.id, "schema", FAIL, None, f"unreadable: {e}")]

    need = ["date", "close"] if per_ticker else ["date", "symbol", "close"]
    miss = [c for c in need if c not in cols]
    out.append(Finding(ds.id, "schema", FAIL if miss else PASS, None,
                       f"missing {miss}" if miss else f"{len(cols)} columns"))
    if miss:
        return out

    has_hl = "high" in cols and "low" in cols
    has_vol = "volume" in cols

    # ── NULLS / RANGE / DUPES in one pass ────────────────────────────────────
    rng = ""
    if has_hl:
        rng = (", sum(CASE WHEN High < Low THEN 1 ELSE 0 END) hl"
               ", sum(CASE WHEN Close > High OR Close < Low THEN 1 ELSE 0 END) oob")
    vol = ", sum(CASE WHEN Volume < 0 THEN 1 ELSE 0 END) nv" if has_vol else ""
    row = con.execute(
        f"SELECT count(*) n, sum(CASE WHEN Close IS NULL THEN 1 ELSE 0 END) n_null,"
        f" sum(CASE WHEN Close <= 0 THEN 1 ELSE 0 END) nonpos {rng}{vol}"
        f" FROM {READ}").fetchone()
    n = row[0] or 1
    nulls, nonpos = row[1] or 0, row[2] or 0
    out.append(Finding(ds.id, "nulls", _grade(nulls / n, NULL_WARN, NULL_FAIL),
                       nulls / n, f"{nulls:,}/{n:,} null closes"))
    bad_rng = nonpos
    detail = f"{nonpos:,} close<=0"
    if has_hl:
        hl, oob = row[3] or 0, row[4] or 0
        bad_rng += hl + oob
        detail += f", {hl:,} high<low, {oob:,} close outside [low,high]"
    if has_vol:
        bad_rng += row[-1] or 0
        detail += f", {row[-1] or 0:,} negative volume"
    out.append(Finding(ds.id, "range", FAIL if bad_rng > n * 0.001 else
                       (WARN if bad_rng else PASS), bad_rng / n, detail))

    # The India store is keyed (Symbol, Date, _exch) — the same scrip legitimately
    # has an NSE and a BSE bar for one session. Grouping without the exchange
    # reported 552,797 "duplicates" in `bhav.assembled`, all of them correct dual
    # listings. A check that fires on healthy data trains the operator to ignore
    # it, so the key includes the exchange wherever the store carries one.
    exch = ', "_exch"' if "_exch" in cols else ""
    key = f"(symbol, session{', exchange' if exch else ''})"
    d = con.execute(
        f"SELECT count(*) FROM (SELECT {SYM} s, Date{exch} FROM {READ}"
        f" GROUP BY {'1,2,3' if exch else '1,2'} HAVING count(*) > 1)").fetchone()[0] or 0
    out.append(Finding(ds.id, "dupes", _grade(d / n, DUPE_WARN, DUPE_WARN * 10),
                       d / n, f"{d:,} duplicate {key} rows"))

    # ── COVERAGE — did the ACTIVE universe carry forward? ────────────────────
    # Measured over symbols that traded in the PRIOR session, not over every
    # symbol the store has ever held. A ten-year panel accumulates thousands of
    # delisted, suspended and permanently illiquid scrips that will never get
    # another bar; counting them made `bhav.assembled` read 42% behind on a day
    # India was perfectly current, and a metric that cannot reach green on
    # healthy data is one the operator learns to skip past.
    #
    # "Traded last session, missing this session" is the actual failure — and it
    # is exactly what 2026-08-19 looked like: 3,872 US tickers with a 17 Aug bar
    # and no 18 Aug bar.
    prev = ms.previous_session(ds.market, expected)
    cov = con.execute(
        f"SELECT count(*) tot, sum(CASE WHEN m >= DATE '{expected}' THEN 1 ELSE 0 END) ok"
        f" FROM (SELECT {SYM} s, max(Date) m FROM {READ} GROUP BY 1)"
        f" WHERE m >= DATE '{prev}'").fetchone()
    tot, ok = cov[0] or 0, cov[1] or 0
    if tot == 0:
        # Nothing traded in the prior session either — the store is behind by
        # more than one session, which `data_state` already grades. Reporting 0/0
        # as 100% failure here would double-count that.
        out.append(Finding(ds.id, "coverage", WARN, None,
                           f"no symbols with a bar on or after {prev} — store is "
                           f"more than one session behind (see data_state)"))
    else:
        behind = 1 - ok / tot
        out.append(Finding(ds.id, "coverage", _grade(behind, COVERAGE_WARN, COVERAGE_FAIL),
                           behind,
                           f"{tot - ok:,}/{tot:,} symbols active on {prev} "
                           f"have no {expected} bar"))

    # ── FLATLINE — the carry-forward detector ────────────────────────────────
    flat = con.execute(f"""
        WITH r AS (SELECT {SYM} s, Close,
                          row_number() OVER (PARTITION BY {SYM} ORDER BY Date DESC) rn
                   FROM {READ}),
             w AS (SELECT s, count(DISTINCT Close) u, count(*) c
                   FROM r WHERE rn <= {FLATLINE_SESSIONS} GROUP BY 1)
        SELECT count(*) tot, sum(CASE WHEN u = 1 AND c >= {FLATLINE_SESSIONS}
                                      THEN 1 ELSE 0 END) flat FROM w""").fetchone()
    ftot, fflat = flat[0] or 1, flat[1] or 0
    out.append(Finding(ds.id, "flatline", _grade(fflat / ftot, FLATLINE_WARN, FLATLINE_FAIL),
                       fflat / ftot,
                       f"{fflat:,}/{ftot:,} symbols unchanged across last "
                       f"{FLATLINE_SESSIONS} bars"))

    # ── GAPS — sessions the store skipped inside its own range ───────────────
    lo, hi = con.execute(
        f"SELECT min(Date), max(Date) FROM {READ}").fetchone()
    if lo and hi:
        held = {r[0] for r in con.execute(
            f"SELECT DISTINCT Date FROM {READ}"
            f" WHERE Date >= DATE '{(dc._as_date(hi) - dt.timedelta(days=40))}'").fetchall()}
        held = {dc._as_date(x) for x in held}
        want = ms.sessions_between(ds.market, dc._as_date(hi) - dt.timedelta(days=40),
                                   dc._as_date(hi))
        gaps = [d for d in want if d not in held]
        out.append(Finding(ds.id, "gaps", WARN if gaps else PASS, len(gaps),
                           f"{len(gaps)} missing session(s) in last 40d"
                           + (f": {', '.join(str(g) for g in gaps[:4])}" if gaps else "")))
    return out


def audit(markets: list[str] | None = None, at: dt.datetime | None = None) -> list[Finding]:
    at = at or dt.datetime.now(ms.UTC)
    findings: list[Finding] = []
    for ds in dc.catalog(at):
        if ds.kind != "prices":
            continue
        if markets and ds.market not in markets:
            continue
        exp = ms.expected_session(ds.market, at)
        findings += audit_price_store(ds, exp)
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="content-level data quality audit")
    ap.add_argument("--markets", nargs="*")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any FAIL")
    a = ap.parse_args()

    fs = audit(a.markets)
    if a.json:
        print(json.dumps([asdict(f) for f in fs], indent=2, default=str))
        return 1 if (a.strict and any(f.bad for f in fs)) else 0

    print("=== DATA QUALITY AUDIT ===")
    cur = None
    for f in fs:
        if f.dataset != cur:
            cur = f.dataset
            print(f"\n  {cur}")
        # 🔴 Format by WHAT THE NUMBER IS, not by its magnitude. Deciding on
        # `value <= 1` treated the `gaps` COUNT as a ratio: 0 gaps printed as
        # "0.00%" (harmless, and why it went unseen) but the very first single
        # missing session would have printed "100.00%" — total failure, from one
        # absent day. `_COUNT_CHECKS` names the checks whose value is a count.
        v = "" if f.value is None else (
            f"{f.value:7.0f}" if f.check in _COUNT_CHECKS else f"{f.value:7.2%}")
        print(f"    {_ICON[f.status]} {f.check:9} {v:>8}  {f.detail}")

    bad = [f for f in fs if f.status == FAIL]
    warn = [f for f in fs if f.status == WARN]
    print(f"\n  {len(bad)} FAIL · {len(warn)} WARN · "
          f"{sum(1 for f in fs if f.status == PASS)} PASS")
    for f in bad:
        print(f"    🔴 {f.dataset} [{f.check}] {f.detail}")
    return 1 if (a.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
