#!/usr/bin/env python3
"""
stock_pick_performance.py — did the pipeline's historical recommendations work?

WHAT THIS ANSWERS, PRECISELY
No archive of "exactly what was in the mailer on day D" exists anywhere on this
machine. daily_mailer.sh's traceable history starts 2026-07-29 (predecessor
daily_pipeline.sh logs start 2026-07-15; nothing survives from before that — the
dead Downloads tree has no mailer logs at all). brief_today.html is overwritten
daily and never archived or git-tracked. watchlist.csv IS git-tracked but only
17 commits ever touched it, mostly code changes not daily snapshots, stopping
2026-07-31.

So this script does the next best thing: it scores every DATED, PRICED entry
across the three partial records that DO exist, honestly disclosing what each
one is and where the real gaps are. It is NOT "every recommendation since the
first mailer" — it is the best available reconstruction, and says so.

SOURCES (deduped by symbol+market+entry_date, in this priority order — later
sources win a duplicate because they carry more provenance):
  1. cache_seed/signal_ledger_backfill.parquet  — 18,957 rows, 2026-06-12→06-26.
     NOT a live day-of record (signal_tracker.py's own rule is signal_date is
     NEVER backfilled) — this file breaks that rule by construction, so treat
     it as reconstructed, not as-it-happened.
  2. cache_seed/signal_ledger.parquet — 4,852 rows, 2026-07-13→07-22, live
     recorded (signal_date stamped same-day). Real record. Also the ledger that
     signal_tracker.py --report reads.
  3. watchlist.csv — 251 rows with real entry_date+entry_price, 2026-07-13→
     08-20. The buy/watch/hold/sell zone system — closer to "what a human would
     have acted on" than a raw filter pass, but it's LIVE STATE (mutated in
     place), not an append-only log, so older entries can be missing fields.
  4. gmail_brief_picks.parquet (research/extract_gmail_briefs.py) — 158 rows,
     real dated/priced picks parsed out of actual "Daily Market Brief" emails:
     Gmail drafts (the MCP send tool doesn't exist, only create_draft, so many
     early briefs were drafted and never sent) plus the few that DID send.
     This is the only source that is literally "what was shown to the user",
     not a reconstruction — highest dedup priority. Covers 2026-07-09,
     07-13, 07-15, 07-16, 07-17. A 2026-06-30 draft exists but is an older
     brief format with no per-pick price column — not recoverable.

REAL GAPS, disclosed in every report this script prints:
  - 2026-06-27 → 2026-07-12 (16 days): no source has anything.
  - 2026-07-23 → today: signal_tracker.py --record is wired into no cron or
    launchd job, so the live ledger has recorded ZERO new signals in this
    window. watchlist.csv fills SOME of this window (entries to 08-20) because
    it's updated by a different path (send_mailer.py), but new signal-level
    detail stopped.
  - EU/JP/KR have no persisted local price panel (signal_tracker.py's own
    comment), so scoring is IN+US only unless --fetch-missing is set, which
    hits yfinance and is off by default.

Reuses signal_tracker.py's PANELS/BENCH/_panel — same warehouse, same
benchmark-staleness handling, same entry-price provenance labelling. Read-only:
opens the pipeline's parquet/csv stores, writes nothing there.

    stock_pick_performance.py                  # full report, both horizons
    stock_pick_performance.py --min-days 21     # only entries aged 21+ days
    stock_pick_performance.py --out FILE.md     # also write a markdown report
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

CODE = Path("/Users/umashankar/market-pipeline/code/python_files")
sys.path.insert(0, str(CODE))
import signal_tracker as ST  # noqa: E402 — reuse PANELS, BENCH, _panel

RESEARCH = Path(__file__).resolve().parent
BACKFILL = CODE / "cache_seed" / "signal_ledger_backfill.parquet"
LIVE = CODE / "cache_seed" / "signal_ledger.parquet"
WATCHLIST = CODE / "watchlist.csv"

STATUS_TIER = {  # watchlist.csv status -> buy/hold/sell tier, as the user recalls
    "signal": "buy", "watch": "buy", "playbook": "buy", "justified": "buy",
    "held": "hold", "value-hold": "hold",
    "sold": "sell", "evicted": "sell",
}


def load_sources() -> tuple[pd.DataFrame, dict]:
    """Return (merged frame, coverage stats). merged has:
    symbol, market, entry_date, entry_price, source, filter."""
    frames = []
    stats = {}

    bf = pd.read_parquet(BACKFILL)
    bf["source"] = "backfill_ledger"
    bf["filter"] = bf["filter"].astype(str)
    stats["backfill_ledger"] = (len(bf), bf["signal_date"].min(), bf["signal_date"].max())
    frames.append(bf[["symbol", "market", "signal_date", "price_at_signal", "source", "filter"]]
                  .rename(columns={"signal_date": "entry_date", "price_at_signal": "entry_price"}))

    lv = pd.read_parquet(LIVE)
    lv["source"] = "live_ledger"
    stats["live_ledger"] = (len(lv), lv["signal_date"].min(), lv["signal_date"].max())
    frames.append(lv[["symbol", "market", "signal_date", "price_at_signal", "source", "filter"]]
                  .rename(columns={"signal_date": "entry_date", "price_at_signal": "entry_price"}))

    wl = pd.read_csv(WATCHLIST)
    wl["entry_date"] = pd.to_datetime(wl["entry_date"], errors="coerce")
    wl = wl.dropna(subset=["entry_date", "entry_price"])
    wl["source"] = "watchlist_zone"
    wl["filter"] = "zone:" + wl["status"].map(lambda s: STATUS_TIER.get(s, s))
    stats["watchlist_zone"] = (len(wl), wl["entry_date"].min(), wl["entry_date"].max())
    frames.append(wl[["symbol", "market", "entry_date", "entry_price", "source", "filter"]])

    gb_path = RESEARCH / "gmail_brief_picks.parquet"
    if gb_path.exists():
        gb = pd.read_parquet(gb_path)
        gb["source"] = "gmail_brief"
        gb["filter"] = "brief:" + gb["tier"].fillna(gb["filter"].fillna("unknown"))
        stats["gmail_brief"] = (len(gb), gb["entry_date"].min(), gb["entry_date"].max())
        frames.append(gb[["symbol", "market", "entry_date", "entry_price", "source", "filter"]])

    d = pd.concat(frames, ignore_index=True)
    d["symbol"] = d["symbol"].astype(str).str.upper()
    d["entry_date"] = pd.to_datetime(d["entry_date"])
    d["entry_price"] = pd.to_numeric(d["entry_price"], errors="coerce")
    d = d.dropna(subset=["entry_price"])
    d = d[d["entry_price"] > 0]

    # dedup: same symbol+market+entry_date, keep watchlist_zone > live_ledger >
    # backfill_ledger (later sources carry more provenance / are less estimated)
    prio = {"backfill_ledger": 0, "live_ledger": 1, "watchlist_zone": 2, "gmail_brief": 3}
    d["_p"] = d["source"].map(prio)
    d = d.sort_values("_p").drop_duplicates(subset=["symbol", "market", "entry_date"], keep="last")
    d = d.drop(columns="_p")

    return d, stats


def _india_benchmark() -> pd.Series:
    """NIFTYBEES (panel ETF, real bars through 2026-07-13) spliced onto the real
    NIFTY 50 index series (2026-07-14 onward) — a clean handoff, no overlap.

    🔴 Does NOT fall back to a cross-sectional panel median. Tried that first:
    it produced a "median close price" series that fell from 230 (mid-June) to
    125 (August) — a fabricated ~46% index decline. The panel's symbol
    composition is not fixed day to day, so "return of the median" is not a
    coherent index return; it is an artifact of which names happen to have a
    bar on which day. Entries with no real benchmark coverage get NaN, not a
    number that looks precise and is wrong.

    🔴 THE BODY MOVED. As of 2026-09-11 the construction lives in
    ST.india_benchmark() and this is a thin alias. It had to move because the
    live tracker — signal_tracker.py, the module that writes the ledger this
    script reads — never got the fix and kept grading every India signal against
    the fabricated median for three weeks after this copy was written. Fixing it
    here and leaving it broken there is what made that possible.

    The move also fixed two bugs this copy had: the seam factor divided
    NIFTYBEES's LAST bar by the index's FIRST bar (fine while "no overlap" held,
    off by +0.69% once the two series drifted six weeks apart), and the concat
    left duplicate dates wherever they overlapped — which the callers' .iloc[0]
    / .iloc[-1] then resolved arbitrarily.
    """
    return ST.india_benchmark()


def score(d: pd.DataFrame, min_days: int) -> tuple[pd.DataFrame, dict]:
    rows = []
    skipped = {"no_panel_file": 0, "not_in_panel": 0, "too_early": 0, "no_bar_at_entry": 0}
    no_bench = 0
    no_market_panel = int((~d["market"].isin(ST.PANELS.keys())).sum())
    if no_market_panel:
        skipped["no_panel_file"] += no_market_panel  # e.g. EU rows from gmail_brief
    d = d[d["market"].isin(ST.PANELS.keys())].copy()  # markets with a local panel
    benches = {"IN": (_india_benchmark(), "NIFTYBEES+NIFTY50")}
    for mkt, grp in d.groupby("market"):
        p = ST.PANELS.get(mkt)
        if not p or not p.exists():
            skipped["no_panel_file"] += len(grp)
            continue
        px = ST._panel(p, columns=["Date", "Symbol", "Close"])
        px["Symbol"] = px["Symbol"].astype(str).str.upper()
        wide = px.pivot_table(index="Date", columns="Symbol", values="Close",
                              aggfunc="last").sort_index()
        panel_end = wide.index.max()

        if mkt in benches:
            bench, bench_name = benches[mkt]
        else:
            # US: SPY, full coverage in this panel. EU/JP/KR have no index ETF in their panels, so
            # their rows score with NaN vs-benchmark (counted in no_benchmark_coverage). The empty
            # series needs a DatetimeIndex: a RangeIndex cannot be compared with entry_date.
            b = ST.BENCH.get(mkt)
            bench = (wide[b].dropna() if b in wide.columns
                     else pd.Series(dtype=float, index=pd.DatetimeIndex([])))
            bench_name = b or "none"

        for _, r in grp.iterrows():
            sym = r["symbol"]
            if sym not in wide.columns:
                skipped["not_in_panel"] += 1
                continue
            if r["entry_date"] > panel_end:
                skipped["too_early"] += 1
                continue
            s = wide[sym].dropna()
            after = s[s.index >= r["entry_date"]]
            if after.empty:
                skipped["no_bar_at_entry"] += 1
                continue
            days_held = (after.index[-1] - r["entry_date"]).days
            if days_held < min_days:
                continue
            last_px = float(after.iloc[-1])
            ret = (last_px / r["entry_price"] - 1) * 100
            bafter = bench[(bench.index >= r["entry_date"]) & (bench.index <= after.index[-1])]
            if len(bafter) >= 2:
                bench_ret = (float(bafter.iloc[-1]) / float(bafter.iloc[0]) - 1) * 100
            else:
                bench_ret = np.nan
                no_bench += 1
            tier = "buy" if not r["filter"].startswith("zone:") else r["filter"].split(":")[1]
            rows.append({
                "symbol": sym, "market": mkt, "source": r["source"], "filter": r["filter"],
                "tier": tier, "entry_date": r["entry_date"], "entry_price": r["entry_price"],
                "last_price": last_px, "as_of": after.index[-1], "days_held": days_held,
                "ret_pct": ret, "bench_ret_pct": bench_ret,
                "xret_pct": ret - bench_ret if pd.notna(bench_ret) else np.nan,
                "bench_name": bench_name,
            })
    skipped["no_benchmark_coverage"] = no_bench
    return pd.DataFrame(rows), skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-days", type=int, default=5,
                    help="only score entries held at least this many days (default 5)")
    ap.add_argument("--out", type=str, default=None, help="also write a markdown report here")
    a = ap.parse_args()

    d, stats = load_sources()
    print("=" * 88)
    print("  STOCK PICK PERFORMANCE — merged from all available dated/priced sources")
    print("=" * 88)
    for name, (n, lo, hi) in stats.items():
        print(f"  {name:<18} {n:>6} rows   {pd.Timestamp(lo):%Y-%m-%d} -> {pd.Timestamp(hi):%Y-%m-%d}")
    print(f"\n  merged, deduped, priced: {len(d):,} entries "
          f"({d['entry_date'].min():%Y-%m-%d} -> {d['entry_date'].max():%Y-%m-%d})")
    print(f"  KNOWN GAP:  2026-06-27 -> 2026-07-12 (16d, no source has anything)")
    live_max = pd.Timestamp(stats["live_ledger"][2])
    today = pd.Timestamp(date.today())
    print(f"  KNOWN GAP:  signal_tracker --record has not run since "
          f"{live_max:%Y-%m-%d} ({(today - live_max).days}d and counting — "
          f"wired into no cron/launchd job)")

    scored, skipped = score(d, a.min_days)
    no_bench = skipped.pop("no_benchmark_coverage", 0)
    print(f"\n  scored (aged >= {a.min_days}d, IN+US only — EU/JP/KR have no local "
          f"panel): {len(scored):,} of {len(d):,}")
    print(f"  not scored at all: " + (", ".join(f"{k}={v}" for k, v in skipped.items() if v) or "none"))
    if no_bench:
        print(f"  of those scored, {no_bench:,} have a real ret_pct but no benchmark "
              f"covering their window (xret_pct = NaN, excluded from 'vs bench' medians "
              f"— not zero-filled, not dropped from ret_pct)")

    if scored.empty:
        print("\n  nothing to report at this min-days threshold."); return

    print(f"\n  {'-'*84}")
    print(f"  BY TIER (buy = signal/watch/playbook/justified/raw filter pass, "
          f"hold = held/value-hold, sell = sold/evicted)")
    print(f"  {'tier':<8}{'n':>6}{'med ret%':>10}{'med vs bench':>14}{'win%':>7}{'med days':>10}")
    print(f"  {'-'*84}")
    for tier, g in scored.groupby("tier"):
        print(f"  {tier:<8}{len(g):>6}{g['ret_pct'].median():>10.2f}"
              f"{g['xret_pct'].median():>14.2f}{(g['ret_pct']>0).mean()*100:>6.0f}%"
              f"{g['days_held'].median():>10.0f}")

    print(f"\n  {'-'*84}")
    print(f"  BY MARKET x SOURCE")
    print(f"  {'-'*84}")
    for (mkt, src), g in scored.groupby(["market", "source"]):
        print(f"  {mkt:<4}{src:<18}{len(g):>6}   med ret {g['ret_pct'].median():>7.2f}%   "
              f"med vs bench {g['xret_pct'].median():>7.2f}%   win {(g['ret_pct']>0).mean()*100:>5.0f}%")

    print(f"\n  {'-'*84}")
    print(f"  OVERALL: {len(scored):,} scored entries, median return "
          f"{scored['ret_pct'].median():.2f}%, median vs benchmark "
          f"{scored['xret_pct'].median():.2f}%, win rate {(scored['ret_pct']>0).mean()*100:.0f}%")
    print(f"  'vs benchmark' is what matters — beating the index, not the sign of the raw return.")

    out_csv = RESEARCH / "stock_pick_performance.csv"
    scored.to_csv(out_csv, index=False)
    print(f"\n  -> {out_csv}")

    if a.out:
        _write_markdown(Path(a.out), stats, d, scored, skipped, a.min_days)
        print(f"  -> {a.out}")


def _write_markdown(path, stats, d, scored, skipped, min_days):
    today = pd.Timestamp(date.today())
    live_max = pd.Timestamp(stats["live_ledger"][2])
    lines = [
        f"# Stock Pick Performance — {today:%Y-%m-%d}",
        "",
        "Merged from every dated/priced source available on this machine — not a "
        "true archive of what was emailed (none exists before this data), see "
        "coverage below.",
        "",
        "## Coverage",
        "",
        "| source | rows | date range |",
        "|---|---:|---|",
    ]
    for name, (n, lo, hi) in stats.items():
        lines.append(f"| {name} | {n:,} | {pd.Timestamp(lo):%Y-%m-%d} → {pd.Timestamp(hi):%Y-%m-%d} |")
    lines += [
        "",
        f"Merged/deduped/priced: **{len(d):,}** entries, "
        f"{d['entry_date'].min():%Y-%m-%d} → {d['entry_date'].max():%Y-%m-%d}.",
        "",
        "**Known gaps:**",
        "- 2026-06-27 → 2026-07-12 (16d): no source has anything.",
        f"- `signal_tracker.py --record` has not run since {live_max:%Y-%m-%d} "
        f"({(today - live_max).days}d and counting) — wired into no cron/launchd job.",
        "- EU/JP/KR: no local price panel, scored 0 unless `--fetch-missing`.",
        "",
        f"## Scored (min {min_days}d held)",
        "",
        f"{len(scored):,} of {len(d):,} entries scored. Skipped: "
        + ", ".join(f"{k}={v}" for k, v in skipped.items() if v),
        "",
        "| tier | n | median ret% | median vs bench% | win% | median days held |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for tier, g in scored.groupby("tier"):
        lines.append(f"| {tier} | {len(g)} | {g['ret_pct'].median():.2f} | "
                     f"{g['xret_pct'].median():.2f} | {(g['ret_pct']>0).mean()*100:.0f}% | "
                     f"{g['days_held'].median():.0f} |")
    lines += [
        "",
        f"**Overall**: median return {scored['ret_pct'].median():.2f}%, "
        f"median vs benchmark {scored['xret_pct'].median():.2f}%, "
        f"win rate {(scored['ret_pct']>0).mean()*100:.0f}%.",
        "",
        "'vs benchmark' is the number that matters — beating the index, not the "
        "sign of the raw return. n is still small; treat as a diary, not a result, "
        "until each tier has hundreds of entries across many dates.",
    ]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
