#!/usr/bin/env python3
"""
Turn a LinkedIn connections export into a ranked list of target companies.

WHY AN EXPORT AND NOT THE SITE
------------------------------
This does not scrape LinkedIn and will not be made to. Automated collection
breaches LinkedIn's terms, risks the account it is run from, and is unnecessary:
LinkedIn will hand you your own connection list on request.

    Settings & Privacy -> Data Privacy -> Get a copy of your data
    -> "Connections" -> download the archive -> Connections.csv

That file is yours, it is complete, and it arrives as clean CSV. Everything
here works from it.

WHAT IT IS FOR
--------------
A job application through a company where you already know someone is a
different proposition from a cold application. This ranks companies in your
network by how many people you know there and how recently you connected,
because a recent connection is a warmer one than a decade-old one.

Usage:
    python3 jobsearch/connections.py ~/Downloads/Connections.csv
    python3 jobsearch/connections.py Connections.csv --min-connections 2 --top 40
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

# LinkedIn puts a "Notes:" preamble above the header row. The number of lines
# has changed between export versions, so find the header rather than skip a
# fixed count.
HEADER_TOKENS = ("First Name", "Company", "Position")

# Seniority markers, used only to flag whether a contact is plausibly able to
# refer or hire. Deliberately crude — it is a sort hint, not a judgement.
SENIOR = re.compile(
    r"\b(chief|c[etoif]o|founder|owner|partner|president|vp|vice president|"
    r"head|director|principal|lead|manager|senior manager)\b", re.I)
# `recruit` deliberately has no trailing boundary — it must match Recruiter,
# Recruiting and Recruitment, which a \b would exclude.
RECRUITING = re.compile(
    r"\b(recruit\w*|talent acquisition|talent partner|sourcer|staffing|"
    r"hr\b|human resources|people operations|people partner)", re.I)


def find_header(text: str) -> int:
    for i, line in enumerate(text.splitlines()):
        if sum(t in line for t in HEADER_TOKENS) >= 2:
            return i
    raise SystemExit(
        "Could not find the header row. Expected a LinkedIn Connections.csv "
        "with First Name / Company / Position columns."
    )


def load(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    start = find_header(raw)
    body = "\n".join(raw.splitlines()[start:])
    rows = list(csv.DictReader(io.StringIO(body)))
    if not rows:
        raise SystemExit("No connection rows found in that file.")
    return rows


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def companies(rows: list[dict], today: date) -> list[dict]:
    by_company: dict[str, list[dict]] = {}
    for r in rows:
        c = (r.get("Company") or "").strip()
        if not c:
            continue
        by_company.setdefault(c, []).append(r)

    out = []
    for company, people in by_company.items():
        dates = [d for d in (parse_date(p.get("Connected On")) for p in people) if d]
        newest = max(dates) if dates else None
        seniors = [p for p in people
                   if SENIOR.search((p.get("Position") or ""))]
        recruiters = [p for p in people
                      if RECRUITING.search((p.get("Position") or ""))]
        out.append({
            "company": company,
            "connections": len(people),
            "senior_contacts": len(seniors),
            "recruiting_contacts": len(recruiters),
            "most_recent_connection": newest.isoformat() if newest else None,
            "years_since_newest": round((today - newest).days / 365.25, 1) if newest else None,
            "example_contact": f"{people[0].get('First Name','')} "
                               f"{people[0].get('Last Name','')}".strip() or None,
            "example_title": (people[0].get("Position") or "").strip() or None,
        })
    return out


def score(rows: list[dict]) -> list[dict]:
    """Warmth = how many you know, weighted up for seniors and recruiters,
    decayed for staleness. A sort hint, not a probability."""
    for r in rows:
        base = r["connections"]
        base += r["senior_contacts"] * 1.5      # can refer or hire
        base += r["recruiting_contacts"] * 2.0  # is literally paid to
        yrs = r["years_since_newest"]
        decay = 1.0 if yrs is None else max(0.4, 1.0 - min(yrs, 10) * 0.06)
        r["warmth"] = round(base * decay, 2)
    return sorted(rows, key=lambda r: (-r["warmth"], r["company"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path", help="LinkedIn Connections.csv from your data export")
    ap.add_argument("--min-connections", type=int, default=1)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--today", default=None, help="YYYY-MM-DD, for reproducible output")
    ap.add_argument("--out", default="reports")
    args = ap.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    path = Path(args.csv_path).expanduser()
    if not path.exists():
        raise SystemExit(f"No such file: {path}")

    rows = load(path)
    print(f"Loaded {len(rows):,} connections from {path.name}")

    titles = Counter((r.get("Position") or "").strip() for r in rows if r.get("Position"))
    print(f"  {len(titles):,} distinct titles · "
          f"{len({(r.get('Company') or '').strip() for r in rows if r.get('Company')}):,} companies")

    scored = score([c for c in companies(rows, today)
                    if c["connections"] >= args.min_connections])

    print(f"\n=== TOP {min(args.top, len(scored))} COMPANIES BY NETWORK WARMTH ===")
    hdr = f"{'company':<34s} {'conns':>5s} {'senior':>6s} {'recr':>5s} {'last':>10s} {'warmth':>7s}"
    print(hdr)
    print("-" * len(hdr))
    for r in scored[:args.top]:
        print(f"{r['company'][:34]:<34s} {r['connections']:>5d} {r['senior_contacts']:>6d} "
              f"{r['recruiting_contacts']:>5d} {str(r['most_recent_connection'] or '-'):>10s} "
              f"{r['warmth']:>7.2f}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "network_targets.csv"
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(scored[0].keys()))
        w.writeheader()
        w.writerows(scored)
    print(f"\nCSV written: {dest}  ({len(scored)} companies)")
    print("\nWarmth is a sort hint, not a probability. It counts who you know, adds")
    print("weight for people senior enough to refer and for recruiters, and decays")
    print("with time since you last connected. Read the columns, not the score.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
