#!/usr/bin/env python3
"""
custom_indices.py — index level series for the gaps this study actually measured.

An index is a published level series, not a screen. The small-cap exclusion work
established a real gap; this turns it into something that can be tracked, charted
and benchmarked like any NIFTY index, into `indices.custom_daily`.

THE GAPS, and the index each one implies:

  SMLSCR  "Smallcap Screened" — the small-cap band MINUS the four exclusions
          (downtrend / distress / blowup / untradeable). The gap: a
          cap-weighted index must hold everything in its band, and over
          2016-2020 the Nifty Smallcap 250 returned 1.95%/yr while the median
          active manager made 6.72%. Managers were not picking better, they
          were declining to own the wreckage. Validated survivorship-free:
          screened-minus-band +3.07%/126 bars, t 8.75.

  SMLEXC  "Smallcap Excluded" — the complement, i.e. exactly what the index
          forces you to hold and a manager drops. Published because it is the
          falsifier: if SMLEXC does NOT underperform, the screen is noise. It
          is a diagnostic, not something to hold.

  SMLEW   "Smallcap Band Equal-Weight" — the band with no screen at all. The
          NULL. Any claim for SMLSCR has to beat this, not merely beat zero:
          equal-weighting alone already departs from cap-weighting, and that
          departure must not be credited to the screen.

CONSTRUCTION
  * universe   point-in-time by trailing turnover rank (the ~43% proxy for the
               real Smallcap 250 — NSE publishes no historical membership, see
               nse_index_tri.py). Stated, not hidden.
  * panel      survivorship-FREE: the price warehouse retains delisted names
               (DENABANK, DHFL, DISHMAN). A name that stops trading exits at
               its last real price rather than vanishing from history.
  * weighting  equal at each rebalance, drifting between — the same mechanic a
               real index uses, and it is what makes SMLEW the honest null.
  * rebalance  126 bars (semi-annual). Chosen by sweep, not taste: edge is
               +1.40pp at 63 bars, +2.59pp at 126, +2.47pp at 252 and REVERSES
               to −1.32pp at 504. Not a buy-and-hold construct.
  * cost       100bp per rebalance, charged to every series including the null,
               so the comparison is cost-neutral.
  * base       1000 at the first common date, matching NIFTY convention.

Usage:
  python3 custom_indices.py --build
  python3 custom_indices.py --status
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
SCHEMA = "indices"
BAND_LO, BAND_HI = 200, 450
REBAL = 126
COST_BPS = 100.0
BASE = 1000.0
WARMUP = 260

DDL = f"""
CREATE SCHEMA IF NOT EXISTS pg."{SCHEMA}";
CREATE TABLE IF NOT EXISTS pg."{SCHEMA}".custom_daily (
  index_code VARCHAR, index_name VARCHAR, index_date DATE,
  level DOUBLE, n_members INTEGER
);
"""
PG_SETUP = f"""
CREATE UNIQUE INDEX IF NOT EXISTS custom_daily_pk
  ON "{SCHEMA}".custom_daily (index_code, index_date);
