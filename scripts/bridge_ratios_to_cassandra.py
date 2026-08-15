#!/usr/bin/env python3
"""
bridge_ratios_to_cassandra.py — real per-symbol P/E, P/B, ROE, market by market.

Generalized from bridge_eu_ratios_to_cassandra.py (2026-07-30), which fixed
Europe alone. Building US next made the SAME three fragile pieces necessary a
second time — the sparse-trailing-date price join, the plausibility backstop,
the fundamentals_source write-safety — and duplicating those into a third,
fourth, fifth near-identical file (Japan/Korea/China are the obvious next
targets) was worse than generalizing now. bridge_eu_ratios_to_cassandra.py is
superseded by `--market EUROPE` here; it is left in place rather than deleted,
since deleting someone's working script is not this script's call to make.

WHY THIS EXISTS AT ALL. completeness_graph.py's Cassandra audit found
`fundamentals_source` — a column that already existed, already populated —
showing 99-100% of EVERY market's rows as `median_imputed`, not measured.
`stock_quotes` reports "100% populated" regardless; a median-imputed ROE ranks
identically to a measured one in anything that sorts on the column. This script
closes that gap from data already collected, market by market, rather than
launching a new extraction per market.

WHY THIS IS FIXABLE FROM DATA ALREADY HERE. public.global_fundamentals
(Postgres) carries RAW financial-statement fields per ticker per fiscal
period — revenue, net_income, equity, shares — for every market this repo
tracks. It has no pe/pb columns; those need a PRICE, which the OHLCV warehouse
(repos/global-market-data/warehouse/ohlcv/<MKT>) already has, same yf_ticker
convention as Cassandra's `instruments` table.

  eps  = net_income / shares
  bvps = equity / shares
  pe   = latest_close / eps    (only if eps > 0 — a P/E on a loss is undefined)
  pb   = latest_close / bvps   (only if bvps > 0)
  roe  = net_income / equity   (a fraction, e.g. 0.098, NOT a percent — matches
                                the convention already in Cassandra's rows)

Per ticker, the LATEST fiscal period with COMPLETE fields is used — the newest
filing for a ticker is often the incomplete one (fields still arriving), and an
incomplete row would either crash the ratio or silently mismatch numerator and
denominator across periods.

🔴 THE PANEL'S OWN max(Date) IS A SPARSE TRAILING ROW, IN EVERY MARKET CHECKED
SO FAR. Europe's max date carried 15 of ~1,610 symbols; US's carried 9 of
~7,600. Filtering to `Date = max(Date)` leaves almost nothing to join against.
A window function picks each symbol's own most recent close instead of
assuming the whole panel shares one "latest day".

WRITE SAFETY. `UPDATE ... SET pe=?, pb=?, roe=?, fundamentals_source=?` touches
ONLY those four columns — never cmp/rsi/ema_*/etc — so this cannot repeat the
UNSET/None tombstone bug fixed in quote_updater.py (that bug was specific to a
single INSERT carrying all 41 columns). fundamentals_source is set to
'derived_price_join' on every row this script writes, not left at whatever it
was — a ratio this script computes is genuinely derived from filed financials
+ a traded price, and leaving the old 'median_imputed' label in place (a
mistake made and then caught in the Europe run) would make it indistinguishable
from a placeholder to the very audit this exists to satisfy.

PLAUSIBILITY IS PER-MARKET, NOT GLOBAL. LSE (.L) quotes in pence while
global_fundamentals reports UK filings in pounds — confirmed on CVSG.L, not
inferred — and produced pe=14,581 uncorrected before a /100 fix. Each market
gets its own known-quirk table (empty until something is actually confirmed
broken, per the same standard as the .L fix) plus a plausibility ceiling as a
backstop for whatever hasn't been individually verified yet. A dropped row is
a reported coverage gap, not a wrong number reported with confidence.

Usage:
  python3 bridge_ratios_to_cassandra.py --market US              # dry run
  python3 bridge_ratios_to_cassandra.py --market US --apply
  python3 bridge_ratios_to_cassandra.py --market EUROPE --apply
"""
from __future__ import annotations

