#!/usr/bin/env python3
"""
Pull occupation-level salary data from Adzuna, for every country it covers.

WHY THIS MATTERS TO THE REST OF THE DIRECTORY
----------------------------------------------
Two gaps have been flagged repeatedly in these modules and Adzuna closes both:

  1. NATIONAL AVERAGES MIX OCCUPATIONS. Every wage figure used so far is an
     economy-wide average. Indian migrants are not an economy-wide sample —
     they concentrate in technology, medicine and finance — so the comparisons
     understate the advanced economies. Adzuna returns salary by search term,
     which lets the comparison be occupation-controlled.

  2. THE INDIA COUNTERFACTUAL WAS NOT COMPARABLE. roi_foreign_life could not
     express the Indian salary and the foreign salary in the same units,
     because bridging them needed a PPP conversion factor that was not
     reachable. Adzuna covers India AND the destinations on ONE methodology —
     advertised salaries, same collection, same definition — so the ratio
     between them needs no conversion factor at all. That is the closest thing
     to a like-for-like counterfactual available anywhere in this project.

CREDENTIALS
-----------
Read from the environment, never from this file and never committed:

    export ADZUNA_APP_ID=...
    export ADZUNA_APP_KEY=...

THIS SCRIPT CANNOT RUN IN THE ENVIRONMENT IT WAS WRITTEN IN. api.adzuna.com is
refused by that environment's egress proxy with a 403, the same organization
policy that blocks oecd.org, ilo.org and mea.gov.in. It is written to run
somewhere with ordinary internet access, and --dry-run exercises every code
path except the network call so the logic can be checked without one.

Usage:
    export ADZUNA_APP_ID=... ADZUNA_APP_KEY=...
    python3 research/diaspora/adzuna_salary_fetch.py --dry-run
    python3 research/diaspora/adzuna_salary_fetch.py
    python3 research/diaspora/adzuna_salary_fetch.py --what "software engineer" --countries gb,us,in
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

BASE = "https://api.adzuna.com/v1/api/jobs"

# Adzuna's country coverage. India is the one that matters most here — it makes
# the counterfactual measurable on the same basis as the destinations.
COUNTRIES = {
    "in": "India", "us": "United States", "gb": "United Kingdom",
    "ca": "Canada", "au": "Australia", "de": "Germany", "nl": "Netherlands",
    "fr": "France", "sg": "Singapore", "za": "South Africa", "nz": "New Zealand",
    "at": "Austria", "be": "Belgium", "ch": "Switzerland", "es": "Spain",
    "it": "Italy", "pl": "Poland", "br": "Brazil", "mx": "Mexico",
}

# Occupations chosen for where Indian migrants actually concentrate, rather
# than for a representative slice of any labour market.
OCCUPATIONS = ["software engineer", "data scientist", "registered nurse",
               "civil engineer", "accountant", "physician"]

CURRENCY = {"in": "INR", "us": "USD", "gb": "GBP", "ca": "CAD", "au": "AUD",
            "de": "EUR", "nl": "EUR", "fr": "EUR", "sg": "SGD", "za": "ZAR",
            "nz": "NZD", "at": "EUR", "be": "EUR", "ch": "CHF", "es": "EUR",
            "it": "EUR", "pl": "PLN", "br": "BRL", "mx": "MXN"}


def credentials() -> tuple[str, str]:
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        sys.exit("Set ADZUNA_APP_ID and ADZUNA_APP_KEY in the environment. "
                 "Do not put them in this file.")
    return app_id, app_key


def build_url(country: str, what: str, app_id: str, app_key: str,
              page: int = 1, per_page: int = 50) -> str:
    q = urllib.parse.urlencode({
        "app_id": app_id, "app_key": app_key,
        "results_per_page": per_page, "what": what,
        "content-type": "application/json",
    })
    return f"{BASE}/{country}/search/{page}?{q}"


def redact(url: str) -> str:
    """Never print a URL with the key in it — logs and tracebacks leak."""
    for var in ("ADZUNA_APP_KEY", "ADZUNA_APP_ID"):
        v = os.environ.get(var)
        if v:
            url = url.replace(v, f"<{var}>")
    return url


def fetch(country: str, what: str, app_id: str, app_key: str,
          timeout: int = 30) -> dict:
    url = build_url(country, what, app_id, app_key)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {redact(url)}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"cannot reach api.adzuna.com ({e.reason}). If this is the "
            f"Claude Code environment, that host is blocked by the egress "
            f"proxy — run this where you have ordinary internet access."
        ) from None


def summarise(payload: dict, country: str, what: str) -> dict:
    """Adzuna returns per-advert salary_min/max. Reduce to a country row."""
    results = payload.get("results", [])
    mids = [(r["salary_min"] + r["salary_max"]) / 2
            for r in results
            if r.get("salary_min") and r.get("salary_max")]
    mids.sort()
    n = len(mids)
    return {
        "country_code": country,
        "country": COUNTRIES.get(country, country),
        "currency": CURRENCY.get(country),
        "occupation": what,
        "adverts_returned": len(results),
        "adverts_with_salary": n,
        "salary_coverage_pct": round(n / len(results) * 100, 1) if results else None,
        "salary_mean": round(sum(mids) / n) if n else None,
        "salary_median": round(mids[n // 2]) if n else None,
        "salary_p25": round(mids[n // 4]) if n >= 4 else None,
        "salary_p75": round(mids[3 * n // 4]) if n >= 4 else None,
        "total_matching_adverts": payload.get("count"),
    }


DRY_RUN_FIXTURE = {
    "count": 4211,
    "results": [
        {"salary_min": 900000, "salary_max": 1400000},
        {"salary_min": 1200000, "salary_max": 1800000},
        {"salary_min": 700000, "salary_max": 1100000},
        {"salary_min": 1500000, "salary_max": 2400000},
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--what", default="software engineer")
    ap.add_argument("--countries", default="in,us,gb,ca,au,de,nl,sg",
                    help="comma-separated Adzuna country codes")
    ap.add_argument("--all-occupations", action="store_true")
    ap.add_argument("--dry-run", action="store_true",
                    help="exercise every path except the network call")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between calls")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    codes = [c.strip() for c in args.countries.split(",") if c.strip()]
    unknown = [c for c in codes if c not in COUNTRIES]
    if unknown:
        sys.exit(f"Adzuna does not cover: {', '.join(unknown)}. "
                 f"Known: {', '.join(sorted(COUNTRIES))}")
    jobs = OCCUPATIONS if args.all_occupations else [args.what]

    if args.dry_run:
        print("DRY RUN — no network call is made.\n")
        app_id, app_key = "DRY", "DRY"
        print("  URL shape (key redacted):")
        print(f"    {redact(build_url('in', args.what, app_id, app_key))}\n")
    else:
        app_id, app_key = credentials()

    rows = []
    for what in jobs:
        for code in codes:
            if args.dry_run:
                payload = DRY_RUN_FIXTURE
            else:
                try:
                    payload = fetch(code, what, app_id, app_key)
                except RuntimeError as e:
                    print(f"  {code}/{what}: {e}")
                    continue
                time.sleep(args.sleep)
            rows.append(summarise(payload, code, what))
            r = rows[-1]
            print(f"  {r['country']:<16s} {what:<20s} "
                  f"{r['currency']} median {r['salary_median']:,}"
                  if r["salary_median"] else
                  f"  {r['country']:<16s} {what:<20s} no salary data")

    if not rows:
        print("\nNothing fetched. If every row failed on reachability, this "
              "environment's egress policy is the cause — see the module docstring.")
        return 1

    df = pd.DataFrame(rows)

    # The counterfactual ratio: how many times an Indian salary is the foreign
    # one, in the SAME occupation, from the SAME source. No conversion factor
    # is applied here deliberately — that would need an FX rate this module
    # does not source. The ratio is reported per currency pair, to be converted
    # by whoever has a rate they trust.
    print("\n--- Per-occupation table ---")
    print(df.to_string(index=False))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "adzuna_salaries.csv"
    df.to_csv(path, index=False)
    print(f"\nCSV written: {path}")

    print("\nNOTE ON WHAT THIS MEASURES: Adzuna reports ADVERTISED salary, from "
          "job postings that\nchoose to state one. Coverage is in "
          "`salary_coverage_pct` and is never 100%. Advertised\npay skews "
          "toward roles that advertise — under-representing senior and "
          "referral-filled\npositions — and is a different quantity from the "
          "OECD's average earnings used elsewhere\nin this directory. Do not "
          "mix the two series in one comparison.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
