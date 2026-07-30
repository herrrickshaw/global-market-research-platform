#!/usr/bin/env python3
"""
completeness_graph.py — a LangGraph audit of what this repo actually knows.

WHY THIS EXISTS. Today a live nightly job (`reentry_engine.py`, pipeline [13w])
was found running on a premise its OWN cited report contradicts: the docstring
claims "IN +12.9%/63d t14.2", while reports/tier_anomaly_backtest.md — the file
it names as its authority — now reports excess -2.01% median, t=0.06, and an
independently written second script (reentry_book.py) agrees at t=0.27. The
number was never re-checked after the backtest was extended. Nothing in the
pipeline noticed, because nothing was looking.

That is the failure this graph is built to catch, and it generalises: a
conclusion is only as good as (a) the data underneath it and (b) whether the
number quoted downstream still matches the number upstream. So there are two
audits here, not one:

  DATA COMPLETENESS  — for every source the regular analyses read: does it
                       exist, how many rows/symbols, what date span, how stale?
                       A conclusion resting on a table that stopped updating
                       three weeks ago is stale regardless of its t-stat.

  CLAIM CONSISTENCY  — for every script that quotes a number AND names the
                       report it came from: does that number still appear in
                       that report? This is mechanical, needs no LLM, and is
                       the check that would have flagged reentry_engine.

  POPULATION         — for a secondary store (Cassandra), how many rows are
                       actually POPULATED, not merely present. A load announcing
                       "fundamentals extended to 28,986 symbols" turned out to
                       carry prices and null fundamentals: `eps > 0` in ZERO rows
                       in every market, `pe > 0` in 112 rows total. A COUNT(*)
                       reports that as full coverage.

  GATE COVERAGE      — which regularly-run analyses apply the contamination
                       gate (contaminated(), which drops symbols with
                       uncorrected corporate actions) and which read the raw
                       panel unguarded. India still carries ~29 symbols whose
                       bonus issues CANNOT be verified (delisted/renamed, so
                       Yahoo has no adjusted series to check against —
                       MINDTREE, MOTHERSUMI, ABIRLANUVO). Scripts that skip the
                       gate silently inherit those discontinuities.

WHY LANGGRAPH. The four audits are independent and fan out in parallel from a
shared inventory, then join for synthesis. That is a graph, and expressing it as
one makes the dependency explicit and the parallelism free. The nodes are
deterministic Python — there is no LLM in this graph and no reason for one.
Every number below is measured, not generated.

🔴 THIS AUDIT DOES NOT VALIDATE CORRECTNESS. It checks presence, freshness,
consistency and gating. A table can be complete, fresh, internally consistent
and still wrong (the 2026-07-28 data_sufficiency.md reports a US liquid
universe of SIX stocks and a date range ending 2029 — complete-looking garbage).
Where a stated figure is impossible on its face, this audit flags it as
IMPLAUSIBLE rather than passing it through.

Usage:
  python3 completeness_graph.py
  python3 completeness_graph.py --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import operator
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, TypedDict

HERE = Path(__file__).resolve().parent
DSN = "dbname=market_data host=/tmp user=umashankar"
REPORTS = HERE / "reports"
OUT_MD = REPORTS / "completeness_graph.md"

# Sources the regularly-scheduled analyses read. `critical` marks the ones a
# daily conclusion depends on; a stale critical source is an alert, a stale
# non-critical one is a note.
# 🔴 STALENESS IS ONLY MEANINGFUL AGAINST AN EXPECTED CADENCE. A flat 7-day rule
# flagged three "stale critical sources" and every one was a modelling error, not
# a fault: nse_deep_ohlcv is an append-only static archive with NO live writer by
# design; india_quarterly was being measured on period_end, a reporting period,
# so a perfectly fresh quarterly table reads as a month behind between results
# seasons; and ohlcv_history has no writer anywhere in this repo — it belongs to
# the event-driven platform and is read, not maintained, here. Judging all three
# against "should have updated yesterday" produced three alarms and zero
# problems, which is how an audit teaches people to ignore it.
#
# tolerance is in days; None means no freshness expectation at all.
CADENCE = {"daily": 5, "weekly": 12, "quarterly": 120, "static": None,
           "external": None}
PG_SOURCES = [
    # (table, date column, critical, cadence)
    ("bhavcopy.cleaned_ohlcv", "trade_date", True, "daily"),
    ("bhavcopy.nse_deep_ohlcv", "trade_date", False, "static"),
    ("fundamentals.india_pe_daily", "obs_date", True, "daily"),
    ("fundamentals.india_quarterly", "filing_date", True, "quarterly"),
    ("fundamentals.ratios", None, False, "weekly"),
    ("funds.nav", "nav_date", False, "daily"),
    ("indices.nse_daily", "index_date", False, "daily"),
    ("indices.nse_tri", "index_date", False, "daily"),
    ("indices.custom_daily", "obs_date", False, "weekly"),
    ("market_daily.snapshots", "snapshot_date", True, "daily"),
    ("market_daily.ticker_freshness", None, True, "daily"),
    ("public.ohlcv_history", "date", False, "external"),
    ("public.global_fundamentals", None, False, "external"),
]

# Scripts that run on a schedule and assert something. (file, cited report)
SCHEDULED = [
    ("reentry_engine.py", "tier_anomaly_backtest.md"),
    ("prediction_filter.py", "mailer_prediction_audit.md"),
    # smallcap_screener writes reports/smallcap_screen.csv and custom_indices
    # writes indices.custom_daily in Postgres — neither produces a markdown
    # conclusion, so there is no document to check a quoted number against.
    # Mapping them to a .md that never existed produced "CITED REPORT MISSING",
    # which blamed the repo for the audit's own bad mapping. They are None here,
    # which surfaces the real and more interesting problem: both quote figures
    # (+3.07%, t 8.75 — the small-cap validation) that live in no reproducible
    # artefact at all, so a reader cannot check them without re-running the job.
    ("smallcap_screener.py", None),
    ("playbook_screener.py", "market_playbook.md"),
    ("watchlist_tiers.py", None),
    # the +3.07%/t 8.75 it quotes is the 126-bar small-cap validation, which
    # now persists to disk instead of only ever being printed to a terminal
    ("custom_indices.py", "smallcap_validation_hold126.md"),
    ("cluster_indices.py", "cluster_indices.md"),
    ("scan_price_reconcile.py", None),
]

# Analyses whose panel must be gated for uncorrected corporate actions.
GATED_EXPECT = ["pead_liquidity_study.py", "pead_portfolio.py", "cluster_indices.py",
                "smallcap_screener.py", "custom_indices.py", "peer_warranted.py",
                "etf_builder.py", "reentry_book.py"]

PCT = re.compile(r"[+-]\d+\.\d+\s?%")
TSTAT = re.compile(r"\bt\s?=?\s?-?\d+\.\d+")


class AuditState(TypedDict):
    sources: Annotated[list, operator.add]
    claims: Annotated[list, operator.add]
    gates: Annotated[list, operator.add]
    power: Annotated[list, operator.add]
    cassandra: Annotated[list, operator.add]
    notes: Annotated[list, operator.add]
    summary: str


def _con():
    import duckdb
    c = duckdb.connect()
    c.execute("INSTALL postgres")
    c.execute("LOAD postgres")
    c.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres, READ_ONLY)")
    return c


def inventory(state: AuditState) -> dict:
    """Measure every source: rows, symbols, span, staleness."""
    out, notes = [], []
    try:
        c = _con()
    except Exception as e:                                    # noqa: BLE001
        return {"sources": [], "notes": [f"warehouse unreachable: {str(e)[:80]}"]}

    today = date.today()
    for tbl, datecol, critical, cadence in PG_SOURCES:
        rec = {"source": tbl, "critical": critical, "kind": "postgres",
               "cadence": cadence, "tolerance": CADENCE.get(cadence)}
        try:
            rec["rows"] = c.execute(f"select count(*) from pg.{tbl}").fetchone()[0]
        except Exception as e:                                # noqa: BLE001
            rec |= {"rows": None, "error": str(e)[:60]}
            out.append(rec)
            continue
        cols = [r[0] for r in c.execute(
            f"select column_name from information_schema.columns "
            f"where table_catalog='pg' and table_schema='{tbl.split('.')[0]}' "
            f"and table_name='{tbl.split('.')[1]}'").fetchall()]
        symcol = next((x for x in ("symbol", "ticker", "yf_ticker", "scheme_code",
                                   "index_name") if x in cols), None)
        if symcol:
            rec["symbols"] = c.execute(
                f"select count(distinct {symcol}) from pg.{tbl}").fetchone()[0]
        if datecol and datecol in cols:
            lo, hi = c.execute(
                f"select min({datecol}), max({datecol}) from pg.{tbl}").fetchone()
            rec["span"] = f"{str(lo)[:10]} -> {str(hi)[:10]}"
            try:
                h = hi.date() if isinstance(hi, datetime) else hi
                rec["stale_days"] = (today - h).days
                # A max date in the future is not freshness, it is corruption.
                if rec["stale_days"] < -1:
                    notes.append(f"{tbl}: max {datecol} is {str(hi)[:10]} — IN THE "
                                 f"FUTURE, table contains impossible dates")
            except Exception:                                 # noqa: BLE001
                pass
        out.append(rec)

    # Local artefacts the analyses depend on but git does not carry.
    for p, label in ((Path("/Users/umashankar/market-pipeline/data/"
                           "india_split_factors.parquet"), "india split factors"),
                     (Path("/Users/umashankar/market-pipeline/data/"
                           "india_unverifiable_symbols.csv"), "india unverifiable")):
        rec = {"source": label, "kind": "file", "critical": True,
               "path": str(p), "exists": p.exists()}
        if p.exists():
            import pandas as pd
            d = (pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p))
            rec["rows"] = len(d)
            if "symbol" in d.columns:
                rec["symbols"] = d.symbol.nunique()
        out.append(rec)
    return {"sources": out, "notes": notes}


def audit_claims(state: AuditState) -> dict:
    """Does each scheduled script's quoted number still exist in its own source?"""
    out = []
    for fn, cited in SCHEDULED:
        p = HERE / fn
        rec = {"script": fn, "cited_report": cited, "exists": p.exists()}
        if not p.exists():
            out.append(rec)
            continue
        head = p.read_text(errors="ignore")[:4000]
        # A docstring that quotes a number IN ORDER TO RETRACT IT is doing the
        # right thing, and flagging it as a stale claim punishes the correction.
        # Lines that announce a withdrawal are excluded from claim extraction.
        # Filtering by LINE is too fine: a retraction runs several lines, and the
        # line carrying the old numbers is rarely the line carrying the word
        # "withdrawn", so the figures survived the filter and the corrected file
        # kept getting flagged. Paragraphs are the unit a retraction is written
        # in, so drop the whole block.
        keep = [para for para in re.split(r"\n\s*\n", head)
                if not re.search(r"withdraw|previously asserted|no longer|"
                                 r"was wrong|retract", para, re.I)]
        head = "\n\n".join(keep)
        nums = sorted(set(PCT.findall(head)) | set(TSTAT.findall(head)))
        rec["claims_in_docstring"] = nums
        if not cited:
            rec["verdict"] = "no numeric claim cited" if not nums else "UNSOURCED"
            out.append(rec)
            continue
        rp = REPORTS / cited
        if not rp.exists():
            rec["verdict"] = "CITED REPORT MISSING"
            out.append(rec)
            continue
        body = rp.read_text(errors="ignore")
        # 🔴 COMPARE NUMBERS, NOT FORMATTED STRINGS. An earlier version stripped
        # whitespace and matched the whole token, so the docstring's "t 17.62"
        # failed against the report's "t = 17.62" (the '=' survives the strip)
        # and cluster_indices.py was reported STALE when its number was sitting
        # right there. Matching the bare numeral is format-agnostic and the
        # thing actually being claimed.
        report_nums = set(re.findall(r"-?\d+\.\d+", body))
        def _bare(tok: str) -> str:
            m = re.search(r"-?\d+\.\d+", tok)
            return m.group(0) if m else tok
        missing = [n for n in nums if _bare(n) not in report_nums]
        rec["missing_from_report"] = missing
        rec["report_mtime"] = datetime.fromtimestamp(
            rp.stat().st_mtime).strftime("%Y-%m-%d")
        rec["verdict"] = ("consistent" if not missing
                          else f"STALE — {len(missing)}/{len(nums)} quoted "
                               f"number(s) absent from {cited}")
        out.append(rec)
    return {"claims": out}


