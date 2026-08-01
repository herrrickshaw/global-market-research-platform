#!/usr/bin/env python3
"""Citation checker — the local, Jenni-style guard for this repo's research docs.

Scans .py/.md files for author-year citations ("Piotroski (2000)", "Fama & French
(1993)", "Bhute et al. (2024)") and checks each against the canonical bibliography
references.bib. The 2026-08-01 literature audit found every recurring failure mode
this tool now catches:

  UNKNOWN   — author-year cited but no matching entry in references.bib
              (how "AlQahtani et al. 2025" floated uncited for weeks)
  YEAR?     — surname matches an entry but the year doesn't
              (how "Balvers & Wu (2005)" survived; published 2006)
  QUOTE?    — a quotation mark directly abuts a citation; verify it's a real
              quote, not a paraphrase in quotes (the Piotroski wording trap)

Usage:
  python3 cite_check.py FILE [FILE...]        # check specific files
  python3 cite_check.py --all                 # every tracked .py/.md in cwd repo
  python3 cite_check.py --staged              # staged files only (pre-commit)
Exit code 1 if any UNKNOWN finding (YEAR?/QUOTE? are warnings only).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BIB = Path(__file__).with_name("references.bib")

# "Name (2000)" / "Name & Name (2003)" / "Name, Name & Name (2016)" / "Name et al. (2024)"
NAME = r"[A-Z][A-Za-zÀ-ſ'\-]+"
CITE = re.compile(
    rf"({NAME}(?:\s*(?:,|&|and|–|-)\s*{NAME}){{0,4}}"
    rf"(?:\s+et\s+al\.?)?)\s*\(\s*(\d{{4}})[a-z]?\s*[,)]"
)
# Words that look like "Surname (Year)" but aren't citations.
STOP = {
    "In", "The", "A", "An", "On", "By", "Since", "From", "For", "See", "Both",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December", "Q1", "Q2", "Q3", "Q4",
    "FY", "CAGR", "IPO", "GDP", "NSE", "BSE", "US", "EU", "UK",
}


def load_bib() -> tuple[set[tuple[str, str]], set[str]]:
    """Return ({(surname_lower, year)}, {surname_lower}) from references.bib."""
    pairs: set[tuple[str, str]] = set()
    names: set[str] = set()
    entry_author, entry_year = None, None
    for line in BIB.read_text(encoding="utf-8").splitlines():
        if line.startswith("@"):
            entry_author, entry_year = None, None
        m = re.match(r"\s*author\s*=\s*\{(.+)\},?\s*$", line)
        if m:
            entry_author = m.group(1)
        m = re.match(r"\s*year\s*=\s*\{(\d{4})\}", line)
        if m:
            entry_year = m.group(1)
        if entry_author and entry_year:
            for chunk in re.split(r"\s+and\s+", entry_author):
                surname = chunk.split(",")[0].strip()
                surname = re.sub(r"\{\\?.\}|\{|\}|\\", "", surname)  # de-TeX
                surname = surname.lower()
                if not surname:
                    continue
                # register the full surname AND its final token, so
                # "De Bondt" matches "Bondt", "López de Prado" matches "Prado"
                for key in {surname, surname.split()[-1]}:
                    pairs.add((key, entry_year))
                    names.add(key)
            entry_author = None  # one author line per entry
    return pairs, names


def lead_candidates(name: str) -> set[str]:
    """Possible lead-author surnames for a cited name string.

    Hyphens are ambiguous: 'Novy-Marx' is one surname, 'Corwin-Schultz' is two —
    so generate leads under both readings and accept if either matches the bib.
    """
    name = re.sub(r"\bet\s+al\.?", "", name)
    leads = set()
    for splitter in (r"\s*(?:,|&|and|–)\s*", r"\s*(?:,|&|and|–|-)\s*"):
        parts = [p.strip().lower() for p in re.split(splitter, name) if p.strip()]
        if parts:
            leads.add(parts[0])
    return leads


def check_file(path: Path, pairs, names) -> list[tuple[str, int, str, str]]:
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in CITE.finditer(line):
            raw, year = m.group(1), m.group(2)
            leads = lead_candidates(raw)
            if not leads or raw in STOP or all(
                    lead.split()[0].capitalize() in STOP for lead in leads):
                continue
            if not (1900 <= int(year) <= 2035):
                continue
            if any((lead, year) in pairs for lead in leads):
                # known citation — still flag adjacent quotes for a human look
                window = line[max(0, m.start() - 2): m.end() + 2]
                if '"' in window or "“" in window or "”" in window:
                    findings.append(("QUOTE?", lineno, f"{raw} ({year})",
                                     "quote mark abuts citation — verify verbatim"))
            elif leads & names:
                lead = next(iter(leads & names))
                known = sorted({y for (s, y) in pairs if s == lead})
                findings.append(("YEAR?", lineno, f"{raw} ({year})",
                                 f"'{lead}' in bib but for year(s) {', '.join(known)}"))
            else:
                findings.append(("UNKNOWN", lineno, f"{raw} ({year})",
                                 "no entry in references.bib — add one or fix the cite"))
    return findings


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 0
    if args == ["--all"] or args == ["--staged"]:
        cmd = (["git", "diff", "--cached", "--name-only"] if args == ["--staged"]
               else ["git", "ls-files"])
        out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
        files = [Path(f) for f in out.splitlines()
                 if f.endswith((".py", ".md")) and Path(f).exists()]
    else:
        files = [Path(a) for a in args]

    if not BIB.exists():
        print(f"cite_check: missing {BIB}", file=sys.stderr)
        return 2
    pairs, names = load_bib()

    n_unknown = 0
    for f in files:
        if f.resolve() == Path(__file__).resolve():
            continue
        for kind, lineno, cite, msg in check_file(f, pairs, names):
            if kind == "UNKNOWN":
                n_unknown += 1
            print(f"{kind:8} {f}:{lineno}  {cite}  — {msg}")
    if n_unknown:
        print(f"\n{n_unknown} UNKNOWN citation(s). Add entries to references.bib "
              f"or correct the author/year.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
