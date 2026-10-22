"""
Durable (crash-resumable) variant of bulk_fetcher.fetch_market_quotes, built on DBOS.

Enabled with BULK_FETCH_DBOS=1; bulk_fetcher falls back to its original path if
DBOS or its Postgres database is unavailable. Needs `pip install dbos`.

Why: the original fetch held every row in memory and wrote to Cassandra once, at
the end, so a crash/restart (uvicorn --reload, sleep, OOM) lost the whole run.
Here each batch is a DBOS step that fetches AND upserts immediately, and DBOS
records the step result in Postgres. After a crash, DBOS.launch() on the next
start recovers the pending workflow, replays finished steps from their stored
results (no refetch), and continues from the first unfinished batch.

Safe to repeat: upsert_quotes writes missing values as UNSET (not NULL), so
re-running a batch never erases fundamentals or prices.

Each run gets a unique workflow id so a second same-day fetch is a real fetch,
not a cached result; resumption of a crashed run is automatic via recovery.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout, as_completed
from datetime import datetime, timezone

import pandas as pd
from dbos import DBOS, DBOSConfig, SetWorkflowID

from db import bulk_fetcher as bf
from db.quote_updater import upsert_quotes

log = logging.getLogger(__name__)

_DB_URL = os.environ.get(
    'BULK_FETCH_DBOS_URL', 'postgresql://localhost:5432/dbos_bulk_fetch')
_launch_lock = threading.Lock()
_launched = False

PHASE2_CHUNK = 50          # tickers per fundamentals step
PHASE2_CHUNK_TIMEOUT = 300  # seconds; replaces the old whole-phase 600s timeout


def ensure_launched() -> None:
    """Configure and launch DBOS once per process (also recovers interrupted runs)."""
    global _launched
    with _launch_lock:
        if _launched:
            return
        cfg: DBOSConfig = {'name': 'bulk-fetcher', 'system_database_url': _DB_URL}
        DBOS(config=cfg)
        DBOS.launch()
        _launched = True


# ── steps ─────────────────────────────────────────────────────────────────────

@DBOS.step()
def _tickers_step(market: str) -> list[str]:
    # A step, so the ticker list stays frozen if the run is resumed.
    return bf._get_tickers(market)


@DBOS.step()
def _phase1_step(market: str, batch: list[str], suffix: str, is_inr: bool) -> dict:
    rows = bf._fetch_ohlcv_batch(batch, suffix, is_inr, market)
    written = upsert_quotes(market, pd.DataFrame(rows)) if rows else 0
    return {'requested': len(batch), 'fetched': len(rows), 'written': written,
            'tickers': [r['ticker'] for r in rows]}


@DBOS.step()
def _phase2_step(market: str, chunk: list[str], suffix: str, is_inr: bool,
                 max_workers: int) -> int:
    rows = []
    pool = ThreadPoolExecutor(max_workers=max_workers)
    futs = {pool.submit(bf._fetch_info_one, t, suffix, is_inr, market): t for t in chunk}
    try:
        for fut in as_completed(futs, timeout=PHASE2_CHUNK_TIMEOUT):
            extras = fut.result()
            if extras:
                rows.append({**extras, 'ticker': futs[fut]})
    except FutTimeout:
        log.warning('bulk_fetcher_dbos: [%s] fundamentals chunk timed out — keeping %d/%d',
                    market, len(rows), len(chunk))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return upsert_quotes(market, pd.DataFrame(rows)) if rows else 0


# ── workflow ──────────────────────────────────────────────────────────────────

@DBOS.workflow()
def fetch_market_workflow(market: str, batch_size: int, max_workers: int,
                          with_fundamentals: bool, inter_batch_delay: float) -> dict:
    cfg    = bf._MARKET_CFG.get(market, {'suffix': '', 'is_inr': False})
    suffix, is_inr = cfg['suffix'], cfg['is_inr']
    started = time.time()

    tickers = _tickers_step(market)
    if not tickers:
        result = {'market': market, 'total': 0, 'done': 0, 'errors': 0,
                  'written': 0, 'status': 'no_instruments', 'elapsed_s': 0}
        with bf._lock:
            bf._progress[market] = result
        return result

    total = len(tickers)
    done = errors = written = 0
    fetched: list[str] = []
    with bf._lock:
        bf._progress[market] = {'status': 'running', 'total': total, 'done': 0,
                                'errors': 0, 'written': 0, 'elapsed_s': 0,
                                'rate_per_min': 0, 'phase': 1}

    for i in range(0, total, batch_size):
        if bf._cancel.is_set():
            break
        r = _phase1_step(market, tickers[i:i + batch_size], suffix, is_inr)
        fetched.extend(r['tickers'])
        done += r['fetched']
        errors += r['requested'] - r['fetched']
        written += r['written']
        elapsed = time.time() - started
        with bf._lock:
            bf._progress[market].update({
                'done': done + errors, 'errors': errors, 'written': written,
                'elapsed_s': round(elapsed, 1),
                'rate_per_min': round((done + errors) / elapsed * 60, 1) if elapsed > 0 else 0})
        if inter_batch_delay > 0:
            DBOS.sleep(inter_batch_delay)

    if with_fundamentals and fetched and not bf._cancel.is_set():
        with bf._lock:
            bf._progress[market]['phase'] = 2
        for i in range(0, len(fetched), PHASE2_CHUNK):
            if bf._cancel.is_set():
                break
            _phase2_step(market, fetched[i:i + PHASE2_CHUNK], suffix, is_inr, max_workers)

    elapsed = time.time() - started
    result = {'market': market, 'total': total, 'done': done, 'errors': errors,
              'written': written, 'elapsed_s': round(elapsed, 1),
              'status': 'cancelled' if bf._cancel.is_set() else 'done',
              'rate_per_min': round(total / elapsed * 60, 1) if elapsed > 0 else 0}
    with bf._lock:
        bf._progress[market] = result
    log.info('bulk_fetcher_dbos: [%s] %s — %d written in %.0fs',
             market, result['status'], written, elapsed)
    return result


def run_market(market: str, batch_size: int, max_workers: int,
               with_fundamentals: bool, inter_batch_delay: float) -> dict:
    wid = f"bulk-{market}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}"
    with SetWorkflowID(wid):
        return fetch_market_workflow(market, batch_size, max_workers,
                                     with_fundamentals, inter_batch_delay)
