#!/usr/bin/env python3
"""
yfinance gap-filler for Cassandra symbols with no local fundamentals source.

- US: remaining 4,858 tickers as-is (includes ETFs — whatever fields yfinance
  returns get written; ETFs typically yield dividend_yield + market_cap only).
- India: remaining 1,105 bare symbols, tried as .NS then .BO.

Checkpoints every ticker to a CSV so the run is restartable; emits CQL at the
end. Fields from Ticker.info: trailingPE, priceToBook, returnOnEquity,
operatingMargins, marketCap, dividendYield, debtToEquity (yfinance reports
percent — /100 when >10), currentRatio, trailingEps, revenueGrowth,
earningsGrowth, sector, industry.
"""

import csv
import math
import os
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

SCRATCH = Path('/private/tmp/claude-501/-Users-umashankar/fce772c6-1b5d-436e-a845-f7e0585e07e4/scratchpad')
CHECKPOINT = SCRATCH / 'yf_gap_results.csv'
FIELDS = ['market', 'yf_ticker', 'pe', 'pb', 'roe', 'opm', 'market_cap',
          'dividend_yield', 'debt_to_equity', 'current_ratio', 'eps',
          'revenue_growth', 'eps_growth', 'sector', 'industry']


def fnum(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def in_range(v, lo, hi):
    return v is not None and lo <= v <= hi


def extract(info, market, yf_ticker):
    row = {'market': market, 'yf_ticker': yf_ticker}
    pe = fnum(info.get('trailingPE'))
    if in_range(pe, 0.5, 2000):
        row['pe'] = pe
    pb = fnum(info.get('priceToBook'))
    if in_range(pb, 0.05, 200):
        row['pb'] = pb
    roe = fnum(info.get('returnOnEquity'))
    if roe is not None and in_range(roe * 100, -500, 500):
        row['roe'] = roe * 100
    opm = fnum(info.get('operatingMargins'))
    if opm is not None and in_range(opm * 100, -300, 100):
        row['opm'] = opm * 100
    mc = fnum(info.get('marketCap'))
    if in_range(mc, 1e6, 1e16):
        row['market_cap'] = mc
    dy = fnum(info.get('dividendYield'))
    if dy is not None:
        # yfinance flips between fraction and percent across versions;
        # values <= 1 are treated as fractions
        dy = dy * 100 if dy <= 1 else dy
        if in_range(dy, 0, 50):
            row['dividend_yield'] = dy
    de = fnum(info.get('debtToEquity'))
    if de is not None:
        de = de / 100 if de > 10 else de
        if in_range(de, 0, 50):
            row['debt_to_equity'] = de
    cr = fnum(info.get('currentRatio'))
    if in_range(cr, 0, 100):
        row['current_ratio'] = cr
    eps = fnum(info.get('trailingEps'))
    if eps is not None and in_range(abs(eps), 0.01, 1e6):
        row['eps'] = eps
    rg = fnum(info.get('revenueGrowth'))
    if rg is not None and in_range(rg * 100, -95, 1000):
        row['revenue_growth'] = rg * 100
    eg = fnum(info.get('earningsGrowth'))
    if eg is not None and in_range(eg * 100, -95, 1000):
        row['eps_growth'] = eg * 100
    for k, col in (('sector', 'sector'), ('industry', 'industry')):
        v = info.get(k)
        if v and isinstance(v, str):
            row[col] = v.strip()
    return row


from yfinance.exceptions import YFRateLimitError


def fetch_one(market, ticker, base_delay=1.2):
    """Returns extracted row, None (dead ticker), or raises YFRateLimitError
    after retries so the caller does NOT checkpoint it as tried.
    India bare symbols try .NS then .BO."""
    candidates = [ticker]
    if market == 'india':
        candidates = [ticker + '.NS', ticker + '.BO']
    for cand in candidates:
        for attempt in range(3):
            try:
                info = yf.Ticker(cand).info
                # accept any non-trivial response (ETFs lack PE/sector but
                # may still yield dividend_yield / market_cap)
                if info and len(info) > 5:
                    return extract(info, market, ticker)
                break  # empty-but-valid response -> try next candidate
            except YFRateLimitError:
                if attempt == 2:
                    raise
                time.sleep(120 * (attempt + 1))
            except Exception:
                break  # 404 etc -> next candidate
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
    for market in ('india', 'us'):
        for t in open(SCRATCH / f'remaining_{market}.txt').read().split('\n'):
            t = t.strip()
            if t and (market, t) not in done:
                work.append((market, t))
    print(f"To fetch: {len(work)} tickers", flush=True)

    mode = 'a' if CHECKPOINT.exists() else 'w'
    out = open(CHECKPOINT, mode, newline='')
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    if mode == 'w':
        writer.writeheader()

    # SERIAL with generous pacing — Yahoo rate-limits aggressively; a
    # parallel burst poisons hours of fetches. Rate-limited tickers are NOT
    # checkpointed, so a re-run retries them.
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
            writer.writerow({'market': m, 'yf_ticker': t})  # dead ticker
            empty += 1
        if i % 50 == 0:
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
