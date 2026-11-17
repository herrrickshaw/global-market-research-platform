from __future__ import annotations

import threading

import pandas as pd

from . import registry
from .interfaces import PredictResult, ServingBackend


class LocalServingBackend(ServingBackend):
    def __init__(self) -> None:
        self._model_cache: dict[tuple[str, str], object] = {}
        self._lock = threading.Lock()

    def list_models(self) -> list[dict]:
        return registry.list_registered_models()

    def predict(self, model_name: str, payload: dict, version: str | None = None) -> PredictResult:
        import mlflow

        mlflow.set_tracking_uri(registry._tracking_uri())
        stage = version or "latest"
        cache_key = (model_name, stage)
        with self._lock:
            model = self._model_cache.get(cache_key)
        if model is None:
            model = mlflow.pyfunc.load_model(f"models:/{model_name}/{stage}")
            with self._lock:
                self._model_cache[cache_key] = model

        prediction = model.predict(pd.DataFrame([payload]))
        value = prediction.tolist()[0] if hasattr(prediction, "tolist") else prediction[0]
        return PredictResult(model_name=model_name, version=stage, prediction=value)