def audit_gates(state: AuditState) -> dict:
    """Which analyses actually drop corporate-action-contaminated symbols?"""
    out = []
    for fn in GATED_EXPECT:
        p = HERE / fn
        rec = {"script": fn, "exists": p.exists()}
        if p.exists():
            src = p.read_text(errors="ignore")
            # Substring-matching the whole file counted the word inside a
            # COMMENT: etf_builder.py explains at length why it deliberately
            # does NOT gate, and that prose made it report as gated — the
            # audit read an explanation as an implementation. Only
            # non-comment lines count as a call site.
            rec["calls_contaminated"] = any(
                "contaminated(" in ln and not ln.lstrip().startswith("#")
                for ln in src.splitlines())
            # 🔴 ONLY A SCRIPT THAT LOADS A RAW PRICE PANEL CAN BE "UNGATED".
            # The first version flagged peer_warranted.py (reads india_pe_daily,
            # a P/E series), etf_builder.py (reads fund NAVs) and reentry_book.py
            # (reads pre-computed events from a CSV) as UNGATED. None of them
            # touch a price panel, so there is nothing to gate and the warning
            # was noise. An audit that cries wolf gets muted, so the question is
            # narrowed to: does this script load OHLCV itself?
            rec["loads_panel"] = bool(
                re.search(r"load_prices|load_market|year=\*\.parquet|"
                          r"cleaned_ohlcv|ohlcv_adj|values=\"Close\"|"
                          r"values='Close'", src))
            # Dropping bad symbols is not the only valid defence. etf_builder
            # REFUSES the India panel outright as split-unadjusted, which is
            # stricter than filtering it, and in the verified-adjusted markets
            # it does run on, a >30% unreversed fall is a REAL crash — gating
            # there would delete losers and manufacture survivorship bias. A
            # refusal is a guard, so the audit must not demand a gate instead.
            rec["refuses"] = bool(re.search(r"REFUSING|allow-unadjusted", src))
            if not rec["loads_panel"]:
                rec["verdict"] = "n/a — no raw price panel loaded"
            elif rec["refuses"] and not rec["calls_contaminated"]:
                rec["verdict"] = ("guarded by refusal — rejects the unadjusted "
                                  "panel rather than filtering it")
            elif rec["calls_contaminated"]:
                rec["verdict"] = "gated"
            else:
                rec["verdict"] = ("UNGATED — loads a raw price panel without "
                                  "dropping uncorrected corporate actions")
        out.append(rec)
    return {"gates": out}


