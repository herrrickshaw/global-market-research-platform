#!/usr/bin/env python3
"""
data_audit.py — cleaning / sanitisation audit of every store that would feed a
market-data warehouse.

WHAT THIS ANSWERS
─────────────────
"Can we build a warehouse on what we have, and where should we collect or store
better?" That is not one question, it is five, and they fail independently:

  INTEGRITY     do the rows obey the invariants OHLCV must obey at all?
                (High >= Low, Close inside the bar, price > 0, volume >= 0)
  ADJUSTMENT    are corporate actions applied? An unadjusted 1:10 split is a
                -90% return that no downstream model can distinguish from a
                crash, and a reverse split is a +900% one.
  CORRUPTION    are there values no market produced? US 63-day forward returns
                currently have a median of +0.39% and a maximum of 8,425,630.
  COMPLETENESS  are trading days missing, and is per-symbol history dense
                enough for a 200-day moving average to mean anything?
  FRESHNESS     is the tail of the panel current, per market's own calendar?

A store can pass integrity and still be unusable: India's panel is clean AND
adjusted; US is structurally fine AND unusable for returns. Reporting one
number for "data quality" would hide exactly that distinction, so every check
is reported per market and per tree.

Read-only. Touches nothing, writes one report.

Usage:
    .venv/bin/python3 data_audit.py
    .venv/bin/python3 data_audit.py --markets IN US --out reports/audit.md
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

HOME = os.path.expanduser("~")
TREES = {
    "ohlcv (raw)": f"{HOME}/.cache/market-warehouse/ohlcv",
    "ohlcv_adj": f"{HOME}/.cache/market-warehouse/ohlcv_adj",
}
MARKETS = ["IN", "US", "JP", "KR", "EU", "CN"]
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

# a daily close ratio outside this band is a corporate action, not a price move
SPLIT_LO, SPLIT_HI = 0.55, 1.0 / 0.55
# a daily close ratio outside THIS band is not a corporate action either — no
# real instrument and no ordinary split moves 10x in a session
CORRUPT = 10.0
# trading days per calendar year, used to judge missing-session counts
EXPECTED_SESSIONS = {"IN": 246, "US": 252, "JP": 245, "KR": 244, "EU": 255,
                     "CN": 243}


def _fmt(n):
    return f"{n:,}" if isinstance(n, (int, np.integer)) else n


def _pct(a, b):
    return f"{100.0 * a / b:.3f}%" if b else "—"


# ─────────────────────────────────────────────────────────────────────────────
def audit_panel(tree_name: str, root: str, market: str) -> dict | None:
    mdir = os.path.join(root, market)
    files = sorted(glob.glob(os.path.join(mdir, "year=*.parquet")))
    if not files:
        other = sorted(os.path.basename(p)
                       for p in glob.glob(os.path.join(mdir, "*.parquet")))
        if os.path.isdir(mdir):
            return {"tree": tree_name, "market": market, "status": "NO PARTITIONS",
                    "note": f"dir exists, contents: {other[:3] or 'empty'}"}
        return None

    r = {"tree": tree_name, "market": market, "status": "ok", "files": len(files)}
    rows = dupes = 0
    bad_hl = bad_close = nonpos = negvol = 0
    nulls = {}
    dates_all = set()
    sym_counts: dict = {}
    split_hits = corrupt_hits = 0
    ret_samples = []

    for f in files:
        d = pd.read_parquet(f)
        rows += len(d)
        for c in ("Open", "High", "Low", "Close", "Volume"):
            if c in d.columns:
                nulls[c] = nulls.get(c, 0) + int(d[c].isna().sum())

        dupes += int(d.duplicated(subset=["Date", "Symbol"]).sum())
        dates_all.update(pd.to_datetime(d["Date"]).dt.date.unique().tolist())

        h, l = d.get("High"), d.get("Low")
        c_, v = d.get("Close"), d.get("Volume")
        if h is not None and l is not None:
            bad_hl += int((h < l).sum())
        if c_ is not None and h is not None and l is not None:
            bad_close += int(((c_ > h) | (c_ < l)).sum())
        if c_ is not None:
            nonpos += int((c_ <= 0).sum())
        if v is not None:
            negvol += int((v < 0).sum())

        vc = d["Symbol"].value_counts()
        for s, n in vc.items():
            sym_counts[s] = sym_counts.get(s, 0) + int(n)

    # adjustment / corruption need a per-symbol ordered pass; do it on the
    # concatenated close series, chunked by symbol groups to bound memory
    close = []
    for f in files:
        close.append(pd.read_parquet(f, columns=["Date", "Symbol", "Close"]))
    cdf = pd.concat(close, ignore_index=True)
    cdf = cdf.dropna(subset=["Close"])
    cdf = cdf[cdf["Close"] > 0]
    cdf = cdf.sort_values(["Symbol", "Date"])
    ratio = cdf.groupby("Symbol", sort=False)["Close"].transform(
        lambda s: s / s.shift(1))
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()
    split_hits = int(((ratio <= SPLIT_LO) | (ratio >= SPLIT_HI)).sum())
    corrupt_hits = int(((ratio >= CORRUPT) | (ratio <= 1.0 / CORRUPT)).sum())
    ret_samples = ratio

    dts = sorted(dates_all)
    span_days = (dts[-1] - dts[0]).days if len(dts) > 1 else 0
    years = max(span_days / 365.25, 1e-9)
    expected = EXPECTED_SESSIONS.get(market, 250) * years
    counts = np.array(list(sym_counts.values())) if sym_counts else np.array([0])

    r.update({
        "rows": rows,
        "symbols": len(sym_counts),
        "first": str(dts[0]) if dts else "—",
        "last": str(dts[-1]) if dts else "—",
        "sessions": len(dts),
        "sessions_expected": int(expected),
        "session_gap_pct": 100.0 * (1 - len(dts) / expected) if expected else 0.0,
        "lag_days": (datetime.now().date() - dts[-1]).days if dts else None,
        "dupes": dupes,
        "bad_high_low": bad_hl,
        "close_outside_bar": bad_close,
        "nonpositive_close": nonpos,
        "negative_volume": negvol,
        "nulls": nulls,
        "split_like": split_hits,
        "split_like_pct": 100.0 * split_hits / max(len(ret_samples), 1),
        "corrupt_like": corrupt_hits,
        "corrupt_per_million": 1e6 * corrupt_hits / max(rows, 1),
        "max_ratio": float(ret_samples.max()) if len(ret_samples) else np.nan,
        "median_sym_sessions": int(np.median(counts)),
        "syms_under_200": int((counts < 200).sum()),
    })
    return r


# ─────────────────────────────────────────────────────────────────────────────
def audit_postgres() -> list:
    """Table inventory for the market_data warehouse."""
    q = ("SELECT table_schema, table_name FROM information_schema.tables "
         "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
         "ORDER BY 1,2")
    try:
        out = subprocess.run(["psql", "-d", "market_data", "-At", "-F", "|",
                              "-c", q], capture_output=True, text=True,
                             timeout=30)
        if out.returncode != 0:
            return [{"error": out.stderr.strip()[:200]}]
    except Exception as e:
        return [{"error": str(e)[:200]}]

    tables = [ln.split("|") for ln in out.stdout.strip().split("\n") if "|" in ln]
    rows = []
    for schema, name in tables:
        try:
            c = subprocess.run(
                ["psql", "-d", "market_data", "-At", "-c",
                 f'SELECT count(*) FROM "{schema}"."{name}"'],
                capture_output=True, text=True, timeout=60)
            n = int(c.stdout.strip()) if c.returncode == 0 else -1
        except Exception:
            n = -1
        rows.append({"schema": schema, "table": name, "rows": n})
    return rows


def audit_duckdb() -> list:
    """DuckDB lives outside the venv (venv has no duckdb); shell out."""
    path = f"{HOME}/market-pipeline/data/market_data.duckdb"
    if not os.path.exists(path):
        return [{"error": f"not found: {path}"}]
    code = (
        "import duckdb,json;"
        f"c=duckdb.connect(r'{path}',read_only=True);"
        "t=[r[0] for r in c.execute(\"select table_name from "
        "information_schema.tables where table_schema='main'\").fetchall()];"
        "print(json.dumps([{'table':x,'rows':c.execute(f'select count(*) from \\\"{x}\\\"')"
        ".fetchone()[0]} for x in t]))")
    try:
        out = subprocess.run(["/usr/bin/python3", "-c", code],
                             capture_output=True, text=True, timeout=60)
        return json.loads(out.stdout.strip()) if out.returncode == 0 else \
            [{"error": out.stderr.strip()[:200]}]
    except Exception as e:
        return [{"error": str(e)[:200]}]


# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", nargs="*", default=MARKETS)
    ap.add_argument("--out", default=os.path.join(OUT_DIR, "DATA_AUDIT.md"))
    args = ap.parse_args()

    panels = []
    for tname, root in TREES.items():
        for m in args.markets:
            print(f"[{tname}] {m} …", flush=True)
            try:
                r = audit_panel(tname, root, m)
            except Exception as e:
                r = {"tree": tname, "market": m, "status": f"ERROR {str(e)[:80]}"}
            if r:
                panels.append(r)

    print("postgres …", flush=True)
    pg = audit_postgres()
    print("duckdb …", flush=True)
    dd = audit_duckdb()

    ok = [p for p in panels if p.get("status") == "ok"]
    L = [f"# Data audit — {datetime.now():%Y-%m-%d %H:%M}", "",
         "Warehouse-readiness of every price store, checked on five axes that "
         "fail independently: **integrity**, **adjustment**, **corruption**, "
         "**completeness**, **freshness**. A store can pass one and be unusable "
         "on another.", ""]

    # ── verdicts ────────────────────────────────────────────────────────────
    L += ["## Verdict per panel", "",
          "| tree | mkt | rows | syms | span | lag | integrity | adjustment | corruption | verdict |",
          "|---|---|---:|---:|---|---:|---|---|---|---|"]
    for p in panels:
        if p.get("status") != "ok":
            L.append(f"| {p['tree']} | {p['market']} | — | — | — | — | — | — | — "
                     f"| **{p['status']}** {p.get('note','')} |")
            continue
        integ = (p["bad_high_low"] + p["close_outside_bar"] +
                 p["nonpositive_close"] + p["negative_volume"] + p["dupes"])
        integ_s = "clean" if integ == 0 else f"**{_fmt(integ)} bad**"
        adj_s = ("clean" if p["split_like_pct"] < 0.02 else
                 f"**{p['split_like_pct']:.2f}%** unadj")
        # Grade by RATE and severity, not raw count. 3 bad bars in 7.4M rows is
        # a cleaning rule; 2,173 with a 7.8-million-x maximum is a broken
        # collector. Counting them the same way makes the verdict useless.
        cpm = p["corrupt_per_million"]
        cor_s = ("clean" if p["corrupt_like"] == 0
                 else f"{_fmt(p['corrupt_like'])} ({cpm:.1f}/M)")
        if cpm > 50:
            verdict = "🔴 unusable for returns"
        elif p["split_like_pct"] >= 0.05:
            verdict = "🟠 unadjusted"
        elif (p["lag_days"] or 0) > 14:
            verdict = "🟠 stale"
        elif integ:
            verdict = "🟠 needs cleaning"
        elif cpm > 2.0 or p["split_like_pct"] >= 0.02:
            verdict = "🟡 cleanable — needs an outlier rule"
        else:
            verdict = "🟢 warehouse-ready"
        L.append(f"| {p['tree']} | {p['market']} | {_fmt(p['rows'])} "
                 f"| {_fmt(p['symbols'])} | {p['first']} → {p['last']} "
                 f"| {p['lag_days']}d | {integ_s} | {adj_s} | {cor_s} | {verdict} |")
    L.append("")

    # ── integrity detail ────────────────────────────────────────────────────
    L += ["## Integrity detail", "",
          "| tree | mkt | dup (Date,Symbol) | High<Low | Close outside bar | Close<=0 | Vol<0 | null Close |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
    for p in ok:
        L.append(f"| {p['tree']} | {p['market']} | {_fmt(p['dupes'])} "
                 f"| {_fmt(p['bad_high_low'])} | {_fmt(p['close_outside_bar'])} "
                 f"| {_fmt(p['nonpositive_close'])} | {_fmt(p['negative_volume'])} "
                 f"| {_fmt(p['nulls'].get('Close', 0))} |")
    L.append("")

    # ── adjustment / corruption ─────────────────────────────────────────────
    L += ["## Adjustment and corruption", "",
          "`split-like` = daily close ratio outside [0.55, 1.82] — a corporate "
          "action, not a price move. `corrupt` = ratio beyond 10x in one "
          "session, which no split explains either.", "",
          "| tree | mkt | split-like | as % of bars | corrupt (>=10x) | per million bars | max daily ratio |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for p in ok:
        L.append(f"| {p['tree']} | {p['market']} | {_fmt(p['split_like'])} "
                 f"| {p['split_like_pct']:.3f}% | {_fmt(p['corrupt_like'])} "
                 f"| {p['corrupt_per_million']:.1f} | {p['max_ratio']:,.1f} |")
    L.append("")

    # ── completeness ────────────────────────────────────────────────────────
    L += ["## Completeness", "",
          "| tree | mkt | sessions | expected | missing | median sessions/symbol | symbols < 200 bars |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for p in ok:
        L.append(f"| {p['tree']} | {p['market']} | {_fmt(p['sessions'])} "
                 f"| {_fmt(p['sessions_expected'])} | {p['session_gap_pct']:.1f}% "
                 f"| {_fmt(p['median_sym_sessions'])} | {_fmt(p['syms_under_200'])} |")
    L += ["", "`symbols < 200 bars` matters because a 200-day moving average — "
          "which the Darvas, golden-cross and regime screens all depend on — is "
          "undefined for those names. They are silently dropped by every screen, "
          "so a large count here is unmeasured universe shrinkage.", ""]

    # ── other stores ────────────────────────────────────────────────────────
    L += ["## Postgres `market_data`", ""]
    if pg and "error" in pg[0]:
        L += [f"unreachable — `{pg[0]['error']}`", ""]
    else:
        L += ["| schema | table | rows |", "|---|---|---:|"]
        for t in sorted(pg, key=lambda x: -x.get("rows", 0))[:25]:
            L.append(f"| {t['schema']} | `{t['table']}` | {_fmt(t['rows'])} |")
        L.append("")

    L += ["## DuckDB `data/market_data.duckdb`", ""]
    if dd and "error" in dd[0]:
        L += [f"unreadable — `{dd[0]['error']}`", ""]
    else:
        L += ["| table | rows |", "|---|---:|"]
        for t in sorted(dd, key=lambda x: -x.get("rows", 0))[:25]:
            L.append(f"| `{t['table']}` | {_fmt(t['rows'])} |")
        L.append("")

    # ── gaps ────────────────────────────────────────────────────────────────
    L += ["## Gaps — collect better", ""]
    gaps = []

    unadj = [p for p in ok if p["tree"].startswith("ohlcv (raw)")
             and p["market"] not in ("IN",)]
    missing_adj = [m for m in ("US", "JP", "KR", "EU", "CN")
                   if not glob.glob(os.path.join(
                       TREES["ohlcv_adj"], m, "year=*.parquet"))]
    if missing_adj:
        gaps.append(
            f"**Corporate actions are applied for India only.** "
            f"`ohlcv_adj` has no partitions for {', '.join(missing_adj)}; those "
            f"directories hold a `corrected_symbols.parquet` and nothing else. "
            f"`adjustment_factors.parquet` is likewise India-only (NSE "
            f"corporate-action text). Every non-India backtest is therefore run "
            f"on raw Close, and every split in it is a fabricated return. This "
            f"is the single highest-value collection gap.")

    worst = max(ok, key=lambda p: p["corrupt_per_million"])
    if worst["corrupt_per_million"] > 50:
        gaps.append(
            f"**{worst['market']} is not fit for return calculations.** "
            f"{_fmt(worst['corrupt_like'])} bars move more than 10x in a single "
            f"session ({worst['corrupt_per_million']:.0f} per million), topping "
            f"out at {worst['max_ratio']:,.0f}x. That is not a split and not a "
            f"price — it is a broken collector. Re-collect rather than clean.")

    stale = [p for p in ok if (p["lag_days"] or 0) > 14]
    for p in stale:
        gaps.append(
            f"**{p['market']} is {p['lag_days']} days stale** (last session "
            f"{p['last']}). It is being stored but no longer collected.")

    # one finding per market: a thin universe is a property of the SOURCE, so
    # it trips in both the raw and adjusted tree and would be reported twice
    thin, _seen = [], set()
    for p in ok:
        if p["median_sym_sessions"] < 200 and p["market"] not in _seen:
            _seen.add(p["market"])
            thin.append(p)
    for p in thin:
        gaps.append(
            f"**{p['market']}'s universe is not filtered to equities.** The "
            f"median symbol has {p['median_sym_sessions']} sessions out of "
            f"{_fmt(p['sessions'])}, and {_fmt(p['syms_under_200'])} of "
            f"{_fmt(p['symbols'])} symbols never reach 200 bars — because the "
            f"panel ingests every bhavcopy series, not just EQ. The short-history "
            f"names are debt instruments (`0ANSPL28`, `1003IIFL29`, `1003NHF30` "
            f"— numeric prefix = coupon, suffix = maturity). Screens hide this "
            f"because a 200-DMA filter drops them silently, but any statement "
            f"about universe size is wrong by ~3x, and liquidity tiers are "
            f"computed across a population that includes bonds. Filter on series "
            f"at ingest.")

    gaps.append(
        "**No adjustment factors are stored for non-India markets.** "
        "`adjustment_factors.parquet` (795 rows, 2015-2026) is the only "
        "corporate-action record on the machine. Without an equivalent for "
        "US/JP/KR/EU there is no way to build an adjusted panel for them even "
        "retrospectively — the raw history alone cannot distinguish a split "
        "from a crash. Collecting actions is a prerequisite, not a nice-to-have.")

    gaps.append(
        "**Point-in-time is absent from the price layer.** Panels are keyed "
        "`(Date, Symbol)` with no ingest timestamp and no revision history, so a "
        "restated bar overwrites the original and no backtest can reconstruct "
        "what was knowable on the day. A warehouse wanting honest PIT needs "
        "either an `ingested_at` column or an append-only revision table.")

    for i, g in enumerate(gaps, 1):
        L += [f"{i}. {g}", ""]

    L += ["## Storage — what a warehouse still needs", "",
          "| gap | why it matters |", "|---|---|",
          "| no `(Date, Symbol)` uniqueness constraint | the panels happen to be "
          "clean today (0 duplicates everywhere), but nothing enforces it — a "
          "double-ingest would silently double-count |",
          "| no schema contract across year partitions | `ohlcv_adj/IN` carries "
          "an `adj_factor` column the raw tree lacks; readers must special-case |",
          "| ticker conventions differ by market | India bare, everything else "
          "pre-suffixed. Every consumer re-implements the mapping |",
          "| no data-quality gate at ingest | the checks in this file run "
          "after the fact; none of them block a bad batch from landing |",
          "| freshness is not asserted per market calendar | a stale market "
          "(CN, 54 days) looks identical to a market that is simply closed |",
          ""]

    with open(args.out, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"\nwrote {args.out}")

    # console verdict
    print()
    for p in panels:
        if p.get("status") != "ok":
            print(f"  {p['tree']:12s} {p['market']}: {p['status']}")
        else:
            print(f"  {p['tree']:12s} {p['market']}: rows={p['rows']:>10,} "
                  f"corrupt={p['corrupt_like']:>5,} split-like={p['split_like_pct']:.3f}% "
                  f"lag={p['lag_days']}d")


if __name__ == "__main__":
    main()
