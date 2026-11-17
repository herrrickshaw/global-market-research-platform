# Avoiding rate-limits and geo-blocks (data collection)

Field notes on getting data reliably without being throttled. Ordered by leverage — the
first two solved our actual blockers.

## 1. Route around geo-blocks with a *different provider* (biggest win)

The block is often on the **provider**, not the data. China's Eastmoney bulk snapshot
(`ak.stock_zh_a_spot_em`) fails with `ConnectionError` from non-China IPs — geo-throttled.
**baostock.com is a different provider, not blocked**, free, no key, and returns *more*
(epsTTM, roeAvg, netProfit, **pubDate** = real filing date) for the whole A-share universe.

| blocked | use instead |
|---|---|
| akshare Eastmoney bulk (CN) | **baostock** (`cn_baostock_collect.py`) — 10y, PIT dates, no throttle |
| J-Quants Premium (JP, paid) | **EDINET-Bench** HF parquets (no key) + **yfinance** (breadth) |
| EDINET API (needs key) | EDINET-Bench pre-parsed dataset |

*Lesson: before fighting a rate-limit, check whether another library reaches the same
underlying filings from a different host.*

## 2. Impersonate a real browser (yfinance)

Yahoo rate-limits requests that don't look like a browser. **`curl_cffi` with
`impersonate="chrome"`** makes yfinance requests indistinguishable from Chrome, sidestepping
most 429/"Invalid Crumb" limiting:

```python
from curl_cffi import requests as cffi
sess = cffi.Session(impersonate="chrome")
yf.Ticker("7203.T", session=sess)          # wired into jp_yf_breadth.py
```

## 3. Persistent socket / session (avoid per-request handshakes)

baostock logs in once and reuses a socket for thousands of queries — no TCP+TLS handshake
per call, so it's fast *and* invisible to per-request rate counters. Reuse a
`requests.Session()` (or curl_cffi session) rather than a fresh connection each call.

## 4. Shard parallelism from one IP (when per-ticker is unavoidable)

Split the ticker list N ways (`index % N == shard_id`), run N workers each writing its own
file, then merge (`cn_shards_run.sh`). ~N× throughput as long as the host doesn't IP-throttle
(it didn't for akshare's per-ticker endpoint). Keep N ≤ ~6 to stay under the radar.

## 5. Backoff + jitter + retry

On `ConnectionError`/429: sleep `base * 2**attempt` plus a small random jitter, retry a few
times, then skip and move on. Never hammer a failing host in a tight loop.

## 6. Checkpoint + resume

Write partial results every K tickers and skip already-done ones on restart. Turns a fragile
multi-hour job into something that survives deaths (all our collectors do this).

## 7. Off-peak scheduling

Fetch when the source market is closed and traffic is low — yfinance US data 03:00–07:00 IST
(post-US-close), China after 12:30 IST. Documented per source in
[`DATA_SOURCES.md`](DATA_SOURCES.md).

## 8. Prefer bulk endpoints when they exist and aren't blocked

One call for many rows beats N calls. Sina's `ak.stock_zh_a_spot()` returns 5,530 A-shares in
one call (prices only, no ratios) — useful where it isn't blocked; Eastmoney's richer bulk is
blocked, hence baostock per-ticker (still fast on a persistent socket).

---

**Current collectors and their tactic:**
`cn_baostock_collect.py` → different-provider + persistent-socket + checkpoint ·
`jp_yf_breadth.py` → curl_cffi impersonation + jitter + checkpoint ·
`cn_shards_run.sh` → shard parallelism + auto-restart.

> Research pipeline. Not investment advice.
