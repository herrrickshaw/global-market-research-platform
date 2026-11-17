#!/usr/bin/env python3
"""
global_price_bands.py — every name in the warehouse sorted by share price and
bucketed into price bands, across all six market panels.

RELATIONSHIP TO THE OTHER TWO PRICE-BAND FILES. price_bands.py owns the LADDER
(edges, labels, bucketing) and nothing else; price_band_analysis.py is the India
cross-section that joins a band to liquidity/quality/pass-rates off the scan
workbook. This file is neither: it is the cross-MARKET census — how the whole
tradable universe of each panel distributes across that market's ladder. It
defines no edges of its own and must not: it reads price_bands.BANDS, so a band
means the same thing here, in the mailer and in the India report.

TWO VIEWS, BECAUSE "SORT ALL MARKETS BY PRICE" IS AMBIGUOUS. A share price is a
currency quantity, so ¥3,000 and ₩3,000 differ ~100x in value and a single
numeric sort over the raw panels is meaningless. So:
  · BANDS are per-market and in LOCAL currency — the shared ladder's design,
    and the only scale on which "a ₹500 stock" means anything.
  · The cross-market SORT is USD-normalised, because ranking Tokyo against
    Mumbai requires one currency and there is no way around that.
Neither view is the "real" one; they answer different questions.

🔴 LONDON QUOTES IN PENCE. `.L` is the largest bloc of the EU panel and its
closes are GBX: a 416p line is £4.16. Currency and the /100 that unwinds a
sub-unit quote come from liquidity.CCY_BY_SUFFIX + liquidity.SUBUNIT, which
already encode this for London, Tel Aviv and Johannesburg. The EU panel is nine
currencies in one partition, so it is converted to EUR and banded as "EU_EUR" —
price_bands refuses the bare key "EU" precisely to stop pence reaching a euro
ladder.

🔴 THE PANELS ARE NOT EQUITY-ONLY. India's partition carries NSE DEBT series
alongside shares: measured 2026-09-16, 362 of the 394 India lines above $1,000
were bonds (`788BOBPERP` = 7.88% Bank of Baroda perpetual, `962APSB32` = 9.62%
Andhra Pradesh 2032), quoted at ₹1-10 lakh face value. Unfiltered that reads as
"5.5% of Indian STOCKS trade above $1,000", which is false. --equity-only
restricts to the liquidity index, a real allowlist: it drops every one of those
bonds while KEEPING digit-leading equities (3MINDIA, 20MICRONS, 63MOONS) that a
"starts with a number" regex would throw away. Instrument type comes from the
allowlist, never from the ticker's shape.

A BAND IS NOT A VALUATION CALL — see price_bands.CAVEAT, which this script
prints rather than restates.

USAGE
    python3 global_price_bands.py --equity-only        # the meaningful cut
    python3 global_price_bands.py                      # raw panels, warts and all
    python3 global_price_bands.py --market JP KR
    python3 global_price_bands.py --watchlist filter_watchlist.csv
    python3 global_price_bands.py --equity-only --csv /tmp/prices.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import data_registry as _dr      # noqa: E402
import liquidity as _liq         # noqa: E402 -- reuse the suffix/sub-unit currency map
import price_bands as _pb        # noqa: E402 -- the SHARED ladder; do not redefine edges here
import warehouse_paths as _wh    # noqa: E402

MARKETS = ["IN", "US", "EU", "JP", "KR", "CN"]
# Single-currency panels. EU is absent on purpose: 17 exchanges, 9 currencies,
# resolved per ticker instead (see module docstring).
MARKET_CCY = {"IN": "INR", "US": "USD", "JP": "JPY", "KR": "KRW", "CN": "CNY"}
# Panel key -> the ladder key in price_bands.BANDS. Only EU differs, because its
# prices have to be converted before a numeric scale applies to them.
LADDER_KEY = {m: m for m in MARKETS} | {"EU": "EU_EUR"}
LADDER_CCY = {"IN": "INR", "US": "USD", "JP": "JPY", "KR": "KRW",
              "CN": "CNY", "EU": "EUR"}

LIQ_INDEX = HERE / "cache_seed" / "liquidity_index.parquet"
# The liquidity index keys Europe by COUNTRY seed (UK/DE/SE/CH/FI/DK beside a
# residual "EU") while the warehouse keeps one "EU" partition. Looking up only
# allow["EU"] drops every London, Frankfurt, Stockholm and Zurich line as "not
# an equity". The panel key maps to the UNION of its seeds.
LIQ_SEEDS = {"EU": ["EU", "UK", "DE", "SE", "FI", "DK", "CH"]}

FX_STALE_DAYS = 7    # same policy as data_registry's fx.usd dataset
OUTLIER_X = 500.0    # xN of a market's median => report as suspect, never drop
THIN_COVERAGE = 0.20 # allowlist dropping more than this of a panel => warn


def fx_rates() -> tuple[dict, str]:
    """USD rates (units per 1 USD) from the pipeline's own cache.

    Refuses a stale file rather than silently pricing the world at a month-old
    rate — the same choice data_registry makes for the fx.usd dataset.
    """
    p = _dr.BHAV_CACHE / "fx_usd.json"
    if not p.exists():
        raise SystemExit(f"  no FX cache at {p} — run liquidity.py to populate it")
    d = json.loads(p.read_text())
    as_of = pd.Timestamp(d["as_of"])
    age = (datetime.now(timezone.utc).replace(tzinfo=None) - as_of.to_pydatetime()).days
    if age > FX_STALE_DAYS:
        raise SystemExit(f"  FX cache is {age}d old (>{FX_STALE_DAYS}d) — refusing "
                         f"to convert prices with it; refresh via liquidity.py")
    return d["rates"], f"{as_of:%Y-%m-%d %H:%M}"


def equity_allowlist() -> dict[str, set]:
    """market -> symbols the liquidity index knows as tradable equities.

    An ALLOWLIST on purpose: India's debt series are coupon-prefixed
    (`728NHAI30`) and so are several real equities (`3MINDIA`, `63MOONS`), so
    nothing about a ticker's shape separates them — only a list of what actually
    trades as a share does.
    """
    if not LIQ_INDEX.exists():
        return {}
    d = pd.read_parquet(LIQ_INDEX, columns=["Symbol", "Market"])
    d["Symbol"] = d["Symbol"].astype(str).str.upper()
    d["Market"] = d["Market"].astype(str).str.upper()
    by_seed = {m: set(g["Symbol"]) for m, g in d.groupby("Market")}
    out = dict(by_seed)
    for panel_key, seeds in LIQ_SEEDS.items():
        out[panel_key] = set().union(*(by_seed.get(s, set()) for s in seeds))
    return out


def _panel_path(mkt: str) -> Path:
    # India reads the split/bonus-adjusted panel like every other consumer here:
    # raw India closes fake -90% crashes straight through every split.
    return _wh.ohlcv_adj_in() if mkt == "IN" else _wh.market(mkt)


def latest_prices(mkt: str) -> pd.DataFrame:
    """Last close per symbol in one market panel, with its own bar date."""
    p = _panel_path(mkt)
    files = sorted(p.glob("year=*.parquet"))
    if not files:
        return pd.DataFrame(columns=["symbol", "market", "bar_date", "close_native"])
    # Two most recent year files: one alone misses a symbol that stopped trading
    # days into January, and reading all eleven costs ~10x for nothing.
    px = pd.concat([pd.read_parquet(f, columns=["Date", "Symbol", "Close"])
                    for f in files[-2:]], ignore_index=True)
    px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
    px = px.dropna(subset=["Date", "Close"])
    px = px[px["Close"] > 0]
    px["Symbol"] = px["Symbol"].astype(str).str.upper()
    last = (px.sort_values("Date").groupby("Symbol", as_index=False)
              .agg(bar_date=("Date", "last"), close_native=("Close", "last")))
    return (last.rename(columns={"Symbol": "symbol"})
                .assign(market=mkt)[["symbol", "market", "bar_date", "close_native"]])


def convert(df: pd.DataFrame, fx: dict) -> pd.DataFrame:
    """Add ccy / close_ccy (sub-units unwound) / close_usd / close_ladder.

    EU resolves currency per ticker suffix; every other panel is single-currency
    and must NOT be read from the suffix, which would price each bare Indian
    symbol in USD. close_ladder is the price in the currency that market's
    ladder is denominated in — identical to close_ccy except for EU, where nine
    quote currencies collapse to EUR.
    """
    out = df.copy()
    out["ccy"] = [
        _liq.currency_for(s) if m == "EU" else MARKET_CCY[m]
        for s, m in zip(out["symbol"], out["market"])
    ]
    sub = out["ccy"].map(_liq.SUBUNIT.get)
    out["ccy"] = [s[0] if s else c for s, c in zip(sub, out["ccy"])]
    native = pd.Series([v / s[1] if s else v
                        for s, v in zip(sub, out["close_native"].astype(float))],
                       index=out.index)
    out["close_ccy"] = native.round(4)
    rate = out["ccy"].map(fx.get)
    out["close_usd"] = (native / rate).where(rate.notna() & (rate > 0))
    ladder_rate = out["market"].map(lambda m: fx.get(LADDER_CCY[m]))
    out["close_ladder"] = (out["close_usd"] * ladder_rate).round(4)
    return out


def assign_bands(df: pd.DataFrame) -> pd.DataFrame:
    """Band each market on ITS OWN ladder, via the shared module."""
    out = df.copy()
    out["band"] = pd.Series(pd.NA, index=out.index, dtype="object")
    for m, g in out.groupby("market"):
        key = LADDER_KEY[m]
        out.loc[g.index, "band"] = _pb.assign(g["close_ladder"], key).astype(object)
        out.loc[g.index, "ladder"] = key
    return out


def band_table(df: pd.DataFrame) -> pd.DataFrame:
    """Band-rank x market counts.

    Ladders differ per market, so the ROW is the rung (1 = cheapest band of that
    market), not a shared price interval — stacking "₹0–250" against "¥0–1,000"
    in one row would imply an equivalence that does not exist. Each cell is
    labelled with its own market's band.
    """
    rows = []
    for m, g in df.groupby("market"):
        labels = _pb.labels_for(LADDER_KEY[m])
        counts = g["band"].value_counts()
        for i, lab in enumerate(labels, start=1):
            rows.append({"rung": i, "market": m, "band": lab,
                         "n": int(counts.get(lab, 0))})
    t = pd.DataFrame(rows)
    cell = t.assign(cell=t["band"] + "  " + t["n"].astype(str).str.rjust(5))
    return cell.pivot(index="rung", columns="market", values="cell").fillna("")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--market", nargs="*", default=MARKETS)
    ap.add_argument("--watchlist", type=str,
                    help="restrict to symbols tracked in this watchlist CSV")
    ap.add_argument("--equity-only", action="store_true",
                    help="restrict to the liquidity index's equity allowlist "
                         "(drops NSE debt series from the India panel)")
    ap.add_argument("--csv", type=str, help="write the full sorted list here")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()

    fx, fx_as_of = fx_rates()
    print(f"  FX as of {fx_as_of}  ({len(fx)} currencies)\n")

    frames = []
    for m in [x.upper() for x in a.market]:
        d = latest_prices(m)
        if d.empty:
            print(f"  {m}: no panel — skipped")
            continue
        frames.append(d)
    if not frames:
        print("  nothing to report")
        return 1
    raw = pd.concat(frames, ignore_index=True)
    df = convert(raw, fx)

    if a.equity_only:
        allow = equity_allowlist()
        if not allow:
            raise SystemExit(f"  --equity-only needs {LIQ_INDEX}, which is missing")
        keep = [s in allow.get(m, set()) for s, m in zip(df["symbol"], df["market"])]
        dropped = df[[not k for k in keep]]
        df = df[keep]
        print(f"  equity allowlist: kept {len(df):,} of {len(raw):,} panel names "
              f"(dropped {len(dropped):,} — {dropped['market'].value_counts().to_dict()})")
        # An allowlist removing a LARGE share of a panel is no longer filtering
        # instruments — it is exposing its own coverage gap, and the bands below
        # are then a sample, not the market. Measured 2026-09-16 the EU seeds
        # miss ~690 real Euronext shares (AKER.OL, ODET.PA, KSB.F …). Say so
        # rather than quietly report a filtered universe as the whole one.
        share = dropped["market"].value_counts() / raw["market"].value_counts()
        for m, frac in share[share > THIN_COVERAGE].dropna().sort_values(ascending=False).items():
            print(f"    ⚠️  {m}: allowlist drops {frac:.0%} of the panel — treat {m} "
                  f"bands as a sample of covered names, not the full market")
        print()

    if a.watchlist:
        # The watchlists and the panels disagree on ticker form for JP and KR
        # (bare '1301' vs '1301.T'; zero-stripped '100' vs '000100.KS'). Raw
        # string matching here would silently report "0 of 1,999 Japanese names
        # tracked". trailing_returns owns that mapping; reuse it rather than
        # keep a second copy that can drift out of step with it.
        from trailing_returns import _resolve_symbol
        wl = pd.read_csv(HERE / a.watchlist)
        by_mkt = {m: set(g["symbol"]) for m, g in df.groupby("market")}
        keep = set()
        for s, m in zip(wl["symbol"].astype(str), wl["market"].astype(str).str.upper()):
            col = _resolve_symbol(s, m, by_mkt.get(m, set()))
            if col:
                keep.add((col, m))
        before = len(df)
        df = df[[(s, m) in keep for s, m in zip(df["symbol"], df["market"])]]
        print(f"  watchlist filter: {len(df):,} of {before:,} panel names matched "
              f"({len(wl):,} watchlist rows)\n")

    df = assign_bands(df).sort_values("close_usd", ascending=False,
                                      na_position="last")

    print("  PANEL COVERAGE (native currency — these columns are NOT comparable)")
    cov = (df.groupby("market")
             .agg(names=("symbol", "count"), last_bar=("bar_date", "max"),
                  ladder=("ladder", "first"),
                  p25=("close_ladder", lambda s: s.quantile(.25)),
                  median=("close_ladder", "median"),
                  p90=("close_ladder", lambda s: s.quantile(.90)))
             .sort_values("names", ascending=False))
    cov["last_bar"] = pd.to_datetime(cov["last_bar"]).dt.date
    print(cov.round(2).to_string())

    n_nofx = int(df["close_usd"].isna().sum())
    if n_nofx:
        miss = sorted(df.loc[df["close_usd"].isna(), "ccy"].unique())
        print(f"\n  🔴 {n_nofx} name(s) unconverted — no FX rate for: {', '.join(miss)}")

    # Suspect quotes: reported, not dropped. Silently binning a ¥1.6e10 print in
    # the top band would rank a broken series as the priciest share on earth.
    med = df.groupby("market")["close_usd"].transform("median")
    susp = df[df["close_usd"] > med * OUTLIER_X].sort_values("close_usd", ascending=False)
    if len(susp):
        print(f"\n  ⚠️  {len(susp)} quote(s) >{OUTLIER_X:.0f}x their market median — "
              f"verify before treating as prices:")
        print(susp.head(8)[["symbol", "market", "ccy", "close_ccy", "close_usd"]]
              .to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    print("\n  PRICE BANDS — each market on its own ladder (rung 1 = cheapest)")
    print(band_table(df).to_string())

    cols = ["symbol", "market", "ccy", "close_ccy", "close_usd", "band", "bar_date"]
    show = df.dropna(subset=["close_usd"])[cols].copy()
    show["bar_date"] = pd.to_datetime(show["bar_date"]).dt.date
    print(f"\n  MOST EXPENSIVE {a.top} (cross-market, USD-normalised)")
    print(show.head(a.top).round(2).to_string(index=False))
    print(f"\n  CHEAPEST {a.top} (cross-market, USD-normalised)")
    print(show.tail(a.top).round(4).to_string(index=False))

    print(f"\n  {_pb.CAVEAT}")

    if a.csv:
        out = Path(a.csv)
        df[cols + ["close_ladder", "ladder"]].to_csv(out, index=False)
        print(f"\n  wrote {len(df):,} rows → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
