"""Rank the companies in your network as job-search targets.

Runs entirely offline: it needs no job feed, only the connections export and the
CV-derived sector profile. Answers "given who I know and what I've done, which
companies should I be working, and who exactly do I contact there?"

This is the complement to a job scan. A scan starts from openings and asks
whether you know anyone; this starts from your network and asks where it is
worth generating an opening.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .models import CompanyNetwork, Connection
from .network import network_strength
from .profile import TargetProfile

# Positions that indicate the company does work adjacent to the candidate's CV.
# Matching on colleagues' titles infers what a company actually does without
# needing any external company database.
_FUNCTION_HINTS = re.compile(
    r"\b(business development|investment|corporate development|strategy|"
    r"strategic|partnership|commercial|m&a|transaction|project finance|"
    r"policy|government affairs|public affairs|energy|lng|oil|gas|renewable|"
    r"hydrogen|decarboni[sz]|sustainability|process engineer|feed|"
    r"procurement|category|consultant|principal|associate director)\b",
    re.I,
)


@dataclass
class Target:
    network: CompanyNetwork
    strength: float
    sector_fit: float
    function_density: float
    score: float
    reasons: list


def _sector_fit(net: CompanyNetwork, profile: TargetProfile) -> float:
    """Infer sector relevance from the company name plus colleagues' titles."""
    blob = (net.display_name + " " + " ".join(c.position or "" for c in net.connections)).lower()
    hits = [(kw, w) for kw, w in profile.sector_keywords.items() if kw in blob]
    if not hits:
        return 0.0
    best = max(w for _, w in hits)
    extra = sum(w for _, w in sorted(hits, key=lambda x: -x[1])[1:3]) * 0.2
    return round(min(1.0, best + extra), 4)


def _function_density(net: CompanyNetwork) -> float:
    """Share of your contacts there doing work adjacent to your own."""
    if not net.connections:
        return 0.0
    n = sum(1 for c in net.connections if _FUNCTION_HINTS.search(c.position or ""))
    return round(min(1.0, math.log1p(n) / math.log1p(12)), 4)


def rank_targets(index: dict, profile: TargetProfile, limit: int = 50,
                 min_connections: int = 2) -> list[Target]:
    """Score every company in the network as a target to work."""
    out: list[Target] = []
    for net in index.values():
        if net.size < min_connections:
            continue
        strength = network_strength(net)
        sector = _sector_fit(net, profile)
        density = _function_density(net)
        # Sector fit is the largest term: a warm path into an irrelevant
        # industry is not a job lead.
        score = 0.40 * sector + 0.35 * strength + 0.25 * density

        reasons = [f"{net.size} connections"]
        if net.hiring_contacts:
            reasons.append(f"{len(net.hiring_contacts)} in talent/HR")
        if net.senior_contacts:
            reasons.append(f"{len(net.senior_contacts)} senior")
        out.append(Target(net, strength, sector, density, round(score, 4), reasons))

    out.sort(key=lambda t: -t.score)
    return out[:limit]


def best_contacts(net: CompanyNetwork, limit: int = 3) -> list[Connection]:
    """Who to actually message: recruiters first, then senior, then anyone."""
    seen, picks = set(), []
    for pool in (net.hiring_contacts, net.senior_contacts, net.connections):
        for c in pool:
            key = c.url or c.name
            if key in seen:
                continue
            seen.add(key)
            picks.append(c)
            if len(picks) >= limit:
                return picks
    return picks
