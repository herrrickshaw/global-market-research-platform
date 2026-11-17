"""
iter_utils.py — small higher-order-function utilities factoring out a
pattern that had independently grown three near-identical copies across
this session's collector scripts (yf_intl_pit_fundamentals.py,
weekly_extended_scan.py): "for item in items: try: fn(item) except:
print and keep going", sometimes with a consecutive-failure circuit
breaker on top. Centralizing it here means a future collector reuses it
instead of writing the same try/except scaffolding a fourth time, and a
fix (like the missing-catch bug this pass found — see
for_each_fail_soft's docstring) only needs to happen once.

    from_iter_utils import for_each_fail_soft, with_circuit_breaker, parallel_map
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def for_each_fail_soft(items: Iterable[T], fn: Callable[[T], R],
                        label: Callable[[T], str] = str) -> dict:
    """Run fn(item) for every item; one item's exception never stops the
    rest. Returns {item: result}, failed items mapped to None.

    Replaces a real latent bug found while extracting this:
    yf_intl_pit_fundamentals.py's CLI `--market ALL` collect loop had NO
    try/except at all around each market's collect() call — an
    unexpected exception from market #3 (e.g. a corrupt local cache file)
    would have silently aborted markets #4 through #15 with no message,
    losing an already-in-progress run's remaining progress for no reason
    related to those other markets."""
    results = {}
    for item in items:
        try:
            results[item] = fn(item)
        except Exception as e:  # noqa: BLE001 — isolation is the whole point
            print(f"[{label(item)}] FAILED: {e}", file=sys.stderr)
            results[item] = None
    return results


def with_circuit_breaker(items: Iterable[T], fn: Callable[[T], R], *,
                          limit: int = 15, sleep_s: float = 0.0,
                          label: Callable[[T], str] = str) -> list:
    """Same fail-soft semantics as for_each_fail_soft, but ALSO stops the
    whole run after `limit` CONSECUTIVE failures — the signal of a real
    rate limit/block, as distinct from scattered delisted-symbol misses
    that should NOT abort a run early. Returns [(item, result), ...] for
    every item actually attempted before any early stop (a trailing
    subset of `items` if the breaker tripped)."""
    done, consecutive_failures = [], 0
    for item in items:
        try:
            done.append((item, fn(item)))
            consecutive_failures = 0
        except Exception as e:  # noqa: BLE001
            consecutive_failures += 1
            print(f"  ERROR {label(item)}: {e}", file=sys.stderr)
            if consecutive_failures >= limit:
                print(f"  {consecutive_failures} consecutive failures — stopping "
                      f"(possible rate limit/block, not assumed without this check)",
                      file=sys.stderr)
                break
        if sleep_s:
            time.sleep(sleep_s)
    return done


def parallel_map(items: Iterable[T], fn: Callable[[T], R], *,
                  max_workers: int = 4, label: Callable[[T], str] = str) -> dict:
    """Bounded-concurrency version of for_each_fail_soft — for LOCAL,
    non-rate-limited work (disk reads, CPU-bound parsing) where a modest
    worker pool gives a real wall-clock win from overlap.

    Deliberately NOT used for yfinance-backed collection in this
    codebase: raising concurrency there was tested live 2026-07-31 (an
    ad hoc smoke test colliding with a running weekly scan job) and
    produced real YFRateLimitError responses — more concurrent requests
    made the SAME time-windowed limiter trip sooner, not the total job
    finish faster. Use with_circuit_breaker + a paced time.sleep for
    anything hitting yfinance; reach for this only where the per-item
    work has no shared external rate limit to contend with."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fn, item): item for item in items}
        for fut in as_completed(futures):
            item = futures[fut]
            try:
                results[item] = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"[{label(item)}] FAILED: {e}", file=sys.stderr)
                results[item] = None
    return results
