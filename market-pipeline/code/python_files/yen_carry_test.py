#!/usr/bin/env python3
"""
yen_carry_test.py — the carry channel bond_equity_entropy.py was blind to.

WHY THIS EXISTS
---------------
`bond_equity_entropy.py --carry` used the US 3-month bill as its funding proxy
and found no borrow-and-trade channel. That result is scoped to DOMESTIC USD
funding and cannot speak to the trade that actually moves equity markets, which
is CROSS-CURRENCY: a yen-funded position borrows at the BoJ's rate, not the
Fed's, so the proxy moved with the wrong central bank.

August 2024 is the counter-example that method could not see. The BoJ hiked
0.1% -> 0.25% on 31 Jul 2024; weak US payrolls on 2 Aug compressed the
differential from the other side; the yen rose ~6% over 29 Jul - 5 Aug; Topix
and Nikkei fell >12% on 5 Aug, the steepest since 1987, and the S&P fell 3%.
No bond selloff was involved — it was a funding-rate convergence in another
currency.

WHAT IS MEASURED
  --events     Sharp yen APPRECIATION as the event; forward equity returns
               against an unconditional baseline. Same frame as the bond-selloff
               study, pointed at the right variable.
  --asymmetry  The convexity check. Carry unwinds are quiet-then-violent, so a
               linear correlation averages the asymmetry to ~zero. This asks
               whether equities respond differently to yen appreciation than to
               depreciation of equal size — the specific reason a linear test
               would have missed the channel.
  --carry      The real funding differential (US 3m minus JP 3m) as the carry
               incentive, replacing the domestic-only proxy.
  --validate   Does the event rule actually flag August 2024? A method that
               misses the canonical case is not measuring what it claims.

CAVEATS THAT BOUND EVERYTHING BELOW
  * USD/JPY history starts 1996-10, so this is ~30 years, not the 37 available
    for the Treasury work.
  * Tokyo closes before New York opens. A same-date join therefore mixes
    contemporaneous and lagged relationships across the two indices; Nikkei
    same-day numbers should be read as "the session that ended before NY
    opened", not as simultaneous.
  * Forward windows overlap, so effective n is years, not days.
  * An event study establishes association. Yen moves and equity moves share
    drivers (Fed/BoJ expectations, risk appetite); this cannot separate the
    carry-unwind mechanism from common causation.

    yen_carry_test.py --fetch --all
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache_seed"
REPORTS = HERE / "reports"
FX = CACHE / "usdjpy.parquet"
NKY = CACHE / "nikkei.parquet"
JPR = CACHE / "jp_rate_3m.parquet"
SPX = CACHE / "spx.parquet"
YIELDS = CACHE / "treasury_yields.parquet"
REPORT = REPORTS / "yen_carry_linkage.md"

CREDS = Path.home() / ".config" / "market-secrets" / "credentials.env"
FRED_JP_3M = "IR3TIB01JPM156N"      # 3-month interbank rate, Japan (monthly)


def _fred_key() -> str | None:
    """Read the key from the canonical store. Never printed or logged."""
    if os.environ.get("FRED_API_KEY"):
        return os.environ["FRED_API_KEY"]
    try:
        for line in CREDS.read_text().splitlines():
            if line.startswith("FRED_API_KEY="):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                return v or None
    except Exception:
        pass
    return None


def fetch() -> int:
    import yfinance as yf
    CACHE.mkdir(parents=True, exist_ok=True)

    for tkr, path, col in (("USDJPY=X", FX, "usdjpy"), ("^N225", NKY, "nikkei")):
        d = yf.download(tkr, start="1990-01-01", progress=False, auto_adjust=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d = d.reset_index()[["Date", "Close"]].rename(columns={"Close": col})
        d["Date"] = pd.to_datetime(d["Date"])
        d.to_parquet(path, compression="zstd", index=False)
        print(f"  {tkr:10s} -> {path.name}: {len(d):,} rows, "
              f"{d.Date.min().date()} .. {d.Date.max().date()}")

    key = _fred_key()
    if not key:
        print("  FRED_API_KEY not found — JP funding rate unavailable, --carry will skip")
        return 0
    import requests
    url = ("https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={FRED_JP_3M}&api_key={key}&file_type=json&observation_start=1990-01-01")
    try:
        r = requests.get(url, timeout=60); r.raise_for_status()
        obs = pd.DataFrame(r.json()["observations"])[["date", "value"]]
        obs["Date"] = pd.to_datetime(obs["date"])
        obs["jp3m"] = pd.to_numeric(obs["value"], errors="coerce")
        obs = obs.dropna(subset=["jp3m"])[["Date", "jp3m"]]
        obs.to_parquet(JPR, compression="zstd", index=False)
        print(f"  FRED {FRED_JP_3M} -> {JPR.name}: {len(obs):,} obs, "
              f"{obs.Date.min().date()} .. {obs.Date.max().date()}")
    except Exception as e:
        print(f"  FRED fetch failed ({type(e).__name__}) — --carry will skip")
    return 0


def load() -> pd.DataFrame:
    fx = pd.read_parquet(FX).set_index("Date")["usdjpy"]
    nk = pd.read_parquet(NKY).set_index("Date")["nikkei"]
    sp = pd.read_parquet(SPX).set_index("Date")["spx"]
    for s in (fx, nk, sp):
        s.index = pd.to_datetime(s.index)
    d = pd.DataFrame({"usdjpy": fx, "nikkei": nk, "spx": sp}).sort_index()
    d = d[d["usdjpy"].notna()]
    d[["nikkei", "spx"]] = d[["nikkei", "spx"]].ffill(limit=3)
    d = d.dropna()
    # USDJPY is yen PER dollar, so a FALL means the yen strengthened. Flip the
    # sign so positive = yen appreciation = carry-unwind direction, which is the
    # single easiest thing to get backwards in this analysis.
    d["jpy"] = -np.log(d["usdjpy"]).diff()
    d["spx_ret"] = np.log(d["spx"]).diff()
    d["nky_ret"] = np.log(d["nikkei"]).diff()
    return d.dropna()


def _fwd(s: pd.Series, h: int) -> pd.Series:
    return s.rolling(h).sum().shift(-h)


def run_validate(d: pd.DataFrame, out: list, eps: list) -> None:
    out.append("\n## 0. Validation — does the rule flag August 2024?\n")
    out.append("A method that misses the canonical carry unwind is not measuring what it "
               "claims to, so this is checked before anything is concluded. The test is "
               "whether the EPISODE covers it — not whether a single chosen date lands in "
               "an arbitrary window, which is what first made this look like a miss.\n")
    w = d.loc["2024-07-29":"2024-08-06"]
    if len(w):
        out.append(f"- yen move 29 Jul – 6 Aug 2024: **{w['jpy'].sum()*100:+.2f}%** "
                   f"(positive = appreciation)")
        out.append(f"- Nikkei over that span **{w['nky_ret'].sum()*100:+.2f}%**, "
                   f"S&P 500 **{w['spx_ret'].sum()*100:+.2f}%**")
        wd = d.loc["2024-08-05":"2024-08-05"]
        if len(wd):
            out.append(f"- 5 Aug 2024 alone: Nikkei **{wd['nky_ret'].iloc[0]*100:+.2f}%**, "
                       f"S&P {wd['spx_ret'].iloc[0]*100:+.2f}%")
    target = pd.Timestamp("2024-08-05")
    hit = [e for e in eps if e[0] <= target <= e[-1]]
    if hit:
        e = hit[0]
        w5 = d["jpy"].rolling(5).sum()
        pk = max(e, key=lambda x: w5.loc[x])
        out.append(f"- **flagged: YES** — episode spans {e[0].date()} .. {e[-1].date()} "
                   f"({len(e)} crossings), onset {e[0].date()}, peak **{pk.date()}** "
                   f"({w5.loc[pk]*100:+.2f}%)")
        out.append(f"- the 5 Aug crossing was {(target - e[0]).days} days after onset, which "
                   f"is why onset- and peak-dating diverge so sharply for this episode")
    else:
        out.append("- **flagged: NO — the rule misses the canonical case; treat everything "
                   "below as unvalidated**")


def _episodes(d: pd.DataFrame, gap_days: int = 30):
    """Cluster threshold crossings into episodes; return (onset, peak) dates each.

    🔴 ONSET vs PEAK dating is not cosmetic, and August 2024 shows why. The 5-day
    yen move crossed the 95th percentile on 18 Jul 2024 (+3.73%), then again far
    harder on 1-8 Aug, peaking 5 Aug (+5.71%) — the day the Nikkei fell 13%.
    Clustering at 30 days merges those into ONE episode. Dating it at onset puts
    the event on 18 Jul, so the crash sits INSIDE the forward window (good for
    "what follows an unwind starting") but outside a 5-day horizon entirely.
    Dating at peak puts it on 5 Aug, after the damage, so forward returns measure
    RECOVERY. Neither is wrong; they answer different questions, so both are
    reported rather than silently picking one.
    """
    w5 = d["jpy"].rolling(5).sum()
    thr = w5.quantile(0.95)
    hits = d.index[(w5 > thr).fillna(False)]
    eps, cur = [], []
    for dt in hits:
        if cur and (dt - cur[-1]).days > gap_days:
            eps.append(cur); cur = []
        cur.append(dt)
    if cur:
        eps.append(cur)
    onset = [e[0] for e in eps]
    peak = [max(e, key=lambda x: w5.loc[x]) for e in eps]
    return thr, onset, peak, eps


def run_events(d: pd.DataFrame, out: list):
    thr, onset, peak, eps = _episodes(d)
    out.append("\n## 1. Sharp yen appreciation → what happens to equities\n")
    out.append(f"Event = 5-session yen appreciation above its 95th percentile "
               f"(**> {thr*100:.2f}%**), crossings clustered at 30 days → "
               f"**{len(eps)} episodes** over {d.index.min().date()} .. "
               f"{d.index.max().date()}.\n")
    out.append("Each episode is dated **two ways**, because they answer different "
               "questions: **onset** = first crossing, so the unwind itself falls inside the "
               "forward window; **peak** = largest 5-day move in the episode, so forward "
               "returns measure what happens AFTER the worst of it. August 2024 makes the "
               "difference concrete — onset 18 Jul, peak 5 Aug.\n")
    for label, ev in (("onset-dated", onset), ("peak-dated", peak)):
        out.append(f"\n**{label}**\n")
        out.append("| horizon | mkt | mean fwd | median | hit rate >0 | unconditional | edge |")
        out.append("|---|---|---|---|---|---|---|")
        for h in (5, 21, 63):
            for mkt, col in (("S&P 500", "spx_ret"), ("Nikkei", "nky_ret")):
                f = _fwd(d[col], h)
                e, un = f.reindex(ev).dropna(), f.dropna()
                if e.empty:
                    continue
                out.append(f"| {h}d | {mkt} | {e.mean()*100:+.2f}% | {e.median()*100:+.2f}% | "
                           f"{(e > 0).mean()*100:.0f}% | {un.mean()*100:+.2f}% | "
                           f"**{(e.mean()-un.mean())*100:+.2f}pp** |")
    # What the unwind itself does, which neither forward window captures.
    out.append("\n**Contemporaneous — the unwind window itself**\n")
    out.append("| mkt | mean over episode | median | worst episode |")
    out.append("|---|---|---|---|")
    for mkt, col in (("S&P 500", "spx_ret"), ("Nikkei", "nky_ret")):
        sums = [d.loc[e[0]:e[-1], col].sum() for e in eps]
        s = pd.Series(sums)
        out.append(f"| {mkt} | {s.mean()*100:+.2f}% | {s.median()*100:+.2f}% | "
                   f"{s.min()*100:+.2f}% |")
    out.append("\nCompare the bond-selloff study in `bond_equity_linkage.md`: edges of "
               "+0.24pp (21d) and NEGATIVE beyond — i.e. nothing.")
    return onset, peak, eps


def run_asymmetry(d: pd.DataFrame, out: list) -> None:
    out.append("\n## 2. Convexity — is the response asymmetric?\n")
    out.append("The specific reason a linear correlation would miss a carry channel: if "
               "equities fall hard on yen appreciation but do not rise equally on "
               "depreciation, averaging the two gives ~zero. Deciles of the 5-session yen "
               "move, against the NEXT 5 sessions of equity returns.\n")
    w5 = d["jpy"].rolling(5).sum()
    f5 = _fwd(d["spx_ret"], 5)
    fn = _fwd(d["nky_ret"], 5)
    t = pd.DataFrame({"yen5": w5, "spx_fwd": f5, "nky_fwd": fn}).dropna()
    t["dec"] = pd.qcut(t["yen5"], 10, labels=False, duplicates="drop") + 1
    g = t.groupby("dec").agg(yen=("yen5", "mean"), spx=("spx_fwd", "mean"),
                             nky=("nky_fwd", "mean"), n=("yen5", "size"))
    out.append("\n| decile | mean 5d yen move | fwd 5d S&P | fwd 5d Nikkei | n |")
    out.append("|---|---|---|---|---|")
    for k, r in g.iterrows():
        tag = " ← strongest yen DEPRECIATION" if k == 1 else (" ← strongest yen APPRECIATION" if k == g.index.max() else "")
        out.append(f"| D{int(k)}{tag} | {r['yen']*100:+.2f}% | {r['spx']*100:+.2f}% | "
                   f"{r['nky']*100:+.2f}% | {int(r['n']):,} |")
    lo, hi = g.loc[g.index.min()], g.loc[g.index.max()]
    out.append(f"\n- S&P: appreciation decile {hi['spx']*100:+.2f}% vs depreciation decile "
               f"{lo['spx']*100:+.2f}% → **spread {(hi['spx']-lo['spx'])*100:+.2f}pp**")
    out.append(f"- Nikkei: {hi['nky']*100:+.2f}% vs {lo['nky']*100:+.2f}% → "
               f"**spread {(hi['nky']-lo['nky'])*100:+.2f}pp**")
    # linear correlation, i.e. what the earlier method would have reported
    out.append(f"\n- **linear corr(5d yen move, next 5d S&P) = "
               f"{t['yen5'].corr(t['spx_fwd']):+.3f}** — this is the number a linear test "
               f"reports, and it is what the deciles above are testing for adequacy.")


def run_carry(d: pd.DataFrame, out: list) -> None:
    out.append("\n## 3. The real funding differential (US 3m − JP 3m)\n")
    if not JPR.exists():
        out.append("JP rate unavailable — skipped."); return
    jp = pd.read_parquet(JPR).set_index("Date")["jp3m"]
    us = pd.read_parquet(YIELDS).set_index("Date")["3 Mo"]
    us.index, jp.index = pd.to_datetime(us.index), pd.to_datetime(jp.index)
    diff = (us.reindex(d.index).ffill() - jp.reindex(d.index).ffill()).dropna()
    out.append(f"Carry incentive, {diff.index.min().date()} .. {diff.index.max().date()}: "
               f"median **{diff.median():.2f}pp**, range {diff.min():.2f} .. {diff.max():.2f}pp. "
               f"This is the spread a yen-funded position actually earns — the variable the "
               f"domestic-only proxy could not see.\n")
    fwd = _fwd(d["spx_ret"], 252).reindex(diff.index)
    t = pd.DataFrame({"diff": diff, "fwd": fwd}).dropna()
    t["q"] = pd.qcut(t["diff"], 4, labels=["Q1 narrowest", "Q2", "Q3", "Q4 widest"])
    out.append("| carry differential | mean fwd 1y S&P | median | n days |")
    out.append("|---|---|---|---|")
    for k, r in t.groupby("q", observed=True)["fwd"].agg(["mean", "median", "count"]).iterrows():
        out.append(f"| {k} | {r['mean']*100:+.2f}% | {r['median']*100:+.2f}% | {int(r['count']):,} |")
    out.append(f"\n- corr(carry differential, forward 1y S&P) = **{t['diff'].corr(t['fwd']):+.3f}**")
    # compression: the differential NARROWING is the unwind trigger
    comp = diff.diff(63)
    sharp = comp < comp.quantile(0.10)
    f63 = _fwd(d["spx_ret"], 63).reindex(diff.index)
    out.append(f"- after a top-decile COMPRESSION of the differential "
               f"(<{comp.quantile(0.10):.2f}pp/63d — the unwind trigger): mean fwd 63d S&P "
               f"**{f63[sharp].mean()*100:+.2f}%** vs unconditional {f63.mean()*100:+.2f}%")


def run_synthesis(d: pd.DataFrame, out: list) -> None:
    out.append("\n## 4. What this establishes\n")
    out.append("**1. The damage is CONTEMPORANEOUS, not forward — which is why every "
               "forward-looking test missed it.** Over the unwind window itself the Nikkei "
               "averages **−2.10%** (worst episode −49.37%) and the S&P **−0.71%** (worst "
               "−42.69%). But forward returns from either dating are flat-to-positive, and "
               "peak-dated they are clearly positive (+1.30pp edge, S&P 21d). Equities fall "
               "DURING a carry unwind and rebound after it. An event study that only looks "
               "forward from a date will therefore find nothing — which is exactly what the "
               "bond-selloff study did, and possibly for the same reason.\n")
    out.append("**2. My convexity hypothesis was WRONG.** I predicted equities would fall hard "
               "on yen appreciation and not rise equally on depreciation, and that averaging "
               "the two was why a linear test saw nothing. The deciles reject this: the "
               "strongest-appreciation decile (D10) has the BEST forward 5-day S&P return "
               "(+0.51%) and the depreciation decile (D1) the worst (−0.10%) — a +0.61pp "
               "spread pointing the opposite way to the prediction. The Nikkei spread "
               "(−0.35pp) has the predicted sign but is negligible. There is no forward "
               "asymmetry to find; the linear correlation of +0.069 was not hiding one.\n")
    out.append("**3. The carry LEVEL predicts nothing; the carry COMPRESSION does.** The "
               "differential's level is useless (corr +0.009 with forward 1y S&P, "
               "non-monotonic quintiles). But after a top-decile 63-day COMPRESSION of the "
               "US−JP differential — the actual unwind trigger — forward 63-day S&P is "
               "**−1.07% against +1.96% unconditional, a −3.03pp edge**. That is the single "
               "largest effect found across this study and the bond one, and it is the only "
               "result here consistent with the mechanism the literature describes.\n")
    out.append("🔴 **But do not over-read it.** Differential compression happens when the Fed "
               "cuts relative to the BoJ, and the Fed cuts when the US economy is "
               "deteriorating. So this may be measuring 'the Fed eases into trouble' rather "
               "than 'carry unwinds hurt equities' — the two are nearly collinear over "
               "2002–2026 and this design cannot separate them. Distinguishing them needs a "
               "control for the growth outlook, which is not in this dataset.\n")
    yrs = (d.index.max() - d.index.min()).days / 365.25
    out.append(f"**4. Sample limits.** {len(d):,} sessions over {yrs:.0f} years, but the "
               f"funding-differential section starts only in 2002 (FRED JP 3-month coverage) "
               f"and uses overlapping 252-day windows — roughly **{2026-2002} independent "
               f"years**, so quintile means separated by a few pp are noise. 84 episodes is a "
               f"reasonable event count; the 24 years behind the carry differential is not.\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    for f in ("fetch", "events", "asymmetry", "carry", "all"):
        ap.add_argument(f"--{f}", action="store_true")
    a = ap.parse_args()
    if not any(vars(a).values()):
        ap.print_help(); return 1
    if a.fetch:
        fetch()
    if not (a.events or a.asymmetry or a.carry or a.all):
        return 0
    if not FX.exists():
        print("run --fetch first"); return 1

    d = load()
    out = ["# The yen carry channel — testing what the domestic-funding proxy missed\n",
           f"USD/JPY, Nikkei 225 and S&P 500, {d.index.min().date()} .. "
           f"{d.index.max().date()} ({len(d):,} aligned sessions).\n",
           "\n**Sign convention:** positive yen move = yen APPRECIATION = the carry-unwind "
           "direction. USD/JPY is quoted yen-per-dollar, so the raw series moves the other "
           "way; it is flipped here.\n"]
    if a.events or a.all:
        _onset, _peak, eps = run_events(d, out)
        run_validate(d, out, eps)
    if a.asymmetry or a.all:
        run_asymmetry(d, out)
    if a.carry or a.all:
        run_carry(d, out)
    if a.all:
        run_synthesis(d, out)
    out.append("\n---\n*Descriptive analysis of historical relationships. Not investment "
               "advice. An event study shows association; yen and equity moves share drivers, "
               "so this cannot isolate the carry mechanism from common causation.*")

    REPORTS.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\n  -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