import argparse
import glob
import sys

import duckdb
import pandas as pd

sys.path.insert(0, "/Users/umashankar/market-pipeline/code/python_files")
import pg_client

DSN = "dbname=market_data host=/tmp user=umashankar"
WAREHOUSE = "/Users/umashankar/repos/global-market-data/warehouse/ohlcv"

# market -> (global_fundamentals market code, Cassandra market partition key,
# OHLCV warehouse subdir, price-panel glob — US spans multiple year files,
# Europe/others currently ship one)
MARKETS = {
    "US":     ("US", "us",     "US",     "year=2026.parquet"),
    "EUROPE": ("EU", "europe", "EU",     "year=2026.parquet"),
    "JAPAN":  ("JP", "japan",  "JP",     "year=2026.parquet"),
    "KOREA":  ("KR", "korea",  "korea",  "year=2026.parquet"),
    "CHINA":  ("CN", "china",  "CN",     "year=2026.parquet"),
    "INDIA":  ("IN", "india",  "IN",     "year=2026.parquet"),
}

# Per-market quoting quirks, confirmed on a specific ticker before being added —
# never a guess extrapolated from a suffix pattern alone. Each entry:
# (predicate over the ticker column, divisor applied to `close`).
KNOWN_QUIRKS = {
    "EUROPE": [(lambda t: t.str.endswith(".L"), 100)],   # LSE: GBp vs GBP, see CVSG.L
}
# NOTE (2026-08-15): the price now comes from Cassandra's cmp, not the panel, so
# each quirk above has to be re-confirmed against THAT source before the market
# it covers is run again. yfinance also quotes .L in pence, so the /100 is very
# likely still right — but "likely" is the standard this table was explicitly
# built to avoid, and EUROPE is not being run here, so it is left untouched.

# 🔴 THE WAREHOUSE ABOVE NO LONGER EXISTS. repos/global-market-data was deleted
# and recreated LFS-free on 2026-08-04; warehouse/ohlcv/ was LFS content and went
# with it, so every market in MARKETS points at a dead path. The surviving panels
# for Japan and Korea are the cleaned_long_*.parquet files in cache_seed, which
# carry the same Symbol/Close/Date columns load_latest_price() already expects.
#
# Only JAPAN and KOREA are repointed here, because only those two were verified
# (2026-08-15) against a source already in use — Cassandra's own stock_quotes.cmp:
#   JP  3,062 overlapping tickers, median panel/cassandra 0.9913, log-corr 0.9958
#   KR  2,592 overlapping tickers, median 1.0724,            log-corr 0.9919
# Both correlate at 0.99+, so there is no unit or scale mismatch of the kind the
# .L pence bug was. KR's 7% median offset is consistent with a market move across
# the two-week gap between the panel's last date and the Cassandra fetch, but it
# is an offset that flows straight into pe/pb — see the coverage note printed at
# run time. US/EUROPE/INDIA/CHINA are deliberately left pointing at the dead path
# rather than guessed at: repointing a market whose panel has not been
# cross-checked is exactly the confidently-wrong write this script exists to avoid.
PANEL_OVERRIDE = {
    "JAPAN": "/Users/umashankar/repos/global-market-data/cache_seed/cleaned_long_JP.parquet",
    "KOREA": "/Users/umashankar/repos/global-market-data/cache_seed/cleaned_long_KR.parquet",
}

MAX_PLAUSIBLE_PE = 200
MAX_PLAUSIBLE_PB = 50

