from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobStatus:
    job_id: str
    job_name: str
    state: str  # 'queued' | 'running' | 'succeeded' | 'failed'
    params: dict = field(default_factory=dict)
    result: dict | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class PredictResult:
    model_name: str
    version: str
    prediction: Any
    metadata: dict | None = None


class TrainingBackend(ABC):
    @abstractmethod
    def submit(self, job_name: str, params: dict) -> str:
        """Submit a training job by name; returns a job_id to poll."""

    @abstractmethod
    def status(self, job_id: str) -> JobStatus:
        """Look up a previously submitted job's status."""

    @abstractmethod
    def list_jobs(self) -> list[JobStatus]:
        """List all known jobs, most recent first."""


class ServingBackend(ABC):
    @abstractmethod
    def predict(self, model_name: str, payload: dict, version: str | None = None) -> PredictResult:
        """Run inference against a registered model."""

    @abstractmethod
    def list_models(self) -> list[dict]:
        """List models available for serving."""