# Cassandra columns that a row is supposed to CARRY, split by what they mean.
# The distinction is the point of this audit: a row can be present and current
# on its price fields while every fundamental field beside it is null.
CASS_FUNDAMENTAL = ("pe", "pb", "roe", "opm", "eps", "debt_to_equity")
CASS_PRICE = ("cmp", "rsi", "ema_50")
CASS_MARKETS = ("us", "india", "japan", "korea", "china", "europe", "hong_kong")


def audit_cassandra(state: AuditState) -> dict:
    """Row counts are not coverage. Measure how many rows are actually POPULATED.

    🔴 WHY THIS NODE EXISTS. A load landed on 2026-07-29 announcing "fundamentals
    extended to 28,986 symbols". Cassandra did gain ~23,000 rows and their PRICE
    fields are genuinely populated — but `eps > 0` was true in ZERO rows in every
    market, `pe > 0` in 112 rows total, and for Japan and China the fundamental
    columns were entirely null. The headline counted symbols that RECEIVED A ROW.
    Nothing in this audit could see that, because it only inspected Postgres and
    local files, so answering "is that data real, and is it reaching the
    analysis?" took a manual afternoon.

    An empty column is more dangerous than a missing table. A missing table
    raises an error at the point of use; a table full of nulls silently narrows
    every downstream sample, and a COUNT(*) over it reports full coverage. So
    presence and population are reported separately, per market, and a store that
    is present-but-unpopulated is called out rather than counted as covered.

    Read-only, and failure here is not fatal: Cassandra is a secondary store for
    this repo, so an unreachable node yields a note rather than an aborted audit.
    """
    try:
        from cassandra.cluster import Cluster
    except ImportError:
        return {"cassandra": [], "notes": ["cassandra-driver not installed — "
                                           "Cassandra store NOT audited"]}
    try:
        cl = Cluster(["127.0.0.1"], connect_timeout=8)
        s = cl.connect("herrrickshaw")
    except Exception as e:                                     # noqa: BLE001
        return {"cassandra": [], "notes": [f"Cassandra unreachable: {str(e)[:70]}"]}

    out, notes = [], []
    for mkt in CASS_MARKETS:
        try:
            total = s.execute(
                "SELECT COUNT(*) FROM stock_quotes WHERE market=%s", (mkt,)
            ).one()[0]
        except Exception:                                      # noqa: BLE001
            continue
        if not total:
            continue
        rec = {"market": mkt, "rows": total}
        # ALLOW FILTERING is acceptable here: this is an audit run on demand over
        # one partition, not a hot path, and there is no secondary index to use.
        for label, cols in (("fund", CASS_FUNDAMENTAL), ("price", CASS_PRICE)):
            best = 0
            for col in cols:
                try:
                    n = s.execute(f"SELECT COUNT(*) FROM stock_quotes WHERE "
                                  f"market=%s AND {col} > 0 ALLOW FILTERING",
                                  (mkt,)).one()[0]
                except Exception:                              # noqa: BLE001
                    continue
                best = max(best, n)          # the BEST-populated column of the group
            rec[label] = best
            rec[label + "_pct"] = best / total if total else 0.0
        # "Present but hollow": rows exist, prices are there, fundamentals are not.
        rec["hollow"] = (rec.get("price", 0) > 0.5 * total
                         and rec.get("fund_pct", 0) < 0.05)

        # 🔴 POPULATED IS NOT MEASURED, EITHER — the gap this "hollow" check and
        # the plausibility check below still both missed. Found 2026-07-30
        # while investigating a DIFFERENT contamination shape (a repeated
        # decimal (pe,pb,roe) triple across unrelated symbols — the low-
        # cardinality-WHOLE-NUMBER check above only catches quality scores like
        # 25/40/50/65, not a repeated decimal constant). The table has its own
        # answer sitting right there: `fundamentals_source`, which exists and is
        # already populated. Sampling it directly: 99-100% of every market's
        # rows are 'median_imputed'. That is not a bug on its own — the
        # 2026-07-29 commit that introduced it says exactly what it does — but
        # this audit was reporting every one of those rows as "fundamentals
        # present" alongside real ones, with no way to tell them apart. A
        # median-imputed ROE ranks identically to a measured one in any
        # screen that sorts on the column.
        try:
            # CQL has no `!=` operator ("Unsupported relation"), so measured is
            # derived as total minus the one equality query CQL DOES support —
            # not queried directly.
            imputed = s.execute(
                "SELECT COUNT(*) FROM stock_quotes WHERE market=%s "
                "AND fundamentals_source = 'median_imputed' ALLOW FILTERING",
                (mkt,)).one()[0]
            rec["imputed"] = imputed
            rec["measured"] = total - imputed
            rec["measured_pct"] = rec["measured"] / total if total else 0.0
        except Exception:                                       # noqa: BLE001
            pass
        if rec.get("measured_pct", 1.0) < 0.10 and rec.get("fund_pct", 0) > 0.5:
            notes.append(
                f"cassandra[{mkt}]: fund_pct reports {rec['fund_pct']:.0%} "
                f"populated, but only {rec.get('measured_pct', 0):.1%} of that "
                f"is measured — the rest is fundamentals_source='median_imputed' "
                f"reporting as if it were real per-symbol data")

        # 🔴 POPULATED IS NOT PLAUSIBLE. On 2026-07-29 this node reported Japan,
        # China, Korea and Europe as "fundamentals present 100%" the moment a
        # rebuild filled their columns. The values were quality SCORES written
        # into ratio-named columns: japan.pb held exactly four distinct values
        # (25, 40, 50, 65), identical to quality_score in every row, where a real
        # price-to-book is continuous over roughly 0.3-20. A `> 0` test cannot
        # tell a 0-100 score from a ratio, so the audit certified the fix it was
        # built to scrutinise. Cardinality can: a genuine ratio over thousands of
        # symbols takes thousands of distinct values, a score takes a handful.
        # Checked across EVERY fundamental column, not just pb: the abuse is not
        # confined to one field. japan/europe carry the score in `pb`, while
        # china/korea carry it in `roe` — and india's `roe` holds a genuine
        # fraction (0.160), so the SAME column means a ratio in one market and a
        # 0-100 grade in another. Anything reading roe across markets compares
        # 0.16 against 80 and treats them as the same quantity.
        rec["suspect_cols"] = []
        for col in CASS_FUNDAMENTAL:
            try:
                vals = [r[0] for r in s.execute(
                    f"SELECT {col} FROM stock_quotes WHERE market=%s LIMIT 400",
                    (mkt,)) if r[0] is not None]
            except Exception:                                  # noqa: BLE001
                continue
            if len(vals) < 100:
                continue
            uniq = len(set(vals))
            # A genuine ratio over hundreds of symbols is near-continuous; a
            # score takes a handful of values and is usually whole-numbered.
            whole = all(float(v) == int(float(v)) for v in vals[:200])
            if uniq <= 20 and whole:
                rec["suspect_cols"].append(f"{col}({uniq} distinct)")
        rec["suspect_scale"] = bool(rec["suspect_cols"])
        if rec["suspect_scale"]:
            notes.append(
                f"cassandra[{mkt}]: {', '.join(rec['suspect_cols'])} — whole "
                f"numbers over a handful of distinct values is a SCORE, not a "
                f"ratio. Populated, and wrong. Anything reading these columns "
                f"gets a 0-100 grade in place of a multiple.")
        if rec["hollow"]:
            notes.append(
                f"cassandra[{mkt}]: {total:,} rows, prices populated "
                f"({rec['price']:,}) but fundamentals effectively EMPTY "
                f"({rec['fund']:,} = {rec['fund_pct']:.1%}) — counts as coverage "
                f"in a row count, is not coverage in an analysis")
        out.append(rec)
    try:
        cl.shutdown()
    except Exception:                                          # noqa: BLE001
        pass
    return {"cassandra": out, "notes": notes}