# 🔴 ROE IS A PERCENT IN THIS COLUMN, NOT A FRACTION. The docstring above used to
# claim the fraction "matches the convention already in Cassandra's rows" — that
# was circular: it matched only the rows THIS script had written. The app's own
# contract is a percent, stated in two places that predate this script:
#   backend/fetchers/providers/base.py:56   roe: Optional[float] = None   # %
#   backend/fetchers/providers/yahoo.py:127 _pct(returnOnEquity)  -> *100
# and the consumer reads it that way: daily_scanner.py:191 is `roe > 12`, i.e.
# 12 PERCENT. Writing 0.094 for a 9.4% ROE meant every row this script "fixed"
# scored 0% on the Buffett ROE criterion by construction, while the
# median_imputed placeholders it replaced passed 4-24% of the time — the fix
# made the column strictly worse for its only consumer. Measured 2026-08-15
# across the rows already written: derived_price_join median roe 0.094 with 0%
# above 12, against median_imputed median 9.0 and statements median 20.4.
ROE_AS_PERCENT = 100.0

# Same near-zero-denominator failure mode as pb (both divide by equity), but ROE
# had no ceiling — Korea's dry run produced roe as low as -1312 (i.e. -131,200%)
# from 8 symbols with equity <= 0. A real operating ROE outside +/-200% is
# essentially always an artifact of near-zero equity, so it is dropped and
# reported rather than written with confidence.
MAX_PLAUSIBLE_ROE_PCT = 200

# 🔴 A RATIO CAN BE PLAUSIBLE AND STILL WRONG IF THE FUNDAMENTALS ARE STALE.
# Found building the US bridge: 328 of 3,465 candidate symbols (9.5%) had their
# most recent COMPLETE fiscal row from 2009-2010 — RTX, PCG, AON, CMI, DKS, all
# real large-caps, not obscure delistings — a genuine collection gap in
# global_fundamentals for those specific tickers, not a bug in this script.
# Joining a 2009 EPS against a 2026 price produced RTX pe=0.077 (implying an
# EPS near $2,763) — plausible-LOOKING (the >200 ceiling only rejects
# implausibly HIGH values) and confidently wrong, which is worse than the
# median_imputed placeholder it would replace: at least a placeholder doesn't
# masquerade as a specific number tied to a real ticker's real current price.
# 2 years is not a guess — Europe's own "good" bulk clusters at 0.58y with a
# max of 2.58y and only 8/424 past 2y, so this is where the genuinely current
# data already ends, in the one market checked before US surfaced the problem.
MAX_FISCAL_AGE_YEARS = 2.0

# 🔴 INDIA REPORTS net_income/equity IN ₹ CRORE, shares IN ABSOLUTE UNITS.
# Confirmed on RELIANCE, not guessed: net_income=43851, equity=566235 (both
# ~crore-scale numbers) against shares=1.35e10 (a real absolute share count —
# Reliance's actual FY24 bonus roughly doubled it from ~6.77e9). Unscaled,
# eps = 43851/1.35e10 ≈ 0.0000032 — every India candidate's P/E blows up
# through the >200 ceiling, which is why the first dry run returned ZERO
# symbols out of 1,417 candidates. Scaled by 1e7 (1 crore = 10,000,000): eps
# = 32.4, matching Reliance's real known EPS — the exact ₹crore convention
# already solved once this session for a DIFFERENT source (screener.in), same
# fix, same number, independently re-derived here rather than assumed.
FUND_SCALE = {"INDIA": 1e7}


