"""Turn a flat connection list into a company-indexed network graph."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Iterable

from .models import CompanyNetwork, Connection
from .normalize import normalize_company

# Titles that mean this person can route a CV internally.
HIRING_PATTERNS = re.compile(
    r"\b(recruit\w*|talent\s+acquisition|talent\s+partner|talent\s+manager|"
    r"technical\s+recruiter|sourcer|staffing|head\s+of\s+people|people\s+ops\w*|"
    r"people\s+partner|human\s+resources?|hr\s+(manager|lead|head|director|business\s+partner)|"
    r"hiring\s+manager|chief\s+people\s+officer|chro)\b",
    re.I,
)

# Titles senior enough to create or unblock a role.
SENIOR_PATTERNS = re.compile(
    r"\b(ceo|cto|coo|cfo|cio|cmo|chief\s+\w+\s+officer|founder|co-?founder|"
    r"managing\s+director|managing\s+partner|\bpartner\b|president|"
    r"vice\s+president|\bvp\b|\bsvp\b|\bevp\b|head\s+of|global\s+head|"
    r"director|general\s+manager|country\s+manager)\b",
    re.I,
)


def is_hiring_contact(conn: Connection) -> bool:
    return bool(HIRING_PATTERNS.search(conn.position or ""))


def is_senior_contact(conn: Connection) -> bool:
    return bool(SENIOR_PATTERNS.search(conn.position or ""))


def build_company_index(connections: Iterable[Connection]) -> dict[str, CompanyNetwork]:
    """Index connections by normalised company name.

    Connections with no resolvable employer (freelance, self-employed, blank)
    are skipped: they would otherwise collapse into one meaningless mega-company.
    """
    buckets: dict[str, list[Connection]] = defaultdict(list)
    spellings: dict[str, Counter] = defaultdict(Counter)

    for conn in connections:
        key = normalize_company(conn.company)
        if not key:
            continue
        buckets[key].append(conn)
        spellings[key][conn.company.strip()] += 1

    index: dict[str, CompanyNetwork] = {}
    for key, members in buckets.items():
        # Most common raw spelling is the best human-facing label: "Shell"
        # rather than a one-off "Shell (Shell Projects & Technology)".
        label = spellings[key].most_common(1)[0][0]
        index[key] = CompanyNetwork(
            display_name=label,
            normalized=key,
            connections=members,
            hiring_contacts=[c for c in members if is_hiring_contact(c)],
            senior_contacts=[c for c in members if is_senior_contact(c)],
        )
    return index


def network_strength(net: CompanyNetwork) -> float:
    """Score 0-1 for how strong a warm path into this company is.

    A recruiter is worth far more than a headcount: one talent-acquisition
    contact beats twenty unrelated colleagues for getting a CV read.
    """
    import math

    if net is None or net.size == 0:
        return 0.0
    # Diminishing returns on raw headcount - 1 contact is transformative,
    # the 40th adds nothing.
    breadth = min(1.0, math.log1p(net.size) / math.log1p(25))
    hiring = min(1.0, len(net.hiring_contacts) / 2.0)
    senior = min(1.0, len(net.senior_contacts) / 5.0)
    return round(min(1.0, 0.35 * breadth + 0.40 * hiring + 0.25 * senior), 4)


def top_companies(index: dict[str, CompanyNetwork], limit: int = 50) -> list[CompanyNetwork]:
    return sorted(index.values(), key=lambda n: (-network_strength(n), -n.size))[:limit]