def audit_power(state: AuditState) -> dict:
    """Is each conclusion built on the full universe, or on a top-N sample?

    The user's question, and the right one: a result measured on the 200 most
    liquid names is a statement about large caps, not about the market. It is
    not invalid — it is narrower than it sounds, and the narrowing is usually
    invisible by the time the number reaches a docstring. So every conclusion
    is tagged with the universe its own report declares, and the sample size
    behind it, so that breadth and power can be read off directly rather than
    inferred.
    """
    out = []
    for rp in sorted(REPORTS.glob("*.md")):
        body = rp.read_text(errors="ignore")
        if len(body) < 200:
            continue
        uni = re.search(r"universe[:\s]+([^\n|]{4,90})", body, re.I)
        topn = re.search(r"top[ -](\d{2,4})\b", body, re.I)
        # the largest explicitly-labelled sample count in the report
        counts = [int(x.replace(",", "")) for x in re.findall(
            r"(?:n\s?=\s?|events\s*:\s*\*{0,2})([\d,]{2,12})", body)]
        forms = re.search(r"(\d+)\s+(?:monthly|quarterly|annual|formation)", body, re.I)
        if not (uni or topn or counts or forms):
            continue
        out.append({
            "report": rp.name,
            "universe": (uni.group(1).strip() if uni else
                         (f"top {topn.group(1)}" if topn else "—")),
            "sample_kind": ("SAMPLE (top-N liquid)" if topn else
                            "declared" if uni else "—"),
            "n_max": max(counts) if counts else None,
            "formations": int(forms.group(1)) if forms else None,
        })
    return {"power": out}


