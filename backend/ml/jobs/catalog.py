from __future__ import annotations

from typing import Callable

JOBS: dict[str, Callable[[dict], dict]] = {}


def _register(name: str, fn: Callable[[dict], dict]) -> None:
    JOBS[name] = fn


def _lazy_ml_supervised(params: dict) -> dict:
    from . import ml_supervised_job

    return ml_supervised_job.run(params)


def _lazy_price_prediction(params: dict) -> dict:
    from . import price_prediction_job

    return price_prediction_job.run(params)


def _lazy_ml_signal_engine(params: dict) -> dict:
    from . import ml_signal_engine_job

    return ml_signal_engine_job.run(params)


_register("ml_supervised", _lazy_ml_supervised)
_register("price_prediction", _lazy_price_prediction)
_register("ml_signal_engine", _lazy_ml_signal_engine)
