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
