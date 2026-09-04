#!/usr/bin/env python3
"""
Price-band segmentation of the India scan universe.

Buckets the universe by LTP (₹0-250 / 250-500 / 500-1000 / 1000-5000 / 5000+)
and reports, per band, the liquidity mix, quality profile and screen pass rates.

The point is NOT that a price band is a valuation signal — in India the share
price is mostly an artefact of face value and share count, not company size, so
"cheap stock" is a category error. What price bands DO track is liquidity and
the size/quality of the underlying business, which is what changes which screen
you can trust. This script measures that instead of assuming it.

Note the '% fundamentals present' column: it was added expecting the cheap end
to be a data desert, and it is not (~96-98% coverage in every band). The cheap
band's low screen pass-rates are a real quality signal, not missing data.

Usage:
    .venv/bin/python3 price_band_analysis.py [--scan <workbook.xlsx>]
                                             [--out reports/price_bands.md]
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import pandas as pd

import price_bands as pb

# The ladder itself lives in price_bands.py, shared with the daily mailer's
# "By price band" section, so the two cannot drift on what a band means. This
# script is the India cross-section, so it bands in ₹ by default.
MARKET = "IN"

# Screens carried in the Fundamentals sheet as yes/no-ish object columns.
SCREEN_COLS = ["Piotroski_Strong", "CoffeeCan", "MagicFormula", "BullCartel"]

# Liquidity tiers, weakest to strongest, as emitted by adaptive_liquidity.py.
TIER_ORDER = [
    "T1_MOST_LIQUID",
    "T2_LIQUID",
    "T3_MID",
    "T4_ILLIQUID",
    "T5_MOST_ILLIQUID",
]


def latest_scan() -> str:
    """Newest India workbook, so the script follows the daily pipeline."""
    hits = sorted(glob.glob("indian_full_scan/indian_full_scan_*.xlsx"))
    if not hits:
        sys.exit("no indian_full_scan workbook found — run the India scan first")
    return hits[-1]


def truthy(s: pd.Series) -> pd.Series:
    """
    The screen columns are stringly-typed and inconsistent across screens
    ('YES'/'Yes'/'✓'/True/'NO'/'-'/nan). Normalise rather than trust any one form.
    """
    t = s.astype(str).str.strip().str.upper()
    return t.isin({"YES", "Y", "TRUE", "1", "✓", "PASS", "BUY"})


def load(path: str) -> pd.DataFrame:
    stocks = pd.read_excel(path, sheet_name="All_Stocks")
    fund = pd.read_excel(path, sheet_name="Fundamentals")

    # LTP lives in both sheets; keep All_Stocks' copy as the single source.
    fund = fund.drop(columns=[c for c in fund.columns if c in stocks.columns and c != "Symbol"])
    df = stocks.merge(fund, on="Symbol", how="left")

    df["Band"] = pb.assign(df["LTP"], MARKET)
    for c in SCREEN_COLS:
        if c in df.columns:
            df[c + "_ok"] = truthy(df[c])
    return df


def profile(df: pd.DataFrame) -> pd.DataFrame:
    """One row per band: size, liquidity, quality, signal."""
    rows = []
    # groupby(observed=False) on Band's Categorical dtype enumerates every
    # band in ladder order, including ones with zero rows here, without
    # re-scanning the full frame once per band the way a "for band in
    # BAND_LABELS: df[df['Band']==band]" loop does.
    for band, g in df.groupby("Band", observed=False):
        if g.empty:
            continue
        n = len(g)
        row = {
            "Band": band,
            "N": n,
            "% univ": 100 * n / len(df),
            "Median ₹": g["LTP"].median(),
            "Median turnover ₹": g["Median_Turnover"].median(),
            "% illiquid (T4+T5)": 100
            * g["Liquidity_Tier"].isin(["T4_ILLIQUID", "T5_MOST_ILLIQUID"]).mean(),
            "% most liquid (T1)": 100 * (g["Liquidity_Tier"] == "T1_MOST_LIQUID").mean(),
            "Median net profit ₹cr": g["Net_Profit_Cr"].median(),
            "Median Piotroski": g["Piotroski_Score"].median(),
            "Median ROCE %": g["ROCE_avg_%"].median(),
            "Median ROIC %": g["ROIC_%"].median(),
            "Median earn yield %": g["Earnings_Yield_%"].median(),
            "% breakout": 100 * (g["Darvas_Signal"] == "BREAKOUT_BUY").mean(),
            "% uptrend (50>200)": 100 * g["DMA50_above_200"].mean(),
            # Fundamentals coverage is itself a finding: the cheap end is where
            # the data thins out, which caps what any screen can claim there.
            "% fundamentals present": 100 * g["Piotroski_Score"].notna().mean(),
        }
        for c in SCREEN_COLS:
            if c + "_ok" in g.columns:
                row[f"% {c}"] = 100 * g[c + "_ok"].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def crosstab_liquidity(df: pd.DataFrame) -> pd.DataFrame:
    """Band x liquidity tier, row-normalised — the core structural claim."""
    ct = pd.crosstab(df["Band"], df["Liquidity_Tier"], normalize="index") * 100
    return ct.reindex(columns=[t for t in TIER_ORDER if t in ct.columns]).round(1)


def candidates(
    df: pd.DataFrame, per_band: int = 8, adv_pct: float = pb.ADV_PCT, drop_t5: bool = False
) -> pd.DataFrame:
    """
    Per band, the names that clear the quality+trend filter, ranked by the
    screen stack. This is a screening shortlist, not a recommendation.

    T5 is kept by DEFAULT. India already carries a ₹1cr policy floor, so an
    India T5 name still trades ≥₹1cr/day — and the platform's own backtests put
    the Piotroski edge in the ILLIQUID names, so filtering T5 out would discard
    exactly the population the edge was measured in. What actually differs by
    band is capacity, so price that in explicitly instead of excluding names:
    Max_pos is the position that keeps you at `adv_pct` of median daily
    turnover, which is the constraint that kills the edge as size grows.
    """
    ok = df[(df["Piotroski_Score"] >= 7) & (df["Darvas_Signal"] != "BREAKDOWN_SELL")].copy()
    if drop_t5:
        ok = ok[ok["Liquidity_Tier"] != "T5_MOST_ILLIQUID"]
    ok["Screens_passed"] = sum(
        ok[c + "_ok"].astype(int) for c in SCREEN_COLS if c + "_ok" in ok.columns
    )
    ok["Max_pos_₹L"] = pb.capacity(ok["Median_Turnover"], adv_pct) / 1e5  # ₹ lakh
    ok = ok.sort_values(
        ["Band", "Screens_passed", "Piotroski_Score", "ROCE_avg_%"],
        ascending=[True, False, False, False],
    )
    cols = [
        "Band", "Symbol", "LTP", "Piotroski_Score", "Screens_passed",
        "ROCE_avg_%", "Earnings_Yield_%", "Darvas_Signal", "Liquidity_Tier",
        "Max_pos_₹L",
    ]
    return ok.groupby("Band", observed=True).head(per_band)[cols]


def edge_population(df: pd.DataFrame, adv_pct: float = pb.ADV_PCT) -> pd.DataFrame:
    """
    Where the validated illiquid-Piotroski edge actually lives, by band.
    Counts high-Piotroski names in the illiquid tiers and the capacity
    available across that basket at `adv_pct`.

    Takes adv_pct explicitly (matching candidates()) rather than reading
    pb.ADV_PCT internally — main() was passing --adv-pct to candidates() but
    not here, so a non-default --adv-pct run showed two different %ADV
    assumptions in the same report with no warning.
    """
    hi = df[df["Piotroski_Score"] >= 7]
    ill = hi[hi["Liquidity_Tier"].isin(["T4_ILLIQUID", "T5_MOST_ILLIQUID"])]
    rows = []
    for band, g in ill.groupby("Band", observed=False):
        rows.append({
            "Band": band,
            "High-F illiquid names": len(g),
            "Median turnover ₹cr": round(g["Median_Turnover"].median() / 1e7, 2) if len(g) else 0,
            f"Basket capacity @{adv_pct:.0f}% ADV ₹cr":
                round(pb.capacity(g["Median_Turnover"], adv_pct).sum() / 1e7, 2),
        })
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", default=None)
    ap.add_argument("--out", default="reports/price_bands.md")
    ap.add_argument("--per-band", type=int, default=8)
    ap.add_argument("--adv-pct", type=float, default=pb.ADV_PCT,
                    help="%% of median daily turnover used as the position cap")
    ap.add_argument("--drop-t5", action="store_true",
                    help="exclude the most-illiquid tier (off by default — see candidates())")
    args = ap.parse_args()

    path = args.scan or latest_scan()
    df = load(path)

    prof = profile(df)
    liq = crosstab_liquidity(df)
    edge = edge_population(df, args.adv_pct)
    cand = candidates(df, args.per_band, args.adv_pct, args.drop_t5)

    pd.set_option("display.width", 220, "display.max_columns", 50)
    print(f"scan: {path}   universe: {len(df)}\n")
    print("── BAND PROFILE ─────────────────────────────────────────────")
    print(prof.round(1).to_string(index=False))
    print("\n── BAND × LIQUIDITY TIER (row %) ────────────────────────────")
    print(liq.to_string())
    print("\n── ILLIQUID-PIOTROSKI EDGE POPULATION ───────────────────────")
    print(edge.to_string(index=False))
    print(f"\n── SHORTLIST (Piotroski>=7, not breaking down; cap @{args.adv_pct}% ADV) ──")
    print(cand.round(1).to_string(index=False))

    # os.makedirs("", ...) raises even with exist_ok=True — dirname is "" for
    # a bare filename like --out price_bands.md, which should just write to
    # the current directory rather than crash before the report is written.
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write(f"# India universe by price band\n\n")
        fh.write(f"Scan: `{os.path.basename(path)}` · universe {len(df)} names\n\n")
        fh.write("## Band profile\n\n")
        fh.write(prof.round(1).to_markdown(index=False) + "\n\n")
        fh.write("## Band x liquidity tier (row %)\n\n")
        fh.write(liq.to_markdown() + "\n\n")
        fh.write("## Illiquid-Piotroski edge population\n\n")
        fh.write(edge.to_markdown(index=False) + "\n\n")
        fh.write(f"## Shortlist (Piotroski>=7, not breaking down; cap @{args.adv_pct}% ADV)\n\n")
        fh.write(cand.round(1).to_markdown(index=False) + "\n\n")
        fh.write(
            "Mechanical screen output on one day's cross-section. "
            "Educational/research only. NOT investment advice. "
            "Consult a SEBI-registered advisor.\n"
        )
    print(f"\n→ {args.out}")


if __name__ == "__main__":
    main()
