"""Mini-SageMaker platform: training/serving behind a portable backend interface.

Callers should only import get_training_backend()/get_serving_backend() from
here, never the concrete local_* classes directly, so a future "aws" backend
can be swapped in via env var without touching router code.
"""
from __future__ import annotations

import os

from .interfaces import ServingBackend, TrainingBackend

_training_backend: TrainingBackend | None = None
_serving_backend: ServingBackend | None = None


def get_training_backend() -> TrainingBackend:
    global _training_backend
    if _training_backend is None:
        kind = os.environ.get("ML_TRAINING_BACKEND", "local")
        if kind == "local":
            from .local_training import LocalTrainingBackend

            _training_backend = LocalTrainingBackend()
        elif kind == "aws":
            raise NotImplementedError("aws training backend not yet implemented")
        else:
            raise ValueError(f"unknown ML_TRAINING_BACKEND: {kind!r}")
    return _training_backend


def get_serving_backend() -> ServingBackend:
    global _serving_backend
    if _serving_backend is None:
        kind = os.environ.get("ML_SERVING_BACKEND", "local")
        if kind == "local":
            from .local_serving import LocalServingBackend

            _serving_backend = LocalServingBackend()
        elif kind == "aws":
            raise NotImplementedError("aws serving backend not yet implemented")
        else:
            raise ValueError(f"unknown ML_SERVING_BACKEND: {kind!r}")
    return _serving_backend
