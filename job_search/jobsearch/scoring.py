"""Score a job posting against the candidate profile and their network."""
from __future__ import annotations

import math
import re
from datetime import date

from .models import CompanyNetwork, JobPosting, Match
from .network import network_strength
from .profile import TargetProfile

# Weights for the final blend. Network is weighted heavily on purpose: a
# mediocre-fit role where a recruiter can hand-carry your CV beats a perfect-fit
# role thrown into a cold ATS pile.
W_ROLE, W_NETWORK, W_FRESH = 0.50, 0.35, 0.15

_HALF_LIFE_DAYS = 30.0


def _contains(haystack: str, needle: str) -> bool:
    """Word-boundary-aware substring test, so 'vp' does not match 'development'."""
    if " " in needle:
        return needle in haystack
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


def role_fit(job: JobPosting, profile: TargetProfile) -> tuple[float, list[str]]:
    """0-1 fit of a posting's title/description to the target profile."""
    title = (job.title or "").lower()
    body = f"{title} {(job.description or '').lower()}"
    reasons: list[str] = []

    for bad in profile.exclude_keywords:
        if _contains(title, bad.lower()):
            return 0.0, [f"excluded: '{bad}' in title"]

    title_hits = [(kw, w) for kw, w in profile.title_keywords.items() if _contains(title, kw)]
    if not title_hits:
        # Fall back to the description at a discount - a relevant role whose
        # title uses in-house jargon still deserves a look, just not a top slot.
        desc_hits = [(kw, w * 0.35) for kw, w in profile.title_keywords.items()
                     if _contains(body, kw)]
        title_hits = sorted(desc_hits, key=lambda x: -x[1])[:2]
        if title_hits:
            reasons.append("matched on description, not title")

    if not title_hits:
        return 0.0, ["no role keyword match"]

    best = max(w for _, w in title_hits)
    extra = sum(w for _, w in sorted(title_hits, key=lambda x: -x[1])[1:3]) * 0.15
    score = min(1.0, best + extra)
    reasons.append("role: " + ", ".join(kw for kw, _ in sorted(title_hits, key=lambda x: -x[1])[:3]))

    sector = max((w for kw, w in profile.sector_keywords.items() if _contains(body, kw)),
                 default=0.0)
    if sector:
        score = min(1.0, score + sector * 0.20)
        hit = [kw for kw in profile.sector_keywords if _contains(body, kw)][:2]
        reasons.append("sector: " + ", ".join(hit))

    seniority = max((w for kw, w in profile.seniority_keywords.items() if _contains(title, kw)),
                    default=0.0)
    if seniority:
        score = min(1.0, score + seniority * 0.12)

    loc = (job.location or "").lower()
    if profile.locations:
        if any(l in loc for l in profile.locations) or (job.remote and profile.remote_ok):
            reasons.append(f"location ok: {job.location or 'remote'}")
        elif loc:
            score *= 0.55
            reasons.append(f"location mismatch: {job.location}")

    return round(min(1.0, score), 4), reasons


def freshness(job: JobPosting, today: date | None = None) -> float:
    """Exponential decay on posting age, 30-day half-life.

    Undated postings get a neutral 0.5 rather than 0 -- several sources omit
    dates entirely and should not be uniformly buried.
    """
    if job.posted_at is None:
        return 0.5
    days = max(0, ((today or date.today()) - job.posted_at).days)
    return round(math.exp(-days * math.log(2) / _HALF_LIFE_DAYS), 4)


def score_job(job: JobPosting, net: CompanyNetwork | None, profile: TargetProfile,
              today: date | None = None) -> Match:
    fit, reasons = role_fit(job, profile)
    net_score = network_strength(net) if net else 0.0
    fresh = freshness(job, today)

    if net and net.size:
        bits = [f"{net.size} connection{'s' if net.size > 1 else ''}"]
        if net.hiring_contacts:
            bits.append(f"{len(net.hiring_contacts)} in talent/HR")
        if net.senior_contacts:
            bits.append(f"{len(net.senior_contacts)} senior")
        reasons.append("network: " + ", ".join(bits))

    total = W_ROLE * fit + W_NETWORK * net_score + W_FRESH * fresh
    # A zero role fit is disqualifying no matter how strong the network is.
    if fit == 0.0:
        total = 0.0

    return Match(job=job, network=net, role_fit=fit, network_score=net_score,
                 freshness=fresh, total=round(total, 4), reasons=reasons)