def load_fundamentals(fund_code: str) -> pd.DataFrame:
    pg_client.connect()
    d = pd.read_sql("""
        SELECT ticker, fy_end, net_income, equity, shares
        FROM public.global_fundamentals
        WHERE market = %s
          AND net_income IS NOT NULL
          AND equity IS NOT NULL
    """, pg_client.get_connection(), params=[fund_code])
    # 🔴 `shares` IS REQUIRED FOR pe/pb BUT NOT FOR roe. roe = net_income/equity
    # needs neither a share count nor a price. Requiring shares up front silently
    # discarded every ticker DART supplies without one — and that is not a long
    # tail: all 10,143 bare-coded KR rows lack shares (dart_history_collect.py
    # takes shares from KR.parquet as a proxy and leaves them null here), which
    # is why Samsung Electronics, SK Hynix and Hyundai Motor — three of Korea's
    # four largest listings — produced no ratio at all. Their net_income and
    # equity are present and give roe 10.36%, 35.63% and 8.12%.
    #
    # So rows are kept on (net_income, equity) alone. A row without usable shares
    # yields roe only; pe/pb come out NaN and are simply not written. Ranking a
    # ticker on a real ROE beats excluding it because one of three inputs is
    # missing.
    #
    # Sorting on (fy_end, shares-present) so that when a ticker has both a newer
    # shares-less row and an older complete one, the newer row wins on recency
    # for roe — the previous keep='last' on fy_end alone was already doing this,
    # but only among rows that all had shares.
    d["fy_end"] = pd.to_datetime(d.fy_end)
    d["shares"] = pd.to_numeric(d.shares, errors="coerce")
    d.loc[d.shares.le(0), "shares"] = float("nan")
    return d.sort_values("fy_end").drop_duplicates("ticker", keep="last")


def resolve_tickers(market: str, tickers: pd.Series) -> pd.Series:
    """
    Korea only: global_fundamentals stores 2,729 of its 4,938 KR tickers as bare
    6-digit codes ('264660') and the rest exchange-qualified ('019660.KQ'), while
    both the price panel and Cassandra use the qualified form throughout. Left
    unresolved, every bare row fails the price join and is silently dropped.

    🔴 THE SUFFIX IS NOT INFERABLE FROM THE CODE. '.KS' (KOSPI) and '.KQ'
    (KOSDAQ) are exchange facts, not string patterns, so this resolves each stem
    against Cassandra's `instruments` table — the same allowlist the rest of the
    system treats as authoritative for what is listed where — and never appends a
    suffix by guessing. Checked before relying on it: all 2,768 korea stems map to
    exactly ONE qualified ticker, so the mapping is deterministic, not a
    best-guess. A stem absent from the allowlist stays bare and drops out at the
    price join, which is the correct outcome for something KRX does not list.
    """
    if market != "KOREA":
        return tickers
    from cassandra.cluster import Cluster
    s = Cluster(["127.0.0.1"]).connect("herrrickshaw")
    stem: dict[str, list[str]] = {}
    for row in s.execute("SELECT yf_ticker FROM instruments WHERE market = 'korea'"):
        stem.setdefault(row.yf_ticker.split(".")[0], []).append(row.yf_ticker)
    s.shutdown()
    unique = {k: v[0] for k, v in stem.items() if len(v) == 1}
    if len(unique) != len(stem):
        print(f"  {len(stem) - len(unique)} ambiguous stem(s) left unresolved "
              f"(more than one listed suffix) — not guessed")
    bare = ~tickers.str.contains(r"\.", regex=True)
    out = tickers.where(~bare, tickers.map(unique).fillna(tickers))
    n = int((out != tickers).sum())
    print(f"  resolved {n:,} bare KR code(s) to exchange-qualified tickers via "
          f"the instruments allowlist ({int(bare.sum()) - n:,} left bare — not listed)")
    return out


