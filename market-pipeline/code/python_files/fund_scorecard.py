#!/usr/bin/env python3
"""
fund_scorecard.py — rank a tier-driven book against Indian mutual-fund peers.

THE QUESTION (user, 2026-07-28): did a book built from the three-tier watchlist
beat its CATEGORY of real funds, after costs, over the same window? Not "did it
make money" — a rising market makes everything money — but "where would it have
ranked among the professionals who were solving the same problem".

SCOPE (user's call): tier 2 is a SCORECARD, not a short book. This measures
whether evicted names underperformed; it does not construct a short position,
which would need per-market borrow assumptions against an India playbook that
is long-only anyway.

HOW THE BOOK'S CURVE IS BUILT. The events carry entry date, holding days and
total return, but no daily path. Rebuilding real marks from
bhavcopy.nse_deep_ohlcv was REJECTED: that panel is split-UNadjusted for India,
so a 1:2 split reads as a −50% day and would inject fake crashes into the curve.
Instead each position's total return — already computed and validated by
backtest_tier_anomalies.py — is spread at a constant geometric daily rate over
the days it was held. Total return is EXACT; only the intra-position path is
interpolated.
  The curve is then built DAILY (equal weight across the positions actually open
  each day) and resampled to month-end. Aggregating position month-fragments
  straight to months and averaging them is BIASED LOW — a position open 3 days
  of a month gets the same weight as one open all 30 — and on the India book
  that error reported CAGR 2.15% where the correct figure is 5.89%. It was
  caught by rebuilding the series daily as an independent check; that check is
  now the implementation.
  CONSEQUENCE, stated rather than hidden: reported max drawdown is a MONTHLY
  drawdown and understates the intra-month worst case.

WHAT THE BOOK IS, AND THE LOOK-AHEAD TRAP IT WOULD BE EASY TO FALL INTO.
backtest_tier_anomalies.py is a TRIPLE-BARRIER experiment: from each eviction
close it runs forward until the name touches +10% (or +5% in an RSI BUY band)
→ ANOMALY, touches −15% → validated_decline, or reaches 90 days → ageout.
`exit_ret_pct` is therefore measured FROM THE EVICTION for every outcome, and
the label is only known AFTERWARDS.
  So the one unbiased book this file supports is: BUY EVERY EVICTED NAME AT
  EVICTION, exit at whichever barrier hits first. That is the default here.
  Filtering to outcome == 'ANOMALY' would select the winners after the fact —
  it reports a median +6.3% in 28 days for India and is worth exactly nothing.
  --outcome exists for diagnostics and prints a LOOK-AHEAD banner when used.
  NB this is NOT the "buy at the anomaly trigger" re-entry book: those returns
  begin where this file's returns END, and are not in this dataset.

THE THREE WAYS THIS COMPARISON LIES, AND WHAT IS DONE ABOUT EACH
  1. COSTS. Fund NAV is net of everything; a backtest is gross. Round-trip
     transaction cost is charged to every position (--cost-bps). A synthetic
     management fee (--ter-bps) is available but defaults to 0, and when it is 0
     the report says so in the verdict line — the reader is told the direction of
     the remaining bias rather than being left to assume there is none.
  2. SURVIVORSHIP. Funds that died mid-window cannot have a full-window return,
     so the rank is necessarily against survivors. The count of non-survivors is
     printed next to every rank, because "12th of 30 survivors" means something
     different when 14 more funds died than when none did.
  3. TIME IN MARKET. The book holds nothing in months with no open positions;
     a fund is always invested. Comparing a 40%-invested book to a fully
     invested fund on raw return flatters whichever had the better regime, so
     time-in-market is reported and the book is also shown INVESTED-ONLY.

PLAN/OPTION: Direct + Growth only. Direct because it is what a self-directed
investor actually gets and it strips the distributor trail; Growth because IDCW
NAV drops on every payout and would understate total return.

Usage:
  python3 fund_scorecard.py                      # IN, all equity categories
  python3 fund_scorecard.py --category "Small Cap"
  python3 fund_scorecard.py --cost-bps 80 --ter-bps 100
  python3 fund_scorecard.py --from 2020-11-01 --to 2025-11-30
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
EVENTS = HERE / "reports" / "tier_anomaly_events.csv"
OUT_MD = HERE / "reports" / "fund_scorecard.md"
DSN = "dbname=market_data host=/tmp user=umashankar"

# Round-trip transaction cost, India delivery equity. STT 0.1% on the sell leg
# (10bp) + exchange/GST/stamp (~2bp) + spread & impact. 50bp is the LIQUID case;
# the tier book is illiquidity-tilted (see cost_vs_edge.py — the edge lives in
# illiquid names), so this is a floor, not a estimate of the true cost.
DEFAULT_COST_BPS = 50.0
MONTHS_PER_YEAR = 12


def book_daily(events: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """Equal-weight DAILY return series from dated, fixed-horizon trades.

    Built daily and resampled, NOT aggregated straight to months. Aggregating
    per-position month-fragments and averaging them is biased LOW: a position
    open 3 days of a month contributes a 3-day return but gets the same weight
    as one open all 30, dragging the month's mean toward zero. Measured on the
    India book that error understated CAGR 2.15% vs 6.26% — a factor of ~3.
    Weighting each DAY by the positions actually open that day removes it.

    Each position's TOTAL return is exact; only its intra-position path is
    interpolated at a constant geometric daily rate.
    """
    acc: dict[pd.Timestamp, list[float]] = {}
    for e in events.itertuples():
        days = max(int(e.days), 1)
        # Cost charged once per round trip, off the total return, before spreading.
        total = (1 + e.exit_ret_pct / 100.0) * (1 - cost_bps / 10_000.0) - 1
        g = (1 + total) ** (1 / days) - 1          # geometric daily rate
        for day in pd.date_range(pd.Timestamp(e.evict_date), periods=days, freq="D"):
            acc.setdefault(day, []).append(g)
    if not acc:
        return pd.DataFrame(columns=["date", "ret", "n_positions"])
    idx = pd.date_range(min(acc), max(acc), freq="D")
    # Days with no open position are CASH at 0%, not missing.
    ret = pd.Series({d: float(np.mean(v)) for d, v in acc.items()}).reindex(idx).fillna(0.0)
    n = pd.Series({d: len(v) for d, v in acc.items()}).reindex(idx).fillna(0)
    return pd.DataFrame({"date": idx, "ret": ret.values, "n_positions": n.values})


def to_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """Month-end NAV from the daily book — the frequency funds are compared at."""
    d = daily.set_index("date")
    nav = (1 + d.ret).cumprod()
    out = pd.DataFrame({
        "nav": nav.resample("ME").last(),
        "n_positions": d.n_positions.resample("ME").mean(),
    }).reset_index()
    out["month"] = out.date.dt.to_period("M")
    out["ret"] = out.nav.pct_change().fillna(out.nav.iloc[0] - 1)
    return out[["month", "ret", "nav", "n_positions"]]


def peer_monthly(con, categories, frm, to) -> pd.DataFrame:
    """Month-end NAV per scheme for Direct+Growth equity schemes."""
    cat_filter = ""
    if categories:
        ors = " OR ".join(f"s.category ILIKE '%{c}%'" for c in categories)
        cat_filter = f"AND ({ors})"
    q = f"""
        SELECT n.scheme_code, n.nav_date, n.nav, s.category, s.scheme_name
        FROM pg.funds.nav n
        JOIN pg.funds.schemes s ON s.scheme_code = n.scheme_code
        WHERE s.plan = 'direct' AND s.option = 'growth'
          AND s.category ILIKE '%Equity%'
          -- '%Equity%' alone drags in 'Hybrid Scheme - Equity Savings', which is
          -- a hybrid product with a debt sleeve — not an equity peer.
          AND s.category NOT ILIKE '%Hybrid%' {cat_filter}
          AND n.nav_date BETWEEN DATE '{frm}' AND DATE '{to}'
          AND n.nav > 0
    """
    df = con.execute(q).df()
    if df.empty:
        return df
    df["month"] = pd.to_datetime(df.nav_date).dt.to_period("M")
    # AMFI ships BOTH "Equity Scheme - Large Cap Fund" and "Equity Schemes -
    # Large Cap Fund". Grouping on the raw string splits one peer set into two
    # (a 1-fund "category" ranks the book against a single fund, which is noise).
    # Normalise to the label inside the parentheses, after the last dash.
    df["cat_norm"] = (df.category.str.extract(r"\(([^)]*)\)")[0]
                      .fillna(df.category).str.split("-").str[-1].str.strip())
    # last NAV in each month = month-end mark
    df = (df.sort_values("nav_date")
            .groupby(["scheme_code", "month"], as_index=False)
            .agg(nav=("nav", "last"), category=("category", "last"),
                 cat_norm=("cat_norm", "last"), scheme_name=("scheme_name", "last")))
    return df


def perf(nav: pd.Series) -> dict:
    """CAGR / annualised vol / monthly max drawdown from a month-end series."""
    nav = nav.dropna()
    if len(nav) < 2:
        return {}
    r = nav.pct_change().dropna()
    yrs = len(r) / MONTHS_PER_YEAR
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1 / yrs) - 1 if yrs > 0 else np.nan
    dd = (nav / nav.cummax() - 1).min()
    return {"cagr": cagr, "vol": r.std() * np.sqrt(MONTHS_PER_YEAR),
            "maxdd": dd, "total": nav.iloc[-1] / nav.iloc[0] - 1, "months": len(r)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", default="IN")
    ap.add_argument("--category", action="append",
                    help="substring match, repeatable (default: all equity)")
    ap.add_argument("--cost-bps", type=float, default=DEFAULT_COST_BPS)
    ap.add_argument("--ter-bps", type=float, default=0.0,
                    help="synthetic annual fee charged to the BOOK (default 0)")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to", dest="to")
    ap.add_argument("--events", default=str(EVENTS))
    ap.add_argument("--outcome", action="append",
                    help="DIAGNOSTIC ONLY — filtering on outcome is look-ahead")
    ap.add_argument("--min-peers", type=int, default=5,
                    help="skip categories thinner than this (default 5): "
                         "'2nd of 2' is not a ranking")
    a = ap.parse_args()

    ev = pd.read_csv(a.events)
    ev = ev[ev.market == a.market].copy()
    if a.outcome:
        ev = ev[ev.outcome.isin(a.outcome)]
        print("=" * 74)
        print("  ⚠  LOOK-AHEAD: --outcome selects trades by what HAPPENED, which")
        print("     was unknowable at entry. These numbers are not achievable and")
        print("     must not be reported as a track record.")
        print("=" * 74)
    if ev.empty:
        print(f"no events for market {a.market}")
        return 1
    ev["evict_date"] = pd.to_datetime(ev.evict_date)
    if a.frm:
        ev = ev[ev.evict_date >= a.frm]
    if a.to:
        ev = ev[ev.evict_date <= a.to]

    daily = book_daily(ev, a.cost_bps)
    if a.ter_bps:                       # synthetic fee accrues per calendar day
        daily["ret"] -= (a.ter_bps / 10_000.0) / 365.25
    book = to_monthly(daily)
    frm = book.month.min().start_time.date()
    to = book.month.max().end_time.date()

    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")

    panel_min, panel_max = con.execute(
        "SELECT min(nav_date), max(nav_date) FROM pg.funds.nav").fetchone()
    peers = peer_monthly(con, a.category, frm, to)

    bp = perf(book.set_index("month").nav)
    invested = book[book.n_positions > 0]
    # Time in market measured on DAYS (the real exposure), not months: a month
    # with one 2-day position is not an invested month.
    tim = float((daily.n_positions > 0).mean())

    lines = []
    def out(s=""):
        print(s); lines.append(s)

    out(f"# Fund scorecard — {a.market} tier book vs Indian MF peers")
    out()
    out(f"- window            : **{frm} → {to}**  ({bp.get('months', 0)} months)")
    out(f"- trades            : {len(ev):,}  (median hold "
        f"{ev.days.median():.0f}d)")
    out(f"- costs charged     : {a.cost_bps:.0f} bps round trip"
        f"{f' + {a.ter_bps:.0f} bps/yr synthetic fee' if a.ter_bps else ''}")
    out(f"- time in market    : **{tim:.0%}** of days "
        f"({int((daily.n_positions > 0).sum())}/{len(daily)}); the rest is cash "
        f"at 0% · mean {daily[daily.n_positions > 0].n_positions.mean():.0f} "
        f"positions open")
    out(f"- book CAGR         : **{bp.get('cagr', float('nan')):.2%}**  "
        f"· vol {bp.get('vol', float('nan')):.1%} "
        f"· monthly maxDD {bp.get('maxdd', float('nan')):.1%}")
    # What the book would have compounded at with no cash drag — the
    # like-for-like number against an always-invested fund.
    inv_d = daily[daily.n_positions > 0].ret
    gross_cagr = ((1 + inv_d).prod() ** (365.25 / len(inv_d)) - 1
                  if len(inv_d) else float("nan"))
    out(f"- invested-only CAGR: **{gross_cagr:.2%}** (cash drag removed; "
        f"the comparable number vs an always-invested fund)")
    out()

    # ── coverage gate ────────────────────────────────────────────────────────
    # Endpoint checks are NOT enough: a backfill running forward from 2016
    # reaches a min/max that spans the window long before the middle is filled,
    # so min<=frm and max>=to both pass over a hole. Coverage is counted as
    # DISTINCT MONTHS present inside the window against months expected.
    want = pd.period_range(book.month.min(), book.month.max(), freq="M")
    have = set(peers.month.unique()) if not peers.empty else set()
    missing = [str(m) for m in want if m not in have]
    if missing:
        out("## ⚠ PEER PANEL DOES NOT COVER THE WINDOW — ranking withheld")
        out()
        out(f"funds.nav spans **{panel_min} → {panel_max}**; the book needs "
            f"**{frm} → {to}**.")
        out(f"Months covered: **{len(want) - len(missing)}/{len(want)}** · "
            f"peer rows in range {len(peers):,}.")
        out(f"First gaps: {', '.join(missing[:6])}"
            f"{f' … (+{len(missing) - 6} more)' if len(missing) > 6 else ''}")
        out()
        # Distinguish "panel not loaded yet" from "no fund in this category
        # existed then" — they need opposite fixes, and blaming the backfill
        # for a category that simply had no Direct plans yet sends the reader
        # to re-run an ingest that is already complete.
        gap_lo, gap_hi = missing[0], missing[-1]
        loaded = con.execute(
            "SELECT count(DISTINCT date_trunc('month', nav_date)) FROM pg.funds.nav "
            "WHERE nav_date BETWEEN ? AND ?",
            [pd.Period(gap_lo).start_time.date(), pd.Period(gap_hi).end_time.date()],
        ).fetchone()[0]
        if loaded:
            out(f"The PANEL does cover those months ({loaded} present), so this is "
                "not a missing backfill: **no fund matching this filter existed "
                "then**. Direct plans only date from Jan 2013 and many categories "
                "were created by SEBI's 2017–18 and 2020 recategorisations. "
                "Re-run with `--from` set to the category's own start.")
        else:
            out("Those months are absent from funds.nav entirely — run "
                "`amfi_nav_collect.py --backfill-years 10`. A partial panel would "
                "rank the book against whichever funds happen to be loaded, which "
                "is worse than no rank at all.")
        OUT_MD.write_text("\n".join(lines) + "\n")
        print(f"\nwrote {OUT_MD}")
        return 0

    # ── rank within each category ────────────────────────────────────────────
    out("## Rank within category (Direct · Growth)")
    out()
    out("| Category | Peers ranked | Present but unrankable | Book CAGR | Median peer | Book rank | Percentile | Rank if fully invested |")
    out("|---|--:|--:|--:|--:|--:|--:|--:|")
    first, last = book.month.min(), book.month.max()
    thin: list[str] = []          # categories too small to rank against
    for cat, grp in peers.groupby("cat_norm"):
        wide = grp.pivot_table(index="month", columns="scheme_code", values="nav")
        present = list(wide.columns)                     # any NAV in the window
        # RANKABLE needs a mark at BOTH ends of the same window — a fund that
        # launched or died mid-window has no comparable full-window return.
        def _mark(c, m):
            return m in wide.index and pd.notna(wide[c].get(m))
        full = [c for c in present if _mark(c, first) and _mark(c, last)]
        unrankable = len(present) - len(full)            # launched OR died
        cagrs = {c: perf(wide[c])["cagr"] for c in full if perf(wide[c])}
        if not cagrs:
            continue
        if len(cagrs) < a.min_peers:
            thin.append(f"{cat} ({len(cagrs)})")
            continue
        s = pd.Series(cagrs).sort_values(ascending=False)
        bc = bp["cagr"]
        # The book competes IN the field, so the denominator includes it:
        # beating every peer is 1 of n+1, losing to every peer is n+1 of n+1.
        rank = int((s > bc).sum()) + 1
        field = len(s) + 1
        pct = (field - rank) / len(s)
        # Second rank on the cash-drag-free number, so a reader can separate
        # "the picks were bad" from "the book was only half invested".
        irank = int((s > gross_cagr).sum()) + 1
        out(f"| {cat} | {len(s)} | {unrankable} | {bc:.2%} | {s.median():.2%} | "
            f"{rank}/{field} | **{pct:.0%}** | {irank}/{field} |")
    out()
    if thin:
        out(f"> Skipped as too thin to rank against (<{a.min_peers} full-window "
            f"peers): {', '.join(thin)}.")
    if not a.ter_bps:
        out("> **Bias note**: no synthetic management fee was charged to the "
            "book (`--ter-bps 0`), so this compares a strategy BEFORE fees to "
            "funds AFTER fees. The book's true rank is lower than shown. Re-run "
            "with `--ter-bps 100` for a fee-parity view.")
    out("> Max drawdown is monthly and understates the intra-month worst case. "
        "Ranks are against funds with a mark at BOTH ends of the window; "
        "'present but unrankable' counts those that launched or died inside it "
        "and therefore have no comparable full-window return.")

    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
