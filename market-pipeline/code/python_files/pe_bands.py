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
        return _bands(q, con, P, a.source)
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
    # 🔴 INDEX MISALIGNMENT — the real cause of the ~10x errors. The previous
    # form was groupby(..., group_keys=False).apply(_ttm).reset_index(level=0,
    # drop=True). With group_keys=False the result ALREADY carries the original
    # index, so reset_index dropped a level that was not there and scrambled the
    # assignment: AHLUCONT's four most recent quarters sum to 47.55 while the
    # stored ttm_eps read 396.50. The XBRL parse was correct all along — this
    # was a pandas alignment bug wearing a data-quality costume. Assign per
    # group by explicit index instead.
    q["ttm_eps"] = np.nan
    for _sym, _g in q.groupby("symbol"):
        _e = _g.eps.rolling(4).sum()
        _span = (_g.period_end - _g.period_end.shift(3)).dt.days
        q.loc[_g.index, "ttm_eps"] = _e.where(_span.between(255, 300)).values
    q = q.dropna(subset=["ttm_eps"])
    q["n"] = q.groupby("symbol").ttm_eps.transform("size")
    q = q[q.n >= MIN_Q]
    print(f"{len(q):,} TTM observations · {q.symbol.nunique():,} symbols with "
          f">= {MIN_Q} quarters", flush=True)
    if q.empty:
        print("no symbol has enough history yet — fetch more filings first")
        return 1

    return _bands(q, con, P, a.source)


def _bands(q, con, P, source: str = "xbrl") -> int:
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
    # 🔴 THIS PRODUCED ELEVEN BUCKETS, NOT TEN. The previous form was
    #   rank(pct=True).mul(10).clip(upper=10).fillna(0).astype(int)
    # and astype(int) TRUNCATES: a percentile rank runs (0, 1], so ×10 gives
    # (0, 10] and int() floors the bottom of the range to 0 while ONLY the single
    # highest-ranked symbol — the one whose rank is exactly 1.0 — reaches 10.
    # Deciles 0..9 held ~143 symbols each and decile 10 held exactly ONE. Any
    # comparison of "the expensive decile" was therefore reading a single stock.
    # Surfaced immediately by writing the tier table into the report artifact on
    # 2026-07-29, having been invisible while the panel only lived in Postgres.
    # ceil maps (0, 1] onto 1..10 with no truncation and no orphan bucket.
    d["tier"] = (d.groupby("obs_date").pe
                  .rank(pct=True).mul(10).apply(np.ceil)
                  .clip(lower=1, upper=10).fillna(0).astype(int))
    con.execute(DDL)
    con.register("inc", d)
    con.execute(f'DELETE FROM pg."{SCHEMA}".india_pe_daily')
    con.execute(f'INSERT INTO pg."{SCHEMA}".india_pe_daily SELECT * FROM inc')
    print(f"wrote {len(d):,} daily P/E observations · {d.symbol.nunique():,} symbols")
    print(f"  {d.obs_date.min().date()} -> {d.obs_date.max().date()}")
    print("\nband occupancy:")
    print(d.band.value_counts(normalize=True).mul(100).round(1).to_string())
    _write_report(source, d, con)
    return 0