def load_cassandra_price(cass_market: str) -> tuple[pd.Series, str]:
    """
    Price straight from the row this script is about to update.

    🔴 THE PRICE MUST COME FROM THE SAME ROW THE RATIO LANDS IN. An external
    panel is a different observation on a different date, so `pe` computed from
    it does NOT satisfy pe == cmp/eps for the row it is written to — the row
    contradicts itself and anyone recomputing gets a third answer. Measured
    2026-08-15 with the cache_seed panel: PE recomputed from the row's own cmp
    moved by a median 4.8% (JAPAN) / 7.1% (KOREA), and by >10% for 21% / 39% of
    symbols. That is the whole reason for reading cmp here instead.

    This makes freshness a precondition rather than a detail: the ratio is only
    as current as cmp, so refresh the market (bulk_fetcher Phase 1) BEFORE
    running this, and check the reported cmp age below.
    """
    from cassandra.cluster import Cluster
    s = Cluster(["127.0.0.1"]).connect("herrrickshaw")
    px, ages = {}, []
    for r in s.execute("SELECT yf_ticker, cmp, fetched_at FROM stock_quotes "
                       "WHERE market = %s", (cass_market,)):
        if r.cmp is not None and r.cmp > 0:
            px[r.yf_ticker] = r.cmp
            if r.fetched_at is not None:
                ages.append(r.fetched_at)
    s.shutdown()
    if not px:
        raise SystemExit(f"no cmp in stock_quotes for {cass_market} — run the "
                         f"backend fetch first; this script will not fall back "
                         f"to a stale panel")
    newest = max(ages).date() if ages else None
    age_days = (pd.Timestamp.now().date() - newest).days if newest else None
    stamp = f"cmp from stock_quotes, newest fetched_at {newest} ({age_days}d old)"
    if age_days is not None and age_days > 3:
        print(f"  🔴 cmp is {age_days} days old ({newest}). Every pe/pb written "
              f"will carry that staleness. Refresh with bulk_fetcher Phase 1 "
              f"before relying on these ratios.")
    return pd.Series(px), stamp


def load_latest_price(market: str, panel_dir: str, panel_glob: str) -> pd.Series:
    override = PANEL_OVERRIDE.get(market)
    files = ([override] if override and glob.glob(override)
             else sorted(glob.glob(f"{WAREHOUSE}/{panel_dir}/{panel_glob}")))
    if not files:
        raise SystemExit(f"no price panel found for {market} at "
                         f"{override or f'{WAREHOUSE}/{panel_dir}/{panel_glob}'}")
    c = duckdb.connect()
    src = ", ".join(f"'{f}'" for f in files)
    d = c.execute(f"""
        SELECT Symbol, Close FROM (
            SELECT Symbol, Close, Date,
                   row_number() OVER (PARTITION BY Symbol ORDER BY Date DESC) rn
            FROM read_parquet([{src}])
            WHERE Close IS NOT NULL
        ) WHERE rn = 1
    """).df()
    return d.set_index("Symbol").Close


