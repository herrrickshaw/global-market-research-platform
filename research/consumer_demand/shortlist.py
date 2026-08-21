#!/usr/bin/env python3
"""
One ranked shortlist of Amazon products worth selling.

Wires the two halves together: `nexscope_keyword_history` says whether demand
for a keyword is RISING, `amazon_demand_compare` says whether the category has
a slot free. Neither alone answers "what should I sell" — a rising term in a
category owned by three entrenched ASINs is not an opportunity, and an open
category nobody searches for is not either.

GATE FIRST, THEN RANK
---------------------
The pipeline does not blend everything into one number and sort. It applies
pass/fail gates, records WHY each rejection failed, and only then ranks the
survivors. Two reasons:

  * A blended score lets a strong growth number outvote a disqualifying review
    moat. Those are not commensurable — no amount of growth makes a category
    with 40,000-review incumbents enterable — so the moat is a gate, not a term.
  * Rejections are more informative than the shortlist. "Rising, but seasonal"
    and "open, but nobody searches for it" are different next actions, and a
    tool that silently drops both teaches you nothing.

THE SCORE IS RELATIVE TO THE CANDIDATE SET
------------------------------------------
Survivors are ranked on a weighted composite of min-max normalised components.
That makes the score comparative, not absolute: adding an eleventh candidate
changes the scores of the other ten, and a score of 0.9 means "best of what you
supplied", never "good in absolute terms". Component values are reported
alongside the total so the ranking can be argued with. Compare scores within a
run; do not compare them across runs.

NEITHER API IS REACHABLE FROM THE CLAUDE CODE SANDBOX — see the two modules
this composes. `--dry-run` exercises the whole pipeline on fixtures.

Usage:
    python3 research/consumer_demand/shortlist.py --dry-run
    export NEXSCOPE_API_KEY=... OPENWEB_NINJA_API_KEY=...
    python3 research/consumer_demand/shortlist.py --keywords "moringa oil,mouth tape"
    python3 research/consumer_demand/shortlist.py --keywords-file candidates.txt \
        --min-volume 1000 --max-review-moat 1500
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import amazon_demand_compare as comp  # noqa: E402
import nexscope_keyword_history as trend  # noqa: E402

# Weights for the survivor ranking. Growth leads because the whole point is to
# enter before saturation; openness is close behind because an unenterable
# category's growth is somebody else's. They sum to 1.0 — asserted at import.
WEIGHTS = {
    "growth": 0.35,     # trend slope — is demand rising
    "demand": 0.25,     # absolute volume — is the prize worth having
    "openness": 0.30,   # low moat, high demand-per-listing — can you get in
    "headroom": 0.10,   # price dispersion — is there room to position
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "WEIGHTS must sum to 1.0"

# Trend verdicts allowed through. "spiky" and "seasonal bounce" are excluded by
# default precisely because they are the two ways a rising-looking series lies.
DEFAULT_ALLOWED_FLAGS = ("RISING",)


def _minmax(values: list[float]) -> list[float]:
    """Scale to 0-1 across the candidate set. A constant column maps to 0.5
    rather than 0 or 1 — with no spread there is no evidence either way, and
    collapsing it to an extreme would silently hand that component's whole
    weight to every candidate or to none."""
    usable = [v for v in values if v is not None]
    if not usable:
        return [0.5] * len(values)
    lo, hi = min(usable), max(usable)
    if hi - lo < 1e-12:
        return [0.5] * len(values)
    return [0.5 if v is None else (v - lo) / (hi - lo) for v in values]


def gate(cand: dict, *, allowed_flags: tuple[str, ...], min_volume: float,
         min_observations: int, max_review_moat: float | None) -> list[str]:
    """-> list of failure reasons. Empty list means the candidate passes."""
    fails = []
    flag = cand.get("opportunity_flag")
    if flag not in allowed_flags:
        fails.append(f"trend is {flag!r}, not in {list(allowed_flags)}")
    if (cand.get("observations") or 0) < min_observations:
        fails.append(f"only {cand.get('observations')} observations "
                     f"(need {min_observations})")
    if (cand.get("latest_volume") or 0) < min_volume:
        fails.append(f"latest volume {cand.get('latest_volume')} below "
                     f"{min_volume:g}")
    moat = cand.get("review_moat")
    if max_review_moat is not None and moat is not None and moat > max_review_moat:
        fails.append(f"review moat {moat:,} above {max_review_moat:,.0f}")
    if cand.get("listings_sampled") in (None, 0):
        fails.append("no competition data")
    return fails


def score_candidates(cands: list[dict]) -> list[dict]:
    """Rank survivors. Mutates nothing; returns new dicts with score fields."""
    if not cands:
        return []

    growth = _minmax([c.get("growth_per_period_pct") for c in cands])
    # Demand on a log scale: the gap between 500 and 5,000 searches matters
    # far more than the gap between 50,000 and 54,500, and a linear scale
    # would let one huge term flatten every other candidate to ~0.
    demand = _minmax([math.log(c["latest_volume"]) if c.get("latest_volume") else None
                      for c in cands])
    # Openness combines a low moat with high demand per competing listing.
    moat_inv = _minmax([-c["review_moat"] if c.get("review_moat") is not None else None
                        for c in cands])
    dpl = _minmax([c.get("demand_per_listing") for c in cands])
    headroom = _minmax([c.get("price_dispersion") for c in cands])

    out = []
    for i, c in enumerate(cands):
        openness = (moat_inv[i] + dpl[i]) / 2
        parts = {"growth": growth[i], "demand": demand[i],
                 "openness": openness, "headroom": headroom[i]}
        total = sum(WEIGHTS[k] * v for k, v in parts.items())
        row = dict(c)
        row["score"] = round(total, 4)
        for k, v in parts.items():
            row[f"score_{k}"] = round(v, 3)
        out.append(row)

    out.sort(key=lambda r: -r["score"])
    for rank, row in enumerate(out, 1):
        row["rank"] = rank
    return out


def build_candidate(keyword: str, trend_summary: dict,
                    comp_summary: dict | None, comp_extra: dict | None) -> dict:
    """Flatten the two halves into one row, prefixing nothing — the column
    names are already distinct and a `trend_`/`comp_` prefix would only make
    the CSV harder to read."""
    row = {"keyword": keyword}
    row.update({k: v for k, v in trend_summary.items() if k != "keyword"})
    if comp_summary:
        for k in ("listings_sampled", "units_past_month_floor", "units_coverage_pct",
                  "est_monthly_revenue_floor", "median_price", "cumulative_ratings",
                  "demand_per_listing", "total_listings_on_primary_keyword"):
            row[k] = comp_summary.get(k)
    if comp_extra:
        row.update(comp_extra)
    return row


def collect(keyword: str, args, trend_key, comp_key) -> dict:
    """Trend first, competition second — and only if the trend passed.

    Ordering is deliberate: the competition call costs Jobs/search credits per
    listing returned, and roughly half of any candidate list dies on the trend
    gate. Paying for competition data on a keyword already disqualified for
    being seasonal is the most expensive way to learn nothing.
    """
    if args.dry_run:
        payload = trend.dry_run_payload(keyword)
    else:
        payload = trend.fetch(keyword, args.country, trend_key, args.endpoint,
                              args.auth_header, args.auth_prefix)
    points = trend.parse_series(payload, keyword)
    tsum = trend.summarise_keyword(keyword, points, args.window)
    tsum["opportunity_flag"] = trend.opportunity_flag(tsum)

    row = build_candidate(keyword, tsum, None, None)

    # Cheap pre-gate on the trend alone, before spending competition credits.
    pre = [f for f in gate(row, allowed_flags=tuple(args.allowed_flags),
                           min_volume=args.min_volume,
                           min_observations=args.min_observations,
                           max_review_moat=None)
           if "competition" not in f]
    if pre and not args.price_all:
        row["gate_failures"] = "; ".join(pre)
        row["priced_competition"] = False
        return row

    rows, breadth = comp.collect_group(
        keyword, [keyword], args.country, args.pages, comp_key, args.sleep,
        args.dry_run, args.from_cache, not args.no_cache,
    )
    if rows:
        csum = comp.summarise_group(keyword, rows, breadth)
        extra = comp.competition_metrics(rows)
        row = build_candidate(keyword, tsum, csum, extra)
    row["priced_competition"] = bool(rows)
    return row


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(rows)


def write_markdown(path: Path, shortlist: list[dict], rejected: list[dict],
                   country: str, args) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    md = [
        "# Amazon product shortlist",
        "",
        f"Marketplace: **{country}** · {len(shortlist)} of "
        f"{len(shortlist) + len(rejected)} candidates passed the gates.",
        "",
        f"Gates: trend in {list(args.allowed_flags)} · latest volume ≥ "
        f"{args.min_volume:g} · ≥ {args.min_observations} observations · "
        f"review moat ≤ {args.max_review_moat:,.0f}",
        "",
        "## Shortlist",
        "",
    ]
    if shortlist:
        cols = ["rank", "keyword", "score", "latest_volume", "growth_per_period_pct",
                "momentum_pct", "yoy_pct", "review_moat", "demand_per_listing",
                "price_dispersion", "median_price"]
        md += ["| " + " | ".join(cols) + " |",
               "| " + " | ".join("---" for _ in cols) + " |"]
        for r in shortlist:
            md.append("| " + " | ".join(
                "" if r.get(c) is None else str(r.get(c)) for c in cols) + " |")
    else:
        md.append("_Nothing passed the gates._")

    md += ["", "## Rejected, and why", ""]
    if rejected:
        md += ["| keyword | trend | latest volume | reason |",
               "| --- | --- | --- | --- |"]
        for r in rejected:
            md.append(f"| {r['keyword']} | {r.get('opportunity_flag')} | "
                      f"{r.get('latest_volume')} | {r.get('gate_failures', '')} |")
    else:
        md.append("_Nothing was rejected._")

    md += [
        "",
        "## How the ranking works",
        "",
        "Weights: " + ", ".join(f"`{k}` {v:.0%}" for k, v in WEIGHTS.items()) + ".",
        "",
        "- **growth** — trend slope, fitted on log volume so it is a rate.",
        "- **demand** — latest volume, also logged: 500→5,000 matters more than "
        "50,000→54,500.",
        "- **openness** — low review moat and high demand-per-listing, averaged. "
        "This is the column that separates a big category from an enterable one.",
        "- **headroom** — price dispersion (IQR/median). Wide spread means room "
        "to position; tight clustering means competing on price alone.",
        "",
        "**The score is relative to this candidate set.** Components are min-max "
        "normalised across the candidates you supplied, so adding an eleventh "
        "changes the other ten, and `0.9` means \"best of what you supplied\", "
        "not \"good in absolute terms\". Compare within a run, never across runs.",
        "",
        "**Gates are not score terms.** No amount of growth makes a category with "
        "entrenched review incumbents enterable, so the moat disqualifies rather "
        "than subtracts. The rejected table above is usually the more useful half: "
        "\"rising but seasonal\" and \"open but unsearched\" are different next "
        "actions.",
    ]
    path.write_text("\n".join(md) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank Amazon product candidates.")
    ap.add_argument("--keywords", default="moringa oil,honey,mouth tape,sleep gummies")
    ap.add_argument("--keywords-file")
    ap.add_argument("--country", default="US")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--window", type=int, default=4)
    ap.add_argument("--weeks", type=int, default=52)
    ap.add_argument("--min-volume", type=float, default=500)
    ap.add_argument("--min-observations", type=int, default=12)
    ap.add_argument("--max-review-moat", type=float, default=2000)
    ap.add_argument("--allowed-flags", nargs="+", default=list(DEFAULT_ALLOWED_FLAGS))
    ap.add_argument("--price-all", action="store_true",
                    help="fetch competition data even for trend-rejected keywords")
    ap.add_argument("--endpoint", default=trend.default_endpoint())
    ap.add_argument("--auth-header", default=trend.DEFAULT_AUTH_HEADER)
    ap.add_argument("--auth-prefix", default=trend.DEFAULT_AUTH_PREFIX)
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    if args.keywords_file:
        text = Path(args.keywords_file).read_text(encoding="utf-8")
        keywords = [ln.strip() for ln in text.splitlines()
                    if ln.strip() and not ln.strip().startswith("#")]
    else:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    if not keywords:
        sys.exit("No keywords given.")
    country = args.country.upper()

    if args.dry_run:
        print("DRY RUN — no network call is made.\n")
        trend_key = comp_key = None
    else:
        trend_key = trend.api_key()
        comp_key = comp.api_key()

    candidates = []
    for kw in keywords:
        print(f"  {kw}:")
        try:
            candidates.append(collect(kw, args, trend_key, comp_key))
        except trend.SchemaMismatch as e:
            print(f"    SCHEMA MISMATCH — {e}")
        except RuntimeError as e:
            print(f"    {e}")

    if not candidates:
        print("\nNothing collected. If every keyword failed on reachability, "
              "this environment's egress policy is the cause.")
        return 1

    passed, rejected = [], []
    for c in candidates:
        fails = c.get("gate_failures")
        fails = fails.split("; ") if fails else gate(
            c, allowed_flags=tuple(args.allowed_flags), min_volume=args.min_volume,
            min_observations=args.min_observations,
            max_review_moat=args.max_review_moat)
        if fails:
            c["gate_failures"] = "; ".join(fails)
            rejected.append(c)
        else:
            passed.append(c)

    shortlist = score_candidates(passed)

    print(f"\n--- Shortlist ({len(shortlist)} of {len(candidates)}) ---")
    for r in shortlist:
        print(f"  {r['rank']}. {r['keyword']:<18s} score {r['score']:.3f}  "
              f"(growth {r['score_growth']:.2f} demand {r['score_demand']:.2f} "
              f"openness {r['score_openness']:.2f} headroom {r['score_headroom']:.2f})")
    if not shortlist:
        print("  nothing passed the gates")

    print(f"\n--- Rejected ({len(rejected)}) ---")
    for r in rejected:
        print(f"  {r['keyword']:<18s} {r['gate_failures']}")

    out = Path(args.out)
    write_csv(out / "amazon_shortlist.csv", shortlist + rejected)
    write_markdown(out / "amazon_shortlist.md", shortlist, rejected, country, args)
    print(f"\nWritten: {out / 'amazon_shortlist.csv'}\n         {out / 'amazon_shortlist.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
