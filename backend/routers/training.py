from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException
from fastapi.concurrency import run_in_threadpool

from ml import get_training_backend

router = APIRouter(prefix='/api/training', tags=['training'])


@router.post('/submit')
async def submit(job_name: str, params: dict = Body(default={})):
    """
    Start a training job in the background by name (see /api/training/jobs
    for the current list of runs, or backend/ml/jobs/catalog.py for known
    job_names). Returns immediately; poll /api/training/status/{job_id}.
    """
    backend = get_training_backend()
    try:
        job_id = await run_in_threadpool(backend.submit, job_name, params)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {
        'status': 'started',
        'job_id': job_id,
        'message': f'Poll /api/training/status/{job_id}',
    }


@router.get('/status/{job_id}')
async def status(job_id: str):
    backend = get_training_backend()
    try:
        job = await run_in_threadpool(backend.status, job_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    return job


@router.get('/jobs')
async def list_jobs():
    backend = get_training_backend()
    return {'jobs': await run_in_threadpool(backend.list_jobs)}