def synthesize(state: AuditState) -> dict:
    """Roll the three audits into one progress statement."""
    src, cl, gt = state["sources"], state["claims"], state["gates"]
    stale = [s for s in src if s.get("tolerance") is not None
             and (s.get("stale_days") or 0) > s["tolerance"]]
    broken = [s for s in src if s.get("error") or s.get("exists") is False]
    bad_claims = [c for c in cl if str(c.get("verdict", "")).startswith(
        ("STALE", "UNSOURCED", "CITED"))]
    ungated = [g for g in gt if g.get("verdict", "").startswith("UNGATED")]
    pw = state.get("power", [])
    samp = [p for p in pw if str(p.get("sample_kind", "")).startswith("SAMPLE")]
    cass = state.get("cassandra", [])
    hollow = [x for x in cass if x.get("hollow")]
    parts = [
        f"{len(src)} sources inventoried, {len(broken)} missing/erroring, "
        f"{len(stale)} source(s) past their expected refresh cadence",
        f"{len(cl)} scheduled scripts checked, {len(bad_claims)} quoting numbers "
        f"their own cited report no longer contains",
        f"{len(gt)} analyses checked for the contamination gate, "
        f"{len(ungated)} ungated",
        f"{len(pw)} conclusions have a declared universe, {len(samp)} rest on a "
        f"top-N liquid SAMPLE rather than the full market",
        f"{len(cass)} Cassandra market(s) audited, {len(hollow)} present but "
        f"hollow (rows and prices, no fundamentals)",
    ]
    return {"summary": " · ".join(parts)}


