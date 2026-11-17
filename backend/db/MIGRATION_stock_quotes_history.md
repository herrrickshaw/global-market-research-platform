# Migration: preserving quote history

**Status:** implemented and verified against a live Cassandra 5.x node
(2026-08-15). Rollout steps 1–3 and 5 done; step 4 (a week of scheduled runs)
outstanding. Verification data was truncated afterwards, so the table is empty
and awaiting its first real scheduled snapshot.
**Touches:** `schema.cql`, `cassandra_client.py`, `quote_updater.py`, `scheduler.py`
**Breaks:** nothing (additive)

## Problem

`stock_quotes` is keyed `PRIMARY KEY (market, yf_ticker)` — one row per instrument,
overwritten in place. Every derived value it carries (RSI, MACD, Bollinger bands, ATR,
stochastics, six return horizons, PE/PB/ROE/OPM) exists only at its latest value. The
moment the next fetch lands, the previous state is gone.

That makes a whole class of question unanswerable: *how did this signal look 30 days
ago?* You cannot backtest the scanner against its own historical inputs, only re-derive
them by re-fetching from yfinance, which is slow, rate-limited, and — for fundamentals —
not point-in-time at all (yfinance serves current PE, not the PE as of a past date).

`price_history` already solves this correctly for close price: `PRIMARY KEY (yf_ticker,
price_date) WITH CLUSTERING ORDER BY (price_date DESC)`. The fix is to give the quote
table the same treatment. It is *not*, however, as simple as re-keying it.

## Why re-keying `stock_quotes` is the wrong move

The obvious change — `PRIMARY KEY ((market, yf_ticker), fetched_at)` — breaks three
readers, because all three depend on `market` being the *entire* partition key:

| Caller | Query | Breaks how |
|---|---|---|
| [`quote_updater.py:282`](quote_updater.py:282) `get_market_quotes_df()` | `SELECT … WHERE market = ?` | Daily-scan hot path. One partition read becomes N per-ticker partition reads — 7,442 round trips for `us`. |
| [`cassandra_router.py:45`](../routers/cassandra_router.py:45) | `SELECT COUNT(*) … WHERE market = ?` | `/api/db/status` |
| [`cassandra_router.py:507`](../routers/cassandra_router.py:507) | `SELECT COUNT(*) … WHERE market = ?` | DB management page |

Under a composite partition key, `WHERE market = ?` is a *partial* partition key and
Cassandra rejects the query outright — it does not degrade, it errors, and only
`ALLOW FILTERING` (a full cluster scan) would satisfy it.

The current shape is not an accident. "Give me every quote in this market" is exactly
the query `PRIMARY KEY (market, yf_ticker)` is built for, and it is the single hottest
read in the app. Re-keying trades a well-modelled serving table for a badly-modelled one.

## Design: two tables, not one re-key

Keep `stock_quotes` byte-for-byte as it is — it is the serving layer, and it is correct.
Add an append-only companion:

```cql
CREATE TABLE IF NOT EXISTS stock_quotes_history (
    market         text,
    yf_ticker      text,
    snapshot_date  date,
    fetched_at     timestamp,     -- provenance: when the underlying data was pulled
    cmp            double,
    ...                            -- same 38 value columns as stock_quotes
    PRIMARY KEY ((market, yf_ticker), snapshot_date)
) WITH CLUSTERING ORDER BY (snapshot_date DESC);
```

This is the same query-driven denormalization already applied to
`instruments` / `_by_symbol` / `_by_name` / `_by_isin`: one table per access path,
redundancy accepted deliberately. Two access paths, two tables.

- `stock_quotes` — "everything in market M, now" → one partition read
- `stock_quotes_history` — "ticker T over time" → one partition read, `snapshot_date DESC`

**Clustering on `snapshot_date` (a `date`), not `fetched_at` (a `timestamp`).** This
makes the write idempotent: re-running a snapshot for the same day overwrites that day's
row instead of appending a duplicate. It matters because `scheduler.py` sets
`misfire_grace_time=3600`, so a late fire is a normal, expected event. `fetched_at` is
retained as a plain column for provenance.

## The constraint that decides the write path

`upsert_quotes` does **not** write whole rows. It binds `UNSET_VALUE` for absent
columns, documented at length in [`quote_updater.py:152-176`](quote_updater.py:152):
a Phase-1 price fetch and a Phase-2 fundamentals fetch each contribute only their own
columns, and omitted columns are skipped rather than tombstoned. A row in `stock_quotes`
is therefore an **accumulated merge** of many partial writes, not the product of any
single one.

This rules out the naive approach of dual-writing from inside `upsert_quotes`. In an
append-only table, each write creates a *new* row, and `UNSET` columns in a new row are
simply absent — they do not inherit from the previous row. Dual-writing would produce a
history of half-rows: price rows with no fundamentals, fundamentals rows with no prices.
Useless for backtesting, and the failure would be silent.

