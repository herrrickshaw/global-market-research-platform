from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool

from ml import get_serving_backend

router = APIRouter(prefix='/api/models', tags=['models'])


@router.get('')
async def list_models():
    backend = get_serving_backend()
    try:
        models = await run_in_threadpool(backend.list_models)
    except Exception as exc:
        raise HTTPException(503, f'MLflow tracking server unreachable: {exc}')
    return {'models': models}


@router.post('/{name}/predict')
async def predict(name: str, payload: dict = Body(...), version: str | None = None):
    backend = get_serving_backend()
    try:
        result = await run_in_threadpool(backend.predict, name, payload, version)
    except Exception as exc:
        raise HTTPException(404, f'Could not serve prediction for model {name!r}: {exc}')
    return {'model': result.model_name, 'version': result.version, 'prediction': result.prediction}
