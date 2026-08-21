# Consumer demand research

Demand signals for physical products, sourced from marketplace search results
rather than from company filings. Built to answer questions of the form "is
there more demand for A or for B, and is the gap big enough to act on".

## `amazon_demand_compare.py`

Compares Amazon demand between product groups. The default comparison is
**moringa oil vs honey**; any groups can be passed on the command line.

```bash
export OPENWEB_NINJA_API_KEY=...
python3 research/consumer_demand/amazon_demand_compare.py --dry-run   # no network
python3 research/consumer_demand/amazon_demand_compare.py             # US, 2 pages
python3 research/consumer_demand/amazon_demand_compare.py --country IN --pages 3
python3 research/consumer_demand/amazon_demand_compare.py \
    --group "moringa oil=moringa oil,moringa seed oil" \
    --group "honey=honey,raw honey,manuka honey"
python3 research/consumer_demand/amazon_demand_compare.py --from-cache  # re-analyse
```

Writes to `reports/`: `amazon_demand_listings.csv` (one row per deduplicated
ASIN), `amazon_demand_summary.csv` (one row per group), and
`amazon_demand_comparison.md` (the verdict, the table, and the caveats).

Raw API responses are cached under `data/amazon_raw/` (gitignored) so the
analysis can be re-run and re-cut without spending quota.

### It cannot run from the Claude Code sandbox

`api.openwebninja.com` is refused by that environment's egress proxy with a 403
on CONNECT — the same organization policy that blocks `api.adzuna.com` for
`research/diaspora/`. Run it anywhere with ordinary internet access.
`--dry-run` exercises every code path except the network call.

### What the numbers mean

Amazon publishes no unit sales. Three proxies are reported side by side rather
than blended, because they measure different quantities on different time
bases:

| Column | Measures | Main weakness |
|---|---|---|
| `units_past_month_floor` | Recent orders, in units | Amazon's "N+ bought in past month" badge is a bucketed **floor**, and only appears on some listings — read `units_coverage_pct` first |
| `est_monthly_revenue_floor` | Recent orders, in money | Inherits the floor above; a high-price niche can out-earn a high-volume staple |
| `cumulative_ratings` | Lifetime category size | Lifetime, not current; only a low single-digit share of buyers rate, and that share varies by category |
| `demand_per_listing` | Demand against competition | The number a prospective seller should care about — a big category split across thousands of listings can be a worse entry than a small one |

Two limits worth stating before anyone quotes a result:

- **Keyword demand is not category demand.** "honey" reaches a grocery staple
  bought on repeat by the general population; "moringa oil" reaches a niche
  cosmetic ingredient. Part of any gap between them is a gap in what the words
  mean, not in the underlying market.
- **A search page is a ranked sample, not a census.** The tool samples the top
  N pages per keyword and unions several keyword variants per group,
  deduplicating by ASIN, which steadies the sample but does not make it
  complete. `total_listings_on_primary_keyword` is the only census-like figure
  and it counts listings, not sales.

## `shortlist.py` — the two combined

Runs the trend read, gates on it, then prices competition only for survivors,
and returns one ranked list.

```bash
export NEXSCOPE_API_KEY=... OPENWEB_NINJA_API_KEY=...
python3 research/consumer_demand/shortlist.py --dry-run
python3 research/consumer_demand/shortlist.py --keywords-file research/consumer_demand/candidates.txt
python3 research/consumer_demand/shortlist.py --min-volume 1000 --max-review-moat 1500
```

Writes `reports/amazon_shortlist.csv` and `.md`.

**Gate first, then rank.** The pipeline does not blend everything into one
number: it applies pass/fail gates, records *why* each rejection failed, and
ranks only survivors. A blended score would let a strong growth number outvote
a disqualifying review moat, and those are not commensurable — no amount of
growth makes a category with 40,000-review incumbents enterable.

The rejected table is usually the more useful half. "Rising, but seasonal" and
"open, but nobody searches for it" are different next actions:

```
--- Shortlist (2 of 6) ---
  1. turmeric soap    score 0.950  (growth 1.00 demand 1.00 openness 1.00 headroom 0.50)
  2. moringa oil      score 0.050  (growth 0.00 demand 0.00 openness 0.00 headroom 0.50)

--- Rejected (4) ---
  shilajit resin   review moat 21,750 above 2,000
  honey            trend is 'flat', not in ['RISING']
  mouth tape       trend is 'seasonal bounce — down year-over-year', not in ['RISING']
  sleep gummies    trend is 'spiky — growth may be noise', not in ['RISING']
```

`shilajit resin` is the case the design exists for: demand genuinely rising, and
the category still not enterable.

Trend runs before competition on purpose — the competition call bills per
listing returned, and roughly half of any candidate list dies on the trend gate.

**The score is relative to the candidate set.** Components are min-max
normalised across the candidates you supply, so adding an eleventh changes the
other ten. `0.9` means "best of what you supplied", never "good in absolute
terms". Compare within a run, never across runs.

`candidates.txt` is a seed universe to run against — read its header first, the
provenance matters.

## `nexscope_keyword_history.py`

Ranks keywords by whether Amazon demand for them is **rising** — the discovery
question, as opposed to the snapshot question the module above answers.

```bash
export NEXSCOPE_API_KEY=...
export NEXSCOPE_PROXY_BASE=https://api.nexscope.ai/
python3 research/consumer_demand/nexscope_keyword_history.py --dry-run
python3 research/consumer_demand/nexscope_keyword_history.py \
    --keywords "moringa oil,raw honey,mouth tape"
python3 research/consumer_demand/nexscope_keyword_history.py \
    --keywords-file candidates.txt --country US --weeks 52
```

Writes `reports/nexscope_keyword_trends.csv` and `.md`, sorted by momentum.

Metrics, and why each one is there:

| Column | What it is | Why |
|---|---|---|
| `growth_per_period_pct` | Least-squares slope of **log** volume | A growth *rate*, so 100→200 and 10,000→20,000 score alike. A linear fit would rank the second 100× higher |
| `momentum_pct` | Last 4 periods vs the 4 before | Search volume is spiky; latest-vs-oldest swings on one reading |
| `yoy_pct` | Latest vs ~52 weeks back | The seasonality control — positive momentum with negative YoY is a trough bounce, not growth |
| `volatility_cv` | Coefficient of variation | Guards the growth numbers; above ~0.6 the trend is inside the noise |
| `opportunity_flag` | A label, not a score | Names *which* test decided the verdict, rather than blending them into one number that hides the reason |

### The schema is assumed

`www.nexscope.ai` is blocked by the sandbox egress proxy, so the docs could not
be read. The endpoint path, auth header and response field names are educated
guesses, and they are isolated so a wrong guess costs a flag rather than an
edit: `--endpoint` / `--auth-header` / `--auth-prefix` override the request
side, and the parser accepts every plausible field name via the `SERIES_KEYS` /
`DATE_KEYS` / `VOLUME_KEYS` tuples. When nothing matches it raises
`SchemaMismatch` **naming the keys the API actually returned** — because a
rigid parser that guessed wrong would return an empty series, and an empty
series reads exactly like "nobody searches for this".

The first live run therefore either works or tells you precisely what to fix.

### Other providers

`DATA_SOURCES.md` surveys the alternatives — Amazon's own Brand Analytics funnel
(real purchases, but your brand only), BSR-based sales estimators (Keepa, Jungle
Scout, Helium 10), the other search-result aggregators (Rainforest, Canopy,
SerpApi, DataForSEO, Bright Data), and free cross-checks like Google Trends. The
aggregators all return the same underlying page, so swapping one in touches
`fetch()` and `products_of()` only — the badge parsing, ASIN dedupe and
coverage-aware scoring are provider-independent.

### Credentials

`OPENWEB_NINJA_API_KEY` is read from the environment only. `tests/test_amazon_demand.py`
scans the tracked tree for the live key's value and for any `ak_…`-shaped
literal, so a key committed by accident fails the suite rather than shipping.
