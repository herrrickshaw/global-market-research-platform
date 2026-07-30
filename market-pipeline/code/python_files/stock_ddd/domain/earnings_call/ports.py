"""
domain/earnings_call/ports.py
=================================
Earnings Call bounded context — Ports (interfaces), DESIGN ONLY this phase.

No infrastructure/earnings_call adapter exists yet — implementing these is
Phase 2 for this bounded context (see domain/earnings_call/entities.py for
why the scheduling side should wrap earnings_dates_sec_8k.py /
earnings_dates_tdnet.py / earnings_dates_cache.py rather than be built from
scratch, and why the transcript side is genuinely new).

Same DDD pattern as domain/market_data/repositories.py and
application/ports/report_writer.py: the Domain defines the contract,
Infrastructure supplies the implementation. No import from infrastructure
appears in this file.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

from domain.earnings_call.entities import (
    EarningsCallEvent,
    EarningsCallSignal,
    EarningsCallTranscript,
)
from domain.shared.value_objects import Ticker


class IEarningsCallScheduleSource(ABC):
    """
    Contract for earnings-call scheduling data.

    Intended Phase 2 implementations wrap EXISTING collectors rather than
    add a new date-fetcher:
      - Sec8kScheduleSource   — wraps earnings_dates_sec_8k.py (US)
      - TdnetScheduleSource   — wraps earnings_dates_tdnet.py (Japan)
      - YFinanceScheduleSource — wraps earnings_dates_cache.py (fallback, all markets)
    """

    @abstractmethod
    def get_upcoming_calls(self, ticker: Ticker) -> List[EarningsCallEvent]:
        """Return known/estimated upcoming earnings calls for one ticker."""
        ...

    @abstractmethod
    def get_calls_in_window(self, days_ahead: int = 7) -> List[EarningsCallEvent]:
        """Return all earnings calls scheduled within the given window, any ticker."""
        ...


class IEarningsCallTranscriptSource(ABC):
    """
    Contract for fetching an earnings call's actual content once it has
    occurred. No implementation exists yet — a real transcript provider
    (company IR page, a paid transcript API, or an audio-to-text pipeline
    reusing the repo's existing Unlimited-OCR-adjacent tooling for scanned
    IR PDFs) is Phase 2 scope.
    """

    @abstractmethod
    def fetch_transcript(self, event: EarningsCallEvent) -> Optional[EarningsCallTranscript]:
        """Return the transcript for a completed call, or None if unavailable."""
        ...


class IEarningsCallAnalyzer(ABC):
    """
    Contract for deriving a structured EarningsCallSignal from a transcript
    (sentiment, guidance direction, key topics). Kept as its own port
    rather than a transcript method because the analysis step is the one
    most likely to be swapped (rule-based keyword extraction now, an LLM
    summarizer later) without touching scheduling or fetching.
    """

    @abstractmethod
    def analyze(self, transcript: EarningsCallTranscript) -> EarningsCallSignal:
        ...


class IEarningsCallSignalRepository(ABC):
    """
    Contract for persisting/retrieving EarningsCallSignal history — the
    durable, queryable output of this bounded context (a transcript itself
    is large and rarely re-read; the signal is what other bounded contexts,
    e.g. screening, would actually consume).
    """

    @abstractmethod
    def save(self, signal: EarningsCallSignal) -> None:
        ...

    @abstractmethod
    def get_history(self, ticker: Ticker, since: Optional[date] = None) -> List[EarningsCallSignal]:
        ...
