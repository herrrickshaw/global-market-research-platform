"""
domain/earnings_call/entities.py
====================================
Earnings Call Domain — Value Objects & Entity (DESIGN ONLY this phase).

GENUINELY GREENFIELD, unlike domain/ipo: confirmed by exhaustive grep across
this repo (no "transcript", "earnings call", or "conference call" handling
anywhere outside third-party packages). No scraper, parser, or ingestion
adapter exists yet — that is Phase 2 for this bounded context.

WHAT ALREADY EXISTS AND IS DELIBERATELY NOT DUPLICATED HERE
─────────────────────────────────────────────────────────────
earnings_dates_sec_8k.py (US, SEC EDGAR 8-K Item 2.02) and
earnings_dates_tdnet.py (Japan, JPX TDnet 決算短信 filings) already collect
real earnings-ANNOUNCEMENT dates, alongside the older yfinance-based
earnings_dates_cache.py. `EarningsCallEvent.scheduled_at` below is designed
to be POPULATED FROM those existing collectors by a future
infrastructure/earnings_call adapter (Phase 2) — the same wrap-don't-rewrite
approach used for domain/ipo — rather than a new date-fetcher. What is
actually new is everything downstream of the date: fetching the call's
transcript/audio and extracting commentary, guidance, and sentiment.

DOMAIN CONCEPTS
───────────────
EarningsCallEvent      : One scheduled or completed earnings call for a
                         ticker's fiscal period. Carries only scheduling
                         metadata — no transcript content.

EarningsCallTranscript : The call's actual content once available:
                         participants, prepared remarks, Q&A. An entity
                         (not a value object) because a transcript can be
                         amended (e.g. a corrected reissue) while remaining
                         "the same" transcript for a given event.

GuidanceChange         : A value object capturing whether management raised,
                         maintained, lowered, or withdrew forward guidance
                         during the call — the single highest-signal,
                         structured fact a transcript yields for screening.

EarningsCallSignal     : The bounded context's output — a structured
                         summary derived from a transcript (guidance
                         direction, sentiment, key topics) for consumption
                         by application/queries, kept separate from the
                         raw transcript so callers who only need the
                         signal never have to load full call text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from domain.shared.value_objects import Ticker


class CallStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    RESCHEDULED = "RESCHEDULED"


class GuidanceDirection(str, Enum):
    RAISED = "RAISED"
    MAINTAINED = "MAINTAINED"
    LOWERED = "LOWERED"
    WITHDRAWN = "WITHDRAWN"
    NOT_PROVIDED = "NOT_PROVIDED"  # company gives no forward guidance at all


class CallSentiment(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"


@dataclass(frozen=True)
class EarningsCallEvent:
    """
    Scheduling metadata for one earnings call. No transcript content —
    see EarningsCallTranscript for that, keyed by this event.
    """
    ticker:         Ticker
    fiscal_period:  str              # e.g. "Q1 FY27"
    scheduled_at:   Optional[datetime]
    status:         CallStatus
    source:         str              # e.g. "sec_8k_item_2.02", "tdnet_tanshin"

    @property
    def is_upcoming(self) -> bool:
        return self.status == CallStatus.SCHEDULED and (
            self.scheduled_at is None or self.scheduled_at >= datetime.now()
        )


@dataclass(frozen=True)
class GuidanceChange:
    """Structured extraction of a single forward-guidance statement from a call."""
    metric:      str                        # e.g. "FY27 Revenue", "Operating Margin"
    direction:   GuidanceDirection
    prior_value: Optional[str] = None       # as stated, unit-preserved (no normalisation here)
    new_value:   Optional[str] = None
    quote:       Optional[str] = None       # supporting verbatim excerpt, if captured


@dataclass
class EarningsCallTranscript:
    """
    An earnings call's content. An ENTITY (has identity via event + version),
    not a value object — a transcript can be corrected/reissued after initial
    publication while remaining conceptually "the same" transcript.
    """
    event:              EarningsCallEvent
    published_at:       datetime
    participants:       List[str] = field(default_factory=list)   # management + analysts
    prepared_remarks:   str = ""
    qa_section:         str = ""
    source_url:         Optional[str] = None
    version:            int = 1                                    # bumped on reissue

    @property
    def full_text(self) -> str:
        return f"{self.prepared_remarks}\n\n{self.qa_section}".strip()

    @property
    def word_count(self) -> int:
        return len(self.full_text.split())


@dataclass(frozen=True)
class EarningsCallSignal:
    """
    Structured summary derived from an EarningsCallTranscript — the
    bounded context's actual output for downstream screening/reporting.
    Deliberately separate from EarningsCallTranscript so a caller that only
    needs the signal (e.g. a daily scan) never has to load full call text.
    """
    ticker:              Ticker
    fiscal_period:       str
    sentiment:           CallSentiment
    guidance_changes:    List[GuidanceChange]
    key_topics:          List[str]
    as_of:               date

    @property
    def has_guidance_cut(self) -> bool:
        return any(g.direction == GuidanceDirection.LOWERED for g in self.guidance_changes)

    @property
    def has_guidance_raise(self) -> bool:
        return any(g.direction == GuidanceDirection.RAISED for g in self.guidance_changes)