def build():
    from langgraph.graph import END, START, StateGraph
    g = StateGraph(AuditState)
    g.add_node("inventory", inventory)
    g.add_node("audit_claims", audit_claims)
    g.add_node("audit_gates", audit_gates)
    g.add_node("audit_power", audit_power)
    g.add_node("audit_cassandra", audit_cassandra)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "inventory")
    # fan out: the four audits are independent of each other
    g.add_edge("inventory", "audit_claims")
    g.add_edge("inventory", "audit_gates")
    g.add_edge("inventory", "audit_power")
    g.add_edge("inventory", "audit_cassandra")
    # join
    g.add_edge("audit_claims", "synthesize")
    g.add_edge("audit_gates", "synthesize")
    g.add_edge("audit_power", "synthesize")
    g.add_edge("audit_cassandra", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


def render(s: AuditState) -> str:
    L: list[str] = []
    def o(x=""):
        L.append(x)

    o("# Completeness audit — data, claims, and gates")
    o()
    o(f"Generated {date.today()} by `completeness_graph.py` (LangGraph, "
      f"4 nodes, deterministic — no LLM).")
    o()
    o(f"**{s['summary']}**")
    o()

    o("## 1. Data completeness")
    o()
    o("| source | rows | symbols | span | stale (d) | cadence | crit |")
    o("|---|--:|--:|---|--:|---|:--:|")
    def num(v):
        return f"{v:,}" if isinstance(v, int) else "—"

    for x in s["sources"]:
        sd, tol = x.get("stale_days"), x.get("tolerance")
        st = ("—" if sd is None
              else f"🔴 {sd}" if (tol is not None and sd > tol) else str(sd))
        flag = "🔴" if (x.get("error") or x.get("exists") is False) else (
            "✅" if x.get("critical") else "")
        o(f"| `{x['source']}` | {num(x.get('rows'))} | {num(x.get('symbols'))} "
          f"| {x.get('span', '—')} | {st} | {x.get('cadence', '—')} | {flag} |")
    o()

    o("## 2. Claim consistency — does the quoted number still exist upstream?")
    o()
    o("| script | cites | quoted | verdict |")
    o("|---|---|---|---|")
    for c in s["claims"]:
        nums = ", ".join(c.get("claims_in_docstring", [])[:4]) or "—"
        v = c.get("verdict", "—")
        mark = "🔴 " if v.startswith(("STALE", "UNSOURCED", "CITED")) else ""
        o(f"| `{c['script']}` | {c.get('cited_report') or '—'} | {nums} | "
          f"{mark}{v} |")
    o()

    o("## 3. Contamination gate coverage")
    o()
    o("| analysis | drops contaminated symbols | verdict |")
    o("|---|:--:|---|")
    for g in s["gates"]:
        if not g.get("exists"):
            o(f"| `{g['script']}` | — | missing |")
            continue
        ok = g.get("calls_contaminated")
        v = g.get("verdict", "")
        # red belongs only on a genuine gap, not on "gate does not apply here"
        o(f"| `{g['script']}` | {'yes' if ok else ('NO' if g.get('loads_panel') else '—')} "
          f"| {'🔴 ' if v.startswith('UNGATED') else ''}{v} |")
    o()

    o("## 4. Breadth and power — full universe, or a top-N sample?")
    o()
    o("| conclusion | declared universe | sample kind | n | formations |")
    o("|---|---|---|--:|--:|")
    for p in sorted(s.get("power", []), key=lambda z: -(z.get("n_max") or 0)):
        mark = "🔶 " if str(p["sample_kind"]).startswith("SAMPLE") else ""
        o(f"| `{p['report']}` | {p['universe'][:58]} | {mark}{p['sample_kind']} "
          f"| {p['n_max'] if p['n_max'] else '—'} "
          f"| {p['formations'] if p['formations'] else '—'} |")
    o()
    o("> 🔶 marks a conclusion measured on the most liquid slice of the market. "
      "That is not a defect — liquidity gating is deliberate and keeps the "
      "result tradeable — but it narrows what the number is ABOUT, and the "
      "narrowing disappears by the time the figure is quoted downstream.")
    o()

    if s.get("cassandra"):
        o("## 5. Cassandra — rows present vs fields POPULATED vs MEASURED")
        o()
        o("| market | rows | price fields | fundamentals | measured | verdict |")
        o("|---|--:|--:|--:|--:|---|")
        for x in sorted(s["cassandra"], key=lambda z: -z["rows"]):
            v = ("🔴 HOLLOW — counts as coverage, is not coverage"
                 if x.get("hollow") else
                 "🔴 SCORE IN A RATIO COLUMN — populated, and wrong"
                 if x.get("suspect_scale") else
                 "🔴 ALMOST ALL IMPUTED — populated, not measured"
                 if x.get("measured_pct", 1.0) < 0.10 and x.get("fund_pct", 0) > 0.5 else
                 "fundamentals present" if x.get("fund_pct", 0) >= 0.05 else "—")
            # "measured" is meaningless where fund_pct is ~0: hong_kong has 0
            # imputed rows (nothing has ever written to it) and would otherwise
            # show "100% measured" — total-minus-zero-imputed — for a market
            # that has NO fundamentals at all. The metric only means something
            # once there is fundamentals data to be measured-vs-imputed WITHIN.
            meas = (f"{x['measured']:,} ({x['measured_pct']:.1%})"
                    if "measured" in x and x.get("fund_pct", 0) > 0.05 else "n/a")
            o(f"| {x['market']} | {x['rows']:,} | {x.get('price', 0):,} "
              f"| {x.get('fund', 0):,} ({x.get('fund_pct', 0):.1%}) | {meas} | {v} |")
        o()
        o("> `fundamentals` is COUNTED as the BEST-populated column in each "
          "group, so it is an upper bound — the true per-field coverage is "
          "lower. `measured` is rows whose `fundamentals_source` is NOT "
          "`median_imputed` — found 2026-07-30 while investigating a repeated-"
          "decimal (pe,pb,roe) triple across unrelated symbols (a contamination"
          " shape the whole-number score check above does not catch). Every "
          "market sampled at 99-100% imputed; a median-imputed ROE ranks "
          "identically to a measured one in anything that sorts on the column, "
          "so `fundamentals present` alone was reporting placeholder coverage "
          "as if it were per-symbol data. A row that exists with null "
          "fundamentals is still worse than a missing table — the missing "
          "table raises an error where it is used, the null column silently "
          "narrows every downstream sample and still reports full coverage to "
          "a `COUNT(*)`.")
        o()

    if s.get("notes"):
        o("## Notes")
        o()
        for n in s["notes"]:
            o(f"- 🔴 {n}")
        o()

    o("> Completeness is not correctness. This audit proves a source is present, "
      "fresh, internally consistent with what quotes it, and gated — not that "
      "the numbers in it are right. `reports/data_sufficiency.md` is the "
      "cautionary case: it reports a US liquid universe of 6 stocks and a span "
      "ending 2029, both impossible, while looking like a clean pass.")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    app = build()
    s = app.invoke({"sources": [], "claims": [], "gates": [], "power": [], "cassandra": [],
                    "notes": [],
                    "summary": ""})
    if a.json:
        print(json.dumps(s, indent=2, default=str))
        return 0
    md = render(s)
    print(md)
    REPORTS.mkdir(exist_ok=True)
    OUT_MD.write_text(md)
    print(f"wrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