**So: snapshot after merge, not dual-write.** Take an explicit end-of-run snapshot that
reads the merged serving rows back and appends them as one complete row per ticker per
day. Conveniently, the efficient read for this already exists — `WHERE market = ?` is one
partition read, which is precisely the access pattern we are preserving by not re-keying.

Cost per run: ~6 partition reads (one per market) + ~17.5k writes. Negligible next to the
20–40 minute fetch that precedes it.

## Code changes

**1. `cassandra_client.py`** — add the `CREATE TABLE` to `_SCHEMA`. Nothing goes in
`_MIGRATIONS`; this is a new table, not an alteration.

**2. `quote_updater.py`** — add a prepared `snapshot` insert and:

```python
def snapshot_market(market: str, day: date | None = None) -> int:
    """
    Append the current merged serving row for every ticker in `market` to
    stock_quotes_history. Idempotent per (ticker, day).
    Blocking — dispatch from a background thread.
    """
```

It reads `stock_quotes WHERE market = ?` and re-binds each row. Note it must bind plain
values, **not** `UNSET_VALUE` — a null in the serving row is a genuine "not known on this
date" and should be recorded as such. The append-bias trade-off documented for
`upsert_quotes` applies to the serving row only; history rows are immutable facts about a
day and should be written literally.

**3. `scheduler.py`** — call `snapshot_market(m)` for each market at the end of
`_run_prefetch()`, after `fetch_all_quotes()` returns, inside the existing try block.
Snapshot only from the scheduled batch. Do **not** snapshot from
[`live.py:108`](../routers/live.py:108) — ad-hoc `/api/live/fetch` calls run on partial
symbol lists and would write partial days into history.

**4. Factor the column list.** It is currently spelled out in three places
(`_stmts['upsert']`, `_stmts['select_in']`, `get_market_quotes_df`) and this change would
make it five. Pull the 41 names into one module-level tuple and build the CQL from it.
The tombstone incident of 2026-07-29 was a column-handling bug; five hand-maintained
copies of the same list is the same class of hazard.

## Sizing

Using the instrument counts in `CLAUDE.md` (india 2,368 · us 7,442 · europe 1,214 ·
japan 3,709 · korea 2,768) ≈ **17.5k instruments**, at ~250 trading days/year:

- **~4.4M rows/year.**
- At ~400 B/row (41 columns, mostly doubles, plus row overhead) ≈ **~1.8 GB/year raw**,
  perhaps 0.6–0.9 GB/year after Cassandra's default LZ4. RF=1, so no replication multiple.
- **Partition size: ~250 rows/year**, ~100 KB/year. Cassandra's guidance is <100 MB and
  <100k rows per partition — this reaches neither within any horizon worth planning for.

**Measured 2026-08-15** (one full day, all 5 markets, `nodetool tablestats` after `flush`):

| | estimated | measured |
|---|---|---|
| instruments/day | 17.5k | **21,198** (india 3,484 · us 9,458 · europe 1,826 · japan 3,664 · korea 2,766) |
| bytes/row (raw) | ~400 B | **385 B** |
| bytes/row (on disk) | — | **249 B** (LZ4 ratio 0.65) |
| per year | ~1.8 GB raw | **1.90 GiB raw · 1.23 GiB on disk** |
| partition after 10y | — | **0.59 MiB / 2,500 rows** (limits: 100 MiB / 100k rows) |

The per-row estimate was close; the annual figure landed near the estimate despite 21%
more instruments than `CLAUDE.md` documents. Write throughput was ~4,500 rows/s
(21,198 rows across 5 markets in 4.5s total). No TTL needed at this rate.

No TTL is proposed. The whole point is retention. If storage becomes a concern, a TTL on
`stock_quotes_history` is the lever, but ~1 GB/year does not warrant one yet.

## What this does and does not fix

**Does:** every quote the pipeline computes becomes recoverable at daily granularity.
Signal backtesting against real historical inputs becomes possible for the first time.

**Does not: the `live.py` clobber.** [`live.py:102-108`](../routers/live.py:102)
fire-and-forgets `upsert_quotes` into the same serving row the nightly batch writes, with
no ordering guarantee. An ad-hoc `/api/live/fetch` on a partial symbol list still
overwrites that market's batch values mid-session. The history table makes this
*visible and recoverable* — you can see what the batch wrote and restore it — but the
serving row is still last-write-wins. Fixing that is a separate change (gate the live
write, or make it conditional on freshness). Do not let this migration create the
impression the clobber is handled.

## Backfill

Day one of the history table is the day it ships. There is nothing to migrate — that is
the cost of not having had it. Partial reconstruction is possible but is a separate
effort, and the columns differ sharply in recoverability:

- **Technicals** (RSI, EMA, MACD, Bollinger, ATR, stochastics, returns) — recoverable.
  All are pure functions of the price series, and the OHLCV panels exist
  (`market-pipeline` `assembled_long.parquet`, Postgres `market_data.public.ohlcv_history`).
