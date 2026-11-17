# market-calendar-core

The trading-day calendar that existed five times.

The cross-repo knowledge graph flagged `is_trading_day` and `trading_days` as
"the same symbol in 8 repos". Reading the code showed they were **not the same
function** — three different implementations shared those two names, with
incompatible signatures:

```python
india_live.is_trading_day(d, holidays=None)   # no market argument at all
markets.is_trading_day(market, d, hol=None)   # ISO codes:  IN, US, JP, SA
computed.is_trading_day(market, d)            # words:      India, US, Japan
```

Calling the wrong one returns a wrong answer instead of raising. That is why
this package deliberately **exports nothing at top level** — you import the
module you mean.

## The three modules

| module | scope | method | extracted from |
|---|---|---|---|
| `india_live` | India (NSE/BSE) only | live `nsepython` list, cached, unioned with a hardcoded fallback | market-pipeline, global-market-data, global-stock-screener, stock-screener-platform |
| `markets` | 19 markets | static tables + per-market weekend rules; delegates `IN` to `india_live` | global-market-data, global-stock-screener |
| `computed` | 5 market groups | Easter algorithm + fixed dates + curated movable list; pandas; accepts exchange aliases | BazaarTalks, global-market-scanners |

`markets` and `computed` are **not** interchangeable. They disagree on
vocabulary (`"IN"` vs `"India"`) and on method (tabled vs computed), so they can
return different answers for the same date. Moving a caller from one to the
other is a behaviour change that needs its own test — not a find-and-replace.

## What differed between the copies

Almost nothing, which is what made the extraction safe:

- **Family A** (`market_calendar.py`) — the four copies differed only in `black`
  formatting and the default cache path. Holiday data and logic were identical.
- **Family B2** (`market_holidays.py`, table-driven) — the logic block was
  **byte-identical** (1,804 B) across both repos; only the data table's
  formatting differed. Same 395 dates, same 19 market keys.
- **Family B1** (`market_holidays.py`, computed) — the two copies were
  byte-identical.

The one deliberate change: the shared cache default. market-pipeline used
`~/market-pipeline/data/bhavcopy_cache`, global-market-data used
`~/Downloads/data/bhavcopy_cache`. Neither works as a shared default, and the
Downloads tree is scratch space other processes wipe. It now defaults to
`~/.cache/market-calendar/`, with the `BHAV_CACHE` env override unchanged. A
cache miss is harmless — the hardcoded fallback list still applies — so callers
relying on either old default keep working.

## Install

```bash
pip install -e ~/market-calendar                 # india_live + markets, stdlib only
pip install -e "~/market-calendar[computed]"     # adds pandas for computed
pip install -e "~/market-calendar[live,test]"    # nsepython + pytest
```

`india_live` works without `nsepython` installed — it falls back to the
hardcoded holiday list rather than raising.

## Use

```python
import datetime as dt
from market_calendar_core import india_live, markets, computed

india_live.is_trading_day(dt.date(2026, 1, 26))          # False — Republic Day
markets.is_trading_day("SA", dt.date(2026, 1, 4))        # True  — Saudi trades Sunday
markets.next_trading_day("JP", dt.date(2026, 1, 1))
computed.trading_days("NYSE", "2026-01-01", "2026-12-31")  # DatetimeIndex
```

## Equivalence is tested, not asserted

`tests/test_equivalence.py` loads **every original copy still on disk**, by file
path, and compares against the extracted module over a 730-day range across all
markets — holiday tables, weekend rules, `next_`/`last_trading_day`, and the
India fallback set. A repo that has been moved is skipped loudly, never silently
passed. No network: the tests pass explicit holiday sets rather than calling the
live NSE fetch.

```bash
cd ~/market-calendar && python3 -m pytest -q     # 22 passed
```

The last test pins the incompatibility itself: if the three signatures ever
converge, it fails and this README needs rewriting.

## Migration status

**Nothing has been migrated yet.** This package is the extracted layer; the five
original copies are still in place and still authoritative. Adopting it in a repo
means installing the package, swapping the import, and re-running that repo's own
tests — one repo at a time, starting with one that is not the live daily pipeline.