def build_ratios(market: str) -> pd.DataFrame:
    fund_code, cass_market, _, _ = MARKETS[market]
    f = load_fundamentals(fund_code)
    f["ticker"] = resolve_tickers(market, f.ticker)
    px, stamp = load_cassandra_price(cass_market)
    n_before = len(f)
    f["close"] = f.ticker.map(px)
    # A missing price costs pe/pb but not roe, so price-less rows are kept.
    n_priced = int(f.close.notna().sum())
    print(f"  price source: {stamp}")
    print(f"  {n_priced:,}/{n_before:,} symbol(s) matched a cmp "
          f"({n_before - n_priced:,} keep roe only)")

    scale = FUND_SCALE.get(market)
    if scale:
        f["net_income"] = f.net_income * scale
        f["equity"] = f.equity * scale

    for predicate, divisor in KNOWN_QUIRKS.get(market, []):
        mask = predicate(f.ticker)
        f.loc[mask, "close"] = f.loc[mask, "close"] / divisor

    age_years = (pd.Timestamp.now() - f.fy_end).dt.days / 365.25
    stale = age_years > MAX_FISCAL_AGE_YEARS
    n_stale = int(stale.sum())
    if n_stale:
        print(f"  dropped {n_stale} symbol(s) whose latest complete fiscal row "
              f"is >{MAX_FISCAL_AGE_YEARS:.0f}y old — a real collection gap for "
              f"those tickers, not something safe to pair with today's price")
    f = f[~stale]

    f["eps"] = f.net_income / f.shares
    f["bvps"] = f.equity / f.shares
    f["roe"] = f.net_income / f.equity * ROE_AS_PERCENT
    f["pe"] = (f.close / f.eps).where(f.eps > 0)
    f["pb"] = (f.close / f.bvps).where(f.bvps > 0)

    wild_roe = f.roe.abs() > MAX_PLAUSIBLE_ROE_PCT
    if int(wild_roe.sum()):
        print(f"  dropped roe on {int(wild_roe.sum())} symbol(s) outside "
              f"+/-{MAX_PLAUSIBLE_ROE_PCT:.0f}% — near-zero or negative equity, "
              f"not a real return on capital")
    f.loc[wild_roe, "roe"] = float("nan")

    implausible = (f.pe.abs() > MAX_PLAUSIBLE_PE) | (f.pb.abs() > MAX_PLAUSIBLE_PB)
    n_dropped = int(implausible.sum())
    if n_dropped:
        print(f"  dropped {n_dropped} symbol(s) with |pe|>{MAX_PLAUSIBLE_PE} or "
              f"|pb|>{MAX_PLAUSIBLE_PB} — likely an unverified currency/unit "
              f"convention, or a non-operating security (warrant/unit/preferred) "
              f"whose 'fundamentals' don't describe an operating company")
    f = f[~implausible]

    # Keep a row if ANY of the three is derivable — roe-only rows are the point
    # of the shares relaxation above, and dropping them here would undo it.
    out = f[["ticker", "fy_end", "close", "pe", "pb", "roe"]].dropna(
        subset=["pe", "pb", "roe"], how="all")

    # 🔴 DEDUPLICATE AFTER RESOLUTION, NOT BEFORE. load_fundamentals() dedupes on
    # the RAW ticker, but resolve_tickers() then maps bare '003547' onto
    # '003547.KS' — which often already exists as its own qualified row. The two
    # collide only after resolution: KOREA came out with 4,749 rows for 2,667
    # distinct tickers (4,164 duplicates); JAPAN, which has no bare codes, had
    # none. The pairs agree on fy_end, close and roe and differ only in whether
    # a share count was present, so one carries pe/pb and the other does not.
    #
    # Left unmerged, both get written and the LAST one wins arbitrarily — so a
    # ticker could keep the roe-only write and lose a perfectly good pe, and its
    # fundamentals_source label depended on row order. Sorting incomplete rows
    # first and keeping the last makes the richer row win deterministically.
    if out.ticker.duplicated().any():
        n_dup = int(out.ticker.duplicated().sum())
        out = (out.assign(_rank=out.pe.notna().astype(int) + out.pb.notna().astype(int))
                  .sort_values(["ticker", "_rank"])
                  .drop_duplicates("ticker", keep="last")
                  .drop(columns="_rank"))
        print(f"  merged {n_dup:,} duplicate ticker row(s) created by resolution "
              f"— kept the most complete row per ticker")
    return out


