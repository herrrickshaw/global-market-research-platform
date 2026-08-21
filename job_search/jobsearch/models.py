"""Core data structures shared across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class Connection:
    """One 1st-degree connection from the LinkedIn export."""
    first_name: str
    last_name: str
    url: str
    email: str
    company: str
    position: str
    connected_on: Optional[date]

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class JobPosting:
    """A live opening, normalised across every source."""
    source: str
    company: str
    title: str
    location: str
    url: str
    posted_at: Optional[date] = None
    description: str = ""
    remote: bool = False
    external_id: str = ""

    def dedupe_key(self) -> tuple:
        from .normalize import normalize_company, normalize_title
        return (normalize_company(self.company), normalize_title(self.title),
                (self.location or "").strip().lower()[:40])


@dataclass
class CompanyNetwork:
    """Aggregated view of the user's network at one company."""
    display_name: str
    normalized: str
    connections: list = field(default_factory=list)
    hiring_contacts: list = field(default_factory=list)
    senior_contacts: list = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.connections)


@dataclass
class Match:
    """A job posting scored against the user's profile and network."""
    job: JobPosting
    network: Optional[CompanyNetwork]
    role_fit: float
    network_score: float
    freshness: float
    total: float
    reasons: list = field(default_factory=list)
    # Populated only when the posting carried real job-description text AND a
    # resume was supplied. Left as None otherwise, deliberately: a title-only
    # score must never be presented as though a JD had been read.
    ats: Optional[object] = None

    @property
    def has_warm_path(self) -> bool:
        return self.network is not None and self.network.size > 0

    @property
    def ats_percent(self) -> Optional[int]:
        return self.ats.percent if self.ats and self.ats.scored_against_jd else None