- **`cmp`, `high_52w`, `low_52w`, `volume`** — recoverable from the same panels.
- **Fundamentals** (PE, PB, ROE, OPM, EPS, D/E, revenue growth) — **not** recoverable from
  price data, and yfinance will not serve them point-in-time. The nearest sources are
  Postgres `global_fundamentals` and the screener.in history collector.
- **`sector`, `industry`** — effectively static; today's values are fine for past dates.

## Known limitation: cross-sectional backtests

This table answers *"ticker T across time"* in one partition read. It answers
*"every ticker as of date D"* only as N partition reads — ~17.5k per date. A backtest
sweeping the full universe over a year would be millions of round trips. Cassandra is the
wrong engine for that shape.

The right move for full-universe work is a periodic columnar export of
`stock_quotes_history` to Parquet/DuckDB — which is the path already in the stack
(`duckdb>=1.4.0` is in `requirements.txt`). Build the table for retention and single-name
history; export for cross-sectional analysis. Deciding this now avoids discovering it
after the first slow backtest.

## Rollout

1. ~~Add the table to `_SCHEMA` and `schema.cql`.~~ **Done.** Restart picks it up; existing
   tables are `IF NOT EXISTS` no-ops.
2. ~~Ship `snapshot_market()` and call it manually for one market.~~ **Done** — verified one partition:
   `SELECT snapshot_date, cmp, rsi, pe FROM stock_quotes_history WHERE market='india' AND yf_ticker='RELIANCE';`
3. ~~Confirm null-vs-value handling — a partial day must show real prices and null
   fundamentals, not the previous day's carried forward.~~ **Done** — all 3,484 india
   rows compared field by field against the serving table (132,392 values), 0 mismatches;
   the 1,117 rows with no `cmp` recorded `cmp`/`rsi` as null rather than filled.
4. ~~Wire into `_run_prefetch()`.~~ **Done** — snapshot count surfaces as
   `total_snapshotted` in `/api/db/scheduler/status`. **Still needs a week of real
   scheduled runs**; that requires the FastAPI app to be running, which it currently
   is not (hence the 17-day-stale serving table).
5. ~~Re-check sizing against `nodetool tablestats`~~ **Done** — see Sizing above; estimate held, no TTL needed.

### Found during live verification

Two things a stubbed session could not have caught:

**1. `cassandra.util.Date` has no `.isoformat()`.** The driver returns its own type for a
CQL `date` column, so `get_quote_history()` raised `AttributeError` on the first real
read. Fixed by using `str()`, which yields ISO for both that type and `datetime.date`.

**2. Stale serving data would have been recorded as a fresh observation.** The serving
table was 17 days old (every row `fetched_at = 2026-07-29`; the FastAPI app, and so the
scheduler, had not run). The first snapshot happily wrote all 21,198 rows under
`snapshot_date = 2026-08-15` — a fabricated observation that no backtest could distinguish
from a real one. `snapshot_market()` now skips rows whose `fetched_at` is older than
`max_age_days` (default 2) before `day`, or absent. A gap in history is honest; a
duplicated stale row is not. Boundary-tested at 1, 2 and 3 days.

### Unrelated data-quality finding

While verifying null handling, the fundamentals in `stock_quotes` turned out to carry a
single repeated value across a large share of every market:

| market | most common `pe` | share | most common `roe` | share | rows with no `cmp` |
|---|---|---|---|---|---|
| india | 27.942288 | 35% | 9.0 | 54% | 1,117 (32%) |
| us | 17.208014 | 53% | 5.179009 | 27% | 3,023 (32%) |
| europe | 20.327778 | 45% | 10.48693 | 33% | 836 (46%) |
| japan | 14.234 | 16% | 7.7846 | 18% | 21 |
| korea | 10.6995 | 45% | 2.6002 | 10% | 9 |

A distinct constant per market applied to 16–53% of rows is the signature of
median-imputation, not observed data — and nothing in the schema distinguishes an imputed
value from a real one. The Darvas/Buffett ROE-PE overlay and Piotroski consume these as
if observed. **This predates the migration and is not caused by it**, but the history
table will now record imputed values permanently and indistinguishably. Worth resolving
before a long history accumulates — either stop imputing, or add a flag column.

### Regression guard

The column list is now generated from `_VALUE_COLS` / `_QUOTE_COLS` in `quote_updater.py`,
and both tables must agree with it. To re-check after any schema change, assert that:
`_QUOTE_COLS` matches the positional bind order in `upsert_quotes`; `_VALUE_COLS` equals
the non-key columns of *both* `stock_quotes` and `stock_quotes_history`; those columns
carry identical types in both; and `schema.cql` matches `cassandra_client._SCHEMA` plus
`_MIGRATIONS`. All four held at implementation time.

**Rollback** is `DROP TABLE stock_quotes_history` plus reverting the `scheduler.py` call.
Nothing else reads it, and `stock_quotes` is untouched throughout — the serving path
cannot regress, which is the main argument for this shape over a re-key.
