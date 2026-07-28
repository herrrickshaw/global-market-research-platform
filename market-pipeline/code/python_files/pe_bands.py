#!/usr/bin/env python3
"""
pe_bands.py — stock-level P/E history, Bollinger-style bands, and P/E tiers.

WHY BANDS RATHER THAN LEVELS. A P/E of 30 means nothing on its own: it is cheap
for an FMCG name and rich for a PSU bank. What is interpretable is a multiple
against its OWN trailing distribution — the same reasoning Bollinger applied to
price, and the same reasoning behind the user's peer-cluster point: multiples are
only meaningful relative to a reference set. Two references are computed here:

  SELF-BANDS   rolling mean +/- k*sigma of the stock's own trailing P/E.
               z = (pe - mean) / sigma. z > +2 = expensive versus its own past.
  PEER-TIERS   cross-sectional deciles at each date, so "tier 1" always means
               the cheapest tenth of the market that day regardless of the
               overall level. Absolute P/E buckets would silently re-rate the
               whole market as the index drifts.

🔴 P/E MUST BE BUILT FROM TRAILING-TWELVE-MONTH EPS, AND ONLY AFTER THE FILING
IS PUBLIC. Two traps live here:
  * TTM, not quarterly-annualised: one seasonal quarter times four is not an
    annual figure, and Indian results are strongly seasonal.
  * The EPS for a quarter ending 31-Mar is not knowable until it is FILED,
    typically 45-60 days later. Joining EPS on period_end would let a P/E
    respond to earnings the market had not seen — the same look-ahead class
    that cost 7.5 points in the ETF universe. TTM EPS is therefore stamped at
    the FILING date and held constant until the next filing.

DATA. fundamentals.india_quarterly, parsed from NSE XBRL by
scripts/nse_xbrl_eps.py. Bands need >= MIN_Q quarters of history, so coverage is
thinner than the raw filing count implies — reported, not glossed.

Usage:
  python3 pe_bands.py --build
  python3 pe_bands.py --show RELIANCE
  python3 pe_bands.py --extremes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, "/Users/umashankar/scripts")
DSN = "dbname=market_data host=/tmp user=umashankar"
SCHEMA = "fundamentals"
MIN_ANNUAL = 6       # annual observations needed on the screener path
MIN_Q = 8            # quarters of TTM history before a band is meaningful
BAND_WIN = 12        # trailing quarters for the rolling mean/sigma
K = 2.0
SD_FLOOR_LOG = 0.15  # minimum sigma of log P/E — see _bands()

DDL = f"""
CREATE TABLE IF NOT EXISTS pg."{SCHEMA}".india_pe_daily (
  symbol VARCHAR, obs_date DATE, close DOUBLE, ttm_eps DOUBLE, pe DOUBLE,
  pe_mean DOUBLE, pe_sd DOUBLE, pe_z DOUBLE, band VARCHAR, tier INTEGER
);
"""


def connect():
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")
    return con



# ── ALTERNATE SOURCE: screener.in annual history ─────────────────────────────
# The XBRL parse is quarterly but its coverage is still filling. This path uses
# the screener.in collector's annual history instead, found via the knowledge
# graph (screener_history_collector.py -> cache_seed/fundamentals_history/).
#
# 🔴 IN.parquet IS THE WRONG FILE. It mixes yfinance rows where QUARTERLY
# figures are labelled annual, which inflates EPS ~4x. IN_screener_only_backup
# is the clean one: 12,511 usable rows, 1,459 tickers, 2004-03 -> 2026-03,
# median 9 years per ticker. IN.parquet is still used, but ONLY to calibrate the
# filing lag below, never for EPS.
#
# 🔴 THE BACKUP HAS NO `filed` COLUMN, so availability must be assumed. Measured
# from IN.parquet's own filed-minus-fy_end: median 90 days, p90 90 days. A
# 90-day lag is therefore used — at the p90, i.e. deliberately late rather than
# optimistic. Using fy_end directly would let a P/E react to results the market
# had not seen, which is the look-ahead this whole module exists to avoid.
#
# TRADE-OFF, stated: this is ANNUAL EPS, so P/E steps once a year rather than
# quarterly. Coarser than the XBRL path, but it spans 2004-2026 today instead of
# waiting on a fetch.
SCREENER_DIR = ("/Users/umashankar/repos/global-stock-screener/"
                "cache_seed/fundamentals_history")
FILING_LAG_DAYS = 90


def load_screener_eps() -> pd.DataFrame:
    f = Path(SCREENER_DIR) / "IN_screener_only_backup.parquet"
    if not f.exists():
        raise SystemExit(f"missing {f}")
    d = pd.read_parquet(f, columns=["ticker", "fy_end", "net_income", "shares"])
    d["fy_end"] = pd.to_datetime(d.fy_end)
    d = d.dropna(subset=["net_income", "shares"])
    d = d[d.shares > 0]
    # 🔴 UNITS. screener.in reports net_income in ₹ CRORE (1e7) while `shares`
    # is an absolute count, so the naive ratio is 1e7 too small and P/E comes
    # out ~1e9. Caught by cross-validating against fundamentals.ratios: median
    # absolute error was 1,086,074,398%, which is the kind of number that can
    # only be a unit bug. Verified on knowns after scaling — RELIANCE ₹32.4 and
    # TCS ₹135.7 EPS, both correct.
    d["eps"] = d.net_income * 1e7 / d.shares
    d["avail"] = d.fy_end + pd.Timedelta(days=FILING_LAG_DAYS)
    d = (d.sort_values(["ticker", "fy_end"])
           .drop_duplicates(["ticker", "fy_end"], keep="last")
           .rename(columns={"ticker": "symbol"}))
    return d[["symbol", "fy_end", "avail", "eps"]]


def build(a) -> int:
    import pead_liquidity_study as P
    con = connect()
    if getattr(a, "source", "screener") == "screener":
        e = load_screener_eps()
        e["n"] = e.groupby("symbol").eps.transform("size")
        q = (e[e.n >= MIN_ANNUAL]
             .rename(columns={"avail": "filing_date", "eps": "ttm_eps",
                              "fy_end": "period_end"}))
        print(f"screener.in annual: {len(q):,} obs · {q.symbol.nunique():,} "
              f"symbols with >= {MIN_ANNUAL} years", flush=True)
        return _bands(q, con, P)
    q = con.execute(f'''SELECT symbol, period_end, filing_date, eps
                        FROM pg."{SCHEMA}".india_quarterly
                        WHERE eps IS NOT NULL''').df()
    if q.empty:
        print("no parsed quarters — run scripts/nse_xbrl_eps.py --parse-local")
        return 1
    q["period_end"] = pd.to_datetime(q.period_end)
    q["filing_date"] = pd.to_datetime(q.filing_date)
    q = (q.sort_values(["symbol", "period_end"])
           .drop_duplicates(["symbol", "period_end"], keep="last"))
    # TTM = 4 consecutive quarters, stamped at the FILING date of the last one
    # 🔴 rolling(4).sum() DOES NOT CHECK THAT THE FOUR QUARTERS ARE CONSECUTIVE.
    # With sparsely parsed filings a symbol may have Q1-2022, Q3-2023, Q1-2024,
    # Q2-2024 on file; the naive rolling sum adds those four and calls it a
    # trailing YEAR. Validated against fundamentals.ratios: FOSECOIND matched
    # (51.8 vs 52.5) while KANSAINER came out at HALF the reference and TARSONS
    # at a THIRD — the signature of a TTM spanning the wrong span. The window
    # must therefore cover ~one year of period_ends, or it is not TTM.
    def _ttm(g):
        e = g.eps.rolling(4).sum()
        # 🔴 OFF-BY-ONE: four consecutive quarter-ENDS span ~275 days, NOT 365.
        # End-to-end across 4 quarters crosses only THREE ~91-day gaps
        # (Mar-31 -> Dec-31 is 275 days). The first guard demanded 330-400 and
        # so rejected every valid window — 0 TTM observations from 20,498
        # parsed quarters. Verified against NITINFIRE and ATLASCYCLE, whose
        # clean consecutive runs measure 273-275 throughout.
        span = g.period_end - g.period_end.shift(3)
        return e.where(span.dt.days.between(255, 300))
    q["ttm_eps"] = (q.groupby("symbol", group_keys=False)
                      .apply(_ttm).reset_index(level=0, drop=True))
    q = q.dropna(subset=["ttm_eps"])
    q["n"] = q.groupby("symbol").ttm_eps.transform("size")
    q = q[q.n >= MIN_Q]
    print(f"{len(q):,} TTM observations · {q.symbol.nunique():,} symbols with "
          f">= {MIN_Q} quarters", flush=True)
    if q.empty:
        print("no symbol has enough history yet — fetch more filings first")
        return 1

    return _bands(q, con, P)


def _bands(q, con, P) -> int:
    px, _ = P.load_prices()
    out = []
    for sym, g in q.groupby("symbol"):
        if sym not in px.columns:
            continue
        g = g.sort_values("filing_date")
        s = px[sym].dropna()
        if s.empty:
            continue
        # step the TTM figure forward from each FILING date — never period_end
        ttm = pd.Series(g.ttm_eps.values, index=g.filing_date).reindex(
            s.index, method="ffill")
        pe = (s / ttm).replace([np.inf, -np.inf], np.nan)
        pe = pe.where(ttm > 0)                     # loss-makers have no P/E
        # bands on the quarterly TTM path, not the daily price path, so the
        # sigma reflects earnings revisions rather than price noise alone
        # 🔴 BANDS GO ON LOG P/E, NOT P/E. A multiple is ratio-scale and
        # violently right-skewed — 10->20 is the same move as 40->80, and the
        # upper tail is unbounded while the lower is floored at 0. Banding raw
        # P/E produced z-scores of +78 and -38 (GUJALKALI P/E 288 against a
        # mean of 9.6), which is not a band, it is a distributional artefact.
        # Same reasoning applied to the Bhojraj-Lee dispersion test earlier.
        lpe = np.log(pe.where(pe > 0))
        qpe = lpe.reindex(g.filing_date, method="ffill")
        win = min(BAND_WIN, max(3, len(qpe)))
        m = qpe.rolling(win, min_periods=3).mean()
        sd = qpe.rolling(win, min_periods=3).std()
        m_d = m.reindex(s.index, method="ffill")
        sd_d = sd.reindex(s.index, method="ffill")
        # 🔴 FLOOR THE SIGMA. With 3-6 annual observations a stock whose
        # multiple barely moved gets a near-zero rolling sd, and z explodes on
        # a trivial gap — THOMASCOTT scored z=-45 with a P/E of 28.8 against a
        # mean of 39.8, which is plainly not a 45-sigma event. The floor is
        # 0.15 in LOG space, i.e. "no stock's multiple is treated as more
        # stable than +/-15%", which is already generous for equities.
        sd_d = sd_d.clip(lower=SD_FLOOR_LOG)
        z = (lpe - m_d) / sd_d
        m_d = np.exp(m_d)                     # report the band in P/E units
        band = pd.cut(z, [-np.inf, -2, -1, 1, 2, np.inf],
                      labels=["<-2sd", "-2..-1sd", "normal", "+1..+2sd", ">+2sd"])
        d = pd.DataFrame({"symbol": sym, "obs_date": s.index, "close": s.values,
                          "ttm_eps": ttm.values, "pe": pe.values,
                          "pe_mean": m_d.values, "pe_sd": sd_d.values,
                          "pe_z": z.values, "band": band.astype(str)})
        out.append(d.dropna(subset=["pe"]))
    if not out:
        print("no overlap between parsed EPS and the price panel"); return 1
    d = pd.concat(out, ignore_index=True)
    # cross-sectional decile per date — "cheapest tenth TODAY", level-invariant
    d["tier"] = (d.groupby("obs_date").pe
                  .rank(pct=True).mul(10).clip(upper=10).fillna(0).astype(int))
    con.execute(DDL)
    con.register("inc", d)
    con.execute(f'DELETE FROM pg."{SCHEMA}".india_pe_daily')
    con.execute(f'INSERT INTO pg."{SCHEMA}".india_pe_daily SELECT * FROM inc')
    print(f"wrote {len(d):,} daily P/E observations · {d.symbol.nunique():,} symbols")
    print(f"  {d.obs_date.min().date()} -> {d.obs_date.max().date()}")
    print("\nband occupancy:")
    print(d.band.value_counts(normalize=True).mul(100).round(1).to_string())
    return 0


def extremes(a) -> int:
    con = connect()
    d = con.execute(f'''SELECT * FROM pg."{SCHEMA}".india_pe_daily
        WHERE obs_date = (SELECT max(obs_date) FROM pg."{SCHEMA}".india_pe_daily)''').df()
    if d.empty:
        print("nothing built"); return 1
    print(f"as of {d.obs_date.iloc[0]} · {len(d)} symbols with a band\n")
    for lbl, sub in (("CHEAPEST vs own history (z lowest)", d.nsmallest(8, "pe_z")),
                     ("RICHEST vs own history (z highest)", d.nlargest(8, "pe_z"))):
        print(lbl)
        for r in sub.itertuples():
            print(f"   {r.symbol:14s} P/E {r.pe:8.1f}  mean {r.pe_mean:7.1f}  "
                  f"z {r.pe_z:+6.2f}  tier {r.tier}")
        print()
    return 0


def show(a) -> int:
    con = connect()
    d = con.execute(f'''SELECT * FROM pg."{SCHEMA}".india_pe_daily
                        WHERE symbol = ? ORDER BY obs_date''', [a.show]).df()
    if d.empty:
        print(f"no P/E band for {a.show}"); return 1
    print(f"{a.show}: {len(d):,} days · {d.obs_date.min()} -> {d.obs_date.max()}")
    print(d.tail(5)[["obs_date", "close", "ttm_eps", "pe", "pe_mean", "pe_z",
                     "band", "tier"]].to_string(index=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--source", default="screener", choices=("screener", "xbrl"))
    ap.add_argument("--extremes", action="store_true")
    ap.add_argument("--show")
    a = ap.parse_args()
    if a.build:
        return build(a)
    if a.extremes:
        return extremes(a)
    if a.show:
        return show(a)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
