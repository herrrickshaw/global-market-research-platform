"""Thin MLflow client wrapper — tracking + model registry."""
from __future__ import annotations

import os
from contextlib import contextmanager

import mlflow


def _tracking_uri() -> str:
    return os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")


@contextmanager
def start_run(experiment: str, run_name: str | None = None):
    mlflow.set_tracking_uri(_tracking_uri())
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name) as run:
        yield run


def log_params(params: dict) -> None:
    mlflow.log_params(params)


def log_metrics(metrics: dict) -> None:
    mlflow.log_metrics(metrics)


def log_sklearn_model(model, artifact_path: str, registered_model_name: str | None = None) -> None:
    import mlflow.sklearn

    mlflow.sklearn.log_model(
        model, artifact_path=artifact_path, registered_model_name=registered_model_name
    )


def list_registered_models() -> list[dict]:
    mlflow.set_tracking_uri(_tracking_uri())
    client = mlflow.MlflowClient()
    out = []
    for rm in client.search_registered_models():
        versions = client.search_model_versions(f"name='{rm.name}'")
        latest = max((int(v.version) for v in versions), default=None)
        out.append({"name": rm.name, "latest_version": latest})
    return out
