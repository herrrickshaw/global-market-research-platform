from __future__ import annotations

import threading
import traceback
import uuid
from datetime import datetime, timezone

from .interfaces import JobStatus, TrainingBackend
from .jobs.catalog import JOBS


class LocalTrainingBackend(TrainingBackend):
    def __init__(self) -> None:
        self._jobs: dict[str, JobStatus] = {}
        self._lock = threading.Lock()

    def submit(self, job_name: str, params: dict) -> str:
        if job_name not in JOBS:
            raise ValueError(f"unknown job_name {job_name!r}; known jobs: {list(JOBS)}")
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = JobStatus(
                job_id=job_id, job_name=job_name, state="queued", params=params
            )
        threading.Thread(target=self._run, args=(job_id, job_name, params), daemon=True).start()
        return job_id

    def status(self, job_id: str) -> JobStatus:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"no such job_id {job_id!r}")
        return job

    def list_jobs(self) -> list[JobStatus]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.started_at or "", reverse=True)

    def _run(self, job_id: str, job_name: str, params: dict) -> None:
        with self._lock:
            self._jobs[job_id].state = "running"
            self._jobs[job_id].started_at = datetime.now(timezone.utc).isoformat()
        try:
            result = JOBS[job_name](params)
            with self._lock:
                self._jobs[job_id].state = "succeeded"
                self._jobs[job_id].result = result
        except Exception as exc:
            with self._lock:
                self._jobs[job_id].state = "failed"
                self._jobs[job_id].error = f"{exc}\n{traceback.format_exc()}"
        finally:
            with self._lock:
                self._jobs[job_id].finished_at = datetime.now(timezone.utc).isoformat()
