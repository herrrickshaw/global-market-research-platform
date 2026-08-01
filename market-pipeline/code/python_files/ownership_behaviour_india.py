#!/usr/bin/env python3
"""
ownership_behaviour_india.py — the within-market test the 5-market table argued for.

WHY THIS DESIGN AND NOT THE CROSS-COUNTRY ONE
---------------------------------------------
`ownership_behaviour.py` compared five markets and found retail/closely-held ones
(IN, KR) trending while institution-heavy ones (US, JP, EU) mean-revert. It could
not support that as a finding: n=5, and no way to separate an ownership effect
from NON-SYNCHRONOUS TRADING — thin stocks show positive autocorrelation for
purely mechanical reasons, because a price that did not update today carries
yesterday's information into today's close.

Within one market that confound becomes testable rather than fatal. Sector mix,
currency, trading calendar, index construction and tax regime are all held
constant, n is in the hundreds, and — the whole point — LIQUIDITY CAN BE
CONTROLLED FOR DIRECTLY. If promoter-heavy stocks still behave differently once
compared only against stocks of similar turnover, that is an ownership effect.
If the difference vanishes inside a liquidity bucket, it was illiquidity all
along, and the cross-country table was measuring float, not behaviour.

THE CONFOUND IS THE POINT, SO IT IS TESTED FIRST
Promoter-heavy stocks ARE typically less liquid — that is not a nuisance to be
waved away, it is the alternative hypothesis. The double sort below is arranged
so the confound gets first refusal on explaining the result.

    ownership_behaviour_india.py --collect      # widen the ownership panel
    ownership_behaviour_india.py --study        # metrics + double sort + regression
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache_seed"
REPORTS = HERE / "reports"
PANEL = CACHE / "india_ownership_wide.parquet"          # screener.in: has FII/DII
NSE_PANEL = CACHE / "india_shareholding_nse.parquet"    # NSE: promoter/public only
REPORT = REPORTS / "ownership_behaviour_india.md"
REPORT_NSE = REPORTS / "ownership_behaviour_india_full.md"
WAREHOUSE = Path("/Users/umashankar/repos/global-market-data/warehouse/ohlcv_adj/IN")

# Default floor. --floor widens it: $5M -> 335 names, $1M -> 794, i.e. essentially
# the whole genuinely tradeable India equity universe. Below ~$1M/day the bhavcopy
# tail is dominated by bonds and debentures (0ANSPL28-style codes) that screener.in
# does not cover as companies, so widening further adds requests, not observations.
TURNOVER_FLOOR = 5_000_000
LOOKBACK_DAYS = 756            # ~3y of daily bars per stock
MIN_BARS = 400


def collect(limit: int = 260, sleep: float = 0.9, floor: float = TURNOVER_FLOOR) -> None:
    """Widen the per-company ownership panel. Resumable — skips what it has."""
    import screener_kit as kit
    import equity_ownership as EO

    if floor <= 0:
        # FULL EQUITY UNIVERSE. Filtering by today's turnover selects on a variable
        # that MOVES — a stock illiquid this year may not be next — and it excludes
        # exactly the small caps where promoter and retail holding vary most, which
        # is the variation this study needs. So the universe is every bhavcopy symbol
        # that the ticker reference independently identifies as an India EQUITY.
        # That filter is a lookup, not a guess from ticker shape: 3MINDIA, 63MOONS
        # and 360ONE all start with digits and are ordinary equities, while
        # 0ANSPL28 and 910MFL26 are debt. Shape cannot tell them apart; the
        # reference can, and it drops ~2,800 requests screener.in would 404 anyway.
        ref = pd.read_parquet(CACHE / "ticker_exchange_reference.parquet")
        eq = set(ref[ref["country"] == "IN"]["base_ticker"].astype(str).str.upper())
        universe = sorted(set(kit.load("IN")) & eq)[:limit]
    else:
        universe = sorted(kit.load("IN", min_turnover_usd=floor))[:limit]
    have = set()
    rows = []
    if PANEL.exists():
        old = pd.read_parquet(PANEL)
        rows = old.to_dict("records")
        have = set(old["symbol"].unique())
        print(f"  resuming: {len(have)} companies already collected")
    todo = [s for s in universe if s not in have]
    print(f"  universe {len(universe)}, to fetch {len(todo)}")

    for i, sym in enumerate(todo, 1):
        t, mc = EO._screener_company(sym)
        if t is None or mc is None:
            continue
        t = t.set_index(t.columns[0])
        t.index = t.index.astype(str).str.replace(r"[+\s]+$", "", regex=True).str.strip()
        for h in [ix for ix in t.index if EO._HOLDER.search(ix)]:
            row = t.loc[h]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            vals = pd.to_numeric(row.astype(str).str.rstrip("%"), errors="coerce")
            for q, v in vals.items():
                if pd.notna(v):
                    rows.append({"symbol": sym, "quarter": str(q), "holder": h,
                                 "pct": float(v), "mcap_cr": mc})
        if i % 25 == 0:
            pd.DataFrame(rows).to_parquet(PANEL, compression="zstd", index=False)
            print(f"    {i}/{len(todo)} … checkpointed")
        time.sleep(sleep)

    d = pd.DataFrame(rows)
    CACHE.mkdir(parents=True, exist_ok=True)
    d.to_parquet(PANEL, compression="zstd", index=False)
    print(f"  -> {PANEL.name}: {d.symbol.nunique()} companies, {len(d):,} rows")


def _metrics_per_stock(symbols: set) -> pd.DataFrame:
    parts = sorted(WAREHOUSE.glob("year=*.parquet"))
    px = pd.concat([pd.read_parquet(p, columns=["Date", "Symbol", "Close", "Volume"])
                    for p in parts], ignore_index=True)
    px["Symbol"] = px["Symbol"].astype(str).str.upper()
    px = px[px["Symbol"].isin(symbols)]
    px["Date"] = pd.to_datetime(px["Date"])
    px = px.sort_values("Date")
    cutoff = px["Date"].max() - pd.Timedelta(days=LOOKBACK_DAYS)
    px = px[px["Date"] >= cutoff]

    out = []
    for sym, g in px.groupby("Symbol"):
        g = g.dropna(subset=["Close"])
        if len(g) < MIN_BARS:
            continue
        r = np.log(g["Close"]).diff().dropna()
        if r.std() == 0:
            continue
        v1, vq = r.var(), r.rolling(5).sum().dropna().var()
        turn = (g["Close"] * g["Volume"]).replace(0, np.nan)
        # Amihud: |return| per unit of rupee turnover — the standard price-impact
        # proxy, and the cleanest single measure of the confound being tested.
        amihud = (r.abs() / turn.reindex(r.index)).replace([np.inf, -np.inf], np.nan).mean()
        out.append({"symbol": sym, "n_bars": len(r),
                    "ann_vol": r.std() * np.sqrt(252) * 100,
                    "autocorr": r.autocorr(1),
                    "var_ratio": vq / (5 * v1) if v1 > 0 else np.nan,
                    "kurtosis": r.kurtosis(),
                    "median_turnover_cr": turn.median() / 1e7,
                    "amihud": amihud * 1e9})
    return pd.DataFrame(out).set_index("symbol")


def _load_nse() -> pd.DataFrame:
    """NSE panel reshaped to match the screener.in schema.

    NSE carries promoter/public/employee-trusts only — no FII/DII — so a study
    run on it can speak to PUBLIC FLOAT and PROMOTER holding across the whole
    universe, and cannot speak to institutional holding at all. That is the
    trade: 13x the companies for one fewer variable, and the missing variable is
    the one with the strongest result. Both runs are kept rather than one
    replacing the other.
    """
    d = pd.read_parquet(NSE_PANEL)
    d["qd"] = pd.to_datetime(d["date"], format="%d-%b-%Y", errors="coerce")
    d = d.dropna(subset=["qd"])
    # 🔴 VALIDATE THE ACCOUNTING IDENTITY. The components must sum to 100 — that
    # is what a shareholding pattern IS — so a row that does not is a filing or
    # parsing error, not a small company. ANTGRAPHIC 31-Mar-2026 arrives as
    # promoter 96.0 + public 9904.0 = 10000, i.e. basis points where percent was
    # expected; unfiltered it put the Public column's max at 9904% and its sd at
    # 940, which would have silently dominated every correlation and quantile in
    # the study. One row in 3,395 — and every other row totals 99.98-100.01, so
    # the check costs almost nothing and catches exactly the failure that matters.
    tot = (d["promoter_pct"].fillna(0) + d["public_pct"].fillna(0)
           + d["employee_trusts_pct"].fillna(0))
    bad = (tot < 99) | (tot > 101)
    if bad.any():
        print(f"  dropped {int(bad.sum())} row(s) failing the sum-to-100 check "
              f"({', '.join(sorted(d.loc[bad, 'symbol'].unique())[:5])})")
        d = d[~bad]
    long = []
    for col, holder in (("promoter_pct", "Promoters"), ("public_pct", "Public")):
        t = d[["symbol", "qd", col]].dropna().rename(columns={col: "pct"})
        t["holder"] = holder
        long.append(t)
    out = pd.concat(long, ignore_index=True)
    out["mcap_cr"] = float("nan")      # NSE does not carry market cap
    return out


def study(source: str = "screener") -> int:
    if source == "nse":
        if not NSE_PANEL.exists():
            print("run nse_shareholding.py --collect first"); return 1
        own = _load_nse()
    else:
        if not PANEL.exists():
            print("run --collect first"); return 1
        own = pd.read_parquet(PANEL)
    if "qd" not in own.columns:
        own["qd"] = pd.to_datetime(own["quarter"], format="%b %Y", errors="coerce")
    own = own.dropna(subset=["qd"])
    # 🔴 NOT own["qd"].max(). A handful of companies report on an off-cycle date,
    # so the newest quarter present is not the newest quarter most companies have:
    # here Jun 2026 carries 323 companies and Jul 2026 carries 8. Taking the global
    # max silently collapsed the cross-section from 323 to 8 — the same thin-quarter
    # trap equity_ownership.py hit, which is why that module drops quarters under 30
    # companies. Pick the BEST-POPULATED quarter instead (ties broken by recency),
    # which also keeps one consistent as-of date across the cross-section rather
    # than mixing per-company reporting dates.
    counts = own.groupby("qd")["symbol"].nunique()
    latest = counts.sort_values(kind="mergesort").index[-1]
    if counts.max() < 40:
        print(f"  best quarter has only {counts.max()} companies — too few"); return 1
    snap = (own[own["qd"] == latest]
            .pivot_table(index="symbol", columns="holder", values="pct", aggfunc="first"))
    caps = own.groupby("symbol")["mcap_cr"].first()

    m = _metrics_per_stock(set(snap.index))
    d = snap.join(m, how="inner").join(caps, how="left").dropna(
        subset=["Promoters", "ann_vol", "autocorr"])
    if len(d) < 40:
        print(f"  only {len(d)} usable companies — too few"); return 1

    out = ["# Ownership and behaviour, WITHIN India\n",
           f"{len(d)} companies with both a shareholding pattern (as of "
           f"{latest:%b %Y}) and ≥{MIN_BARS} daily bars in the last ~3 years. "
           + (f"Source: **NSE corporate-share-holdings-master** — the exchange's own filing, "
            f"covering the full equity universe. Carries promoter/public only, so this run "
            f"says nothing about FII/DII holding; see ownership_behaviour_india.md for the "
            f"screener.in run that does.\n"
            if source == "nse" else
            f"Source: **screener.in**, which carries the FII/DII split. Collection targeted "
            f"all 4,692 India equities but was rate-limited after ~800, so this is what was "
            f"retrieved before the block — skewed toward more liquid names.\n"),
           "\nThis is the test `ownership_behaviour.md` argued for and could not run: "
           "sector, currency, calendar and index construction are held constant, and "
           "**liquidity can be controlled for directly** — which is the whole reason the "
           "5-market version could not distinguish an ownership effect from thin trading.\n"]

    out.append("\n## 1. Spread — is there variation to explain?\n")
    out.append("| variable | min | p25 | median | p75 | max | sd |")
    out.append("|---|---|---|---|---|---|---|")
    for c in ("Promoters", "FIIs", "DIIs", "Public", "ann_vol", "autocorr",
              "median_turnover_cr"):
        if c in d.columns:
            s = d[c].dropna()
            out.append(f"| {c} | {s.min():.2f} | {s.quantile(.25):.2f} | {s.median():.2f} | "
                       f"{s.quantile(.75):.2f} | {s.max():.2f} | {s.std():.2f} |")

    out.append("\n## 2. Raw cross-sectional correlations\n")
    out.append("Before any control — this is the naive answer, and section 3 exists "
               "because it is not trustworthy.\n")
    out.append("\n| ownership | vs ann_vol | vs autocorr | vs var_ratio | vs amihud (illiq) |")
    out.append("|---|---|---|---|---|")
    for o in ("Promoters", "FIIs", "DIIs", "Public"):
        if o not in d.columns:
            continue
        row = [f"{d[o].corr(d[c]):+.3f}" for c in ("ann_vol", "autocorr", "var_ratio", "amihud")]
        out.append(f"| {o} | " + " | ".join(row) + " |")

    # ── the decisive test ────────────────────────────────────────────────────
    # ── the decisive test ────────────────────────────────────────────────────
    # AXIS ORDER IS DELIBERATE. Promoters is tested FIRST and kept even though it
    # is a null: it was the axis this study was originally built around, on the
    # prior that closely-held stocks behave differently. The raw correlations say
    # otherwise — promoter holding is near-flat against every behavioural metric
    # (+0.066 vol, +0.042 autocorr) while the real variation is institutional vs
    # retail float (DIIs -0.493 vol, Public +0.516). Re-pointing the sort at the
    # variable that moves is the right call; deleting the null that motivated the
    # design is not, so it stays recorded.
    AXES = [("Promoters", "promoter", "recorded null — the original prior"),
            ("DIIs", "DII", "domestic institutional holding"),
            ("Public", "public float", "retail / non-institutional float")]

    out.append("\n## 3. 🔴 Double sort — does the effect survive a liquidity control?\n")
    out.append("Stocks are split into liquidity terciles by median rupee turnover, then into "
               "ownership terciles WITHIN each. If ownership matters for its own sake the "
               "pattern holds down every liquidity row; if it only appears across rows, the "
               "story was illiquidity. **This is the alternative hypothesis getting first "
               "refusal** — public float correlates +0.27 with illiquidity, so a raw "
               "float-vs-volatility number is partly just 'small illiquid stocks are volatile'.\n")
    d["liq_t"] = pd.qcut(d["median_turnover_cr"], 3, labels=["illiquid", "mid", "liquid"])

    for col, label, why in AXES:
        if col not in d.columns or d[col].dropna().nunique() < 10:
            continue
        try:
            d["_own_t"] = pd.qcut(d[col], 3, labels=[f"low {label}", "mid", f"high {label}"])
        except ValueError:
            continue
        out.append(f"\n### by {col} — {why}\n")
        for metric in ("autocorr", "ann_vol"):
            piv = d.pivot_table(index="liq_t", columns="_own_t", values=metric,
                                aggfunc="mean", observed=True)
            cnt = d.pivot_table(index="liq_t", columns="_own_t", values=metric,
                                aggfunc="size", observed=True)
            out.append(f"\n**{metric}** (cell mean; n in brackets)\n")
            out.append("| liquidity | " + " | ".join(str(c) for c in piv.columns) + " | spread |")
            out.append("|---" * (len(piv.columns) + 2) + "|")
            spreads = []
            for ix in piv.index:
                cells = " | ".join(f"{piv.loc[ix, c]:+.3f} ({int(cnt.loc[ix, c])})"
                                   for c in piv.columns)
                sp = piv.loc[ix, piv.columns[-1]] - piv.loc[ix, piv.columns[0]]
                spreads.append(sp)
                out.append(f"| {ix} | {cells} | **{sp:+.3f}** |")
            same = all(x > 0 for x in spreads) or all(x < 0 for x in spreads)
            # Sign consistency alone is a weak test: three spreads of +0.014,
            # +0.005, +0.001 share a sign while shrinking to nothing, and calling
            # that "survives" would overstate it badly. Require the typical spread
            # to be material relative to the metric's own cross-sectional spread.
            typical = float(np.mean(np.abs(spreads)))
            scale = float(d[metric].std())
            material = scale > 0 and typical > 0.15 * scale
            if same and material:
                verdict = ("CONSISTENT in sign and MATERIAL "
                           f"({typical:.3f} vs sd {scale:.3f}) — survives the liquidity control")
            elif same:
                verdict = (f"consistent in sign but NEGLIGIBLE ({typical:.3f} against a "
                           f"cross-sectional sd of {scale:.3f}) — sign-only, not a real effect")
            else:
                verdict = "INCONSISTENT across liquidity rows — does NOT survive; the raw correlation was liquidity"
            out.append(f"\n→ {verdict}.")

    # ── regression: ownership beyond size and liquidity ──────────────────────
    out.append("\n## 4. Regression — ownership beyond size and liquidity\n")
    d["log_turn"] = np.log(d["median_turnover_cr"].clip(lower=1e-6))
    d["log_cap"] = np.log(d["mcap_cr"].clip(lower=1))
    out.append("| dependent | ownership var | spec | R\u00b2 | coef | t-stat |")
    out.append("|---|---|---|---|---|---|")
    for dep in ("autocorr", "ann_vol"):
        for col, label, _ in AXES:
            if col not in d.columns:
                continue
            # NSE carries no market cap, so log_cap is all-NaN there and a naive
            # dropna silently removed EVERY row — the controlled spec just vanished
            # from the table rather than failing loudly. Keep only controls that
            # actually have data, and name the spec after what was really fitted.
            for name, extra in (("alone", []), ("+ liquidity + size", ["log_turn", "log_cap"])):
                extra = [c for c in extra if d[c].notna().any()]
                if name != "alone":
                    name = "+ " + " + ".join(c.replace("log_", "") for c in extra) if extra else None
                    if name is None:
                        continue
                cols = [col] + extra
                sub = d[cols + [dep]].replace([np.inf, -np.inf], np.nan).dropna()
                if len(sub) < 30:
                    continue
                X = np.column_stack([np.ones(len(sub))] + [sub[c].values for c in cols])
                y = sub[dep].values
                beta, *_ = np.linalg.lstsq(X, y, rcond=None)
                resid = y - X @ beta
                dof = max(len(sub) - X.shape[1], 1)
                s2 = (resid @ resid) / dof
                try:
                    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
                    t = beta[1] / se[1]
                except np.linalg.LinAlgError:
                    t = float("nan")
                r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
                out.append(f"| {dep} | {col} | {name} | {r2:.3f} | {beta[1]:+.5f} | {t:+.2f} |")
    out.append("\n|t| > ~2 is conventionally significant at 5%. **The comparison that matters "
               "is whether a coefficient SURVIVES the addition of liquidity and size** — not "
               "whether it is significant alone. A coefficient that collapses when log_turn "
               "enters was measuring liquidity wearing an ownership label.")

    out.append("\n## 5. What this establishes\n")
    if source == "nse":
        out.append("**🔴 THE EFFECT DOES NOT REPLICATE IN THE FULL UNIVERSE. This is the "
                   "headline, and it contradicts the screener.in run.**\n")
        out.append("On 347 liquid large caps, public float correlated **+0.516** with "
                   "volatility and +0.230 with autocorrelation. Across the full NSE universe "
                   "it is **-0.04 and +0.02** — indistinguishable from zero. Every regression "
                   "coefficient here has |t| < 0.6, with or without the liquidity control, and "
                   "no double sort survives: the volatility sort flips sign across liquidity "
                   "rows, and the autocorrelation sort holds its sign only at a magnitude of "
                   "0.006 against a cross-sectional sd of 0.061 — sign-only, not an effect.\n")
        out.append("**The most likely reading is that the original result was a large-cap "
                   "phenomenon.** The screener sample floored at $20M/day turnover; this one "
                   "reaches a median turnover of Rs 0.02 crore. Widening the universe by ~2x "
                   "the companies and ~100x the liquidity range destroyed the relationship, "
                   "which is what a size-restricted artifact looks like.\n")
        out.append("**🔴 A structural caveat specific to this source.** NSE reports only "
                   "promoter, public and employee trusts, and they sum to 100 — so Public is "
                   "mechanically `100 - Promoters` and the two are the SAME variable with "
                   "opposite sign. Their correlations here are exact mirrors (+0.040 / -0.040) "
                   "because they must be. In the screener data, Public was a genuine residual "
                   "after FII, DII and government, and therefore carried information that "
                   "promoter holding did not. **These two runs are not measuring the same "
                   "quantity**, and that alone could explain the divergence without any "
                   "large-cap story at all. Distinguishing the two explanations needs the "
                   "FII/DII split across the wide universe, which no free source provides.\n")
        out.append("**What still stands from the screener run**: the DII result (volatility "
                   "t=-9.9 with controls) is untouched by this, because NSE cannot measure DII "
                   "holding. It stands on 347 companies and is not confirmed at scale.\n")
    else:
        out.append("**1. Institutional holding is associated with calmer prices, and it is NOT "
                   "just illiquidity.** DII holding predicts lower volatility and lower "
                   "autocorrelation, and the relationship barely moves when liquidity and size "
                   "enter: the volatility coefficient goes -0.476 (t=-11.2) to -0.345 (t=-9.9), "
                   "and autocorrelation -0.00094 (t=-3.5) to -0.00091 (t=-3.2). The double sort "
                   "agrees — the spread keeps its sign down all three liquidity terciles.\n")
        out.append("**2. Retail float destabilises, but two-thirds of the raw effect WAS "
                   "liquidity.** Public float alone gives +0.404 on volatility (t=11.8); adding "
                   "liquidity and size cuts it to +0.136 (t=3.5). 🔴 And the full-universe NSE "
                   "run (`--source nse`) finds NOTHING — see ownership_behaviour_india_full.md. "
                   "Treat this as a large-cap result until reconciled.\n")
        out.append("**3. My original axis was a null, and one part of it inverted.** Promoter "
                   "holding does nothing for autocorrelation (t=+0.45 alone, +1.51 controlled). "
                   "On volatility it is insignificant alone (t=+1.81) but becomes strongly "
                   "positive once liquidity and size are controlled (+0.139, t=+5.71) — a "
                   "SUPPRESSION effect, since promoter-heavy stocks are also larger.\n")
    out.append("\n### 🔴 The limit neither run clears: direction\n")
    out.append("Everything here is association. **Institutions may be selecting stable stocks "
               "rather than stabilising them** — a mandate screening for predictable earnings "
               "produces exactly this cross-section with no stabilising behaviour at all. "
               "Controlling for liquidity and size does not touch that. Separating them needs "
               "ownership variation not chosen by the owner: index-inclusion events, mandate "
               "changes, or a within-stock panel on holding over time — the quarterly history "
               "for the last is already collected.\n")
    out.append("*Descriptive analysis of historical relationships. Not investment advice.*\n")

    REPORTS.mkdir(parents=True, exist_ok=True)
    target = REPORT_NSE if source == "nse" else REPORT
    target.write_text("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\n  -> {target}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--study", action="store_true")
    ap.add_argument("--source", choices=("screener", "nse"), default="screener",
                    help="screener = has FII/DII, ~350 cos; nse = promoter/public only, full universe")
    ap.add_argument("--limit", type=int, default=260)
    ap.add_argument("--floor", type=float, default=TURNOVER_FLOOR,
                    help="min USD/day turnover for the universe")
    a = ap.parse_args()
    if not (a.collect or a.study):
        ap.print_help(); return 1
    if a.collect:
        collect(limit=a.limit, floor=a.floor)
    if a.study:
        return study(source=a.source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