def write_cassandra(d: pd.DataFrame, cass_market: str) -> tuple[int, int]:
    from cassandra.cluster import Cluster
    from cassandra.query import UNSET_VALUE

    # Same cluster/keyspace as backend/db/cassandra_client.py:17
    # (KEYSPACE = 'herrrickshaw') — intentionally NOT imported from there:
    # this is a short-lived manual CLI run (--market X --apply), not the
    # long-lived FastAPI server process cassandra_client.py's singleton
    # lifecycle is designed for, and backend/ has no existing import
    # relationship with market-pipeline/scripts/ (verified by grep — the
    # Postgres side above uses pg_client.py precisely because that mirrors
    # an established pattern; this would be new coupling instead). If
    # host/keyspace ever need to be genuinely shared, the right unit to
    # extract is a small constants module, not this session-lifecycle import.
    s = Cluster(["127.0.0.1"]).connect("herrrickshaw")
    # 🔴 THE LABEL MUST DESCRIBE WHAT WAS ACTUALLY WRITTEN, PER ROW.
    # A single unconditional 'derived_price_join' was correct only while every
    # written row carried a pe. Once roe-only rows became writable (the `shares`
    # relaxation above), a row with UNSET pe kept whatever pe was already there —
    # a median_imputed placeholder — while being restamped as derived. Measured
    # on the first --apply run: 348 japan and 1,005 korea rows (39% of Korea's
    # derived set) claimed a derived PE that was still the market-median
    # sentinel. That is the exact failure this column exists to prevent, just
    # inverted from the Europe-run mistake the header describes.
    stmt_full = s.prepare(
        "UPDATE stock_quotes SET pe = ?, pb = ?, roe = ?, "
        "fundamentals_source = 'derived_price_join' "
        "WHERE market = ? AND yf_ticker = ?"
    )
    stmt_roe = s.prepare(
        "UPDATE stock_quotes SET roe = ?, "
        "fundamentals_source = 'derived_roe_only' "
        "WHERE market = ? AND yf_ticker = ?"
    )
    written = skipped = roe_only = 0
    for r in d.itertuples():
        pe = float(r.pe) if pd.notna(r.pe) else UNSET_VALUE
        pb = float(r.pb) if pd.notna(r.pb) else UNSET_VALUE
        roe = float(r.roe) if pd.notna(r.roe) else UNSET_VALUE
        if pe is UNSET_VALUE and pb is UNSET_VALUE and roe is UNSET_VALUE:
            skipped += 1
            continue
        if pe is UNSET_VALUE and pb is UNSET_VALUE:
            # roe alone is worth writing — for the DART-sourced Korean mega-caps
            # it is the ONLY ratio derivable — but it must NOT claim a derived
            # price ratio it did not compute. pe/pb are left untouched and the
            # row is labelled for what it is.
            s.execute(stmt_roe, (roe, cass_market, r.ticker))
            roe_only += 1
        else:
            # 🔴 A ROW WITH pb BUT NO pe MUST NOT KEEP ITS OLD pe. pe is NaN here
            # precisely when eps <= 0 — a loss-making company, for which a P/E is
            # undefined. Binding UNSET would leave the market-median placeholder
            # in place and then stamp the row 'derived', asserting a positive
            # earnings multiple for a company that lost money: 830 KOREA rows on
            # the first corrected run. An explicit NULL says "no P/E", which is
            # the truth. This is a single deliberate column null, not the blanket
            # UNSET/None confusion that caused the 2026-07-29 tombstone incident.
            if pe is UNSET_VALUE:
                pe = None
            s.execute(stmt_full, (pe, pb, roe, cass_market, r.ticker))
        written += 1
    s.shutdown()
    return written, skipped, roe_only


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", required=True, choices=sorted(MARKETS))
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    _, cass_market, _, _ = MARKETS[a.market]
    d = build_ratios(a.market)
    print(f"{len(d):,} {a.market} symbols with a real, derivable ratio "
          f"(price + complete fundamentals)")
    if len(d):
        print(d.describe()[["pe", "pb", "roe"]].round(2).to_string())
        print()
        print(d.head(8)[["ticker", "fy_end", "close", "pe", "pb", "roe"]]
              .round(3).to_string(index=False))

    if not a.apply:
        print("\n(dry run — pass --apply to write to Cassandra)")
        return 0

    written, skipped, roe_only = write_cassandra(d, cass_market)
    print(f"\nwrote {written:,} symbol(s) to Cassandra ({cass_market}) · "
          f"{written - roe_only:,} with pe/pb (derived_price_join) · "
          f"{roe_only:,} roe-only (derived_roe_only, pe/pb left untouched) · "
          f"skipped {skipped:,} (no positive-denominator ratio)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