def _write_report(source: str, d, con) -> None:
    """Persist what the build measured, including its own accuracy.

    Until 2026-07-29 this script wrote to Postgres and printed to a terminal and
    produced no document at all, so the figures it is judged on — coverage, band
    occupancy, and the ~20.5% median error against fundamentals.ratios that
    justifies `--source xbrl` being the default — existed nowhere a reader could
    check them. Same failure as smallcap_screener's validation: a number nobody
    can verify without re-running a multi-minute job is unsourced in practice,
    however true it is.

    The accuracy check is recomputed HERE rather than quoted, so the artefact
    cannot drift from the panel it describes the way reentry_engine's docstring
    drifted from its cited report.
    """
    import datetime as _dt
    L: list[str] = []
    def o(x=""):
        L.append(x)

    o("# India P/E panel — bands, tiers and accuracy")
    o()
    o(f"Generated {_dt.date.today()} by `pe_bands.py --build --source {source}`.")
    o()
    o(f"- **{len(d):,}** daily observations · **{d.symbol.nunique():,}** symbols")
    o(f"- span **{d.obs_date.min().date()} → {d.obs_date.max().date()}**")
    o(f"- P/E is TTM: four consecutive quarters, each stamped at its FILING "
      f"date, so a lookup on any bar uses only what the market could already see")
    o()
    o("## Band occupancy")
    o()
    o("Bands are ±σ on **log** P/E. A multiple is ratio-scale and right-skewed —")
    o("10→20 must count the same as 40→80 — and banding raw P/E produced")
    o("z-scores of +78/−38 before this was corrected. σ carries a floor of 0.15")
    o("log units, because a near-constant multiple otherwise divides by ~0 (one")
    o("symbol reached z = −45 that way).")
    o()
    o("| band | share |")
    o("|---|--:|")
    for k, v in d.band.value_counts(normalize=True).mul(100).round(1).items():
        o(f"| {k} | {v}% |")
    o()
    nan_pct = float((d.band == "nan").mean() * 100) if "band" in d else 0.0
    o(f"> `nan` at {nan_pct:.1f}% is the honest coverage gap — symbols without "
      f"enough consecutive quarters to form a TTM window, or without the "
      f"{BAND_WIN}-observation history a band needs. It is reported rather than "
      f"dropped: a hidden gap reads as coverage.")
    o()

    # Accuracy against the independently-built ratios table.
    try:
        r = con.execute("""select ticker as symbol, pe as pe_ref
                           from pg.fundamentals.ratios
                           where market='india' and pe > 0""").df()
        last = d[d.obs_date == d.obs_date.max()][["symbol", "pe"]]
        m = last.merge(r, on="symbol", how="inner")
        m = m[(m.pe > 0) & (m.pe_ref > 0)]
        if len(m) >= 30:
            err = ((m.pe - m.pe_ref).abs() / m.pe_ref * 100)
            o("## Accuracy vs `fundamentals.ratios`")
            o()
            o(f"Independent cross-check on the latest bar, {len(m):,} symbols "
              f"present in both. `ratios` is built from a different source, so "
              f"agreement is evidence and disagreement is a question, not proof "
              f"either side is right.")
            o()
            o("| percentile | abs error |")
            o("|---|--:|")
            for q in (0.25, 0.50, 0.75, 0.90):
                o(f"| p{int(q * 100)} | {err.quantile(q):.1f}% |")
            o()
            o(f"- **median {err.median():.1f}%** · within 25%: "
              f"{(err <= 25).mean():.0%} · within 50%: {(err <= 50).mean():.0%}")
            o()
            o("> This number is why `--source` defaults to `xbrl`: the screener "
              "path measures wider AND covers fewer symbols (1,301 vs 1,744). "
              "Recomputed on every build rather than quoted, so it cannot drift "
              "from the panel it describes.")
            o()
    except Exception as e:                                    # noqa: BLE001
        o(f"> accuracy cross-check unavailable: {str(e)[:80]}")
        o()

    o("## Cross-sectional tiers")
    o()
    o("`tier` is a per-DATE decile of P/E, so tier 1 is \"cheapest tenth "
      "TODAY\" rather than cheap against a fixed historical level. That keeps "
      "it invariant to market-wide re-rating: in a bull market every absolute "
      "P/E rises, and a fixed threshold would silently empty the cheap tier.")
    o()
    try:
        t = d[d.obs_date == d.obs_date.max()].tier.value_counts().sort_index()
        o("| tier (latest bar) | symbols |")
        o("|---|--:|")
        for k, v in t.items():
            o(f"| {k} | {v:,} |")
        o()
    except Exception:                                          # noqa: BLE001
        pass

    p = HERE / "reports" / f"pe_bands_{source}.md"
    p.parent.mkdir(exist_ok=True)
    p.write_text("\n".join(L) + "\n")
    print(f"\nwrote {p}")


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
    # 🔴 DEFAULT IS xbrl, AND CHANGING IT BACK WILL SHRINK THE TABLE. The default
    # used to be "screener", which is not what fundamentals.india_pe_daily is
    # built from — so a plain `--build` silently REPLACED the live 1,744-symbol
    # XBRL table with a 1,301-symbol screener one, dropping 277k observations
    # (done accidentally on 2026-07-28 while fixing an unrelated date lag). The
    # XBRL path wins on both axes it is judged by: coverage 1,744 vs 1,301
    # symbols, and accuracy ~20.5% vs ~28.5% median error against
    # fundamentals.ratios. The screener path stays available because it reaches
    # back to 2016 where XBRL starts at 2019, which matters for long-horizon
    # work — but it must be asked for explicitly, not arrived at by default.
    ap.add_argument("--source", default="xbrl", choices=("screener", "xbrl"))
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
