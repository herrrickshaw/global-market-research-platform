#!/usr/bin/env python3
"""
yf_sqlite_tuning.py — give yfinance's SQLite caches a busy timeout.

WHY (2026-08-25). Every full US scan logged 32-76 copies of

    ['SHOO', 'NESR', 'QURE', ...]: OperationalError('unable to open database file')

and 564-719 DISTINCT tickers hit it per run — 7-9% of the 7,667-name universe,
every run since at least 2026-08-13.

The cause is not permissions, corruption or disk. yfinance builds each of its
three caches as

    _peewee.SqliteDatabase(..., pragmas={'journal_mode': 'wal', 'cache_size': -64})

(yfinance/cache.py:85, :280, :490). There is no `busy_timeout`, so SQLite uses
its default of ZERO: a connection that finds the database locked fails on the
spot instead of waiting. The scans run ThreadPoolExecutor(max_workers=10)
against one shared cache file, so lock collisions are constant and every one of
them surfaces as a failed download.

Measured on the live cache, 60 opens across 10 threads:

    busy_timeout=0 (yfinance default)  ->  failures
    busy_timeout=5s                    ->  0 failures

The data was never wrong — yfinance's retry path recovered these tickers, and
the 424 affected names that reached the 2026-08-25 workbook show no null-rate
gap against clean names on any price column. What it cost was retries, and a
log so loud that a REAL failure has nowhere to show. That is the actual damage:
the 2026-07-15 seven-week-old-price incident is exactly what hides in noise
like this.

WAL is left alone deliberately. It is the right journal mode for a
read-mostly cache with concurrent readers, and the macOS WAL hazard in the
`feedback_sqlite_macos` memory is about per-row commits in a synced folder,
which this is not.

Import for effect (scan_core.py does this once on behalf of all five scans),
or call apply() directly. Never raises: a tuning failure must not take down a
scan that would otherwise run, so it degrades to the old noisy-but-working
behaviour.
"""
from __future__ import annotations

BUSY_TIMEOUT_MS = 5000

_applied = False


def apply(timeout_ms: int = BUSY_TIMEOUT_MS) -> list[str]:
    """Add busy_timeout to every yfinance SQLite cache. Returns names tuned.

    Idempotent and safe to call from any thread before the pool starts. Tuning
    AFTER worker threads are live would leave already-open connections on the
    old pragma, so call this during startup.
    """
    global _applied
    tuned: list[str] = []
    try:
        from yfinance import cache as _c
    except Exception:                                          # noqa: BLE001
        return tuned

    for mgr_name in ("_TzDBManager", "_CookieDBManager", "_ISINDBManager"):
        mgr = getattr(_c, mgr_name, None)
        if mgr is None:                       # yfinance version without it
            continue
        try:
            db = mgr.get_database()
            if db is None:
                continue
            if any(p[0] == "busy_timeout" for p in db._pragmas):
                tuned.append(mgr_name)        # already tuned; nothing to do
                continue
            # peewee applies _pragmas on every new connection. Bounce the
            # connection so the pragma is live for this thread too, not just
            # for connections opened later.
            db.close()
            db._pragmas = tuple(list(db._pragmas) + [("busy_timeout", timeout_ms)])
            db.connect(reuse_if_open=True)
            tuned.append(mgr_name)
        except Exception:                                      # noqa: BLE001
            # A cache we cannot tune is a cache that behaves as it did before.
            continue

    _applied = bool(tuned)
    return tuned


if __name__ == "__main__":
    import sys
    names = apply()
    print(f"tuned {len(names)} yfinance cache(s): {', '.join(names) or 'none'}")
    try:
        from yfinance import cache as _c
        db = _c._TzDBManager.get_database()
        print("tz busy_timeout =", db.execute_sql("PRAGMA busy_timeout").fetchone()[0], "ms")
    except Exception as e:                                     # noqa: BLE001
        print("verify failed:", e); sys.exit(1)