"""

SPECS = {
    "SMLSCR": "Smallcap Screened (band ex downtrend/distress/blowup/illiquid)",
    "SMLEXC": "Smallcap Excluded (what the index forces you to hold)",
    "SMLEW":  "Smallcap Band Equal-Weight (the null)",
}



# ── THEMATIC BASKETS ─────────────────────────────────────────────────────────
# 🔴 THESE ARE NOT SURVIVORSHIP-FREE, unlike the SML* indices above. The
# small-cap band is selected POINT-IN-TIME by trailing turnover, so a company
# that later failed is still in the early universe. A thematic basket is a
# FIXED list written TODAY from knowledge of who exists today — every member
# survived to be named. Their histories therefore flatter the theme, and the
# level series is a descriptive record of "what these names did", NOT evidence
# that the theme was investable ex ante. Read them against SMLEW/Nifty, never
# as a backtest.
#
# Themes chosen for gaps NIFTY does not publish: there is no ethanol/sugar
# index, no EPC index, no railway index. Defence and renewables have partial
# NIFTY coverage but not at this composition.
THEMES = {
    "ETHANOL": ("Ethanol & Sugar Distillery",
                ["BALRAMCHIN", "TRIVENI", "PRAJIND", "DWARKESH", "BAJAJHIND",
                 "EIDPARRY", "DALMIASUG", "AVADHSUGAR", "DHAMPURSUG", "GAEL",
                 "TRUALT", "GODAVARIB"]),
    "EPC":     ("Engineering, Procurement & Construction",
                ["LT", "NCC", "HGINFRA", "PNCINFRA", "IRCON", "RVNL", "TECHNOE",
                 "ENGINERSIN", "RITES", "AFCONS", "GRINFRA", "JKIL", "ITDCEM",
                 "PATELENG", "GPTINFRA", "AHLUCONT", "CAPACITE"]),
    "RAIL":    ("Railways & Rolling Stock",
                ["IRCON", "RVNL", "RITES", "TITAGARH", "TEXRAIL", "BEML",
                 "IRFC", "CONCOR", "JWL", "RAILTEL"]),
    "DEFENCE": ("Defence & Aerospace",
                ["HAL", "BEL", "BDL", "MAZDOCK", "COCHINSHIP", "GRSE", "MIDHANI",
                 "PARAS", "DATAPATTNS", "ZENTEC", "ASTRAMICRO", "IDEAFORGE"]),
    "RENEW":   ("Renewable Energy & Transition",
                ["SUZLON", "INOXWIND", "ADANIGREEN", "JSWENERGY", "NTPCGREEN",
                 "WAAREEENER", "PREMIERENE", "ACMESOLAR", "KPIGREEN",
                 "ORIENTGREEN", "BOROSIL"]),
}


def build_themes(px, tv, rets, dates, cost):
    """Fixed-basket thematic indices. Equal-weight, same rebalance mechanic."""
    series, level = {}, {}
    for code, (name, syms) in THEMES.items():
        have = [s for s in syms if s in px.columns]
        if len(have) < 4:
            print(f"  {code}: only {len(have)} symbols present — skipped")
            continue
        lv, out = BASE, []
        i = WARMUP
        while i < len(dates) - 1:
            # a member counts only once it actually has a price; pre-IPO names
            # join the basket on listing rather than back-filling their absence
            live = [c for c in have if pd.notna(px[c].iloc[i])]
            j = min(i + REBAL, len(dates) - 1)
            if len(live) >= 3:
                lv *= (1 - cost)
                seg = rets.loc[dates[i + 1]:dates[j], live]
                path = lv * (1 + seg.mean(axis=1).fillna(0.0)).cumprod()
                out += list(zip(path.index, path.values, [len(live)] * len(path)))
                lv = float(path.iloc[-1]) if len(path) else lv
            i = j
        if out:
            series[code] = out
            level[code] = lv
            print(f"  {code:8s} {name:42s} {len(have):>2}/{len(syms)} symbols", flush=True)
    return series



# ── CROSS-COUNTRY THEMES ─────────────────────────────────────────────────────
# Same fixed-basket caveat as THEMES: written today, so survivorship-flattered.
# Prices for these markets need NO split adjustment — US/JP/KR/EU panels were
# verified adjusted earlier (India alone carried raw closes), so the India-only
# split-factor machinery does not apply here.
# Chosen where a real economic theme has no clean listed index:
GLOBAL_THEMES = {
    "US": {
        "NUCLEAR": ("US Nuclear & SMR",
                    ["CCJ", "LEU", "BWXT", "SMR", "OKLO", "VST", "CEG"]),
        "SEMICAP": ("US/EU Semiconductor Capital Equipment",
                    ["AMAT", "LRCX", "KLAC", "ASML", "TER", "ONTO", "ACLS"]),
        "GRID":    ("US Grid & Electrification",
                    ["ETN", "PWR", "NVT", "HUBB", "AME", "GEV"]),
    },
    "JP": {
        "ROBOT":   ("Japan Robotics & Factory Automation",
                    ["6954.T", "6506.T", "6861.T", "6273.T", "6324.T", "6141.T"]),
        "SEMIMAT": ("Japan Semiconductor Materials & Tools",
                    ["8035.T", "4063.T", "3436.T", "6857.T", "6146.T", "4062.T"]),
        "TRADING": ("Japan Trading Houses (sogo shosha)",
                    ["8058.T", "8031.T", "8001.T", "8053.T", "8002.T"]),
    },
    "KR": {
        "BATTERY":   ("Korea Battery & EV Supply Chain",
                      ["373220.KS", "006400.KS", "096770.KS", "086520.KQ", "003670.KS"]),
        "SHIPBUILD": ("Korea Shipbuilding",
                      ["329180.KS", "010140.KS", "042660.KS"]),
    },
    "EU": {
        "DEFEU":  ("Europe Defence",
                   ["RHM.DE", "BA.L", "HO.PA", "LDO.MI", "SAAB-B.ST", "AM.PA"]),
        "LUXURY": ("Europe Luxury",
                   ["MC.PA", "RMS.PA", "CFR.SW", "KER.PA", "MONC.MI"]),
    },
}


def build_global(cost):
    """Thematic baskets in US/JP/KR/EU, same mechanic, own market panels."""
    from backtest_tier_anomalies import load_market
    series = {}
    for mkt, themes in GLOBAL_THEMES.items():
        wanted = {s for _, (_, syms) in themes.items() for s in syms}
        df = load_market(mkt)
        df = df[df.Symbol.isin(wanted)]
        px = df.pivot_table(index="Date", columns="Symbol", values="Close").sort_index()
        px = px.loc["2016":]
        if px.empty:
            continue
        rets = px.pct_change(fill_method=None)
        dates = px.index
        for code, (name, syms) in themes.items():
            have = [s for s in syms if s in px.columns]
            if len(have) < 3:
                continue
            lv, out = BASE, []
            i = min(WARMUP, len(dates) - 2)
            while i < len(dates) - 1:
                live = [c for c in have if pd.notna(px[c].iloc[i])]
                j = min(i + REBAL, len(dates) - 1)
                if len(live) >= 3:
                    lv *= (1 - cost)
                    seg = rets.loc[dates[i + 1]:dates[j], live]
                    path = lv * (1 + seg.mean(axis=1).fillna(0.0)).cumprod()
                    out += list(zip(path.index, path.values, [len(live)] * len(path)))
                    lv = float(path.iloc[-1]) if len(path) else lv
                i = j
            if out:
                series[code] = out
                SPECS[code] = f"[{mkt}] {name}"
                print(f"  {code:10s} [{mkt}] {name:44s} {len(have)}/{len(syms)}",
                      flush=True)
    return series


def build(a) -> int:
    import duckdb
    import pead_liquidity_study as P
    from smallcap_screener import flags

    px, tv = P.load_prices()
    bad = P.contaminated(px)
    px = px.drop(columns=[c for c in bad if c in px.columns])
    tv = tv[px.columns]
    rets = px.pct_change(fill_method=None)
    dates = px.index
    print(f"{px.shape[1]:,} symbols × {len(px):,} bars "
          f"({len(bad)} excluded for unexplained discontinuity)", flush=True)

    series = {k: [] for k in SPECS}
    level = {k: BASE for k in SPECS}
    members = {k: [] for k in SPECS}
    cost = COST_BPS / 10_000

    i = WARMUP
    while i < len(dates) - 1:
        turn = tv.iloc[i - 260:i].median().dropna().sort_values(ascending=False)
        band = [c for c in turn.index[BAND_LO:BAND_HI] if c in px.columns]
        if len(band) >= 60:
            f = flags(px, tv, i, band)
            members["SMLEW"] = band
            members["SMLSCR"] = [c for c in band if not f.excluded.get(c, True)]
            members["SMLEXC"] = [c for c in band if f.excluded.get(c, True)]
            for k in SPECS:                      # rebalance cost
                if members[k]:
                    level[k] *= (1 - cost)
        j = min(i + REBAL, len(dates) - 1)
        # equal weight AT rebalance, drifting between: compound the daily
        # cross-sectional mean of the members fixed at formation
        for k, mem in members.items():
            if not mem:
                continue
            seg = rets.loc[dates[i + 1]:dates[j], mem]
            daily = seg.mean(axis=1).fillna(0.0)
            path = level[k] * (1 + daily).cumprod()
            series[k] += list(zip(path.index, path.values, [len(mem)] * len(path)))
            level[k] = float(path.iloc[-1]) if len(path) else level[k]
        i = j

    print("\nthematic baskets (fixed lists — NOT survivorship-free, see THEMES):",
          flush=True)
    tseries = build_themes(px, tv, rets, dates, cost)
    for code, vals in tseries.items():
        series[code] = vals
        SPECS[code] = THEMES[code][0]

    print("\ncross-country thematic baskets:", flush=True)
    for code, vals in build_global(cost).items():
        series[code] = vals

    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")
    for s in filter(None, (x.strip() for x in DDL.split(";"))):
        con.execute(s)
    con.execute("CALL postgres_execute('pg', ?)", [PG_SETUP])
    con.execute("CALL pg_clear_cache()")

    rows = []
    for k, vals in series.items():
        for d, lv, n in vals:
            rows.append({"index_code": k, "index_name": SPECS[k],
                         "index_date": d.date(), "level": lv, "n_members": n})
    df = pd.DataFrame(rows)
    con.register("inc", df)
    con.execute(f'DELETE FROM pg."{SCHEMA}".custom_daily WHERE index_code IN '
                "(SELECT DISTINCT index_code FROM inc)")
    con.execute(f'INSERT INTO pg."{SCHEMA}".custom_daily SELECT * FROM inc')
    con.unregister("inc")
    print(f"wrote {len(df):,} rows across {df.index_code.nunique()} indices\n")
    return status(a)


def status(a) -> int:
    import duckdb
    con = duckdb.connect()
    con.execute("INSTALL postgres"); con.execute("LOAD postgres")
    con.execute(f"ATTACH '{DSN}' AS pg (TYPE postgres)")
    d = con.execute(f'SELECT * FROM pg."{SCHEMA}".custom_daily').df()
    if d.empty:
        print("no custom indices built"); return 1
    d["index_date"] = pd.to_datetime(d.index_date)
    print(f"{'code':8s}{'index':56s}{'CAGR':>9s}{'vol':>8s}{'maxDD':>9s}{'members':>9s}")
    base = None
    order = (["SMLEW", "SMLSCR", "SMLEXC"] + sorted(THEMES) +
             sorted(c for m in GLOBAL_THEMES.values() for c in m))
    for k in order:
        g = d[d.index_code == k].sort_values("index_date")
        if g.empty:
            continue
        yrs = (g.index_date.iloc[-1] - g.index_date.iloc[0]).days / 365.25
        cagr = (g.level.iloc[-1] / g.level.iloc[0]) ** (1 / yrs) - 1
        r = g.level.pct_change().dropna()
        dd = (g.level / g.level.cummax() - 1).min()
        if k == "SMLEW":
            base = cagr
        nm = SPECS.get(k) or (THEMES[k][0] if k in THEMES else k)
        print(f"{k:8s}{nm[:55]:56s}{cagr:>8.2%}{r.std()*np.sqrt(252):>8.1%}"
              f"{dd:>9.1%}{g.n_members.mean():>9.0f}")
    if base is not None:
        for k in ("SMLSCR", "SMLEXC"):
            g = d[d.index_code == k].sort_values("index_date")
            if g.empty:
                continue
            yrs = (g.index_date.iloc[-1] - g.index_date.iloc[0]).days / 365.25
            c = (g.level.iloc[-1] / g.level.iloc[0]) ** (1 / yrs) - 1
            print(f"   {k} vs the null (SMLEW): {(c - base) * 100:+.2f}pp/yr")
    print(f"\nspan {d.index_date.min().date()} → {d.index_date.max().date()} · "
          f"rebalance {REBAL} bars · {COST_BPS:.0f}bp charged to ALL series")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    return build(a) if a.build else status(a)


if __name__ == "__main__":
    sys.exit(main())
