#!/usr/bin/env python3
"""
yfinance gap-filler, global markets (korea/china/japan/europe/australia/
canada/taiwan/hongkong). Work list: scratchpad/remaining_global.csv
(market,yf_ticker — already yfinance-format).

Same extraction + guards as yf_gap_filler.py. Checkpoints to
yf_gap_global_results.csv (restartable). At merge time only columns that are
NULL in Cassandra get written, so official statement-derived values are never
overwritten by yfinance approximations.
"""

import csv
import time
from pathlib import Path

import yfinance as yf
from yfinance.exceptions import YFRateLimitError
import sys
sys.path.insert(0, '/Users/umashankar/market-pipeline')
from yf_gap_filler import extract, FIELDS

SCRATCH = Path('/private/tmp/claude-501/-Users-umashankar/fce772c6-1b5d-436e-a845-f7e0585e07e4/scratchpad')
CHECKPOINT = SCRATCH / 'yf_gap_global_results.csv'


def fetch_one(market, ticker, base_delay=0.8):
    """Row, None (dead), or raises YFRateLimitError (NOT checkpointed)."""
    try:
        for attempt in range(3):
            try:
                info = yf.Ticker(ticker).info
                if info and len(info) > 5:
                    return extract(info, market, ticker)
                return None
            except YFRateLimitError:
                if attempt == 2:
                    raise
                time.sleep(120 * (attempt + 1))
            except Exception:
                return None
    finally:
        time.sleep(base_delay)
    return None


def main():
    done = set()
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            for r in csv.DictReader(f):
                done.add((r['market'], r['yf_ticker']))
        print(f"Resuming: {len(done)} already fetched", flush=True)

    work = []
    with open(SCRATCH / 'remaining_global.csv') as f:
        for r in csv.DictReader(f):
            if (r['market'], r['yf_ticker']) not in done:
                work.append((r['market'], r['yf_ticker']))
    print(f"To fetch: {len(work)} tickers", flush=True)

    mode = 'a' if CHECKPOINT.exists() else 'w'
    out = open(CHECKPOINT, mode, newline='')
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    if mode == 'w':
        writer.writeheader()

    # serial — parallel bursts trip Yahoo's limiter and poison the checkpoint
    fetched = empty = ratelimited = 0
    t0 = time.time()
    for i, (m, t) in enumerate(work, 1):
        try:
            row = fetch_one(m, t)
        except YFRateLimitError:
            ratelimited += 1
            print(f"  rate-limited at {m}:{t} — backing off 10m", flush=True)
            time.sleep(600)
            continue  # not checkpointed; retried on next run
        if row and len(row) > 2:
            writer.writerow(row)
            fetched += 1
        else:
            writer.writerow({'market': m, 'yf_ticker': t})
            empty += 1
        if i % 200 == 0:
            out.flush()
            rate = i / (time.time() - t0)
            eta = (len(work) - i) / rate / 3600
            print(f"  {i}/{len(work)} | data: {fetched} empty: {empty} "
                  f"rl: {ratelimited} | {rate:.2f}/s | ETA {eta:.1f}h", flush=True)
    out.close()
    print(f"DONE: {fetched} with data, {empty} empty, {ratelimited} rate-limited "
          f"of {len(work)}", flush=True)


if __name__ == '__main__':
    main()
